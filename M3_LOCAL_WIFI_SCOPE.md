# Milestone 3 local-Wi-Fi transport scope

## Status

`SCOPE_STATUS: FROZEN_PENDING_MILESTONE_APPROVAL`

This scope responds to the product-owner instruction on 2026-07-30:

> communicate with a nearby device over Wi-Fi without internet

It is a narrow Milestone 3 design delta. It does not change the canonical
Python protocol core or the frozen simulator.

## Outcome

Two Android phones running Shongket can exchange a human-confirmed crisis
capsule while both are connected to the same local Wi-Fi network. The network
may be an ordinary access point with no internet service or a hotspot enabled
by the user on one phone.

Each phone:

1. opens Shongket and starts local-Wi-Fi mode;
2. advertises and discovers Shongket services through Android Network Service
   Discovery (DNS-SD/mDNS);
3. selects a discovered peer;
4. sends a bounded, integrity-protected text capsule through a local TCP
   socket; and
5. displays the received capsule and its verification result.

The feature is classified **experimental** until AT-47 through AT-50 are
executed on named physical phones.

## Acceptance criteria

### Software gate

- **LW-01 — bounded wire schema:** every frame has a version, type, explicit
  byte lengths and a hard maximum before allocation. Unknown versions,
  malformed UTF-8, oversized fields, trailing bytes and integrity mismatches
  are refused.
- **LW-02 — content integrity:** the capsule identifier is the SHA-256 digest
  of the canonical wire body. The receiver verifies it before displaying
  content.
- **LW-03 — local-only socket boundary:** outbound endpoints must be loopback,
  link-local, RFC1918 IPv4 or unique-local IPv6. Public internet addresses are
  refused.
- **LW-04 — real discovery adapter:** the Android adapter registers and
  discovers `_shongket._tcp` services with `NsdManager`, exposes resolved local
  endpoints, and removes lost peers.
- **LW-05 — bidirectional foreground exchange:** either phone can advertise,
  discover, send and receive while the app remains open. A positive
  acknowledgement is matched to the capsule identifier.
- **LW-06 — human and privacy gates:** blank or unconfirmed capsules are never
  sent. Private capsules require literal forwarding consent. Received peer
  labels are explicitly unverified.
- **LW-07 — graceful refusal:** permission denial, unavailable NSD, malformed
  peer input, socket timeout and shutdown produce bounded error states without
  crashing or disabling the manual capsule form.
- **LW-08 — resource bounds:** the server uses bounded frame sizes, bounded
  duplicate history, timeouts and a bounded worker pool. It closes sockets and
  unregisters discovery when local-Wi-Fi mode stops.
- **LW-09 — no hidden network dependency:** runtime code contains no cloud
  endpoint, analytics call, account dependency or internet reachability check.
  Automated socket tests run on loopback with external network access absent.

### Physical-device gate

AT-47 through AT-50 remain the real-radio acceptance catalogue:

- discovery and capability exchange on two named phones with internet
  disabled;
- transfer, interruption and reconnection evidence;
- an explicit OEM/Android compatibility matrix; and
- ten consecutive cold discovery-to-transfer runs.

No emulator, loopback test or successful build may mark these tests passing.

## Architecture

The implementation remains behind the transport boundary:

- `android/data-transport` owns the wire codec, bounded socket endpoint and
  Android NSD adapter;
- `android/app` owns runtime permission prompts and unidirectional Compose UI
  state;
- the adapter moves bytes and reports liveness only;
- human confirmation and private-forwarding consent remain application/core
  policy gates; and
- received payloads are treated as untrusted until schema and SHA-256
  verification pass.

## Permissions

For target SDK 36:

- `INTERNET` permits local TCP sockets; it does not make the feature depend on
  internet service.
- `ACCESS_NETWORK_STATE` supports plain-language connectivity status.
- `ACCESS_WIFI_STATE` and `CHANGE_WIFI_MULTICAST_STATE` support foreground
  mDNS reception on older devices.
- `NEARBY_WIFI_DEVICES` is requested at point of use on Android 13+ with
  `neverForLocation`; denial leaves the manual form available.

No location, Bluetooth, camera, microphone, storage or account permission is
added.

## Dependency decision

No library dependency is added. The slice uses Android platform `NsdManager`,
`WifiManager.MulticastLock`, Java sockets and JCA SHA-256.

| Required item | Decision |
|---|---|
| Purpose | Local discovery and capsule exchange without internet |
| License | Android platform / Java runtime; no new redistributed library |
| Maintenance | Platform APIs documented and maintained by Android |
| Binary size | No external runtime artifact |
| Offline behavior | All discovery and traffic remain on the local network |
| Platform requirements | Android 8.0+; both phones on the same Wi-Fi or user-enabled hotspot |
| Smaller alternative | Manual IP entry is smaller but is not a usable nearby-device experience |

## Security and privacy boundary

- The first slice does not claim end-to-end encryption or authenticated peer
  identity.
- The UI warns users to use a trusted local network and labels peer names
  unverified.
- Private forwarding still requires explicit consent, but consent does not
  turn an unauthenticated transport into a secure channel.
- Message and location content are not written to diagnostics or console logs.
- Public internet destinations are rejected by address classification.

## Explicit exclusions

- Wi-Fi Direct group creation or automatic hotspot provisioning;
- Nearby Connections or any Google Play Services dependency;
- Bluetooth or BLE;
- media, photo, audio or video transfer in this slice;
- store-carry-forward relaying beyond the selected peer;
- background transfer after the app is closed;
- end-to-end encryption, authenticated identity or factual verification;
- public-store publication; and
- a claim that AT-47 through AT-50 pass without physical evidence.

## Files

Expected implementation changes are limited to:

- `PRODUCT_DECISIONS.md`
- `RESEARCH_LOG.md`
- `android/README.md`
- `android/app/src/main/AndroidManifest.xml`
- `android/app/src/main/kotlin/org/shongket/app/MainActivity.kt`
- Android string resources
- new local-Wi-Fi sources and tests in `android/data-transport`

## Verification

1. JVM codec and loopback socket tests.
2. Existing Kotlin vector, transport, persistence, security and release tests.
3. Android lint and debug/release-candidate assembly.
4. API 35 emulator install and launch with permission-denial evidence.
5. Full Python regression.
6. Physical AT-47 through AT-50 only when two named phones are available and
   field validation is separately authorized.

## Rollback

Remove the concrete local-Wi-Fi adapter, permissions and UI section. The
transport contract, deterministic simulator, canonical core and stored
protocol data remain unchanged.
