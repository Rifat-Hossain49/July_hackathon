"""Simulated peer and in-process transport (M0).

Implements the ``SimulatedTransport`` described in SYSTEM_ARCHITECTURE.md §6.1
for the M0 slice. Two peers exchange bytes through an in-process pipe with
deterministic ordering and no loss. Real radio (Android transport adapters,
Bluetooth, Wi-Fi Direct, Nearby Connections) is explicitly out of scope.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from . import events
from .store import ContentAddressedStore


@dataclass
class SimulatedPeer:
    """One deterministic peer: identity, store, and transport mailbox."""

    peer_id: str
    store: ContentAddressedStore = field(default_factory=ContentAddressedStore)
    _outbox: deque[bytes] = field(default_factory=deque)
    _inbox: deque[bytes] = field(default_factory=deque)

    # -- transport (in-process) ---------------------------------------------

    def send(self, payload: bytes) -> None:
        self._outbox.append(payload)

    def receive(self) -> bytes | None:
        if not self._inbox:
            return None
        return self._inbox.popleft()

    def deliver_to(self, peer: "SimulatedPeer") -> None:
        """Drain outgoing bytes to ``peer``'s inbox. No loss, no reorder."""
        while self._outbox:
            peer._inbox.append(self._outbox.popleft())

    def has_outgoing(self) -> bool:
        return bool(self._outbox)

    def has_incoming(self) -> bool:
        return bool(self._inbox)


@dataclass
class Envelope:
    """In-process envelope shared between two peers during an encounter.

    Wraps the encoded ``Event`` so the simulator can decode it as if it
    arrived over a real transport. The format is deliberately simple:
    ``length:4 bytes BE || json payload``.
    """

    payload: bytes

    def encode(self) -> bytes:
        import json
        body = json.loads(self.payload.decode("utf-8"))
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def open_encounter(a: SimulatedPeer, b: SimulatedPeer, logger: events.EventLogger) -> None:
    """Mark the start of an in-process encounter between ``a`` and ``b``."""
    logger.advance(1)
    logger.emit(events.EventType.ENCOUNTER_OPENED, sender_id=a.peer_id, receiver_id=b.peer_id)
    logger.advance(1)
    logger.emit(events.EventType.ENCOUNTER_OPENED, sender_id=b.peer_id, receiver_id=a.peer_id)


def close_encounter(a: SimulatedPeer, b: SimulatedPeer, logger: events.EventLogger) -> None:
    """Mark the end of an in-process encounter between ``a`` and ``b``."""
    logger.advance(1)
    logger.emit(events.EventType.ENCOUNTER_CLOSED, sender_id=a.peer_id, receiver_id=b.peer_id)
    logger.advance(1)
    logger.emit(events.EventType.ENCOUNTER_CLOSED, sender_id=b.peer_id, receiver_id=a.peer_id)
    logger.flush()
