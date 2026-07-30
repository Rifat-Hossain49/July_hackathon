from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android"


def test_local_wifi_scope_has_exact_milestone_approval() -> None:
    decisions = (ROOT / "PRODUCT_DECISIONS.md").read_text(encoding="utf-8")
    scope = (ROOT / "M3_LOCAL_WIFI_SCOPE.md").read_text(encoding="utf-8")

    assert (
        "M3_LOCAL_WIFI_IMPLEMENTATION_STATUS: "
        "APPROVED_FOR_MILESTONE_3_LOCAL_WIFI_IMPLEMENTATION"
    ) in decisions
    assert "050e1a50ea758dd9dcd7b43791c663941f54f0c2" in decisions
    assert "M3_LOCAL_WIFI_FIELD_VALIDATION_STATUS: FIELD_VALIDATION_NOT_APPROVED" in decisions
    assert "same local Wi-Fi network" in scope
    assert "AT-47 through AT-50" in scope


def test_android_manifest_requests_only_the_scoped_network_permissions() -> None:
    manifest_path = ANDROID / "app" / "src" / "main" / "AndroidManifest.xml"
    document = ElementTree.parse(manifest_path)
    android_name = "{http://schemas.android.com/apk/res/android}name"
    permissions = {
        element.attrib[android_name]
        for element in document.getroot().findall("uses-permission")
    }

    assert "android.permission.INTERNET" in permissions
    assert "android.permission.ACCESS_NETWORK_STATE" in permissions
    assert "android.permission.ACCESS_WIFI_STATE" in permissions
    assert "android.permission.CHANGE_WIFI_MULTICAST_STATE" in permissions
    assert "android.permission.NEARBY_WIFI_DEVICES" in permissions
    assert all("BLUETOOTH" not in permission for permission in permissions)
    assert all("LOCATION" not in permission for permission in permissions)


def test_local_wifi_implementation_is_bounded_local_and_content_free_in_logs() -> None:
    transport = (
        ANDROID
        / "data-transport"
        / "src"
        / "main"
        / "kotlin"
        / "org"
        / "shongket"
        / "data"
        / "transport"
    )
    limits = (transport / "LocalWifiTransportLimits.kt").read_text(encoding="utf-8")
    sockets = (transport / "LocalWifiSocketTransport.kt").read_text(encoding="utf-8")
    discovery = (transport / "AndroidLocalWifiTransportAdapter.kt").read_text(
        encoding="utf-8"
    )
    app_source = (
        ANDROID
        / "app"
        / "src"
        / "main"
        / "kotlin"
        / "org"
        / "shongket"
        / "app"
    )
    protocol = (app_source / "LocalWifiCapsuleProtocol.kt").read_text(encoding="utf-8")
    activity = (app_source / "MainActivity.kt").read_text(encoding="utf-8")

    assert "MAX_LOCAL_WIFI_FRAME_BYTES: Int = 8_192" in limits
    assert "INTEGRITY_MISMATCH" in protocol
    assert "CodingErrorAction.REPORT" in protocol
    assert "NON_LOCAL_ADDRESS" in sockets
    assert "DUPLICATE_HISTORY_LIMIT = 256" in sockets
    assert 'SERVICE_TYPE = "_shongket._tcp."' in discovery
    assert "NsdManager" in discovery
    assert "LocalWifiCapsuleAdmission.evaluate" in activity
    assert "selectSimulatedPeer" not in activity
    assert "println(" not in protocol + sockets + discovery + activity
    assert "http://" not in protocol + sockets + discovery + activity
    assert "https://" not in protocol + sockets + discovery + activity
