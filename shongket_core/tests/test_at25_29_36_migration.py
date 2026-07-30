"""AT-25, AT-29, AT-36 -- deterministic migration, rollback, upgrade.

Canonical definitions (ACCEPTANCE_TESTS.md):

* **AT-25** migrated document byte-identical across two runs from
  identical starting bytes; every verified fragment preserved with
  matching SHA-256; migration steps applied in order.
* **AT-29** a migration that fails mid-chain leaves the original vN
  document readable and byte-identical; no partially migrated state is
  visible; the failure is classified retryable.
* **AT-36** a populated vN store opens transparently, the in-progress
  transfer resumes without re-requesting verified chunks, the store is
  at the current version afterwards, and a second open performs no
  further migration.

Also completes the failed-migration path of **AT-30**, which the Slice 2
module deferred to here because the migration machinery did not exist
then.

Runtime boundary: `core/migrate` (+ `core/persist`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shongket_core import ErrorCode, ProtocolError, codec
from shongket_core.evidence import EvidenceLog, EventCode
from shongket_core.migrate import (
    CURRENT_VERSION,
    Migration,
    MigrationRegistry,
    migrate_privacy_fields,
    rebuild_checksums,
    upgrade_store,
)
from shongket_core.persist import SnapshotStore, restore_into
from shongket_core.store import Fragment, FragmentStore
from shongket_core.version import SchemaVersion


V0_9 = SchemaVersion(0, 9)
V0_8 = SchemaVersion(0, 8)


def frag(index: int, obj: str = "c" * 64) -> Fragment:
    payload = bytes([70 + (index % 26)]) * 24
    return Fragment(
        object_id=obj,
        representation_id="original",
        chunk_index=index,
        byte_range=(index * 24, index * 24 + 23),
        sha256=codec.sha256_hex(payload),
        payload=payload,
    )


def _add_marker(doc: dict) -> dict:
    """A v0.9 -> v1.0 step that adds a header field, touching no fragment."""
    out = dict(doc)
    out["upgraded_from"] = "v0.9"
    return out


def _add_earlier(doc: dict) -> dict:
    out = dict(doc)
    out["earlier_step"] = True
    return out


def registry_09() -> MigrationRegistry:
    return MigrationRegistry(
        (Migration(V0_9, CURRENT_VERSION, _add_marker, "add marker"),)
    )


def registry_chain() -> MigrationRegistry:
    return MigrationRegistry(
        (
            Migration(V0_8, V0_9, _add_earlier, "0.8 -> 0.9"),
            Migration(V0_9, CURRENT_VERSION, _add_marker, "0.9 -> 1.0"),
        )
    )


def write_legacy(path: Path, version: SchemaVersion, n: int = 4) -> SnapshotStore:
    """Write a populated snapshot stamped with an older version."""
    store = FragmentStore()
    for i in range(n):
        store.put(frag(i))
    document = SnapshotStore.build_document(
        store.fragments(), peer_id="peer-A", created_at_unix=1_700_000_000
    )
    document["schema"] = f"shongket.snapshot.v{version.major}.{version.minor}"
    document = rebuild_checksums(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(codec.canonical_bytes(document))
    return SnapshotStore(path)


class Boom(RuntimeError):
    """Injected migration failure."""


# --- AT-25 deterministic migration -------------------------------------------


def test_migration_is_byte_identical_across_two_runs(tmp_path):
    outputs = []
    for tag in ("a", "b"):
        snap = write_legacy(tmp_path / tag / "s.json", V0_9)
        before = snap.path.read_bytes()
        result = upgrade_store(snap, registry_09())
        outputs.append((before, snap.path.read_bytes(), result))

    assert outputs[0][0] == outputs[1][0], "identical starting bytes"
    assert outputs[0][1] == outputs[1][1], "identical migrated bytes"
    assert outputs[0][2].document_checksum == outputs[1][2].document_checksum


def test_migration_preserves_every_verified_fragment(tmp_path):
    snap = write_legacy(tmp_path / "s.json", V0_9, n=6)
    before = {
        (f["object_id"], f["chunk_index"]): f["sha256"]
        for f in snap.read_document()["fragments"]
    }

    upgrade_store(snap, registry_09())

    after_doc = snap.read_document()
    after = {
        (f["object_id"], f["chunk_index"]): f["sha256"]
        for f in after_doc["fragments"]
    }
    assert after == before

    restored = FragmentStore()
    restore_into(restored, snap.load().fragments)
    assert len(restored) == 6
    for fragment in restored.fragments():
        assert fragment.verify()


def test_multi_step_chain_applies_in_order(tmp_path):
    snap = write_legacy(tmp_path / "s.json", V0_8)
    result = upgrade_store(snap, registry_chain())

    assert result.steps_applied == 2
    document = snap.read_document()
    # Both steps ran, and the later one is present.
    assert document["earlier_step"] is True
    assert document["upgraded_from"] == "v0.9"
    assert document["schema"] == "shongket.snapshot.v1.0"


def test_migration_evidence_records_versions_and_result(tmp_path):
    log = EvidenceLog()
    snap = write_legacy(tmp_path / "s.json", V0_9)
    upgrade_store(snap, registry_09(), evidence=log)

    applied = log.of(EventCode.MIGRATION_APPLIED)
    assert len(applied) == 1
    detail = applied[0].detail
    assert detail["source_version"] == "v0.9"
    assert detail["target_version"] == "v1.0"
    assert detail["steps_applied"] == 1
    assert detail["migrated"] is True
    assert detail["error_code"] is None


def test_migration_output_contains_no_timestamps_or_paths(tmp_path):
    """Same content in two directories migrates to identical bytes."""
    a = write_legacy(tmp_path / "a" / "s.json", V0_9)
    b = write_legacy(tmp_path / "b" / "other-name.json", V0_9)
    upgrade_store(a, registry_09())
    upgrade_store(b, registry_09())
    assert a.path.read_bytes() == b.path.read_bytes()


# --- AT-29 rollback -----------------------------------------------------------


def test_failed_migration_leaves_original_byte_identical(tmp_path):
    snap = write_legacy(tmp_path / "s.json", V0_9)
    before = snap.path.read_bytes()
    before_sha = codec.sha256_hex(before)

    with pytest.raises(ProtocolError) as excinfo:
        upgrade_store(
            snap,
            registry_09(),
            fault_hook=lambda stage: (_ for _ in ()).throw(Boom())
            if stage == "after_temp_write"
            else None,
        )

    assert excinfo.value.retryable is True
    after = snap.path.read_bytes()
    assert after == before
    assert codec.sha256_hex(after) == before_sha
    # Still readable and still at the old version.
    assert snap.read_document()["schema"] == "shongket.snapshot.v0.9"


def test_failure_during_a_step_rolls_back(tmp_path):
    def explode(_doc: dict) -> dict:
        raise Boom("step failed")

    snap = write_legacy(tmp_path / "s.json", V0_9)
    before = snap.path.read_bytes()
    registry = MigrationRegistry((Migration(V0_9, CURRENT_VERSION, explode),))

    with pytest.raises(ProtocolError) as excinfo:
        upgrade_store(snap, registry)
    assert excinfo.value.code is ErrorCode.SNAPSHOT_INVALID
    assert excinfo.value.retryable is True
    assert snap.path.read_bytes() == before


def test_rollback_is_recorded_as_evidence(tmp_path):
    log = EvidenceLog()
    snap = write_legacy(tmp_path / "s.json", V0_9)
    with pytest.raises(ProtocolError):
        upgrade_store(
            snap,
            registry_09(),
            evidence=log,
            fault_hook=lambda stage: (_ for _ in ()).throw(Boom())
            if stage == "after_temp_write"
            else None,
        )
    rolled = log.of(EventCode.MIGRATION_ROLLED_BACK)
    assert len(rolled) == 1
    assert rolled[0].detail["source_version"] == "v0.9"
    assert rolled[0].detail["error_code"]
    assert log.of(EventCode.MIGRATION_APPLIED) == ()


def test_no_partially_migrated_state_is_visible(tmp_path):
    snap = write_legacy(tmp_path / "s.json", V0_8)
    before = snap.path.read_bytes()

    with pytest.raises(ProtocolError):
        upgrade_store(
            snap,
            registry_chain(),
            fault_hook=lambda stage: (_ for _ in ()).throw(Boom())
            if stage == "after_step_2"
            else None,
        )

    document = snap.read_document()
    assert snap.path.read_bytes() == before
    assert document["schema"] == "shongket.snapshot.v0.8"
    assert "earlier_step" not in document
    assert "upgraded_from" not in document


def test_migration_that_would_discard_fragments_is_refused(tmp_path):
    def drop_one(doc: dict) -> dict:
        out = dict(doc)
        out["fragments"] = out["fragments"][1:]
        return out

    snap = write_legacy(tmp_path / "s.json", V0_9, n=4)
    before = snap.path.read_bytes()
    registry = MigrationRegistry((Migration(V0_9, CURRENT_VERSION, drop_one),))

    with pytest.raises(ProtocolError) as excinfo:
        upgrade_store(snap, registry)
    assert "discard" in excinfo.value.detail
    assert snap.path.read_bytes() == before


def test_migration_that_would_alter_a_digest_is_refused(tmp_path):
    def tamper(doc: dict) -> dict:
        out = dict(doc)
        frags = [dict(f) for f in out["fragments"]]
        frags[0]["sha256"] = "0" * 64
        out["fragments"] = frags
        return out

    snap = write_legacy(tmp_path / "s.json", V0_9)
    before = snap.path.read_bytes()
    registry = MigrationRegistry((Migration(V0_9, CURRENT_VERSION, tamper),))

    with pytest.raises(ProtocolError) as excinfo:
        upgrade_store(snap, registry)
    assert "alter" in excinfo.value.detail
    assert snap.path.read_bytes() == before


# --- AT-30 completion: failed-migration recovery path -------------------------


def test_at30_failed_migration_preserves_fragments(tmp_path):
    """The fifth AT-30 recovery path, deferred from Slice 2."""
    snap = write_legacy(tmp_path / "s.json", V0_9, n=5)
    before_store = FragmentStore()
    restore_into(before_store, snap.load().fragments)
    before_inventory = before_store.inventory()

    with pytest.raises(ProtocolError):
        upgrade_store(
            snap,
            registry_09(),
            fault_hook=lambda stage: (_ for _ in ()).throw(Boom())
            if stage == "after_temp_write"
            else None,
        )

    after_store = FragmentStore()
    restore_into(after_store, snap.load().fragments)
    assert after_store.inventory() == before_inventory
    assert after_store.used_bytes == after_store.recompute_used_bytes()
    for fragment in after_store.fragments():
        assert fragment.verify()


# --- AT-36 end-to-end upgrade -------------------------------------------------


def test_upgrade_is_transparent_and_resumes_without_refetch(tmp_path):
    snap = write_legacy(tmp_path / "s.json", V0_9, n=3)
    assert snap.read_document()["schema"] == "shongket.snapshot.v0.9"

    result = upgrade_store(snap, registry_09())
    assert result.migrated is True
    assert snap.read_document()["schema"] == "shongket.snapshot.v1.0"

    # Resume: the three migrated chunks are not re-requested.
    store = FragmentStore()
    restore_into(store, snap.load().fragments)
    expected = tuple(range(6))
    missing = store.missing_indexes("c" * 64, "original", expected)
    assert missing == (3, 4, 5)

    for index in missing:
        store.put(frag(index))
    snap.save(store, peer_id="peer-A", created_at_unix=1_700_000_001)

    # Restart and reopen: still current, no further migration.
    reopened = SnapshotStore(snap.path)
    second = upgrade_store(reopened, registry_09())
    assert second.migrated is False
    assert second.steps_applied == 0
    assert len(reopened.load().fragments) == 6


def test_second_open_performs_no_further_migration(tmp_path):
    log = EvidenceLog()
    snap = write_legacy(tmp_path / "s.json", V0_9)
    upgrade_store(snap, registry_09(), evidence=log)
    after_first = snap.path.read_bytes()

    second = upgrade_store(SnapshotStore(snap.path), registry_09(), evidence=log)
    assert second.migrated is False
    assert snap.path.read_bytes() == after_first
    assert len(log.of(EventCode.MIGRATION_APPLIED)) == 1
    assert len(log.of(EventCode.MIGRATION_NOT_REQUIRED)) == 1


def test_upgrade_is_idempotent_when_repeated(tmp_path):
    snap = write_legacy(tmp_path / "s.json", V0_9)
    upgrade_store(snap, registry_09())
    once = snap.path.read_bytes()
    for _ in range(3):
        upgrade_store(SnapshotStore(snap.path), registry_09())
        assert snap.path.read_bytes() == once


# --- registry rules -----------------------------------------------------------


def test_unregistered_path_is_refused_not_inferred(tmp_path):
    snap = write_legacy(tmp_path / "s.json", V0_8)
    with pytest.raises(ProtocolError) as excinfo:
        upgrade_store(snap, registry_09())  # knows 0.9 -> 1.0 only
    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED
    assert "never inferred" in excinfo.value.detail


def test_newer_snapshot_is_refused_rather_than_downgraded(tmp_path):
    snap = write_legacy(tmp_path / "s.json", SchemaVersion(2, 0))
    with pytest.raises(ProtocolError) as excinfo:
        upgrade_store(snap, registry_09())
    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED
    assert "downgrade is not defined" in excinfo.value.detail


def test_ambiguous_registry_is_refused_at_construction():
    with pytest.raises(ValueError, match="ambiguous migration path"):
        MigrationRegistry(
            (
                Migration(V0_9, CURRENT_VERSION, _add_marker),
                Migration(V0_9, SchemaVersion(0, 95), _add_earlier),
            )
        )


def test_migration_cycle_is_refused_at_construction():
    with pytest.raises(ValueError, match="cycle"):
        MigrationRegistry(
            (
                Migration(V0_8, V0_9, _add_earlier),
                Migration(V0_9, V0_8, _add_marker),
            )
        )


def test_self_edge_is_refused():
    with pytest.raises(ValueError, match="must change the version"):
        Migration(V0_9, V0_9, _add_marker)


def test_registry_edges_are_deterministically_ordered():
    a = MigrationRegistry(
        (Migration(V0_8, V0_9, _add_earlier), Migration(V0_9, CURRENT_VERSION, _add_marker))
    )
    b = MigrationRegistry(
        (Migration(V0_9, CURRENT_VERSION, _add_marker), Migration(V0_8, V0_9, _add_earlier))
    )
    assert [e.source for e in a.edges()] == [e.source for e in b.edges()]


def test_corrupted_input_is_rejected_before_migration(tmp_path):
    snap = write_legacy(tmp_path / "s.json", V0_9)
    document = json.loads(snap.path.read_text(encoding="utf-8"))
    document["peer_id"] = "tampered"
    snap.path.write_bytes(codec.canonical_bytes(document))

    with pytest.raises(ProtocolError) as excinfo:
        upgrade_store(SnapshotStore(snap.path), registry_09())
    assert excinfo.value.code is ErrorCode.SNAPSHOT_CORRUPTED


# --- legacy privacy migration (feeds AT-34) -----------------------------------


@pytest.mark.parametrize(
    "legacy, expected",
    [
        ({"private": True}, "private"),
        ({"private": False}, "public"),
        ({}, "public"),
    ],
)
def test_legacy_private_marker_maps_to_visibility(legacy, expected):
    migrated = migrate_privacy_fields({"object_id": "a" * 64, **legacy})
    assert migrated["visibility"] == expected
    assert "private" not in migrated


def test_existing_visibility_is_left_alone():
    migrated = migrate_privacy_fields({"visibility": "private", "private": False})
    assert migrated["visibility"] == "private"
    assert "private" not in migrated


@pytest.mark.parametrize("marker", ["true", 1, 0, [], {}])
def test_non_boolean_private_marker_is_refused(marker):
    with pytest.raises(ProtocolError) as excinfo:
        migrate_privacy_fields({"object_id": "a" * 64, "private": marker})
    assert excinfo.value.code is ErrorCode.SCHEMA_INVALID


def test_privacy_migration_is_deterministic():
    source = {"object_id": "a" * 64, "private": True}
    first = migrate_privacy_fields(source)
    second = migrate_privacy_fields(source)
    assert codec.canonical_bytes(first) == codec.canonical_bytes(second)
    assert source == {"object_id": "a" * 64, "private": True}, "input unmutated"
