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

    def as_dict(self) -> dict:
        return {
            "stored": self.stored,
            "duplicate_no_op": self.duplicate_no_op,
            "rejected_corruption": self.rejected_corruption,
            "rejected_schema": self.rejected_schema,
        }


@dataclass
class ContentAddressedStore:
    """In-memory fragment store keyed by ``(object_id, representation_id, chunk_index)``."""

    _fragments: dict[tuple[str, str, int], Chunk] = field(default_factory=dict)
    stats: StoreStats = field(default_factory=StoreStats)

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

    # -- ingest -------------------------------------------------------------

    def put_chunk(self, chunk: Chunk) -> None:
        """Validate, verify SHA-256, dedup, store.

        Raises
        ------
        validation.ProtocolError
            On schema validation failure (AT-20) or corrupted payload
            (AT-10). Nothing is persisted in either case.
        """
        descriptor = _fragment_descriptor_from(chunk)
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
        self._fragments[key] = chunk
        self.stats.stored += 1


def _fragment_descriptor_from(chunk: Chunk) -> dict:
    """Build a ``shongket.fragment.v1`` descriptor for schema validation."""
    return {
        "schema": "shongket.fragment.v1",
        "object_id": chunk.object_id,
        "representation_id": chunk.representation_id,
        "chunk_index": chunk.chunk_index,
        "chunk_size": len(chunk.payload),
        "byte_range": [chunk.byte_range[0], chunk.byte_range[1]],
        "hash": chunk.sha256,
        "signature": None,  # M0: unsigned
    }
