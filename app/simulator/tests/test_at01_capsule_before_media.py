"""AT-01 — semantic capsule reaches the receiver before bulk media for the same object.

The acceptance criterion (ACCEPTANCE_TESTS.md §AT-01, M0, S1):

    critical capsule arrives ahead of bulk delivery

The test runs the canonical two-peer scenario and asserts that every
``CAPSULE_DELIVERED`` event for ``scenario.object_id`` precedes every
``CHUNK_DELIVERED`` event for the same ``object_id`` in the event log.
The deterministic priority order in ``priority.py`` guarantees this.
"""

from __future__ import annotations

from app.simulator import events


def test_capsule_event_precedes_all_media_events(full_transfer_result):
    scenario, logger, result = full_transfer_result

    capsule_ticks: list[int] = []
    chunk_ticks: list[int] = []
    for ev in logger.events:
        if ev.object_id != scenario.object_id:
            continue
        if ev.type == events.EventType.CAPSULE_DELIVERED:
            capsule_ticks.append(ev.tick)
        elif ev.type == events.EventType.CHUNK_DELIVERED:
            chunk_ticks.append(ev.tick)

    assert capsule_ticks, "expected at least one CAPSULE_DELIVERED event"
    assert chunk_ticks, "expected at least one CHUNK_DELIVERED event"
    assert max(capsule_ticks) < min(chunk_ticks), (
        f"capsule ticks {capsule_ticks} must all precede chunk ticks {chunk_ticks}"
    )


def test_capsule_before_manifest_for_same_object(full_transfer_result):
    """The deterministic priority order places the capsule above the manifest."""
    scenario, logger, _ = full_transfer_result

    capsule_tick: int | None = None
    manifest_tick: int | None = None
    for ev in logger.events:
        if ev.object_id != scenario.object_id:
            continue
        if ev.type == events.EventType.CAPSULE_DELIVERED:
            capsule_tick = ev.tick if capsule_tick is None else min(capsule_tick, ev.tick)
        elif ev.type == events.EventType.MANIFEST_DELIVERED:
            manifest_tick = ev.tick if manifest_tick is None else min(manifest_tick, ev.tick)

    assert capsule_tick is not None and manifest_tick is not None
    assert capsule_tick < manifest_tick