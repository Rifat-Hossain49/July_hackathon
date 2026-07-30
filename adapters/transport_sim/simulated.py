"""Deterministic in-memory implementation of the transport contract."""

from __future__ import annotations

from collections import defaultdict, deque

from shongket_core.capabilities import (
    NegotiatedCapabilities,
    PeerCapabilities,
    ensure_payload_fits,
    negotiate_capabilities,
)

from .contract import (
    Ack,
    PeerRef,
    TransportEvent,
    TransportEventKind,
    TransportFailure,
)


class InMemoryNetwork:
    """Explicit peer registry and byte queues with no clock or randomness."""

    def __init__(self) -> None:
        self._adapters: dict[str, SimulatedTransportAdapter] = {}
        self._queues: dict[tuple[str, str], deque[bytes]] = defaultdict(deque)

    def register(self, adapter: "SimulatedTransportAdapter") -> None:
        peer_id = adapter.capability_report().peer_id
        if peer_id in self._adapters:
            raise ValueError(f"peer {peer_id!r} is already registered")
        self._adapters[peer_id] = adapter

    def peers_for(self, peer_id: str) -> tuple[PeerRef, ...]:
        return tuple(
            PeerRef(candidate)
            for candidate in sorted(self._adapters)
            if candidate != peer_id
        )

    def report(self, peer: PeerRef) -> PeerCapabilities:
        try:
            return self._adapters[peer.peer_id].capability_report()
        except KeyError as exc:
            raise TransportFailure("peer_unavailable") from exc

    def deliver(self, sender: str, receiver: str, body: bytes) -> None:
        if receiver not in self._adapters:
            raise TransportFailure("peer_unavailable")
        self._queues[(receiver, sender)].append(bytes(body))

    def receive(self, receiver: str, sender: str) -> bytes:
        queue = self._queues[(receiver, sender)]
        if not queue:
            raise TransportFailure("no_frame_available")
        return queue.popleft()


class _InMemorySession:
    def __init__(
        self,
        network: InMemoryNetwork,
        *,
        local_peer_id: str,
        remote_peer_id: str,
        negotiated: NegotiatedCapabilities,
    ) -> None:
        self._network = network
        self._local = local_peer_id
        self._remote = remote_peer_id
        self._negotiated = negotiated
        self._events: list[TransportEvent] = []
        self._interrupted = False
        self._closed = False
        self._note(TransportEventKind.CONNECTED)

    def _note(self, kind: TransportEventKind, byte_count: int = 0) -> None:
        self._events.append(
            TransportEvent(
                seq=len(self._events),
                kind=kind,
                byte_count=byte_count,
            )
        )

    def _require_open(self) -> None:
        if self._closed:
            raise TransportFailure("session_closed")
        if self._interrupted:
            raise TransportFailure("session_interrupted")

    def send(self, frame_body: bytes) -> Ack:
        self._require_open()
        ensure_payload_fits(len(frame_body), self._negotiated.max_payload)
        self._network.deliver(self._local, self._remote, frame_body)
        self._note(TransportEventKind.PROGRESS, len(frame_body))
        return Ack(accepted=True, byte_count=len(frame_body))

    def receive(self) -> bytes:
        self._require_open()
        body = self._network.receive(self._local, self._remote)
        ensure_payload_fits(len(body), self._negotiated.max_payload)
        self._note(TransportEventKind.PROGRESS, len(body))
        return body

    def interrupt(self) -> None:
        if self._closed or self._interrupted:
            return
        self._interrupted = True
        self._note(TransportEventKind.INTERRUPTED)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._note(TransportEventKind.CLOSED)

    def events(self) -> tuple[TransportEvent, ...]:
        return tuple(self._events)


class SimulatedTransportAdapter:
    """Required deterministic adapter used by shared conformance tests."""

    def __init__(
        self,
        network: InMemoryNetwork,
        capabilities: PeerCapabilities,
    ) -> None:
        if "simulated" not in capabilities.transports:
            raise ValueError("simulated adapter requires the simulated transport")
        self._network = network
        self._capabilities = capabilities
        network.register(self)

    def discover(self) -> tuple[PeerRef, ...]:
        return self._network.peers_for(self._capabilities.peer_id)

    def capabilities(self, peer: PeerRef) -> PeerCapabilities:
        return self._network.report(peer)

    def connect(self, peer: PeerRef) -> _InMemorySession:
        remote = self.capabilities(peer)
        result = negotiate_capabilities(
            self._capabilities,
            remote,
            enabled_transports=("simulated",),
        )
        if not result.accepted or result.negotiated is None:
            raise TransportFailure(result.reason or "negotiation_declined")
        return _InMemorySession(
            self._network,
            local_peer_id=self._capabilities.peer_id,
            remote_peer_id=peer.peer_id,
            negotiated=result.negotiated,
        )

    def capability_report(self) -> PeerCapabilities:
        return self._capabilities
