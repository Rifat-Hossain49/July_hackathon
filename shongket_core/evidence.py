"""Deterministic evidence log (M1).

Every acceptance test in the M1 catalogue requires *evidence*: a record
of what the core decided and why. This module is that record.

Determinism rules:

* records are ordered by a monotonic sequence number owned by the log,
  never by a clock;
* no wall-clock value, random identifier, memory address or filesystem
  path outside the caller's control enters a record;
* details are canonical values only, so a log serializes byte-identically
  across processes and platforms.

The log is an ordinary object with no global state; each caller
constructs its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from . import codec


class EventCode(str, Enum):
    """Deterministic evidence codes emitted by the M1 core."""

    # persistence (Slice 2)
    SNAPSHOT_SAVED = "snapshot_saved"
    SNAPSHOT_LOADED = "snapshot_loaded"
    SNAPSHOT_QUARANTINED = "snapshot_quarantined"
    SNAPSHOT_FALLBACK_USED = "snapshot_fallback_used"
    TEMP_ARTEFACT_DISCARDED = "temp_artefact_discarded"
    FRAGMENT_DROPPED = "fragment_dropped"
    PARENT_DIR_SYNC = "parent_dir_sync"
    # store (Slice 2)
    FRAGMENT_STORED = "fragment_stored"
    FRAGMENT_DUPLICATE = "fragment_duplicate"
    FRAGMENT_REJECTED = "fragment_rejected"
    # migration (Slice 3)
    MIGRATION_APPLIED = "migration_applied"
    MIGRATION_ROLLED_BACK = "migration_rolled_back"
    MIGRATION_NOT_REQUIRED = "migration_not_required"
    # policy (Slice 4)
    FORWARD_ADMITTED = "forward_admitted"
    FORWARD_REFUSED = "forward_refused"
    PRIVACY_MIGRATED = "privacy_migrated"


@dataclass(frozen=True)
class EvidenceRecord:
    """One ordered evidence entry."""

    seq: int
    code: EventCode
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"seq": self.seq, "code": self.code.value, "detail": dict(self.detail)}


class EvidenceLog:
    """Ordered, deterministic evidence recorder."""

    def __init__(self) -> None:
        self._records: list[EvidenceRecord] = []

    def record(self, code: EventCode, **detail: Any) -> EvidenceRecord:
        """Append a record. ``detail`` must be canonically serializable."""
        codec.check_canonical(detail)
        entry = EvidenceRecord(seq=len(self._records), code=code, detail=dict(detail))
        self._records.append(entry)
        return entry

    @property
    def records(self) -> tuple[EvidenceRecord, ...]:
        return tuple(self._records)

    def of(self, code: EventCode) -> tuple[EvidenceRecord, ...]:
        return tuple(r for r in self._records if r.code is code)

    def codes(self) -> tuple[str, ...]:
        return tuple(r.code.value for r in self._records)

    def as_list(self) -> list[dict]:
        return [r.as_dict() for r in self._records]

    def to_json(self) -> str:
        """Canonical serialization of the whole log."""
        return codec.canonical_text(self.as_list())

    def digest(self) -> str:
        """SHA-256 over the canonical log bytes."""
        return codec.sha256_hex(self.to_json().encode("utf-8"))

    def __len__(self) -> int:
        return len(self._records)
