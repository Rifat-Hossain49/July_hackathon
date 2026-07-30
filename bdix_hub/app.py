"""Dependency-free WSGI boundary for the Shongket BDIX domestic hub."""

from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Callable, Iterable
import json
import mimetypes
import os
from pathlib import Path
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .local_access import FRIENDLY_LABEL, validate_local_ipv4
from .store import CapsuleStore, StoreLimits
from .validation import (
    HubError,
    MAX_REQUEST_BYTES,
    normalize_channel,
    parse_nonnegative_integer,
    validate_capsule,
)


StartResponse = Callable[[str, list[tuple[str, str]]], Any]
Clock = Callable[[], float]
STATIC_ROOT = Path(__file__).with_name("static")
DEPLOYMENT_MODES = frozenset({"domestic-hub", "local-access-point"})

_STATUS_TEXT = {
    200: "OK",
    201: "Created",
    204: "No Content",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    411: "Length Required",
    413: "Content Too Large",
    415: "Unsupported Media Type",
    429: "Too Many Requests",
    500: "Internal Server Error",
    503: "Service Unavailable",
    507: "Insufficient Storage",
}

_STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/styles.css": "styles.css",
    "/manifest.webmanifest": "manifest.webmanifest",
    "/service-worker.js": "service-worker.js",
    "/icon.svg": "icon.svg",
}

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".svg": "image/svg+xml",
}


class PublishRateLimiter:
    """Bounded per-address sliding-window limiter for publish attempts."""

    def __init__(
        self,
        *,
        maximum: int = 12,
        window_seconds: int = 60,
        max_addresses: int = 2048,
    ) -> None:
        if min(maximum, window_seconds, max_addresses) < 1:
            raise ValueError("rate-limit values must be positive")
        self.maximum = maximum
        self.window_seconds = window_seconds
        self.max_addresses = max_addresses
        self._attempts: OrderedDict[str, deque[int]] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, address: str, *, now_unix: int) -> None:
        key = address[:128] or "unknown"
        cutoff = now_unix - self.window_seconds
        with self._lock:
            attempts = self._attempts.pop(key, deque())
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= self.maximum:
                self._attempts[key] = attempts
                raise HubError(
                    "RATE_LIMITED",
                    "publish rate limit exceeded; retry later",
                    status=429,
                )
            attempts.append(now_unix)
            self._attempts[key] = attempts
            while len(self._attempts) > self.max_addresses:
                self._attempts.popitem(last=False)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _positive_environment_integer(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _validated_local_entry_url(value: str, *, friendly: bool) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("local entry URL is invalid") from exc
    if (
        parsed.scheme != "http"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("local entry URL is invalid")
    if friendly:
        if parsed.hostname.lower() != FRIENDLY_LABEL:
            raise ValueError("friendly entry URL must use shongket.local")
    else:
        validate_local_ipv4(parsed.hostname)
    return value.rstrip("/")


def _base_headers(content_type: str, body_length: int) -> list[tuple[str, str]]:
    return [
        ("Content-Type", content_type),
        ("Content-Length", str(body_length)),
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Referrer-Policy", "no-referrer"),
        (
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        ),
        (
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        ),
    ]


class HubApplication:
    def __init__(
        self,
        store: CapsuleStore,
        *,
        clock: Clock,
        public_origin: str | None,
        trusted_proxy: str | None,
        rate_limiter: PublishRateLimiter,
        static_root: Path,
        deployment_mode: str,
        friendly_url: str | None,
        fallback_url: str | None,
        friendly_available: bool,
    ) -> None:
        if deployment_mode not in DEPLOYMENT_MODES:
            raise ValueError("deployment_mode is unsupported")
        if deployment_mode == "local-access-point" and (
            not friendly_url or not fallback_url
        ):
            raise ValueError("local-access-point mode requires both entry URLs")
        if deployment_mode == "domestic-hub" and (
            friendly_url is not None or fallback_url is not None
        ):
            raise ValueError("domestic-hub mode does not accept local entry URLs")
        self.store = store
        self.clock = clock
        self.public_origin = public_origin.rstrip("/") if public_origin else None
        self.trusted_proxy = trusted_proxy
        self.rate_limiter = rate_limiter
        self.static_root = static_root.resolve()
        self.deployment_mode = deployment_mode
        self.friendly_url = (
            _validated_local_entry_url(friendly_url, friendly=True)
            if friendly_url is not None
            else None
        )
        self.fallback_url = (
            _validated_local_entry_url(fallback_url, friendly=False)
            if fallback_url is not None
            else None
        )
        self.friendly_available = bool(friendly_available)

    def set_friendly_available(self, available: bool) -> None:
        if self.deployment_mode != "local-access-point":
            raise ValueError("friendly advertisement applies only to local mode")
        self.friendly_available = bool(available)

    def _respond(
        self,
        start_response: StartResponse,
        *,
        status: int,
        body: bytes,
        content_type: str,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> list[bytes]:
        headers = _base_headers(content_type, len(body))
        headers.extend(extra_headers or [])
        start_response(f"{status} {_STATUS_TEXT[status]}", headers)
        return [body]

    def _json_response(
        self,
        start_response: StartResponse,
        *,
        status: int,
        document: dict[str, Any],
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> list[bytes]:
        headers = [("Cache-Control", "no-store")]
        headers.extend(extra_headers or [])
        return self._respond(
            start_response,
            status=status,
            body=_json_bytes(document),
            content_type="application/json; charset=utf-8",
            extra_headers=headers,
        )

    def _error(
        self,
        start_response: StartResponse,
        error: HubError,
    ) -> list[bytes]:
        headers: list[tuple[str, str]] = []
        if error.status == 429:
            headers.append(("Retry-After", "60"))
        return self._json_response(
            start_response,
            status=error.status,
            document={
                "schema": "shongket.bdix.error.v1.0",
                "error": error.code,
                "detail": error.detail,
            },
            extra_headers=headers,
        )

    @staticmethod
    def _origin_from_request(environ: dict[str, Any]) -> str:
        scheme = str(environ.get("wsgi.url_scheme", "http"))
        host = str(environ.get("HTTP_HOST", "")).strip()
        return f"{scheme}://{host}".rstrip("/")

    def _check_origin(self, environ: dict[str, Any]) -> None:
        origin = str(environ.get("HTTP_ORIGIN", "")).rstrip("/")
        if not origin:
            return
        expected = self.public_origin or self._origin_from_request(environ)
        if origin != expected:
            raise HubError(
                "ORIGIN_REFUSED",
                "cross-origin publication is not allowed",
                status=403,
            )

    def _request_address(self, environ: dict[str, Any]) -> str:
        remote_address = str(environ.get("REMOTE_ADDR", "unknown"))
        if self.trusted_proxy is None or remote_address != self.trusted_proxy:
            return remote_address
        forwarded_address = str(environ.get("HTTP_X_REAL_IP", "")).strip()
        if (
            not forwarded_address
            or len(forwarded_address) > 64
            or any(character.isspace() for character in forwarded_address)
        ):
            return remote_address
        return forwarded_address

    @staticmethod
    def _read_body(environ: dict[str, Any]) -> bytes:
        raw_length = environ.get("CONTENT_LENGTH")
        if raw_length in (None, ""):
            raise HubError("LENGTH_REQUIRED", "Content-Length is required", status=411)
        try:
            length = int(str(raw_length), 10)
        except ValueError as exc:
            raise HubError("SCHEMA_INVALID", "Content-Length is invalid") from exc
        if length < 1:
            raise HubError("SCHEMA_INVALID", "request body is empty")
        if length > MAX_REQUEST_BYTES:
            raise HubError(
                "PAYLOAD_TOO_LARGE",
                f"request exceeds {MAX_REQUEST_BYTES} bytes",
                status=413,
            )
        stream = environ.get("wsgi.input")
        if stream is None:
            raise HubError("SCHEMA_INVALID", "request body stream is missing")
        body = stream.read(length)
        if len(body) != length:
            raise HubError("SCHEMA_INVALID", "request body is truncated")
        return body

    def _publish(
        self,
        environ: dict[str, Any],
        start_response: StartResponse,
    ) -> list[bytes]:
        content_type = str(environ.get("CONTENT_TYPE", "")).lower()
        media_type = content_type.split(";", maxsplit=1)[0].strip()
        if media_type != "application/json":
            raise HubError(
                "CONTENT_TYPE_REQUIRED",
                "Content-Type must be application/json",
                status=415,
            )
        now_unix = int(self.clock())
        self.rate_limiter.check(
            self._request_address(environ),
            now_unix=now_unix,
        )
        self._check_origin(environ)
        request = validate_capsule(self._read_body(environ))
        capsule, created = self.store.publish(request, now_unix=now_unix)
        return self._json_response(
            start_response,
            status=201 if created else 200,
            document={
                "schema": "shongket.bdix.publish-result.v1.0",
                "created": created,
                "capsule": capsule.public_document(include_client_id=True),
            },
        )

    def _feed(
        self,
        environ: dict[str, Any],
        start_response: StartResponse,
    ) -> list[bytes]:
        try:
            query = parse_qs(
                str(environ.get("QUERY_STRING", "")),
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=3,
            )
        except ValueError as exc:
            raise HubError("SCHEMA_INVALID", "query string is invalid") from exc
        if frozenset(query) - {"channel", "after", "limit"}:
            raise HubError("SCHEMA_INVALID", "query contains an unknown field")
        if "channel" not in query or len(query["channel"]) != 1:
            raise HubError("SCHEMA_INVALID", "one channel value is required")
        if any(len(values) != 1 for values in query.values()):
            raise HubError("SCHEMA_INVALID", "query fields must not repeat")
        channel = normalize_channel(query["channel"][0])
        after = parse_nonnegative_integer(
            query.get("after", [None])[0],
            field="after",
            default=0,
            maximum=9_223_372_036_854_775_807,
        )
        limit = parse_nonnegative_integer(
            query.get("limit", [None])[0],
            field="limit",
            default=50,
            maximum=50,
        )
        if limit < 1:
            raise HubError("SCHEMA_INVALID", "limit must be at least 1")
        capsules, next_cursor = self.store.list_active(
            channel=channel,
            after=after,
            limit=limit,
            now_unix=int(self.clock()),
        )
        return self._json_response(
            start_response,
            status=200,
            document={
                "schema": "shongket.bdix.feed.v1.0",
                "channel": channel,
                "capsules": [capsule.public_document() for capsule in capsules],
                "next_cursor": next_cursor,
                "poll_after_ms": 5000,
            },
        )

    def _health(self, start_response: StartResponse) -> list[bytes]:
        health = self.store.health()
        return self._json_response(
            start_response,
            status=200,
            document={
                "schema": "shongket.bdix.health.v1.0",
                "mode": self.deployment_mode,
                "unix": int(self.clock()),
                **health,
            },
        )

    def _status(self, start_response: StartResponse) -> list[bytes]:
        if self.deployment_mode == "local-access-point":
            mode_fields: dict[str, Any] = {
                "requires": "same local Wi-Fi as the laptop hub",
                "fallback": "use the numeric local URL if multicast is blocked",
                "entry": {
                    "friendly_url": self.friendly_url,
                    "fallback_url": self.fallback_url,
                    "friendly_available": self.friendly_available,
                },
            }
        else:
            mode_fields = {
                "requires": "reachable domestic route to this hub",
                "fallback": "nearby local-Wi-Fi mode",
                "entry": None,
            }
        return self._json_response(
            start_response,
            status=200,
            document={
                "schema": "shongket.bdix.status.v1.0",
                "mode": self.deployment_mode,
                "accepts": "public-text-capsules",
                "private_content": "refused",
                "field_validation": "not-run",
                **mode_fields,
            },
        )

    def _static(
        self,
        path: str,
        start_response: StartResponse,
    ) -> list[bytes]:
        file_name = _STATIC_FILES[path]
        file_path = (self.static_root / file_name).resolve()
        if file_path.parent != self.static_root or not file_path.is_file():
            raise HubError("NOT_FOUND", "asset is unavailable", status=404)
        body = file_path.read_bytes()
        content_type = _CONTENT_TYPES.get(file_path.suffix)
        if content_type is None:
            content_type = (
                mimetypes.guess_type(file_path.name)[0]
                or "application/octet-stream"
            )
        cache_control = (
            "no-cache"
            if path in {"/", "/index.html", "/service-worker.js"}
            else "public, max-age=3600"
        )
        return self._respond(
            start_response,
            status=200,
            body=body,
            content_type=content_type,
            extra_headers=[("Cache-Control", cache_control)],
        )

    def __call__(
        self,
        environ: dict[str, Any],
        start_response: StartResponse,
    ) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        try:
            if path == "/api/v1/capsules":
                if method == "POST":
                    return self._publish(environ, start_response)
                if method == "GET":
                    return self._feed(environ, start_response)
                raise HubError("METHOD_NOT_ALLOWED", "method is not allowed", status=405)
            if path == "/api/v1/status":
                if method != "GET":
                    raise HubError("METHOD_NOT_ALLOWED", "method is not allowed", status=405)
                return self._status(start_response)
            if path == "/healthz":
                if method != "GET":
                    raise HubError("METHOD_NOT_ALLOWED", "method is not allowed", status=405)
                return self._health(start_response)
            if path in _STATIC_FILES:
                if method != "GET":
                    raise HubError("METHOD_NOT_ALLOWED", "method is not allowed", status=405)
                return self._static(path, start_response)
            raise HubError("NOT_FOUND", "resource was not found", status=404)
        except HubError as error:
            return self._error(start_response, error)
        except Exception:
            return self._error(
                start_response,
                HubError(
                    "INTERNAL",
                    "the hub could not complete this request",
                    status=500,
                ),
            )


def create_app(
    *,
    db_path: str | Path | None = None,
    clock: Clock = time.time,
    public_origin: str | None = None,
    trusted_proxy: str | None = None,
    store_limits: StoreLimits | None = None,
    rate_limiter: PublishRateLimiter | None = None,
    static_root: str | Path | None = None,
    deployment_mode: str = "domestic-hub",
    friendly_url: str | None = None,
    fallback_url: str | None = None,
    friendly_available: bool = False,
) -> HubApplication:
    selected_path = Path(
        db_path
        or os.environ.get("SHONGKET_HUB_DB", "var/shongket-hub.sqlite3")
    )
    selected_origin = public_origin
    if selected_origin is None:
        selected_origin = os.environ.get("SHONGKET_HUB_ORIGIN") or None
    selected_trusted_proxy = trusted_proxy
    if selected_trusted_proxy is None:
        selected_trusted_proxy = os.environ.get("SHONGKET_HUB_TRUSTED_PROXY") or None
    selected_limits = store_limits or StoreLimits(
        max_active_capsules=_positive_environment_integer(
            "SHONGKET_HUB_MAX_ACTIVE",
            10_000,
        ),
        max_active_per_channel=_positive_environment_integer(
            "SHONGKET_HUB_MAX_PER_CHANNEL",
            1_000,
        ),
        max_database_bytes=_positive_environment_integer(
            "SHONGKET_HUB_MAX_DB_BYTES",
            64 * 1024 * 1024,
        ),
        cleanup_batch=_positive_environment_integer(
            "SHONGKET_HUB_CLEANUP_BATCH",
            500,
        ),
    )
    selected_rate_limiter = rate_limiter or PublishRateLimiter(
        maximum=_positive_environment_integer(
            "SHONGKET_HUB_PUBLISH_PER_MINUTE",
            12,
        ),
    )
    return HubApplication(
        CapsuleStore(selected_path, limits=selected_limits),
        clock=clock,
        public_origin=selected_origin,
        trusted_proxy=selected_trusted_proxy,
        rate_limiter=selected_rate_limiter,
        static_root=Path(static_root or STATIC_ROOT),
        deployment_mode=deployment_mode,
        friendly_url=friendly_url,
        fallback_url=fallback_url,
        friendly_available=friendly_available,
    )


_default_lock = threading.Lock()
_default_app: HubApplication | None = None


def application(
    environ: dict[str, Any],
    start_response: StartResponse,
) -> Iterable[bytes]:
    """Lazy WSGI entry point for Gunicorn without import-time filesystem writes."""

    global _default_app
    if _default_app is None:
        with _default_lock:
            if _default_app is None:
                _default_app = create_app()
    return _default_app(environ, start_response)
