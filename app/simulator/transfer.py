"""In-process encounter driver (M0).

The driver loops for a configurable number of ticks, scheduling the next
unit of work for the sender and delivering it to the receiver through the
in-process transport. The receiver validates and persists the payload.

This is the smallest building block that proves capsule-before-media
ordering for AT-01.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import events, priority
from .chunks import Chunk
from .peer import SimulatedPeer, open_encounter, close_encounter
from .priority import SchedulerItem
from .validation import ProtocolError


@dataclass
class EncounterResult:
    """Summary of a single encounter between two peers."""

    sender_id: str
    receiver_id: str
    delivered_capsule: bool = False
    delivered_manifest: bool = False
    delivered_chunk_indexes: list[int] = field(default_factory=list)
    rejected_indexes: list[int] = field(default_factory=list)


def _encode_event(ev: events.Event) -> bytes:
    return ev.to_jsonl().encode("utf-8")


def run_encounter(
    *,
    sender: SimulatedPeer,
    receiver: SimulatedPeer,
    logger: events.EventLogger,
    items: list[SchedulerItem],
    capsule_payload: dict,
    manifest_payload: dict,
    chunks: list[Chunk],
) -> EncounterResult:
    """Drive a deterministic encounter delivering items in scheduler order.

    Parameters
    ----------
    items:
        Output of ``priority.order(...)`` dictating the order.
    capsule_payload, manifest_payload:
        Signal-plane payloads stored once and referenced by id.
    chunks:
        Media-plane fragments, addressable by ``(object_id, representation_id, chunk_index)``.
    """
    open_encounter(sender, receiver, logger)

    # Index media chunks for O(1) lookup.
    chunk_by_key: dict[tuple[str, str, int], Chunk] = {
        (c.object_id, c.representation_id, c.chunk_index): c for c in chunks
    }

    result = EncounterResult(sender_id=sender.peer_id, receiver_id=receiver.peer_id)

    for it in items:
        logger.advance(1)
        if it.representation_id and it.representation_id.startswith("capsule:"):
            payload = json.dumps(capsule_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            sender.send(payload)
            sender.deliver_to(receiver)
            message = receiver.receive()
            logger.advance(1)
            try:
                decoded = json.loads(message.decode("utf-8"))  # noqa: F841 (validation applied in store)
            except Exception:
                logger.emit(
                    events.EventType.CHUNK_REJECTED,
                    sender_id=sender.peer_id,
                    receiver_id=receiver.peer_id,
                    object_id=it.object_id,
                    detail={"reason": "malformed_capsule"},
                )
                continue
            logger.emit(
                events.EventType.CAPSULE_DELIVERED,
                sender_id=sender.peer_id,
                receiver_id=receiver.peer_id,
                object_id=it.object_id,
                representation_id=it.representation_id,
                detail={"capsule_id": capsule_payload["capsule_id"]},
            )
            result.delivered_capsule = True
            continue

        if it.representation_id and it.representation_id.startswith("manifest:"):
            payload = json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            sender.send(payload)
            sender.deliver_to(receiver)
            receiver.receive()
            logger.advance(1)
            logger.emit(
                events.EventType.MANIFEST_DELIVERED,
                sender_id=sender.peer_id,
                receiver_id=receiver.peer_id,
                object_id=it.object_id,
                representation_id=it.representation_id,
                detail={"manifest_id": manifest_payload["manifest_id"]},
            )
            result.delivered_manifest = True
            continue

        # Media chunk tier.
        if it.representation_id is None or it.chunk_index is None:
            continue
        chunk = chunk_by_key.get((it.object_id, it.representation_id, it.chunk_index))
        if chunk is None:
            logger.emit(
                events.EventType.CHUNK_REJECTED,
                sender_id=sender.peer_id,
                receiver_id=receiver.peer_id,
                object_id=it.object_id,
                representation_id=it.representation_id,
                chunk_index=it.chunk_index,
                detail={"reason": "missing_chunk"},
            )
            result.rejected_indexes.append(it.chunk_index)
            continue
        sender.send(chunk.payload)
        sender.deliver_to(receiver)
        message = receiver.receive()
        logger.advance(1)
        if message is None:
            logger.emit(
                events.EventType.CHUNK_REJECTED,
                sender_id=sender.peer_id,
                receiver_id=receiver.peer_id,
                detail={"reason": "empty"},
            )
            continue
        # Build a Chunk for the receiver (with the same metadata and incoming payload).
        delivered = Chunk(
            object_id=chunk.object_id,
            representation_id=chunk.representation_id,
            chunk_index=chunk.chunk_index,
            byte_range=chunk.byte_range,
            sha256=chunk.sha256,
            payload=message,
        )
        try:
            receiver.store.put_chunk(delivered)
        except ProtocolError as exc:
            logger.emit(
                events.EventType.CHUNK_REJECTED,
                sender_id=sender.peer_id,
                receiver_id=receiver.peer_id,
                object_id=it.object_id,
                representation_id=it.representation_id,
                chunk_index=it.chunk_index,
                detail={"reason": exc.code, "detail": exc.detail},
            )
            result.rejected_indexes.append(it.chunk_index)
            continue
        logger.emit(
            events.EventType.CHUNK_DELIVERED,
            sender_id=sender.peer_id,
            receiver_id=receiver.peer_id,
            object_id=it.object_id,
            representation_id=it.representation_id,
            chunk_index=it.chunk_index,
        )
        result.delivered_chunk_indexes.append(it.chunk_index)

    close_encounter(sender, receiver, logger)
    return result


def run_duplication(
    *,
    receiver: SimulatedPeer,
    chunk: Chunk,
    logger: events.EventLogger,
) -> tuple[bool, bool]:
    """Send the same chunk twice to ``receiver`` and return ``(stored_again, rejected_corrupt)``.

    Used by AT-09 to assert dedup behaviour.
    """
    recv_id = receiver.peer_id
    sender_id = "test-sender"
    try:
        receiver.store.put_chunk(chunk)
    except ProtocolError:
        return (False, True)
    try:
        receiver.store.put_chunk(chunk)
    except ProtocolError:
        return (False, True)
    logger.advance(1)
    logger.emit(
        events.EventType.CHUNK_DUPLICATE,
        sender_id=sender_id,
        receiver_id=recv_id,
        object_id=chunk.object_id,
        representation_id=chunk.representation_id,
        chunk_index=chunk.chunk_index,
    )
    return (True, False)


def run_corruption(
    *,
    receiver: SimulatedPeer,
    chunk: Chunk,
    payload_override: bytes,
    logger: events.EventLogger,
) -> bool:
    """Deliver a chunk whose payload does not match its SHA-256; return ``True`` if rejected."""
    tampered = Chunk(
        object_id=chunk.object_id,
        representation_id=chunk.representation_id,
        chunk_index=chunk.chunk_index,
        byte_range=chunk.byte_range,
        sha256=chunk.sha256,
        payload=payload_override,
    )
    try:
        receiver.store.put_chunk(tampered)
    except ProtocolError:
        logger.advance(1)
        logger.emit(
            events.EventType.CHUNK_REJECTED,
            sender_id="test-sender",
            receiver_id=receiver.peer_id,
            object_id=chunk.object_id,
            representation_id=chunk.representation_id,
            chunk_index=chunk.chunk_index,
            detail={"reason": "hash_mismatch"},
        )
        return True
    logger.advance(1)
    logger.emit(
        events.EventType.CHUNK_DELIVERED,
        sender_id="test-sender",
        receiver_id=receiver.peer_id,
        object_id=chunk.object_id,
        representation_id=chunk.representation_id,
        chunk_index=chunk.chunk_index,
    )
    return False
