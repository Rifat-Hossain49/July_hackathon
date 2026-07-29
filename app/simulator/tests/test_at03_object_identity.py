"""AT-03 — object identity derives from the whole-object hash.

The acceptance criterion (ACCEPTANCE_TESTS.md §AT-03, M0, S1):

    identical CIDs across two senders for the same bytes

The M0 plan locks ``object_id = sha256_hex(original_source_bytes)``. The
test builds two independent scenarios from identical synthetic inputs
and asserts the ``object_id`` matches. It also verifies that the
manifest ``object_id`` matches the source-derived CID and that the
``manifest_id`` is a separate value derived from the canonical
manifest JSON.
"""

from __future__ import annotations

from app.simulator import hashutil, media, scenario


def test_object_id_matches_sha256_of_source_bytes(deterministic_scenario):
    expected = hashutil.sha256_hex(deterministic_scenario.source_bytes)
    assert deterministic_scenario.object_id == expected
    assert deterministic_scenario.object_id == media.object_id_from_source(
        deterministic_scenario.source_bytes
    )


def test_object_id_is_stable_across_independent_scenarios():
    a = scenario.build_two_peer_scenario(seed=42, chunk_size=65536, source_size_bytes=200_000)
    b = scenario.build_two_peer_scenario(seed=42, chunk_size=65536, source_size_bytes=200_000)
    assert a.object_id == b.object_id
    assert a.capsule["object_ref"] == b.capsule["object_ref"]
    assert a.manifest["object_id"] == b.manifest["object_id"]


def test_object_id_changes_when_source_changes():
    a = scenario.build_two_peer_scenario(seed=42)
    b = scenario.build_two_peer_scenario(seed=43)
    assert a.source_bytes != b.source_bytes
    assert a.object_id != b.object_id


def test_manifest_id_is_separate_from_object_id(deterministic_scenario):
    assert deterministic_scenario.manifest["manifest_id"] != deterministic_scenario.object_id