"""Local development runner; production uses Gunicorn behind HTTPS."""

from __future__ import annotations

import argparse

from .app import create_app
from .local_access import (
    LocalAccessError,
    fallback_url,
    friendly_url,
    select_local_ipv4,
    start_advertisement,
)
from .local_server import make_local_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Shongket domestic hub locally")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--db-path", default="var/shongket-hub.sqlite3")
    parser.add_argument("--public-origin")
    parser.add_argument(
        "--access-point",
        action="store_true",
        help="serve nearby browsers and advertise shongket.local",
    )
    parser.add_argument(
        "--advertise-address",
        help="private/link-local laptop IPv4 to advertise in access-point mode",
    )
    return parser


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if arguments.advertise_address and not arguments.access_point:
        parser.error("--advertise-address requires --access-point")
    if arguments.access_point and arguments.public_origin:
        parser.error("--public-origin is not used in local access-point mode")

    listener_host = arguments.host or (
        "0.0.0.0" if arguments.access_point else "127.0.0.1"
    )
    selected_address: str | None = None
    selected_friendly_url: str | None = None
    selected_fallback_url: str | None = None
    if arguments.access_point:
        try:
            selected_address = select_local_ipv4(arguments.advertise_address)
            selected_friendly_url = friendly_url(arguments.port)
            selected_fallback_url = fallback_url(
                selected_address,
                arguments.port,
            )
        except LocalAccessError as exc:
            parser.error(str(exc))
    app = create_app(
        db_path=arguments.db_path,
        public_origin=arguments.public_origin,
        deployment_mode=(
            "local-access-point" if arguments.access_point else "domestic-hub"
        ),
        friendly_url=selected_friendly_url,
        fallback_url=selected_fallback_url,
    )
    advertisement = None
    with make_local_server(listener_host, arguments.port, app) as server:
        if arguments.access_point:
            assert selected_address is not None
            try:
                advertisement = start_advertisement(
                    selected_address,
                    arguments.port,
                )
            except LocalAccessError as exc:
                parser.error(str(exc))
            app.set_friendly_available(advertisement is not None)
            print("Shongket local access-point hub is ready.")
            if advertisement is None:
                print(
                    "Friendly name unavailable: install "
                    "deploy/local_access_point/requirements.txt."
                )
            else:
                print(
                    "Optional friendly link (device support varies): "
                    f"{selected_friendly_url}"
                )
            print(f"Wi-Fi link: {selected_fallback_url}")
            print("Everyone must join this laptop's Wi-Fi or access point.")
        else:
            print(
                "Shongket domestic hub listening on "
                f"http://{listener_host}:{arguments.port}"
            )
            print("Development server only; use the documented production deployment.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Shongket hub stopped")
        finally:
            if advertisement is not None:
                advertisement.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
