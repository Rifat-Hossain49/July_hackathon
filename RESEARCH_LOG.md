# Shongket — Research Log (Draft 1)

Research and planning log. Sources are cited with date accessed; each claim is tagged
**fact** / **experiment** / **inference**. Where the entry below
leaves a fact blank, this plan does **not** assert it; an entry is a
placeholder for the real-device smoke-test phase to fill in.

---

## Format

For each entry:

- Title
- Organization / authors
- URL
- Publication date (if known)
- Date accessed
- Relevant claim
- Effect on Shongket
- Limitations
- Tag: fact / experiment / inference

---

## 1. Transport candidates

### 1.1 Nearby Connections (Google Play Services)

- Title: Connect to other devices — Nearby Connections API.
- Organization: Google / Android Developers.
- URL: https://developers.google.com/nearby/overview
- Date accessed: 2026-07-30.
- Relevant claim (fact): Nearby Connections is a discovery +
  peer transport abstraction that can discover, connect and exchange
  data without internet connectivity and uses Bluetooth, Wi-Fi and
  other available technologies.
- Effect on Shongket: provisional first adapter per DR-ARCH-04;
  behind `TransportAdapter`.
- Limitations: the Android setup requires the Google Play Services SDK
  and runtime permissions; actual OEM/radio behaviour remains a
  physical-device question.
- Tag: fact.

### 1.2 Wi-Fi Direct (P2P)

- Title: Wi-Fi Direct — Android Developers.
- Organization: Google / Wi-Fi Alliance.
- URL: https://developer.android.com/guide/topics/connectivity/wifip2p
- Date accessed: 2026-07-28.
- Relevant claim (fact): Wi-Fi Direct creates a peer-to-peer Wi-Fi
  link without an AP; widely supported but with permission and
  concurrency caveats.
- Effect on Shongket: documented alt adapter; subject to smoke-test.
- Limitations: pairing UX varies; legacy device differences.
- Tag: fact.

### 1.3 Local hotspot + LAN sockets

- Title: SoftAP on Android — Android Developers.
- Organization: Google / Android Developers.
- URL: https://developer.android.com/reference/android/net/wifi/WifiManager#startLocalOnlyHotspot
- Date accessed: 2026-07-28.
- Relevant claim (fact): `startLocalOnlyHotspot` provides a
  network-restricted soft AP for nearby-device data exchange without
  internet; usable with raw sockets.
- Effect on Shongket: fallback when Nearby / Wi-Fi Direct are
  unavailable.
- Limitations: API availability on some Android versions / OEMs;
  permission gating; Android 13+ behavior differences.
- Tag: fact.

### 1.4 Wi-Fi Aware (NAN)

- Title: Wi-Fi Aware — Wi-Fi Alliance.
- Organization: Wi-Fi Alliance.
- URL: https://www.wi-fi.org/discover-wi-fi/wi-fi-aware
- Date accessed: 2026-07-28.
- Relevant claim (fact): Wi-Fi Aware (NAN) enables discovery + direct
  data exchange without infrastructure.
- Effect on Shongket: documented alt adapter; availability varies
  widely on consumer phones.
- Limitations: limited device support; not assumed in M0.
- Tag: fact.

### 1.5 Bluetooth Low Energy (control-only)

- Title: Bluetooth Low Energy overview — Android Developers.
- Organization: Google.
- URL: https://developer.android.com/guide/topics/connectivity/bluetooth/ble-overview
- Date accessed: 2026-07-28.
- Relevant claim (fact): BLE provides low-rate discovery + control;
  unsuitable for bulk media.
- Effect on Shongket: documented for control / discovery only.
- Limitations: low throughput.
- Tag: fact.

### 1.6 Transport comparison

| Axis | Nearby Connections | Wi-Fi Direct | Local hotspot + LAN | Wi-Fi Aware | BLE-only |
|---|---|---|---|---|---|
| Fully offline | yes | yes | yes | yes | yes |
| Bulk data rate | high | high | high | high | low |
| Control over protocol | medium | medium | high | medium | low |
| Interruption handling | framework-dependent | framework-dependent | manual | framework-dependent | manual |
| Android compatibility | broad (Play Services) | broad | varies | narrow | broad |
| Play Services dep | yes | no | no | no | no |
| Permissions | nearby-devices, location | location, wifi | wifi, location | varies | bluetooth, location |
| Low-end availability | moderate | high | high | low | high |
| Implementation complexity | low | medium | medium | medium | low |
| Testability | medium | medium | high | medium | high |
| Live-demo reliability | depends on Play Services | depends on OEM | depends on OEM | low (narrow) | medium |

### 1.7 Provisional recommendation

Per DR-ARCH-04: **Nearby Connections** is a provisional first adapter;
no transport is locked until the smoke-test gate passes. The gate
criteria are:

1. Offline discovery.
2. Compatibility with intended demo phones.
3. Large-file transfer.
4. Interruption detection.
5. Reconnection.
6. Permission behavior.
7. Repeated demo reliability (≥ 10× cold runs).

**Status: PROVISIONAL CANDIDATE.**

Nearby Connections is not the selected Shongket transport until the
real-device smoke-test gate passes.

Real-device transport selection and Android vendor testing belong to
**Milestone 3**, not Milestone 2.

Gate result drives M3 transport choice.

### 1.8 Remaining-scope Android source verification

Accessed 2026-07-30. These are platform facts used to bound D-RS-01,
D-RS-05, D-RS-06, D-RS-11 and D-RS-12; none is device-success evidence.

| Primary source | Verified fact | Effect on Shongket |
|---|---|---|
| Android Developers, [Architecture recommendations](https://developer.android.com/topic/architecture/recommendations) and [Compose UI architecture](https://developer.android.com/develop/ui/compose/architecture) | The current guidance recommends a single-activity structure, Compose, separated UI/data layers and unidirectional data flow | Supports the small Android shell in D-RS-06; these are recommendations, not protocol requirements |
| Android Developers, [Data-transfer background options](https://developer.android.com/develop/background-work/background-tasks/data-transfer-options), [foreground-service overview](https://developer.android.com/develop/background-work/services/fgs) and [service types](https://developer.android.com/develop/background-work/services/fgs/service-types) | User-visible local-device transfers may use a connected-device foreground service, but background-start, type and timeout rules vary by target API | Freeze a background-work port and durable resume; do not assume a service is immortal |
| Android Developers, [Compose state saving](https://developer.android.com/develop/ui/compose/state-saving) | `SavedStateHandle`/saveable state covers small UI state across recreation; complex durable state belongs in local persistence | UI saves identifiers only; canonical transfer state stays in the durable store |
| Android Developers, [Runtime permissions](https://developer.android.com/training/permissions/requesting) | Permissions should be requested in context and denial should degrade gracefully | Supports D-RS-12 and AT-46/AT-66 |
| Android Developers, [App-specific storage](https://developer.android.com/training/data-storage/app-specific) and [Auto Backup](https://developer.android.com/identity/data/autobackup) | Internal app-specific files are sandboxed; backup is configurable, but Android 12+ device-transfer behaviour can vary by manufacturer | Use app-private storage and explicit backup/data-extraction rules, then verify on target devices rather than claiming absolute exclusion |
| Android Developers, [Android Keystore](https://developer.android.com/privacy-and-security/keystore) | Keystore keys can remain non-exportable while cryptographic operations are performed through the provider | Supports a key-store abstraction; does not establish a production trust root or security audit |
| Google for Developers, [Nearby overview](https://developers.google.com/nearby/overview), [Android setup](https://developers.google.com/nearby/connections/android/get-started) and [Play Services setup](https://developers.google.com/android/guides/setup) | Nearby Connections supports offline nearby exchange, requires the Play Services SDK on Android, and requires version-dependent runtime permissions | Nearby remains provisional; denial/GMS absence is an explicit unsupported state and alternates remain behind the adapter |

### 1.9 Provisional Nearby dependency admission record

No dependency is added by this documentation task. Before the Android
slice adds `play-services-nearby`, the implementation commit must
refresh and close every row.

| Required item | Current record |
|---|---|
| Purpose | Provisional direct peer discovery and payload exchange behind `TransportAdapter` |
| License | Google Play Services SDK terms apply; not assumed open source; release/legal review remains manual |
| Maintenance | Official setup and permission documentation updated in 2026; exact artifact/version must be pinned at implementation |
| Binary size | `UNMEASURED`; measure resolved APK/AAB contribution before adding |
| Offline behaviour | Nearby exchange does not require an internet connection; the Android client still requires compatible Google Play Services |
| Platform requirements | Android plus version-dependent Bluetooth/Wi-Fi/local-network permissions; target API must be recorded |
| Smaller alternative | Raw local-hotspot/LAN sockets or Wi-Fi Direct adapter; higher implementation cost but no Play Services runtime |

### 1.10 Android build and UI dependency admission record

Accessed and measured 2026-07-30. These entries close the dependency
gate for the Android foundation only. Artifact sizes are the exact
compressed files downloaded from the official Gradle, Google Maven and
Maven Central repositories; they are not APK-size claims. Transitive
size and final APK contribution must be measured from the resolved
release graph before a release-size claim is made.

Primary sources:

- Android Developers, [AGP 9.2 release notes](https://developer.android.com/build/releases/agp-9-2-0-release-notes):
  AGP 9.2 supports API 37, requires/defaults to Gradle 9.4.1, defaults
  to Build Tools 36.0.0 and requires JDK 17; the page records the 9.2.1
  patch.
- Gradle, [9.4.1 release notes](https://docs.gradle.org/9.4.1/release-notes.html)
  and [release checksums](https://gradle.org/release-checksums/):
  the pinned binary ZIP SHA-256 is
  `2ab2958f2a1e51120c326cad6f385153bb11ee93b3c216c5fccebfdfbb7ec6cb`
  and the wrapper JAR SHA-256 is
  `55243ef57851f12b070ad14f7f5bb8302daceeebc5bce5ece5fa6edb23e1145c`.
- Android Developers, [built-in Kotlin migration](https://developer.android.com/build/migrate-to-built-in-kotlin):
  AGP 9.0 and later enable built-in Kotlin by default, so the Android
  foundation does not apply a separate Kotlin Android plugin. The AGP
  9.2 fixed-issue ledger records its Kotlin Gradle plugin dependency as
  `2.3.10`.
- Android Developers, [Compose BOM](https://developer.android.com/develop/ui/compose/bom),
  [Activity releases](https://developer.android.com/jetpack/androidx/releases/activity)
  and [Material 3 releases](https://developer.android.com/jetpack/androidx/releases/compose-material3):
  the stable versions selected here are BOM `2026.06.00`, Activity
  Compose `1.13.0` and Material 3 `1.4.0`.
- The relevant upstream license texts are the
  [Gradle Apache-2.0 license](https://github.com/gradle/gradle/blob/v9.4.1/LICENSE),
  [AndroidX Apache-2.0 license](https://github.com/androidx/androidx/blob/androidx-main/LICENSE.txt),
  [JUnit 4.13.2 EPL-1.0 license](https://github.com/junit-team/junit4/blob/r4.13.2/LICENSE-junit.txt)
  and [Hamcrest 1.3 BSD license](https://github.com/hamcrest/JavaHamcrest/blob/v1.3/LICENSE.txt).

| Dependency | Purpose | License | Maintenance | Exact downloaded size | Offline behaviour | Platform requirements | Smaller alternative |
|---|---|---|---|---:|---|---|---|
| Gradle wrapper/distribution `9.4.1` | Reproducible Android build entry point | Apache-2.0 | Current AGP 9.2 default; patch release recommended by Gradle | 137,878,901-byte binary ZIP; wrapper checksum pinned | Works after the distribution and dependencies are cached | JDK 17+; Java 24 on this workstation is supported | None compatible with AGP 9.2's stated Gradle floor |
| Android Gradle Plugin `9.2.1` | Compile, test and package Android modules | Apache-2.0 source; Android SDK terms also apply to SDK components | Current documented AGP 9.2 patch | 12,974,080-byte direct plugin JAR | Works after plugin and SDK artifacts are cached | Gradle 9.4.1, JDK 17+, Build Tools 36.0.0; compile SDK 36 selected | A custom Android toolchain would be much larger in project complexity |
| AGP built-in Kotlin | Compile Kotlin sources without a separately applied Kotlin Android plugin | Apache-2.0 | Shipped and maintained with AGP 9.2 | No separately admitted artifact; included in the resolved AGP graph | Same as AGP after cache warm-up | AGP 9.0+ | Java-only code would lose the approved Kotlin conformance target |
| Kotlin Compose compiler plugin `2.3.10` | Compile Compose functions with the same Kotlin compiler line embedded by AGP | Apache-2.0 | Maintained with Kotlin; version exactly matches AGP 9.2's recorded KGP dependency | 1,434-byte marker POM, 98,165-byte Gradle plugin JAR and 936,054-byte embeddable compiler JAR | Works after the build-plugin graph is cached | Kotlin/KGP 2.3.10 | No supported smaller compiler path exists for Compose |
| Compose BOM `2026.06.00` | Pin a compatible stable Compose graph | Apache-2.0 | Official stable BOM current at access date | 40,411-byte POM; no runtime code | Resolution is offline after cache warm-up | Android/Compose build | Individually pin every Compose artifact, with greater drift risk |
| Activity Compose `1.13.0` | Single-activity Compose host | Apache-2.0 | Official stable Activity release | 144,321-byte direct AAR | Fully local at runtime | Android min SDK 23 upstream; Shongket selects 26 | A framework Activity plus manual Compose owner integration is smaller only in declared dependencies, not complexity |
| Material 3 `1.4.0` | Accessible standard UI primitives and theme | Apache-2.0 | Official stable Material 3 release | 5,167,765-byte direct Android AAR | Fully local at runtime | Android with Compose | Raw Compose UI primitives reduce bytes but duplicate accessibility and component behavior |
| JUnit `4.13.2` | JVM conformance test runner | EPL-1.0 | Mature final JUnit 4 line; test-only | 384,581-byte JAR | Test execution works after cache warm-up | JVM test runtime | A bespoke runner would save a test-only dependency but weaken standard reporting |
| Hamcrest Core `1.3` | JUnit 4's test-only transitive matcher API | BSD 3-Clause | Mature compatibility dependency | 45,024-byte JAR | Test execution works after cache warm-up | JVM test runtime | Excluding it risks incompatible JUnit runtime linkage |

The downloaded AAR metadata sets Activity Compose 1.13.0's
`minCompileSdk` to 36 and Material 3 1.4.0's to 35. The admitted BOM
maps Compose UI to 1.11.3. Shongket therefore selects the stable,
available API 36 platform; API 37 is within AGP's maximum but is not a
build requirement for this graph.

No runtime internet permission, analytics SDK, cloud dependency,
production signing material or transport SDK is admitted by this
record. The Google Nearby row above remains open and provisional.

### 1.11 Android CI action admission record

Accessed and measured 2026-07-30. Every action is pinned to a full
Git commit rather than a mutable tag. Sizes below are the exact
compressed source snapshots downloaded from GitHub; downloaded JDK,
Gradle and emulator images are separate build-environment inputs and
are not application payload.

| Action and immutable revision | Purpose | License | Maintenance | Exact source snapshot size | Offline behaviour | Platform requirements | Smaller alternative |
|---|---|---|---|---:|---|---|---|
| [`actions/checkout@11d5960a326750d5838078e36cf38b85af677262`](https://github.com/actions/checkout/tree/11d5960a326750d5838078e36cf38b85af677262) | Materialize the repository in CI | MIT | Official GitHub action, current `v4` target at access | 434,773 bytes | CI-only; needs GitHub to fetch source | GitHub Actions runner | A shell `git` invocation is smaller but duplicates authentication and cleanup handling |
| [`actions/setup-java@c1e323688fd81a25caa38c78aa6df2d33d3e20d9`](https://github.com/actions/setup-java/tree/c1e323688fd81a25caa38c78aa6df2d33d3e20d9) | Pin Temurin JDK 17 and cache Gradle dependencies | MIT | Official GitHub action, current `v4` target at access | 2,518,151 bytes | CI-only; cold runners download a JDK | GitHub Actions runner | Preinstalled Java is less deterministic |
| [`android-actions/setup-android@9fc6c4e9069bf8d3d10b2204b1fb8f6ef7065407`](https://github.com/android-actions/setup-android/tree/9fc6c4e9069bf8d3d10b2204b1fb8f6ef7065407) | Provision Android command-line tools and expose `sdkmanager` after the hosted image stopped doing so | MIT | Active, non-archived repository; current `v3` target at access | 393,066 bytes | CI-only; cold runners download command-line tools and SDK packages | GitHub Actions runner and JDK | Hand-installing command-line tools duplicates checksum, path and cache handling |
| [`ReactiveCircus/android-emulator-runner@4c44018e59b437e86cdfc41da381398f93ed8808`](https://github.com/ReactiveCircus/android-emulator-runner/tree/4c44018e59b437e86cdfc41da381398f93ed8808) | Boot a software emulator for install/launch smoke evidence | MIT | Maintained third-party action, current `v2` target at access | 470,455 bytes | CI-only; a cold runner downloads the selected emulator image | macOS GitHub runner with Android SDK and hardware acceleration | Hand-written `sdkmanager`/`avdmanager`/emulator lifecycle shell is dependency-free but materially more fragile |
| [`actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02`](https://github.com/actions/upload-artifact/tree/ea165f8d65b6e75b540449e92b4886f43607fa02) | Retain test reports and the debug APK as inspectable CI evidence | MIT | Official GitHub action, current `v4` target at access | 2,222,593 bytes | CI-only and requires GitHub artifact storage | GitHub Actions runner | Omitting uploads is smaller but removes inspectable evidence |

The emulator job is software evidence only. It does not establish
Bluetooth/Wi-Fi behavior, OEM compatibility, battery use or any
physical-device acceptance result.

---

### 1.12 Local-Wi-Fi NSD and socket verification

Accessed 2026-07-30. These primary sources define the implementation boundary
in `M3_LOCAL_WIFI_SCOPE.md`. They are platform facts, not physical-device
success evidence.

| Primary source | Verified fact | Effect on Shongket |
|---|---|---|
| Android Developers, [Use network service discovery](https://developer.android.com/develop/connectivity/wifi/use-nsd) and [`NsdManager`](https://developer.android.com/reference/android/net/nsd/NsdManager) | Android NSD advertises and discovers DNS-SD/mDNS services on a local network. Applications should unregister active discovery and service registration. Older devices may require a Wi-Fi multicast lock for mDNS reception. | Use `_shongket._tcp` discovery while the app is open, release registration/discovery/lock on stop, and keep an explicit unsupported/error state. |
| Android Developers, [Local network permission](https://developer.android.com/privacy-and-security/local-network-permission) | Apps targeting SDK 36 or lower retain local-network access through `INTERNET`; `ACCESS_LOCAL_NETWORK` becomes required for apps targeting SDK 37+, with privacy-preserving NSD picker alternatives. | The current target remains 36. Do not declare the API 37 permission early. Record a mandatory permission/API review before any future target-37 update. |
| Android Developers, [Android 16 behavior changes](https://developer.android.com/about/versions/16/behavior-changes-16) | Android 16 local-network restrictions are opt-in; granting `NEARBY_WIFI_DEVICES` restores access during that compatibility test. | Declare and request `NEARBY_WIFI_DEVICES` at point of use on Android 13+, handle denial, and test the Android 16 compatibility restriction when a device is available. |
| Android Developers, [Nearby Wi-Fi device permissions](https://developer.android.com/develop/connectivity/wifi/wifi-permissions) | Android 13+ groups nearby Wi-Fi access under the runtime `NEARBY_WIFI_DEVICES` permission and supports `neverForLocation` when the app does not derive location. | Request only the nearby-device permission for this feature and explicitly assert no location derivation. No fine-location permission is introduced. |
| Android Developers, [`startLocalOnlyHotspot`](https://developer.android.com/reference/android/net/wifi/WifiManager#startLocalOnlyHotspot(android.net.wifi.WifiManager.LocalOnlyHotspotCallback,android.os.Handler)) | Android can create a local-only hotspot for co-located device communication with no internet access. | A user-enabled hotspot is supported as a network topology. Programmatic hotspot creation is excluded from the first slice to avoid credential-sharing and additional Wi-Fi-management scope. |
| Android Developers, [Wi-Fi Direct](https://developer.android.com/develop/connectivity/wifi/wifi-direct) | Wi-Fi Direct can connect devices without a network or hotspot but requires a separate P2P API, permissions and OEM-sensitive group negotiation. | Wi-Fi Direct remains a later alternate. It is not silently mixed with the same-LAN NSD adapter. |

**Design assumption:** the intended first demo uses two phones on the same
local Wi-Fi network or on a hotspot enabled by the user. Whether NSD is
reliable on each intended phone/hotspot pairing remains AT-47 through AT-50
physical evidence.

**Dependency record:** no external dependency is added. Android platform APIs,
Java sockets and JCA SHA-256 are sufficient for this slice.

## 2. Coded-delivery candidates

| Strategy | Description | License / availability | M0 plan |
|---|---|---|---|
| Plain chunks | fixed-size + SHA-256 | n/a (algorithm) | **M0 default** |
| Parity chunks | XOR / simple parity | n/a | later research |
| Reed–Solomon | RS over GF(2^8) or GF(2^16) | multiple permissive libs | later research |
| Fountain / LT | rateless | multiple permissive libs | later research |
| RaptorQ | advanced rateless | some libs restricted | later research |

Recommendation:

- **M0:** plain fixed-size chunks + SHA-256 behind `FragmentationStrategy`.
- **Research extension:** RS or RaptorQ behind the same interface.
- **Do not claim** RaptorQ implementation unless M5+ actually implements
  it.

---

## 3. Content-centric and delay-tolerant networking — prior art

This section credits prior work; Shongket does not invent these
concepts.

### 3.1 Content-Centric Networking (CCN) / Named Data Networking (NDN)

- Title: Named Data Networking.
- Organization: NDN Project.
- URL: https://named-data.net/
- Date accessed: 2026-07-28.
- Relevant claim (fact): NDN names content rather than endpoints and
  uses in-network caching; transfers are content-addressed.
- Effect on Shongket: Shongket borrows the **content-addressed**
  idea (CIDs, manifests, hashes) but does not implement NDN routing;
  it runs on opportunistic peer links, not an NDN deployment.
- Limitations: NDN is a research network architecture; not a
  deployable protocol on consumer phones.
- Tag: fact (about NDN) / inference (about what Shongket borrows).

### 3.2 Delay-Tolerant Networking (DTN) — RFC 9171

- Title: Bundle Protocol Version 7.
- Organization: IETF.
- URL: https://www.rfc-editor.org/rfc/rfc9171
- Date accessed: 2026-07-28.
- Relevant claim (fact): Bundle Protocol defines store-carry-forward
  delivery, custody transfer, and fragmentation.
- Effect on Shongket: Shongket borrows store-carry-forward
  semantics in spirit but does not claim BP7 conformance. M0
  forwarding policy borrows BP-style hop limits and copy budgets.
- Limitations: BP is not directly implemented on consumer phones.
- Tag: fact.

### 3.3 Licklider Transmission Protocol (LTP) — RFC 5326

- Title: Licklider Transmission Protocol for Delay-Tolerant
  Networking.
- Organization: IETF.
- URL: https://www.rfc-editor.org/rfc/rfc5326
- Date accessed: 2026-07-28.
- Relevant claim (fact): LTP defines reliable link-layer block
  transfer for DTN.
- Effect on Shongket: a useful reference for retransmission logic.
- Limitations: not directly implemented.
- Tag: fact.

### 3.4 Fountain codes reference

- Title: Fountain codes and LT codes.
- Organization: academic literature (e.g. Luby 2002; Shokrollahi 2006).
- URL: (placeholder — fill in M5+ when an actual implementation is
  selected).
- Date accessed: 2026-07-28.
- Relevant claim (inference): rateless codes are well-suited to
  peer-drop scenarios.
- Effect on Shongket: deferred to research extension behind
  `FragmentationStrategy`.
- Limitations: this plan does not implement them.
- Tag: inference.

### 3.5 Prior art vs Shongket contribution vs unverified hypotheses

For each technical concept three columns:

- **Prior art:** what already exists.
- **Shongket contribution:** what combination, scheduling behavior,
  protocol rule or crisis-specific design is being proposed.
- **Unverified hypothesis:** what still requires experiments.

| Concept | Prior art | Shongket contribution | Unverified hypothesis |
|---|---|---|---|
| Content-addressed objects | NDN, IPFS, git | borrows the content-addressed idea; simplifies for phone-to-phone | whether Shongket's object schema + dedup beats a comparable non-content-addressed baseline on real devices |
| Store-carry-forward | DTN (RFC 9171), BP | borrows hop-limit / copy-budget semantics; targets opportunistic phone-to-phone links | whether the deterministic copy budget is sufficient under realistic mobility |
| Semantic priority (capsule before bulk) | none standard | **proposes** the signal-vs-media plane split + capsule-first ordering (D-002, D-007, D-009) | whether capsule-before-bulk ordering measurably improves time-to-first-actionable-meaning on real devices |
| Multi-peer missing-chunk completion | standard peer-to-peer | borrows; uses ordinary fixed-size SHA-256 chunks only | whether two-peer completion reliably generalizes to ≥ 3-peer scenarios |
| Critical preemption | none standard | **proposes** chunk-level preemption with resumption at last verified index | whether measured preemption latency stays within the declared bound on real devices |
| Crisis-scoped UX | various messengers | borrows general offline-messenger UX; **proposes** semantic-first delivery as the primary unit | whether end-users in the target scenario understand and trust the semantic-first model |
| Fixed-size SHA-256 chunks | standard | borrows; uses fixed-size + SHA-256 in M0; reserves CDC + keyframe-aligned for later research behind `FragmentationStrategy` | whether 64 KB default chunk size is optimal across modalities on real hardware |
| Manual-form fallback for AI | none standard | **proposes** the structured-form fallback as a first-class path (D-011) | whether manual-form-only capsules are accepted by users at acceptable rates |
| Coded reconstruction (RS / RaptorQ) | standard coding theory | **does not implement in M0–M5**; reserves as a separately approved later research extension | whether rateless coding measurably improves multi-peer completion under realistic peer-drop scenarios |

---

## 4. Unverified claims (not asserted here)

The following are **not** claimed in this plan and remain unfilled:

- Real-wireless throughput on target devices.
- Battery use on real phones.
- Codec availability on all target devices.
- Ble / Wi-Fi Aware coverage on consumer devices in Bangladesh.
- Energy per inference for any candidate model.

These belong in M3+ measurement, not in this plan.

---

## 5. Decision records

### DR-RES-01 — Primary sources only

- Decision: claims above cite official documentation or peer-reviewed
  sources.
- Alternatives: blog posts; vendor marketing.
- Recommended: primary sources.
- Reason: per `AGENTS.md` research rules.
- Evidence required: URL + date accessed.
- Trade-offs: slower to fill.
- Risks: leaving placeholders may look weak.
- Validation: review of source quality at milestone approvals.
- Revisit condition: none.

### DR-RES-02 — No unverified capability claim

- Decision: M0 must not claim any feature that hasn't been
  measured or implemented.
- Alternatives: claim the feature anyway.
- Recommended: do not claim.
- Reason: D-012 + AGENTS.md research rules.
- Evidence required: measurement record.
- Trade-offs: weaker pitch.
- Risks: competitive impression.
- Validation: status table + presenter script.
- Revisit condition: implementation + measurement.

---

## 6. iOS local-network interoperability research

Date accessed: 2026-07-30.

### 6.1 Apple local-network privacy

- Title: Support local network privacy in your app.
- Organization: Apple.
- URL: https://developer.apple.com/videos/play/wwdc2020/10110/
- Verified fact: iOS 14 and later require user permission before an app can
  access the local network. Apps using Bonjour must provide a local-network
  usage description and declare the Bonjour service types they browse.
- Effect on Shongket: nearby mode starts only after an explicit user action;
  `NSLocalNetworkUsageDescription` and `_shongket._tcp` in
  `NSBonjourServices` are required.
- Limitation: simulator build success does not demonstrate that a user granted
  permission on a physical iPhone.
- Tag: fact.

### 6.2 Network framework Bonjour APIs

- Titles: NWListener; NWBrowser; NWConnection.
- Organization: Apple.
- URLs:
  - https://developer.apple.com/documentation/network/nwlistener
  - https://developer.apple.com/documentation/network/nwbrowser
  - https://developer.apple.com/documentation/network/nwconnection
- Verified fact: Network framework provides a listener that can advertise a
  Bonjour service, a browser that can discover Bonjour service endpoints and
  a connection that can exchange bytes with a selected endpoint.
- Effect on Shongket: the iOS adapter uses Network framework instead of a
  third-party networking or discovery dependency.
- Limitation: these APIs do not themselves define Shongket framing,
  validation, authentication or encryption.
- Tag: fact.

### 6.3 iOS property-list declarations

- Titles: NSLocalNetworkUsageDescription; NSBonjourServices.
- Organization: Apple.
- URLs:
  - https://developer.apple.com/documentation/bundleresources/information-property-list/nslocalnetworkusagedescription
  - https://developer.apple.com/documentation/bundleresources/information-property-list/nsbonjourservices
- Verified fact: the usage-description string explains why local-network
  access is needed, while the Bonjour services array lists service types used
  by the app.
- Effect on Shongket: both keys are part of the checked-in iOS Info.plist.
- Limitation: declarations do not bypass the user permission decision.
- Tag: fact.

### 6.4 Multicast DNS and DNS-Based Service Discovery

- Titles: RFC 6762 - Multicast DNS; RFC 6763 - DNS-Based Service Discovery.
- Organization: IETF.
- URLs:
  - https://www.rfc-editor.org/rfc/rfc6762
  - https://www.rfc-editor.org/rfc/rfc6763
- Verified fact: mDNS performs DNS-like operations on a local link without a
  conventional DNS server; DNS-SD discovers named service instances and their
  endpoints.
- Effect on Shongket: Android NSD and Apple Bonjour use the same
  `_shongket._tcp` DNS-SD service contract. This provides the standards basis
  for software-level interoperability.
- Limitation: a Wi-Fi access point can disable multicast or isolate clients,
  so standards compatibility does not guarantee discovery on every network.
- Tag: fact.

### 6.5 Design assumptions requiring physical evidence

- Assumption: a user-enabled phone hotspot permits Bonjour traffic between
  the hotspot host and its connected peer.
- Assumption: the selected Android and iOS device/OS combinations preserve
  service discovery while both Shongket apps remain foregrounded.
- Assumption: common Wi-Fi access points do not enable client isolation.
- Validation: the separately gated Android-to-iPhone physical test matrix in
  `IOS_LOCAL_WIFI_SCOPE.md`.
- Tag: design assumption.
