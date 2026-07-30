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


def test_app_private_persistence_is_bounded_and_rejection_only() -> None:
    persistence = ANDROID / "data-persistence" / "src" / "main" / "kotlin"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(persistence.rglob("*.kt"))
    )
    strings = (ANDROID / "app" / "src" / "main" / "res" / "values" / "strings.xml").read_text(
        encoding="utf-8"
    )

    assert "MAX_FRAGMENT_BYTES: Int = 1_048_576" in source
    assert "MAX_STORE_CAPACITY_BYTES" in source
    assert "IngestResult.OutOfBudget" in source
    assert "evict" not in source.lower()
    assert "nothing was evicted" in strings


def test_android_transport_adapters_are_policy_free_and_bounded() -> None:
    transport = ANDROID / "data-transport" / "src" / "main" / "kotlin"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(transport.rglob("*.kt"))
    )
    lowered = source.lower()

    assert "MAX_TRANSPORT_FRAME_BYTES: Int = 1_048_576" in source
    assert "PAYLOAD_TOO_LARGE" in source
    assert "FIELD_VALIDATION_REQUIRED" in source
    for policy_term in (
        "visibility",
        "consent",
        "expiry",
        "hop_limit",
        "copy_budget",
        "storage_admission",
    ):
        assert policy_term not in lowered


def test_media_pipeline_preserves_source_and_reports_availability() -> None:
    media = ANDROID / "media" / "src" / "main" / "kotlin"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(media.rglob("*.kt"))
    )

    assert "MAX_SOURCE_BYTES: Int = 8 * 1024 * 1024" in source
    assert "encoder mutated source evidence" in source
    assert "Availability.UNAVAILABLE" in source
    assert "TRANSFER_INCOMPLETE" in source
    assert "RepresentationId.ORIGINAL" in source


def test_semantic_default_is_manual_offline_and_human_confirmed() -> None:
    semantic = ANDROID / "semantic" / "src" / "main" / "kotlin"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(semantic.rglob("*.kt"))
    )
    lowered = source.lower()

    assert "UnavailableSemanticExtractor" in source
    assert "HUMAN_CONFIRMATION_REQUIRED" in source
    assert "sourceObjectId" in source
    assert "MODEL_SUGGESTION" in source
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "urlconnection" not in lowered
    form = (
        ANDROID
        / "app"
        / "src"
        / "main"
        / "kotlin"
        / "org"
        / "shongket"
        / "app"
        / "ManualCapsuleForm.kt"
    ).read_text(encoding="utf-8")
    assert "OutlinedTextField" in form
    assert "complete && confirmed" in form


def test_security_and_diagnostics_are_bounded_redacted_and_no_backup() -> None:
    manifest = (
        ANDROID / "app" / "src" / "main" / "AndroidManifest.xml"
    ).read_text(encoding="utf-8")
    security = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ANDROID / "security").rglob("*.kt"))
    )
    diagnostics = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ANDROID / "diagnostics").rglob("*.kt"))
    )

    assert 'android:allowBackup="false"' in manifest
    assert "PlatformKeyStorePort" in security
    assert "SIGNATURE_INVALID" in security
    assert "MAX_APPLICATION_PAYLOAD_BYTES: Int = 1_048_576" in security
    assert "MAX_REPLAY_ENTRIES_PER_PEER" in security
    assert "EXPLICIT_ACTION_REQUIRED" in diagnostics
    assert "MAX_DIAGNOSTIC_EXPORT_BYTES" in diagnostics
    assert "capsuleText" not in diagnostics


def test_release_candidate_is_unsigned_reproducible_and_integrated() -> None:
    app_build = (ANDROID / "app" / "build.gradle.kts").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "android.yml").read_text(
        encoding="utf-8"
    )
    integration = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ANDROID / "release-integration").rglob("*.kt"))
    )

    assert 'create("releaseCandidate")' in app_build
    assert "signingConfig = null" in app_build
    assert "cmp /tmp/shongket-first.apk" in workflow
    assert ":app:assembleReleaseCandidate" in workflow
    assert "SoftwareReleaseFlow" in integration
    assert "explicitPrivateForwardConsent" in integration


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
