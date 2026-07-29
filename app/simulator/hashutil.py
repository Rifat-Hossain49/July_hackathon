"""SHA-256 helpers.

Thin wrappers so tests can patch hashing without touching the rest of the
simulator. Implements no other cryptographic primitive.
"""

from __future__ import annotations

import hashlib


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of ``data``.

    Parameters
    ----------
    data:
        Byte string. Empty bytes are permitted and yield the well-known
        empty-string SHA-256 (``e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855``).

    Returns
    -------
    str
        64-character lowercase hexadecimal digest.
    """
    return hashlib.sha256(data).hexdigest()
