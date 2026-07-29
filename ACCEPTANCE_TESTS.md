# Shongket — Acceptance Tests (Draft 1)

Planning-only. Each test: preconditions, input, steps, expected
result, automation level, milestone, evidence required, failure
severity.

Severity scale:
- **S1 critical:** blocks M0 approval.
- **S2 major:** blocks M1 approval.
- **S3 minor:** tracked but non-blocking.

---

## AT-01 Semantic capsule reaches peers before bulk media

- Preconditions: synthetic media queued; deterministic forwarding.
- Input: a critical semantic capsule + large low-priority media.
- Steps: send bulk first; queue critical capsule.
- Expected: critical capsule arrives ahead of bulk delivery.
- Automation: harness.
- Milestone: M0.
- Evidence required: measured log.
- Severity: S1.

## AT-02 Human confirmation blocks any sending

- Preconditions: capsule with `human_confirmed = false`.
- Input: try to publish.
- Steps: attempt to schedule the capsule for transmission.
- Expected: refused; logged; never sent.
- Automation: harness (M0 unit) + manual review (UI M5+).
- Milestone: M0.
- Evidence required: rejection log.
- Severity: S1.

## AT-03 Object identity derives from whole-object hash

- Preconditions: known input bytes.
- Input: same bytes sent by two senders.
- Steps: capture CIDs from both.
- Expected: identical CIDs.
- Automation: harness.
- Milestone: M0.
- Evidence required: CID equality log.
- Severity: S1.

## AT-04 Progressive media layers arrive in order

- Preconditions: text, photo, video all queued.
- Input: mixed priorities.
- Steps: run a single planner.
- Expected: capsule, then preview, then full media, by priority.
- Automation: harness.
- Milestone: M0.
- Evidence required: planner log.
- Severity: S1.

## AT-05 Critical preemption observed

- Preconditions: bulk transfer mid-flight; critical capsule arrives.
- Input: preemption request.
- Steps: emit preemption event.
- Expected: in-flight transfer saved; critical capsule scheduled.
- Automation: harness.
- Milestone: M0.
- Evidence required: preemption event log.
- Severity: S1.

## AT-06 Interrupted transfer retains progress

- Preconditions: chunk 5 of 20 sent.
- Input: peer disappears.
- Steps: later reconnect.
- Expected: chunks 6+ continue; previous chunks not duplicated.
- Automation: harness.
- Milestone: M0.
- Evidence required: reconnect log.
- Severity: S1.

## AT-07 Restart recovers progress

- Preconditions: same as AT-06; then app restart.
- Input: crash and restart.
- Steps: restart.
- Expected: persistence preserves acquired chunks; transfer resumes.
- Automation: harness.
- Milestone: M0.
- Evidence required: restart log.
- Severity: S1.

## AT-08 Multi-peer missing-chunk completion

- Preconditions: source data spread across ≥ 2 peers; no peer has
  full data.
- Input: receiver requests.
- Steps: receiver negotiates with both.
- Expected: full reconstruction; missing-chunks only.
- Automation: harness.
- Milestone: M0.
- Evidence required: reconstruction log; ≥ 2 peer ids.
- Severity: S1.

## AT-09 Duplicate-fragment dedup

- Preconditions: same fragment offered twice.
- Input: identical `FragmentDescriptor`.
- Steps: store twice.
- Expected: stored once; second is no-op.
- Automation: harness.
- Milestone: M0.
- Evidence required: dedup log.
- Severity: S1.

## AT-10 Corrupted-fragment rejection

- Preconditions: tampered fragment.
- Input: modified bytes.
- Steps: send to receiver.
- Expected: hash mismatch; rejected; logged.
- Automation: harness.
- Milestone: M0.
- Evidence required: rejection log.
- Severity: S1.

## AT-11 Expired content not forwarded

- Preconditions: TTL exceeded.
- Input: try to forward.
- Steps: forward.
- Expected: refused; object not scheduled.
- Automation: harness.
- Milestone: M0.
- Evidence required: refusal log.
- Severity: S1.

## AT-12 Storage budget enforcement

- Preconditions: low storage marker.
- Input: new content.
- Steps: ingest.
- Expected: eviction policy engages.
- Automation: harness (M0 unit, M5+ on real device).
- Milestone: M0 (rule), M5+ (effect).
- Evidence required: log; quota values.
- Severity: S2 (M0) / S1 (M5+).

## AT-13 Permission gate (later)

- Preconditions: required runtime permissions.
- Input: UI flow.
- Steps: decline.
- Expected: feature disabled; reason shown.
- Automation: manual on real device.
- Milestone: M5+.
- Evidence required: screen recording.
- Severity: S1 (release readiness).

## AT-14 Offline behavior

- Preconditions: airplane mode.
- Input: try to send.
- Steps: attempt.
- Expected: clear offline-path messaging.
- Automation: manual on real device.
- Milestone: M5+.
- Evidence required: recording.
- Severity: S2.

## AT-15 AI fallback to manual form

- Preconditions: model disabled or low-confidence.
- Input: capsule draft.
- Steps: request confirmation.
- Expected: structured manual form presented.
- Automation: M0 unit (model disabled path).
- Milestone: M0.
- Evidence required: fallback log.
- Severity: S1.

## AT-16 Privacy boundary

- Preconditions: private marker.
- Input: contact requests.
- Steps: forward.
- Expected: refused unless explicit consent.
- Automation: M0 unit.
- Milestone: M0.
- Evidence required: refusal log.
- Severity: S1.

## AT-17 Security boundary

- Preconditions: oversized payload.
- Input: send oversized.
- Steps: send.
- Expected: rejected with `ProtocolError`.
- Automation: harness.
- Milestone: M0.
- Evidence required: rejection log.
- Severity: S1.

## AT-18 Benchmarking acceptance

- Preconditions: experiments in EXPERIMENT_PLAN.md.
- Input: harness runs.
- Steps: collect metrics.
- Expected: metric values recorded; targets met.
- Automation: harness.
- Milestone: M0 (logging) → M5+ (per-device measurement).
- Evidence required: metric log per scenario.
- Severity: S1 (M0) / S1 (M5+ per scenario).

## AT-19 Demo readiness (later)

- Preconditions: two devices.
- Input: scripted demo.
- Steps: run script.
- Expected: completes with public-survivable behavior.
- Automation: manual.
- Milestone: M9.
- Evidence required: screen recording; reliability N runs.
- Severity: S1 (release readiness).

## AT-20 Malformed schema payload rejected

- Preconditions: payload is within the size limit but violates the declared
  protocol schema.
- Input: a payload with a missing required field, unsupported schema
  version, invalid enum value or invalid field type.
- Steps: submit the payload to protocol ingestion.
- Expected:
  - payload rejected;
  - nothing persisted;
  - nothing scheduled;
  - `ProtocolError` code is `SCHEMA_INVALID`;
  - rejection logged.
- Automation: harness.
- Milestone: M0.
- Evidence: schema-validation rejection log.
- Severity: S1.

## AT-21 Original source media remains preserved

- Preconditions: known original media bytes and a semantic capsule derived
  from them.
- Input: finalize and publish the Shongket object.
- Steps:
  1. record original source-media hash;
  2. attach semantic capsule;
  3. finalize manifest;
  4. retrieve stored source representation.
- Expected:
  - original source bytes unchanged;
  - source representation hash equals original hash;
  - semantic capsule references the source object;
  - generated summary or preview does not overwrite the original.
- Automation: harness.
- Milestone: M0.
- Evidence: before-and-after source hash and manifest-link log.
- Severity: S1.

---

## Test-count inventory

- **Total acceptance tests:** 21 (AT-01 … AT-21)
- **S1 tests across all milestone scopes:** 20
- **S1 tests within Milestone 0 scope:** 17
- **Milestone 0 blocking tests:** 18

> The 18 Milestone 0 blocking tests comprise the 17 S1 tests in the M0
> scope (AT-01 … AT-11, AT-15, AT-16, AT-17, AT-18, AT-20, AT-21) plus
> AT-12 as the M0-blocking S2 unit-level storage-budget test. AT-12 is
> included as blocking because its rule must be enforced even though its
> on-device effect is later (M5+).
>
> The 20 S1 tests across all milestone scopes add AT-13 (permissions,
> M5+) and AT-19 (demo readiness, M9), both of which are release-blocking
> but outside M0.

## Canonical traceability table

Every row uses a real `AT-NN` identifier. Legacy `AC-*` rows have been
removed; legacy identifiers cited elsewhere in the repository now map to
the canonical rows below per the cross-reference mappings recorded in
`SYSTEM_ARCHITECTURE.md`, `PROTOCOL_SPEC.md`, `MEDIA_PIPELINE.md` and
`MODEL_EVALUATION_PLAN.md`.

| Requirement | Canonical test | Evidence |
|---|---|---|
| Capsule before bulk media | AT-01 | priority-order event log (signal-plane ahead of media-plane for same object) |
| Human confirmation required | AT-02 | rejection log showing `human_confirmed = false` blocks publish |
| Stable object identity | AT-03 | CID equality log (same bytes → same CID across two senders) |
| Progressive layer ordering | AT-04 | planner log (capsule → preview → full media by priority) |
| Critical preemption | AT-05 | preemption event log with bulk-pause and critical-schedule timestamps |
| Interrupted transfer recovery | AT-06 | reconnect log (chunks 6+ sent; previous chunks not duplicated) |
| Restart recovery | AT-07 | persistence snapshot (verified chunks intact across restart) |
| Multi-peer missing-chunk completion | AT-08 | fragment-source report with ≥ 2 peer IDs and successful reconstruction |
| Duplicate-fragment rejection | AT-09 | dedup counter (second store is a no-op) |
| Corrupted-fragment rejection | AT-10 | hash-failure log; later valid chunks still accepted |
| Expired content rejection | AT-11 | refusal log showing object not scheduled past `expires_at` |
| Storage-budget rule | AT-12 | quota values and eviction-policy engagement log |
| Manual AI fallback | AT-15 | fallback log showing structured manual form when model is disabled or low-confidence |
| Private-content consent | AT-16 | refusal log showing private object not forwarded without explicit consent |
| Oversized-payload rejection | AT-17 | rejection log with `ProtocolError` for oversized payload |
| Metrics recorded | AT-18 | `EXPERIMENT_PLAN.md` result-table entries per scenario |
| Malformed-schema rejection | AT-20 | schema-validation rejection log with `ProtocolError` code `SCHEMA_INVALID` |
| Source-media preservation | AT-21 | before-and-after source hash and manifest-link log (hash unchanged, capsule linked) |

---

## Test inventory

> Counts are taken from the table below.

- Total acceptance tests: 21
- Severity S1 tests: 20 (S1 in any milestone scope)
- Severity S1 tests, **M0 scope only**: 17
- Severity S2 tests: AT-12 (M0 unit), AT-14
- Milestone 0 blocking tests (18):
  AT-01, AT-02, AT-03, AT-04, AT-05, AT-06, AT-07, AT-08, AT-09,
  AT-10, AT-11, AT-12 (unit-level), AT-15, AT-16, AT-17, AT-18
  (logging), AT-20, AT-21

### M0 success-criterion → acceptance-test mapping

The 10 M0 success criteria from `MILESTONES.md` map onto the tests as
follows:

| M0 criterion | Acceptance test ID | Severity | Evidence |
|---|---|---|---|
| Capsule before media | AT-01 | S1 | measured log (priority-order events) |
| Critical preemption | AT-05 | S1 | preemption event log + timestamps |
| Bulk transfer resumes | AT-05, AT-06 | S1 | transfer-state log |
| Restart recovery | AT-07 | S1 | persistence snapshot |
| Two-peer completion | AT-08 | S1 | fragment-source report (≥ 2 peer ids) |
| Duplicate rejection | AT-09 | S1 | dedup counter |
| Corruption rejection | AT-10 | S1 | hash-failure log |
| Final hash verification | AT-10, AT-04 | S1 | representation hash check |
| Expiry enforcement | AT-11 | S1 | advertisement / forwarding log |
| Metrics produced | AT-18 | S1 | `EXPERIMENT_PLAN.md` result-table entries |

Each row must produce its declared evidence before M0 sign-off.

## Test summary table

| ID | Theme | Automation | Milestone | Severity |
|---|---|---|---|---|
| AT-01 | Priority ordering | harness | M0 | S1 |
| AT-02 | Human confirmation | harness | M0 | S1 |
| AT-03 | Content identity | harness | M0 | S1 |
| AT-04 | Progressive layers | harness | M0 | S1 |
| AT-05 | Critical preemption | harness | M0 | S1 |
| AT-06 | Interruption resume | harness | M0 | S1 |
| AT-07 | Restart recovery | harness | M0 | S1 |
| AT-08 | Multi-peer completion | harness | M0 | S1 |
| AT-09 | Dedup | harness | M0 | S1 |
| AT-10 | Corruption reject | harness | M0 | S1 |
| AT-11 | Expiry | harness | M0 | S1 |
| AT-12 | Storage budget | harness + device | M0/M5+ | S2/S1 |
| AT-13 | Permissions | manual | M5+ | S1 |
| AT-14 | Offline | manual | M5+ | S2 |
| AT-15 | AI fallback | harness | M0 | S1 |
| AT-16 | Privacy | harness | M0 | S1 |
| AT-17 | Security | harness | M0 | S1 |
| AT-18 | Benchmarking | harness | M0/M5+ | S1 |
| AT-19 | Demo readiness | manual | M9 | S1 |
| AT-20 | Schema rejection | harness | M0 | S1 |
| AT-21 | Source preservation | harness | M0 | S1 |

---

## Decision records

### DR-AT-01 — All acceptance tests have evidence required

- Decision: every test row above declares evidence expected.
- Alternatives: track outcomes informally.
- Recommended: explicit evidence.
- Reason: per `AGENTS.md` research rules.
- Evidence required: source-quality check at milestone close.
- Trade-offs: extra metadata per test.
- Risks: none significant.
- Validation: AT-M0 closure checklist.
- Revisit condition: M5+.

### DR-AT-02 — Severity scale locks early

- Decision: S1/S2/S3 above are the test-verdict policy for M0.
- Alternatives: rework when S2 becomes S1.
- Recommended: keep scale conservative (S1 at first; promote later
  by decision).
- Reason: avoid mid-stream scope expansion.
- Evidence required: revisit conditions.
- Trade-offs: later revisions required.
- Risks: tests perceived as too easy.
- Validation: each milestone closure.
- Revisit condition: M3 / M5 / M7.
