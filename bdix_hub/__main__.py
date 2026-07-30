"""Local development runner; production uses Gunicorn behind HTTPS."""

from __future__ import annotations

import argparse
from wsgiref.simple_server import make_server

from .app import create_app


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Shongket domestic hub locally")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--db-path", default="var/shongket-hub.sqlite3")
    parser.add_argument("--public-origin")
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    app = create_app(
        db_path=arguments.db_path,
        public_origin=arguments.public_origin,
    )
    with make_server(arguments.host, arguments.port, app) as server:
        print(f"Shongket domestic hub listening on http://{arguments.host}:{arguments.port}")
        print("Development server only; use the documented production deployment.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Shongket domestic hub stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
