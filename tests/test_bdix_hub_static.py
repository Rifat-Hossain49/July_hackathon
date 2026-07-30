from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "bdix_hub" / "static"


def test_bh10_browser_client_has_no_global_runtime_dependency_or_media_gate() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "Bangladesh Domestic Hub" in html
    assert "Android phone or iPad" in html
    assert "different Wi-Fi networks" in html
    assert "An image is never required" in html
    assert "Cross-ISP field validation has not yet been run" in html
    assert "PUBLIC • NO ACCOUNT" in html
    assert "Add to Home Screen" in html
    assert 'type="file"' not in html
    assert "<script src=\"http" not in html.lower()
    assert "<link rel=\"stylesheet\" href=\"http" not in html.lower()
    assert "googletagmanager" not in html.lower()
    assert "analytics" not in javascript.lower()
    assert "visibility: \"public\"" in javascript
    assert "public_forwarding_consent: true" in javascript


def test_bh07_outbox_is_bounded_persistent_and_idempotent() -> None:
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'const OUTBOX_KEY = "shongket-bdix-public-outbox-v1"' in javascript
    assert "const MAX_OUTBOX = 20" in javascript
    assert "localStorage.setItem(OUTBOX_KEY" in javascript
    assert "client_id: newClientId()" in javascript
    assert "flushOutbox()" in javascript
    assert "terminal_error" in javascript
    assert "capsule remains queued" in javascript


def test_bh10_service_worker_caches_shell_but_never_api_responses() -> None:
    worker = (STATIC / "service-worker.js").read_text(encoding="utf-8")
    manifest = json.loads(
        (STATIC / "manifest.webmanifest").read_text(encoding="utf-8")
    )

    assert 'const CACHE_NAME = "shongket-bdix-shell-v1"' in worker
    assert 'url.pathname.startsWith("/api/")' in worker
    assert 'url.origin !== self.location.origin' in worker
    assert '"/app.js"' in worker
    assert '"/styles.css"' in worker
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["icons"][0]["src"] == "/icon.svg"


def test_bh12_interface_states_the_domestic_and_nearby_boundaries() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "Domestic hub" in html
    assert "Nearby local Wi-Fi" in html
    assert "Total network loss" in html
    assert "No website can bridge distant users" in html
    assert "BDIX / cross-ISP field validation: <strong>NOT RUN</strong>" in html


def test_bh11_deployment_is_loopback_tls_bounded_and_version_pinned() -> None:
    deploy = ROOT / "deploy" / "bdix"
    requirements = (deploy / "requirements.txt").read_text(encoding="utf-8")
    service = (deploy / "shongket-hub.service").read_text(encoding="utf-8")
    nginx = (deploy / "nginx.conf.example").read_text(encoding="utf-8")
    guide = (deploy / "README.md").read_text(encoding="utf-8")

    assert "gunicorn==26.0.0" in requirements
    assert "--bind 127.0.0.1:8787" in service
    assert "--workers 1" in service
    assert "--threads 8" in service
    assert "--access-logfile" not in service
    assert "ReadWritePaths=/var/lib/shongket-hub" in service
    assert "listen 443 ssl" in nginx
    assert "client_max_body_size 8k" in nginx
    assert "proxy_set_header X-Real-IP $remote_addr" in nginx
    assert "Do not label the deployment \"BDIX validated\"" in guide
    assert "No GitHub token" in guide
    assert "do not" in guide.lower() and "certificate warnings" in guide.lower()


def test_static_files_are_small_and_complete() -> None:
    expected = {
        "index.html",
        "styles.css",
        "app.js",
        "service-worker.js",
        "manifest.webmanifest",
        "icon.svg",
    }
    assert {path.name for path in STATIC.iterdir() if path.is_file()} == expected
    for name in expected:
        assert 0 < (STATIC / name).stat().st_size < 100_000
