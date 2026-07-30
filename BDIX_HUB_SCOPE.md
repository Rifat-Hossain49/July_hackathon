# Shongket BDIX Domestic Hub — Scope Freeze

Date frozen: 2026-07-31

## 1. Product-owner request

The product owner asked Shongket to reproduce the useful network pattern seen
during the 2024 Bangladesh Internet shutdown: people on different local
Wi-Fi/ISP networks should be able to exchange crisis information through a
Bangladesh-hosted service while domestic ISP/BDIX routing remains available,
even when global Internet routes are unavailable.

This is a second transport path. It does not replace the existing one-hop
Android/iOS local-Wi-Fi mode.

## 2. Smallest valid product

The first BDIX hub is a **public, text-only crisis-capsule bulletin** served as
a small progressive web app from one Bangladesh-hosted origin.

It:

1. opens in a browser on a laptop, Android phone, iPhone or iPad;
2. lets a person join a bounded incident channel;
3. creates a short message with operator-supplied location and urgency;
4. requires human confirmation and explicit acknowledgement that the message
   will be public;
5. stores the confirmed capsule durably on the domestic hub;
6. lets other clients in the channel receive new capsules through bounded
   short polling;
7. queues a confirmed outgoing capsule locally when the hub is temporarily
   unreachable and retries it when the domestic path returns; and
8. caches only the application shell for repeat opening.

An image is never required and media upload is not part of this milestone.

## 3. Network claim

The authorized claim is:

> A Shongket hub placed on a Bangladesh network reachable through participating
> ISPs/BDIX can carry public text capsules between browser clients on different
> Wi-Fi networks while that domestic path remains operational.

The software path is:

```text
Browser A → ISP A → domestic/BDIX route → Shongket hub
Shongket hub → domestic/BDIX route → ISP B → Browser B
```

This is not communication without all networking. It is not guaranteed to work
when an ISP turns off customer access, domestic routing fails, DNS cannot
resolve the hub, the hub is blocked, or the hub host loses power/connectivity.
The existing nearby local-Wi-Fi mode remains the deeper-outage fallback.

No BDIX reachability, cross-ISP compatibility, censorship resistance,
guaranteed availability or field validation may be claimed until the separate
field gate in §8 is executed.

## 4. Frozen behavior

### 4.1 Capsule request

`POST /api/v1/capsules` accepts one UTF-8 JSON document no larger than 8192
bytes:

```json
{
  "schema": "shongket.bdix.capsule.v1.0",
  "client_id": "client-generated UUID",
  "channel": "DHAKA-RELIEF",
  "message": "Human-confirmed crisis text",
  "location": "Operator-supplied location text",
  "urgency": "normal | important | critical",
  "visibility": "public",
  "human_confirmed": true,
  "public_forwarding_consent": true,
  "expires_in_seconds": 21600
}
```

Frozen limits:

- `client_id`: canonical lowercase UUID string;
- `channel`: 3–32 ASCII characters, `A-Z`, `0-9` and `-`, normalized to
  uppercase;
- `message`: 1–1024 Unicode scalar values after trimming;
- `location`: 1–200 Unicode scalar values after trimming;
- `urgency`: exact enum;
- `visibility`: literal `"public"` only;
- both confirmation values: literal boolean `true`;
- `expires_in_seconds`: one of 3600, 21600 or 86400;
- unknown fields, duplicate JSON keys, non-UTF-8, non-finite numbers and
  malformed types are rejected before persistence.

The server sets `received_at_unix` and `expires_at_unix`. `capsule_id` is a
SHA-256 digest over the canonical accepted request. Repeating the same
`client_id` with identical content is idempotent; reusing it with different
content is rejected.

### 4.2 Feed

`GET /api/v1/capsules?channel=<code>&after=<cursor>&limit=<n>` returns only
unexpired capsules in ascending durable cursor order. `limit` is 1–50. The
response is bounded and includes `next_cursor`.

Short polling is used instead of an unbounded streaming connection. The client
backs off when the hub is unavailable and retains its last cursor.

### 4.3 Storage and resource limits

- SQLite is used from the Python standard library with one short transaction
  per request.
- Expired rows are removed during bounded maintenance.
- Active rows are capped globally and per channel.
- the configured database byte budget is checked before a new insert;
- request body, response count, channel count, request rate and server
  execution time are bounded;
- a limit refusal does not delete an existing unexpired capsule;
- all client input is untrusted and parameterized SQL is mandatory.

### 4.4 Privacy and trust

- The hub accepts **public capsules only**. Private content is refused.
- The channel code is an organizer label, not a password or security boundary.
- No account, phone number, automatic location, contact list, analytics,
  advertising or cloud AI is added.
- The server stores message and location text because serving that public
  capsule is its purpose. Operational logs and diagnostics must not copy
  message or location text.
- A capsule says that a human confirmed the text for publication. It does not
  prove that the event is factually true or that the author has a verified
  identity.
- Transport encryption requires HTTPS at the deployment edge. End-to-end
  encryption is not implemented or claimed.

## 5. Architecture boundary

```text
bdix_hub/
  validation.py   canonical request validation and identity
  store.py        SQLite persistence, expiry, idempotency and caps
  app.py          dependency-free WSGI HTTP/API boundary
  static/         same-origin installable browser client
deploy/bdix/
  requirements.txt
  systemd and reverse-proxy examples
```

The hub consumes the frozen capsule concepts but is a transport/application
adapter. It does not change the M0/M1 protocol core, simulator, Android radio
adapter or iOS Bonjour adapter.

The application is standard-library-only. The production process supervisor
may add one reviewed WSGI server dependency; TLS and static edge controls stay
at the reverse proxy.

## 6. Explicit exclusions

- generic private chat, direct messages, accounts or social profiles;
- private-content storage or forwarding;
- image, audio, video or arbitrary file upload;
- global-Internet replacement or satellite connectivity;
- standards-based mesh, Wi-Fi Direct, Bluetooth or new radio work;
- push notifications or background execution after the browser/app is closed;
- automatic hotspot creation;
- cross-hub federation or store-carry-forward between hubs;
- end-to-end encryption, anonymity or censorship-resistance claims;
- moderation automation, factual verification or AI-generated content;
- message editing and deletion in the first slice;
- GitHub Pages as the production domestic hub; and
- a passing BDIX/cross-ISP field claim without captured field evidence.

## 7. Software acceptance catalogue

- **BH-01 — Cross-client exchange:** two independent clients with different
  simulated source addresses can publish and fetch a capsule through the WSGI
  boundary.
- **BH-02 — Bounded strict schema:** exact-size boundaries pass; oversized,
  malformed, duplicate-key and wrong-type input is refused without mutation.
- **BH-03 — Public confirmation gate:** private, unconfirmed or
  non-consented content is refused before persistence.
- **BH-04 — Durable restart:** accepted capsules and cursors survive closing
  and recreating the application/store.
- **BH-05 — Idempotency and conflict:** identical `client_id` replay returns
  the original capsule once; conflicting replay is refused.
- **BH-06 — Expiry and bounded retention:** expired capsules are never returned
  and cleanup never removes an unexpired row merely to admit a new one.
- **BH-07 — Interruption recovery:** the browser outbox survives reload,
  retries after a failed request and does not create a duplicate.
- **BH-08 — Abuse/resource boundary:** per-address publish rate, global active
  row cap, per-channel cap and database byte budget refuse safely.
- **BH-09 — Content-free operations:** server diagnostics and ordinary
  application logs include codes/counters only, not message or location text.
- **BH-10 — Offline application shell:** all runtime assets are same-origin,
  the shell is service-worker cached, and no global CDN/API is required after
  first load.
- **BH-11 — Deployment readiness:** health endpoint, production WSGI command,
  reverse-proxy/TLS example, backup procedure and environment validation are
  documented and smoke tested.
- **BH-12 — Honest status:** UI and documentation distinguish domestic-hub,
  nearby-only and globally offline states, and make no field claim.

BH-01 through BH-12 are software-testable. They do not prove BDIX reachability.

## 8. Separate field-validation gate

`BDIX_HUB_FIELD_VALIDATION_STATUS: FIELD_VALIDATION_NOT_APPROVED`

Field validation requires:

1. a named host physically located in Bangladesh with a documented
   BDIX/domestic route;
2. two named broadband ISPs on different networks;
3. the production commit and deployment timestamp;
4. HTTPS and domestic DNS resolution plus a documented IP fallback plan;
5. an explicitly controlled test in which global Internet reachability is
   unavailable while the domestic route remains available;
6. bidirectional publish/fetch evidence from both ISPs;
7. interruption and reconnect evidence;
8. latency and ten consecutive cold-run records; and
9. an honest failed result if either ISP cannot reach the host.

Real users, private information or a live emergency are not required for this
gate. Synthetic public fixtures must be used.

## 9. Assumptions and unresolved deployment inputs

Assumptions:

- participating fixed-broadband ISPs continue customer LAN/WAN and domestic
  peering during the tested international outage;
- the hosting provider routes the selected address domestically;
- users learn the channel code and hub address before or during the disruption;
- modern Safari/Chromium can run the same-origin web client.

Inputs still required for deployment:

- a BDIX-connected Bangladesh VPS or hosting account;
- host/IP, SSH user and a secure key-delivery method;
- a domain whose authoritative DNS remains reachable domestically, or a
  documented IP/hosts-file fallback;
- the deployment operator's retention/moderation/legal decision; and
- permission to execute the §8 field test on two named ISP connections.

## 10. Planned files for the approved implementation

- `BDIX_HUB_SCOPE.md`
- `PRODUCT_DECISIONS.md`
- `RESEARCH_LOG.md`
- `SYSTEM_ARCHITECTURE.md`
- `PROTOCOL_SPEC.md`
- `ACCEPTANCE_TESTS.md`
- `README.md`
- `SUBMISSION.md`
- `bdix_hub/**`
- `deploy/bdix/**`
- `tests/test_bdix_hub.py`
- `tests/test_bdix_hub_static.py`
- `.github/workflows/python.yml`

The smallest valid change does not modify Android, iOS, `shongket_core`,
`app/simulator` or the existing GitHub Pages demo.
