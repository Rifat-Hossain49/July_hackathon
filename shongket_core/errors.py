"""Canonical error taxonomy (M1).

Encodes the enum frozen in ``PROTOCOL_SPEC.md`` §3.8 under decision
D-M1-07: one canonical set of codes shared by ``ProtocolError``,
acknowledgements, events and recovery evidence, with every code
classified **terminal** or **retryable**.

* **terminal** — re-offering byte-identical input must fail identically.
* **retryable** — the same input may succeed once external state changes.

No code carries both classifications, and no code exists outside the
canonical enum.

Slice-1 scope
-------------
The full enum is declared here because it is approved specification
data, not new behaviour. Slice 1 *raises* only the codes reachable from
schema parsing, canonical serialization and version resolution
(``SCHEMA_INVALID``, ``VERSION_UNSUPPORTED``). The remaining codes are
declared so later slices raise them without redefining the taxonomy.

Relationship to the M0 simulator
--------------------------------
``app.simulator.validation.ProtocolError`` is a *separate* class and is
deliberately left untouched: M0 behaviour and its 125 tests must not
change in this slice. Reconciling the two is Slice 4/5 work. Both types
carry a ``code`` string drawn from the same canonical vocabulary, so the
eventual merge is a type change rather than a semantic one.
"""

from __future__ import annotations

from enum import Enum


class ErrorClass(str, Enum):
    """Whether retrying identical input could ever succeed."""

    TERMINAL = "terminal"
    RETRYABLE = "retryable"


class ErrorCode(str, Enum):
    """The canonical ``shongket.error.v1`` code set (PROTOCOL_SPEC §3.8)."""

    SCHEMA_INVALID = "SCHEMA_INVALID"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    VERSION_UNSUPPORTED = "VERSION_UNSUPPORTED"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    EXPIRED = "EXPIRED"
    HOP_LIMIT = "HOP_LIMIT"
    COPY_BUDGET = "COPY_BUDGET"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    HUMAN_CONFIRMATION_MISSING = "HUMAN_CONFIRMATION_MISSING"
    PEER_REFUSES_PRIVATE = "PEER_REFUSES_PRIVATE"
    UNKNOWN_OBJECT = "UNKNOWN_OBJECT"
    OUT_OF_BUDGET = "OUT_OF_BUDGET"
    SNAPSHOT_INVALID = "SNAPSHOT_INVALID"
    SNAPSHOT_CORRUPTED = "SNAPSHOT_CORRUPTED"
    INTERNAL = "INTERNAL"


# Exactly one classification per code. Mirrors the table in
# PROTOCOL_SPEC.md §3.8; the test suite asserts this map covers the enum
# completely, so the two cannot drift apart silently.
ERROR_CLASSES: dict[ErrorCode, ErrorClass] = {
    ErrorCode.SCHEMA_INVALID: ErrorClass.TERMINAL,
    ErrorCode.PAYLOAD_TOO_LARGE: ErrorClass.TERMINAL,
    ErrorCode.VERSION_UNSUPPORTED: ErrorClass.TERMINAL,
    ErrorCode.SIGNATURE_INVALID: ErrorClass.TERMINAL,
    ErrorCode.EXPIRED: ErrorClass.TERMINAL,
    ErrorCode.HOP_LIMIT: ErrorClass.TERMINAL,
    ErrorCode.COPY_BUDGET: ErrorClass.TERMINAL,
    ErrorCode.CONSENT_REQUIRED: ErrorClass.TERMINAL,
    ErrorCode.HUMAN_CONFIRMATION_MISSING: ErrorClass.TERMINAL,
    ErrorCode.PEER_REFUSES_PRIVATE: ErrorClass.TERMINAL,
    ErrorCode.UNKNOWN_OBJECT: ErrorClass.RETRYABLE,
    ErrorCode.OUT_OF_BUDGET: ErrorClass.RETRYABLE,
    ErrorCode.SNAPSHOT_INVALID: ErrorClass.RETRYABLE,
    ErrorCode.SNAPSHOT_CORRUPTED: ErrorClass.RETRYABLE,
    ErrorCode.INTERNAL: ErrorClass.TERMINAL,
}


def classify(code: ErrorCode) -> ErrorClass:
    """Return the canonical classification for ``code``."""
    return ERROR_CLASSES[code]


class ProtocolError(Exception):
    """A protocol violation carrying a canonical code.

    Parameters
    ----------
    code:
        A member of :class:`ErrorCode`. Passing a bare string is
        rejected, so an undocumented code cannot enter the system.
    detail:
        Short, deterministic description. Must not embed a wall-clock
        value, so the same failure always renders identically.
    object_id:
        Optional content identifier the failure relates to.
    """

    def __init__(
        self,
        code: ErrorCode,
        detail: str,
        *,
        object_id: str | None = None,
    ) -> None:
        if not isinstance(code, ErrorCode):
            raise TypeError(
                f"code must be an ErrorCode, got {type(code).__name__}; "
                "undocumented error codes are not permitted"
            )
        super().__init__(f"{code.value}: {detail}")
        self.code = code
        self.detail = detail
        self.object_id = object_id

    @property
    def error_class(self) -> ErrorClass:
        return classify(self.code)

    @property
    def retryable(self) -> bool:
        return self.error_class is ErrorClass.RETRYABLE

    def to_dict(self) -> dict:
        """Canonical ``shongket.error.v1`` representation."""
        return {
            "schema": "shongket.error.v1",
            "code": self.code.value,
            "object_id": self.object_id,
            "detail": self.detail,
        }
