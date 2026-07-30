from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import threading
from urllib.request import urlopen

import pytest

from bdix_hub import __main__ as command
from bdix_hub.app import create_app
from bdix_hub.local_access import (
    FRIENDLY_HOST,
    HTTP_SERVICE_NAME,
    HTTP_SERVICE_TYPE,
    LocalAccessError,
    fallback_url,
    friendly_url,
    select_local_ipv4,
    start_advertisement,
    validate_local_ipv4,
)
from bdix_hub.local_server import (
    BoundedThreadingWSGIServer,
    ContentFreeRequestHandler,
    make_local_server,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10.4.3.2", "10.4.3.2"),
        ("172.16.0.1", "172.16.0.1"),
        ("172.31.255.254", "172.31.255.254"),
        ("192.168.0.29", "192.168.0.29"),
        ("169.254.9.8", "169.254.9.8"),
        (" 192.168.50.7 ", "192.168.50.7"),
    ],
)
def test_lap03_private_and_link_local_ipv4_is_canonical(
    value: str,
    expected: str,
) -> None:
    assert validate_local_ipv4(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-an-address",
        "127.0.0.1",
        "0.0.0.0",
        "8.8.8.8",
        "172.32.0.1",
        "224.0.0.251",
        "255.255.255.255",
        "::1",
    ],
)
def test_lap03_unsafe_advertised_addresses_are_rejected(value: str) -> None:
    with pytest.raises(LocalAccessError):
        validate_local_ipv4(value)


def test_lap02_address_selection_prefers_route_then_hostname_fallback() -> None:
    assert (
        select_local_ipv4(
            route_probe=lambda: "192.168.0.29",
            hostname_candidates=lambda: ["192.168.50.4"],
        )
        == "192.168.0.29"
    )

    def failed_probe() -> str:
        raise OSError("no default route")

    assert (
        select_local_ipv4(
            route_probe=failed_probe,
            hostname_candidates=lambda: ["127.0.0.1", "10.0.0.9"],
        )
        == "10.0.0.9"
    )


def test_lap02_urls_are_exact_and_bounded() -> None:
    assert friendly_url(8787) == "http://shongket.local:8787"
    assert fallback_url("192.168.0.29", 8787) == "http://192.168.0.29:8787"
    assert friendly_url(80) == "http://shongket.local"
    assert fallback_url("192.168.0.29", 80) == "http://192.168.0.29"
    with pytest.raises(LocalAccessError):
        friendly_url(0)


class FakeServiceInfo:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs


class FakeZeroconf:
    instances: list[FakeZeroconf] = []
    fail_registration = False

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs
        self.registered: list[tuple[object, bool]] = []
        self.unregistered: list[object] = []
        self.closed = False
        self.__class__.instances.append(self)

    def register_service(
        self,
        info: object,
        *,
        allow_name_change: bool,
    ) -> None:
        if self.fail_registration:
            raise RuntimeError("conflict")
        self.registered.append((info, allow_name_change))

    def unregister_service(self, info: object) -> None:
        self.unregistered.append(info)

    def close(self) -> None:
        self.closed = True


def fake_zeroconf_api() -> SimpleNamespace:
    FakeZeroconf.instances.clear()
    FakeZeroconf.fail_registration = False
    return SimpleNamespace(
        Zeroconf=FakeZeroconf,
        ServiceInfo=FakeServiceInfo,
        IPVersion=SimpleNamespace(V4Only="v4"),
    )


def test_lap04_advertisement_uses_exact_host_service_address_and_port() -> None:
    advertisement = start_advertisement(
        "192.168.0.29",
        8787,
        zeroconf_api=fake_zeroconf_api(),
    )
    assert advertisement is not None
    instance = FakeZeroconf.instances[-1]
    info = advertisement.service_info
    assert instance.kwargs == {
        "interfaces": ["192.168.0.29"],
        "ip_version": "v4",
    }
    assert info.args == (HTTP_SERVICE_TYPE, HTTP_SERVICE_NAME)
    assert info.kwargs["server"] == FRIENDLY_HOST
    assert info.kwargs["port"] == 8787
    assert info.kwargs["properties"][b"path"] == b"/"
    assert instance.registered == [(info, False)]


def test_lap05_advertisement_cleanup_is_idempotent() -> None:
    advertisement = start_advertisement(
        "10.0.0.5",
        8787,
        zeroconf_api=fake_zeroconf_api(),
    )
    assert advertisement is not None
    instance = FakeZeroconf.instances[-1]
    advertisement.close()
    advertisement.close()
    assert instance.unregistered == [advertisement.service_info]
    assert instance.closed is True


def test_lap05_registration_failure_is_explicit_and_closes_socket() -> None:
    api = fake_zeroconf_api()
    FakeZeroconf.fail_registration = True
    with pytest.raises(LocalAccessError, match="could not claim shongket.local"):
        start_advertisement("192.168.1.4", 8787, zeroconf_api=api)
    assert FakeZeroconf.instances[-1].closed is True


def test_lap06_missing_optional_dependency_keeps_numeric_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import bdix_hub.local_access as local_access

    monkeypatch.setattr(local_access, "_load_zeroconf", lambda: None)
    assert start_advertisement("192.168.0.29", 8787) is None


def test_lap07_status_and_health_report_honest_local_mode(tmp_path: Path) -> None:
    hub = create_app(
        db_path=tmp_path / "hub.sqlite3",
        deployment_mode="local-access-point",
        friendly_url="http://shongket.local:8787",
        fallback_url="http://192.168.0.29:8787",
    )

    from tests.test_bdix_hub import invoke_json

    status, _, document = invoke_json(hub, path="/api/v1/status")
    assert status == 200
    assert document["mode"] == "local-access-point"
    assert document["requires"] == "same local Wi-Fi as the laptop hub"
    assert document["entry"] == {
        "friendly_url": "http://shongket.local:8787",
        "fallback_url": "http://192.168.0.29:8787",
        "friendly_available": False,
    }
    hub.set_friendly_available(True)
    status, _, document = invoke_json(hub, path="/api/v1/status")
    assert status == 200
    assert document["entry"]["friendly_available"] is True
    status, _, health = invoke_json(hub, path="/healthz")
    assert status == 200
    assert health["mode"] == "local-access-point"


def test_lap07_mode_configuration_is_strict(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires both entry URLs"):
        create_app(
            db_path=tmp_path / "missing.sqlite3",
            deployment_mode="local-access-point",
        )
    with pytest.raises(ValueError, match="unsupported"):
        create_app(
            db_path=tmp_path / "unknown.sqlite3",
            deployment_mode="mesh",
        )
    with pytest.raises(ValueError, match="must use shongket.local"):
        create_app(
            db_path=tmp_path / "host.sqlite3",
            deployment_mode="local-access-point",
            friendly_url="http://attacker.example:8787",
            fallback_url="http://192.168.0.29:8787",
        )
    with pytest.raises(LocalAccessError):
        create_app(
            db_path=tmp_path / "public.sqlite3",
            deployment_mode="local-access-point",
            friendly_url="http://shongket.local:8787",
            fallback_url="http://8.8.8.8:8787",
        )


def test_lap01_launcher_binds_all_interfaces_and_prints_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    class FakeServer:
        def __enter__(self) -> FakeServer:
            return self

        def __exit__(self, *unused: object) -> None:
            del unused

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

    def fake_server(host: str, port: int, app: object) -> FakeServer:
        captured.update(host=host, port=port, app=app)
        return FakeServer()

    monkeypatch.setattr(command, "select_local_ipv4", lambda explicit=None: "192.168.0.29")
    monkeypatch.setattr(command, "start_advertisement", lambda address, port: None)
    monkeypatch.setattr(command, "make_local_server", fake_server)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bdix_hub",
            "--access-point",
            "--db-path",
            str(tmp_path / "hub.sqlite3"),
        ],
    )

    assert command.main() == 0
    output = capsys.readouterr().out
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8787
    assert "Friendly name unavailable" in output
    assert "Wi-Fi link: http://192.168.0.29:8787" in output


def test_lap09_threaded_runner_has_bounded_content_free_configuration(
    tmp_path: Path,
) -> None:
    assert BoundedThreadingWSGIServer.max_workers == 16
    assert BoundedThreadingWSGIServer.request_queue_size == 32
    assert ContentFreeRequestHandler.log_message is not object.__str__

    hub = create_app(db_path=tmp_path / "hub.sqlite3")
    server = make_local_server("127.0.0.1", 0, hub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_port)

        def health() -> str:
            with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=3) as response:
                return json.loads(response.read())["status"]

        with ThreadPoolExecutor(max_workers=8) as executor:
            assert list(executor.map(lambda unused: health(), range(16))) == [
                "ready"
            ] * 16
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    assert not thread.is_alive()


def test_local_access_point_dependency_and_operator_guide_are_pinned() -> None:
    root = Path(__file__).resolve().parents[1]
    deploy = root / "deploy" / "local_access_point"
    requirements = (deploy / "requirements.txt").read_text(encoding="utf-8")
    guide = (deploy / "README.md").read_text(encoding="utf-8")

    assert "zeroconf==0.150.0" in requirements
    assert "ifaddr==0.2.0" in requirements
    assert "DHCP" in guide
    assert "numeric link" in guide
    assert "browser resolution varies by device" in guide
    assert "untrusted public Wi-Fi" in guide
