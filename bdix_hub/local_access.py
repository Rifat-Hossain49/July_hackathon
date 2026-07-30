"""Local-link address selection and optional mDNS/DNS-SD advertisement."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from ipaddress import IPv4Address, IPv4Network
import socket
from types import ModuleType
from typing import Callable


FRIENDLY_HOST = "shongket.local."
FRIENDLY_LABEL = "shongket.local"
HTTP_SERVICE_TYPE = "_http._tcp.local."
HTTP_SERVICE_NAME = "Shongket._http._tcp.local."

_ALLOWED_NETWORKS = (
    IPv4Network("10.0.0.0/8"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
    IPv4Network("169.254.0.0/16"),
)


class LocalAccessError(ValueError):
    """The local-access-point configuration is invalid or unavailable."""


def validate_local_ipv4(value: str) -> str:
    """Return a canonical private/link-local IPv4 string."""

    try:
        address = IPv4Address(value.strip())
    except ValueError as exc:
        raise LocalAccessError(
            "advertised address must be a private or link-local IPv4 address"
        ) from exc
    if not any(address in network for network in _ALLOWED_NETWORKS):
        raise LocalAccessError(
            "advertised address must be a private or link-local IPv4 address"
        )
    return str(address)


def _route_probe() -> str:
    """Ask the routing table for the default local IPv4 without sending data."""

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("192.0.2.1", 9))
        return str(probe.getsockname()[0])


def _hostname_candidates() -> list[str]:
    candidates: list[str] = []
    for result in socket.getaddrinfo(
        socket.gethostname(),
        None,
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
    ):
        address = str(result[4][0])
        if address not in candidates:
            candidates.append(address)
    return candidates


def select_local_ipv4(
    explicit: str | None = None,
    *,
    route_probe: Callable[[], str] = _route_probe,
    hostname_candidates: Callable[[], list[str]] = _hostname_candidates,
) -> str:
    """Select a safe local address, preferring the active default route."""

    if explicit is not None:
        return validate_local_ipv4(explicit)
    try:
        return validate_local_ipv4(route_probe())
    except (LocalAccessError, OSError):
        pass
    for candidate in hostname_candidates():
        try:
            return validate_local_ipv4(candidate)
        except LocalAccessError:
            continue
    raise LocalAccessError(
        "no private/link-local IPv4 address was found; "
        "pass --advertise-address with the laptop Wi-Fi address"
    )


def friendly_url(port: int) -> str:
    if not 1 <= port <= 65535:
        raise LocalAccessError("port must be between 1 and 65535")
    port_suffix = "" if port == 80 else f":{port}"
    return f"http://{FRIENDLY_LABEL}{port_suffix}"


def fallback_url(address: str, port: int) -> str:
    if not 1 <= port <= 65535:
        raise LocalAccessError("port must be between 1 and 65535")
    port_suffix = "" if port == 80 else f":{port}"
    return f"http://{validate_local_ipv4(address)}{port_suffix}"


def _load_zeroconf() -> ModuleType | None:
    try:
        return import_module("zeroconf")
    except ModuleNotFoundError as exc:
        if exc.name == "zeroconf":
            return None
        raise LocalAccessError(
            "the zeroconf installation is incomplete"
        ) from exc


@dataclass
class LocalAdvertisement:
    """Registered local HTTP service with deterministic cleanup."""

    zeroconf: object
    service_info: object
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.zeroconf.unregister_service(self.service_info)  # type: ignore[attr-defined]
        finally:
            self.zeroconf.close()  # type: ignore[attr-defined]

    def __enter__(self) -> LocalAdvertisement:
        return self

    def __exit__(self, *unused: object) -> None:
        del unused
        self.close()


def start_advertisement(
    address: str,
    port: int,
    *,
    zeroconf_api: ModuleType | object | None = None,
) -> LocalAdvertisement | None:
    """Register the friendly host; return None only when dependency is absent."""

    selected_address = validate_local_ipv4(address)
    if not 1 <= port <= 65535:
        raise LocalAccessError("port must be between 1 and 65535")
    api = zeroconf_api if zeroconf_api is not None else _load_zeroconf()
    if api is None:
        return None
    instance = None
    try:
        instance = api.Zeroconf(  # type: ignore[attr-defined]
            interfaces=[selected_address],
            ip_version=api.IPVersion.V4Only,  # type: ignore[attr-defined]
        )
        service_info = api.ServiceInfo(  # type: ignore[attr-defined]
            HTTP_SERVICE_TYPE,
            HTTP_SERVICE_NAME,
            addresses=[socket.inet_aton(selected_address)],
            port=port,
            properties={b"path": b"/", b"mode": b"local-access-point"},
            server=FRIENDLY_HOST,
        )
        instance.register_service(service_info, allow_name_change=False)
    except Exception as exc:
        if instance is not None:
            instance.close()
        raise LocalAccessError(
            "could not claim shongket.local on this Wi-Fi; "
            "stop another Shongket hub or use the numeric fallback"
        ) from exc
    return LocalAdvertisement(instance, service_info)
