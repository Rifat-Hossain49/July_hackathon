# iOS local-Wi-Fi interoperability scope

## Status

`IOS_SCOPE_STATUS: FROZEN_PENDING_IOS_MILESTONE_APPROVAL`

This scope responds to the product-owner instruction on 2026-07-30:

> Make it iOS compatible also

It extends the frozen Milestone 3 local-Wi-Fi slice to iOS without changing
the canonical Python protocol, the browser simulator or the Android wire
contract.

## Outcome

An iPhone running Shongket and an Android phone running Shongket can exchange
a human-confirmed text crisis capsule while both are connected to the same
local Wi-Fi network. The network may be an ordinary access point with no
internet service or a personal hotspot enabled by the user.

The iOS app:

1. asks for local-network access only after the user starts nearby mode;
2. advertises and discovers `_shongket._tcp` through Bonjour DNS-SD;
3. lists discovered, unverified peers;
4. sends and receives the existing bounded, SHA-256-protected capsule frame
   through local TCP; and
5. displays received text only after schema and integrity verification.

No image is required. Internet service, an account and a cloud server are not
required.

The feature remains **experimental** until the cross-platform physical-device
gate is executed on named Android and iOS devices.

## Acceptance criteria

### Software gate

- **IOS-LW-01 - exact wire interoperability:** Swift encodes and decodes the
  frozen version-1 capsule and acknowledgement formats byte-for-byte with the
  Android implementation. Shared golden vectors cover capsule, request and
  accepted/duplicate/refused acknowledgement bytes.
- **IOS-LW-02 - bounded untrusted input:** the iOS receiver rejects unknown
  versions and types, invalid booleans, malformed UTF-8, oversized fields,
  invalid timestamps, trailing bytes, invalid frame lengths and SHA-256
  mismatches before displaying content.
- **IOS-LW-03 - Bonjour interoperability:** the app registers and browses
  `_shongket._tcp`, advertises `v=1` and `max=8192`, removes lost peers and
  does not present its own advertisement as a selectable peer.
- **IOS-LW-04 - local-only foreground exchange:** `NWListener`, `NWBrowser`
  and `NWConnection` operate only while nearby mode is active. The listener,
  browser and connections are cancelled when nearby mode stops.
- **IOS-LW-05 - matched acknowledgement:** a successful or duplicate
  acknowledgement is accepted only when its digest matches the exact sent
  capsule frame. Refused, malformed and mismatched acknowledgements fail
  closed.
- **IOS-LW-06 - human and privacy gates:** blank or unconfirmed capsules are
  not sent. Private capsules require literal forwarding consent. Peer labels
  and message contents are explicitly unverified.
- **IOS-LW-07 - graceful permission and network failure:** denied local
  network access, unavailable Bonjour, connection refusal, timeout,
  interruption and malformed peer input produce bounded UI errors without
  crashing or disabling the manual text form.
- **IOS-LW-08 - resource bounds:** request and acknowledgement reads have
  fixed maximum lengths and deadlines; duplicate history, received message
  history and concurrent inbound work are bounded.
- **IOS-LW-09 - no hidden dependency:** iOS runtime code contains no cloud
  endpoint, analytics call, account requirement or internet reachability
  check. The feature uses Apple system frameworks only.
- **IOS-LW-10 - unsigned build evidence:** a GitHub macOS runner compiles the
  Swift protocol tests and an unsigned iOS Simulator app. A successful
  simulator build does not claim physical-device or distribution readiness.

### Physical-device gate

The following evidence remains manual and unapproved:

- discovery in both directions between one named Android phone and one named
  iPhone with internet service disabled;
- one verified text transfer in each direction;
- interruption, peer disappearance and restart behavior;
- denied local-network permission and subsequent Settings recovery;
- ordinary same-Wi-Fi and user-enabled hotspot configurations; and
- ten consecutive cold start-to-transfer runs with captured app versions and
  OS versions.

No macOS unit test, simulator build or loopback test may mark this gate
passing.

## Architecture

- `ios/Sources/ShongketProtocol` owns the transport-independent Swift codec,
  validation, acknowledgement and admission models.
- `ios/App/LocalWifiNode.swift` owns Network framework discovery and bounded
  byte transport. It does not own human-confirmation or forwarding policy.
- `ios/App/NearbyWifiViewModel.swift` owns foreground lifecycle and applies
  user/privacy policy before calling the transport.
- `ios/App/ContentView.swift` provides the manual, text-only send and receive
  interface.
- The iOS and Android implementations consume shared protocol vectors so that
  compatibility is verified without physical devices.

Protocol code does not import SwiftUI or Network. Transport code does not
decide visibility, consent, urgency or message truth.

## Apple platform privacy

- Deployment target: iOS 16 or later.
- `NSLocalNetworkUsageDescription` explains nearby Shongket discovery and
  direct transfer.
- `NSBonjourServices` declares `_shongket._tcp`.
- Discovery begins from an explicit user action so the local-network prompt
  appears in context.
- No location, camera, photo-library, microphone, Bluetooth, contacts or
  account permission is requested.
- The multicast networking entitlement is not requested because the app uses
  Bonjour through Network framework rather than arbitrary multicast sockets.

## Dependency decision

No third-party library is added.

| Required item | Decision |
|---|---|
| Purpose | Native iOS local discovery and direct capsule exchange |
| License | Apple system frameworks; no redistributed runtime library |
| Maintenance | SwiftUI, Foundation, CryptoKit and Network are maintained by Apple |
| Binary size | No external runtime artifact |
| Offline behavior | Bonjour discovery and TCP payloads remain on the local network |
| Platform requirements | iOS 16+; devices on the same Wi-Fi or user-enabled hotspot |
| Smaller alternative | Manual IP entry omits discovery and is not the requested nearby-device experience |

## Security and privacy boundary

- SHA-256 detects corruption; it does not authenticate the sender or encrypt
  content.
- Peer names are unverified and can be spoofed.
- The UI warns users to use a trusted local network.
- Private forwarding requires explicit consent, but consent does not make an
  unauthenticated network confidential.
- Message and location content are not written to diagnostics or console
  logs.
- All peer bytes are treated as untrusted and bounded before allocation.

## Explicit exclusions

- iOS Multipeer Connectivity, Bluetooth, BLE, Wi-Fi Direct or Apple
  peer-to-peer/AWDL claims;
- automatic hotspot creation or configuration;
- media, photo, audio or video transfer;
- store-carry-forward relaying beyond the selected peer;
- background transfer after the app leaves the foreground;
- end-to-end encryption, authenticated identity or factual verification;
- App Store, TestFlight or enterprise distribution;
- production signing credentials; and
- any claim that the physical-device gate passes without captured evidence.

## Expected files

- `PRODUCT_DECISIONS.md`
- `RESEARCH_LOG.md`
- `README.md`
- `.github/workflows/ios.yml`
- `protocol-testdata/local_wifi_v1.json`
- `android/app` test-resource configuration and interoperability tests
- `ios/Package.swift`
- `ios/Sources/ShongketProtocol`
- `ios/Tests/ShongketProtocolTests`
- `ios/App`
- `ios/Shongket.xcodeproj`
- structural and security regression tests under `tests/`

## Verification

1. Swift protocol and malformed-input unit tests on a GitHub macOS runner.
2. Shared golden-vector parity with Android.
3. Unsigned iOS Simulator debug build.
4. Existing Android local-WiFi, lint and assembly gates.
5. Full Python regression and repository security scan.
6. The physical-device gate only when named devices and signing are
   available and field validation is separately authorized.

## Distribution boundary

The repository can produce a tested unsigned Simulator build without an
Apple account. Installing on an iPhone requires Apple code signing through a
developer team in Xcode or an approved distribution path. No Apple ID
password, signing certificate or private key is committed to this repository.

## Rollback

Remove `ios/`, the iOS workflow and shared-vector consumers. The Android app,
canonical protocol core, deployed browser simulator and stored protocol data
remain unchanged.
