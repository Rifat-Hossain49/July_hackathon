"""Protocol/schema validation boundary (M0).

This is the single boundary every payload crosses before it is persisted or
scheduled. It exists to satisfy AT-20: malformed payloads (missing required
fields, bad enum values, unsupported schema versions, wrong field types) are
rejected with ``ProtocolError(code="SCHEMA_INVALID")`` and nothing is stored
or scheduled.

The boundary is intentionally a pure function over plain dicts. Tests exhaust
every rejection path; production transport code (M1+) would call this from
the ingestion adapter.
"""

from __future__ import annotations

from dataclasses import dataclass


class ProtocolError(Exception):
    """Raised when a payload violates the declared protocol schema.

    AT-20 asserts ``code == "SCHEMA_INVALID"`` for the schema-validation
    boundary. Other code values are reserved for future boundaries
    (oversized payload, signature invalid, expired, etc.) that are out of
    scope for this M0 slice.
    """

    def __init__(self, code: str, detail: str, *, object_id: str | None = None) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.object_id = object_id

    def to_dict(self) -> dict:
        return {
            "schema": "shongket.error.v1",
            "code": self.code,
            "object_id": self.object_id,
            "detail": self.detail,
        }


# --- schema and enum catalogues (M0 only) -----------------------------------

_SUPPORTED_SCHEMAS: dict[str, dict] = {
    "shongket.capsule.v1": {
        "required": ["schema", "capsule_id", "object_ref", "human_confirmed"],
        "enums": {
            "confirmation_method": {"human_confirm", "manual_form_only", "ai_only_disabled"},
        },
        "size_limit_bytes": 4 * 1024,
    },
    "shongket.content.v1": {
        "required": [
            "schema",
            "object_id",
            "capsule_ref",
            "representations",
            "priority",
            "created_at_unix",
            "hop_limit",
            "copy_budget",
        ],
        "enums": {
            "priority": {"life_safety", "high", "routine"},
        },
        "size_limit_bytes": 32 * 1024,
    },
    "shongket.fragment.v1": {
        "required": [
            "schema",
            "object_id",
            "representation_id",
            "chunk_index",
            "chunk_size",
            "byte_range",
            "hash",
        ],
        "enums": {
            "representation_id": {"thumb", "preview", "standard", "original"},
        },
        "size_limit_bytes": 512,
    },
}


# --- entry points ------------------------------------------------------------


def validate_payload(kind: str, payload: dict) -> None:
    """Validate ``payload`` against the schema identified by ``kind``.

    Parameters
    ----------
    kind:
        One of the schema names in ``_SUPPORTED_SCHEMAS`` (e.g.
        ``"shongket.capsule.v1"``).
    payload:
        A plain dict representation of the payload. ``payload["schema"]``
        must equal ``kind``; mismatches are rejected.

    Raises
    ------
    ProtocolError
        With ``code == "SCHEMA_INVALID"`` when any rule below fails:
        * unsupported ``kind``;
        * missing required field;
        * unspecified schema string;
        * wrong field type;
        * unsupported enum value;
        * payload exceeds the schema's size limit (estimated from a
          canonical JSON encoding).
    """
    if kind not in _SUPPORTED_SCHEMAS:
        raise ProtocolError(
            "SCHEMA_INVALID",
            f"unsupported schema kind: {kind!r}",
            object_id=(payload.get("object_id") if isinstance(payload, dict) else None),
        )
    if not isinstance(payload, dict):
        raise ProtocolError("SCHEMA_INVALID", "payload is not an object")

    schema = _SUPPORTED_SCHEMAS[kind]
    declared_schema = payload.get("schema")
    if declared_schema != kind:
        raise ProtocolError(
            "SCHEMA_INVALID",
            f"schema field {declared_schema!r} does not match kind {kind!r}",
            object_id=payload.get("object_id"),
        )

    # Required-field check.
    for field in schema["required"]:
        if field not in payload:
            raise ProtocolError(
                "SCHEMA_INVALID",
                f"missing required field '{field}' for {kind}",
                object_id=payload.get("object_id"),
            )

    # Enum-value check.
    for field, allowed in schema["enums"].items():
        if field in payload and payload[field] not in allowed:
            raise ProtocolError(
                "SCHEMA_INVALID",
                f"field '{field}' has unsupported value {payload[field]!r}",
                object_id=payload.get("object_id"),
            )

    # Type check: int / list / dict per schema.
    _check_types(kind, payload)

    # Size-limit check via canonical JSON.
    import json

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > schema["size_limit_bytes"]:
        raise ProtocolError(
            "SCHEMA_INVALID",
            f"payload exceeds {schema['size_limit_bytes']} bytes for {kind}",
            object_id=payload.get("object_id"),
        )


def _check_types(kind: str, payload: dict) -> None:
    """Reject mismatched field types for known schemas."""
    if kind == "shongket.fragment.v1":
        if not isinstance(payload.get("chunk_index"), int):
            raise ProtocolError("SCHEMA_INVALID", "chunk_index must be int", object_id=payload.get("object_id"))
        if not isinstance(payload.get("chunk_size"), int):
            raise ProtocolError("SCHEMA_INVALID", "chunk_size must be int", object_id=payload.get("object_id"))
        if not isinstance(payload.get("byte_range"), list) or len(payload["byte_range"]) != 2:
            raise ProtocolError("SCHEMA_INVALID", "byte_range must be a 2-element list", object_id=payload.get("object_id"))
        if not isinstance(payload.get("hash"), str):
            raise ProtocolError("SCHEMA_INVALID", "hash must be str", object_id=payload.get("object_id"))
    elif kind == "shongket.content.v1":
        if not isinstance(payload.get("representations"), list):
            raise ProtocolError("SCHEMA_INVALID", "representations must be list", object_id=payload.get("object_id"))
        if not isinstance(payload.get("hop_limit"), int):
            raise ProtocolError("SCHEMA_INVALID", "hop_limit must be int", object_id=payload.get("object_id"))
        if not isinstance(payload.get("copy_budget"), int):
            raise ProtocolError("SCHEMA_INVALID", "copy_budget must be int", object_id=payload.get("object_id"))
        if not isinstance(payload.get("created_at_unix"), int):
            raise ProtocolError("SCHEMA_INVALID", "created_at_unix must be int", object_id=payload.get("object_id"))
    elif kind == "shongket.capsule.v1":
        if not isinstance(payload.get("capsule_id"), str):
            raise ProtocolError("SCHEMA_INVALID", "capsule_id must be str", object_id=payload.get("object_id"))
        if not isinstance(payload.get("object_ref"), str):
            raise ProtocolError("SCHEMA_INVALID", "object_ref must be str", object_id=payload.get("object_id"))
        if not isinstance(payload.get("human_confirmed"), bool):
            raise ProtocolError("SCHEMA_INVALID", "human_confirmed must be bool", object_id=payload.get("object_id"))


@dataclass(frozen=True)
class Validated:
    """Marker returned to indicate success; returned for symmetry with future
    enrichments (e.g. signed-payload validation). The current M0 slice
    treats ``None`` as success and never returns a ``Validated`` value."""


# Patch the namespace so the ``validated`` marker is importable; never returned.
_ = Validated
