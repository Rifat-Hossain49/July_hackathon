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

# Milestone 1 acceptance tests (AT-22 … AT-37)

**Status: PROPOSED.** These define the M1-blocking catalogue approved in
`M1_SCOPE_FREEZE.md`. They are specifications only — no M1
implementation exists and no M1 result is recorded. `IMPLEMENTATION_STATUS`
remains `APPROVED_FOR_MILESTONE_0`, so none of these may be implemented
yet.

Severity follows the existing scale: **S2 blocks M1 approval**; the two
S1 rows (AT-30, AT-37) additionally protect M0 evidence already earned.

## AT-22 Canonical serialization is byte-stable

- Preconditions: a populated object of each canonical schema.
- Input: each object encoded, decoded and re-encoded.
- Steps: encode → decode → encode; compare bytes; repeat in a fresh
  process.
- Expected: both encodings byte-identical; key order and separators
  stable; no float-formatting divergence; identical across processes.
- Automation: harness.
- Milestone: M1.
- Evidence required: SHA-256 of each encoding, per schema.
- Severity: S2.
- Runtime boundary: `core/codec`.

## AT-23 Compatible minor-version payload accepted

- Preconditions: registry supports major `1`; a registered compatibility
  entry exists for the higher minor.
- Input: a payload declaring a higher registered minor and carrying one
  unknown additional field.
- Steps: submit to the validation boundary.
- Expected: accepted; the unknown field is ignored, not persisted and
  not echoed; no error raised; known fields validated normally.
- Automation: harness.
- Milestone: M1.
- Evidence required: acceptance log naming the ignored field.
- Severity: S2.
- Runtime boundary: `core/schema` + `core/validate`.

## AT-24 Unsupported version rejected

- Preconditions: registry supports major `1` only, with a known set of
  registered minors.
- Input: (a) a payload declaring major `2`; (b) a payload that is both
  major `2` and structurally malformed; (c) a payload declaring major
  `1` with an **unregistered** minor.
- Steps: submit each.
- Expected: all three rejected with `VERSION_UNSUPPORTED` — case (b)
  proves the version is resolved before structural parsing, so
  `SCHEMA_INVALID` is never returned instead; no partial decode; nothing
  scheduled or persisted.
- Automation: harness.
- Milestone: M1.
- Evidence required: rejection log with code and declared version.
- Severity: S2.
- Runtime boundary: `core/schema`.

## AT-25 Deterministic persistence migration

- Preconditions: a snapshot at version N; current version N+1.
- Input: the vN snapshot.
- Steps: open, migrate, write; repeat the whole sequence from identical
  starting bytes.
- Expected: migrated document byte-identical across both runs; every
  verified fragment preserved with matching SHA-256; migration steps
  applied in order.
- Automation: harness.
- Milestone: M1.
- Evidence required: SHA-256 before and after; migration step log.
- Severity: S2.
- Runtime boundary: `core/migrate`.

## AT-26 Crash-safe atomic snapshot write

- Preconditions: an existing durable snapshot.
- Input: a save interrupted at each stage — after temp write, after temp
  fsync, after replace, before parent-directory fsync.
- Steps: inject the interruption at each point; reopen the store.
- Expected: the reader always sees either the complete previous document
  or the complete new one, never a blend; no partial document is loaded;
  temp artefacts are ignored and cleaned.
- Automation: harness (fault injection; no real power loss).
- Milestone: M1.
- Evidence required: per-stage recovery log and resulting checksum.
- Severity: S2.
- Runtime boundary: `core/persist`.

## AT-27 Partial-write recovery

- Preconditions: a durable snapshot plus a truncated temporary file.
- Input: a temporary file containing a prefix of a valid document.
- Steps: open the store.
- Expected: the truncated temp is ignored and removed; the previous
  durable snapshot loads intact; no exception escapes; recovery logged.
- Automation: harness.
- Milestone: M1.
- Evidence required: recovery log naming the discarded artefact.
- Severity: S2.
- Runtime boundary: `core/persist`.

## AT-28 Corrupted-snapshot recovery

- Preconditions: a durable snapshot with a valid last-good copy.
- Input: (a) corrupted document checksum; (b) one fragment's bytes
  corrupted while the document checksum remains valid.
- Steps: open the store for each case.
- Expected: (a) the file is quarantined — renamed aside, **never
  deleted** — and the last good snapshot loads; (b) only the corrupt
  fragment is dropped, every intact fragment is preserved, and the loss
  is logged.
- Automation: harness.
- Milestone: M1.
- Evidence required: quarantine path and per-fragment integrity report.
- Severity: S2.
- Runtime boundary: `core/persist`.

## AT-29 Rollback after failed migration

- Preconditions: a vN snapshot; a migration that fails mid-chain.
- Input: an injected failure during the durable write of the migrated
  document.
- Steps: attempt migration; fail; reopen.
- Expected: the original vN document remains readable and byte-identical
  to before the attempt; no partially migrated state is visible; the
  failure is classified retryable.
- Automation: harness.
- Milestone: M1.
- Evidence required: pre/post SHA-256 of the original document.
- Severity: S2.
- Runtime boundary: `core/migrate` + `core/persist`.

## AT-30 Verified fragments preserved across all recovery paths

- Preconditions: a store holding N verified fragments.
- Input: every recovery path — restart, partial write, corrupted
  document, failed migration, refused over-budget write.
- Steps: run each path; enumerate surviving fragments.
- Expected: every fragment verified before the event is present
  afterwards with its original SHA-256, except one whose own bytes were
  deliberately corrupted; byte accounting matches a recomputed sum in
  every case.
- Automation: harness.
- Milestone: M1.
- Evidence required: fragment inventory and byte accounting, before and
  after.
- Severity: S1.
- Runtime boundary: `core/store` + `core/persist`.

## AT-31 Deterministic restart behaviour

- Preconditions: an interrupted transfer with partial progress.
- Input: identical starting state, restarted twice.
- Steps: interrupt, restart, resume; capture the event log each time.
- Expected: both runs produce byte-identical event logs and identical
  resulting stores; only missing chunks are requested after restart.
- Automation: harness.
- Milestone: M1.
- Evidence required: SHA-256 of both event logs.
- Severity: S2.
- Runtime boundary: `core/persist` + `adapters/simulator`.

## AT-32 Error classification is complete and canonical

- Preconditions: the canonical taxonomy in `PROTOCOL_SPEC.md` §3.8.
- Input: one triggering condition per code.
- Steps: trigger each; capture code and classification.
- Expected: every raised code exists in the canonical enum; every enum
  member is either reached by a test or explicitly recorded as
  unreachable-by-design with a reason; each code carries exactly one
  terminal/retryable classification.
- Automation: harness.
- Milestone: M1.
- Evidence required: coverage matrix over the enum.
- Severity: S2.
- Runtime boundary: `core/errors`.

## AT-33 Retryable versus terminal failure behaviour

- Preconditions: the classification verified by AT-32.
- Input: a terminal failure re-offered with byte-identical input; a
  retryable failure re-offered after the blocking condition clears.
- Steps: offer, re-offer, compare.
- Expected: the terminal case fails identically every time with no state
  change; the retryable case succeeds once external state permits;
  neither mutates state on a failing attempt.
- Automation: harness.
- Milestone: M1.
- Evidence required: paired attempt logs with state snapshots.
- Severity: S2.
- Runtime boundary: `core/errors` + `core/store`.

## AT-34 Privacy and consent field compatibility

- Preconditions: `visibility` and `forwarding_consent` frozen per
  `PROTOCOL_SPEC.md` §3.2.
- Input: a legacy manifest using boolean `private`; a v1.0 manifest
  using `visibility`; malformed values of each.
- Steps: migrate the legacy shape; validate all; attempt forwarding.
- Expected: `private: true → visibility "private"`; `false` or absent
  `→ "public"`; malformed `visibility` → `SCHEMA_INVALID`; non-boolean
  `forwarding_consent` → `CONSENT_REQUIRED`; every AT-16 assertion still
  holds after migration.
- Automation: harness.
- Milestone: M1.
- Evidence required: migration log plus the AT-16 refusal matrix re-run.
- Severity: S2.
- Runtime boundary: `core/migrate` + `core/policy`.

## AT-35 `public_only` peer refusal

- Preconditions: `public_only` semantics frozen per `PROTOCOL_SPEC.md`
  §6.
- Input: a private object **with valid consent** targeted at a peer
  declaring `public_only: true`; the same object to an ordinary peer; a
  public object to the `public_only` peer.
- Steps: attempt forwarding in each case.
- Expected: the first is refused with `PEER_REFUSES_PRIVATE` before
  queueing and before transmission, with receiver storage unchanged; the
  second and third are permitted. Consent does not override
  `public_only`.
- Automation: harness.
- Milestone: M1.
- Evidence required: refusal evidence naming the failing clause.
- Severity: S2.
- Runtime boundary: `core/policy`.

## AT-36 Persistence schema upgrade end-to-end

- Preconditions: a populated vN store from a prior release.
- Input: the vN store opened by the current build.
- Steps: open, migrate, resume an in-progress transfer, restart, reopen.
- Expected: the upgrade is transparent to the caller; the in-progress
  transfer resumes without re-requesting verified chunks; the store is
  at the current version afterwards; a second open performs no further
  migration.
- Automation: harness.
- Milestone: M1.
- Evidence required: version before and after; resumed-chunk list.
- Severity: S2.
- Runtime boundary: `core/migrate` + `adapters/simulator`.

## AT-37 M0 regression and core/adapter isolation

- Preconditions: the M1 refactor complete.
- Input: the full M0 acceptance suite; a static import scan.
- Steps: run all M0 tests unmodified; scan `shongket_core` imports;
  re-run the deterministic CLI and metrics.
- Expected: all 125 M0 tests pass **unchanged**; `shongket_core` imports
  nothing from `adapters/` and nothing outside the standard library; CLI
  and metrics hashes match the values recorded in the M0 harness
  evidence, or any change is separately justified and re-approved.
- Automation: harness.
- Milestone: M1.
- Evidence required: test counts, import-scan output, both hashes.
- Severity: S1.
- Runtime boundary: whole package.

## Milestone 1 forwarding-admission coverage

The six clauses of the M1 admission rule (`PROTOCOL_SPEC.md` §6) map to
tests as follows. No clause is left untested:

| Clause | Refusal code | Covered by |
|---|---|---|
| Expiry | `EXPIRED` | AT-11 (M0), AT-32 |
| Hop limit | `HOP_LIMIT` | AT-32, AT-33 |
| Copy budget | `COPY_BUDGET` | AT-32, AT-33 |
| Human confirmation | `HUMAN_CONFIRMATION_MISSING` | AT-02 (M0), AT-32 |
| Consent | `CONSENT_REQUIRED` | AT-16 (M0), AT-34 |
| Peer `public_only` | `PEER_REFUSES_PRIVATE` | AT-35 |

---

## Test-count inventory

Milestone 0 figures below are unchanged; the Milestone 1 catalogue is
counted separately so no M0 classification is disturbed.

- **Total acceptance tests:** 37 (AT-01 … AT-37)
  - Milestone 0 catalogue: 21 (AT-01 … AT-21)
  - Milestone 1 catalogue: 16 (AT-22 … AT-37), PROPOSED
- **S1 tests across all milestone scopes:** 20 within AT-01 … AT-21,
  plus AT-30 and AT-37 in the M1 catalogue
- **S1 tests within Milestone 0 scope:** 17
- **Milestone 0 blocking tests:** 18
- **Milestone 1 blocking tests:** 16 (all of AT-22 … AT-37; 14 at S2,
  and AT-30 and AT-37 at S1 because they protect M0 evidence already
  earned)

> The 18 Milestone 0 blocking tests comprise the 17 S1 tests in the M0
> scope (AT-01 … AT-11, AT-15, AT-16, AT-17, AT-18, AT-20, AT-21) plus
> AT-12 as the M0-blocking S2 unit-level storage-budget test. AT-12 is
> included as blocking because its rule must be enforced even though its
> on-device effect is later (M5+).
>
> The 20 S1 tests across all milestone scopes add AT-13 (permissions,
> M5+) and AT-19 (demo readiness, M9), both of which are release-blocking
> but outside M0.

---

## Milestone 0 harness evidence

Recorded from an actual run of the M0 harness. The test definitions
above are unchanged; this section only records results.

**Run summary:** 125 tests collected, **125 passed, 0 failed, 0
skipped**. Modules live in `app/simulator/tests/`. Each module was also
run in isolation and passed independently.

Deterministic outputs, verified by re-running and comparing SHA-256:

- CLI event log: `D5AC79B18B6B3329A2788CDCCF45A92D10534639B20079039D1902D7F82CB4DF` (3114 bytes)
- serialized metrics: `E10E11D4AEF1788E92CC907060C48CA06A3E76913C2BDD58ABF43858B8891B28` (1580 bytes)

All results are **simulated** protocol behaviour between in-process
peers (D-012). Nothing here is a real-device, radio or wall-clock
measurement.

| AT ID | Test module | Result | Evidence summary |
|---|---|---|---|
| AT-01 | `test_at01_capsule_before_media.py` | PASS (2) | Priority-order event log: signal plane precedes media plane for the same object |
| AT-02 | `test_at02_human_confirmation.py` | PASS (4) | `CAPSULE_REJECTED` on `human_confirmed=false`; nothing scheduled, sent or stored |
| AT-03 | `test_at03_object_identity.py` | PASS (4) | Same bytes yield the same CID across two senders; `object_id = SHA-256(source bytes)` |
| AT-04 | `test_at04_progressive_layers.py` | PASS (4) | Planner log orders capsule → thumb → preview → standard → original; no fragment-key collision |
| AT-05 | `test_at05_critical_preemption.py` | PASS (2) | `PREEMPTION_LOGGED`; bulk pauses and resumes; measured preemption latency 1 tick |
| AT-06 | `test_at06_interrupted_transfer.py` | PASS (2) | `TRANSFER_INTERRUPTED` then `TRANSFER_RESUMED`; only missing chunks re-requested |
| AT-07 | `test_at07_restart_recovery.py` | PASS (6) | Snapshot round-trip; 7 of 21 verified chunks survive restart and transfer completes |
| AT-08 | `test_at08_multi_peer_completion.py` | PASS (6) | Completion from 2 distinct peer IDs (`peer-A`, `peer-B`); overlap not re-requested; reconstructed SHA-256 equals the manifest representation hash |
| AT-09 | `test_at09_dedup.py` | PASS (3) | Second store is a no-op; duplicate counter increments, byte usage does not |
| AT-10 | `test_at10_corruption.py` | PASS (3) | 3 tampered chunks rejected on hash mismatch; all 13 valid chunks still accepted afterwards |
| AT-11 | `test_at11_expiry.py` | PASS (8) | Boundary covered at tick < = > expiry; at and past expiry the queue admits 0 items and `FORWARD_REFUSED` is logged with no storage mutation |
| AT-12 | `test_at12_storage_budget.py` | PASS (14) | Exact-fit accepted, +1 byte refused with `out_of_budget` and quota values logged; duplicate, corrupted and schema-invalid chunks consume no capacity; accounting survives restart |
| AT-15 | `test_at15_manual_fallback.py` | PASS (12) | Structured manual form returned for every canonical model condition; `MODEL_FALLBACK` logged with `ai_output_present=false`; no model loaded, downloaded or called |
| AT-16 | `test_at16_private_consent.py` | PASS (13) | Private object without explicit consent refused before scheduling; `CONSENT_REJECTED` is the only event emitted; public content unaffected |
| AT-17 | `test_at17_oversized_payload.py` | PASS (17) | Exact-limit accepted and +1 byte rejected with `ProtocolError` code `PAYLOAD_TOO_LARGE` at all four canonical limits (capsule 4096 B, manifest 32768 B, fragment descriptor 512 B, transport frame 1048576 B); checked before parse, scheduling, transmission and persistence |
| AT-18 | `test_at18_metrics.py` | PASS (12) | Metrics computed from event log, store counters and chunk plans; repeated runs byte-identical; unmeasurable metrics declared, not fabricated |
| AT-20 | `test_at20_schema_rejection.py` | PASS (8) | `SCHEMA_INVALID` raised; scheduler queue, fragment map, store counters and event log all verified unchanged |
| AT-21 | `test_at21_source_preservation.py` | PASS (5) | Source-media hash identical before and after; capsule references the source rather than replacing it |

### Caveats carried forward

These qualify the rows above and are not resolved by this run:

- **AT-12** implements the **M0 rule** — deterministic byte accounting
  and refusal with the canonical `out_of_budget` status. The device-side
  **eviction effect** remains later-milestone work, consistent with this
  test's own milestone split ("M0 (rule), M5+ (effect)").
- **AT-16** was run against the provisional manifest fields `private`
  and `forwarding_consent`. Those names have since been frozen for M1 as
  `visibility` (a `"public" | "private"` enum) and a strictly-boolean
  `forwarding_consent` — see `PROTOCOL_SPEC.md` §3.2. The M0 result
  above stands as recorded; AT-34 is the M1 test that the migration
  preserves every AT-16 assertion.
- **AT-18** reports timing in deterministic simulator ticks and marks
  throughput in bytes/second, peak memory, energy use and AI inference
  latency as unmeasured rather than fabricating them.

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
