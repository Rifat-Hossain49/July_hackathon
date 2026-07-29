"""AT-09 — duplicate-fragment dedup.

The acceptance criterion (ACCEPTANCE_TESTS.md §AT-09, M0, S1):

    identical FragmentDescriptor offered twice is stored once; second is no-op.

The store counts duplicate inserts and rejects hash collisions at the
same fragment key. The test asserts both the no-op path and the
hash-collision rejection path.
"""

from __future__ import annotations

import pytest

from app.simulator import transfer, validation
from app.simulator.chunks import Chunk
from app.simulator.peer import SimulatedPeer


def _make_chunk(object_id: str, rep: str, index: int, payload: bytes) -> Chunk:
    import hashlib

    return Chunk(
        object_id=object_id,
        representation_id=rep,
        chunk_index=index,
        byte_range=(index * 100, index * 100 + len(payload) - 1),
        sha256=hashlib.sha256(payload).hexdigest(),
        payload=payload,
    )


def test_duplicate_chunk_is_noop(deterministic_scenario):
    receiver = SimulatedPeer(peer_id="peer-B")
    chunk = _make_chunk(deterministic_scenario.object_id, "thumb", 0, b"abc123")
    receiver.store.put_chunk(chunk)
    before_stats = receiver.store.stats.as_dict()
    receiver.store.put_chunk(chunk)
    after_stats = receiver.store.stats.as_dict()
    assert after_stats["stored"] == before_stats["stored"] == 1
    assert after_stats["duplicate_no_op"] == before_stats["duplicate_no_op"] + 1
    assert after_stats["rejected_corruption"] == before_stats["rejected_corruption"]


def test_hash_collision_at_same_key_is_rejected(deterministic_scenario):
    receiver = SimulatedPeer(peer_id="peer-B")
    first = _make_chunk(deterministic_scenario.object_id, "thumb", 0, b"abc123")
    receiver.store.put_chunk(first)
    colliding = Chunk(
        object_id=first.object_id,
        representation_id=first.representation_id,
        chunk_index=first.chunk_index,
        byte_range=first.byte_range,
        sha256=first.sha256,
        payload=b"different-bytes",
    )
    with pytest.raises(validation.ProtocolError) as excinfo:
        receiver.store.put_chunk(colliding)
    assert excinfo.value.code == "SCHEMA_INVALID"
    assert receiver.store.stats.rejected_corruption == 1
    assert receiver.store.stats.duplicate_no_op == 0


def test_run_duplication_helper_emits_duplicate_event(deterministic_scenario, capsule_logger):
    receiver = SimulatedPeer(peer_id="peer-B")
    chunk = _make_chunk(deterministic_scenario.object_id, "thumb", 0, b"zzz")
    stored_again, rejected = transfer.run_duplication(receiver=receiver, chunk=chunk, logger=capsule_logger)
    assert stored_again is True
    assert rejected is False
    types = [ev.type.value for ev in capsule_logger.events]
    assert "chunk_duplicate" in types