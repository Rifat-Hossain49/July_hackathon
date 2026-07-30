"""Bounded canonical framing and local-process transport endpoints."""

from .client import ProcessClient, ProcessTranscript
from .endpoint import (
    LoopbackListener,
    SocketFrameEndpoint,
    StreamFrameEndpoint,
    connect_loopback,
)
from .frame import EndOfStream, FrameCodec
from .session import ProcessSession, ProcessTransportAdapter

__all__ = [
    "EndOfStream",
    "FrameCodec",
    "LoopbackListener",
    "SocketFrameEndpoint",
    "StreamFrameEndpoint",
    "connect_loopback",
    "ProcessSession",
    "ProcessTransportAdapter",
    "ProcessClient",
    "ProcessTranscript",
]
