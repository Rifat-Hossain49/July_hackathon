"""AT-30 and AT-31 -- fragment preservation and deterministic restart.

Canonical definitions (ACCEPTANCE_TESTS.md):

* **AT-30** every fragment verified before a recovery event is present
  afterwards with its original SHA-256 — except one whose own bytes were
  deliberately corrupted — and byte accounting matches a recomputed sum
  in every case. Paths: restart, partial write, corrupted document,
  failed migration, refused over-budget write.
* **AT-31** an interrupted transfer restarted twice produces
  byte-identical event logs and identical resulting stores, and requests
  only the missing chunks after restart.

The failed-migration path of AT-30 is added by the Slice 3 module
(`test_at25_29_36_migration.py::test_at30_failed_migration_preserves_fragments`),
because the migration machinery it exercises does not exist until that
slice. The other four paths are covered here.

Runtime boundary: `core/store` + `core/persist`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shongket_core import ErrorCode, ProtocolError, codec
from shongket_core.evidence import EvidenceLog
from shongket_core.persist import SnapshotStore, restore_into
from shongket_core.store import Fragment, FragmentStore


def frag(index: int, obj: str = "b" * 64) -> Fragment:
    payload = bytes([65 + (index % 26)]) * 32
    return Fragment(
        object_id=obj,
        representation_id="original",
        chunk_index=index,
        byte_range=(index * 32, index * 32 + 31),
        sha256=codec.sha256_hex(payload),
        payload=payload,
    )


def populated(n: int) -> FragmentStore:
    store = FragmentStore()
    for i in range(n):
        store.put(frag(i))
    return store


def inventory_of(store: FragmentStore) -> list[dict]:
    return store.inventory()


def accounting_is_consistent(store: FragmentStore) -> bool:
    return store.used_bytes == store.recompute_used_bytes()


# --- AT-30 preservation across recovery paths --------------------------------


def test_restart_preserves_every_fragment(tmp_path):
    store = populated(6)
    before = inventory_of(store)
    before_bytes = store.used_bytes

    snap = SnapshotStore(tmp_path / "s.json")
    snap.save(store, peer_id="peer-A", created_at_unix=1_700_000_000)

    restarted = FragmentStore()
    restore_into(restarted, snap.load().fragments)

    assert inventory_of(restarted) == before
    assert restarted.used_bytes == before_bytes
    assert accounting_is_consistent(restarted)


def test_partial_write_path_preserves_every_fragment(tmp_path):
    store = populated(5)
    before = inventory_of(store)
    snap = SnapshotStore(tmp_path / "s.json")
    snap.save(store, peer_id="peer-A", created_at_unix=1_700_000_000)

    (tmp_path / (snap.path.name + ".xyz.tmp")).write_bytes(b"truncated prefix")

    restarted = FragmentStore()
    result = SnapshotStore(snap.path).load()
    restore_into(restarted, result.fragments)

    assert result.discarded_temps
    assert inventory_of(restarted) == before
    assert accounting_is_consistent(restarted)


def test_corrupted_document_path_preserves_fragments_via_fallback(tmp_path):
    first = populated(4)
    before = inventory_of(first)

    snap = SnapshotStore(tmp_path / "s.json")
    snap.save(first, peer_id="peer-A", created_at_unix=1_700_000_000)
    snap.save(populated(6), peer_id="peer-A", created_at_unix=1_700_000_001)
    snap.path.write_bytes(b"corrupt")

    restarted = FragmentStore()
    result = SnapshotStore(snap.path).load()
    restore_into(restarted, result.fragments)

    assert result.used_fallback is True
    # Every fragment in the recovered snapshot is intact and verified.
    assert inventory_of(restarted) == before
    assert accounting_is_consistent(restarted)
    for fragment in restarted.fragments():
        assert fragment.verify()


def test_only_the_deliberately_corrupted_fragment_is_lost(tmp_path):
    store = populated(5)
    snap = SnapshotStore(tmp_path / "s.json")
    snap.save(store, peer_id="peer-A", created_at_unix=1_700_000_000)

    import base64

    document = json.loads(snap.path.read_text(encoding="utf-8"))
    document["fragments"][2]["payload_b64"] = base64.b64encode(b"X" * 32).decode()
    document["payload_checksum"] = codec.sha256_hex(
        codec.canonical_bytes(document["fragments"])
    )
    document["document_checksum"] = codec.sha256_hex(
        codec.identity_bytes(document, exclude=("document_checksum",))
    )
    snap.path.write_bytes(codec.canonical_bytes(document))

    restarted = FragmentStore()
    result = SnapshotStore(snap.path).load()
    restore_into(restarted, result.fragments)

    survivors = [f.chunk_index for f in restarted.fragments()]
    assert survivors == [0, 1, 3, 4]
    for fragment in restarted.fragments():
        assert fragment.verify()
        assert fragment.sha256 == frag(fragment.chunk_index).sha256
    assert accounting_is_consistent(restarted)


def test_refused_over_budget_write_preserves_existing_fragments(tmp_path):
    store = FragmentStore(capacity_bytes=32 * 3)
    for i in range(3):
        store.put(frag(i))
    before = inventory_of(store)
    before_bytes = store.used_bytes

    with pytest.raises(ProtocolError) as excinfo:
        store.put(frag(3))
    assert excinfo.value.code is ErrorCode.OUT_OF_BUDGET

    assert inventory_of(store) == before
    assert store.used_bytes == before_bytes
    assert accounting_is_consistent(store)

    # And the refusal survives a save/restore cycle unchanged.
    snap = SnapshotStore(tmp_path / "s.json")
    snap.save(store, peer_id="peer-A", created_at_unix=1_700_000_000)
    restarted = FragmentStore(capacity_bytes=32 * 3)
    restore_into(restarted, snap.load().fragments)
    assert inventory_of(restarted) == before
    assert restarted.used_bytes == before_bytes


def test_byte_accounting_matches_recomputed_sum_in_every_path(tmp_path):
    store = populated(4)
    snap = SnapshotStore(tmp_path / "s.json")
    snap.save(store, peer_id="peer-A", created_at_unix=1_700_000_000)

    for _ in range(3):
        restarted = FragmentStore()
        restore_into(restarted, SnapshotStore(snap.path).load().fragments)
        assert restarted.used_bytes == restarted.recompute_used_bytes()
        snap.save(restarted, peer_id="peer-A", created_at_unix=1_700_000_000)


# --- AT-31 deterministic restart ---------------------------------------------


EXPECTED_CHUNKS = tuple(range(8))
CUTOFF = 3


def interrupted_then_resumed(tmp_path: Path, tag: str) -> tuple[str, list[dict], tuple[int, ...]]:
    """Run interrupt -> save -> restart -> resume; return evidence + state."""
    evidence = EvidenceLog()
    store = FragmentStore(evidence=evidence)

    # Partial transfer: only the first CUTOFF chunks arrive.
    for i in range(CUTOFF):
        store.put(frag(i))

    snap = SnapshotStore(tmp_path / f"{tag}.json", evidence=evidence)
    snap.save(store, peer_id="peer-A", created_at_unix=1_700_000_000)

    # Restart: fresh store, restore from the snapshot.
    restarted = FragmentStore(evidence=evidence)
    restore_into(restarted, SnapshotStore(snap.path, evidence=evidence).load().fragments)

    # Resume: request only what is missing.
    missing = restarted.missing_indexes("b" * 64, "original", EXPECTED_CHUNKS)
    for index in missing:
        restarted.put(frag(index))

    return evidence.digest(), restarted.inventory(), missing


def test_restart_is_byte_identical_across_two_runs(tmp_path):
    first_dir = tmp_path / "run1"
    second_dir = tmp_path / "run2"
    first_dir.mkdir()
    second_dir.mkdir()

    digest_a, inv_a, missing_a = interrupted_then_resumed(first_dir, "s")
    digest_b, inv_b, missing_b = interrupted_then_resumed(second_dir, "s")

    assert digest_a == digest_b
    assert inv_a == inv_b
    assert missing_a == missing_b


def test_resume_requests_only_missing_chunks(tmp_path):
    _digest, inventory, missing = interrupted_then_resumed(tmp_path, "s")

    # The first CUTOFF chunks survived the restart and were not re-requested.
    assert missing == tuple(range(CUTOFF, len(EXPECTED_CHUNKS)))
    assert all(i not in missing for i in range(CUTOFF))
    # The object is complete afterwards, with no duplicates.
    assert [entry["chunk_index"] for entry in inventory] == list(EXPECTED_CHUNKS)


def test_restart_stores_are_identical_and_complete(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _da, inv_a, _ma = interrupted_then_resumed(a, "s")
    _db, inv_b, _mb = interrupted_then_resumed(b, "s")
    assert inv_a == inv_b
    assert len(inv_a) == len(EXPECTED_CHUNKS)


def test_missing_indexes_is_deterministic_and_sorted():
    store = FragmentStore()
    for i in (5, 1, 3):
        store.put(frag(i))
    missing = store.missing_indexes("b" * 64, "original", range(7))
    assert missing == (0, 2, 4, 6)
    assert missing == store.missing_indexes("b" * 64, "original", range(7))


def test_restart_evidence_contains_no_wall_clock_or_paths_outside_control(tmp_path):
    evidence_digest, _inv, _missing = interrupted_then_resumed(tmp_path, "s")
    # Same logical run in a different directory yields the same digest,
    # proving no absolute path or clock value leaked into the evidence.
    other = tmp_path / "elsewhere"
    other.mkdir()
    assert interrupted_then_resumed(other, "s")[0] == evidence_digest
