from __future__ import annotations

import hashlib
import re
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android"


def test_gradle_wrapper_and_distribution_are_pinned() -> None:
    wrapper = ANDROID / "gradle" / "wrapper" / "gradle-wrapper.jar"
    properties = (
        ANDROID / "gradle" / "wrapper" / "gradle-wrapper.properties"
    ).read_text(encoding="utf-8")

    assert hashlib.sha256(wrapper.read_bytes()).hexdigest() == (
        "55243ef57851f12b070ad14f7f5bb8302daceeebc5bce5ece5fa6edb23e1145c"
    )
    assert "gradle-9.4.1-bin.zip" in properties
    assert (
        "distributionSha256Sum="
        "2ab2958f2a1e51120c326cad6f385153bb11ee93b3c216c5fccebfdfbb7ec6cb"
    ) in properties


def test_android_manifest_declares_no_runtime_permissions() -> None:
    manifest = ElementTree.parse(ANDROID / "app" / "src" / "main" / "AndroidManifest.xml")
    assert manifest.getroot().findall("uses-permission") == []


def test_core_conformance_has_no_android_or_transport_dependency() -> None:
    source_root = ANDROID / "core-conformance" / "src" / "main"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(source_root.rglob("*"))
        if path.is_file()
    )
    lowered = source.lower()

    assert "import android." not in source
    assert "bluetooth" not in lowered
    assert "nearby" not in lowered
    assert "wifi" not in lowered

    build = (ANDROID / "core-conformance" / "build.gradle.kts").read_text(
        encoding="utf-8"
    )
    assert "../../shongket_core/testdata" in build
    assert "testImplementation(libs.junit)" in build


def test_agp_uses_built_in_kotlin_and_pinned_compose_compiler() -> None:
    build_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(ANDROID.rglob("*.gradle.kts"))
    )
    catalog = (ANDROID / "gradle" / "libs.versions.toml").read_text(encoding="utf-8")

    assert "org.jetbrains.kotlin.android" not in build_text
    assert 'composeCompiler = "2.3.10"' in catalog
    assert 'agp = "9.2.1"' in catalog
    assert 'composeBom = "2026.06.00"' in catalog


def test_github_actions_are_immutable_revisions() -> None:
    workflow = (ROOT / ".github" / "workflows" / "android.yml").read_text(
        encoding="utf-8"
    )
    uses = re.findall(r"^\s*uses:\s*([^@\s]+)@([^\s]+)\s*$", workflow, re.MULTILINE)

    assert uses
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for _, revision in uses)
