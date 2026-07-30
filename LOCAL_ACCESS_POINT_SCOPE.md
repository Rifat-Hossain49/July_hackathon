# Shongket local-access-point friendly-link scope

Status: `SCOPE_FROZEN`

Date frozen: 2026-07-31

## 1. User outcome

A person runs Shongket on a laptop connected to an ordinary Wi-Fi access
point or user-enabled hotspot. Other people on that same local link open one
memorable browser address:

```text
http://shongket.local:8787
```

They can exchange the existing public, human-confirmed text capsules without
the access point having an Internet uplink. The laptop remains the hub and
must stay powered, connected and running.

This is local-link communication. It does not join unrelated or
geographically separated Wi-Fi networks.

## 2. Frozen design

### 2.1 Local entry point

- `python -m bdix_hub --access-point` is the explicit local-access-point
  launcher.
- Access-point mode listens on all IPv4 interfaces unless the operator
  explicitly supplies `--host`.
- The launcher advertises `shongket.local.` on the selected IPv4 interface
  using standards-based Multicast DNS and advertises an HTTP service using
  DNS-Based Service Discovery.
- The browser URL remains `http://shongket.local:8787`; the existing strict
  capsule API, SQLite store and resource limits remain unchanged.
- Only one Shongket friendly-name advertiser may use that name on a local link.
  A name conflict is an explicit startup failure, not a silent redirect.

### 2.2 Bounded fallback

- The launcher prints the exact numeric local URL as a fallback.
- Automatic address selection accepts only RFC 1918 private IPv4 or IPv4
  link-local addresses and excludes loopback, multicast, unspecified and
  public addresses.
- `--advertise-address` provides an operator override with the same validation.
- If the optional mDNS package is not installed, the local HTTP hub still
  starts and reports that only the numeric fallback is available.
- If an access point suppresses multicast or enables client isolation,
  `shongket.local` may not work; the numeric URL works only if peer traffic is
  permitted.

### 2.3 Browser presentation

- `/api/v1/status` reports either `domestic-hub` or `local-access-point`.
- Local mode visibly says that the laptop is the hub, Internet is unnecessary,
  and everyone must be on the same Wi-Fi.
- The page shows the memorable address and numeric fallback supplied by the
  server. It does not label the local session as BDIX or cross-ISP.
- Static rendering continues to use `textContent`; server-provided labels are
  never injected as HTML.

### 2.4 Process boundary

- The local runner uses a bounded threaded WSGI server so several nearby
  browsers can poll without one request monopolizing the process.
- Stopping the process unregisters the mDNS service and closes its sockets.
- The local runner remains an operator-run local service, not a hardened
  Internet deployment. The production domestic deployment remains Gunicorn
  behind TLS.
- Application logs remain content-free. Discovery records contain only the
  product name, local address, port and root path.

## 3. Dependency decision

### `zeroconf==0.150.0`

- Purpose: advertise the laptop's friendly `.local` host name and HTTP service
  using RFC 6762 mDNS and RFC 6763 DNS-SD.
- License: LGPL-2.1-or-later.
- Maintenance: PyPI classifies it production/stable; version 0.150.0 was
  released 2026-06-22 and supports Python 3.10 through 3.14.
- Size: the CPython 3.14 Windows x86-64 wheel is approximately 3.1 MB; the
  source archive is approximately 213.6 kB.
- Offline behavior: after installation it advertises only on the local link
  and requires no cloud service or Internet request.
- Platforms: Windows, macOS and POSIX; Python >= 3.10.
- Transitive dependency: `ifaddr==0.2.0`, MIT, 12.3 kB universal wheel,
  released 2022-06-15. It enumerates local interfaces and has no runtime
  network service.
- Smaller alternative: hand-writing an mDNS responder would avoid the package
  but would duplicate conflict detection, packet encoding, interface handling
  and shutdown behavior from two standards. Router-specific DNS would require
  manual administration on every access point. The reviewed package is
  therefore optional and isolated to the local launcher.

## 4. Acceptance catalogue

| ID | Software acceptance |
|---|---|
| LAP-01 | `--access-point` listens on the local network and preserves an explicit `--host` override. |
| LAP-02 | A valid private/link-local IPv4 address produces `http://shongket.local:<port>` plus the exact numeric fallback. |
| LAP-03 | Public, loopback, multicast, unspecified and malformed advertised addresses are rejected. |
| LAP-04 | With the optional dependency available, the launcher registers one `_http._tcp.local.` service whose server is `shongket.local.` and whose A record and port match the listener. |
| LAP-05 | Registration conflict or registration failure is explicit; shutdown unregisters and closes the advertiser. |
| LAP-06 | Without the optional dependency, the hub remains usable through the numeric URL and emits a bounded warning. |
| LAP-07 | Status and browser text distinguish local-access-point mode from domestic/BDIX mode and render server labels safely. |
| LAP-08 | Existing strict public-only schema, consent, rate, storage, expiry, restart and idempotency tests remain unchanged and passing. |
| LAP-09 | Several concurrent local health requests complete through the threaded runner. |
| LAP-10 | A real browser can load local mode, publish, reload and retrieve; physical Android/iPad friendly-name resolution remains a separately reported field observation. |

## 5. Explicit exclusions

- No captive-portal interception, DNS spoofing or forced redirect.
- No claim that a single `.local` name works outside its local link.
- No communication across disconnected access points.
- No automatic access-point creation or router reconfiguration.
- No Bluetooth, Wi-Fi Direct, mesh or application-level multi-hop work.
- No accounts, private chat, media upload or end-to-end encryption claim.
- No guaranteed Android/iOS resolution when multicast is blocked.
- No HTTPS or installable-PWA claim for the local HTTP address.
- No field-success label based only on automated tests.

## 6. Assumptions and field gate

- Clients are connected to the same local link as the laptop.
- The access point allows client-to-client traffic and mDNS multicast.
- The laptop firewall permits inbound TCP on the selected port and mDNS
  advertisement on UDP 5353.
- Modern Android and Apple devices normally provide `.local` resolution, but
  the exact phone, tablet, browser and access point combination must be tested.

The user's successful `192.168.0.29:8787` laptop-to-phone exchange is a useful
field observation for the existing numeric path. It is not evidence that the
new friendly hostname has passed on Android or iPad.

