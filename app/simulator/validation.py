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
    boundary. The slice-2 boundaries introduce two more codes:

    * ``"HUMAN_CONFIRMATION_MISSING"`` (AT-02): a capsule payload passes
      schema validation but ``human_confirmed`` is ``False``. The capsule
      must not be scheduled, sent, or persisted.
    * ``"SNAPSHOT_INVALID"`` / ``"SNAPSHOT_CORRUPTED"`` (AT-07): a
      persisted progress snapshot cannot be loaded because the JSON is
      malformed or the recorded SHA-256 no longer matches the stored
      bytes.

    The slice-3 boundaries add one more:

    * ``"OUT_OF_BUDGET"`` (AT-12): a schema-valid, hash-verified, new
      chunk does not fit the store's remaining byte capacity. Named
      after the canonical ``FragmentAck`` status ``out_of_budget``
      (PROTOCOL_SPEC.md §3.6); nothing is stored and no existing
      fragment is touched.

    AT-11 expiry does not raise: expired content is refused at queue
    admission (``priority.admit_for_forwarding``) and never reaches a
    store boundary at all.

    The slice-4 boundaries add two more:

    * ``"PAYLOAD_TOO_LARGE"`` (AT-17): a payload exceeds its canonical
      serialized size limit, or a transport frame exceeds the peer's
      ``max_payload``. This is a canonical code from the
      ``shongket.error.v1`` enum (PROTOCOL_SPEC.md §3.8) and is checked
      *before* the payload is parsed, per §8 "size limits enforced
      before parse".
    * ``"CONSENT_REQUIRED"`` (AT-16): a private object was offered for
      forwarding without explicit consent.
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


# --- canonical size limits (AT-17) -------------------------------------------
#
# Every value below is quoted directly from PROTOCOL_SPEC.md. They are
# limits on the *serialized* form, not on Python object size.
#
# * SemanticCapsule   -- §3.1 "Size limit: capsule <= 4 KB serialized."
# * ContentManifest   -- §3.2 "Size limit: manifest <= 32 KB serialized."
# * FragmentDescriptor-- §3.4 "Size limit: <= 512 B serialized."
# * Transport frame   -- §3.5 PeerCapabilities ``max_payload`` = 1048576,
#   enforced by §6.0 factor 10 "Payload size: respect peer max_payload".
#
# §8 additionally requires that oversized payloads are "rejected at
# framing layer" with "size limits enforced before parse", so the size
# check runs ahead of the schema checks in ``validate_payload``.
#
# The distinction that matters: the 512 B fragment limit bounds the
# *descriptor*, never the chunk payload it describes. A 64 KB chunk has
# a ~250 B descriptor. Chunk payload bytes are bounded by the transport
# frame limit instead.

MAX_FRAME_BYTES = 1_048_576


def size_limit_for(kind: str) -> int:
    """Return the canonical serialized size limit for ``kind`` in bytes."""
    if kind not in _SUPPORTED_SCHEMAS:
        raise ProtocolError("SCHEMA_INVALID", f"unsupported schema kind: {kind!r}")
    return _SUPPORTED_SCHEMAS[kind]["size_limit_bytes"]


def canonical_bytes(payload: dict) -> bytes:
    """Canonical JSON encoding used for every size measurement."""
    import json

    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def check_frame_size(
    frame: bytes,
    *,
    max_payload_bytes: int = MAX_FRAME_BYTES,
    object_id: str | None = None,
) -> None:
    """Framing-layer size guard for raw transport bytes (AT-17).

    Enforces PROTOCOL_SPEC.md §6.0 factor 10 ("respect peer
    ``max_payload``") before the frame is parsed or stored.

    Raises
    ------
    ProtocolError
        With ``code == "PAYLOAD_TOO_LARGE"`` when the frame exceeds the
        limit. A frame of exactly ``max_payload_bytes`` is accepted.
    """
    if len(frame) > max_payload_bytes:
        raise ProtocolError(
            "PAYLOAD_TOO_LARGE",
            f"frame of {len(frame)} bytes exceeds max_payload "
            f"{max_payload_bytes}",
            object_id=object_id,
        )


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
        * unsupported enum value.

        With ``code == "PAYLOAD_TOO_LARGE"`` when the canonical JSON
        encoding exceeds the schema's canonical size limit (AT-17).
        This check runs before any of the above, per PROTOCOL_SPEC.md §8
        ("size limits enforced before parse").
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

    # Framing-layer size check first (AT-17). PROTOCOL_SPEC.md §8
    # requires "size limits enforced before parse", so an oversized
    # payload is refused with the canonical PAYLOAD_TOO_LARGE code
    # before any field, enum or type is inspected. AT-20 is explicitly
    # scoped to payloads "within the size limit", so the two boundaries
    # do not overlap.
    encoded = canonical_bytes(payload)
    if len(encoded) > schema["size_limit_bytes"]:
        raise ProtocolError(
            "PAYLOAD_TOO_LARGE",
            f"payload of {len(encoded)} bytes exceeds "
            f"{schema['size_limit_bytes']} bytes for {kind}",
            object_id=payload.get("object_id"),
        )

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
