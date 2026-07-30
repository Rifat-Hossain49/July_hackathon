"""Platform-neutral content-addressed fragment store (M1).

The fragment key is ``(object_id, representation_id, chunk_index)`` and
every payload is verified against its declared SHA-256 before it is
admitted. Storage pressure is **rejection-only**: a chunk that does not
fit the byte budget is refused with the retryable ``OUT_OF_BUDGET``
code before any mutation. No eviction is implemented — that remains a
later-milestone device concern (D-M1-04, SYSTEM_ARCHITECTURE §3.2).

Relationship to the M0 simulator
--------------------------------
``app.simulator.store`` is a separate, untouched implementation. This is
the M1 core equivalent; the two coexist until the adapter work in a
later slice. Behaviour is deliberately the same so that migrating a
caller changes types, not semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Mapping

from . import codec
from .errors import ErrorCode, ProtocolError
from .evidence import EvidenceLog, EventCode


FragmentKey = tuple[str, str, int]


@dataclass(frozen=True)
class Fragment:
    """One verified fragment of a representation."""

    object_id: str
    representation_id: str
    chunk_index: int
    byte_range: tuple[int, int]
    sha256: str
    payload: bytes

    @property
    def key(self) -> FragmentKey:
        return (self.object_id, self.representation_id, self.chunk_index)

    def verify(self) -> bool:
        """True when the payload actually hashes to the declared digest."""
        return codec.sha256_hex(self.payload) == self.sha256


@dataclass
class StoreStats:
    """Deterministic counters used as evidence."""

    stored: int = 0
    duplicate: int = 0
    rejected_integrity: int = 0
    rejected_budget: int = 0

    def as_dict(self) -> dict:
        return {
            "stored": self.stored,
            "duplicate": self.duplicate,
            "rejected_integrity": self.rejected_integrity,
            "rejected_budget": self.rejected_budget,
        }


class FragmentStore:
    """In-memory verified fragment store with an optional byte budget.

    ``capacity_bytes=None`` means unbounded. Byte accounting counts
    actual stored payload bytes and is maintained incrementally;
    :meth:`recompute_used_bytes` exists so tests can prove the counter
    never drifts from the bytes actually held.
    """

    def __init__(
        self,
        *,
        capacity_bytes: int | None = None,
        evidence: EvidenceLog | None = None,
    ) -> None:
        if capacity_bytes is not None and capacity_bytes < 0:
            raise ValueError("capacity_bytes must be non-negative or None")
        self._fragments: dict[FragmentKey, Fragment] = {}
        self._used_bytes = 0
        self.capacity_bytes = capacity_bytes
        self.stats = StoreStats()
        self._evidence = evidence

    # -- introspection ------------------------------------------------------

    def __len__(self) -> int:
        return len(self._fragments)

    def __contains__(self, key: object) -> bool:
        return key in self._fragments

    def has(self, object_id: str, representation_id: str, chunk_index: int) -> bool:
        return (object_id, representation_id, chunk_index) in self._fragments

    def get(
        self, object_id: str, representation_id: str, chunk_index: int
    ) -> Fragment | None:
        return self._fragments.get((object_id, representation_id, chunk_index))

    def keys(self) -> tuple[FragmentKey, ...]:
        """All fragment keys in deterministic sorted order."""
        return tuple(sorted(self._fragments))

    def fragments(self) -> Iterator[Fragment]:
        for key in self.keys():
            yield self._fragments[key]

    def chunk_indexes(self, object_id: str, representation_id: str) -> tuple[int, ...]:
        return tuple(
            sorted(
                idx
                for (obj, rep, idx) in self._fragments
                if obj == object_id and rep == representation_id
            )
        )

    def missing_indexes(
        self,
        object_id: str,
        representation_id: str,
        expected: Iterable[int],
    ) -> tuple[int, ...]:
        """Indexes from ``expected`` this store does not hold.

        The resume path uses this so a restarted transfer requests only
        what is genuinely absent (AT-31). Returned in ascending order so
        the request sequence is deterministic.
        """
        held = set(self.chunk_indexes(object_id, representation_id))
        return tuple(sorted(set(expected) - held))

    @property
    def used_bytes(self) -> int:
        return self._used_bytes

    @property
    def remaining_bytes(self) -> int | None:
        if self.capacity_bytes is None:
            return None
        return self.capacity_bytes - self._used_bytes

    def recompute_used_bytes(self) -> int:
        return sum(len(f.payload) for f in self._fragments.values())

    def quota(self) -> dict:
        return {
            "capacity_bytes": self.capacity_bytes,
            "used_bytes": self._used_bytes,
            "remaining_bytes": self.remaining_bytes,
            "fragment_count": len(self._fragments),
        }

    def inventory(self) -> list[dict]:
        """Deterministic per-fragment inventory, used as AT-30 evidence."""
        return [
            {
                "object_id": f.object_id,
                "representation_id": f.representation_id,
                "chunk_index": f.chunk_index,
                "sha256": f.sha256,
                "bytes": len(f.payload),
            }
            for f in self.fragments()
        ]

    # -- admission ----------------------------------------------------------

    def put(self, fragment: Fragment) -> bool:
        """Verify and store ``fragment``.

        Returns ``True`` when newly stored, ``False`` when it was an
        exact duplicate (a no-op consuming no capacity).

        Order of checks matters and is asserted by the tests: integrity
        first, then duplicate, then budget. A corrupted or duplicate
        chunk therefore never consumes capacity, and a budget refusal
        happens before any mutation.

        Raises
        ------
        ProtocolError
            ``SCHEMA_INVALID`` (terminal) when the payload does not match
            its declared digest, or when a different payload is offered
            under an existing key.
            ``OUT_OF_BUDGET`` (retryable) when the new bytes do not fit.
        """
        if not fragment.verify():
            self.stats.rejected_integrity += 1
            self._note(
                EventCode.FRAGMENT_REJECTED,
                reason="integrity",
                code=ErrorCode.SCHEMA_INVALID.value,
                chunk_index=fragment.chunk_index,
            )
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"fragment {fragment.chunk_index} payload does not match its "
                "declared SHA-256",
                object_id=fragment.object_id,
            )

        existing = self._fragments.get(fragment.key)
        if existing is not None:
            if existing.sha256 != fragment.sha256:
                self.stats.rejected_integrity += 1
                self._note(
                    EventCode.FRAGMENT_REJECTED,
                    reason="hash_collision",
                    code=ErrorCode.SCHEMA_INVALID.value,
                    chunk_index=fragment.chunk_index,
                )
                raise ProtocolError(
                    ErrorCode.SCHEMA_INVALID,
                    f"conflicting payload offered for existing fragment "
                    f"{fragment.chunk_index}",
                    object_id=fragment.object_id,
                )
            self.stats.duplicate += 1
            self._note(
                EventCode.FRAGMENT_DUPLICATE, chunk_index=fragment.chunk_index
            )
            return False

        size = len(fragment.payload)
        if self.capacity_bytes is not None and self._used_bytes + size > self.capacity_bytes:
            self.stats.rejected_budget += 1
            self._note(
                EventCode.FRAGMENT_REJECTED,
                reason="out_of_budget",
                code=ErrorCode.OUT_OF_BUDGET.value,
                chunk_index=fragment.chunk_index,
                payload_bytes=size,
                **self.quota(),
            )
            raise ProtocolError(
                ErrorCode.OUT_OF_BUDGET,
                f"storage budget exceeded: used={self._used_bytes} "
                f"payload={size} capacity={self.capacity_bytes}",
                object_id=fragment.object_id,
            )

        self._fragments[fragment.key] = fragment
        self._used_bytes += size
        self.stats.stored += 1
        self._note(EventCode.FRAGMENT_STORED, chunk_index=fragment.chunk_index)
        return True

    def drop(self, key: FragmentKey) -> bool:
        """Remove a fragment. Used only by integrity recovery, never by policy."""
        fragment = self._fragments.pop(key, None)
        if fragment is None:
            return False
        self._used_bytes -= len(fragment.payload)
        return True

    def _note(self, event: EventCode, **detail: object) -> None:
        # Parameter is named ``event`` rather than ``code`` so a detail
        # field called ``code`` (the canonical error code) can be passed
        # through without colliding with it.
        if self._evidence is not None:
            self._evidence.record(event, **detail)


def fragment_from_record(record: Mapping[str, object]) -> Fragment:
    """Rebuild a :class:`Fragment` from a persisted record.

    Performs no integrity check; the caller decides what to do with a
    fragment whose bytes no longer match.
    """
    import base64

    byte_range = record["byte_range"]
    if not isinstance(byte_range, list) or len(byte_range) != 2:
        raise ProtocolError(
            ErrorCode.SNAPSHOT_INVALID, "fragment byte_range must be a 2-element list"
        )
    try:
        payload = base64.b64decode(str(record["payload_b64"]).encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise ProtocolError(
            ErrorCode.SNAPSHOT_INVALID, f"fragment payload is not valid base64: {exc!s}"
        ) from exc
    return Fragment(
        object_id=str(record["object_id"]),
        representation_id=str(record["representation_id"]),
        chunk_index=int(record["chunk_index"]),  # type: ignore[arg-type]
        byte_range=(int(byte_range[0]), int(byte_range[1])),
        sha256=str(record["sha256"]),
        payload=payload,
    )


def record_from_fragment(fragment: Fragment) -> dict:
    """Canonical persisted record for a fragment."""
    import base64

    return {
        "object_id": fragment.object_id,
        "representation_id": fragment.representation_id,
        "chunk_index": fragment.chunk_index,
        "byte_range": [fragment.byte_range[0], fragment.byte_range[1]],
        "sha256": fragment.sha256,
        "payload_b64": base64.b64encode(fragment.payload).decode("ascii"),
    }
