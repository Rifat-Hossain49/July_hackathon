"""Deterministic transport-capability negotiation.

The transport boundary reports what each endpoint can carry. This module,
owned by the canonical core, decides whether those reports form a usable
session. Concrete adapters must not weaken the negotiated payload bound or
reinterpret the receiver's ``public_only`` declaration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .errors import ErrorCode, ProtocolError


MAX_TRANSPORT_PAYLOAD = 1_048_576


@dataclass(frozen=True)
class PeerCapabilities:
    """Canonical capability values declared before inventory exchange."""

    peer_id: str
    transports: tuple[str, ...]
    max_payload: int = MAX_TRANSPORT_PAYLOAD
    public_only: bool = False

    def __post_init__(self) -> None:
        if not self.peer_id:
            raise ValueError("peer_id must not be empty")
        if isinstance(self.max_payload, bool) or not isinstance(self.max_payload, int):
            raise ValueError("max_payload must be an integer")
        if not isinstance(self.public_only, bool):
            raise ValueError("public_only must be boolean")
        if any(not isinstance(item, str) or not item for item in self.transports):
            raise ValueError("transports must contain non-empty strings")
        if len(set(self.transports)) != len(self.transports):
            raise ValueError("transports must not contain duplicates")

    def as_dict(self) -> dict:
        return {
            "peer_id": self.peer_id,
            "transports": list(self.transports),
            "max_payload": self.max_payload,
            "public_only": self.public_only,
        }


@dataclass(frozen=True)
class NegotiatedCapabilities:
    """Successful, deterministic capability intersection."""

    transport: str
    max_payload: int
    receiver_public_only: bool

    def as_dict(self) -> dict:
        return {
            "transport": self.transport,
            "max_payload": self.max_payload,
            "receiver_public_only": self.receiver_public_only,
        }


@dataclass(frozen=True)
class NegotiationResult:
    """A successful session description or a clean decline."""

    accepted: bool
    negotiated: NegotiatedCapabilities | None
    reason: str | None

    @classmethod
    def decline(cls, reason: str) -> "NegotiationResult":
        return cls(accepted=False, negotiated=None, reason=reason)


def negotiate_capabilities(
    sender: PeerCapabilities,
    receiver: PeerCapabilities,
    *,
    enabled_transports: Iterable[str],
) -> NegotiationResult:
    """Intersect two reports without consulting adapter-specific state.

    When more than one declared transport is enabled, lexical ordering is
    the deterministic tie-breaker. A non-positive payload declaration
    declines the session rather than being coerced.
    """

    enabled = {
        item
        for item in enabled_transports
        if isinstance(item, str) and item
    }
    shared = sorted(set(sender.transports) & set(receiver.transports) & enabled)
    if not shared:
        return NegotiationResult.decline("no_usable_transport")

    if sender.max_payload <= 0 or receiver.max_payload <= 0:
        return NegotiationResult.decline("non_positive_payload_limit")

    max_payload = min(
        sender.max_payload,
        receiver.max_payload,
        MAX_TRANSPORT_PAYLOAD,
    )
    if max_payload <= 0:
        return NegotiationResult.decline("non_positive_payload_limit")

    return NegotiationResult(
        accepted=True,
        negotiated=NegotiatedCapabilities(
            transport=shared[0],
            max_payload=max_payload,
            receiver_public_only=receiver.public_only,
        ),
        reason=None,
    )


def ensure_payload_fits(payload_size: int, negotiated_limit: int) -> None:
    """Refuse an over-limit body before an adapter transmits it."""

    if isinstance(payload_size, bool) or not isinstance(payload_size, int):
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            "payload_size must be an integer",
        )
    if isinstance(negotiated_limit, bool) or not isinstance(negotiated_limit, int):
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            "negotiated_limit must be an integer",
        )
    if payload_size <= 0 or negotiated_limit <= 0:
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            "payload sizes and negotiated limits must be positive",
        )
    if payload_size > min(negotiated_limit, MAX_TRANSPORT_PAYLOAD):
        raise ProtocolError(
            ErrorCode.PAYLOAD_TOO_LARGE,
            f"payload of {payload_size} bytes exceeds negotiated limit "
            f"{min(negotiated_limit, MAX_TRANSPORT_PAYLOAD)}",
        )
