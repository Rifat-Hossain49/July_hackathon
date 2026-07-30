# Shongket Product Decisions

## Current status

IMPLEMENTATION_STATUS: APPROVED_FOR_MILESTONE_1

This top-level value records the last approved completed milestone. M0 and
M1 work is governed by it. M2 through M9 work is governed by the exact
per-milestone software authorization ledger below, which references the
reviewed scope-freeze commit.

### Milestone 1 approval record

Milestone 1 implementation is authorised, **strictly within the frozen
M1 scope**.

- The M1 scope was frozen and reviewed in
  [M1_SCOPE_FREEZE.md](./M1_SCOPE_FREEZE.md) and merged to `main`
  before this approval.
- Decisions **D-M1-01 through D-M1-08** and **D-M1-A1 through D-M1-A5**
  were accepted and encoded in `PROTOCOL_SPEC.md`,
  `SYSTEM_ARCHITECTURE.md` and `ACCEPTANCE_TESTS.md`.
- **AT-22 through AT-37** are the approved M1-blocking acceptance
  catalogue. The 125 M0 tests are preserved as the AT-37 regression
  gate.
- Authorised work is limited to the production-quality deterministic
  core: canonical serialization, schema registry and protocol version
  handling, durable crash-safe persistence, migration and rollback,
  richer validation and failure handling, the frozen privacy and
  forwarding rules, and the M1 conformance suite.
- M1 adds **no new product functionality** beyond Milestone 0.

Explicitly **not** authorised by this approval: Android application or
UI, Bluetooth, Wi-Fi Direct, Nearby Connections, any real radio
transport, real offline AI inference, production encryption or
cryptographic identity, Bloom-filter inventory, Reed-Solomon, fountain
codes, RaptorQ, storage eviction, field trials, and all Milestone 2 or
later work.

Approval for Milestone 1 does not authorise Milestone 2 or later work.

### Milestone 0 implementation evidence

Milestone 0 work authorised by the boundary below is implemented in
`app/simulator/` and covered by 125 passing automated tests (0 failed, 0
skipped) across the 18 M0-blocking acceptance IDs. Evidence is recorded
in `ACCEPTANCE_TESTS.md` and `EXPERIMENT_PLAN.md`.

Milestone 1 was subsequently approved and completed. The current status
records that M1 approval. The separate descendant approval record below
governs the software-testable portions of Milestones 2 through 9.

## Implementation approval policy

Implementation approval is milestone-specific.

A global `IMPLEMENTATION_STATUS: APPROVED` value is prohibited.

Valid approval values include:

- `NOT_APPROVED`
- `APPROVED_FOR_MILESTONE_0`
- `APPROVED_FOR_MILESTONE_1`
- per-milestone `APPROVED_FOR_SOFTWARE_IMPLEMENTATION`
- per-milestone `APPROVED_FOR_EVIDENCE_TOOLING_ONLY`
- per-milestone `FIELD_VALIDATION_NOT_APPROVED`

Approval for one milestone or completion level does not authorize any
other milestone or completion level.

## Milestone 0 approval boundary

When Milestone 0 is approved, it authorizes only:

- an executable protocol simulator;
- synthetic deterministic media;
- simulated peers and encounters;
- deterministic priority scheduling;
- fixed-size chunks;
- SHA-256 integrity verification;
- ordinary multi-peer chunk completion;
- simulated interruption and restart recovery;
- lightweight persistence;
- metrics required by EXPERIMENT_PLAN.md.

It does not authorize:

- Android development;
- Nearby Connections;
- Wi-Fi Direct;
- local hotspot networking;
- physical wireless experiments;
- offline AI model integration;
- production cryptographic identity;
- production encryption;
- content-defined chunking;
- Reed-Solomon;
- fountain coding;
- RaptorQ;
- Milestone 1 or later implementation.

## Product thesis

Shongket is a semantic-first, content-centric and disruption-tolerant
multimedia distribution protocol for partial-connectivity crises.

It immediately distributes a compact, human-confirmed semantic capsule,
then progressively distributes previews and original-quality multimedia
through nearby peer-to-peer connections and store-carry-forward relays.

## Locked decisions

### D-001: Not a messenger

Shongket is not a generic Bluetooth, Wi-Fi Direct or mesh chat application.

Its primary networking unit is a content object containing:

1. a semantic capsule;
2. progressive media representations;
3. integrity metadata;
4. independently transferable media fragments.

### D-002: Dual-plane design

Shongket has two logical planes:

- Signal plane: semantic capsules, manifests, priorities and inventories.
- Media plane: thumbnails, keyframes, previews and original media fragments.

### D-003: Human-confirmed intelligence

An offline model may extract:

- event type;
- location;
- urgency suggestion;
- affected people;
- requested action;
- short Bangla summary;
- significant media timestamps.

The user must be able to review and correct these fields before publishing.

The model must not independently declare that a report is true.

### D-004: Original media preservation

AI-generated summaries never replace the source media.

The source media must remain:

- content-addressed;
- integrity-verifiable;
- reconstructable;
- clearly linked to its semantic capsule.

### D-005: Transport-independent core

Protocol and scheduling logic must not depend directly on one transport API.

Initial candidate transports:

- Nearby Connections;
- Wi-Fi Direct;
- local Wi-Fi sockets.

Additional transports may be explored later.

### D-006: Nearby high-rate transfer

Shongket may provide high-rate multimedia transfer between nearby devices.

It must not claim guaranteed broadband or real-time HD delivery between
distant users when no continuous high-bandwidth path exists.

### D-007: Progressive usefulness

The receiver should obtain information in this order:

1. critical semantic capsule;
2. thumbnail or keyframe;
3. short low-resolution preview;
4. standard representation;
5. original-quality representation.

### D-008: Interruption tolerance

A transfer interrupted after a short encounter must still preserve all
verified fragments already received.

The receiver may continue reconstruction using fragments obtained from
other peers.

### D-009: Critical preemption

A newly created critical capsule must be able to preempt a lower-priority
bulk media transfer.

### D-010: Offline core

Core capture, semantic review, storage, synchronization and reconstruction
must not require cloud connectivity.

### D-011: AI fallback

If the local model is unavailable or too slow, the user must be able to
create the semantic capsule through a compact structured form.

### D-012: Honest demonstration

Every feature must be classified as:

- fully implemented;
- experimentally implemented;
- simulated;
- planned.

Simulated behavior must never be presented as real networking behavior.

## Remaining open or manual decisions

- Production signing-key ownership and custody.
- Production signer allow-list / trust root.
- Public app-store publication.
- Final privacy/legal review and any data-retention policy.
- Field-trial site, participants and informed consent.
- Benchmark-selected optional offline model and measured thresholds.
- Device compatibility and performance claims, which require evidence.
- Any future coded-delivery or probabilistic-inventory experiment,
  which requires a separate scope and approval.

### Milestone 1 design decisions — ACCEPTED

These eight decisions are **ACCEPTED** as the design basis for Milestone
1. They were later approved and implemented; all M1 acceptance evidence
is complete. Full rationale and trade-offs are in
[M1_SCOPE_FREEZE.md](./M1_SCOPE_FREEZE.md) §5.

| ID | Decision | Status |
|---|---|---|
| D-M1-01 | `visibility` enum `"public" \| "private"`; legacy `private: true → "private"`, `false`/absent `→ "public"`; v1.0 payloads require a valid enum | ACCEPTED |
| D-M1-02 | Strictly-boolean `forwarding_consent`; private content requires literal `true`; absent/`false` = no consent; truthy strings or integers are malformed | ACCEPTED |
| D-M1-03 | `PeerCapabilities.public_only` = public content only for receive, request, advertise and forward; consent does **not** override it; reject before queueing and transmission with deterministic evidence | ACCEPTED |
| D-M1-04 | Rejection-only under storage pressure; **no eviction in M1**; preserve verified fragments; device eviction effects deferred | ACCEPTED |
| D-M1-05 | `shongket.<object>.v<major>.<minor>`; bare `...v1` is a legacy alias for `...v1.0`; unknown major → `VERSION_UNSUPPORTED`; unknown minor requires explicit registered compatibility | ACCEPTED |
| D-M1-06 | Schema-versioned canonical JSON persistence with payload **and** document checksums, advisory single-writer locking, temp fsync → atomic replace → parent-directory fsync, retained prior snapshot, deterministic migration and rollback | ACCEPTED |
| D-M1-07 | One canonical error enum shared by `ProtocolError`, acknowledgements, events and recovery evidence; every code classified terminal or retryable | ACCEPTED |
| D-M1-08 | M1 core stays **Python**; add a language-neutral protocol specification, canonical serialization rules, golden vectors and conformance tests; **no Kotlin port in M1** | ACCEPTED |

Additional accepted decisions:

| ID | Decision | Status |
|---|---|---|
| D-M1-A1 | `created_at_unix` and `expires_at_unix` as **integer seconds** are canonical for v1.0, superseding the RFC3339 string form | ACCEPTED |
| D-M1-A2 | Serialized-byte limits frozen: capsule 4096, manifest 32768, fragment descriptor 512, transport frame 1048576 | ACCEPTED |
| D-M1-A3 | Complete `hop_limit` and `copy_budget` enforcement in M1; add forwarding-state `hop_count` and `remaining_copy_budget` **without** changing `object_id` or immutable content identity | ACCEPTED |
| D-M1-A4 | AT-22 … AT-37 adopted as the M1-blocking acceptance catalogue | ACCEPTED |
| D-M1-A5 | All 125 M0 tests preserved as the AT-37 regression gate | ACCEPTED |

All three contradictions previously blocking M1 are now reconciled:
the version format (D-M1-05, `PROTOCOL_SPEC.md` §9.1), the timestamp
divergence (D-M1-A1, §9.2) and unenforced `hop_limit` / `copy_budget`
(D-M1-A3, §6). See `M1_SCOPE_FREEZE.md` §4 for the record of each.

### Historical decisions carried from Milestone 0

The following surfaced during Milestone 0 and are retained as history.
The first three are resolved by accepted M1 decisions; the transport
choice is frozen only as a provisional remaining-scope decision:

- **Canonical private/consent field names — RESOLVED by D-M1-01/02.**
  `PROTOCOL_SPEC.md` §8
  requires explicit consent before forwarding private content, and
  AT-16 assumes a "private marker", but no §3 schema names the fields
  that carry either. The M0 simulator uses provisional manifest fields
  `private` and `forwarding_consent`; the names need freezing in the
  schema before M1.
- **`PeerCapabilities.public_only` interaction — RESOLVED by D-M1-03.**
  §3.5 declares this
  peer property, but no document defines how it composes with an
  object's private marker and consent. M0 implements the object-side
  gate only and leaves the interaction unspecified.
- **Device-side storage eviction — RESOLVED as rejection-only for the
  frozen M0–M9 software scope by D-M1-04/D-RS-07.** No eviction is
  silently introduced.
- **Later Android transport choices — PROVISIONAL.** Nearby Connections
  is first to implement behind the adapter, but remains unlocked until
  AT-47 through AT-50 pass on hardware.

## Remaining-scope design ledger — FROZEN AND SOFTWARE-AUTHORISED

`REMAINING_SCOPE.md` and scope-freeze commit
`f85a7c5e1f400b53c8f348284140b488ae677958` freeze the
following design decisions against baseline `80b5fe8`. This section is
the separate descendant approval record. It authorizes only the
software-testable modules and acceptance IDs in the authorization table
below.

| ID | Frozen decision | Scope-freeze status |
|---|---|---|
| D-RS-01 | Android implementation uses Kotlin and Android Gradle | FROZEN |
| D-RS-02 | Python remains canonical; Kotlin proves vector parity | FROZEN |
| D-RS-03 | M2 uses a bounded four-byte-length-prefixed canonical JSON frame over stdio/loopback | FROZEN |
| D-RS-04 | Transport adapters carry bytes/capabilities/liveness and make no policy decision | FROZEN |
| D-RS-05 | Nearby Connections is provisional; hardware gate required before selection claims | FROZEN |
| D-RS-06 | Single-activity Compose, unidirectional state and a platform-permitted background-transfer port | FROZEN |
| D-RS-07 | Android persists the canonical envelope in app-private storage; storage pressure remains rejection-only | FROZEN |
| D-RS-08 | Platform codecs sit behind `MediaPipeline`; source bytes and identity are preserved | FROZEN |
| D-RS-09 | `SemanticExtractor` is optional; manual/unavailable is default and tests use a deterministic double | FROZEN |
| D-RS-10 | Development signing mechanics only; production key custody and trust root are manual | FROZEN |
| D-RS-11 | Platform key storage, app-private data and explicit backup exclusions; no bespoke crypto claim | FROZEN |
| D-RS-12 | Least-privilege, point-of-use permissions; denial is a supported state | FROZEN |
| D-RS-13 | Diagnostics are opt-in, allow-listed and content-free | FROZEN |
| D-RS-14 | Reproducible local release candidate; store deployment and production signing remain manual | FROZEN |

Manual release decisions MRD-01 through MRD-05 cover production signing
custody, the production trust root, public-store deployment, any
personal-data retention, and field-trial participants/consent. They are
not delegated to an implementation agent and do not block the
software-complete candidate.

### Remaining software implementation authorization

- `SOFTWARE_SCOPE_STATUS: APPROVED_FOR_SOFTWARE_IMPLEMENTATION`
- `SOFTWARE_SCOPE_FREEZE_COMMIT: f85a7c5e1f400b53c8f348284140b488ae677958`
- `SOFTWARE_TARGET: SOFTWARE_COMPLETE_RELEASE_CANDIDATE`
- `FIELD_VALIDATION_STATUS: FIELD_VALIDATION_NOT_APPROVED`

### Milestone 3 local-Wi-Fi implementation approval record

- `M3_LOCAL_WIFI_IMPLEMENTATION_STATUS: APPROVED_FOR_MILESTONE_3_LOCAL_WIFI_IMPLEMENTATION`
- `M3_LOCAL_WIFI_SCOPE_FREEZE_COMMIT: 050e1a50ea758dd9dcd7b43791c663941f54f0c2`
- `M3_LOCAL_WIFI_SOFTWARE_ACCEPTANCE: LW-01_THROUGH_LW-09`
- `M3_LOCAL_WIFI_FIELD_VALIDATION_STATUS: FIELD_VALIDATION_NOT_APPROVED`

The product owner explicitly requested nearby-device communication over
Wi-Fi without internet on 2026-07-30. That instruction authorizes the
software implementation frozen in `M3_LOCAL_WIFI_SCOPE.md`: Android
DNS-SD/mDNS discovery and bounded local TCP exchange between phones on the
same Wi-Fi network or a user-enabled hotspot.

This is a milestone-specific implementation approval, not a global approval.
It narrowly permits:

- a concrete local-Wi-Fi adapter behind the frozen transport boundary;
- a human-confirmed, text-only capsule send/receive UI;
- the permissions and foreground lifecycle needed by that adapter;
- bounded schema, integrity, duplicate, timeout and denial handling; and
- JVM, emulator and evidence-tooling verification for LW-01 through LW-09.

It does not authorize marking AT-47 through AT-50 passing. Real-radio
discovery, interruption, OEM compatibility and ten cold runs still require
two named physical devices and captured evidence. It also does not authorize
Wi-Fi Direct, automatic hotspot creation, Bluetooth, Nearby Connections,
background execution after the app closes, media transfer, production
identity/encryption, a locked transport-selection claim or any later field
milestone.

### iOS local-Wi-Fi interoperability approval record

- `IOS_LOCAL_WIFI_IMPLEMENTATION_STATUS: APPROVED_FOR_IOS_LOCAL_WIFI_INTEROPERABILITY`
- `IOS_LOCAL_WIFI_SCOPE_FREEZE_COMMIT: 5d4bf187cfa7cc56a3db64567c2f53fbb77bd500`
- `IOS_LOCAL_WIFI_SOFTWARE_ACCEPTANCE: IOS-LW-01_THROUGH_IOS-LW-10`
- `IOS_LOCAL_WIFI_FIELD_VALIDATION_STATUS: FIELD_VALIDATION_NOT_APPROVED`

The product owner explicitly requested iOS compatibility on 2026-07-30. That
instruction authorizes the software implementation frozen in
`IOS_LOCAL_WIFI_SCOPE.md`: a native iOS 16+ text-only client that uses Bonjour
DNS-SD and bounded local TCP to interoperate with the existing Android app on
the same Wi-Fi network or a user-enabled hotspot.

This is a milestone-specific interoperability approval, not a global
approval. It narrowly permits:

- a transport-independent Swift codec for the frozen version-1 wire format;
- a native Network framework adapter for `_shongket._tcp`;
- a human-confirmed, text-only SwiftUI send/receive interface;
- the local-network privacy declarations and foreground lifecycle required by
  Apple platforms;
- bounded schema, integrity, duplicate, timeout and denial handling;
- shared Android/Swift golden interoperability vectors; and
- macOS Swift tests and unsigned iOS Simulator build evidence for IOS-LW-01
  through IOS-LW-10.

It does not authorize marking the cross-platform physical-device gate
passing. Android-to-iPhone discovery, bidirectional transfer, interruption,
hotspot behavior and ten cold runs still require named physical devices and
captured evidence. It also does not authorize media transfer, Bluetooth,
Multipeer Connectivity, AWDL claims, background execution, production
identity/encryption, production signing, TestFlight, App Store publication or
handling Apple signing secrets in the repository.

### BDIX domestic hub software approval record

- `BDIX_HUB_IMPLEMENTATION_STATUS: APPROVED_FOR_BDIX_DOMESTIC_HUB_SOFTWARE`
- `BDIX_HUB_SCOPE_FREEZE_COMMIT: 3b77dfe367a0e5c1d5b2ca242d6496824e868384`
- `BDIX_HUB_SOFTWARE_ACCEPTANCE: BH-01_THROUGH_BH-12`
- `BDIX_HUB_FIELD_VALIDATION_STATUS: FIELD_VALIDATION_NOT_APPROVED`

The product owner explicitly requested on 2026-07-31 that Shongket reproduce
the Bangladesh domestic-server pattern used during the 2024 global Internet
blackout: users on different Wi-Fi/ISP networks should exchange crisis
information through a Bangladesh-hosted service while domestic ISP/BDIX
routing remains available.

That instruction authorizes the software implementation frozen in
`BDIX_HUB_SCOPE.md`: a dependency-light, text-only, public crisis-capsule hub
and same-origin progressive web client for laptops, Android phones and Apple
mobile devices.

This is a milestone-specific implementation approval, not a global approval.
It narrowly permits:

- a strict public-only capsule API behind a transport/application boundary;
- durable SQLite persistence, expiry, idempotency and bounded resource
  controls;
- a human-confirmed browser interface with a retrying local outbox;
- an HTTPS-installable application shell containing no global runtime
  dependency;
- the reviewed Gunicorn production process dependency and reverse-proxy
  deployment examples; and
- automated local software evidence for BH-01 through BH-12.

It does not authorize private chat, accounts, media upload, factual
verification, end-to-end encryption claims, cloud AI, cross-hub federation,
Bluetooth or other new radio work. It also does not authorize marking
cross-ISP/BDIX reachability as passing. A named Bangladesh host, two named
ISPs, controlled loss of global reachability and captured evidence remain the
separate field gate in `BDIX_HUB_SCOPE.md` §8.

AT-38 through AT-78 are approved as the remaining acceptance
specification. None is implemented or passing at this approval point.
AT-38 through AT-46, AT-51 through AT-54, AT-58 through AT-60, AT-63,
AT-64, AT-66 through AT-73, AT-75 and AT-76 are the 28
software-complete blockers.

| Milestone | Exact authorization | Authorized acceptance IDs | Explicit exclusions |
|---|---|---|---|
| M2 | `APPROVED_FOR_SOFTWARE_IMPLEMENTATION` | AT-38–AT-41 | No Android, radio or field claim |
| M3 | `APPROVED_FOR_SOFTWARE_IMPLEMENTATION`; `FIELD_VALIDATION_NOT_APPROVED` | AT-39, AT-42–AT-46 | AT-47–AT-50; Nearby or other radio-selection claim |
| M4 | `APPROVED_FOR_SOFTWARE_IMPLEMENTATION`; `FIELD_VALIDATION_NOT_APPROVED` | AT-51–AT-54 | AT-55–AT-57; real-device progressive-transfer claim |
| M5 | `APPROVED_FOR_EVIDENCE_TOOLING_ONLY`; `FIELD_VALIDATION_NOT_APPROVED` | Harness/evidence preparation for AT-55–AT-57 | Passing AT-55–AT-57; real-device or real-radio completion claim |
| M6 | `APPROVED_FOR_SOFTWARE_IMPLEMENTATION`; `FIELD_VALIDATION_NOT_APPROVED` | AT-58–AT-60 | Passing AT-61–AT-62; bundling a production model without a separate dependency decision |
| M7 | `APPROVED_FOR_SOFTWARE_IMPLEMENTATION`; `FIELD_VALIDATION_NOT_APPROVED` | AT-63–AT-64, AT-66–AT-73 | Passing AT-65; production keys or trust-root decisions |
| M8 | `APPROVED_FOR_EVIDENCE_TOOLING_ONLY`; `FIELD_VALIDATION_NOT_APPROVED` | Benchmark harness and evidence schema for AT-74 | Measured device results or a passing AT-74 claim |
| M9 | `APPROVED_FOR_SOFTWARE_IMPLEMENTATION`; `FIELD_VALIDATION_NOT_APPROVED` | AT-75–AT-76 plus evidence-package assembly | Passing AT-77–AT-78; public-store deployment, production signing, or field-trial approval |

This authorization permits the nine implementation slices in
`REMAINING_SCOPE.md` only to the extent covered by the table. Physical
device, real-radio and field-only success evidence remains a manual
completion level. Production key custody, production trust roots,
public-store deployment, personal-data retention policy, and field-trial
participants/consent remain MRD-01 through MRD-05 and are not delegated
to an implementation agent.
