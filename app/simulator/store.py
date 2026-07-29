"""Per-peer content-addressed store.

Stored-fragment key is the triple ``(object_id, representation_id,
chunk_index)`` so thumbnails, previews, standards and originals cannot
collide at the same index. Ingest validates the descriptor with
``validation.validate_payload`` before any state mutation, satisfying the
AT-20 boundary inside the store. SHA-256 verification satisfies AT-09
(duplicate dedup) and AT-10 (corruption rejection).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import hashutil, validation
from .chunks import Chunk


@dataclass
class StoreStats:
    """Observability counters consumed by the event logger."""

    stored: int = 0
    duplicate_no_op: int = 0
    rejected_corruption: int = 0
    rejected_schema: int = 0
    rejected_budget: int = 0

    def as_dict(self) -> dict:
        return {
            "stored": self.stored,
            "duplicate_no_op": self.duplicate_no_op,
            "rejected_corruption": self.rejected_corruption,
            "rejected_schema": self.rejected_schema,
            "rejected_budget": self.rejected_budget,
        }


@dataclass
class ContentAddressedStore:
    """In-memory fragment store keyed by ``(object_id, representation_id, chunk_index)``.

    ``capacity_bytes`` is the AT-12 deterministic storage budget measured
    in actual stored payload bytes. ``None`` (the default) means
    unbounded, which preserves the behaviour every earlier slice relies
    on. When a budget is set, a chunk whose payload does not fit in the
    remaining capacity is refused *before* any mutation, so existing
    fragments survive the refusal untouched.
    """

    _fragments: dict[tuple[str, str, int], Chunk] = field(default_factory=dict)
    stats: StoreStats = field(default_factory=StoreStats)
    capacity_bytes: int | None = None
    _used_bytes: int = field(default=0, init=False)

    def has(self, object_id: str, representation_id: str, chunk_index: int) -> bool:
        return (object_id, representation_id, chunk_index) in self._fragments

    def get(self, object_id: str, representation_id: str, chunk_index: int) -> Chunk | None:
        return self._fragments.get((object_id, representation_id, chunk_index))

    def known_representations(self, object_id: str) -> set[str]:
        return {rep for (_o, rep, _idx) in self._fragments.keys() if _o == object_id}

    def known_chunks(self, object_id: str, representation_id: str) -> set[int]:
        return {
            idx
            for (_o, _r, idx) in self._fragments.keys()
            if _o == object_id and _r == representation_id
        }

    # -- storage budget (AT-12) ---------------------------------------------

    @property
    def used_bytes(self) -> int:
        """Actual stored payload bytes, maintained incrementally."""
        return self._used_bytes

    @property
    def remaining_bytes(self) -> int | None:
        """Remaining capacity, or ``None`` when the store is unbounded."""
        if self.capacity_bytes is None:
            return None
        return self.capacity_bytes - self._used_bytes

    def recompute_used_bytes(self) -> int:
        """Sum payload lengths from scratch.

        Exists so tests can prove the incremental ``used_bytes`` counter
        never drifts from the bytes actually held.
        """
        return sum(len(c.payload) for c in self._fragments.values())

    def quota(self) -> dict:
        """Deterministic quota values recorded as AT-12 evidence."""
        return {
            "capacity_bytes": self.capacity_bytes,
            "used_bytes": self._used_bytes,
            "remaining_bytes": self.remaining_bytes,
            "fragment_count": len(self._fragments),
        }

    def _would_exceed(self, payload_len: int) -> bool:
        if self.capacity_bytes is None:
            return False
        return self._used_bytes + payload_len > self.capacity_bytes

    def _budget_error(self, chunk: Chunk) -> validation.ProtocolError:
        return validation.ProtocolError(
            "OUT_OF_BUDGET",
            f"storage budget exceeded: used={self._used_bytes} "
            f"payload={len(chunk.payload)} capacity={self.capacity_bytes}",
            object_id=chunk.object_id,
        )

    # -- ingest -------------------------------------------------------------

    def _descriptor(self, chunk: Chunk) -> dict:
        """Build the JSON payload that crosses the validation boundary."""
        return {
            "schema": "shongket.fragment.v1",
            "object_id": chunk.object_id,
            "representation_id": chunk.representation_id,
            "chunk_index": chunk.chunk_index,
            "chunk_size": len(chunk.payload),
            "byte_range": [chunk.byte_range[0], chunk.byte_range[1]],
            "hash": chunk.sha256,
        }

    def put_chunk(self, chunk: Chunk) -> None:
        """Validate, verify SHA-256, dedup, store.

        Raises
        ------
        validation.ProtocolError
            On schema validation failure (AT-20) or corrupted payload
            (AT-10). Nothing is persisted in either case.
        """
        descriptor = self._descriptor(chunk)
        # Schema-validation boundary first (AT-20).
        try:
            validation.validate_payload("shongket.fragment.v1", descriptor)
        except validation.ProtocolError:
            self.stats.rejected_schema += 1
            raise

        # Corruption check (AT-10): hash must equal sha256(payload).
        if chunk.sha256 != hashutil.sha256_hex(chunk.payload):
            self.stats.rejected_corruption += 1
            raise validation.ProtocolError(
                "SCHEMA_INVALID",
                f"hash mismatch on chunk index {chunk.chunk_index}",
                object_id=chunk.object_id,
            )

        key = (chunk.object_id, chunk.representation_id, chunk.chunk_index)
        existing = self._fragments.get(key)
        if existing is not None:
            # AT-09 dedup: identical (object_id, representation_id, chunk_index, sha256)
            # is a no-op. Mismatched hash at the same key is rejected.
            if existing.sha256 != chunk.sha256:
                self.stats.rejected_corruption += 1
                raise validation.ProtocolError(
                    "SCHEMA_INVALID",
                    f"hash collision at {key}",
                    object_id=chunk.object_id,
                )
            self.stats.duplicate_no_op += 1
            return

        # AT-12 storage budget. Reached only by a chunk that is
        # schema-valid, hash-verified and genuinely new, so malformed,
        # corrupted and duplicate chunks never consume capacity. Checked
        # before the assignment below, so a refusal cannot mutate the
        # fragment map or the byte counter.
        if self._would_exceed(len(chunk.payload)):
            self.stats.rejected_budget += 1
            raise self._budget_error(chunk)

        self._fragments[key] = chunk
        self._used_bytes += len(chunk.payload)
        self.stats.stored += 1

    # -- snapshot / restore (slice 2 / AT-07) -------------------------------

    def snapshot_fragments(self) -> dict[tuple[str, str, int], Chunk]:
        """Return a defensive copy of the verified fragment map.

        Used by :mod:`app.simulator.persistence` to serialize progress
        without leaking internal mutability.
        """
        return dict(self._fragments)

    def restore_fragment(self, chunk: Chunk) -> bool:
        """Insert a single fragment, bypassing validation but verifying SHA-256.

        Returns ``True`` when a new fragment was stored, ``False`` when
        the key was already present (dedup). Raises
        :class:`validation.ProtocolError` with
        ``code == "SNAPSHOT_CORRUPTED"`` when the supplied chunk's
        declared SHA-256 does not match its payload, or
        ``code == "OUT_OF_BUDGET"`` when the restored bytes would not fit
        the configured capacity. Restored bytes are accounted exactly as
        ingested bytes are, so budget accounting survives a restart.
        """
        if chunk.sha256 != hashutil.sha256_hex(chunk.payload):
            raise validation.ProtocolError(
                "SNAPSHOT_CORRUPTED",
                f"chunk at index {chunk.chunk_index} is corrupted on restore",
                object_id=chunk.object_id,
            )
        key = (chunk.object_id, chunk.representation_id, chunk.chunk_index)
        if key in self._fragments:
            return False
        if self._would_exceed(len(chunk.payload)):
            self.stats.rejected_budget += 1
            raise self._budget_error(chunk)
        self._fragments[key] = chunk
        self._used_bytes += len(chunk.payload)
        self.stats.stored += 1
        return True
