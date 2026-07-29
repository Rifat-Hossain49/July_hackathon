"""ContentManifest builder (M0).

Produces a ``shongket.content.v1`` manifest that:

* binds the upstream ``object_id = sha256_hex(original_source_bytes)``;
* carries a separate ``manifest_id = sha256_hex(canonical_json(manifest))``
  for cache-keying;
* references the semantic capsule by its ``capsule_id``.

The manifest supports one or more representations (thumb / preview /
standard / original). Each representation has its own chunk plan and
hashes. AT-04 (``thumb[0]`` and ``preview[0]`` coexist) is exercised by
the scenario builder, which now produces all four representations.
"""

from __future__ import annotations

import json
import time

from . import hashutil


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_manifest(
    *,
    object_id: str,
    capsule_id: str,
    representations: list[dict],
    priority: str = "life_safety",
    expires_at_unix: int | None = None,
    hop_limit: int = 6,
    copy_budget: int = 8,
    created_at_unix: int | None = None,
) -> dict:
    """Build a canonical M0 manifest.

    Parameters
    ----------
    object_id:
        SHA-256 of the original source bytes (see ``media.object_id_from_source``).
    capsule_id:
        Capsule ID this manifest binds to.
    representations:
        List of representation descriptors. Each entry is a dict with
        keys ``id``, ``kind``, ``byte_len``, ``chunk_size``, ``hashes``
        (list of chunk SHA-256 strings in order), ``rep_sha256``.
        The M0 schema accepts ``id`` in
        ``{thumb, preview, standard, original}``.
    priority:
        One of ``"life_safety"``, ``"high"``, ``"routine"``.
    """
    manifest: dict = {
        "schema": "shongket.content.v1",
        "object_id": object_id,
        "capsule_ref": capsule_id,
        "representations": [dict(rep) for rep in representations],
        "priority": priority,
        "created_at_unix": int(created_at_unix if created_at_unix is not None else time.time()),
        "expires_at_unix": expires_at_unix,
        "hop_limit": hop_limit,
        "copy_budget": copy_budget,
        "signatures": [],
    }
    manifest["manifest_id"] = hashutil.sha256_hex(_canonical_json(manifest))
    return manifest


def canonical_manifest_bytes(manifest: dict) -> bytes:
    """Return the canonical byte encoding of ``manifest`` (no ``manifest_id`` field)."""
    m = {k: v for k, v in manifest.items() if k != "manifest_id"}
    return _canonical_json(m)
