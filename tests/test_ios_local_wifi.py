from __future__ import annotations

import json
import plistlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IOS = ROOT / "ios"


def test_ios_scope_has_exact_immutable_approval() -> None:
    decisions = (ROOT / "PRODUCT_DECISIONS.md").read_text(encoding="utf-8")
    scope = (ROOT / "IOS_LOCAL_WIFI_SCOPE.md").read_text(encoding="utf-8")

    assert (
        "IOS_LOCAL_WIFI_IMPLEMENTATION_STATUS: "
        "APPROVED_FOR_IOS_LOCAL_WIFI_INTEROPERABILITY"
    ) in decisions
    assert "5d4bf187cfa7cc56a3db64567c2f53fbb77bd500" in decisions
    assert (
        "IOS_LOCAL_WIFI_FIELD_VALIDATION_STATUS: FIELD_VALIDATION_NOT_APPROVED"
        in decisions
    )
    assert "IOS-LW-01" in scope and "IOS-LW-10" in scope
    assert "No image is required" in scope


def test_info_plist_declares_only_scoped_local_network_access() -> None:
    with (IOS / "App" / "Info.plist").open("rb") as handle:
        info = plistlib.load(handle)

    assert info["NSBonjourServices"] == ["_shongket._tcp"]
    assert "Internet service is not required" in info["NSLocalNetworkUsageDescription"]
    forbidden = {
        "NSBluetoothAlwaysUsageDescription",
        "NSCameraUsageDescription",
        "NSLocationWhenInUseUsageDescription",
        "NSMicrophoneUsageDescription",
        "NSPhotoLibraryUsageDescription",
    }
    assert forbidden.isdisjoint(info)


def test_protocol_is_transport_independent_and_network_is_bounded() -> None:
    protocol = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((IOS / "Sources" / "ShongketProtocol").glob("*.swift"))
    )
    node = (IOS / "App" / "LocalWifiNode.swift").read_text(encoding="utf-8")
    view_model = (IOS / "App" / "NearbyWifiViewModel.swift").read_text(
        encoding="utf-8"
    )

    assert "import Network" not in protocol
    assert "import SwiftUI" not in protocol
    assert "maxLocalWifiFrameBytes = 8_192" in protocol
    assert "INTEGRITY_MISMATCH" in protocol
    assert "BOOLEAN_INVALID" in protocol
    assert 'serviceType = "_shongket._tcp"' in node
    assert "acceptLocalOnly = true" in node
    assert "maximumActiveConnections = 8" in node
    assert "duplicateHistoryLimit = 256" in node
    assert "operationTimeoutSeconds" in node
    assert "LocalWifiCapsuleAdmission.evaluate" in view_model
    assert "print(" not in protocol + node + view_model
    assert "http://" not in protocol + node + view_model
    assert "https://" not in protocol + node + view_model


def test_shared_vector_has_capsule_request_and_all_acknowledgements() -> None:
    vector = json.loads(
        (ROOT / "protocol-testdata" / "local_wifi_v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert vector["serviceType"] == "_shongket._tcp"
    assert vector["protocolVersion"] == 1
    assert vector["maxFrameBytes"] == 8192
    assert len(bytes.fromhex(vector["frameIdHex"])) == 32
    assert len(bytes.fromhex(vector["acceptedAckHex"])) == 42
    assert len(bytes.fromhex(vector["duplicateAckHex"])) == 42
    assert len(bytes.fromhex(vector["refusedAckHex"])) == 42
    assert bytes.fromhex(vector["requestHex"])[:4] == len(
        bytes.fromhex(vector["frameHex"])
    ).to_bytes(4, "big")


def test_ios_workflow_builds_unsigned_simulator_only() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ios.yml").read_text(
        encoding="utf-8"
    )
    project = (
        IOS / "Shongket.xcodeproj" / "project.pbxproj"
    ).read_text(encoding="utf-8")

    assert "swift test --package-path ios" in workflow
    assert 'generic/platform=iOS Simulator' in workflow
    assert "CODE_SIGNING_ALLOWED=NO" in workflow
    assert "archive" not in re.sub(r"Simulator artifact", "", workflow).lower()
    assert "IPHONEOS_DEPLOYMENT_TARGET = 16.0" in project
    assert "PRODUCT_BUNDLE_IDENTIFIER = org.shongket.ios" in project
