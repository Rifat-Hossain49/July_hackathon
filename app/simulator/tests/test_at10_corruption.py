"""AT-10 — corrupted-fragment rejection.

The acceptance criterion (ACCEPTANCE_TESTS.md §AT-10, M0, S1):

    tampered fragment is rejected by hash mismatch and logged.

The store verifies ``sha256(payload) == chunk.sha256`` on every ingest.
A chunk whose recorded hash matches the original bytes but whose
``payload`` differs from the recorded bytes is rejected with
``ProtocolError(code="SCHEMA_INVALID")``. Subsequent valid chunks for
the same object must still be accepted.
"""

from __future__ import annotations

import pytest

from app.simulator import transfer, validation
from app.simulator.chunks import Chunk
from app.simulator.peer import SimulatedPeer


def test_tampered_payload_is_rejected(deterministic_scenario):
    receiver = SimulatedPeer(peer_id="peer-B")
    # Use a known-good chunk and substitute the payload while keeping the
    # recorded hash. The recorded hash no longer matches the payload.
    chunk = deterministic_scenario.plans["thumb"].chunks[0]
    tampered = Chunk(
        object_id=chunk.object_id,
        representation_id=chunk.representation_id,
        chunk_index=chunk.chunk_index,
        byte_range=chunk.byte_range,
        sha256=chunk.sha256,
        payload=b"tampered-bytes",
    )
    with pytest.raises(validation.ProtocolError) as excinfo:
        receiver.store.put_chunk(tampered)
    assert excinfo.value.code == "SCHEMA_INVALID"
    assert receiver.store.stats.rejected_corruption == 1
    assert receiver.store.stats.stored == 0


def test_subsequent_valid_chunk_for_same_object_is_accepted(deterministic_scenario):
    receiver = SimulatedPeer(peer_id="peer-B")
    # Tampered first.
    chunk = deterministic_scenario.plans["thumb"].chunks[0]
    tampered = Chunk(
        object_id=chunk.object_id,
        representation_id=chunk.representation_id,
        chunk_index=chunk.chunk_index,
        byte_range=chunk.byte_range,
        sha256=chunk.sha256,
        payload=b"tampered",
    )
    with pytest.raises(validation.ProtocolError):
        receiver.store.put_chunk(tampered)
    # Real one then accepted.
    receiver.store.put_chunk(chunk)
    assert receiver.store.stats.stored == 1
    assert receiver.store.has(chunk.object_id, chunk.representation_id, chunk.chunk_index)


def test_run_corruption_helper_emits_rejection_event(deterministic_scenario, capsule_logger):
    receiver = SimulatedPeer(peer_id="peer-B")
    chunk = deterministic_scenario.plans["thumb"].chunks[0]
    rejected = transfer.run_corruption(
        receiver=receiver, chunk=chunk, payload_override=b"corrupt", logger=capsule_logger
    )
    assert rejected is True
    rejected_events = [ev for ev in capsule_logger.events if ev.type.value == "chunk_rejected"]
    assert any(ev.detail.get("reason") == "hash_mismatch" for ev in rejected_events)
    assert receiver.store.stats.stored == 0