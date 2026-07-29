"""Fixed-size fragmentation (M0).

``FixedSizeFragmenter`` slices a payload into a sequence of content-addressed
chunks. Chunk size is configurable; the terminal chunk may be shorter. Each
chunk is identified by ``(object_id, representation_id, chunk_index)`` and
verified by SHA-256. Coded chunking (Reed-Solomon / fountain / RaptorQ) is
out of scope for M0.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import hashutil


@dataclass(frozen=True)
class Chunk:
    """A single fixed-size fragment of a representation."""

    object_id: str
    representation_id: str
    chunk_index: int
    byte_range: tuple[int, int]  # inclusive [start, end]
    sha256: str
    payload: bytes


@dataclass(frozen=True)
class ChunkPlan:
    """The plan produced by ``FixedSizeFragmenter.fragment``."""

    representation_id: str
    representation_hash: str
    chunk_size: int
    chunks: list[Chunk]


class FixedSizeFragmenter:
    """Split a representation into deterministic fixed-size chunks."""

    def __init__(self, chunk_size: int) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._chunk_size = chunk_size

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    def fragment(self, *, object_id: str, representation_id: str, payload: bytes) -> ChunkPlan:
        """Return a ``ChunkPlan`` over ``payload`` for the given identity."""
        chunk_size = self._chunk_size
        chunks: list[Chunk] = []
        idx = 0
        cursor = 0
        n = len(payload)
        while cursor < n:
            end = min(cursor + chunk_size, n) - 1
            chunk_bytes = payload[cursor : end + 1]
            chunks.append(
                Chunk(
                    object_id=object_id,
                    representation_id=representation_id,
                    chunk_index=idx,
                    byte_range=(cursor, end),
                    sha256=hashutil.sha256_hex(chunk_bytes),
                    payload=chunk_bytes,
                )
            )
            idx += 1
            cursor = end + 1
        return ChunkPlan(
            representation_id=representation_id,
            representation_hash=hashutil.sha256_hex(payload),
            chunk_size=chunk_size,
            chunks=chunks,
        )

    def reconstruct(self, plan: ChunkPlan, chunks: list[Chunk]) -> bytes:
        """Reassemble bytes from ``chunks`` against the indexes in ``plan``.

        Gaps raise ``ValueError``; the caller (a recovery test) is expected
        to fill every index up to ``len(plan.chunks) - 1`` before calling
        this in M0. Coded reconstruction is not part of M0.
        """
        if not plan.chunks:
            return b""
        max_index = len(plan.chunks) - 1
        found: dict[int, bytes] = {}
        for c in chunks:
            if c.object_id != plan.chunks[0].object_id:
                raise ValueError("object_id mismatch in chunk")
            if c.representation_id != plan.representation_id:
                raise ValueError("representation_id mismatch in chunk")
            if c.chunk_index < 0 or c.chunk_index > max_index:
                raise ValueError(f"chunk_index {c.chunk_index} out of plan bounds")
            expected = plan.chunks[c.chunk_index]
            if c.sha256 != expected.sha256 or c.byte_range != expected.byte_range:
                raise ValueError(f"chunk at index {c.chunk_index} does not match plan")
            if c.sha256 != hashutil.sha256_hex(c.payload):
                raise ValueError(f"chunk at index {c.chunk_index} is corrupted")
            found[c.chunk_index] = c.payload
        assembled = bytearray()
        for i in range(len(plan.chunks)):
            if i not in found:
                raise ValueError(f"missing chunk index {i}")
            assembled.extend(found[i])
        return bytes(assembled)
