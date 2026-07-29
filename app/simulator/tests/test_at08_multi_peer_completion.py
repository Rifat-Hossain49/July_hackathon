"""AT-08 -- multi-peer missing-chunk completion.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-08, M0, S1):

    source data is spread across >= 2 peers and no peer has the full
    data; the receiver negotiates with both and achieves full
    reconstruction, requesting missing chunks only.

Evidence required: reconstruction log; >= 2 peer ids.

The fixture (``scenario.build_multi_peer_scenario``) splits one
representation into a leading block on ``peer-A`` and an overlapping
trailing block on ``peer-B``, plus a ``peer-C`` that holds only chunks
the others already cover. Neither A nor B alone completes the object, so
completion must draw on at least two peer IDs; the overlap and the
redundant ``peer-C`` make "request only what is missing" falsifiable.

Completion uses ordinary chunks only -- no Reed-Solomon, fountain code
or RaptorQ (DR-SPEC-04, DR-MS-02).
"""

from __future__ import annotations

import io

from app.simulator import chunks as chunks_mod
from app.simulator import events, hashutil, scenario, transfer


def _completed_chunks(scen) -> list:
    """Read every completed chunk back out of the receiver's store."""
    return [
        scen.receiver.store.get(scen.object_id, scen.representation_id, idx)
        for idx in scen.chunk_indexes
    ]


def test_no_single_peer_holds_the_complete_representation():
    """Precondition: the object is genuinely split across peers."""
    scen = scenario.build_multi_peer_scenario()
    total = len(scen.chunk_indexes)
    assert total >= 4

    for peer in scen.providers:
        held = peer.store.known_chunks(scen.object_id, scen.representation_id)
        assert len(held) < total, f"{peer.peer_id} alone completes the object"

    # The union of all providers does cover the object.
    union: set[int] = set()
    for peer in scen.providers:
        union |= peer.store.known_chunks(scen.object_id, scen.representation_id)
    assert union == set(scen.chunk_indexes)

    # The receiver starts with nothing.
    assert scen.receiver.store.known_chunks(scen.object_id, scen.representation_id) == set()


def test_multi_peer_completion_reconstructs_and_verifies_hash():
    scen = scenario.build_multi_peer_scenario()
    logger = events.EventLogger(sink=io.StringIO())

    result = transfer.run_multi_peer_completion(
        receiver=scen.receiver,
        providers=scen.providers,
        logger=logger,
        object_id=scen.object_id,
        representation_id=scen.representation_id,
        chunk_indexes=scen.chunk_indexes,
    )

    # Completion drew on at least two distinct contributing peer IDs.
    assert len(result.contributing_peer_ids) >= 2
    assert result.contributing_peer_ids == ["peer-A", "peer-B"]

    # Every required chunk has recorded provenance, and the receiver holds it.
    assert sorted(result.fragment_sources) == scen.chunk_indexes
    assert scen.receiver.store.known_chunks(
        scen.object_id, scen.representation_id
    ) == set(scen.chunk_indexes)

    # Reconstruct from ordinary verified chunks and verify the hash.
    fragmenter = chunks_mod.FixedSizeFragmenter(scen.base.chunk_size)
    reconstructed = fragmenter.reconstruct(scen.plan, _completed_chunks(scen))

    assert len(reconstructed) == len(scen.base.source_bytes)
    assert hashutil.sha256_hex(reconstructed) == scen.plan.representation_hash

    # The 'original' representation hash is the canonical object_id, i.e.
    # SHA-256 of the original source bytes (AT-03 / AT-21 invariant).
    assert scen.plan.representation_hash == scen.object_id
    assert reconstructed == scen.base.source_bytes

    # ...and it matches the hash advertised in the manifest.
    rep_entry = next(
        rep
        for rep in scen.base.manifest["representations"]
        if rep["id"] == scen.representation_id
    )
    assert hashutil.sha256_hex(reconstructed) == rep_entry["rep_sha256"]


def test_receiver_requests_only_missing_chunks():
    scen = scenario.build_multi_peer_scenario()
    logger = events.EventLogger(sink=io.StringIO())

    result = transfer.run_multi_peer_completion(
        receiver=scen.receiver,
        providers=scen.providers,
        logger=logger,
        object_id=scen.object_id,
        representation_id=scen.representation_id,
        chunk_indexes=scen.chunk_indexes,
    )

    requested_a = result.requested_by_peer["peer-A"]
    requested_b = result.requested_by_peer["peer-B"]
    requested_c = result.requested_by_peer["peer-C"]

    # peer-A is asked for exactly what it holds (the receiver is empty).
    assert requested_a == scen.holdings["peer-A"]

    # peer-B holds an overlapping block, but is asked only for the part
    # peer-A did not already supply.
    overlap = sorted(set(scen.holdings["peer-A"]) & set(scen.holdings["peer-B"]))
    assert overlap, "fixture must overlap for this assertion to mean anything"
    assert not (set(requested_b) & set(requested_a))
    assert not (set(requested_b) & set(overlap))
    assert requested_b == sorted(set(scen.holdings["peer-B"]) - set(requested_a))

    # peer-C holds nothing new, so it is asked for nothing at all.
    assert requested_c == []

    # No chunk was requested from more than one peer.
    all_requested = requested_a + requested_b + requested_c
    assert len(all_requested) == len(set(all_requested))
    assert sorted(all_requested) == scen.chunk_indexes

    # The driver never had to skip a re-request.
    assert result.retransmission_requests == 0


def test_verified_chunks_are_not_retransmitted():
    scen = scenario.build_multi_peer_scenario()
    logger = events.EventLogger(sink=io.StringIO())

    transfer.run_multi_peer_completion(
        receiver=scen.receiver,
        providers=scen.providers,
        logger=logger,
        object_id=scen.object_id,
        representation_id=scen.representation_id,
        chunk_indexes=scen.chunk_indexes,
    )

    delivered = [
        ev
        for ev in logger.of_type(events.EventType.CHUNK_DELIVERED)
        if ev.object_id == scen.object_id
        and ev.representation_id == scen.representation_id
    ]
    # Exactly one delivery per chunk: no duplicate transmission anywhere.
    assert len(delivered) == len(scen.chunk_indexes)
    assert sorted(ev.chunk_index for ev in delivered) == scen.chunk_indexes

    # The store agrees: nothing was stored twice.
    assert scen.receiver.store.stats.stored == len(scen.chunk_indexes)
    assert scen.receiver.store.stats.duplicate_no_op == 0
    assert scen.receiver.store.stats.rejected_corruption == 0
    assert scen.receiver.store.stats.rejected_schema == 0


def test_fragment_source_report_derived_from_event_log():
    """The >= 2 peer-id evidence is recoverable from the log alone."""
    scen = scenario.build_multi_peer_scenario()
    logger = events.EventLogger(sink=io.StringIO())

    result = transfer.run_multi_peer_completion(
        receiver=scen.receiver,
        providers=scen.providers,
        logger=logger,
        object_id=scen.object_id,
        representation_id=scen.representation_id,
        chunk_indexes=scen.chunk_indexes,
    )

    report = transfer.fragment_source_report(
        logger,
        object_id=scen.object_id,
        representation_id=scen.representation_id,
    )

    # Log-derived provenance matches the driver's own bookkeeping.
    assert report == result.fragment_sources
    assert sorted(set(report.values())) == ["peer-A", "peer-B"]
    assert len(set(report.values())) >= 2

    # The completion event records the same contributor set.
    completed = logger.of_type(events.EventType.MULTI_PEER_COMPLETED)
    assert len(completed) == 1
    detail = completed[0].detail
    assert detail["contributing_peer_ids"] == ["peer-A", "peer-B"]
    assert detail["contributing_peer_count"] == 2
    assert detail["chunks_completed"] == len(scen.chunk_indexes)
    assert detail["chunks_required"] == len(scen.chunk_indexes)

    # Every FRAGMENT_REQUESTED event carries the canonical request shape.
    requests = logger.of_type(events.EventType.FRAGMENT_REQUESTED)
    assert len(requests) == len(scen.providers)
    for ev in requests:
        assert ev.detail["schema"] == "shongket.fragreq.v1"
        assert isinstance(ev.detail["chunk_indexes"], list)


def test_multi_peer_completion_is_deterministic():
    """Two independent runs produce byte-identical logs and provenance."""
    outputs = []
    provenance = []
    for _ in range(2):
        scen = scenario.build_multi_peer_scenario()
        sink = io.StringIO()
        logger = events.EventLogger(sink=sink)
        result = transfer.run_multi_peer_completion(
            receiver=scen.receiver,
            providers=scen.providers,
            logger=logger,
            object_id=scen.object_id,
            representation_id=scen.representation_id,
            chunk_indexes=scen.chunk_indexes,
        )
        outputs.append(sink.getvalue())
        provenance.append(result.fragment_sources)

    assert outputs[0] == outputs[1]
    assert provenance[0] == provenance[1]
