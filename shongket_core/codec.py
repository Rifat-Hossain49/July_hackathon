"""Canonical serialization (M1 — AT-22).

Produces byte-stable JSON: the same logical value always encodes to the
same bytes, in this process and any other.

Canonical rules
---------------
1. ``sort_keys=True`` — field order is a property of the value, never of
   insertion order.
2. ``separators=(",", ":")`` — no incidental whitespace.
3. ``ensure_ascii=True`` — see the compatibility note below.
4. UTF-8 output.
5. ``allow_nan=False`` — ``NaN`` / ``Infinity`` are not JSON and are
   refused rather than emitted as bare words no other parser accepts.
6. **Floats are rejected outright.** The protocol carries integer
   seconds, byte counts and indexes; nothing needs a float. Refusing the
   type is what makes "no float-formatting divergence" (AT-22) a
   structural guarantee instead of a hope.
7. **Non-string mapping keys are rejected.** ``json`` would silently
   coerce ``{1: "a"}`` into ``{"1": "a"}``, which is exactly the kind of
   quiet coercion D-M1-05 and §5 forbid.

Why ``ensure_ascii=True``
-------------------------
The M0 simulator computes ``object_id``, ``manifest_id`` and
``capsule_id`` with ``json.dumps(..., sort_keys=True,
separators=(",", ":"))``, whose ``ensure_ascii`` default is ``True``.
Content identity is derived from those bytes.

Choosing ``ensure_ascii=False`` here would read more naturally as
"UTF-8", but it would produce different bytes for any non-ASCII payload
— and Shongket is a Bangla-first product, so that is not a hypothetical
difference. It would change ``object_id`` for the same media between M0
and M1, and would break the AT-37 requirement that the recorded M0 CLI
hash still matches after the refactor.

Byte-compatibility with already-issued content identifiers wins.
Non-ASCII characters are therefore escaped as ``\\uXXXX``; the output is
ASCII, which is a strict subset of UTF-8, so rule 4 still holds.

No clock, random source or environment value is consulted.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import ErrorCode, ProtocolError


#: Mutable forwarding state, excluded from immutable identity bytes.
#: PROTOCOL_SPEC.md §3.2: these fields are transport state, not content
#: identity, so forwarding an object must never change its ``object_id``.
FORWARDING_STATE_FIELDS: tuple[str, ...] = ("hop_count", "remaining_copy_budget")


def _reject_float(text: str) -> Any:
    raise ProtocolError(
        ErrorCode.SCHEMA_INVALID,
        f"floating-point value {text!r} is not canonical; "
        "the protocol carries integers only",
    )


def _reject_constant(text: str) -> Any:
    raise ProtocolError(
        ErrorCode.SCHEMA_INVALID,
        f"non-finite constant {text!r} is not valid canonical JSON",
    )


def check_canonical(value: object, *, path: str = "$") -> None:
    """Raise unless ``value`` is representable in canonical form.

    Walks the whole tree so a violation is reported with its location
    rather than surfacing later as a mismatched hash.
    """
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, float):
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"float at {path} is not canonical; use integers",
        )
    if isinstance(value, int):
        # bool is a subclass of int and is handled above.
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProtocolError(
                    ErrorCode.SCHEMA_INVALID,
                    f"non-string mapping key {key!r} at {path}; "
                    "keys are never coerced",
                )
            check_canonical(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)) and not isinstance(value, (str, bytes)):
        if isinstance(value, tuple):
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"tuple at {path} is not canonical; use a list",
            )
        for index, item in enumerate(value):
            check_canonical(item, path=f"{path}[{index}]")
        return
    raise ProtocolError(
        ErrorCode.SCHEMA_INVALID,
        f"value of type {type(value).__name__} at {path} is not canonical",
    )


def canonical_text(value: object) -> str:
    """Return the canonical JSON text for ``value``."""
    check_canonical(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def canonical_bytes(value: object) -> bytes:
    """Return the canonical UTF-8 bytes for ``value``."""
    return canonical_text(value).encode("utf-8")


def decode(data: bytes | str) -> Any:
    """Parse canonical JSON strictly.

    Floats and non-finite constants in the *input* are refused, so a
    payload that could not have been produced canonically is never
    accepted and silently re-encoded into something different.

    Raises
    ------
    ProtocolError
        ``SCHEMA_INVALID`` for malformed JSON, bad UTF-8, or any
        non-canonical value.
    """
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID, f"payload is not valid UTF-8: {exc!s}"
            ) from exc
    elif isinstance(data, str):
        text = data
    else:
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"cannot decode {type(data).__name__}; expected bytes or str",
        )

    try:
        value = json.loads(
            text, parse_float=_reject_float, parse_constant=_reject_constant
        )
    except ProtocolError:
        raise
    except ValueError as exc:
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID, f"payload is not valid JSON: {exc!s}"
        ) from exc

    check_canonical(value)
    return value


def identity_bytes(
    payload: Mapping[str, Any],
    *,
    exclude: Sequence[str] = (),
) -> bytes:
    """Canonical bytes used for content identity.

    Mutable forwarding state (:data:`FORWARDING_STATE_FIELDS`) is always
    removed, plus any field named in ``exclude`` — typically the
    identifier being computed, which cannot include itself.

    Only top-level fields are removed; nested structures are untouched.
    """
    if not isinstance(payload, Mapping):
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"identity requires an object, got {type(payload).__name__}",
        )
    removed = set(FORWARDING_STATE_FIELDS) | set(exclude)
    reduced = {k: v for k, v in payload.items() if k not in removed}
    return canonical_bytes(reduced)


def sha256_hex(data: bytes) -> str:
    """SHA-256 of ``data`` as lowercase hex."""
    import hashlib

    return hashlib.sha256(data).hexdigest()
