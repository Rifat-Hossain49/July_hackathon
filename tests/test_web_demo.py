from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-demo"


def test_web_demo_is_dependency_free_and_discloses_simulation() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "SIMULATED PEER TRANSPORT" in html
    assert "Real radio and field validation are not included" in html
    assert "বাংলা" in html
    assert "Optional image evidence" in html
    assert "text-only delivery is supported" in html
    assert 'rel="manifest"' in html
    assert 'id="install-app"' in html
    assert "app.js" in html
    assert "styles.css" in html
    assert '<script src="http' not in html.lower()
    assert "googletagmanager" not in html.lower()


def test_web_flow_is_bounded_restart_safe_and_content_free_in_diagnostics() -> None:
    source = (WEB / "app.js").read_text(encoding="utf-8")
    assert 'const STORAGE_KEY = "shongket-functional-demo-v2"' in source
    assert 'const LEGACY_STORAGE_KEY = "shongket-functional-demo-v1"' in source
    assert "MAX_MEDIA_BYTES = 512 * 1024" in source
    assert "CAPSULE_DELIVERED_FIRST" in source
    assert "TEXT_ONLY_DELIVERED" in source
    assert "CAPSULE_VERIFIED" in source
    assert "OPTIONAL_ATTACHMENT_OMITTED" in source
    assert "MEDIA_REQUIRED" not in source
    assert "MISSING_ONLY_RESUME" in source
    assert "DUPLICATE_IGNORED" in source
    assert "RECONSTRUCTION_VERIFIED" in source
    assert 'navigator.serviceWorker.register("./service-worker.js")' in source
    export_section = source.split("const exportDocument =", maxsplit=1)[1]
    assert "state.message" not in export_section
    assert "state.location" not in export_section
    assert "state.media.bytes" not in export_section


def test_web_demo_has_a_bounded_offline_app_shell() -> None:
    manifest = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
    service_worker = (WEB / "service-worker.js").read_text(encoding="utf-8")

    assert manifest["start_url"] == "./#demo"
    assert manifest["scope"] == "./"
    assert manifest["display"] == "standalone"
    assert manifest["icons"][0]["src"] == "icon.svg"
    assert "shongket-offline-shell-v1" in service_worker
    assert '"./index.html"' in service_worker
    assert '"./app.js"' in service_worker
    assert '"./styles.css"' in service_worker
    assert "url.origin !== self.location.origin" in service_worker
    assert 'caches.match("./index.html")' in service_worker
