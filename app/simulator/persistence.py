"""Snapshot persistence (M0 slice 2 — AT-07).

This module is the deterministic, standard-library-only persistence
boundary for a ``SimulatedPeer``'s verified progress. It is used by the
restart-recovery driver (``transfer.run_with_persistence``) and by the
AT-07 acceptance test.

The on-disk format is a single JSON document with the following top-level
keys (sorted, ``separators=(",", ":")``):

* ``schema`` — ``"shongket.snapshot.v1"``.
* ``peer_id`` — the saved peer's identifier.
* ``created_at_unix`` — caller-supplied deterministic timestamp.
* ``fragments`` — list of per-fragment records. Each record carries the
  fragment key ``(object_id, representation_id, chunk_index)``, the
  declared ``sha256`` and the ``payload`` bytes encoded as a
  ``base64`` string.

The atomic-write discipline (``tempfile`` + ``os.replace``) keeps the
file consistent under crash. The boundary rejects three classes of
failure:

* malformed JSON — raises ``ProtocolError("SNAPSHOT_INVALID", ...)``;
* well-formed JSON that does not match the snapshot schema — same code;
* stored bytes whose SHA-256 does not match the declared digest — code
  ``"SNAPSHOT_CORRUPTED"``.

No wall-clock is consulted: ``created_at_unix`` is supplied by the
caller and stored verbatim. Random sources are not touched.
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path

from . import hashutil, validation
from .chunks import Chunk
from .store import ContentAddressedStore


_SNAPSHOT_SCHEMA = "shongket.snapshot.v1"
_SNAPSHOT_REQUIRED = {"schema", "peer_id", "created_at_unix", "fragments"}


def store_snapshot(
    store: ContentAddressedStore,
    *,
    peer_id: str,
    path: Path,
    created_at_unix: int,
) -> None:
    """Atomically write ``store`` to ``path`` as a snapshot document.

    Parameters
    ----------
    store:
        The store whose verified progress should be persisted. Only
        already-verified chunks (``store._fragments``) are written.
    peer_id:
        Identifier written into the snapshot header.
    path:
        Destination path. Any parent directories are created.
    created_at_unix:
        Caller-supplied deterministic timestamp. No wall-clock.
    """
    fragments: list[dict] = []
    for key, chunk in sorted(store.snapshot_fragments().items()):
        object_id, representation_id, chunk_index = key
        fragments.append(
            {
                "object_id": object_id,
                "representation_id": representation_id,
                "chunk_index": chunk_index,
                "byte_range": [chunk.byte_range[0], chunk.byte_range[1]],
                "sha256": chunk.sha256,
                "payload_b64": base64.b64encode(chunk.payload).decode("ascii"),
            }
        )
    document = {
        "schema": _SNAPSHOT_SCHEMA,
        "peer_id": peer_id,
        "created_at_unix": int(created_at_unix),
        "fragments": fragments,
    }
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_snapshot(path: Path) -> tuple[str, int, list[Chunk]]:
    """Read a snapshot document and return ``(peer_id, created_at_unix, chunks)``.

    Parameters
    ----------
    path:
        Path to the snapshot file. The file must exist and contain a
        well-formed snapshot document.

    Raises
    ------
    validation.ProtocolError
        With ``code == "SNAPSHOT_INVALID"`` when the file cannot be
        parsed as JSON or does not match the snapshot schema; with
        ``code == "SNAPSHOT_CORRUPTED"`` when a fragment's payload no
        longer matches its declared SHA-256.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise validation.ProtocolError(
            "SNAPSHOT_INVALID",
            f"cannot read snapshot: {exc!s}",
        ) from exc

    try:
        document = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise validation.ProtocolError(
            "SNAPSHOT_INVALID",
            f"snapshot is not valid JSON: {exc!s}",
        ) from exc

    if not isinstance(document, dict):
        raise validation.ProtocolError(
            "SNAPSHOT_INVALID",
            "snapshot root must be a JSON object",
        )
    if document.get("schema") != _SNAPSHOT_SCHEMA:
        raise validation.ProtocolError(
            "SNAPSHOT_INVALID",
            f"snapshot schema must be {_SNAPSHOT_SCHEMA!r}, "
            f"got {document.get('schema')!r}",
        )
    missing = _SNAPSHOT_REQUIRED - set(document.keys())
    if missing:
        raise validation.ProtocolError(
            "SNAPSHOT_INVALID",
            f"snapshot missing required keys: {sorted(missing)!r}",
        )

    peer_id = document["peer_id"]
    created_at_unix = document["created_at_unix"]
    if not isinstance(peer_id, str):
        raise validation.ProtocolError(
            "SNAPSHOT_INVALID", "peer_id must be a string"
        )
    if not isinstance(created_at_unix, int):
        raise validation.ProtocolError(
            "SNAPSHOT_INVALID", "created_at_unix must be an int"
        )

    raw_fragments = document["fragments"]
    if not isinstance(raw_fragments, list):
        raise validation.ProtocolError(
            "SNAPSHOT_INVALID", "fragments must be a list"
        )

    chunks: list[Chunk] = []
    for i, entry in enumerate(raw_fragments):
        if not isinstance(entry, dict):
            raise validation.ProtocolError(
                "SNAPSHOT_INVALID",
                f"fragment {i} is not an object",
            )
        try:
            object_id = entry["object_id"]
            representation_id = entry["representation_id"]
            chunk_index = entry["chunk_index"]
            byte_range = entry["byte_range"]
            sha = entry["sha256"]
            payload_b64 = entry["payload_b64"]
        except KeyError as exc:
            raise validation.ProtocolError(
                "SNAPSHOT_INVALID",
                f"fragment {i} missing field {exc.args[0]!r}",
            ) from exc
        if not (
            isinstance(object_id, str)
            and isinstance(representation_id, str)
            and isinstance(chunk_index, int)
            and isinstance(byte_range, list)
            and len(byte_range) == 2
            and isinstance(sha, str)
            and isinstance(payload_b64, str)
        ):
            raise validation.ProtocolError(
                "SNAPSHOT_INVALID",
                f"fragment {i} has wrong field types",
            )
        try:
            payload = base64.b64decode(payload_b64.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as exc:
            raise validation.ProtocolError(
                "SNAPSHOT_INVALID",
                f"fragment {i} payload_b64 is not valid base64: {exc!s}",
            ) from exc
        if hashutil.sha256_hex(payload) != sha:
            raise validation.ProtocolError(
                "SNAPSHOT_CORRUPTED",
                f"fragment {i} payload SHA-256 mismatch",
            )
        chunks.append(
            Chunk(
                object_id=object_id,
                representation_id=representation_id,
                chunk_index=chunk_index,
                byte_range=(int(byte_range[0]), int(byte_range[1])),
                sha256=sha,
                payload=payload,
            )
        )
    return peer_id, created_at_unix, chunks


def restore_store(
    store: ContentAddressedStore, chunks: list[Chunk]
) -> int:
    """Place ``chunks`` back into ``store`` after verifying each one.

    Duplicates (identical key, identical SHA) are silently deduped to
    match the store's normal behavior. Returns the number of chunks
    newly persisted.
    """
    stored = 0
    for c in chunks:
        if store.restore_fragment(c):
            stored += 1
    return stored