"""Deterministic persistence migration and rollback (M1 — AT-25/29/36).

Implements the model frozen in ``SYSTEM_ARCHITECTURE.md`` §3.3 under
decision D-M1-06.

Registry, not inference
-----------------------
Every migration is an explicitly registered **edge** between two exact
persistence versions. Nothing is inferred from numeric ordering — the
same principle the schema registry applies to wire versions (D-M1-05).
A path from vN to the current version exists only if every intermediate
edge was registered; otherwise the upgrade is refused rather than
guessed at.

Path selection is deterministic: from any version there may be at most
one outgoing edge, so the chain is unique. Registering a second edge out
of the same version is rejected at construction as ambiguous, which
means a build can never migrate two different ways depending on dict
ordering.

Durability and rollback
-----------------------
The original document is retained until the migrated one is durably
written **and** re-verified by reading it back. If any step fails, the
original remains exactly as it was and the failure is reported as
retryable. A partially migrated document is never activated: migration
builds the new document in memory, and only a complete, checksummed
document reaches the durable write.

Downgrades are not defined. A snapshot newer than this build is refused
with ``VERSION_UNSUPPORTED`` rather than silently downgraded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

from . import codec
from .errors import ErrorCode, ProtocolError
from .evidence import EvidenceLog, EventCode
from .persist import SNAPSHOT_FAMILY, SnapshotStore
from .version import SchemaVersion, parse_schema_id


#: The persistence version this build writes.
CURRENT_VERSION = SchemaVersion(1, 0)

MigrationStep = Callable[[dict], dict]


@dataclass(frozen=True)
class Migration:
    """One explicitly registered migration edge."""

    source: SchemaVersion
    target: SchemaVersion
    apply: MigrationStep
    description: str = ""

    def __post_init__(self) -> None:
        if self.source == self.target:
            raise ValueError("a migration must change the version")


def _snapshot_id(version: SchemaVersion) -> str:
    return f"shongket.{SNAPSHOT_FAMILY}.v{version.major}.{version.minor}"


class MigrationRegistry:
    """Immutable, deterministic set of migration edges."""

    def __init__(
        self,
        migrations: Iterable[Migration] = (),
        *,
        current: SchemaVersion = CURRENT_VERSION,
    ) -> None:
        edges: dict[SchemaVersion, Migration] = {}
        for migration in migrations:
            if migration.source in edges:
                raise ValueError(
                    f"ambiguous migration path: two edges leave "
                    f"v{migration.source.major}.{migration.source.minor}"
                )
            edges[migration.source] = migration
        self._edges = edges
        self.current = current
        self._detect_cycles()

    def _detect_cycles(self) -> None:
        for start in self._edges:
            seen = {start}
            cursor = start
            while cursor in self._edges:
                cursor = self._edges[cursor].target
                if cursor in seen:
                    raise ValueError(
                        f"migration cycle detected at "
                        f"v{cursor.major}.{cursor.minor}"
                    )
                seen.add(cursor)

    def edges(self) -> tuple[Migration, ...]:
        return tuple(self._edges[key] for key in sorted(self._edges))

    def path(self, source: SchemaVersion) -> tuple[Migration, ...]:
        """Ordered edges from ``source`` to :attr:`current`.

        Raises
        ------
        ProtocolError
            ``VERSION_UNSUPPORTED`` when ``source`` is newer than the
            current version (downgrade, undefined), or when no complete
            registered chain reaches the current version.
        """
        if source == self.current:
            return ()
        if source > self.current:
            raise ProtocolError(
                ErrorCode.VERSION_UNSUPPORTED,
                f"snapshot version v{source.major}.{source.minor} is newer "
                f"than this build's v{self.current.major}.{self.current.minor}; "
                "downgrade is not defined",
            )

        chain: list[Migration] = []
        cursor = source
        while cursor != self.current:
            edge = self._edges.get(cursor)
            if edge is None:
                raise ProtocolError(
                    ErrorCode.VERSION_UNSUPPORTED,
                    f"no registered migration from v{cursor.major}.{cursor.minor} "
                    f"toward v{self.current.major}.{self.current.minor}; "
                    "migration paths are never inferred",
                )
            chain.append(edge)
            cursor = edge.target
        return tuple(chain)


@dataclass(frozen=True)
class MigrationResult:
    """Outcome of an upgrade attempt."""

    source_version: SchemaVersion
    target_version: SchemaVersion
    steps_applied: int
    migrated: bool
    document_checksum: str
    #: Canonical error code when the attempt failed and was rolled back.
    error_code: str | None = None

    def as_dict(self) -> dict:
        return {
            "source_version": f"v{self.source_version.major}.{self.source_version.minor}",
            "target_version": f"v{self.target_version.major}.{self.target_version.minor}",
            "steps_applied": self.steps_applied,
            "migrated": self.migrated,
            "document_checksum": self.document_checksum,
            "error_code": self.error_code,
        }


def rebuild_checksums(document: Mapping[str, object]) -> dict:
    """Return ``document`` with both checksums recomputed canonically."""
    rebuilt = {k: v for k, v in document.items() if k != "document_checksum"}
    rebuilt["payload_checksum"] = codec.sha256_hex(
        codec.canonical_bytes(rebuilt["fragments"])
    )
    rebuilt["document_checksum"] = codec.sha256_hex(
        codec.identity_bytes(rebuilt, exclude=("document_checksum",))
    )
    return rebuilt


def upgrade_store(
    snapshot: SnapshotStore,
    registry: MigrationRegistry,
    *,
    evidence: EvidenceLog | None = None,
    fault_hook: Callable[[str], None] | None = None,
) -> MigrationResult:
    """Migrate the snapshot at ``snapshot`` forward to the current version.

    Idempotent: a store already at the current version is left untouched
    and reports ``migrated=False`` with zero steps.

    On any failure the original document is left byte-identical and the
    error is reported as retryable, so the caller may fix the cause and
    try again.
    """
    log = evidence if evidence is not None else snapshot.evidence

    original_bytes = snapshot.path.read_bytes() if snapshot.path.exists() else None
    document = snapshot.read_document()
    source = parse_schema_id(document["schema"]).version

    chain = registry.path(source)
    if not chain:
        log.record(
            EventCode.MIGRATION_NOT_REQUIRED,
            version=f"v{source.major}.{source.minor}",
        )
        return MigrationResult(
            source_version=source,
            target_version=source,
            steps_applied=0,
            migrated=False,
            document_checksum=str(document["document_checksum"]),
        )

    fragments_before = {
        (f["object_id"], f["representation_id"], f["chunk_index"]): f["sha256"]
        for f in document["fragments"]
    }

    try:
        working = dict(document)
        for step, edge in enumerate(chain, start=1):
            working = edge.apply(dict(working))
            working["schema"] = _snapshot_id(edge.target)
            working = rebuild_checksums(working)
            if fault_hook:
                fault_hook(f"after_step_{step}")

        _assert_fragments_preserved(fragments_before, working)

        # Only a complete, checksummed document reaches the durable write.
        snapshot.save_document(working, fault_hook=fault_hook)

        # Read back and re-verify before declaring success.
        verified = snapshot.read_document()
        if verified["document_checksum"] != working["document_checksum"]:
            raise ProtocolError(
                ErrorCode.SNAPSHOT_CORRUPTED,
                "migrated document failed read-back verification",
            )
    except ProtocolError as exc:
        _rollback(snapshot, original_bytes)
        log.record(
            EventCode.MIGRATION_ROLLED_BACK,
            source_version=f"v{source.major}.{source.minor}",
            target_version=f"v{registry.current.major}.{registry.current.minor}",
            error_code=exc.code.value,
        )
        raise
    except BaseException as exc:
        _rollback(snapshot, original_bytes)
        log.record(
            EventCode.MIGRATION_ROLLED_BACK,
            source_version=f"v{source.major}.{source.minor}",
            target_version=f"v{registry.current.major}.{registry.current.minor}",
            error_code=ErrorCode.SNAPSHOT_INVALID.value,
        )
        raise ProtocolError(
            ErrorCode.SNAPSHOT_INVALID,
            f"migration failed and was rolled back: {type(exc).__name__}",
        ) from exc

    result = MigrationResult(
        source_version=source,
        target_version=registry.current,
        steps_applied=len(chain),
        migrated=True,
        document_checksum=str(working["document_checksum"]),
    )
    log.record(EventCode.MIGRATION_APPLIED, **result.as_dict())
    return result


def _assert_fragments_preserved(before: Mapping, document: Mapping) -> None:
    """Refuse a migration that silently discards verified fragments."""
    after = {
        (f["object_id"], f["representation_id"], f["chunk_index"]): f["sha256"]
        for f in document["fragments"]
    }
    lost = sorted(set(before) - set(after))
    if lost:
        raise ProtocolError(
            ErrorCode.SNAPSHOT_INVALID,
            f"migration would discard {len(lost)} verified fragment(s)",
        )
    changed = sorted(k for k in before if after.get(k) != before[k])
    if changed:
        raise ProtocolError(
            ErrorCode.SNAPSHOT_INVALID,
            f"migration would alter {len(changed)} verified fragment digest(s)",
        )


def _rollback(snapshot: SnapshotStore, original_bytes: bytes | None) -> None:
    """Restore the pre-migration bytes exactly."""
    if original_bytes is None:
        return
    if snapshot.path.exists() and snapshot.path.read_bytes() == original_bytes:
        return
    snapshot.path.write_bytes(original_bytes)


# --- legacy privacy-field migration (D-M1-01 / D-M1-02) ----------------------


def migrate_privacy_fields(manifest: Mapping[str, object]) -> dict:
    """Map the legacy boolean ``private`` marker onto ``visibility``.

    ``private: true`` becomes ``"private"``; ``false`` or absent becomes
    ``"public"``. A manifest that already carries ``visibility`` is left
    alone. A non-boolean ``private`` is refused rather than coerced —
    guessing what an ambiguous privacy marker meant is exactly the kind
    of inference that could leak private content.
    """
    result = dict(manifest)
    if "visibility" in result:
        result.pop("private", None)
        return result

    marker = result.pop("private", None)
    if marker is None:
        result["visibility"] = "public"
    elif marker is True:
        result["visibility"] = "private"
    elif marker is False:
        result["visibility"] = "public"
    else:
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"legacy 'private' marker must be boolean, got "
            f"{type(marker).__name__}",
            object_id=result.get("object_id"),  # type: ignore[arg-type]
        )
    return result
