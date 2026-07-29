"""AT-06 -- interrupted transfer retains verified progress.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-06, M0, S1):

    when a peer disappears mid-transfer, the verified chunks remain in
    the receiver store; after a reconnect, only the missing chunks are
    requested.

The test runs ``transfer.run_interrupted_transfer`` up to a configurable
``peer_disappear_after_chunks`` cutoff, then runs
``transfer.run_resume_transfer`` with a fresh sender. It asserts:

* the first encounter emits a ``TRANSFER_INTERRUPTED`` event;
* the receiver store retains exactly the chunks delivered before the
  cutoff (no loss, no duplication);
* the second encounter emits ``TRANSFER_RESUMED`` events only for
  chunks not yet in the receiver store;
* the total delivery count equals the canonical chunk plan size.
"""

from __future__ import annotations

import io

from app.simulator import events, scenario, transfer


def test_interrupted_then_resumed_completes_object(deterministic_scenario):
    scen = deterministic_scenario
    items = scenario.schedule_full_transfer(scen)
    chunks = scenario.all_chunks(scen)

    # Pick a small cutoff so the test stays fast: deliver ~30% then disappear.
    cutoff = max(1, len(chunks) // 3)

    receiver = scen.receiver
    sender = scen.sender
    logger1 = events.EventLogger(sink=io.StringIO())
    first = transfer.run_interrupted_transfer(
        sender=sender,
        receiver=receiver,
        logger=logger1,
        items=items,
        capsule_payload=scen.capsule,
        manifest_payload=scen.manifest,
        chunks=chunks,
        peer_disappear_after_chunks=cutoff,
    )

    # First encounter produced a TRANSFER_INTERRUPTED event.
    interrupted = logger1.of_type(events.EventType.TRANSFER_INTERRUPTED)
    assert len(interrupted) == 1
    intr = interrupted[0]
    assert intr.detail["delivered_chunks"] == cutoff
    assert intr.detail["missing_chunks"] > 0
    # Capsule + manifest were delivered before the bulk chunks started.
    assert first.delivered_capsule is True
    assert first.delivered_manifest is True

    # Receiver store has exactly ``cutoff`` chunks.
    assert receiver.store.stats.stored == cutoff

    # Second encounter: a fresh sender, same receiver, only the missing chunks.
    fresh_sender = scen.sender.__class__(peer_id="peer-C")
    logger2 = events.EventLogger(sink=io.StringIO())
    second = transfer.run_resume_transfer(
        sender=fresh_sender,
        receiver=receiver,
        logger=logger2,
        items=items,
        chunks=chunks,
    )

    # TRANSFER_RESUMED was emitted once per missing chunk.
    resumed = logger2.of_type(events.EventType.TRANSFER_RESUMED)
    assert len(resumed) == len(chunks) - cutoff

    # The total number of delivered chunks across both encounters equals the
    # full chunk plan size.
    delivered_first = len(logger1.of_type(events.EventType.CHUNK_DELIVERED))
    delivered_second = len(logger2.of_type(events.EventType.CHUNK_DELIVERED))
    assert delivered_first == cutoff
    assert delivered_first + delivered_second == len(chunks)

    # Receiver store now holds every chunk and no duplicates.
    assert receiver.store.stats.stored == len(chunks)
    seen: set = set()
    for c in chunks:
        key = (c.object_id, c.representation_id, c.chunk_index)
        assert key not in seen, "chunk delivered twice across the two encounters"
        seen.add(key)
        assert receiver.store.has(*key)

    # The second encounter did not duplicate any chunk.
    assert second.rejected_indexes == []
    assert delivered_second == len(chunks) - cutoff


def test_resume_does_not_request_already_verified_chunks(deterministic_scenario):
    """If a chunk is already in the receiver store, the resume skips it."""
    scen = deterministic_scenario
    items = scenario.schedule_full_transfer(scen)
    chunks = scenario.all_chunks(scen)

    cutoff = 1
    transfer.run_interrupted_transfer(
        sender=scen.sender,
        receiver=scen.receiver,
        logger=events.EventLogger(sink=io.StringIO()),
        items=items,
        capsule_payload=scen.capsule,
        manifest_payload=scen.manifest,
        chunks=chunks,
        peer_disappear_after_chunks=cutoff,
    )
    assert scen.receiver.store.stats.stored == cutoff

    logger2 = events.EventLogger(sink=io.StringIO())
    transfer.run_resume_transfer(
        sender=scen.sender.__class__(peer_id="peer-D"),
        receiver=scen.receiver,
        logger=logger2,
        items=items,
        chunks=chunks,
    )

    # Exactly one TRANSFER_RESUMED event for each missing chunk, and no event
    # for the chunk already verified.
    resumed = logger2.of_type(events.EventType.TRANSFER_RESUMED)
    assert len(resumed) == len(chunks) - cutoff
    # No CHUNK_DELIVERED re-emission for the already-stored chunk: the
    # second encounter only delivers (len(chunks) - cutoff) chunks.
    delivered_second = logger2.of_type(events.EventType.CHUNK_DELIVERED)
    assert len(delivered_second) == len(chunks) - cutoff
    # The store retains exactly the original cutoff plus the new deliveries.
    assert scen.receiver.store.stats.stored == len(chunks)