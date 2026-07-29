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


# ---------------------------------------------------------------------------
# Slice 2 drivers: human-confirmation gate (AT-02), critical preemption
# (AT-05), interrupted transfer (AT-06) and persistence-backed restart
# recovery (AT-07).
#
# These helpers do not modify the existing ``run_encounter``; the CLI
# keeps using it so first-slice determinism is preserved.
# ---------------------------------------------------------------------------


def _send_capsule(
    *,
    sender: SimulatedPeer,
    receiver: SimulatedPeer,
    capsule_payload: dict,
    logger: events.EventLogger,
    object_id: str,
) -> bool:
    """Send a capsule payload through the in-process transport.

    Returns ``True`` when the capsule was delivered successfully;
    returns ``False`` when the payload could not be decoded as JSON.
    Does not consult the human-confirmation gate -- the caller is
    responsible for invoking the gate first.
    """
    payload = json.dumps(
        capsule_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    sender.send(payload)
    sender.deliver_to(receiver)
    message = receiver.receive()
    logger.advance(1)
    try:
        decoded = json.loads(message.decode("utf-8"))  # noqa: F841
    except Exception:
        logger.emit(
            events.EventType.CHUNK_REJECTED,
            sender_id=sender.peer_id,
            receiver_id=receiver.peer_id,
            object_id=object_id,
            detail={"reason": "malformed_capsule"},
        )
        return False
    logger.emit(
        events.EventType.CAPSULE_DELIVERED,
        sender_id=sender.peer_id,
        receiver_id=receiver.peer_id,
        object_id=object_id,
        representation_id=f"capsule:{capsule_payload['capsule_id']}",
        detail={"capsule_id": capsule_payload["capsule_id"]},
    )
    return True


def _send_manifest(
    *,
    sender: SimulatedPeer,
    receiver: SimulatedPeer,
    manifest_payload: dict,
    logger: events.EventLogger,
    object_id: str,
) -> None:
    payload = json.dumps(
        manifest_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    sender.send(payload)
    sender.deliver_to(receiver)
    receiver.receive()
    logger.advance(1)
    logger.emit(
        events.EventType.MANIFEST_DELIVERED,
        sender_id=sender.peer_id,
        receiver_id=receiver.peer_id,
        object_id=object_id,
        representation_id=f"manifest:{manifest_payload['manifest_id']}",
        detail={"manifest_id": manifest_payload["manifest_id"]},
    )


def _send_chunk(
    *,
    sender: SimulatedPeer,
    receiver: SimulatedPeer,
    chunk: Chunk,
    logger: events.EventLogger,
    result: "EncounterResult",
) -> bool:
    """Send one media chunk. Returns True when stored, False when rejected."""
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
        return False
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
            object_id=chunk.object_id,
            representation_id=chunk.representation_id,
            chunk_index=chunk.chunk_index,
            detail={"reason": exc.code, "detail": exc.detail},
        )
        result.rejected_indexes.append(chunk.chunk_index)
        return False
    logger.emit(
        events.EventType.CHUNK_DELIVERED,
        sender_id=sender.peer_id,
        receiver_id=receiver.peer_id,
        object_id=chunk.object_id,
        representation_id=chunk.representation_id,
        chunk_index=chunk.chunk_index,
    )
    result.delivered_chunk_indexes.append(chunk.chunk_index)
    return True


def run_with_human_gate(
    *,
    sender: SimulatedPeer,
    receiver: SimulatedPeer,
    logger: events.EventLogger,
    items: list,
    capsule_payload: dict,
    manifest_payload: dict,
    chunks: list,
) -> EncounterResult:
    """AT-02 driver.

    Behaves like :func:`run_encounter` but invokes the human-confirmation
    gate on the capsule. ``human_confirmed=True`` is delivered
    normally; ``human_confirmed=False`` raises
    ``ProtocolError("HUMAN_CONFIRMATION_MISSING")`` and the driver
    emits a deterministic ``CAPSULE_REJECTED`` event before the
    exception propagates.
    """
    from . import gate, validation as _validation

    open_encounter(sender, receiver, logger)

    chunk_by_key = {
        (c.object_id, c.representation_id, c.chunk_index): c for c in chunks
    }

    result = EncounterResult(sender_id=sender.peer_id, receiver_id=receiver.peer_id)
    try:
        _validation.validate_payload("shongket.capsule.v1", capsule_payload)
        gate.capsule_human_confirmation(
            capsule_payload,
            logger=logger,
            sender_id=sender.peer_id,
            receiver_id=receiver.peer_id,
        )
        for it in items:
            logger.advance(1)
            if it.representation_id and it.representation_id.startswith("capsule:"):
                _send_capsule(
                    sender=sender,
                    receiver=receiver,
                    capsule_payload=capsule_payload,
                    logger=logger,
                    object_id=it.object_id,
                )
                result.delivered_capsule = True
                continue
            if it.representation_id and it.representation_id.startswith("manifest:"):
                _send_manifest(
                    sender=sender,
                    receiver=receiver,
                    manifest_payload=manifest_payload,
                    logger=logger,
                    object_id=it.object_id,
                )
                result.delivered_manifest = True
                continue
            if it.representation_id is None or it.chunk_index is None:
                continue
            chunk = chunk_by_key.get(
                (it.object_id, it.representation_id, it.chunk_index)
            )
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
            _send_chunk(
                sender=sender,
                receiver=receiver,
                chunk=chunk,
                logger=logger,
                result=result,
            )
    finally:
        close_encounter(sender, receiver, logger)
    return result


def run_preemption_encounter(
    *,
    sender: SimulatedPeer,
    receiver: SimulatedPeer,
    logger: events.EventLogger,
    bulk_items: list,
    bulk_chunks: list,
    critical_capsule_payload: dict,
    critical_object_id: str,
    inject_after_chunks: int,
) -> EncounterResult:
    """AT-05 driver.

    Begin an ordinary bulk transfer for ``bulk_items``. After exactly
    ``inject_after_chunks`` chunks have been delivered, inject the
    ``critical_capsule_payload`` at a deterministic tick, log the
    preemption, deliver the critical, then resume the bulk transfer
    from the next missing chunk. Already-delivered chunks are not
    re-sent.
    """
    from . import gate, validation as _validation

    open_encounter(sender, receiver, logger)

    chunk_by_key = {
        (c.object_id, c.representation_id, c.chunk_index): c for c in bulk_chunks
    }

    result = EncounterResult(sender_id=sender.peer_id, receiver_id=receiver.peer_id)
    delivered_so_far = 0
    pending_bulk = list(bulk_items)
    injected = False

    while pending_bulk:
        it = pending_bulk.pop(0)
        if (
            not injected
            and it.representation_id is not None
            and not it.representation_id.startswith(("capsule:", "manifest:"))
            and delivered_so_far >= inject_after_chunks
        ):
            logger.advance(1)
            logger.emit(
                events.EventType.PREEMPTION_LOGGED,
                sender_id=sender.peer_id,
                receiver_id=receiver.peer_id,
                object_id=critical_object_id,
                detail={
                    "delivered_before_preempt": delivered_so_far,
                    "pending_bulk": len(pending_bulk),
                    "capsule_id": critical_capsule_payload["capsule_id"],
                },
            )
            _validation.validate_payload(
                "shongket.capsule.v1", critical_capsule_payload
            )
            gate.capsule_human_confirmation(
                critical_capsule_payload,
                logger=logger,
                sender_id=sender.peer_id,
                receiver_id=receiver.peer_id,
            )
            ok = _send_capsule(
                sender=sender,
                receiver=receiver,
                capsule_payload=critical_capsule_payload,
                logger=logger,
                object_id=critical_object_id,
            )
            if ok:
                result.delivered_capsule = True
            injected = True
            pending_bulk.insert(0, it)
            continue

        logger.advance(1)
        if it.representation_id is None or it.chunk_index is None:
            continue
        chunk = chunk_by_key.get(
            (it.object_id, it.representation_id, it.chunk_index)
        )
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
        if _send_chunk(
            sender=sender,
            receiver=receiver,
            chunk=chunk,
            logger=logger,
            result=result,
        ):
            delivered_so_far += 1

    close_encounter(sender, receiver, logger)
    return result


def run_interrupted_transfer(
    *,
    sender: SimulatedPeer,
    receiver: SimulatedPeer,
    logger: events.EventLogger,
    items: list,
    capsule_payload: dict,
    manifest_payload: dict,
    chunks: list,
    peer_disappear_after_chunks: int,
) -> EncounterResult:
    """AT-06 first-encounter driver.

    Deliver capsule, manifest and the first
    ``peer_disappear_after_chunks`` chunks, then close the encounter
    (the ``peer disappears`` moment). Verified chunks remain in the
    receiver store. The caller is responsible for invoking
    :func:`run_resume_transfer` after a reconnect.
    """
    open_encounter(sender, receiver, logger)

    chunk_by_key = {
        (c.object_id, c.representation_id, c.chunk_index): c for c in chunks
    }

    result = EncounterResult(sender_id=sender.peer_id, receiver_id=receiver.peer_id)
    delivered = 0
    try:
        for it in items:
            logger.advance(1)
            if it.representation_id and it.representation_id.startswith("capsule:"):
                _send_capsule(
                    sender=sender,
                    receiver=receiver,
                    capsule_payload=capsule_payload,
                    logger=logger,
                    object_id=it.object_id,
                )
                result.delivered_capsule = True
                continue
            if it.representation_id and it.representation_id.startswith("manifest:"):
                _send_manifest(
                    sender=sender,
                    receiver=receiver,
                    manifest_payload=manifest_payload,
                    logger=logger,
                    object_id=it.object_id,
                )
                result.delivered_manifest = True
                continue
            if it.representation_id is None or it.chunk_index is None:
                continue
            chunk = chunk_by_key.get(
                (it.object_id, it.representation_id, it.chunk_index)
            )
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
            if delivered >= peer_disappear_after_chunks:
                logger.emit(
                    events.EventType.TRANSFER_INTERRUPTED,
                    sender_id=sender.peer_id,
                    receiver_id=receiver.peer_id,
                    object_id=it.object_id,
                    representation_id=it.representation_id,
                    chunk_index=it.chunk_index,
                    detail={
                        "delivered_chunks": delivered,
                        "missing_chunks": _count_missing(
                            receiver, items, chunk_by_key
                        ),
                    },
                )
                return result
            if _send_chunk(
                sender=sender,
                receiver=receiver,
                chunk=chunk,
                logger=logger,
                result=result,
            ):
                delivered += 1
    finally:
        close_encounter(sender, receiver, logger)
    return result


def _count_missing(
    receiver: SimulatedPeer,
    items: list,
    chunk_by_key: dict,
) -> int:
    n = 0
    for it in items:
        if it.representation_id is None or it.chunk_index is None:
            continue
        if it.representation_id.startswith(("capsule:", "manifest:")):
            continue
        key = (it.object_id, it.representation_id, it.chunk_index)
        if key in chunk_by_key and not receiver.store.has(*key):
            n += 1
    return n


def run_resume_transfer(
    *,
    sender: SimulatedPeer,
    receiver: SimulatedPeer,
    logger: events.EventLogger,
    items: list,
    chunks: list,
) -> EncounterResult:
    """AT-06 second-encounter driver.

    Reconnects and transfers only the missing chunks. Already-verified
    chunks are NOT re-sent (the request is filtered against
    ``receiver.store.has``).
    """
    open_encounter(sender, receiver, logger)

    chunk_by_key = {
        (c.object_id, c.representation_id, c.chunk_index): c for c in chunks
    }

    result = EncounterResult(sender_id=sender.peer_id, receiver_id=receiver.peer_id)
    requested = 0
    try:
        for it in items:
            if it.representation_id is None or it.chunk_index is None:
                continue
            if it.representation_id.startswith(("capsule:", "manifest:")):
                continue
            key = (it.object_id, it.representation_id, it.chunk_index)
            if key not in chunk_by_key:
                continue
            if receiver.store.has(*key):
                continue
            logger.advance(1)
            logger.emit(
                events.EventType.TRANSFER_RESUMED,
                sender_id=sender.peer_id,
                receiver_id=receiver.peer_id,
                object_id=it.object_id,
                representation_id=it.representation_id,
                chunk_index=it.chunk_index,
                detail={"requested": requested},
            )
            requested += 1
            _send_chunk(
                sender=sender,
                receiver=receiver,
                chunk=chunk_by_key[key],
                logger=logger,
                result=result,
            )
    finally:
        close_encounter(sender, receiver, logger)
    return result
