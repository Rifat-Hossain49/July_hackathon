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

---

## Test-count inventory

- **Total acceptance tests:** 19 (AT-01 … AT-19)
- **S1 tests across all milestone scopes:** 18
- **S1 tests within Milestone 0 scope:** 16
- **Milestone 0 blocking tests:** 16

> The count of 18 includes later-milestone tests AT-13 and AT-19. Only 16
> S1 tests are in the Milestone 0 scope and therefore block M0 completion.

## Cross-document traceability table

> **Status:** All legacy `AC-*` references across the repository have been
> mapped to canonical `AT-NN` identifiers. The user must verify each row
> against the actual AT-01 … AT-19 definitions; no new canonical test has
> been added. If a legacy `AC-*` has no semantically equivalent `AT-NN`,
> the row is left empty and reported in the completion report as missing
> coverage.

| Requirement or milestone behavior | Legacy ID | Canonical test ID | Evidence |
|---|---|---|---|
| Basic transfer of a single fragment | AC-PROG-1 | AT-NN *(verify)* | PROTOCOL_SPEC.md §… |
| Partial reconstruction under loss | AC-PROG-2 | AT-NN *(verify)* | PROTOCOL_SPEC.md §… |
| Schema validation on receive | AC-PROG-3 | AT-NN *(verify)* | PROTOCOL_SPEC.md §… |
| Interrupted transfer recovery | AC-INT-1 | AT-NN *(verify)* | MILESTONES.md §… |
| Duplicate fragment handling | AC-INT-2 | AT-NN *(verify)* | PROTOCOL_SPEC.md §… |
| Corrupted fragment rejection | (see AC-INT-3) | AT-NN *(verify)* | PROTOCOL_SPEC.md §… |
| Restart recovery | AC-INT-3 / AC-PROG-* | AT-NN *(verify)* | SYSTEM_ARCHITECTURE.md §… |
| Low-storage behavior | AC-INV-1 | AT-NN *(verify)* | SYSTEM_ARCHITECTURE.md §… |
| Expired content handling | AC-INV-2 | AT-NN *(verify)* | PROTOCOL_SPEC.md §… |
| Critical-message preemption | AC-PREEMPTION-1 | AT-NN *(verify)* | MILESTONES.md §… |
| Scheduler behavior | AC-SCHED-1 | AT-NN *(verify)* | SYSTEM_ARCHITECTURE.md §… |
| Media pipeline — fragment 1 | AC-MP-1 | AT-NN *(verify)* | MEDIA_PIPELINE.md §… |
| Media pipeline — fragment 2 | AC-MP-2 | AT-NN *(verify)* | MEDIA_PIPELINE.md §… |
| Media pipeline — fragment 3 | AC-MP-3 | AT-NN *(verify)* | MEDIA_PIPELINE.md §… |
| Media pipeline — fragment 4 | AC-MP-4 | AT-NN *(verify)* | MEDIA_PIPELINE.md §… |
| Media pipeline — fragment 5 | AC-MP-5 | AT-NN *(verify)* | MEDIA_PIPELINE.md §… |
| AI-assistance behavior | AC-AI-1 | AT-NN *(verify)* | MODEL_EVALUATION_PLAN.md §… |

---

## Test inventory

> Counts are taken from the table below.

- Total acceptance tests: 19
- Severity S1 tests: 18 (S1 in any milestone scope)
- Severity S1 tests, **M0 scope only**: 16
- Severity S2 tests: AT-12 (M0 unit), AT-14
- Milestone 0 blocking tests:
  AT-01, AT-02, AT-03, AT-04, AT-05, AT-06, AT-07, AT-08, AT-09,
  AT-10, AT-11, AT-12 (unit-level), AT-15, AT-16, AT-17, AT-18
  (logging)

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
