"""AT-05 -- critical content preempts in-progress bulk transfer.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-05, M0, S1):

    when a critical capsule arrives mid-transfer, the bulk transfer is
    interrupted, the critical capsule is delivered, and the bulk
    transfer then resumes from the next missing chunk without
    re-sending already-delivered chunks.

The test exercises ``transfer.run_preemption_encounter`` and asserts:

* exactly one ``PREEMPTION_LOGGED`` event is emitted at the boundary;
* the ``PREEMPTION_LOGGED`` event precedes the critical capsule's
  ``CAPSULE_DELIVERED``;
* the bulk transfer resumes after the critical delivery;
* every chunk from the bulk plan is delivered exactly once.
"""

from __future__ import annotations

import io

from app.simulator import events, priority, scenario, transfer


def _bulk_only_items(scen, *, exclude_reps=("thumb",)):
    """Build a scheduler list with only bulk-tier chunks (no capsule/manifest)."""
    items: list = []
    for rep_id, plan in scen.plans.items():
        if rep_id in exclude_reps:
            continue
        for c in plan.chunks:
            items.append(
                priority.SchedulerItem.chunk(
                    object_id=c.object_id,
                    representation_id=c.representation_id,
                    chunk_index=c.chunk_index,
                )
            )
    return priority.order(items)


def _bulk_chunks(scen, *, exclude_reps=("thumb",)):
    out = []
    for rep_id, plan in scen.plans.items():
        if rep_id in exclude_reps:
            continue
        out.extend(plan.chunks)
    return out


def test_preemption_interrupts_bulk_and_logs_event(deterministic_scenario):
    scen = deterministic_scenario
    bulk_items = _bulk_only_items(scen)
    bulk_chunks = _bulk_chunks(scen)
    # Inject the critical capsule after 3 chunks have been delivered.
    inject_after = 3

    # Build a distinct critical capsule payload for a different object id.
    critical_object_id = "c" * 64
    from app.simulator import capsule

    critical_capsule = capsule.build_capsule(
        object_id=critical_object_id,
        summary_bn="URGENT: cyclone landfall in two hours.",
        event_type="cyclone",
        urgency="life_safety",
        location_text="Kuakata",
        required_action="Move to the designated cyclone shelter immediately.",
        required_resource="Batteries, radio, drinking water",
        human_confirmed=True,
        confirmation_method="manual_form_only",
        created_at_unix=1_700_000_001,
    )

    logger = events.EventLogger(sink=io.StringIO())
    result = transfer.run_preemption_encounter(
        sender=scen.sender,
        receiver=scen.receiver,
        logger=logger,
        bulk_items=bulk_items,
        bulk_chunks=bulk_chunks,
        critical_capsule_payload=critical_capsule,
        critical_object_id=critical_object_id,
        inject_after_chunks=inject_after,
    )

    # Exactly one preemption event was logged.
    preemption = logger.of_type(events.EventType.PREEMPTION_LOGGED)
    assert len(preemption) == 1
    preemption_ev = preemption[0]
    assert preemption_ev.object_id == critical_object_id
    assert preemption_ev.detail["delivered_before_preempt"] == inject_after
    assert preemption_ev.detail["capsule_id"] == critical_capsule["capsule_id"]

    # The preemption event tick is strictly less than the critical capsule
    # delivery tick.
    critical_delivered = [
        ev
        for ev in logger.of_type(events.EventType.CAPSULE_DELIVERED)
        if ev.object_id == critical_object_id
    ]
    assert len(critical_delivered) == 1
    assert preemption_ev.tick < critical_delivered[0].tick
    assert result.delivered_capsule is True

    # Every bulk chunk was delivered exactly once.
    delivered = logger.of_type(events.EventType.CHUNK_DELIVERED)
    assert len(delivered) == len(bulk_chunks)
    seen_keys = {(ev.object_id, ev.representation_id, ev.chunk_index) for ev in delivered}
    assert len(seen_keys) == len(bulk_chunks)
    # Receiver store has every chunk.
    for c in bulk_chunks:
        assert scen.receiver.store.has(c.object_id, c.representation_id, c.chunk_index)


def test_preemption_resumes_without_resending_already_delivered(deterministic_scenario):
    """Already-delivered chunks must NOT be re-sent after preemption."""
    scen = deterministic_scenario
    bulk_items = _bulk_only_items(scen)
    bulk_chunks = _bulk_chunks(scen)
    inject_after = 2

    from app.simulator import capsule

    critical_capsule = capsule.build_capsule(
        object_id="d" * 64,
        summary_bn="URGENT: earthquake aftershock imminent.",
        event_type="earthquake",
        urgency="life_safety",
        location_text="Bandarban",
        required_action="Stay outdoors away from structures.",
        required_resource="First-aid, water",
        human_confirmed=True,
        confirmation_method="manual_form_only",
        created_at_unix=1_700_000_002,
    )

    logger = events.EventLogger(sink=io.StringIO())
    transfer.run_preemption_encounter(
        sender=scen.sender,
        receiver=scen.receiver,
        logger=logger,
        bulk_items=bulk_items,
        bulk_chunks=bulk_chunks,
        critical_capsule_payload=critical_capsule,
        critical_object_id="d" * 64,
        inject_after_chunks=inject_after,
    )

    # Count how many times each chunk key was emitted as CHUNK_DELIVERED.
    counts: dict = {}
    for ev in logger.of_type(events.EventType.CHUNK_DELIVERED):
        key = (ev.object_id, ev.representation_id, ev.chunk_index)
        counts[key] = counts.get(key, 0) + 1
    assert all(v == 1 for v in counts.values()), (
        f"every chunk must be delivered exactly once, got {counts!r}"
    )

    # Critical capsule delivery comes after the preemption event AND after
    # the inject_after_chunks-th CHUNK_DELIVERED.
    preemption_tick = logger.of_type(events.EventType.PREEMPTION_LOGGED)[0].tick
    critical_tick = [
        ev
        for ev in logger.of_type(events.EventType.CAPSULE_DELIVERED)
        if ev.object_id == "d" * 64
    ][0].tick
    chunk_ticks = [ev.tick for ev in logger.of_type(events.EventType.CHUNK_DELIVERED)]
    assert preemption_tick < critical_tick
    # Some chunk ticks are after the critical delivery (the resumed bulk).
    assert any(t > critical_tick for t in chunk_ticks)
