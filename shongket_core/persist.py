"""Durable, crash-safe snapshot persistence (M1 — AT-26/27/28/30/31).

Implements the model frozen in ``SYSTEM_ARCHITECTURE.md`` §3.1 under
decision D-M1-06.

Envelope
--------
Canonical JSON, schema-versioned, with **two** independent integrity
levels:

* ``payload_checksum`` — SHA-256 over the canonical bytes of the
  fragment array alone;
* ``document_checksum`` — SHA-256 over the canonical bytes of the whole
  document with the checksum field itself removed.

Two levels because they fail differently. A truncation or a tampered
header is caught by the document checksum; a single decayed fragment
whose enclosing document was subsequently re-checksummed is caught only
by that fragment's own digest. Fragment-level integrity also localises
damage: one bad fragment is dropped, the rest survive (AT-28b).

Write sequence
--------------
1. acquire the advisory single-writer lock;
2. write the new document to a temporary file **in the destination
   directory** (so the later replace is same-filesystem and atomic);
3. flush and ``os.fsync`` the temporary file;
4. retain the current primary as the previous-good snapshot;
5. ``os.replace`` the temporary file onto the primary path;
6. ``fsync`` the parent directory where the platform supports it;
7. release the lock.

Step 6 is the durability barrier the M0 implementation omitted: without
it a POSIX rename can be lost after a crash even though the file
contents were synced.

Parent-directory durability across platforms
--------------------------------------------
Directory ``fsync`` is a POSIX facility. Windows does not permit opening
a directory as a file handle for synchronisation, so the call cannot be
made there. The operation is therefore **attempted and its outcome
recorded** — ``"synced"`` or ``"unsupported"`` — rather than silently
skipped. :func:`parent_sync_capability` reports what the running
platform can do, so tests assert the recorded outcome matches the
platform rather than skipping.

Reader model
------------
Readers do not take the lock: the model is single-writer, multi-reader
per store path. Multi-process *writing* is out of scope until M2 defines
it, and is refused deterministically with ``STORE_LOCKED``.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from . import codec
from .errors import ErrorCode, ProtocolError
from .evidence import EvidenceLog, EventCode
from .store import (
    Fragment,
    FragmentStore,
    fragment_from_record,
    record_from_fragment,
)
from .version import SchemaId, parse_schema_id


SNAPSHOT_FAMILY = "snapshot"
SNAPSHOT_SCHEMA = "shongket.snapshot.v1.0"

#: Fault-injection stage names, matching the AT-26 interruption points.
STAGE_AFTER_TEMP_WRITE = "after_temp_write"
STAGE_AFTER_TEMP_FSYNC = "after_temp_fsync"
STAGE_AFTER_REPLACE = "after_replace"
STAGE_BEFORE_PARENT_FSYNC = "before_parent_fsync"

_REQUIRED_KEYS = frozenset(
    {"schema", "peer_id", "created_at_unix", "fragments",
     "payload_checksum", "document_checksum"}
)


def parent_sync_capability() -> str:
    """Return ``"synced"`` or ``"unsupported"`` for this platform.

    A pure capability probe: it opens nothing and changes nothing.
    """
    return "unsupported" if os.name == "nt" else "synced"


def _fsync_parent(directory: Path) -> str:
    """Best-effort parent-directory durability barrier.

    Returns the recorded outcome. Never raises for an unsupported
    platform — the outcome is evidence, not an error — but a genuine
    I/O failure on a platform that *does* support it propagates.
    """
    if parent_sync_capability() == "unsupported":
        return "unsupported"
    fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return "synced"


@dataclass(frozen=True)
class LoadResult:
    """Outcome of opening a store path."""

    fragments: tuple[Fragment, ...]
    peer_id: str
    created_at_unix: int
    schema_id: SchemaId
    #: True when the primary was unusable and the previous snapshot was used.
    used_fallback: bool = False
    #: Quarantined file paths, in the order they were set aside.
    quarantined: tuple[str, ...] = field(default=())
    #: Fragment keys dropped because their own bytes failed verification.
    dropped_fragments: tuple[tuple[str, str, int], ...] = field(default=())
    #: Temporary artefacts discarded on open.
    discarded_temps: tuple[str, ...] = field(default=())


class StoreLock:
    """Advisory single-writer lock backed by an exclusive lock file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fd: int | None = None

    def acquire(self) -> None:
        try:
            self._fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise ProtocolError(
                ErrorCode.STORE_LOCKED,
                f"another writer holds the lock for {self.path.name}",
            ) from exc

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self) -> "StoreLock":
        self.acquire()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()


class SnapshotStore:
    """Durable snapshot file set rooted at ``path``.

    Companion paths are derived from ``path`` and never configurable, so
    a store directory's layout is predictable:

    ``<path>``            primary snapshot
    ``<path>.prev``       previous good snapshot
    ``<path>.lock``       advisory writer lock
    ``<path>.*.tmp``      in-flight temporary files
    ``<path>.quarantine-N`` set-aside corrupt snapshots
    """

    def __init__(self, path: Path | str, *, evidence: EvidenceLog | None = None) -> None:
        self.path = Path(path)
        self.evidence = evidence if evidence is not None else EvidenceLog()

    # -- companion paths ----------------------------------------------------

    @property
    def previous_path(self) -> Path:
        return self.path.with_name(self.path.name + ".prev")

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(self.path.name + ".lock")

    def _temp_prefix(self) -> str:
        return self.path.name + "."

    def _temps(self) -> list[Path]:
        return sorted(self.path.parent.glob(self._temp_prefix() + "*.tmp"))

    def _next_quarantine_path(self) -> Path:
        index = 0
        while True:
            candidate = self.path.with_name(f"{self.path.name}.quarantine-{index}")
            if not candidate.exists():
                return candidate
            index += 1

    # -- document construction ---------------------------------------------

    @staticmethod
    def build_document(
        fragments: Iterable[Fragment], *, peer_id: str, created_at_unix: int
    ) -> dict:
        """Build the canonical, checksummed snapshot document.

        Fragments are emitted in sorted key order so the document is a
        function of its contents, not of insertion order.
        """
        records = [record_from_fragment(f) for f in sorted(fragments, key=lambda f: f.key)]
        payload_checksum = codec.sha256_hex(codec.canonical_bytes(records))
        document = {
            "schema": SNAPSHOT_SCHEMA,
            "peer_id": peer_id,
            "created_at_unix": int(created_at_unix),
            "fragments": records,
            "payload_checksum": payload_checksum,
        }
        document["document_checksum"] = codec.sha256_hex(
            codec.identity_bytes(document, exclude=("document_checksum",))
        )
        return document

    # -- save ---------------------------------------------------------------

    def save(
        self,
        store: FragmentStore,
        *,
        peer_id: str,
        created_at_unix: int,
        fault_hook: Callable[[str], None] | None = None,
    ) -> str:
        """Durably write ``store`` to the primary path.

        ``fault_hook`` is test-only fault injection: it is called with
        each stage name from the AT-26 interruption points and may raise
        to simulate a crash. Production callers pass ``None``.

        Returns the document checksum of what was written.
        """
        document = self.build_document(
            store.fragments(), peer_id=peer_id, created_at_unix=created_at_unix
        )
        return self.save_document(document, fault_hook=fault_hook)

    def save_document(
        self, document: dict, *, fault_hook: Callable[[str], None] | None = None
    ) -> str:
        """Durably write an already-built document. Used by migration."""
        encoded = codec.canonical_bytes(document)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with StoreLock(self.lock_path):
            fd, tmp_name = tempfile.mkstemp(
                prefix=self._temp_prefix(), suffix=".tmp", dir=str(self.path.parent)
            )
            tmp_path = Path(tmp_name)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(encoded)
                    handle.flush()
                    if fault_hook:
                        fault_hook(STAGE_AFTER_TEMP_WRITE)
                    os.fsync(handle.fileno())
                if fault_hook:
                    fault_hook(STAGE_AFTER_TEMP_FSYNC)

                # Retain the current primary before it is overwritten.
                if self.path.exists():
                    self._retain_previous()

                os.replace(str(tmp_path), str(self.path))
                if fault_hook:
                    fault_hook(STAGE_AFTER_REPLACE)
            except BaseException:
                # The temp never became the primary; remove it so a later
                # open does not have to reason about it.
                try:
                    tmp_path.unlink()
                except FileNotFoundError:
                    pass
                raise

            if fault_hook:
                fault_hook(STAGE_BEFORE_PARENT_FSYNC)
            outcome = _fsync_parent(self.path.parent)

        self.evidence.record(EventCode.PARENT_DIR_SYNC, outcome=outcome)
        self.evidence.record(
            EventCode.SNAPSHOT_SAVED,
            document_checksum=document["document_checksum"],
            fragment_count=len(document["fragments"]),
            bytes=len(encoded),
        )
        return str(document["document_checksum"])

    def _retain_previous(self) -> None:
        """Copy the current primary to the previous-good path atomically."""
        data = self.path.read_bytes()
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.previous_path.name + ".", suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, str(self.previous_path))
        except BaseException:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    # -- load ---------------------------------------------------------------

    def load(self) -> LoadResult:
        """Open the store, recovering from partial or corrupt state.

        Never raises for a recoverable condition; every recovery step is
        recorded as evidence. Raises only when no usable snapshot exists
        at all.
        """
        discarded = self._discard_temps()
        quarantined: list[str] = []

        for candidate, is_fallback in ((self.path, False), (self.previous_path, True)):
            if not candidate.exists():
                continue
            try:
                document = self._read_verified(candidate)
            except ProtocolError as exc:
                target = self._quarantine(candidate, exc.code.value)
                quarantined.append(target)
                continue

            fragments, dropped = self._fragments_from(document)
            if is_fallback:
                self.evidence.record(
                    EventCode.SNAPSHOT_FALLBACK_USED, path=self.previous_path.name
                )
            self.evidence.record(
                EventCode.SNAPSHOT_LOADED,
                fragment_count=len(fragments),
                dropped=len(dropped),
                used_fallback=is_fallback,
            )
            return LoadResult(
                fragments=tuple(fragments),
                peer_id=str(document["peer_id"]),
                created_at_unix=int(document["created_at_unix"]),  # type: ignore[arg-type]
                schema_id=parse_schema_id(document["schema"]),
                used_fallback=is_fallback,
                quarantined=tuple(quarantined),
                dropped_fragments=tuple(dropped),
                discarded_temps=tuple(discarded),
            )

        raise ProtocolError(
            ErrorCode.SNAPSHOT_INVALID,
            f"no usable snapshot at {self.path.name}"
            + (f"; quarantined {len(quarantined)}" if quarantined else ""),
        )

    def exists(self) -> bool:
        return self.path.exists() or self.previous_path.exists()

    def read_document(self, path: Path | None = None) -> dict:
        """Read and fully verify a snapshot document without loading fragments."""
        return self._read_verified(path if path is not None else self.path)

    # -- internals ----------------------------------------------------------

    def _discard_temps(self) -> list[str]:
        """Remove in-flight temporary artefacts left by an interrupted write."""
        discarded: list[str] = []
        for temp in self._temps():
            try:
                temp.unlink()
            except FileNotFoundError:
                continue
            discarded.append(temp.name)
            self.evidence.record(EventCode.TEMP_ARTEFACT_DISCARDED, path=temp.name)
        return discarded

    def _read_verified(self, path: Path) -> dict:
        raw = path.read_bytes()
        document = codec.decode(raw)

        if not isinstance(document, dict):
            raise ProtocolError(
                ErrorCode.SNAPSHOT_INVALID, "snapshot root must be an object"
            )
        missing = _REQUIRED_KEYS - set(document)
        if missing:
            raise ProtocolError(
                ErrorCode.SNAPSHOT_INVALID,
                f"snapshot missing required keys {sorted(missing)!r}",
            )
        # Version is resolved before structural interpretation, matching
        # the wire rule in PROTOCOL_SPEC §9.1.
        schema_id = parse_schema_id(document["schema"])
        if schema_id.family != SNAPSHOT_FAMILY:
            raise ProtocolError(
                ErrorCode.SNAPSHOT_INVALID,
                f"not a snapshot document: family {schema_id.family!r}",
            )
        if not isinstance(document["fragments"], list):
            raise ProtocolError(
                ErrorCode.SNAPSHOT_INVALID, "fragments must be a list"
            )

        expected_document = codec.sha256_hex(
            codec.identity_bytes(document, exclude=("document_checksum",))
        )
        if expected_document != document["document_checksum"]:
            raise ProtocolError(
                ErrorCode.SNAPSHOT_CORRUPTED,
                "document checksum mismatch",
            )
        expected_payload = codec.sha256_hex(codec.canonical_bytes(document["fragments"]))
        if expected_payload != document["payload_checksum"]:
            raise ProtocolError(
                ErrorCode.SNAPSHOT_CORRUPTED,
                "payload checksum mismatch",
            )
        return document

    def _fragments_from(
        self, document: dict
    ) -> tuple[list[Fragment], list[tuple[str, str, int]]]:
        """Rebuild fragments, dropping only those failing their own digest."""
        fragments: list[Fragment] = []
        dropped: list[tuple[str, str, int]] = []
        for record in document["fragments"]:
            fragment = fragment_from_record(record)
            if not fragment.verify():
                dropped.append(fragment.key)
                self.evidence.record(
                    EventCode.FRAGMENT_DROPPED,
                    reason="integrity",
                    object_id=fragment.object_id,
                    representation_id=fragment.representation_id,
                    chunk_index=fragment.chunk_index,
                )
                continue
            fragments.append(fragment)
        return fragments, dropped

    def _quarantine(self, path: Path, reason: str) -> str:
        """Set a corrupt snapshot aside. Never deletes it (AT-28a)."""
        target = self._next_quarantine_path()
        os.replace(str(path), str(target))
        self.evidence.record(
            EventCode.SNAPSHOT_QUARANTINED,
            path=target.name,
            source=path.name,
            reason=reason,
        )
        return target.name


def restore_into(store: FragmentStore, fragments: Iterable[Fragment]) -> int:
    """Insert verified fragments into ``store``; return the number stored."""
    stored = 0
    for fragment in fragments:
        if store.put(fragment):
            stored += 1
    return stored
