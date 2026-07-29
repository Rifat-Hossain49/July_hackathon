"""Synthetic source media.

M0 only produces deterministic synthetic bytes derived from a local seeded
``random.Random(seed)``. Real capture (camera, microphone, document import)
is not part of M0. No use of the ``secrets`` module here — it is not
designed to provide reproducible seeded output.
"""

from __future__ import annotations

import random

from . import hashutil


def synthetic_source_bytes(seed: int, size_bytes: int) -> bytes:
    """Return ``size_bytes`` of deterministic synthetic media bytes.

    Parameters
    ----------
    seed:
        Integer seed. Two calls with the same ``seed`` and ``size_bytes``
        return byte-identical outputs.
    size_bytes:
        Number of bytes to generate. Values <= 0 yield ``b""``.

    Returns
    -------
    bytes
        Synthetic payload.

    Notes
    -----
    A fresh ``random.Random(seed)`` instance is created per call so that
    callers cannot accidentally share global RNG state.
    """
    if size_bytes <= 0:
        return b""
    rng = random.Random(seed)
    return rng.randbytes(size_bytes)


def object_id_from_source(source_bytes: bytes) -> str:
    """Return the Shongket content object ID for a source payload.

    Per the M0 plan, ``object_id = sha256_hex(original_source_bytes)``.
    Manifests bind this value as the foreign key to ``ContentObject``;
    a separate ``manifest_id`` is computed from the canonical manifest
    JSON (see ``manifest.py``).
    """
    return hashutil.sha256_hex(source_bytes)
