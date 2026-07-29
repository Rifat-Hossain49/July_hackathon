"""AT-12 -- storage-budget enforcement.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-12, M0 unit / M5+ device,
S2 at M0):

    with a low-storage marker, ingesting new content engages the storage
    policy.

Evidence required: log; quota values.

Scope note. AT-12 is explicitly split: "Milestone: M0 (rule), M5+
(effect)". This module tests the **M0 rule** -- deterministic byte
accounting and refusal of content that does not fit -- using the
canonical ``FragmentAck`` status ``out_of_budget`` (PROTOCOL_SPEC.md
§3.6) and the M0 scheduler factor "Storage: under threshold, defer
non-critical media" (§6.0). Device-side *eviction* of already-stored
content is the M5+ effect and is deliberately not implemented here;
SYSTEM_ARCHITECTURE.md assigns eviction to the insufficient-storage
device path, and evicting at M0 would contradict the requirement that a
refusal leave existing fragments intact.
"""

from __future__ import annotations

import io

from app.simulator import events, hashutil, persistence, scenario, transfer
from app.simulator.chunks import Chunk
from app.simulator.peer import SimulatedPeer
from app.simulator.store import ContentAddressedStore
from app.simulator.validation import ProtocolError


CHUNK_SIZE = 16_384


def _plan_chunks() -> list[Chunk]:
    """Deterministic chunk sequence for the 'original' representation."""
    scen = scenario.build_two_peer_scenario(chunk_size=CHUNK_SIZE)
    return list(scen.plans["original"].chunks)


def _tiny_chunk(payload: bytes, *, chunk_index: int = 0) -> Chunk:
    """A schema-valid one-off chunk with an exact known payload size."""
    return Chunk(
        object_id="a" * 64,
        representation_id="thumb",
        chunk_index=chunk_index,
        byte_range=(0, max(len(payload) - 1, 0)),
        sha256=hashutil.sha256_hex(payload),
        payload=payload,
    )


# --- accounting -------------------------------------------------------------


def test_empty_store_reports_zero_used_bytes():
    store = ContentAddressedStore(capacity_bytes=1_000)
    assert store.used_bytes == 0
    assert store.remaining_bytes == 1_000
    assert store.recompute_used_bytes() == 0
    assert store.quota() == {
        "capacity_bytes": 1_000,
        "used_bytes": 0,
        "remaining_bytes": 1_000,
        "fragment_count": 0,
    }


def test_unbounded_store_is_the_default_and_never_refuses():
    store = ContentAddressedStore()
    assert store.capacity_bytes is None
    assert store.remaining_bytes is None
    for chunk in _plan_chunks():
        store.put_chunk(chunk)
    assert store.stats.rejected_budget == 0
    assert store.used_bytes == store.recompute_used_bytes()


def test_used_bytes_counts_actual_payload_bytes():
    chunks = _plan_chunks()
    store = ContentAddressedStore(capacity_bytes=10_000_000)
    expected = 0
    for chunk in chunks:
        store.put_chunk(chunk)
        expected += len(chunk.payload)
        # The incremental counter never drifts from the real payload sum.
        assert store.used_bytes == expected == store.recompute_used_bytes()
    assert store.remaining_bytes == 10_000_000 - expected


# --- exact boundaries -------------------------------------------------------


def test_payload_that_fits_exactly_is_accepted():
    chunks = _plan_chunks()[:3]
    capacity = sum(len(c.payload) for c in chunks)
    store = ContentAddressedStore(capacity_bytes=capacity)

    for chunk in chunks:
        store.put_chunk(chunk)

    assert store.stats.stored == len(chunks)
    assert store.stats.rejected_budget == 0
    assert store.used_bytes == capacity
    assert store.remaining_bytes == 0


def test_payload_exceeding_by_one_byte_is_rejected():
    chunks = _plan_chunks()
    head, nxt = chunks[:3], chunks[3]
    capacity = sum(len(c.payload) for c in head) + len(nxt.payload) - 1
    store = ContentAddressedStore(capacity_bytes=capacity)

    for chunk in head:
        store.put_chunk(chunk)
    used_before = store.used_bytes
    fragments_before = store.snapshot_fragments()

    try:
        store.put_chunk(nxt)
    except ProtocolError as exc:
        assert exc.code == "OUT_OF_BUDGET"
        assert exc.object_id == nxt.object_id
    else:  # pragma: no cover - the call above must raise
        raise AssertionError("over-budget chunk was accepted")

    # Rejected before any mutation.
    assert store.stats.rejected_budget == 1
    assert store.stats.stored == len(head)
    assert store.used_bytes == used_before
    assert store.snapshot_fragments() == fragments_before
    assert not store.has(nxt.object_id, nxt.representation_id, nxt.chunk_index)


def test_zero_capacity_store_rejects_any_non_empty_payload():
    store = ContentAddressedStore(capacity_bytes=0)
    chunk = _tiny_chunk(b"x")

    try:
        store.put_chunk(chunk)
    except ProtocolError as exc:
        assert exc.code == "OUT_OF_BUDGET"
    else:  # pragma: no cover
        raise AssertionError("chunk accepted into a zero-capacity store")

    assert store.stats.stored == 0
    assert store.used_bytes == 0
    assert store.stats.rejected_budget == 1


def test_rejection_leaves_earlier_fragments_intact_and_allows_a_later_fit():
    """A refusal is not fatal: a smaller chunk still fits afterwards."""
    chunks = _plan_chunks()
    big = chunks[0]
    small = _tiny_chunk(b"z" * 16, chunk_index=99)
    store = ContentAddressedStore(capacity_bytes=len(big.payload) + 8)

    store.put_chunk(big)
    try:
        store.put_chunk(chunks[1])
    except ProtocolError as exc:
        assert exc.code == "OUT_OF_BUDGET"

    # The first fragment survived, and the remaining 8 bytes are usable.
    assert store.has(big.object_id, big.representation_id, big.chunk_index)
    store.put_chunk(_tiny_chunk(b"z" * 8, chunk_index=98))
    assert store.stats.stored == 2
    assert store.remaining_bytes == 0

    # ...but nothing larger than the remainder.
    try:
        store.put_chunk(small)
    except ProtocolError as exc:
        assert exc.code == "OUT_OF_BUDGET"
    else:  # pragma: no cover
        raise AssertionError("chunk accepted beyond remaining capacity")


# --- what must never consume capacity ---------------------------------------


def test_duplicate_chunks_consume_no_additional_capacity():
    chunk = _plan_chunks()[0]
    store = ContentAddressedStore(capacity_bytes=len(chunk.payload))

    store.put_chunk(chunk)
    used_after_first = store.used_bytes
    assert used_after_first == len(chunk.payload)
    assert store.remaining_bytes == 0

    # The store is exactly full; re-offering the same chunk is a no-op,
    # not an over-budget refusal.
    store.put_chunk(chunk)

    assert store.stats.duplicate_no_op == 1
    assert store.stats.rejected_budget == 0
    assert store.stats.stored == 1
    assert store.used_bytes == used_after_first == store.recompute_used_bytes()


def test_corrupted_chunks_consume_no_capacity():
    chunk = _plan_chunks()[0]
    store = ContentAddressedStore(capacity_bytes=10_000_000)
    tampered = Chunk(
        object_id=chunk.object_id,
        representation_id=chunk.representation_id,
        chunk_index=chunk.chunk_index,
        byte_range=chunk.byte_range,
        sha256=chunk.sha256,
        payload=b"\x00" * len(chunk.payload),
    )

    try:
        store.put_chunk(tampered)
    except ProtocolError as exc:
        assert exc.code == "SCHEMA_INVALID"
    else:  # pragma: no cover
        raise AssertionError("corrupted chunk was accepted")

    assert store.used_bytes == 0
    assert store.recompute_used_bytes() == 0
    assert store.stats.rejected_corruption == 1
    assert store.stats.rejected_budget == 0
    assert store.stats.stored == 0


def test_schema_invalid_chunks_consume_no_capacity():
    chunk = _plan_chunks()[0]
    store = ContentAddressedStore(capacity_bytes=10_000_000)
    # 'bogus' is not in the M0 representation enum, so the descriptor
    # fails schema validation before any storage decision is made.
    malformed = Chunk(
        object_id=chunk.object_id,
        representation_id="bogus",
        chunk_index=chunk.chunk_index,
        byte_range=chunk.byte_range,
        sha256=chunk.sha256,
        payload=chunk.payload,
    )

    try:
        store.put_chunk(malformed)
    except ProtocolError as exc:
        assert exc.code == "SCHEMA_INVALID"
    else:  # pragma: no cover
        raise AssertionError("schema-invalid chunk was accepted")

    assert store.used_bytes == 0
    assert store.stats.rejected_schema == 1
    assert store.stats.rejected_budget == 0
    assert store.stats.stored == 0


# --- evidence ---------------------------------------------------------------


def test_budget_rejection_emits_quota_values():
    chunks = _plan_chunks()
    capacity = sum(len(c.payload) for c in chunks[:2])
    receiver = SimulatedPeer(peer_id="peer-B")
    receiver.store.capacity_bytes = capacity
    sender = SimulatedPeer(peer_id="peer-A")
    logger = events.EventLogger(sink=io.StringIO())

    result = transfer.run_budgeted_ingest(
        sender=sender,
        receiver=receiver,
        logger=logger,
        chunks=chunks[:4],
    )

    assert result.accepted_indexes == [0, 1]
    assert result.rejected_indexes == [2, 3]
    assert result.quota_before["used_bytes"] == 0
    assert result.quota_after["used_bytes"] == capacity
    assert result.quota_after["remaining_bytes"] == 0

    rejections = logger.of_type(events.EventType.STORAGE_BUDGET_REJECTED)
    assert len(rejections) == 2
    for ev, chunk in zip(rejections, chunks[2:4]):
        detail = ev.detail
        assert detail["reason"] == "OUT_OF_BUDGET"
        assert detail["ack_status"] == "out_of_budget"
        assert detail["payload_bytes"] == len(chunk.payload)
        assert detail["capacity_bytes"] == capacity
        assert detail["used_bytes"] == capacity
        assert detail["remaining_bytes"] == 0
        assert detail["fragment_count"] == 2
        assert ev.chunk_index == chunk.chunk_index

    # Storage matches the accepted set exactly.
    assert receiver.store.stats.stored == 2
    assert receiver.store.stats.rejected_budget == 2
    assert receiver.store.used_bytes == receiver.store.recompute_used_bytes()


def test_budgeted_ingest_is_deterministic():
    chunks = _plan_chunks()
    capacity = sum(len(c.payload) for c in chunks[:2])
    logs = []
    for _ in range(2):
        receiver = SimulatedPeer(peer_id="peer-B")
        receiver.store.capacity_bytes = capacity
        sink = io.StringIO()
        transfer.run_budgeted_ingest(
            sender=SimulatedPeer(peer_id="peer-A"),
            receiver=receiver,
            logger=events.EventLogger(sink=sink),
            chunks=chunks[:4],
        )
        logs.append(sink.getvalue())
    assert logs[0] == logs[1]


# --- restart compatibility --------------------------------------------------


def test_budget_accounting_survives_snapshot_and_restart(tmp_path):
    chunks = _plan_chunks()[:3]
    capacity = sum(len(c.payload) for c in chunks) + 4

    original = SimulatedPeer(peer_id="peer-B")
    original.store.capacity_bytes = capacity
    for chunk in chunks:
        original.store.put_chunk(chunk)
    used_before = original.store.used_bytes
    quota_before = original.store.quota()

    snapshot = tmp_path / "snapshot.json"
    original.save_progress(snapshot, created_at_unix=1_700_000_000)

    # Restart into a fresh peer carrying the same budget.
    restarted = SimulatedPeer(peer_id="peer-B")
    restarted.store.capacity_bytes = capacity
    restored = restarted.load_progress(snapshot)

    assert restored == len(chunks)
    assert restarted.store.used_bytes == used_before
    assert restarted.store.recompute_used_bytes() == used_before
    assert restarted.store.quota() == quota_before
    assert restarted.store.remaining_bytes == 4

    # The restored budget is still enforced for new content.
    try:
        restarted.store.put_chunk(_plan_chunks()[3])
    except ProtocolError as exc:
        assert exc.code == "OUT_OF_BUDGET"
    else:  # pragma: no cover
        raise AssertionError("over-budget chunk accepted after restart")

    assert restarted.store.used_bytes == used_before

    # A chunk that fits the 4-byte remainder is still accepted.
    restarted.store.put_chunk(_tiny_chunk(b"abcd", chunk_index=77))
    assert restarted.store.used_bytes == used_before + 4
    assert restarted.store.remaining_bytes == 0


def test_restore_does_not_double_count_duplicates(tmp_path):
    chunks = _plan_chunks()[:2]
    capacity = sum(len(c.payload) for c in chunks)

    peer = SimulatedPeer(peer_id="peer-B")
    peer.store.capacity_bytes = capacity
    for chunk in chunks:
        peer.store.put_chunk(chunk)

    snapshot = tmp_path / "snapshot.json"
    peer.save_progress(snapshot, created_at_unix=1_700_000_000)

    # Loading the same snapshot twice must not consume capacity twice.
    _peer_id, _created, loaded = persistence.load_snapshot(snapshot)
    again = persistence.restore_store(peer.store, loaded)

    assert again == 0
    assert peer.store.used_bytes == capacity
    assert peer.store.recompute_used_bytes() == capacity
    assert peer.store.stats.rejected_budget == 0
