"""Structured event logger (M0).

The logger produces JSONL output consumable by the experiment harness and
the acceptance-test evidence requirements. Events are ordered by a
monotonic tick counter; no wall-clock is used in tests.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import IO, Any


class EventType(str, Enum):
    """M0 event types emitted by the simulator."""

    OBJECT_FINALIZED = "object_finalized"
    CAPSULE_QUEUED = "capsule_queued"
    CAPSULE_DELIVERED = "capsule_delivered"
    CAPSULE_REJECTED = "capsule_rejected"
    MANIFEST_DELIVERED = "manifest_delivered"
    CHUNK_QUEUED = "chunk_queued"
    CHUNK_DELIVERED = "chunk_delivered"
    CHUNK_DUPLICATE = "chunk_duplicate"
    CHUNK_REJECTED = "chunk_rejected"
    ENCOUNTER_OPENED = "encounter_opened"
    ENCOUNTER_CLOSED = "encounter_closed"
    PREEMPTION_LOGGED = "preemption_logged"
    TRANSFER_INTERRUPTED = "transfer_interrupted"
    TRANSFER_RESUMED = "transfer_resumed"
    RESTART_COMPLETED = "restart_completed"
    # Slice 3 (AT-08 multi-peer completion, AT-11 expiry, AT-12 budget).
    FRAGMENT_REQUESTED = "fragment_requested"
    MULTI_PEER_COMPLETED = "multi_peer_completed"
    FORWARD_QUEUED = "forward_queued"
    FORWARD_REFUSED = "forward_refused"
    STORAGE_BUDGET_REJECTED = "storage_budget_rejected"
    # Slice 4 (AT-15 manual fallback, AT-16 consent, AT-17 oversize).
    MODEL_FALLBACK = "model_fallback"
    CONSENT_REJECTED = "consent_rejected"
    PAYLOAD_REJECTED = "payload_rejected"


@dataclass
class Event:
    """A single structured event."""

    tick: int
    type: EventType
    sender_id: str
    receiver_id: str
    object_id: str | None = None
    representation_id: str | None = None
    chunk_index: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_jsonl(self) -> str:
        d = asdict(self)
        d["type"] = self.type.value
        return json.dumps(d, sort_keys=True, separators=(",", ":"))


class EventLogger:
    """Ordered, deterministic event recorder with optional JSONL sink."""

    def __init__(self, sink: IO[str] | None = None) -> None:
        self._events: list[Event] = []
        self._tick = 0
        self._sink = sink

    def advance(self, ticks: int = 1) -> None:
        self._tick += ticks

    def emit(
        self,
        type: EventType,
        *,
        sender_id: str,
        receiver_id: str,
        object_id: str | None = None,
        representation_id: str | None = None,
        chunk_index: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> Event:
        ev = Event(
            tick=self._tick,
            type=type,
            sender_id=sender_id,
            receiver_id=receiver_id,
            object_id=object_id,
            representation_id=representation_id,
            chunk_index=chunk_index,
            detail=detail or {},
        )
        self._events.append(ev)
        if self._sink is not None:
            self._sink.write(ev.to_jsonl() + "\n")
        return ev

    @property
    def events(self) -> list[Event]:
        return list(self._events)

    def of_type(self, type: EventType) -> list[Event]:
        return [e for e in self._events if e.type == type]

    def flush(self) -> None:
        if self._sink is not None:
            self._sink.flush()
