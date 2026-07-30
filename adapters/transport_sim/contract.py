"""Platform-neutral byte and liveness contract for transport bindings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from shongket_core.capabilities import PeerCapabilities


@dataclass(frozen=True, order=True)
class PeerRef:
    peer_id: str

    def __post_init__(self) -> None:
        if not self.peer_id:
            raise ValueError("peer_id must not be empty")


class TransportEventKind(str, Enum):
    CONNECTED = "connected"
    PROGRESS = "progress"
    INTERRUPTED = "interrupted"
    CLOSED = "closed"


@dataclass(frozen=True)
class TransportEvent:
    seq: int
    kind: TransportEventKind
    byte_count: int = 0

    def as_dict(self) -> dict:
        return {
            "seq": self.seq,
            "kind": self.kind.value,
            "byte_count": self.byte_count,
        }


@dataclass(frozen=True)
class Ack:
    accepted: bool
    byte_count: int


class TransportFailure(Exception):
    """Deterministic transport/liveness failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Session(Protocol):
    def send(self, frame_body: bytes) -> Ack: ...

    def receive(self) -> bytes: ...

    def interrupt(self) -> None: ...

    def close(self) -> None: ...

    def events(self) -> tuple[TransportEvent, ...]: ...


class TransportAdapter(Protocol):
    def discover(self) -> tuple[PeerRef, ...]: ...

    def capabilities(self, peer: PeerRef) -> PeerCapabilities: ...

    def connect(self, peer: PeerRef) -> Session: ...

    def capability_report(self) -> PeerCapabilities: ...
