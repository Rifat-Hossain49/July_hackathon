"""AT-26, AT-27, AT-28 -- durable, crash-safe, recoverable persistence.

Canonical definitions (ACCEPTANCE_TESTS.md):

* **AT-26** a save interrupted after temp write, after temp fsync, after
  replace, and before parent-directory fsync; the reader always sees the
  complete previous or the complete new document, never a blend; temp
  artefacts are ignored and cleaned.
* **AT-27** a truncated temporary file is ignored and removed; the
  previous durable snapshot loads intact; no exception escapes.
* **AT-28** (a) a corrupted document checksum quarantines the file —
  renamed aside, never deleted — and the last good snapshot loads;
  (b) one corrupted fragment with a valid document checksum drops only
  that fragment and preserves the rest.

Runtime boundary: `core/persist`. These tests use real temporary
directories: the behaviour under acceptance *is* filesystem behaviour,
so mocking it away would test nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shongket_core import ErrorCode, ProtocolError, codec
from shongket_core.evidence import EventCode
from shongket_core.persist import (
    STAGE_AFTER_REPLACE,
    STAGE_AFTER_TEMP_FSYNC,
    STAGE_AFTER_TEMP_WRITE,
    STAGE_BEFORE_PARENT_FSYNC,
    SnapshotStore,
    parent_sync_capability,
)
from shongket_core.store import Fragment, FragmentStore


def frag(index: int, payload: bytes, obj: str = "a" * 64) -> Fragment:
    return Fragment(
        object_id=obj,
        representation_id="original",
        chunk_index=index,
        byte_range=(index * 16, index * 16 + len(payload) - 1),
        sha256=codec.sha256_hex(payload),
        payload=payload,
    )


def populated(n: int = 4) -> FragmentStore:
    store = FragmentStore()
    for i in range(n):
        store.put(frag(i, bytes([65 + i]) * 16))
    return store


def save(tmp_path: Path, store: FragmentStore, name: str = "snap.json") -> SnapshotStore:
    snap = SnapshotStore(tmp_path / name)
    snap.save(store, peer_id="peer-A", created_at_unix=1_700_000_000)
    return snap


class Boom(RuntimeError):
    """Injected crash."""


# --- AT-26 crash-safe atomic write ------------------------------------------


@pytest.mark.parametrize(
    "stage, primary_should_be_new",
    [
        (STAGE_AFTER_TEMP_WRITE, False),
        (STAGE_AFTER_TEMP_FSYNC, False),
        (STAGE_AFTER_REPLACE, True),
        (STAGE_BEFORE_PARENT_FSYNC, True),
    ],
)
def test_interruption_never_yields_a_blended_document(
    tmp_path, stage, primary_should_be_new
):
    snap = save(tmp_path, populated(2))
    before = snap.read_document()

    bigger = populated(5)
    with pytest.raises(Boom):
        snap.save(
            bigger,
            peer_id="peer-A",
            created_at_unix=1_700_000_001,
            fault_hook=lambda s: (_ for _ in ()).throw(Boom()) if s == stage else None,
        )

    # A fresh reader must see one complete document, never a mixture.
    reopened = SnapshotStore(snap.path)
    result = reopened.load()
    after = reopened.read_document()

    assert after["document_checksum"] == codec.sha256_hex(
        codec.identity_bytes(after, exclude=("document_checksum",))
    )
    if primary_should_be_new:
        assert len(result.fragments) == 5
        assert after["created_at_unix"] == 1_700_000_001
    else:
        assert len(result.fragments) == 2
        assert after == before

    # Temp artefacts are gone after the crash and after the reopen.
    assert list(tmp_path.glob("*.tmp")) == []


def test_lock_is_released_after_an_interrupted_save(tmp_path):
    snap = save(tmp_path, populated(2))
    with pytest.raises(Boom):
        snap.save(
            populated(3),
            peer_id="peer-A",
            created_at_unix=1_700_000_002,
            fault_hook=lambda s: (_ for _ in ()).throw(Boom())
            if s == STAGE_AFTER_TEMP_WRITE
            else None,
        )
    assert not snap.lock_path.exists()
    # A subsequent save succeeds.
    snap.save(populated(3), peer_id="peer-A", created_at_unix=1_700_000_003)
    assert len(snap.load().fragments) == 3


def test_parent_directory_sync_outcome_is_recorded_not_skipped(tmp_path):
    snap = save(tmp_path, populated(1))
    records = snap.evidence.of(EventCode.PARENT_DIR_SYNC)
    assert len(records) == 1
    outcome = records[0].detail["outcome"]
    assert outcome in {"synced", "unsupported"}
    assert outcome == parent_sync_capability()


def test_previous_snapshot_is_retained_on_overwrite(tmp_path):
    snap = save(tmp_path, populated(2))
    first = snap.read_document()
    snap.save(populated(5), peer_id="peer-A", created_at_unix=1_700_000_004)

    assert snap.previous_path.exists()
    assert snap.read_document(snap.previous_path) == first


# --- AT-27 partial-write recovery -------------------------------------------


def test_truncated_temp_file_is_discarded_and_previous_snapshot_loads(tmp_path):
    snap = save(tmp_path, populated(3))
    good = snap.read_document()

    stray = tmp_path / (snap.path.name + ".abc123.tmp")
    stray.write_bytes(codec.canonical_bytes(good)[:40])
    assert stray.exists()

    reopened = SnapshotStore(snap.path)
    result = reopened.load()

    assert not stray.exists()
    assert stray.name in result.discarded_temps
    assert len(result.fragments) == 3
    assert reopened.read_document() == good
    assert reopened.evidence.of(EventCode.TEMP_ARTEFACT_DISCARDED)


def test_multiple_stray_temps_all_discarded(tmp_path):
    snap = save(tmp_path, populated(2))
    for tag in ("aaa", "bbb", "ccc"):
        (tmp_path / (snap.path.name + f".{tag}.tmp")).write_bytes(b"partial")

    result = SnapshotStore(snap.path).load()
    assert len(result.discarded_temps) == 3
    assert list(tmp_path.glob("*.tmp")) == []


# --- AT-28 corrupted-snapshot recovery --------------------------------------


def test_corrupted_document_checksum_quarantines_and_falls_back(tmp_path):
    snap = save(tmp_path, populated(2))
    snap.save(populated(4), peer_id="peer-A", created_at_unix=1_700_000_005)
    assert snap.previous_path.exists()

    tampered = json.loads(snap.path.read_text(encoding="utf-8"))
    tampered["peer_id"] = "peer-ATTACKER"
    snap.path.write_bytes(codec.canonical_bytes(tampered))

    reopened = SnapshotStore(snap.path)
    result = reopened.load()

    assert result.used_fallback is True
    assert len(result.quarantined) == 1
    quarantine = tmp_path / result.quarantined[0]
    # Set aside, never deleted.
    assert quarantine.exists()
    assert json.loads(quarantine.read_text(encoding="utf-8"))["peer_id"] == "peer-ATTACKER"
    # The last good snapshot was used.
    assert len(result.fragments) == 2
    assert reopened.evidence.of(EventCode.SNAPSHOT_QUARANTINED)
    assert reopened.evidence.of(EventCode.SNAPSHOT_FALLBACK_USED)


def test_corrupted_fragment_with_valid_document_checksum_drops_only_that_fragment(
    tmp_path,
):
    snap = save(tmp_path, populated(4))
    document = json.loads(snap.path.read_text(encoding="utf-8"))

    # Corrupt one payload and re-checksum the document, so only the
    # per-fragment digest can detect it.
    import base64

    document["fragments"][1]["payload_b64"] = base64.b64encode(b"Z" * 16).decode()
    document["payload_checksum"] = codec.sha256_hex(
        codec.canonical_bytes(document["fragments"])
    )
    document["document_checksum"] = codec.sha256_hex(
        codec.identity_bytes(document, exclude=("document_checksum",))
    )
    snap.path.write_bytes(codec.canonical_bytes(document))

    reopened = SnapshotStore(snap.path)
    result = reopened.load()

    assert result.used_fallback is False
    assert result.quarantined == ()
    assert len(result.dropped_fragments) == 1
    assert result.dropped_fragments[0][2] == 1
    # Every intact fragment survives.
    assert sorted(f.chunk_index for f in result.fragments) == [0, 2, 3]
    for fragment in result.fragments:
        assert fragment.verify()
    dropped = reopened.evidence.of(EventCode.FRAGMENT_DROPPED)
    assert len(dropped) == 1 and dropped[0].detail["chunk_index"] == 1


def test_malformed_json_is_quarantined(tmp_path):
    snap = save(tmp_path, populated(2))
    snap.save(populated(3), peer_id="peer-A", created_at_unix=1_700_000_006)
    snap.path.write_bytes(b"{not json at all")

    result = SnapshotStore(snap.path).load()
    assert result.used_fallback is True
    assert len(result.quarantined) == 1
    assert len(result.fragments) == 2


def test_no_usable_snapshot_raises_rather_than_returning_empty(tmp_path):
    snap = SnapshotStore(tmp_path / "missing.json")
    with pytest.raises(ProtocolError) as excinfo:
        snap.load()
    assert excinfo.value.code is ErrorCode.SNAPSHOT_INVALID
    assert excinfo.value.retryable is True


def test_corrupt_primary_and_corrupt_fallback_both_quarantined(tmp_path):
    snap = save(tmp_path, populated(2))
    snap.save(populated(3), peer_id="peer-A", created_at_unix=1_700_000_007)
    snap.path.write_bytes(b"garbage-primary")
    snap.previous_path.write_bytes(b"garbage-previous")

    reopened = SnapshotStore(snap.path)
    with pytest.raises(ProtocolError) as excinfo:
        reopened.load()
    assert excinfo.value.code is ErrorCode.SNAPSHOT_INVALID
    # Both were set aside, neither deleted.
    assert len(list(tmp_path.glob("*.quarantine-*"))) == 2


# --- locking ------------------------------------------------------------------


def test_second_writer_is_refused_deterministically(tmp_path):
    from shongket_core.persist import StoreLock

    snap = save(tmp_path, populated(1))
    holder = StoreLock(snap.lock_path)
    holder.acquire()
    try:
        with pytest.raises(ProtocolError) as excinfo:
            snap.save(populated(2), peer_id="peer-A", created_at_unix=1_700_000_008)
        assert excinfo.value.code is ErrorCode.STORE_LOCKED
        assert excinfo.value.retryable is True
    finally:
        holder.release()

    # Once released, the same save succeeds — the failure was retryable.
    snap.save(populated(2), peer_id="peer-A", created_at_unix=1_700_000_008)
    assert len(snap.load().fragments) == 2


def test_readers_do_not_need_the_lock(tmp_path):
    from shongket_core.persist import StoreLock

    snap = save(tmp_path, populated(2))
    holder = StoreLock(snap.lock_path)
    holder.acquire()
    try:
        assert len(SnapshotStore(snap.path).load().fragments) == 2
    finally:
        holder.release()


# --- envelope -----------------------------------------------------------------


def test_envelope_is_schema_versioned_and_double_checksummed(tmp_path):
    snap = save(tmp_path, populated(2))
    document = json.loads(snap.path.read_text(encoding="utf-8"))

    assert document["schema"] == "shongket.snapshot.v1.0"
    assert document["payload_checksum"] == codec.sha256_hex(
        codec.canonical_bytes(document["fragments"])
    )
    assert document["document_checksum"] == codec.sha256_hex(
        codec.identity_bytes(document, exclude=("document_checksum",))
    )
    assert document["payload_checksum"] != document["document_checksum"]


def test_saved_bytes_are_deterministic_across_two_directories(tmp_path):
    """Same logical content, different paths, identical bytes."""
    a = tmp_path / "dir_a"
    b = tmp_path / "dir_b"
    a.mkdir()
    b.mkdir()
    sa = SnapshotStore(a / "snap.json")
    sb = SnapshotStore(b / "snap.json")
    sa.save(populated(3), peer_id="peer-A", created_at_unix=1_700_000_000)
    sb.save(populated(3), peer_id="peer-A", created_at_unix=1_700_000_000)
    assert sa.path.read_bytes() == sb.path.read_bytes()


def test_fragment_order_does_not_affect_saved_bytes(tmp_path):
    forward = FragmentStore()
    for i in range(4):
        forward.put(frag(i, bytes([65 + i]) * 16))
    reverse = FragmentStore()
    for i in reversed(range(4)):
        reverse.put(frag(i, bytes([65 + i]) * 16))

    a = SnapshotStore(tmp_path / "a.json")
    b = SnapshotStore(tmp_path / "b.json")
    a.save(forward, peer_id="peer-A", created_at_unix=1_700_000_000)
    b.save(reverse, peer_id="peer-A", created_at_unix=1_700_000_000)
    assert a.path.read_bytes() == b.path.read_bytes()
