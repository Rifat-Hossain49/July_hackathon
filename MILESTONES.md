# Shongket — Milestones (Draft 1)

Implementation approval status is **tracked per milestone and completion
level**. M0 and M1 are complete. Scope-freeze commit `f85a7c5` was
reviewed before the separate software authorization for M2 through M9.

Per `PRODUCT_DECISIONS.md`: `IMPLEMENTATION_STATUS: APPROVED_FOR_MILESTONE_1`.
The remaining-scope ledger separately records exact software and
evidence-tooling authorization.

Approval is never cumulative by implication: approval for one milestone
does not authorise any later milestone's work.

---

## Milestone 0 — Executable protocol simulator

**Status:** APPROVED_FOR_MILESTONE_0. Simulator implementation and
automated acceptance evidence are COMPLETE.

Scope:

- simulated peers;
- simulated encounters;
- synthetic media;
- deterministic scheduler;
- fixed-size chunks;
- SHA-256 verification;
- ordinary multi-peer completion;
- simulated restart recovery;
- metrics harness.

This milestone does not implement coded reconstruction.

- **Objective:** validate the central protocol claim in an
  executable, end-to-end simulator.
- **Why:** isolate protocol correctness from radio / Android risk.
- **Dependencies:** `SYSTEM_ARCHITECTURE.md`, `PROTOCOL_SPEC.md`,
  `MEDIA_PIPELINE.md`, `EXPERIMENT_PLAN.md`, `ACCEPTANCE_TESTS.md`
  approved.
- **Deliverables:**
  - executable simulator harness with single-process simulated peers
  - fixed-size fragmentation strategy implementation
  - SHA-256 per chunk + per representation
  - deterministic scheduler
  - deterministic explicit fragment inventory
  - empty result tables fed by harness logs
- **Acceptance criteria (all required):**
  1. Semantic capsule always scheduled before bulk media for the same
     object.
  2. Critical capsule preempts in-progress bulk transfer within a
     measurable latency.
  3. Preempted bulk transfer resumes after critical delivery.
  4. Partial transfer progress survives a simulated restart.
  5. Receiver completes an object using fragments from ≥ 2 peers.
  6. Duplicate chunks are not stored twice.
  7. Corrupted chunks are rejected without halting.
  8. Reconstructed representation hash equals manifest hash.
  9. Expired content is not forwarded.
  10. All metrics in `EXPERIMENT_PLAN.md` are produced by the harness,
      not invented.
- **Tests:** mapped 1:1 to `ACCEPTANCE_TESTS.md`.
- **Explicitly excluded:** Android, real radios, offline AI runtime,
  production encryption, advanced routing, RaptorQ / any erasure
  coding, utility-based forwarding.
- **Fallback:** if M0 cannot demonstrate preemption or reconstruction,
  return to architecture revision before M1.
- **Rollback condition:** M0 docs and harness can be reverted to
  Draft 1 without breaking planning artifacts.
- **Estimated complexity:** S (small).
- **Primary risks:** overconfidence in simulation; missing edge cases.
- **Implementation approval status:** `IMPLEMENTATION_STATUS: APPROVED_FOR_MILESTONE_0`.
- **M0 simulator implementation:** COMPLETE (`app/simulator/`).
- **M0 automated acceptance evidence:** COMPLETE — 18 of 18 M0-blocking
  acceptance IDs mapped to test modules; 125 automated tests pass, 0
  failed, 0 skipped. See the evidence table in `ACCEPTANCE_TESTS.md` and
  the measured results in `EXPERIMENT_PLAN.md`.
- **Real-device implementation:** NOT STARTED — a later milestone. M0
  demonstrates simulated protocol behaviour between in-process peers
  only, and asserts nothing about radios, Android or field performance.

---

## Milestone 1 — Production-quality deterministic core

**Status:** APPROVED_FOR_MILESTONE_1 and COMPLETE.

Stabilize the protocol proven in Milestone 0.

This milestone adds engineering quality, robust persistence and stable
interfaces, but does not add Android transport or coded delivery.

- **Objective:** harden M0 into a production-quality core suitable
  for Android integration in later milestones.
- **Why:** M0 is a prototype-quality proof; M1 is the real
  implementation backbone.
- **Dependencies:** M0 success criteria all met.
- **Deliverables:**
  - stable schemas with explicit versioning
  - robust persistence (durable, crash-safe, schema-versioned)
  - explicit failure handling
  - protocol conformance test suite
- **Acceptance criteria:**
  - all M0 acceptance tests pass
  - additional M1 conformance tests pass
  - persistence layer survives crash and continues in-progress
    transfers
- **Tests:** expanded conformance suite.
- **Explicitly excluded:** new product features vs. M0; AI extraction;
  Android-specific UI.
- **Fallback:** if M1 rejects a M0 invariant, return to architecture.
- **Rollback condition:** M2 cannot begin without M1 deliverables.
- **Estimated complexity:** M.
- **Primary risks:** scope creep; premature optimization.
- **Implementation approval status:** `IMPLEMENTATION_STATUS: APPROVED_FOR_MILESTONE_1`.
- **Approval record:** the frozen M1 scope was reviewed and merged
  before approval; D-M1-01 … D-M1-08 and D-M1-A1 … D-M1-A5 are
  accepted; AT-22 … AT-37 are the approved M1-blocking catalogue; the
  125 M0 tests are preserved as the AT-37 regression gate. Authorised
  work is limited to the production-quality deterministic core. Android,
  radios, offline AI inference, production security, eviction and all
  M2+ work remain unauthorised. Approval for M1 does not authorise M2 or
  later. See `PRODUCT_DECISIONS.md` § Milestone 1 approval record.
- **Implementation state:** COMPLETE. All five slices are implemented in
  `shongket_core/`; AT-22 through AT-37 pass. 242 M1 tests plus the 125
  M0 regression tests — 367 total, 0 failed, 0 skipped.
  - Slice 1 — canonical serialization, schema registry, version handling
    (AT-22, AT-23, AT-24).
  - Slice 2 — durable crash-safe persistence and recovery
    (AT-26, AT-27, AT-28, AT-30, AT-31).
  - Slice 3 — deterministic migration, rollback, schema upgrade
    (AT-25, AT-29, AT-36).
  - Slice 4 — policy, privacy, `public_only`, hop/copy, error taxonomy
    (AT-32, AT-33, AT-34, AT-35).
  - Slice 5 — conformance vectors, core isolation, M0 regression gate
    (AT-37).
- **Completion boundary:** M1 delivers a deterministic, platform-neutral,
  standard-library-only protocol core. It adds no product behaviour
  beyond M0 and asserts nothing about Android, radios, offline AI,
  production security, storage eviction or real-device performance.
  `IMPLEMENTATION_STATUS` remains `APPROVED_FOR_MILESTONE_1`; Milestone 2
  is neither approved nor started.
- **Scope freeze:** scope, architecture, acceptance catalogue and
  implementation slices are recorded in
  [M1_SCOPE_FREEZE.md](./M1_SCOPE_FREEZE.md). All thirteen design
  decisions (D-M1-01 … D-M1-08 and D-M1-A1 … D-M1-A5) are **ACCEPTED**
  and encoded in `PROTOCOL_SPEC.md`, `SYSTEM_ARCHITECTURE.md` and
  `ACCEPTANCE_TESTS.md`. AT-22 … AT-37 are the M1-blocking catalogue.
- **Accepted M1 design basis:** `visibility` enum and strict-boolean
  `forwarding_consent`; `public_only` peers handle public content only
  and consent does not override it; rejection-only under storage
  pressure with no eviction; `shongket.<object>.v<major>.<minor>`
  versioning with `…v1` as a legacy alias; durable checksummed
  persistence with atomic replace, parent-directory fsync and
  deterministic migration/rollback; one canonical terminal/retryable
  error enum; core stays Python with golden vectors and conformance
  tests; integer-second timestamps; frozen serialized-byte limits;
  `hop_limit` / `copy_budget` enforcement via forwarding-state
  `hop_count` and `remaining_copy_budget` that never alter `object_id`.
- **Approval gate:** cleared. The design was frozen and reviewed first,
  then approved separately; `IMPLEMENTATION_STATUS` is now
  `APPROVED_FOR_MILESTONE_1`. All five authorised slices are complete;
  this approval does not extend to M2 or later work.

---

## Remaining milestone completion model

M2 through M9 use two distinct gates:

- **SOFTWARE-COMPLETE RELEASE CANDIDATE:** locally implementable code,
  Android/JVM or emulator evidence, two-process evidence, packaging and
  checklists. It makes no device, radio or field claim.
- **FIELD-VALIDATED RELEASE:** the software candidate plus physical
  devices, real radios, repeated runs, device measurements, production
  release decisions and field evidence.

Automation vocabulary is defined in `ACCEPTANCE_TESTS.md`:
`AUTOMATED_LOCAL`, `TWO_PROCESS`, `JVM_OR_EMULATOR`,
`PHYSICAL_DEVICE`, `REAL_RADIO` and `FIELD_ONLY`.

---

## Separate delivery path — Bangladesh domestic/BDIX hub

**Status:** SCOPE_FROZEN; APPROVED_FOR_BDIX_DOMESTIC_HUB_SOFTWARE;
FIELD_VALIDATION_NOT_APPROVED.
**Classification:** software/deployment package plus a separate domestic
network field gate.

- **Objective:** exchange public, human-confirmed text capsules between
  browsers on different Bangladeshi ISP/Wi-Fi networks while those networks
  can still reach one Bangladesh-hosted hub through a domestic route.
- **Scope freeze:** `BDIX_HUB_SCOPE.md`, commit
  `3b77dfe367a0e5c1d5b2ca242d6496824e868384`.
- **Deliverables:** strict bounded WSGI API; SQLite durability, expiry and
  idempotency; public-only browser client with a persistent outbox and cached
  shell; health/backup/deployment package.
- **Acceptance IDs:** BH-01 through BH-12.
- **Exclusions:** private chat, accounts, media, end-to-end encryption claims,
  global-Internet replacement, cross-hub federation and any claim that the
  route works when domestic ISP/BDIX connectivity is also unavailable.
- **Software gate:** automated API/storage/static/deployment tests plus a real
  browser publish/fetch/reload exercise and Linux Gunicorn smoke.
- **Field gate:** one named Bangladesh host, two named ISPs, controlled loss of
  global reachability, bidirectional exchange, interruption/reconnect evidence
  and ten cold runs.
- **Fallback:** the existing same-Wi-Fi/hotspot transport is the deeper-outage
  nearby path. It is not silently presented as distant connectivity.

This path is centralized and optional. It does not modify the M0/M1
deterministic core or imply approval for any numbered milestone.

---

## Milestone 2 — Local two-process transfer

**Status:** SCOPE_FROZEN; APPROVED_FOR_SOFTWARE_IMPLEMENTATION.
**Classification:** software-testable.

- **Objective:** run the completed M1 core across two real OS processes
  on one developer machine.
- **Prerequisite milestones:** M1 COMPLETE.
- **Deliverables:** a 4-byte big-endian `FrameCodec`; stdio and TCP
  loopback endpoints; deterministic process fixtures; interruption,
  crash, restart and resume evidence.
- **Exclusions:** Android, radio APIs, device claims, shared concurrent
  writers and any change to M1 protocol behaviour.
- **Implementation boundary:** `adapters/process/` and
  `adapters/transport_sim/`; both import the core, never the reverse.
- **Acceptance IDs:** AT-38, AT-39, AT-40, AT-41.
- **Evidence and tests:** `TWO_PROCESS` transcripts, canonical-vector
  hashes, missing-chunk request lists, process-exit evidence and the
  unchanged 367-test baseline. No emulator or hardware test is needed.
- **Completion gate:** all four IDs pass in two fresh OS processes and
  M0/M1 evidence remains byte-identical.
- **Rollback boundary:** revert the M2 adapter slice; the in-process M1
  core remains the working baseline.

---

## Milestone 3 — Android foundation and direct peer transport

**Status:** SCOPE_FROZEN; APPROVED_FOR_SOFTWARE_IMPLEMENTATION;
FIELD_VALIDATION_NOT_APPROVED.
**Classification:** mixed (software/emulator plus real radio).

- **Objective:** create the Android/Kotlin application foundation,
  prove Kotlin conformance, and place direct peer transport behind the
  frozen adapter boundary.
- **Prerequisite milestones:** M2 software gate.
- **Deliverables:** Android Gradle project; Kotlin conformance codec;
  app-private persistence adapter; single-activity Compose shell;
  lifecycle-safe UI state; permission UX; simulated transport; a
  provisional Nearby Connections adapter and documented alternates.
- **Exclusions:** locked transport claims, OEM support claims, offline
  model inference, field completion, public-store publication and
  production keys.
- **Implementation boundary:** new `android/` modules only, plus the
  transport interfaces frozen in `REMAINING_SCOPE.md`; the Python core
  and M0 simulator are not rewritten for Android.
- **Acceptance IDs:** AT-39, AT-42 through AT-50.
- **Automated/local tests:** AT-39 and the simulated portions of AT-42
  through AT-44.
- **Emulator tests:** AT-39 and AT-42 through AT-46.
- **Physical/real-radio tests:** AT-47 through AT-50; these are manual
  field-validation gates and cannot block software implementation.
- **Evidence:** vector hash parity, adapter event sequences, lifecycle
  and denied-permission state, then device/session logs and ten cold
  real-radio runs.
- **Completion gate:** software half passes AT-39 and AT-42 through
  AT-46; field half separately passes AT-47 through AT-50 on the named
  devices. Until then the transport remains provisional.
- **Rollback boundary:** remove or swap Android adapters; M2 and the
  canonical Python core remain intact.

---

## Milestone 4 — Progressive media transfer

**Status:** SCOPE_FROZEN; APPROVED_FOR_SOFTWARE_IMPLEMENTATION;
FIELD_VALIDATION_NOT_APPROVED.
**Classification:** mixed (software/emulator plus real radio).

- **Objective:** implement source-preserving progressive
  representations and D-007 delivery ordering.
- **Prerequisite milestones:** M3 software gate; real-radio validation
  is required only for the M4 field gate.
- **Deliverables:** capture/load ports for photo, short video, audio,
  text and document; `thumb`, `preview`, `standard`, `original`
  availability metadata; platform codec adapter; fixed-size chunking,
  hashes, preview/playback state and reconstruction.
- **Exclusions:** SVC, partial-file playback, content-defined chunking,
  keyframe-aligned chunking and any claim of universal codec support.
- **Implementation boundary:** `android/media/` performs platform
  encoding; deterministic chunking, identity, ordering and integrity
  stay transport-neutral.
- **Acceptance IDs:** AT-51 through AT-55.
- **Automated/local tests:** AT-51, AT-52, AT-54 with deterministic
  fixtures; **emulator tests:** AT-51 through AT-54; **real-radio
  test:** AT-55.
- **Evidence:** representation manifests, availability states,
  before/after source hashes, arrival-order logs and the final
  reconstruction hash.
- **Completion gate:** AT-51 through AT-54 gate software completion;
  AT-55 gates the M4 field claim.
- **Rollback boundary:** fall back to thumbnail-only representation
  while retaining the original and explicit unavailable states.

---

## Milestone 5 — Real-device multi-peer completion

**Status:** SCOPE_FROZEN; APPROVED_FOR_EVIDENCE_TOOLING_ONLY;
FIELD_VALIDATION_NOT_APPROVED.
**Classification:** physical-device-dependent and real-radio-dependent.

- **Objective:** validate ordinary missing-chunk completion from a
  least three physical peers.
- **Prerequisite milestones:** M4 software and real-radio gates.
- **Deliverables:** device-run script, inventory seed fixtures,
  fragment-source report and reconstruction-hash report.
- **Exclusions:** Reed-Solomon, fountain codes, RaptorQ, simulated
  evidence presented as device evidence, and guaranteed delivery.
- **Implementation boundary:** no new protocol algorithm; M5 executes
  the M4/M1 implementation on real devices.
- **Acceptance IDs:** AT-56 and AT-57.
- **Tests:** `REAL_RADIO` only; local/emulator fixtures may rehearse the
  script but cannot satisfy either ID.
- **Evidence:** named device/OS matrix, contributing peer IDs,
  missing-only requests and matching representation hashes.
- **Completion gate:** both IDs pass on at least three real devices.
- **Rollback boundary:** retain the software-complete M4 candidate and
  report M5 as unvalidated; never replace failed evidence with a
  simulation claim.

---

## Later research extension — Coded delivery

**Status:** OUTSIDE_M0_THROUGH_M9.

Reed-Solomon, fountain codes and RaptorQ require a separate scope,
dependency review, acceptance catalogue and implementation approval.

---

## Milestone 6 — Offline semantic extraction

**Status:** SCOPE_FROZEN; APPROVED_FOR_SOFTWARE_IMPLEMENTATION;
FIELD_VALIDATION_NOT_APPROVED.
**Classification:** mixed (software fallback plus optional device model).

- **Objective:** provide an optional offline `SemanticExtractor` while
  preserving the complete manual capsule path.
- **Prerequisite milestones:** M4 software gate. M5 field evidence is
  not required to implement or verify the model-independent software.
- **Deliverables:** `Unavailable`, deterministic `TestDouble` and
  pluggable real-runtime interfaces; manual form; human review and
  confirmation; model package/resource evaluation hooks.
- **Exclusions:** cloud inference, mandatory model downloads, model
  output as truth, autonomous publication and source replacement.
- **Implementation boundary:** `android/semantic/` is independent from
  networking; protocol acceptance uses only deterministic doubles.
- **Acceptance IDs:** AT-58 through AT-62.
- **Automated/local and emulator tests:** AT-58 through AT-60.
- **Physical-device evidence:** AT-61 and AT-62 are non-blocking
  research evidence; a negative result selects `Unavailable` and the
  manual fallback.
- **Evidence:** deterministic paired outputs, offline/no-download
  assertion, source linkage, resource measurements and Bangla scores.
- **Completion gate:** AT-58 through AT-60 gate software completion.
  Model claims additionally require AT-61 and AT-62 evidence.
- **Rollback boundary:** select `Unavailable`; the app remains usable
  through the manual form.

---

## Milestone 7 — Integration, resilience and privacy controls

**Status:** SCOPE_FROZEN; APPROVED_FOR_SOFTWARE_IMPLEMENTATION;
FIELD_VALIDATION_NOT_APPROVED.
**Classification:** mixed (software/emulator plus device evidence).

- **Objective:** integrate M2, the M3/M4 software, and the M6 manual
  path with lifecycle, storage, permission, security and diagnostic
  controls.
- **Prerequisite milestones:** M2 and the software gates of M3, M4 and
  M6.
- **Deliverables:** restart recovery; rejection-only storage-pressure
  UX; permission degradation; consent UX; malformed-input and
  replay/flood limits; platform key-storage abstraction; redacted,
  opt-in diagnostics.
- **Exclusions:** bespoke encryption, production trust roots,
  production keys, silent telemetry, cloud services and claims of a
  security audit.
- **Implementation boundary:** `android/app`, `android/ui`,
  `android/security`, `android/diagnostics` and adapters over unchanged
  deterministic core contracts.
- **Acceptance IDs:** AT-63 through AT-73.
- **Automated/local tests:** AT-64, AT-67 and AT-69 through AT-73;
  **emulator tests:** AT-63, AT-64 and AT-66 through AT-70;
  **physical-device test:** AT-65.
- **Evidence:** restart inventories, quota and permission transcripts,
  refusal records, repository secret scan, storage/backup inspection
  and field-level diagnostic scan.
- **Completion gate:** all applicable software/emulator assertions in
  AT-63, AT-64 and AT-66 through AT-73 pass. AT-65 separately gates the
  low-battery device claim.
- **Rollback boundary:** revert the failing integration slice and keep
  the last passing M4/M6 software assembly; verified content is not
  discarded to make rollback succeed.

---

## Milestone 8 — Device benchmarking

**Status:** SCOPE_FROZEN; APPROVED_FOR_EVIDENCE_TOOLING_ONLY;
FIELD_VALIDATION_NOT_APPROVED.
**Classification:** physical-device-dependent.

- **Objective:** replace `UNMEASURED` device cells with reproducible
  observations from the integrated build.
- **Prerequisite milestones:** M7 software gate and required device
  setup.
- **Deliverables:** committed benchmark runner/checklist, device/run
  metadata schema and filled `EXPERIMENT_PLAN.md` result tables.
- **Exclusions:** invented numbers, simulator values labelled as device
  values, performance marketing claims and hidden failed runs.
- **Implementation boundary:** evidence tooling may be prepared
  locally; actual measurements require physical devices.
- **Acceptance ID:** AT-74.
- **Tests:** runner/schema validation is `AUTOMATED_LOCAL`; acceptance
  evidence is `PHYSICAL_DEVICE`.
- **Evidence:** raw run records, confidence interval or explicit
  failure note, device/OS/build metadata and reproducible aggregation.
- **Completion gate:** AT-74 is executed on the named devices; a failed
  target is recorded as a result, not rewritten as success.
- **Rollback boundary:** preserve M7 and leave cells `UNMEASURED`;
  never substitute fabricated values.

---

## Milestone 9 — Packaging, demo and public release

**Status:** SCOPE_FROZEN; APPROVED_FOR_SOFTWARE_IMPLEMENTATION;
FIELD_VALIDATION_NOT_APPROVED.
**Classification:** mixed (software packaging plus radio/field gates).

- **Objective:** produce an honest, reproducible software release
  candidate and a separately field-validated demonstration package.
- **Prerequisite milestones:** M7 software gate for packaging; M8
  evidence and the required manual release decisions for public claims.
- **Deliverables:** reproducible local build; install/upgrade fixtures;
  demo script; device/field checklists; public status documentation.
- **Exclusions:** embedded production keys, automatic store
  publication, claims exceeding evidence and any field trial without
  explicit consent/authorisation.
- **Implementation boundary:** build/packaging, migration fixtures and
  documentation. Production signing and publication remain manual.
- **Acceptance IDs:** AT-75 through AT-78.
- **Automated/local test:** AT-75; **emulator test:** AT-76;
  **real-radio test:** AT-77; **field-only test:** AT-78.
- **Evidence:** independent build hashes, install/upgrade inventories,
  ten cold demo records and consented field logs.
- **Completion gate:** AT-75 and AT-76 produce the software-complete
  candidate. AT-77, AT-78 and all manual release gates are required
  before any field-validated or public-release claim.
- **Rollback boundary:** publish no claim or artifact; retain the
  software candidate and document the failed gate.

---

## Cross-milestone decision records

### DR-MS-01 — M0 is the only milestone eligible for first approval

- Decision: only M0 may be approved first in this plan.
- Alternatives: approve M3 first.
- Recommended: M0 first.
- Reason: it validates the protocol without radio risk.
- Evidence required: M0 acceptance tests.
- Trade-offs: slower time-to-real-device.
- Risks: M0 success may not predict real-device success.
- Validation: M3 entry gate.
- Revisit condition: M0 results.

### DR-MS-02 — Coded reconstruction is not a target of any M0–M5 milestone

- Decision: M0–M5 do not implement erasure / rateless coding.
- Alternatives: include in M5.
- Recommended: defer.
- Reason: keep descriptions honest.
- Evidence required: M5+ implementation.
- Trade-offs: lower robustness.
- Risks: docs confusion.
- Validation: README, `EXPERIMENT_PLAN.md`, `PROTOCOL_SPEC.md`,
  `MEDIA_PIPELINE.md` all use distinct language.
- Revisit condition: post-M5.

### DR-MS-03 — Utility-based forwarding is not a target of any M0–M5 milestone

- Decision: M0–M5 use deterministic forwarding.
- Alternatives: include in M5.
- Recommended: defer.
- Reason: M0 must be reproducible.
- Evidence required: M5+ implementation.
- Trade-offs: less adaptivity.
- Risks: people compare to learned policies.
- Validation: explicit deferral callout in `EXPERIMENT_PLAN.md`.
- Revisit condition: post-M5.
