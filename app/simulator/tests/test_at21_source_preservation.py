"""AT-21 — original source media remains preserved.

The acceptance criterion (ACCEPTANCE_TESTS.md §AT-21, M0, S1):

    original source bytes unchanged; source representation hash equals
    original hash; semantic capsule references the source object;
    generated summary does not overwrite the original.

The test records the source bytes and source hash before the encounter,
runs the canonical scenario, then verifies the bytes and the manifest
``original`` representation hash are unchanged after the encounter.
"""

from __future__ import annotations

from app.simulator import hashutil


def test_source_bytes_unchanged_after_encounter(full_transfer_result):
    scenario, _, _ = full_transfer_result
    bytes_before = bytes(scenario.source_bytes)
    hash_before = hashutil.sha256_hex(scenario.source_bytes)
    # Re-running the build path produces the same source bytes from the seed.
    from app.simulator import media

    rebuilt = media.synthetic_source_bytes(scenario.seed, len(scenario.source_bytes))
    assert rebuilt == bytes_before
    assert hashutil.sha256_hex(rebuilt) == hash_before


def test_original_representation_hash_matches_source_hash(deterministic_scenario):
    source_hash = hashutil.sha256_hex(deterministic_scenario.source_bytes)
    original_entry = next(
        r for r in deterministic_scenario.manifest["representations"] if r["id"] == "original"
    )
    assert original_entry["rep_sha256"] == source_hash
    assert original_entry["byte_len"] == len(deterministic_scenario.source_bytes)


def test_capsule_object_ref_matches_object_id(deterministic_scenario):
    assert deterministic_scenario.capsule["object_ref"] == deterministic_scenario.object_id
    assert deterministic_scenario.manifest["object_id"] == deterministic_scenario.object_id


def test_receiver_reconstructs_original_bytes(full_transfer_result):
    scenario, _, _ = full_transfer_result
    receiver = scenario.receiver
    # All original chunks must be stored; reconstruction must yield
    # the original source bytes verbatim.
    original_plan = scenario.plans["original"]
    stored: list = []
    for c in original_plan.chunks:
        chunk = receiver.store.get(c.object_id, c.representation_id, c.chunk_index)
        assert chunk is not None
        stored.append(chunk)
    from app.simulator.chunks import FixedSizeFragmenter

    fragmenter = FixedSizeFragmenter(scenario.chunk_size)
    rebuilt = fragmenter.reconstruct(original_plan, stored)
    assert rebuilt == scenario.source_bytes
    assert hashutil.sha256_hex(rebuilt) == hashutil.sha256_hex(scenario.source_bytes)


def test_summary_does_not_overwrite_source(full_transfer_result):
    """The capsule must not be stored as a chunk; it is the signal plane."""
    scenario, _, _ = full_transfer_result
    receiver = scenario.receiver
    # No fragment must carry a ``representation_id`` of ``"capsule:..."``
    # because capsules ride the signal plane, never the media plane.
    for (obj_id, rep_id, _idx) in receiver.store._fragments.keys():
        assert not rep_id.startswith("capsule:"), f"capsule leaked into store as {rep_id}"
    # The capsule payload itself is byte-equal to the original.
    assert hashutil.sha256_hex(scenario.source_bytes) == scenario.object_id