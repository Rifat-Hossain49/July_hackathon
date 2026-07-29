"""AT-04 — progressive media layers arrive in tier order.

The acceptance criterion (ACCEPTANCE_TESTS.md §AT-04, M0, S1):

    capsule, then preview, then full media, by priority

The four representations ``thumb``, ``preview``, ``standard`` and
``original`` must coexist without fragment-key collision.

The test asserts:

1. every representation is present in the manifest;
2. ``thumb[0]`` and ``preview[0]`` are stored under distinct keys;
3. the deterministic scheduler emits chunks in the tier order
   ``thumb → preview → standard → original``.
"""

from __future__ import annotations

from app.simulator import events, priority, scenario


def test_manifest_lists_all_representations(deterministic_scenario):
    rep_ids = {r["id"] for r in deterministic_scenario.manifest["representations"]}
    assert rep_ids == {"thumb", "preview", "standard", "original"}


def test_thumb_zero_and_preview_zero_do_not_collide(deterministic_scenario):
    """The fragment key ``(object_id, representation_id, chunk_index)`` must
    disambiguate thumb[0] from preview[0]."""
    from app.simulator.chunks import Chunk
    from app.simulator.peer import SimulatedPeer

    receiver = SimulatedPeer(peer_id="peer-B")
    thumb_chunk = deterministic_scenario.plans["thumb"].chunks[0]
    preview_chunk = deterministic_scenario.plans["preview"].chunks[0]
    assert thumb_chunk.object_id == preview_chunk.object_id
    assert thumb_chunk.chunk_index == preview_chunk.chunk_index == 0
    assert thumb_chunk.representation_id != preview_chunk.representation_id
    assert thumb_chunk is not preview_chunk
    # Storing both must succeed and produce two distinct keys.
    receiver.store.put_chunk(thumb_chunk)
    receiver.store.put_chunk(preview_chunk)
    assert receiver.store.has(thumb_chunk.object_id, "thumb", 0)
    assert receiver.store.has(preview_chunk.object_id, "preview", 0)
    assert {"thumb", "preview"} <= receiver.store.known_representations(preview_chunk.object_id)


def test_scheduler_emits_thumb_before_preview_before_original(full_transfer_result):
    scenario_, logger, _ = full_transfer_result
    seen_rep_order: list[str] = []
    for ev in logger.events:
        if ev.type == events.EventType.CHUNK_DELIVERED and ev.object_id == scenario_.object_id:
            assert ev.representation_id is not None
            seen_rep_order.append(ev.representation_id)
    # First occurrence of each tier is monotonically non-decreasing in tier rank.
    tier = {"thumb": 0, "preview": 1, "standard": 2, "original": 3}
    first_idx = {rep: seen_rep_order.index(rep) for rep in tier}
    seq = [first_idx["thumb"], first_idx["preview"], first_idx["standard"], first_idx["original"]]
    assert seq == sorted(seq), f"expected monotone first-seen order, got {first_idx}"


def test_priority_order_classifies_thumb_at_tier_three(deterministic_scenario):
    thumb_item = priority.SchedulerItem.chunk(
        object_id=deterministic_scenario.object_id,
        representation_id="thumb",
        chunk_index=0,
    )
    original_item = priority.SchedulerItem.chunk(
        object_id=deterministic_scenario.object_id,
        representation_id="original",
        chunk_index=0,
    )
    assert thumb_item.tier < original_item.tier