# Shongket — Research Log (Draft 1)

Research and planning log. Sources are cited with date accessed; each claim is tagged
**fact** / **experiment** / **inference**. Where the entry below
leaves a fact blank, this plan does **not** assert it; an entry is a
placeholder for the real-device smoke-test phase to fill in.

---

## Forma

For each entry:

- Title
- Organization / authors
- URL
- Publication date (if known)
- Date accessed
- Relevant claim
- Effect on Shongke
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
- URL: https://developer.android.com/reference/android/net/wifi/WifiManager#startLocalOnlyHotspo
- Date accessed: 2026-07-28.
- Relevant claim (fact): `startLocalOnlyHotspot` provides a
  network-restricted soft AP for nearby-device data exchange withou
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
- Relevant claim (fact): Wi-Fi Aware (NAN) enables discovery + direc
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
slice adds `play-services-nearby`, the implementation commit mus
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

---

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

## 3. Content-centric and delay-tolerant networking — prior ar

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

- Title: Licklider Transmission Protocol for Delay-Toleran
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
