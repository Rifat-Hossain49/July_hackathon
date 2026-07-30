"""Strict validation and canonical identity for public BDIX hub capsules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
import unicodedata
from typing import Any
from uuid import UUID


SCHEMA = "shongket.bdix.capsule.v1.0"
MAX_REQUEST_BYTES = 8192
MAX_MESSAGE_CHARS = 1024
MAX_LOCATION_CHARS = 200
MAX_CHANNEL_CHARS = 32
MIN_CHANNEL_CHARS = 3
ALLOWED_EXPIRY_SECONDS = frozenset({3600, 21600, 86400})
ALLOWED_URGENCIES = frozenset({"normal", "important", "critical"})

_CHANNEL_PATTERN = re.compile(r"^[A-Z0-9](?:[A-Z0-9-]{1,30}[A-Z0-9])?$")
_EXPECTED_FIELDS = frozenset(
    {
        "schema",
        "client_id",
        "channel",
        "message",
        "location",
        "urgency",
        "visibility",
        "human_confirmed",
        "public_forwarding_consent",
        "expires_in_seconds",
    }
)


class HubError(Exception):
    """A bounded public error with a stable machine-readable code."""

    def __init__(self, code: str, detail: str, status: int = 400) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True, slots=True)
class CapsuleRequest:
    schema: str
    client_id: str
    channel: str
    message: str
    location: str
    urgency: str
    visibility: str
    human_confirmed: bool
    public_forwarding_consent: bool
    expires_in_seconds: int

    def canonical_bytes(self) -> bytes:
        return canonical_json(asdict(self))

    @property
    def capsule_id(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def _reject_constant(value: str) -> None:
    raise HubError("SCHEMA_INVALID", f"non-finite number is not allowed: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise HubError("SCHEMA_INVALID", f"duplicate field: {key}")
        result[key] = value
    return result


def canonical_json(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise HubError("SCHEMA_INVALID", "value is not canonical UTF-8 JSON") from exc
    return encoded


def decode_json_document(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_REQUEST_BYTES:
        raise HubError(
            "PAYLOAD_TOO_LARGE",
            f"request exceeds {MAX_REQUEST_BYTES} bytes",
            status=413,
        )
    if not raw:
        raise HubError("SCHEMA_INVALID", "request body is empty")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise HubError("SCHEMA_INVALID", "request is not valid UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except HubError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise HubError("SCHEMA_INVALID", "request is not valid JSON") from exc
    if not isinstance(value, dict):
        raise HubError("SCHEMA_INVALID", "request root must be an object")
    return value


def _require_exact_fields(value: dict[str, Any]) -> None:
    fields = frozenset(value)
    missing = sorted(_EXPECTED_FIELDS - fields)
    unknown = sorted(fields - _EXPECTED_FIELDS)
    if missing:
        raise HubError("SCHEMA_INVALID", f"missing field: {missing[0]}")
    if unknown:
        raise HubError("SCHEMA_INVALID", f"unknown field: {unknown[0]}")


def normalize_channel(value: Any) -> str:
    if not isinstance(value, str):
        raise HubError("SCHEMA_INVALID", "channel must be a string")
    channel = value.strip().upper()
    if not MIN_CHANNEL_CHARS <= len(channel) <= MAX_CHANNEL_CHARS:
        raise HubError(
            "SCHEMA_INVALID",
            f"channel must be {MIN_CHANNEL_CHARS}-{MAX_CHANNEL_CHARS} characters",
        )
    if not _CHANNEL_PATTERN.fullmatch(channel):
        raise HubError(
            "SCHEMA_INVALID",
            "channel may contain only A-Z, 0-9 and internal hyphens",
        )
    return channel


def _bounded_text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise HubError("SCHEMA_INVALID", f"{field} must be a string")
    normalized = value.strip()
    if not normalized:
        raise HubError("SCHEMA_INVALID", f"{field} must not be empty")
    if len(normalized) > maximum:
        raise HubError(
            "SCHEMA_INVALID",
            f"{field} exceeds {maximum} characters",
        )
    for character in normalized:
        category = unicodedata.category(character)
        if category == "Cs" or (category == "Cc" and character not in "\n\t"):
            raise HubError(
                "SCHEMA_INVALID",
                f"{field} contains an unsupported control character",
            )
    try:
        normalized.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise HubError("SCHEMA_INVALID", f"{field} is not valid Unicode") from exc
    return normalized


def _canonical_uuid(value: Any) -> str:
    if not isinstance(value, str):
        raise HubError("SCHEMA_INVALID", "client_id must be a string")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise HubError("SCHEMA_INVALID", "client_id must be a UUID") from exc
    canonical = str(parsed)
    if value != canonical:
        raise HubError(
            "SCHEMA_INVALID",
            "client_id must use canonical lowercase UUID form",
        )
    return canonical


def validate_capsule(raw: bytes) -> CapsuleRequest:
    value = decode_json_document(raw)
    _require_exact_fields(value)

    if value["schema"] != SCHEMA:
        raise HubError("VERSION_UNSUPPORTED", f"schema must be {SCHEMA}")
    if value["visibility"] != "public":
        raise HubError(
            "PUBLIC_ONLY",
            "the domestic hub accepts public capsules only",
            status=403,
        )
    if value["human_confirmed"] is not True:
        raise HubError(
            "HUMAN_CONFIRMATION_MISSING",
            "human confirmation is required",
            status=403,
        )
    if value["public_forwarding_consent"] is not True:
        raise HubError(
            "PUBLIC_CONSENT_REQUIRED",
            "explicit public forwarding consent is required",
            status=403,
        )

    urgency = value["urgency"]
    if not isinstance(urgency, str) or urgency not in ALLOWED_URGENCIES:
        raise HubError("SCHEMA_INVALID", "urgency is not supported")

    expiry = value["expires_in_seconds"]
    if isinstance(expiry, bool) or not isinstance(expiry, int):
        raise HubError("SCHEMA_INVALID", "expires_in_seconds must be an integer")
    if expiry not in ALLOWED_EXPIRY_SECONDS:
        raise HubError("SCHEMA_INVALID", "expires_in_seconds is not supported")

    request = CapsuleRequest(
        schema=SCHEMA,
        client_id=_canonical_uuid(value["client_id"]),
        channel=normalize_channel(value["channel"]),
        message=_bounded_text(value["message"], "message", MAX_MESSAGE_CHARS),
        location=_bounded_text(value["location"], "location", MAX_LOCATION_CHARS),
        urgency=urgency,
        visibility="public",
        human_confirmed=True,
        public_forwarding_consent=True,
        expires_in_seconds=expiry,
    )
    if len(request.canonical_bytes()) > MAX_REQUEST_BYTES:
        raise HubError(
            "PAYLOAD_TOO_LARGE",
            f"canonical request exceeds {MAX_REQUEST_BYTES} bytes",
            status=413,
        )
    return request


def parse_nonnegative_integer(
    value: str | None,
    *,
    field: str,
    default: int,
    maximum: int,
) -> int:
    if value is None:
        return default
    if not value or not value.isascii() or not value.isdecimal():
        raise HubError("SCHEMA_INVALID", f"{field} must be a non-negative integer")
    parsed = int(value)
    if parsed > maximum:
        raise HubError("SCHEMA_INVALID", f"{field} exceeds {maximum}")
    return parsed


def reject_nonfinite(value: Any) -> None:
    """Defensive helper for tests and future schema extensions."""

    if isinstance(value, float) and not math.isfinite(value):
        raise HubError("SCHEMA_INVALID", "non-finite number is not allowed")
