# Shongket — Milestones (Draft 1)

Implementation approval status is **tracked per milestone**. M0 was
approved first, as this plan requires; every later milestone remains
unapproved.

Per `PRODUCT_DECISIONS.md`: `IMPLEMENTATION_STATUS: APPROVED_FOR_MILESTONE_0`.

Approval for Milestone 0 does not authorise Milestone 1 or later work.

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
  - executable simulator harness (single-process multi-agent or two-process)
  - fixed-size fragmentation strategy implementation
  - SHA-256 per chunk + per representation
  - deterministic scheduler
  - Bloom inventory encoding
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

**Status:** PROPOSED.

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
- **Implementation approval status:** PROPOSED.
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
- **Approval gate:** the design is settled, but implementation is **not
  authorised**. This milestone stays PROPOSED and
  `IMPLEMENTATION_STATUS` stays `APPROVED_FOR_MILESTONE_0` until the
  user changes both. No M1 code exists and no M1 result is recorded.

---

## Milestone 2 — Local two-process transfer

**Status:** PROPOSED.

Two local processes exchange protocol objects through a local test
transport.

No Android, Nearby Connections, Wi-Fi Direct or OEM compatibility
testing belongs to this milestone.

- **Objective:** run the M1 core across two real OS processes on a
  developer machine.
- **Why:** validates scheduler / IPC boundary before Android.
- **Dependencies:** M1 acceptance.
- **Deliverables:** two processes cooperating over loopback /
  stdin-stdout for testing.
- **Acceptance criteria:** M1 acceptance tests pass on two-process
  harness.
- **Tests:** same suite, two-process mode.
- **Explicitly excluded:** Android, real radios.
- **Fallback:** if IPC fails, narrow to single-process before M3.
- **Rollback condition:** revert to M1 harness.
- **Estimated complexity:** S.
- **Primary risks:** IPC bottlenecks.
- **Implementation approval status:** PROPOSED.

---

## Milestone 3 — Android direct peer transport

**Status:** PROPOSED; gated by the **transport smoke-test gate**.

This milestone contains:

- Nearby Connections smoke testing;
- Wi-Fi Direct evaluation;
- local-hotspot evaluation;
- Android permission behavior;
- vendor compatibility;
- interruption and reconnection testing;
- real-device throughput measurements;
- repeated demo-device reliability testing.

The transport remains provisional until the smoke-test gate passes.

- **Objective:** connect the M1 core to a real Android transport.
- **Why:** tests the `TransportAdapter` boundary in practice.
- **Dependencies:** M2; smoke-test gate result (see
  `RESEARCH_LOG.md` §Transport).
- **Deliverables:** an APK-shaped artifact (no `app/` change in this
  plan) running the M1 core on real hardware.
- **Acceptance criteria:** smoke-test gate criteria all pass;
  short-encounter scenario passes on real devices.
- **Tests:** real-device transport tests in `ACCEPTANCE_TESTS.md`.
- **Explicitly excluded:** production hardening; offline AI runtime.
- **Fallback:** if no transport passes the gate, M3 is blocked; use
  the simulated heap until a transport passes.
- **Rollback condition:** keep M1 core; do not abandon `app/`
  scaffolding.
- **Estimated complexity:** L.
- **Primary risks:** Android vendor fragmentation; permission
  complexity; Play Services dependency.
- **Implementation approval status:** PROPOSED.

---

## Milestone 4 — Progressive media transfer

**Status:** PROPOSED.

- **Objective:** demonstrate the D-007 progressive delivery order in
  real transfers.
- **Why:** supports the central thesis; non-trivial real-device
  validation.
- **Dependencies:** M3.
- **Deliverables:** progressive representations + ordering on real
  devices.
- **Acceptance criteria:** AT-PROG-1..AT-PROG-3 pass.
- **Tests:** `ACCEPTANCE_TESTS.md` progressive media group.
- **Explicitly excluded:** SVC; partial-file playback.
- **Fallback:** if a representation can't be produced at runtime, the
  UI shows a clear "this representation unavailable" status.
- **Rollback condition:** fall back to thumbnail-only delivery.
- **Estimated complexity:** M.
- **Primary risks:** codec availability; storage pressure.
- **Implementation approval status:** PROPOSED.

---

## Milestone 5 — Real-device multi-peer completion

**Status:** PROPOSED.

Complete original media using ordinary verified chunks collected from
multiple physical peers.

This is not coded reconstruction.

- **Objective:** validate multi-peer missing-chunk completion on real
  devices.
- **Why:** central to the product thesis.
- **Dependencies:** M4.
- **Deliverables:** ≥ 3 devices demonstrating multi-peer
  reconstruction.
- **Acceptance criteria:** AT-MP-1..AT-MP-5 pass.
- **Tests:** `ACCEPTANCE_TESTS.md` multi-peer group.
- **Explicitly excluded:** erasure / rateless coding (deferred to a
  later research milestone).
- **Fallback:** if real devices fail, fall back to M1+simulation.
- **Rollback condition:** none — multi-peer is a core claim.
- **Estimated complexity:** L.
- **Primary risks:** real-device reliability.
- **Implementation approval status:** PROPOSED.

---

## Later research extension — Coded delivery

**Status:** NOT PART OF M0–M5.

Possible later strategies:

- Reed-Solomon;
- fountain codes;
- RaptorQ.

This extension requires separate approval and is not part of M0–M5
unless explicitly added later.

---

## Milestone 6 — Offline semantic extraction

**Status:** PROPOSED.

- **Objective:** integrate a benchmark-selected offline model
  (per `MODEL_EVALUATION_PLAN.md`).
- **Why:** automate the suggestion step; preserve manual form as
  fallback.
- **Dependencies:** M5; benchmark result on M6 device profiles.
- **Deliverables:** offline model selector + manual form fallback.
- **Acceptance criteria:** metrics in `MODEL_EVALUATION_PLAN.md` meet
  declared thresholds; Bangla support meets threshold.
- **Tests:** benchmark corpus + AT-AI-1..AT-AI-4.
- **Explicitly excluded:** cloud AI; replacing original media.
- **Fallback:** manual form (D-011).
- **Rollback condition:** revert to M5 product shape.
- **Estimated complexity:** L.
- **Primary risks:** model size, Bangla support, energy use.
- **Implementation approval status:** PROPOSED.

---

## Milestone 7 — Integration and resilience

**Status:** PROPOSED.

- **Objective:** full integration of M1–M6 with restart, interruption,
  low-storage, low-battery, denied-permissions handling.
- **Why:** real-world resilience.
- **Dependencies:** M6.
- **Deliverables:** integrated app; resilience test results.
- **Acceptance criteria:** `ACCEPTANCE_TESTS.md` resilience group.
- **Tests:** `ACCEPTANCE_TESTS.md` resilience group.
- **Explicitly excluded:** production hardening (out of hackathon).
- **Fallback:** narrower resilience subset on lower tiers.
- **Rollback condition:** M5+M6 stable build.
- **Estimated complexity:** M.
- **Primary risks:** low-end device behavior.
- **Implementation approval status:** PROPOSED.

---

## Milestone 8 — Benchmarking

**Status:** PROPOSED.

- **Objective:** fill the empty result tables with measured numbers
  from M7.
- **Why:** replaces simulations with measured numbers.
- **Dependencies:** M7.
- **Deliverables:** filled `EXPERIMENT_PLAN.md` tables; per-tier
  results.
- **Acceptance criteria:** every "hypothesis" target has a measured
  number with confidence interval or explicit failure note.
- **Tests:** all metrics in `EXPERIMENT_PLAN.md`.
- **Explicitly excluded:** marketing claims.
- **Fallback:** fall back to M7 simulation-only results.
- **Rollback condition:** keep M7 as the baseline.
- **Estimated complexity:** M.
- **Primary risks:** measurement bias.
- **Implementation approval status:** PROPOSED.

---

## Milestone 9 — Demo and public release

**Status:** PROPOSED.

- **Objective:** honest, reproducible demonstration + public release.
- **Why:** rubric weights impact + presentation + public engagement.
- **Dependencies:** M8.
- **Deliverables:** demo script, public README, public release.
- **Acceptance criteria:** demo runs the smoke-test gate 10× in a row.
- **Tests:** repeated demo reliability test.
- **Explicitly excluded:** claims exceeding measurements.
- **Fallback:** if repeated run fails, demo runs with documented
  countermeasure.
- **Rollback condition:** none.
- **Estimated complexity:** S.
- **Primary risks:** demo flakiness; overclaim.
- **Implementation approval status:** PROPOSED.

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
