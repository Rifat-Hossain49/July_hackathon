"""Process stream binding for the shared transport contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from shongket_core.capabilities import (
    NegotiatedCapabilities,
    PeerCapabilities,
    ensure_payload_fits,
    negotiate_capabilities,
)

from adapters.transport_sim.contract import (
    Ack,
    PeerRef,
    TransportEvent,
    TransportEventKind,
    TransportFailure,
)

from .endpoint import StreamFrameEndpoint
from .frame import EndOfStream


class ProcessSession:
    def __init__(
        self,
        endpoint: StreamFrameEndpoint,
        negotiated: NegotiatedCapabilities,
    ) -> None:
        self._endpoint = endpoint
        self._negotiated = negotiated
        self._events: list[TransportEvent] = []
        self._interrupted = False
        self._closed = False
        self._note(TransportEventKind.CONNECTED)

    def _note(self, kind: TransportEventKind, byte_count: int = 0) -> None:
        self._events.append(
            TransportEvent(len(self._events), kind, byte_count)
        )

    def _require_open(self) -> None:
        if self._closed:
            raise TransportFailure("session_closed")
        if self._interrupted:
            raise TransportFailure("session_interrupted")

    def send(self, frame_body: bytes) -> Ack:
        self._require_open()
        ensure_payload_fits(len(frame_body), self._negotiated.max_payload)
        self._endpoint.send(frame_body)
        self._note(TransportEventKind.PROGRESS, len(frame_body))
        return Ack(accepted=True, byte_count=len(frame_body))

    def receive(self) -> bytes:
        self._require_open()
        try:
            body = self._endpoint.receive()
        except EndOfStream as exc:
            self.interrupt()
            raise TransportFailure("session_interrupted") from exc
        ensure_payload_fits(len(body), self._negotiated.max_payload)
        self._note(TransportEventKind.PROGRESS, len(body))
        return body

    def interrupt(self) -> None:
        if self._closed or self._interrupted:
            return
        self._interrupted = True
        self._endpoint.close()
        self._note(TransportEventKind.INTERRUPTED)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._endpoint.close()
        self._note(TransportEventKind.CLOSED)

    def events(self) -> tuple[TransportEvent, ...]:
        return tuple(self._events)


class ProcessTransportAdapter:
    """Configured stdio/loopback adapter with externally supplied streams."""

    def __init__(
        self,
        local: PeerCapabilities,
        remotes: Mapping[str, PeerCapabilities],
        connector: Callable[[PeerRef, NegotiatedCapabilities], StreamFrameEndpoint],
        *,
        enabled_transport: str,
    ) -> None:
        if enabled_transport not in local.transports:
            raise ValueError("enabled transport is absent from local capabilities")
        self._local = local
        self._remotes = dict(remotes)
        self._connector = connector
        self._enabled = enabled_transport

    def discover(self) -> tuple[PeerRef, ...]:
        return tuple(PeerRef(peer_id) for peer_id in sorted(self._remotes))

    def capabilities(self, peer: PeerRef) -> PeerCapabilities:
        try:
            return self._remotes[peer.peer_id]
        except KeyError as exc:
            raise TransportFailure("peer_unavailable") from exc

    def connect(self, peer: PeerRef) -> ProcessSession:
        result = negotiate_capabilities(
            self._local,
            self.capabilities(peer),
            enabled_transports=(self._enabled,),
        )
        if not result.accepted or result.negotiated is None:
            raise TransportFailure(result.reason or "negotiation_declined")
        return ProcessSession(
            self._connector(peer, result.negotiated),
            result.negotiated,
        )

    def capability_report(self) -> PeerCapabilities:
        return self._local
