from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO, StringIO
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from bdix_hub.app import PublishRateLimiter, create_app
from bdix_hub.store import StoreLimits
from bdix_hub.validation import MAX_REQUEST_BYTES, SCHEMA


@dataclass
class MutableClock:
    value: int = 2_000_000_000

    def __call__(self) -> float:
        return float(self.value)


def capsule_payload(
    *,
    client_id: str | None = None,
    channel: str = "DHAKA-RELIEF",
    message: str = "বিশুদ্ধ পানি প্রয়োজন",
    location: str = "নদীর পূর্ব পাড়",
    urgency: str = "critical",
    visibility: str = "public",
    human_confirmed: Any = True,
    public_forwarding_consent: Any = True,
    expires_in_seconds: Any = 3600,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "client_id": client_id or str(uuid4()),
        "channel": channel,
        "message": message,
        "location": location,
        "urgency": urgency,
        "visibility": visibility,
        "human_confirmed": human_confirmed,
        "public_forwarding_consent": public_forwarding_consent,
        "expires_in_seconds": expires_in_seconds,
    }


def invoke(
    app: Any,
    *,
    method: str = "GET",
    path: str = "/",
    query: str = "",
    body: bytes = b"",
    remote_addr: str = "127.0.0.1",
    content_type: str = "application/json",
    origin: str | None = None,
    content_length: str | None = None,
    extra_environ: dict[str, Any] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    captured: dict[str, Any] = {}

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        exc_info: Any = None,
    ) -> None:
        del exc_info
        captured["status"] = status
        captured["headers"] = headers

    environ: dict[str, Any] = {
        "REQUEST_METHOD": method,
        "SCRIPT_NAME": "",
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "8787",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "HTTP_HOST": "127.0.0.1:8787",
        "REMOTE_ADDR": remote_addr,
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(body)) if content_length is None else content_length,
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": BytesIO(body),
        "wsgi.errors": StringIO(),
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }
    if origin is not None:
        environ["HTTP_ORIGIN"] = origin
    environ.update(extra_environ or {})
    response = b"".join(app(environ, start_response))
    status_code = int(str(captured["status"]).split(" ", maxsplit=1)[0])
    headers = {name.lower(): value for name, value in captured["headers"]}
    return status_code, headers, response


def invoke_json(
    app: Any,
    *,
    method: str = "GET",
    path: str = "/",
    query: str = "",
    document: dict[str, Any] | None = None,
    raw_body: bytes | None = None,
    **kwargs: Any,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    body = (
        raw_body
        if raw_body is not None
        else json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if document is not None
        else b""
    )
    status, headers, response = invoke(
        app,
        method=method,
        path=path,
        query=query,
        body=body,
        **kwargs,
    )
    return status, headers, json.loads(response.decode("utf-8"))


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock()


@pytest.fixture
def hub(tmp_path: Path, clock: MutableClock) -> Any:
    return create_app(
        db_path=tmp_path / "hub.sqlite3",
        clock=clock,
        public_origin="http://127.0.0.1:8787",
    )


def test_bh01_two_different_client_addresses_exchange_one_capsule(hub: Any) -> None:
    request = capsule_payload()
    status, headers, published = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        document=request,
        remote_addr="10.0.0.8",
        origin="http://127.0.0.1:8787",
    )
    assert status == 201
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
    assert published["created"] is True
    assert published["capsule"]["client_id"] == request["client_id"]

    status, _, feed = invoke_json(
        hub,
        path="/api/v1/capsules",
        query="channel=DHAKA-RELIEF&after=0&limit=50",
        remote_addr="172.20.1.4",
    )
    assert status == 200
    assert feed["channel"] == "DHAKA-RELIEF"
    assert len(feed["capsules"]) == 1
    assert feed["capsules"][0]["message"] == request["message"]
    assert "client_id" not in feed["capsules"][0]


def test_bh02_exact_text_boundaries_and_normalization_pass(hub: Any) -> None:
    request = capsule_payload(
        channel="dhaka-1",
        message="m" * 1024,
        location="l" * 200,
    )
    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        document=request,
    )
    assert status == 201
    assert result["capsule"]["channel"] == "DHAKA-1"
    UUID(result["capsule"]["client_id"])


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("message", "", "SCHEMA_INVALID"),
        ("message", "x" * 1025, "SCHEMA_INVALID"),
        ("location", "x" * 201, "SCHEMA_INVALID"),
        ("urgency", "urgent", "SCHEMA_INVALID"),
        ("expires_in_seconds", True, "SCHEMA_INVALID"),
        ("expires_in_seconds", 60, "SCHEMA_INVALID"),
        ("client_id", "NOT-A-UUID", "SCHEMA_INVALID"),
        ("schema", "shongket.bdix.capsule.v2.0", "VERSION_UNSUPPORTED"),
    ],
)
def test_bh02_invalid_fields_are_rejected_without_mutation(
    hub: Any,
    field: str,
    value: Any,
    code: str,
) -> None:
    request = capsule_payload()
    request[field] = value
    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        document=request,
    )
    assert status == 400
    assert result["error"] == code
    _, _, feed = invoke_json(
        hub,
        path="/api/v1/capsules",
        query="channel=DHAKA-RELIEF&after=0&limit=50",
    )
    assert feed["capsules"] == []


def test_bh02_duplicate_unknown_truncated_and_oversized_documents_are_refused(
    hub: Any,
) -> None:
    request = capsule_payload(message="first")
    encoded = json.dumps(request, separators=(",", ":"))
    duplicate = encoded[:-1] + ',"message":"second"}'
    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        raw_body=duplicate.encode("utf-8"),
    )
    assert status == 400
    assert result["error"] == "SCHEMA_INVALID"

    unknown = capsule_payload()
    unknown["extra"] = "no"
    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        document=unknown,
    )
    assert status == 400
    assert result["error"] == "SCHEMA_INVALID"

    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        raw_body=b'{"schema":',
    )
    assert status == 400
    assert result["error"] == "SCHEMA_INVALID"

    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        raw_body=b"x" * (MAX_REQUEST_BYTES + 1),
    )
    assert status == 413
    assert result["error"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"visibility": "private"}, "PUBLIC_ONLY"),
        ({"human_confirmed": False}, "HUMAN_CONFIRMATION_MISSING"),
        ({"public_forwarding_consent": False}, "PUBLIC_CONSENT_REQUIRED"),
        ({"public_forwarding_consent": 1}, "PUBLIC_CONSENT_REQUIRED"),
    ],
)
def test_bh03_public_confirmation_gate(
    hub: Any,
    changes: dict[str, Any],
    code: str,
) -> None:
    request = capsule_payload()
    request.update(changes)
    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        document=request,
    )
    assert status == 403
    assert result["error"] == code


def test_bh04_capsules_and_cursor_survive_application_restart(
    tmp_path: Path,
    clock: MutableClock,
) -> None:
    database = tmp_path / "durable.sqlite3"
    first = create_app(db_path=database, clock=clock)
    request = capsule_payload()
    status, _, result = invoke_json(
        first,
        method="POST",
        path="/api/v1/capsules",
        document=request,
    )
    assert status == 201
    original_cursor = result["capsule"]["cursor"]

    second = create_app(db_path=database, clock=clock)
    status, _, feed = invoke_json(
        second,
        path="/api/v1/capsules",
        query="channel=DHAKA-RELIEF&after=0&limit=50",
    )
    assert status == 200
    assert feed["capsules"][0]["cursor"] == original_cursor
    assert feed["next_cursor"] == original_cursor


def test_bh05_replay_is_idempotent_and_conflicting_replay_is_rejected(
    hub: Any,
) -> None:
    client_id = str(uuid4())
    request = capsule_payload(client_id=client_id)
    first_status, _, first = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        document=request,
    )
    second_status, _, second = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        document=request,
    )
    assert first_status == 201
    assert second_status == 200
    assert second["created"] is False
    assert second["capsule"]["capsule_id"] == first["capsule"]["capsule_id"]
    assert second["capsule"]["cursor"] == first["capsule"]["cursor"]

    conflict = capsule_payload(client_id=client_id, message="different")
    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        document=conflict,
    )
    assert status == 409
    assert result["error"] == "CLIENT_ID_CONFLICT"

    _, _, feed = invoke_json(
        hub,
        path="/api/v1/capsules",
        query="channel=DHAKA-RELIEF&after=0&limit=50",
    )
    assert len(feed["capsules"]) == 1


def test_bh06_expired_capsule_is_not_returned_and_capacity_recovers(
    tmp_path: Path,
    clock: MutableClock,
) -> None:
    app = create_app(
        db_path=tmp_path / "expiry.sqlite3",
        clock=clock,
        store_limits=StoreLimits(
            max_active_capsules=1,
            max_active_per_channel=1,
            max_database_bytes=1_000_000,
            cleanup_batch=10,
        ),
    )
    status, _, _ = invoke_json(
        app,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(expires_in_seconds=3600),
    )
    assert status == 201
    clock.value += 3600
    _, _, expired_feed = invoke_json(
        app,
        path="/api/v1/capsules",
        query="channel=DHAKA-RELIEF&after=0&limit=50",
    )
    assert expired_feed["capsules"] == []

    status, _, _ = invoke_json(
        app,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(),
    )
    assert status == 201


def test_bh08_rate_channel_global_and_database_limits_refuse_safely(
    tmp_path: Path,
    clock: MutableClock,
) -> None:
    rate_app = create_app(
        db_path=tmp_path / "rate.sqlite3",
        clock=clock,
        rate_limiter=PublishRateLimiter(maximum=2),
    )
    for expected in (201, 201):
        status, _, _ = invoke_json(
            rate_app,
            method="POST",
            path="/api/v1/capsules",
            document=capsule_payload(),
            remote_addr="198.51.100.8",
        )
        assert status == expected
    status, headers, result = invoke_json(
        rate_app,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(),
        remote_addr="198.51.100.8",
    )
    assert status == 429
    assert headers["retry-after"] == "60"
    assert result["error"] == "RATE_LIMITED"

    channel_app = create_app(
        db_path=tmp_path / "channel.sqlite3",
        clock=clock,
        store_limits=StoreLimits(
            max_active_capsules=2,
            max_active_per_channel=1,
            max_database_bytes=1_000_000,
        ),
    )
    assert invoke_json(
        channel_app,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(),
    )[0] == 201
    status, _, result = invoke_json(
        channel_app,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(),
    )
    assert status == 507
    assert result["error"] == "CHANNEL_CAPACITY_REACHED"
    assert invoke_json(
        channel_app,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(channel="CHITTAGONG"),
    )[0] == 201
    status, _, result = invoke_json(
        channel_app,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(channel="SYLHET"),
    )
    assert status == 507
    assert result["error"] == "HUB_CAPACITY_REACHED"

    budget_app = create_app(
        db_path=tmp_path / "budget.sqlite3",
        clock=clock,
        store_limits=StoreLimits(max_database_bytes=1),
    )
    status, _, result = invoke_json(
        budget_app,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(),
    )
    assert status == 507
    assert result["error"] == "OUT_OF_BUDGET"


def test_bh09_message_content_is_not_written_to_application_output(
    hub: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_marker = "PUBLIC-CONTENT-MUST-NOT-BE-IN-OPS-LOG-7921"
    status, _, _ = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(message=secret_marker),
    )
    assert status == 201
    captured = capsys.readouterr()
    assert secret_marker not in captured.out
    assert secret_marker not in captured.err


def test_origin_content_type_query_and_health_boundaries(hub: Any) -> None:
    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(),
        origin="https://evil.example",
    )
    assert status == 403
    assert result["error"] == "ORIGIN_REFUSED"

    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(),
        content_type="text/plain",
    )
    assert status == 415
    assert result["error"] == "CONTENT_TYPE_REQUIRED"

    status, _, result = invoke_json(
        hub,
        path="/api/v1/capsules",
        query="channel=A&after=0&limit=50",
    )
    assert status == 400
    assert result["error"] == "SCHEMA_INVALID"

    status, headers, health = invoke_json(hub, path="/healthz")
    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert health["mode"] == "domestic-hub"
    assert health["status"] == "ready"
    assert int(health["database_bytes"]) > 0


def test_reverse_proxy_address_is_trusted_only_when_explicitly_configured(
    tmp_path: Path,
    clock: MutableClock,
) -> None:
    limiter = PublishRateLimiter(maximum=1)
    trusted = create_app(
        db_path=tmp_path / "trusted.sqlite3",
        clock=clock,
        trusted_proxy="127.0.0.1",
        rate_limiter=limiter,
    )
    assert invoke_json(
        trusted,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(),
        remote_addr="127.0.0.1",
        extra_environ={"HTTP_X_REAL_IP": "198.51.100.1"},
    )[0] == 201
    assert invoke_json(
        trusted,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(channel="SYLHET"),
        remote_addr="127.0.0.1",
        extra_environ={"HTTP_X_REAL_IP": "198.51.100.2"},
    )[0] == 201

    untrusted = create_app(
        db_path=tmp_path / "untrusted.sqlite3",
        clock=clock,
        rate_limiter=PublishRateLimiter(maximum=1),
    )
    assert invoke_json(
        untrusted,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(),
        remote_addr="203.0.113.9",
        extra_environ={"HTTP_X_REAL_IP": "198.51.100.1"},
    )[0] == 201
    status, _, result = invoke_json(
        untrusted,
        method="POST",
        path="/api/v1/capsules",
        document=capsule_payload(channel="SYLHET"),
        remote_addr="203.0.113.9",
        extra_environ={"HTTP_X_REAL_IP": "198.51.100.2"},
    )
    assert status == 429
    assert result["error"] == "RATE_LIMITED"


def test_content_length_is_required_and_truncation_is_rejected(hub: Any) -> None:
    body = json.dumps(capsule_payload()).encode("utf-8")
    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        raw_body=body,
        content_length="",
    )
    assert status == 411
    assert result["error"] == "LENGTH_REQUIRED"

    status, _, result = invoke_json(
        hub,
        method="POST",
        path="/api/v1/capsules",
        raw_body=body,
        content_length=str(len(body) + 1),
    )
    assert status == 400
    assert result["error"] == "SCHEMA_INVALID"
