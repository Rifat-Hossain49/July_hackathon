# Shongket — Remaining Project Scope Freeze

**Status:** SCOPE_FROZEN; APPROVED_FOR_SOFTWARE_IMPLEMENTATION BY
DESCENDANT RECORD. This document freezes the remaining scope, decisions,
architecture and acceptance catalogue. The separate descendant approval
in `PRODUCT_DECISIONS.md` references this freeze as commit `f85a7c5` and
authorizes only the software/evidence-tooling subset listed there.
Field validation remains unapproved.

Baseline this freeze was written against:

- `main` at `80b5fe8` (Milestone 1 merge, PR #5);
- Milestone 0 COMPLETE, Milestone 1 COMPLETE;
- `IMPLEMENTATION_STATUS: APPROVED_FOR_MILESTONE_1`;
- AT-01 … AT-37 defined, all M0/M1-blocking tests passing;
- **367 passed, 0 failed, 0 skipped**;
- M0 CLI `D5AC79B1…2CB4DF` and metrics `E10E11D4…891B28` unchanged;
- Milestone 2 and later not implemented.

---

## 1. Two completion levels

The remaining project is deliberately split, because one half can be
finished and verified on this machine and the other cannot.

### A. SOFTWARE-COMPLETE RELEASE CANDIDATE

Everything implementable and verifiable **without physical field
access**: all protocol code, adapters, the Android application and its
UI, local persistence integration, the media pipeline, the offline-model
interface with a deterministic test double, privacy and consent flows,
diagnostics, packaging, and every automated, emulator and two-process
test.

A software-complete build is a *candidate*. It asserts nothing about
real radios, real devices or real crises.

### B. FIELD-VALIDATED RELEASE

Additionally requires physical devices, real radios, environmental
testing, production key handling and field-trial evidence. **B can never
be claimed from simulations, emulators or mocked radios.**

The implementation prompts that follow this document target **A only**.

### What remains manual for B

| Requirement | Why it cannot be automated here |
|---|---|
| Real-radio discovery, pairing, transfer | Requires physical phones and radios |
| Vendor/OEM compatibility matrix | Requires the actual demo handsets |
| Transport smoke-test gate (7 criteria, `RESEARCH_LOG.md`) | Explicitly a real-device gate |
| Three-peer completion on real hardware | Requires ≥ 3 physical devices |
| Battery and thermal behaviour | Requires real hardware under load |
| Throughput, latency, energy measurements | Simulator has no wall-clock or radio |
| Bangla model quality on device profiles | Requires the selected model on target hardware |
| Production signing keys and store deployment | Key ownership is the user's decision |
| Field trial in a partial-connectivity environment | Requires people, place and time |

---

## 2. Remaining milestone freeze

Existing numbering is preserved. No milestone is consolidated: no
canonical document authorises consolidation.

| M | Objective (frozen) | Prereq | Completion gate | Level |
|---|---|---|---|---|
| **M2** | Run the M1 core across two OS processes on a developer machine | M1 | AT-38…AT-41 pass; M1 suite passes in two-process mode | **A** |
| **M3** | Connect the M1 core to a real Android transport behind an adapter | M2 | AT-42…AT-46 pass (A); AT-47…AT-50 pass on hardware (B) | A + **B** |
| **M4** | Progressive representation delivery in real transfers | M3 | AT-51…AT-54 pass (A); AT-55 on hardware (B) | A + **B** |
| **M5** | Multi-peer completion from ≥ 3 physical peers | M4 | AT-56, AT-57 on hardware | **B** |
| **M6** | Offline semantic extraction with manual fallback | M4 software gate; M5 is not required for model-independent work | AT-58…AT-60 pass (A); AT-61, AT-62 measured on hardware before model claims (B) | A + **B** |
| **M7** | Integration and resilience | M6 | AT-63…AT-73 (mixed) | A + **B** |
| **M8** | Benchmarking: fill result tables with measured numbers | M7 | AT-74 on hardware | **B** |
| **M9** | Demo and public release | M8 | AT-75, AT-76 (A); AT-77, AT-78 (B) | A + **B** |

Exclusions, fallbacks and rollback boundaries remain exactly as written
in `MILESTONES.md`; this freeze does not relax any of them. Coded
delivery (Reed-Solomon, fountain, RaptorQ) remains outside M0–M9.

### Software-completable subset

**M2 fully**, and the software halves of **M3, M4, M6, M7, M9**. M5 and
M8 are inherently field milestones and contribute no software-complete
work beyond what M4 and M7 already deliver.

---

## 3. Contradictions found and resolved

| # | Finding | Resolution |
|---|---|---|
| R-1 | `MILESTONES.md` cites `AT-PROG-1..3`, `AT-MP-1..5`, `AT-AI-1..4`; none is defined in `ACCEPTANCE_TESTS.md`, which records that legacy identifiers were removed | Mapped to canonical IDs: AT-PROG → AT-51…AT-55; AT-MP → AT-56, AT-57; AT-AI → AT-58…AT-62. `MILESTONES.md` updated |
| R-2 | M3 says "an APK-shaped artifact (**no `app/` change in this plan**)", but `app/` is the M0 simulator package | `app/simulator` is the M0 harness and stays frozen. Android lives in a new top-level `android/` tree; the phrase is read as "do not disturb the existing `app/` package" |
| R-3 | `MEDIA_PIPELINE.md` §6 says M1 should "begin transition … using `android.media`" | Already resolved by D-M1-08: interface shaping only. Media platform work is M4, not M1 |
| R-4 | No milestone owns security controls, diagnostics or packaging explicitly | Assigned: security/privacy → M7; diagnostics → M7; packaging/release → M9 |
| R-5 | No acceptance coverage existed for process boundaries, adapters, UI, permissions or release | AT-38 … AT-78 added |

---

## 4. Decisions resolved (D-RS-01 … D-RS-14)

Resolved from canonical documents, accepted decisions, and safety-first
deterministic defaults. Each is **ACCEPTED FOR THE AUTHORIZED SOFTWARE
SUBSET** by the descendant approval record.

### D-RS-01 — Android implementation language: Kotlin
- **Alternatives:** Kotlin; Java; Python-on-Android (Chaquopy/BeeWare).
- **Selected:** Kotlin, with the Android Gradle build.
- **Rationale:** `MILESTONES.md` M3 targets a real Android artifact;
  Kotlin is the first-class Android language. Python-on-Android would
  drag an interpreter into a crisis app and complicate permissions and
  background limits. D-M1-08 already anticipated a later port.
- **Consequences:** a second implementation of the protocol core exists.
  It is bound by D-RS-02.
- **Affects:** M3–M9. **Rollback:** the Python core remains canonical
  and runnable; deleting `android/` restores today's state.

### D-RS-02 — Python core stays canonical; Kotlin proves conformance
- **Alternatives:** port and retire Python; keep Python canonical; dual
  canonical.
- **Selected:** `shongket_core` (Python) remains the canonical
  behavioural reference. The Kotlin core is an implementation that must
  reproduce every committed golden vector byte-for-byte.
- **Rationale:** the vectors already exist and are independently
  computed; conformance-by-vector is checkable, "we ported it carefully"
  is not.
- **Consequences:** every new protocol behaviour must land in Python
  first, with vectors, then Kotlin.
- **Affects:** M3–M9. **Rollback:** revert the Kotlin module.

### D-RS-03 — Two-process transport: length-prefixed frames over stdio/loopback
- **Alternatives:** stdio pipes; TCP loopback; UNIX/named sockets; gRPC.
- **Selected:** a single `FrameCodec` (4-byte big-endian length prefix +
  canonical JSON body) carried over either stdio pipes or TCP loopback,
  selected by configuration.
- **Rationale:** no third-party dependency, works identically on Windows
  and POSIX, and the framing is already implied by the M0 envelope.
  gRPC would add a large dependency and a schema system that competes
  with the canonical one.
- **Consequences:** frame size bounded by the canonical 1 048 576-byte
  transport limit.
- **Affects:** M2, M3. **Rollback:** revert to in-process harness.

### D-RS-04 — Transport adapters are dumb pipes
- **Selected:** adapters move bytes and report capability and liveness.
  They never evaluate expiry, consent, hop/copy, visibility or
  integrity.
- **Rationale:** `PROTOCOL_SPEC.md` §6 makes admission a core
  responsibility; duplicating it in each radio adapter would guarantee
  divergence.
- **Affects:** M2–M7. **Rollback:** none needed; this is a constraint.

### D-RS-05 — First real transport: Nearby Connections, provisional
- **Selected:** Nearby Connections as the first adapter, **provisional**
  until the 7-criterion smoke-test gate passes on hardware. Wi-Fi Direct
  and local-hotspot adapters are written against the same interface as
  alternates.
- **Rationale:** DR-ARCH-04 and `RESEARCH_LOG.md` already name it
  provisional. The gate is a real-device gate and cannot be pre-passed.
- **Consequences:** software-complete status must **not** claim any
  transport is locked.
- **Affects:** M3. **Rollback:** swap adapters; the core is unaffected.

### D-RS-06 — Android architecture: single-activity, unidirectional state
- **Selected:** one activity, Compose UI, unidirectional data flow, a
  repository layer over the core, and a `BackgroundTransferCoordinator`
  that selects the platform-permitted user-visible transfer mechanism
  for the target API. A `connectedDevice` foreground service is the
  provisional direct-device mechanism, not a promise of indefinite
  execution. No fragments-as-navigation, no MVP.
- **Rationale:** smallest structure that satisfies background transfer,
  lifecycle recovery and testability; state is deterministic and
  snapshot-testable.
- **Affects:** M3–M9. **Rollback:** UI layer is replaceable without
  touching the core.

### D-RS-07 — Persistence on Android: the canonical file envelope
- **Alternatives:** Room/SQLite; DataStore; the existing snapshot file.
- **Selected:** reuse the canonical snapshot envelope and its atomic
  write discipline, stored in app-private storage. SQLite is not
  introduced.
- **Rationale:** the envelope, checksums, migration and rollback are
  already specified, implemented and tested. A second storage model
  would need its own migration story and would break vector parity.
- **Consequences:** Android must implement the same
  temp→fsync→replace→dir-fsync sequence, honouring the recorded
  `parent_dir_sync` outcome.
- **Affects:** M3–M7. **Rollback:** revert the adapter.

### D-RS-08 — Media: platform codecs behind a `MediaPipeline` interface
- **Selected:** representation building uses platform codecs on Android
  and a deterministic synthetic pipeline in tests. Chunking, hashing and
  identity stay in the core.
- **Rationale:** `MEDIA_PIPELINE.md` already specifies fixed-size
  chunking and SHA-256; only encoding is platform-specific.
- **Consequences:** a representation that cannot be produced is reported
  as unavailable, never silently omitted.
- **Affects:** M4. **Rollback:** thumbnail-only delivery.

### D-RS-09 — Offline model: interface first, model optional
- **Selected:** a `SemanticExtractor` interface with three
implementations — `Unavailable` (default), `TestDouble`
(deterministic, used by all automated tests) and a separately packaged,
benchmark-selected real runtime added at M6. No model is selected or
bundled by this freeze, and no model is downloaded during any automated
test. The app is fully usable with no model.
- **Rationale:** D-011 and AT-15 already require the manual form to
  work; the model is an accelerator, not a dependency.
- **Consequences:** model quality is evaluated separately from protocol
  acceptance and never gates a protocol test.
- **Affects:** M6. **Rollback:** `Unavailable` is the default.

### D-RS-10 — Identity: development keys only until a manual release gate
- **Selected:** Ed25519 signing behind a `KeyStore` interface. Automated
  tests use committed **development test keys** clearly marked as such.
  Production key generation, custody and the trust root are a
  **MANUAL_RELEASE_DECISION**.
- **Rationale:** signature verification is a documented protocol
  behaviour (`SIGNATURE_INVALID`), but key ownership is irreversible and
  for the user to decide.
- **Consequences:** software-complete includes signing *mechanics*, not
  a production trust root.
- **Affects:** M7, M9.

### D-RS-11 — Data at rest: platform key storage, no bespoke crypto
- **Selected:** Android Keystore via an abstraction; app-private storage;
  explicit backup/data-extraction exclusion; no secrets in logs or
  diagnostics. The manifest sets `allowBackup=false`, but the Android
  version/OEM-specific device-transfer behaviour is verified rather
  than assumed.
- **Rationale:** AGENTS.md forbids committing secrets and D-012 forbids
  unaudited security claims. Inventing a cipher would be worse than
  using the platform's.
- **Consequences:** no claim of audited cryptographic security is made
  anywhere.
- **Affects:** M7.

### D-RS-12 — Permissions: least privilege, refusal is a supported state
- **Selected:** request the minimum set, at point of use, with an
  in-app explanation. Every refusal path leads to a working, degraded
  app — never a crash or a dead end.
- **Rationale:** AT-13 already requires "feature disabled; reason
  shown"; R-04 flags permission complexity as a high risk.
- **Affects:** M3, M7.

### D-RS-13 — Diagnostics: structured, opt-in, content-free
- **Selected:** the existing deterministic evidence log is the
  diagnostic format. Export is explicit and user-initiated, contains
  identifiers, counters, codes and ticks, and **never** capsule text,
  media bytes, location text or peer-identifying data.
- **Rationale:** AGENTS.md forbids logging private content by default.
- **Affects:** M7, M9.

### D-RS-14 — Release: reproducible debug builds now, store deployment manual
- **Selected:** a reproducible, locally verifiable build with a
  development signing config is part of software-complete. Public store
  deployment and production signing are a
  **MANUAL_RELEASE_DECISION**.
- **Affects:** M9.

### Manual release decisions (deliberately unresolved)

| ID | Decision | Why not resolved here |
|---|---|---|
| MRD-01 | Production signing key ownership and custody | Irreversible; requires the user's key material |
| MRD-02 | Cryptographic trust root and signer allow-list | Irreversible trust decision |
| MRD-03 | Public app-store deployment | Legal, account and policy obligations |
| MRD-04 | Any personal-data collection or retention | Privacy/legal; current design collects none |
| MRD-05 | Field-trial site, participants and consent | Requires people and place |

None of these blocks software-complete work.

---

## 5. Architecture freeze

```
shongket_core/            Python — CANONICAL behavioural reference
  errors schema version codec store persist migrate policy evidence
  testdata/               committed language-neutral golden vectors

app/simulator/            M0 harness — FROZEN, not modified again

adapters/
  process/                M2: FrameCodec, stdio + loopback endpoints
  transport_sim/          deterministic in-memory transport for tests

android/                  Kotlin (M3+)
  core-conformance/       Kotlin port; proves parity against the vectors
  data-persistence/       canonical envelope on app-private storage
  data-transport/         Nearby / Wi-Fi Direct / hotspot adapters
  media/                  capture, representations, playback
  semantic/               SemanticExtractor: Unavailable | TestDouble | real
  security/               KeyStore abstraction, signing, consent gate
  ui/                     single activity, Compose, unidirectional state
  diagnostics/            evidence export
  app/                    assembly, permissions, foreground service
```

Invariants, enforced by AT-44 and AT-39:

1. `shongket_core` imports nothing from `adapters/`, `android/` or any
   third party.
2. Adapters depend on the core; the core never depends on an adapter.
3. Every protocol decision lives in the core. Adapters carry bytes.
4. The Kotlin core is validated only against committed vectors.
5. `app/simulator` is not modified again.

---

## 6. Transport abstraction (frozen)

```
discover()                 -> stream of PeerRef
capabilities(PeerRef)      -> PeerCapability (incl. public_only, max_payload)
connect(PeerRef)           -> Session
Session.send(Frame)        -> Ack | TransportError
Session.receive()          -> Frame | TransportError
Session.close()
Session.events()           -> connected | progress | interrupted | closed
Adapter.capability_report()-> name, transports, max_payload, reliability
```

Adapters **must not** decide admission, consent, expiry, hop/copy or
integrity. Duplicate suppression and integrity verification are core
responsibilities performed on received frames; the adapter only reports
what arrived.

| Transport | Status for software-complete |
|---|---|
| In-memory simulated | **Required** |
| Two-process stdio / loopback | **Required** |
| Nearby Connections | Adapter required; behaviour real-device-only |
| Wi-Fi Direct | Optional alternate adapter |
| Local hotspot | Experimental alternate |
| BLE-only | Not in scope for M0–M9 |

Emulator success never counts as real-radio evidence.

---

## 7. Media and offline AI (frozen)

**Media.** Source types: photo, short video, audio, text, document.
Representations `thumb`, `preview`, `standard`, `original` exactly as
`MEDIA_PIPELINE.md` defines. Chunking stays `FixedSize(64 KB)` in the
core; only encoding is platform-side. The original source is preserved
and its hash is the `object_id`; derived media never overwrites it. A
representation that cannot be produced is reported unavailable. Storage
accounting reuses the M1 budget, which remains **rejection-only** — no
eviction.

**Offline AI.** `SemanticExtractor` with `Unavailable` as the default.
Automated tests use only the deterministic `TestDouble`. No model is
downloaded during tests. Human confirmation remains mandatory (D-003).
Generated text is a *suggestion* and can never replace source evidence
or the original media. Model quality is measured by
`MODEL_EVALUATION_PLAN.md` and never gates a protocol acceptance test.

---

## 8. Security and privacy scope

Bounded threat model for the remaining software. "SW" = required for
software-complete; "FIELD" = verifiable only on hardware.

| Threat | Control | Gate |
|---|---|---|
| Malicious payloads | Canonical validation, size limits before parse | SW (AT-67) |
| Forged metadata | Signature verification with dev keys | SW (AT-71) |
| Tampered fragments | Per-fragment SHA-256 | SW (already AT-10/AT-28) |
| Replay | Expiry + content-ID uniqueness | SW (AT-72) |
| Duplicate flooding | Per-peer caps, dedup, rate limit | SW (AT-72) |
| Resource exhaustion | Frame and payload caps, storage budget | SW (AT-67) |
| Unauthorised forwarding | Six-clause admission rule | SW (AT-35, AT-68) |
| Private-content disclosure | Consent gate + explicit UX | SW (AT-68) |
| Transport impersonation | Signed manifests; adapter carries no trust | SW (AT-71) |
| Local data exposure | App-private storage, platform key storage | SW (AT-69) |
| Backup leakage | `allowBackup=false` | SW (AT-69) |
| Sensitive content in logs | Content-free evidence; opt-in export | SW (AT-70) |
| Permission misuse | Least privilege, point-of-use requests | SW (AT-66) |
| Insecure key storage | Keystore abstraction; no embedded secrets | SW (AT-69) |
| Downgrade attempts | Unknown/unregistered version refused | SW (AT-73) |

**Never committed:** production keys, signing certificates, passwords,
tokens, personal datasets. Development test keys are committed only
under an unmistakable `testdata/dev-keys/` path and are unusable for
release. No claim of audited cryptographic security is made.

---

## 9. Implementation program

The next implementation branch may complete the eight software slices
below as separate auditable commits, followed by a ninth evidence-only
package. Hardware is never required to merge a software slice.

### Slice 1 — M2 process boundary and deterministic transport framework

- **Requirements/modules:** frame codec, stdio/loopback endpoints and
  deterministic simulated adapter in `adapters/process/` and
  `adapters/transport_sim/`.
- **Acceptance IDs:** AT-38 through AT-44.
- **Prerequisite/order:** M1; build frame validation before endpoints,
  then interruption and adapter conformance.
- **Tests/evidence:** local and two-process suites, process transcripts,
  vector hashes, missing-only resume lists; no hardware.
- **Commit:** `feat: add deterministic process transport boundary`.
- **Rollback:** revert the slice; M1 remains the runnable baseline.

### Slice 2 — Android/Kotlin foundation and conformance

- **Requirements/modules:** Android Gradle skeleton,
  `android/core-conformance/`, language-neutral vector loader and
  Kotlin codec; no transport policy.
- **Acceptance IDs:** Kotlin portion of AT-39, plus Android build
  preconditions for AT-42 and AT-45.
- **Prerequisite/order:** Slice 1; make vector parity pass before any UI
  or platform adapter.
- **Tests/evidence:** JVM vector suite, emulator smoke build and
  per-language SHA-256 table; no hardware.
- **Commit:** `feat: add Android foundation and Kotlin conformance`.
- **Rollback:** remove `android/`; Python remains canonical.

### Slice 3 — Android state, persistence and lifecycle

- **Requirements/modules:** `android/data-persistence/`, repository
  layer, app-private canonical envelope, saved UI identifiers and
  lifecycle restart handling.
- **Acceptance IDs:** AT-45, AT-63, AT-64.
- **Prerequisite/order:** Slice 2; persistence before lifecycle/UI
  restoration.
- **Tests/evidence:** JVM/emulator crash, restart and storage-pressure
  transcripts; no hardware.
- **Commit:** `feat: add Android durable state and lifecycle recovery`.
- **Rollback:** revert the adapter; no canonical store bytes are
  rewritten by rollback.

### Slice 4 — Transport adapters, capability negotiation and permissions

- **Requirements/modules:** `android/data-transport/`,
  `BackgroundTransferCoordinator`, simulated binding, provisional
  Nearby adapter, capability negotiation and denial UX.
- **Acceptance IDs:** software portions of AT-42, AT-43, AT-46;
  AT-47 through AT-50 remain evidence-only.
- **Prerequisite/order:** Slices 2 and 3; simulated conformance before
  compiling any radio adapter.
- **Tests/evidence:** adapter event parity, emulator permission matrix
  and explicit unsupported states; no radio success claim.
- **Commit:** `feat: add Android transport adapters and permission gates`.
- **Rollback:** disable or remove a concrete adapter; keep the shared
  contract and simulated adapter.

### Slice 5 — Progressive media capture, representation and playback

- **Requirements/modules:** `android/media/`, source preservation,
  availability metadata, deterministic test media, capture/load ports
  and progressive UI state.
- **Acceptance IDs:** AT-51 through AT-54; AT-55 remains evidence-only.
- **Prerequisite/order:** Slices 3 and 4; source preservation and
  manifests before playback.
- **Tests/evidence:** local fixture hashes, emulator codec capability
  matrix, ordered delivery and unavailable-state snapshots.
- **Commit:** `feat: add source-preserving progressive media pipeline`.
- **Rollback:** thumbnail-only fallback; never delete or replace the
  original source.

### Slice 6 — Semantic capsule UI and optional offline-model interface

- **Requirements/modules:** `android/semantic/`, manual structured form,
  human confirmation, `Unavailable` and deterministic `TestDouble`;
  real runtime remains an optional package.
- **Acceptance IDs:** AT-58 through AT-60; AT-61 and AT-62 remain
  device/model evidence.
- **Prerequisite/order:** Slice 5; manual path first, test double second.
- **Tests/evidence:** offline/no-download assertion, deterministic
  suggestions, manual publish transcript and source-link hashes.
- **Commit:** `feat: add manual semantic flow and model interface`.
- **Rollback:** select `Unavailable`; the app stays usable.

### Slice 7 — Privacy, security, resilience and diagnostics

- **Requirements/modules:** `android/security/`, `android/diagnostics/`,
  consent UX, key-storage abstraction, malformed-input and flood caps,
  denied-permission integration and redacted export.
- **Acceptance IDs:** AT-66 through AT-73; AT-65 remains device evidence.
- **Prerequisite/order:** Slices 3 through 6; policy wiring before UI
  evidence and diagnostic export.
- **Tests/evidence:** local/emulator refusal matrices, repository secret
  scan, storage/backup inspection and field-level export scan.
- **Commit:** `feat: integrate privacy security and redacted diagnostics`.
- **Rollback:** revert the integration slice; never weaken a gate to
  retain a feature.

### Slice 8 — Packaging and software release candidate

- **Requirements/modules:** build configuration, install/upgrade
  fixtures, reproducibility tooling and assembled application.
- **Acceptance IDs:** AT-67, AT-75 and AT-76 plus the full
  software-complete blocker set.
- **Prerequisite/order:** Slices 1 through 7; clean-build and upgrade
  evidence last.
- **Tests/evidence:** full Python/JVM/emulator regression, two build
  hashes, install/upgrade inventories and documentation audit.
- **Commit:** `build: assemble Shongket software release candidate`.
- **Rollback:** keep the last passing slice; do not publish the
  candidate.

### Slice 9 — Device and field evidence package only

- **Requirements/modules:** scripts, schemas and checklists for AT-47
  through AT-50, AT-55 through AT-57, AT-61, AT-62, AT-65, AT-74,
  AT-77 and AT-78.
- **Prerequisite/order:** Slice 8. It may prepare evidence capture but
  cannot execute or mark a hardware test passing here.
- **Tests/evidence:** validate script determinism and empty evidence
  schemas locally; physical execution remains manual.
- **Commit:** `test: add device and field evidence package`.
- **Rollback:** remove the package; no product behaviour changes.
- **Hardware:** required to fill evidence, never to create the package.

Every slice runs focused acceptance tests, the full regression and an
internal audit before commit. `shongket_core` remains canonical;
protocol changes, if later required, land there with new vectors before
Kotlin. `app/simulator` is frozen. No model download occurs in tests,
and no secret, production key or private dataset is committed.

---

## 10. Approval checklist

- [x] Scope-freeze commit created before approval
- [x] Remaining milestone scopes frozen (§2)
- [x] Contradictions resolved (§3)
- [x] D-RS-01 … D-RS-14 frozen for approval (§4)
- [x] MRD-01 … MRD-05 acknowledged as manual gates (§4)
- [x] AT-38 … AT-78 added to `ACCEPTANCE_TESTS.md`
- [x] Per-milestone approval recorded for the software-complete subset
- [x] Field milestones remain unapproved for completion claims

Implementation beyond Milestone 1 is authorized only within the exact
per-milestone ledger in `PRODUCT_DECISIONS.md`. Device, radio and field
success claims remain unauthorized.
