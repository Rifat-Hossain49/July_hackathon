# Shongket Multi-Path Software Demo Submission

## Project

Shongket is a semantic-first, disruption-tolerant multimedia distribution
protocol for crisis environments with partial connectivity. It sends a
human-confirmed critical capsule before progressively transferring verified
source-media chunks.

Repository owner: [Rifat-Hossain49](https://github.com/Rifat-Hossain49)

## Submission links

- Functional web demo:
  <https://rifat-hossain49.github.io/July_hackathon/>
- Source repository:
  <https://github.com/Rifat-Hossain49/July_hackathon>
- GitHub prerelease:
  <https://github.com/Rifat-Hossain49/July_hackathon/releases/tag/v0.2.0-local-wifi.1>
- Direct demo APK:
  <https://github.com/Rifat-Hossain49/July_hackathon/releases/download/v0.2.0-local-wifi.1/Shongket-0.2.0-local-wifi.1-debug.apk>
- Bangladesh domestic hub: software and deployment package are in
  `bdix_hub/` and `deploy/bdix/`; a public BDIX-hosted URL is pending host,
  DNS and SSH inputs.

## Demonstration

1. Open the public web demo and choose **Run the local demo**.
2. Enter a Bengali or English crisis message or select **Load sample
   scenario**.
3. Use the generated source fixture or select a small local image.
4. Review the manually created capsule against the source evidence, then
   confirm it.
5. Choose public or private visibility. Private content requires explicit
   forwarding consent.
6. Select a simulated peer and start transfer.
7. Interrupt after the first media chunk, refresh the page if desired, and
   resume.
8. Observe that only missing chunks are requested, duplicate replay is
   ignored, the reconstructed SHA-256 matches, and the receiver view appears.
9. Export the content-free redacted diagnostics JSON.

The browser workflow above remains an in-device simulator. For actual nearby
exchange, install the Android APK on two phones, join them to the same Wi-Fi
network (or join one to the other phone's manually enabled hotspot), open the
app on both, tap **Start nearby Wi-Fi**, select the discovered peer and send a
human-confirmed text capsule. Internet service is not required.

For the different-Wi-Fi domestic path, run `python -m bdix_hub` locally for
software verification or deploy the approved package to a Bangladesh host
using `deploy/bdix/README.md`. A laptop, Android phone and iPad then open the
same HTTPS origin, join the same public incident channel and publish/fetch
text-only capsules. This path works only if both ISPs can still reach that
host; it has not yet passed the named-host/two-ISP BDIX field gate.

For a cable-free single-access-point demonstration, install
`deploy/local_access_point/requirements.txt` and run
`python -m bdix_hub --access-point`. Every nearby browser uses the numeric
Wi-Fi link printed by the laptop. The link works without an Internet uplink;
the laptop and access point must stay on. Reserve the laptop address in the
access point DHCP configuration if the link must remain permanent.
`shongket.local` is advertised only as an optional device-dependent
convenience.

## Functional scope

- Bengali and English crisis-message input.
- Manual, human-confirmed semantic capsule creation; no AI model required.
- Public/private handling with forwarding consent for private content.
- Capsule-before-manifest-before-media scheduling.
- Fixed-size chunk transfer, interruption, durable restart recovery, and
  missing-only resume.
- Duplicate suppression, per-fragment integrity checks, reconstruction, and
  source-byte equality verification.
- Received-item display and redacted diagnostics export.
- Browser-local state, no login, no analytics, and no silent network upload.
- Experimental foreground Android DNS-SD/mDNS discovery and bounded local TCP
  text-capsule exchange on a shared Wi-Fi network.
- Public-only, text-only domestic hub with strict validation, durable SQLite,
  expiry, idempotent retry, bounded abuse controls and a cached browser shell.
- Laptop local-access-point mode with a bounded multi-client runner, automatic
  private-address detection, a primary numeric Wi-Fi link and optional mDNS.

## Architecture

Pure protocol logic is isolated from user interfaces and transport adapters.
Semantic extraction, media processing, storage, diagnostics, and transport
have separate boundaries. The web demo is a dependency-free static
HTML/CSS/JavaScript application. The Android app is a Kotlin single-activity
application backed by the shared deterministic protocol concepts and durable
local state. The optional domestic hub is a standard-library WSGI application
behind a transport boundary; it does not change the nearby Android/iOS wire
protocol.

## Evidence

[![Completed Shongket browser demo](web-demo/assets/shongket-demo-complete.png)](web-demo/assets/shongket-demo-complete.png)

The screenshot shows an interrupted transfer after recovery: verified
progress is 100%, the missing-only resume requested chunk 1, one duplicate was
ignored, and received content was reconstructed with matching integrity.

## Limitations and disclosures

**SIMULATED PEER TRANSPORT**

The web demo uses simulated peer transport. The Android APK contains the
experimental local-Wi-Fi implementation, but physical-device and real-radio
validation have not been run.

The BDIX hub software uses a real central-server API rather than simulated peer
transport, but it is not yet deployed to a named Bangladesh host and
cross-ISP/BDIX validation has not been run.

The numeric laptop-to-browser access-point path passed a real Chromium
publish/reload/retrieve exercise. The optional `shongket.local` name returned
NXDOMAIN in that Windows observation; Android and iPad friendly-name behavior
is still unverified. The laptop's numeric address also changes unless the
access point reserves it.

- This is a functional software demo, not a production or field-validated
  emergency system.
- The published APK uses Android debug/demo signing and is not production
  signed.
- Real radios, physical-device testing, and field trials were not run.
- A domestic route is still a network: if ISP access or BDIX/domestic routing
  fails, the hub cannot connect distant users.
- The hub accepts public capsules only and does not provide end-to-end
  encryption, verified identity or factual verification.
- Delivery is disruption-tolerant but never guaranteed.
- No cloud AI is required or used by the offline demo core.
- The screenshot and bundled media are synthetic; source evidence is
  preserved and never silently replaced by generated capsule text.
