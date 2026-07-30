"""Forwarding admission policy (M1 — AT-32/33/34/35).

Implements the six-clause admission rule frozen in ``PROTOCOL_SPEC.md``
§6 under decisions D-M1-01, D-M1-02, D-M1-03 and D-M1-A3.

Clause order is fixed and documented, because the order decides which
code a caller sees when several clauses would fail. Evaluating cheapest
and most objective first keeps the reported reason stable and
explainable:

1. expiry            → ``EXPIRED``
2. hop limit         → ``HOP_LIMIT``
3. copy budget       → ``COPY_BUDGET``
4. human confirmation→ ``HUMAN_CONFIRMATION_MISSING``
5. consent           → ``CONSENT_REQUIRED``
6. peer ``public_only`` → ``PEER_REFUSES_PRIVATE``

Every refusal happens **before** anything is queued, transmitted or
persisted, and every refusal is deterministic: the same inputs always
produce the same code and the same detail string.

Forwarding state (``hop_count``, ``remaining_copy_budget``) is mutable
transport state. It is excluded from canonical identity bytes, so
advancing it never changes ``object_id`` or any fragment digest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from . import codec
from .errors import ErrorCode, ProtocolError
from .evidence import EvidenceLog, EventCode


VISIBILITY_PUBLIC = "public"
VISIBILITY_PRIVATE = "private"
VALID_VISIBILITY = frozenset({VISIBILITY_PUBLIC, VISIBILITY_PRIVATE})

FIELD_VISIBILITY = "visibility"
FIELD_CONSENT = "forwarding_consent"
FIELD_HOP_COUNT = "hop_count"
FIELD_REMAINING_COPY_BUDGET = "remaining_copy_budget"


@dataclass(frozen=True)
class PeerCapability:
    """The subset of ``shongket.peer.v1`` the M1 policy consults."""

    peer_id: str
    public_only: bool = False


@dataclass(frozen=True)
class ForwardDecision:
    """Outcome of evaluating the admission rule."""

    admitted: bool
    clause: str
    code: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def read_visibility(manifest: Mapping[str, object]) -> str:
    """Return the object's visibility, defaulting to public when absent.

    A present-but-invalid value is refused rather than defaulted: an
    unrecognised privacy class must never be silently treated as public.
    """
    if FIELD_VISIBILITY not in manifest:
        return VISIBILITY_PUBLIC
    value = manifest[FIELD_VISIBILITY]
    if not isinstance(value, str) or value not in VALID_VISIBILITY:
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"{FIELD_VISIBILITY} must be one of {sorted(VALID_VISIBILITY)}, "
            f"got {value!r}",
            object_id=_object_id(manifest),
        )
    return value


def has_consent(manifest: Mapping[str, object]) -> bool:
    """True only for a literal boolean ``True``.

    A truthy string or integer is *not* consent. A consent decision
    recorded in an ambiguous type is not evidence that a human consented,
    so it is refused rather than coerced.
    """
    return manifest.get(FIELD_CONSENT) is True


def consent_is_malformed(manifest: Mapping[str, object]) -> bool:
    """True when the consent field is present but not a boolean."""
    if FIELD_CONSENT not in manifest:
        return False
    return not isinstance(manifest[FIELD_CONSENT], bool)


def _object_id(manifest: Mapping[str, object]) -> str | None:
    value = manifest.get("object_id")
    return value if isinstance(value, str) else None


def _int_field(manifest: Mapping[str, object], name: str, default: int) -> int:
    if name not in manifest:
        return default
    value = manifest[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"{name} must be an integer, got {type(value).__name__}",
            object_id=_object_id(manifest),
        )
    if value < 0:
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"{name} must not be negative, got {value}",
            object_id=_object_id(manifest),
        )
    return value


def evaluate_forwarding(
    manifest: Mapping[str, object],
    *,
    now_unix: int,
    peer: PeerCapability,
    human_confirmed: bool = True,
    evidence: EvidenceLog | None = None,
) -> ForwardDecision:
    """Evaluate the six-clause admission rule without mutating anything.

    Returns a :class:`ForwardDecision`. It never raises for a policy
    refusal — a refusal is an expected outcome carrying a canonical code
    — but it does raise ``SCHEMA_INVALID`` for a structurally invalid
    privacy or forwarding-state field, because that is a malformed
    payload rather than a policy decision.
    """
    object_id = _object_id(manifest)

    def refuse(clause: str, code: ErrorCode, **detail: Any) -> ForwardDecision:
        payload = {"clause": clause, "code": code.value, **detail}
        if object_id is not None:
            payload["object_id"] = object_id
        if evidence is not None:
            evidence.record(EventCode.FORWARD_REFUSED, **payload)
        return ForwardDecision(
            admitted=False, clause=clause, code=code.value, detail=payload
        )

    # 1. expiry (inclusive: expired at exactly expires_at_unix)
    expires_at = manifest.get("expires_at_unix")
    if expires_at is not None:
        if isinstance(expires_at, bool) or not isinstance(expires_at, int):
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"expires_at_unix must be an integer or null, got "
                f"{type(expires_at).__name__}",
                object_id=object_id,
            )
        if now_unix >= expires_at:
            return refuse(
                "expiry",
                ErrorCode.EXPIRED,
                now_unix=now_unix,
                expires_at_unix=expires_at,
            )

    # 2. hop limit
    hop_limit = _int_field(manifest, "hop_limit", 6)
    hop_count = _int_field(manifest, FIELD_HOP_COUNT, 0)
    if hop_count + 1 > hop_limit:
        return refuse(
            "hop_limit",
            ErrorCode.HOP_LIMIT,
            hop_count=hop_count,
            hop_limit=hop_limit,
        )

    # 3. copy budget
    copy_budget = _int_field(manifest, "copy_budget", 8)
    remaining = _int_field(manifest, FIELD_REMAINING_COPY_BUDGET, copy_budget)
    if remaining < 1:
        return refuse(
            "copy_budget",
            ErrorCode.COPY_BUDGET,
            remaining_copy_budget=remaining,
            copy_budget=copy_budget,
        )

    # 4. human confirmation
    if not human_confirmed:
        return refuse("human_confirmation", ErrorCode.HUMAN_CONFIRMATION_MISSING)

    # 5. consent (private objects only)
    visibility = read_visibility(manifest)
    if visibility == VISIBILITY_PRIVATE:
        if consent_is_malformed(manifest):
            return refuse(
                "consent",
                ErrorCode.CONSENT_REQUIRED,
                reason="consent_malformed",
                consent_type=type(manifest[FIELD_CONSENT]).__name__,
            )
        if not has_consent(manifest):
            return refuse(
                "consent",
                ErrorCode.CONSENT_REQUIRED,
                reason="consent_missing"
                if FIELD_CONSENT not in manifest
                else "consent_false",
            )

        # 6. peer public_only — consent never overrides it
        if peer.public_only:
            return refuse(
                "peer_public_only",
                ErrorCode.PEER_REFUSES_PRIVATE,
                peer_id=peer.peer_id,
                visibility=visibility,
            )

    if evidence is not None:
        evidence.record(
            EventCode.FORWARD_ADMITTED,
            visibility=visibility,
            hop_count=hop_count,
            remaining_copy_budget=remaining,
            **({"object_id": object_id} if object_id is not None else {}),
        )
    return ForwardDecision(admitted=True, clause="admitted")


def advance_forwarding_state(manifest: Mapping[str, object]) -> dict:
    """Return a copy with forwarding state advanced by exactly one hop.

    Only called after a successful admission. Identity is unaffected:
    :func:`codec.identity_bytes` excludes both fields, so the object's
    ``object_id`` and every fragment digest are unchanged by forwarding.
    """
    hop_count = _int_field(manifest, FIELD_HOP_COUNT, 0)
    copy_budget = _int_field(manifest, "copy_budget", 8)
    remaining = _int_field(manifest, FIELD_REMAINING_COPY_BUDGET, copy_budget)
    if remaining < 1:
        raise ProtocolError(
            ErrorCode.COPY_BUDGET,
            "cannot advance forwarding state with no remaining copy budget",
            object_id=_object_id(manifest),
        )
    advanced = dict(manifest)
    advanced[FIELD_HOP_COUNT] = hop_count + 1
    advanced[FIELD_REMAINING_COPY_BUDGET] = remaining - 1
    return advanced


def identity_is_stable(before: Mapping[str, object], after: Mapping[str, object]) -> bool:
    """True when two manifests share identical canonical identity bytes."""
    return codec.identity_bytes(before) == codec.identity_bytes(after)
