# Shongket — Acceptance Tests (Draft 1)

Canonical acceptance specification and evidence catalogue. Each test
defines preconditions, input, steps, expected result, automation level,
milestone, evidence and failure severity.

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

**Status: COMPLETE.** These are the M1-blocking catalogue approved in
`M1_SCOPE_FREEZE.md`. AT-22 through AT-37 are implemented and passing;
the evidence below records 242 M1 tests plus the 125-test M0 regression
gate. `IMPLEMENTATION_STATUS` is `APPROVED_FOR_MILESTONE_1`.

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

## Milestone 1 harness evidence

Recorded from actual runs. **All 16 M1-blocking acceptance IDs
(AT-22 … AT-37) are implemented and passing.** Milestone 1 is COMPLETE;
`IMPLEMENTATION_STATUS` remains `APPROVED_FOR_MILESTONE_1` and no later
milestone is approved or started.

Modules implemented: `shongket_core/` — `errors.py`, `version.py`,
`codec.py`, `schema.py`, `store.py`, `persist.py`, `migrate.py`,
`policy.py`, `evidence.py`.

**Run summary (complete M1):** 242 M1 tests passed, plus the 125 M0
regression tests — **367 passed, 0 failed, 0 skipped**. Modules live in
`shongket_core/tests/`. Counts below are measured per module.

| AT ID | Test module | Result | Evidence summary |
|---|---|---|---|
| AT-22 | `test_at22_canonical_serialization.py` | PASS (41) | Encode→decode→encode byte-identical for capsule, manifest, fragment, a reversed-insertion-order manifest and a non-ASCII payload; each matched a committed golden SHA-256; verified identical in a freshly spawned process and across >1s of elapsed time; floats, non-finite constants, non-string keys, tuples, sets and bytes all rejected rather than coerced |
| AT-23 | `test_at23_minor_compatibility.py` | PASS (23) | Exact registered version accepted without any entry; **unregistered lower *and* higher minors both refused**; registered lower minor accepted and marked compatibility-based; registering `1.2` grants nothing to `1.1` or `1.3`; no leakage across families or majors; all 4 construction-order permutations produce equal registries and identical resolutions; legacy `…v1` resolves to `1.0` only and does not bypass registration when the exact version is later |
| AT-24 | `test_at24_unsupported_version.py` | PASS (34) | Unknown major, unknown-major-plus-malformed, and unregistered minor all rejected `VERSION_UNSUPPORTED`; the malformed case proves version resolution precedes structural parsing; 8 malformed identifier forms plus 10 leading/trailing whitespace forms — including trailing LF and CRLF — rejected; registry, payload and error detail unchanged across repeated attempts |
| AT-25 | `test_at25_29_36_migration.py` | PASS (32, shared with AT-29/36) | Two runs from identical starting bytes produce byte-identical migrated documents; every verified fragment preserved with matching SHA-256; a two-edge chain applies in order; migration output is path-independent |
| AT-26 | `test_at26_28_persistence.py` | PASS (19, shared with AT-27/28) | Interruption injected after temp write, after temp fsync, after replace and before parent-directory fsync; every reader sees a complete previous or complete new document, never a blend; temp artefacts cleaned; lock released after a crash; parent-directory sync outcome recorded, not skipped |
| AT-27 | `test_at26_28_persistence.py` | PASS (shared) | A truncated temp file is discarded and named in the recovery evidence; the previous durable snapshot loads intact; multiple stray temps all removed |
| AT-28 | `test_at26_28_persistence.py` | PASS (shared) | (a) corrupted document checksum quarantines the file — renamed aside, still readable on disk — and the last good snapshot loads; (b) a corrupted fragment under a valid document checksum drops only that fragment and preserves the other three |
| AT-29 | `test_at25_29_36_migration.py` | PASS (shared) | Failure injected mid-chain and during the durable write; the original document remains byte-identical and still at its old version; no partially migrated state visible; failure classified retryable |
| AT-30 | `test_at30_31_recovery.py` + `test_at25_29_36_migration.py` | PASS (11 + 1) | All five recovery paths — restart, partial write, corrupted document, failed migration, refused over-budget write — preserve every fragment with its original SHA-256; only the deliberately corrupted fragment is lost; byte accounting equals a recomputed sum in every case |
| AT-31 | `test_at30_31_recovery.py` | PASS (shared) | Two independent interrupt→restart→resume runs produce byte-identical evidence digests and identical stores; only the missing chunk indexes are requested; evidence is directory-independent |
| AT-32 | `test_at32_35_policy.py` | PASS (57, shared with AT-33/34/35) | All 16 enum members classified exactly once; 13 codes triggered by an executable reachability test; 3 recorded unreachable-by-design with reasons; error details deterministic and address-free |
| AT-33 | `test_at32_35_policy.py` | PASS (shared) | A terminal failure repeats identically three times with no state change; a retryable `OUT_OF_BUDGET` succeeds once capacity is freed; neither mutates state on the failing attempt |
| AT-34 | `test_at32_35_policy.py` | PASS (shared) | Legacy `private` maps to `visibility`; 8 malformed `visibility` values are `SCHEMA_INVALID`; 6 non-boolean consent values are `CONSENT_REQUIRED`; the full AT-16 refusal matrix re-runs green after migration |
| AT-35 | `test_at32_35_policy.py` | PASS (shared) | A private object **with valid consent** is refused by a `public_only` peer with `PEER_REFUSES_PRIVATE` before queueing; the same object reaches an ordinary peer; a public object reaches the `public_only` peer; the manifest is unmutated |
| AT-36 | `test_at25_29_36_migration.py` | PASS (shared) | A v0.9 store upgrades transparently, resumes without re-requesting the three migrated chunks, ends at v1.0, and a second open performs no further migration; repeated upgrades are byte-idempotent |
| AT-37 | `test_at37_conformance.py` | PASS (20) | All 125 M0 tests pass unchanged in a subprocess; M0 CLI and metrics hashes unchanged; Slice-1 golden vectors unchanged; AST scan proves the core imports nothing from `app/`, `adapters/` or outside the standard library; `git diff` confirms `app/` untouched |
| — | `test_public_exports.py` | PASS (5) | Every `__all__` name reachable after a plain `import shongket_core`, verified in a fresh process; import has no side effects; `canonical_registry()` returns equal but independent instances |

Golden vectors live in `shongket_core/testdata/golden_vectors.json`
(Slice 1) and `m1_conformance_vectors.json` (Slice 5). Both were
computed independently of `shongket_core` from the canonical rules and
are committed as expected output; the tests compare against them and
never regenerate them.

| Vector | Bytes | SHA-256 |
|---|---|---|
| capsule v1.0 | 555 | `8b0a3231…` |
| content v1.0 | 464 | `d61e057b…` |
| fragment v1.0 | 283 | `8eea53cc…` |
| non-ASCII capsule | 297 | `028d7ab7…` |
| snapshot envelope v1.0 | 1365 | `4cfa18dd…` |
| snapshot envelope v0.9 | 1365 | `b8a72f83…` |
| snapshot, reversed fragment order | 1365 | `4cfa18dd…` (identical) |
| manifest identity excl. forwarding state | — | `dad9f3c6…` |

Preserved M0 evidence, re-verified by AT-37: CLI
`D5AC79B1…2CB4DF` (3114 bytes) and metrics `E10E11D4…891B28`
(1580 bytes), both unchanged.

### Implementation notes

`shongket_core` is standard-library only. An AST scan in AT-37 proves it
imports nothing from `app/`, `adapters/` or any third-party package, and
`git diff` confirms `app/simulator/` was not modified by any M1 slice.

`shongket_core.errors.ProtocolError` and
`app.simulator.validation.ProtocolError` still coexist. Unifying the two
*types* would require editing M0 source, which AT-37 forbids; both draw
their `code` from the same canonical vocabulary, so the semantics are
already unified. Collapsing the types belongs with the M2 adapter work.

`STORE_LOCKED` (retryable) was added to the canonical enum in Slice 2
for advisory single-writer lock contention, following the precedent of
`SNAPSHOT_INVALID` and `SNAPSHOT_CORRUPTED`. It is recorded in
`PROTOCOL_SPEC.md` §3.8.

Parent-directory `fsync` is a POSIX facility. On Windows it cannot be
performed, so the outcome is **recorded as evidence** (`"synced"` or
`"unsupported"`) rather than silently skipped, and AT-26 asserts the
recorded value matches the platform's capability. No test is skipped on
any platform.

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

# Remaining-project acceptance tests (AT-38 … AT-78)

**Status: APPROVED SPECIFICATION. None of these is implemented and none
is passing.** The descendant approval record authorizes only the
software/evidence-tooling portions named in `PRODUCT_DECISIONS.md`.
Physical-device, real-radio and field definitions are gates, not
authorization or success claims.

Automation levels used below:

- `AUTOMATED_LOCAL` — normal suite on a developer machine;
- `TWO_PROCESS` — two real OS processes on one machine;
- `JVM_OR_EMULATOR` — Android JVM or emulator, with no radio claim;
- `PHYSICAL_DEVICE` — real handset evidence without a radio claim;
- `REAL_RADIO` — real handsets communicating over the named radio;
- `FIELD_ONLY` — a real partial-connectivity environment.

Only *automated local*, *two-process* and *emulator* tests can gate a
software-complete release candidate. Physical-device and field-only
tests gate field validation and must never be claimed from a simulator
or emulator run.

## AT-38 Two-process framed transfer

- Requirement: the M1 core exchanges protocol objects across two real OS processes (M2 objective).
- Preconditions: two processes started from the same build; a shared loopback or stdio channel.
- Input: a complete object — capsule, manifest and every fragment.
- Steps: start both processes; transfer; verify on the receiver.
- Expected result: the receiver reconstructs the representation; the SHA-256 equals the manifest hash; frames respect the 1048576-byte transport limit.
- Automation level: TWO_PROCESS.
- Milestone: M2.
- Severity: S1.
- Evidence: per-process event logs and the reconstructed hash.
- Runtime boundary: `adapters/process`.

## AT-39 Cross-language and cross-process conformance parity

- Requirement: every implementation of the core produces byte-identical canonical output (D-RS-02).
- Preconditions: the committed golden vectors.
- Input: every vector in `shongket_core/testdata/`.
- Steps: encode each vector in the Python core, in the sending process, in the receiving process, and in the Kotlin core once it exists; compare bytes and SHA-256.
- Expected result: all implementations agree byte-for-byte; a divergence fails the build and names the vector.
- Automation level: AUTOMATED_LOCAL, TWO_PROCESS, JVM_OR_EMULATOR.
- Milestone: M2, M3.
- Severity: S1.
- Evidence: per-implementation SHA-256 table.
- Runtime boundary: `shongket_core/codec`, `android/core-conformance`.

## AT-40 Two-process interruption and resume

- Requirement: an interrupted cross-process transfer resumes without re-sending verified chunks.
- Preconditions: a transfer in progress across two processes.
- Input: the channel is severed mid-transfer, then restored.
- Steps: interrupt; reconnect; resume; enumerate requests.
- Expected result: only missing chunk indexes are requested; verified chunks are retained; the object completes; no duplicate is stored.
- Automation level: TWO_PROCESS.
- Milestone: M2.
- Severity: S1.
- Evidence: resume request list and the store inventory.
- Runtime boundary: `adapters/process`, `shongket_core/store`.

## AT-41 Process crash and restart across the boundary

- Requirement: a process killed mid-transfer recovers from durable state (extends AT-31 across processes).
- Preconditions: a partially completed transfer with a durable snapshot.
- Input: the receiving process is terminated without cleanup, then restarted.
- Steps: kill; restart; reopen the store; resume.
- Expected result: verified fragments survive; no partial snapshot is loaded; the resumed run requests only missing chunks; two identical runs produce identical evidence digests.
- Automation level: TWO_PROCESS.
- Milestone: M2.
- Severity: S1.
- Evidence: pre/post fragment inventory and evidence digests.
- Runtime boundary: `shongket_core/persist`, `adapters/process`.

## AT-42 Transport adapter interface conformance

- Requirement: every adapter satisfies the frozen transport contract (`REMAINING_SCOPE.md` §6).
- Preconditions: the simulated adapter and any further adapter.
- Input: the shared adapter conformance suite.
- Steps: run discovery, capability exchange, connect, send, receive, interrupt, close against each adapter.
- Expected result: identical observable behaviour and identical event sequences from every adapter; capability reports are complete.
- Automation level: AUTOMATED_LOCAL, JVM_OR_EMULATOR.
- Milestone: M3.
- Severity: S1.
- Evidence: per-adapter event sequence comparison.
- Runtime boundary: `adapters/transport_sim`, `android/data-transport`.

## AT-43 Capability negotiation and graceful downgrade

- Requirement: peers agree on a usable capability set, or decline cleanly.
- Preconditions: two peers with differing `max_payload`, transports and `public_only`.
- Input: capability exchange before transfer.
- Steps: exchange; negotiate; attempt a transfer that exceeds the peer's limit.
- Expected result: the negotiated frame size never exceeds the lower `max_payload`; an over-limit frame is refused with `PAYLOAD_TOO_LARGE` before transmission; an incompatible pair declines without crashing.
- Automation level: AUTOMATED_LOCAL, JVM_OR_EMULATOR.
- Milestone: M3.
- Severity: S1.
- Evidence: negotiated parameters and the refusal record.
- Runtime boundary: `shongket_core/policy`, transport adapters.

## AT-44 Adapter isolation — transports make no policy decisions

- Requirement: D-RS-04; admission stays in the core.
- Preconditions: the full adapter set.
- Input: a static scan plus a behavioural probe.
- Steps: scan adapter sources for references to expiry, consent, visibility, hop, copy or admission; drive an adapter with an object that the core would refuse.
- Expected result: no adapter references a policy field; the refusal originates in the core and is identical regardless of adapter; the core imports no adapter.
- Automation level: AUTOMATED_LOCAL.
- Milestone: M3.
- Severity: S1.
- Evidence: scan output and paired refusal records.
- Runtime boundary: whole package.

## AT-45 Android lifecycle and background survival

- Requirement: transfers survive backgrounding, configuration change and process death.
- Preconditions: an Android build with a transfer in progress.
- Input: background the app; rotate; trigger process death; return.
- Steps: perform each event; observe state.
- Expected result: no crash; the transfer continues or resumes from durable state; UI state is restored; no duplicate fragments; no work is silently abandoned.
- Automation level: JVM_OR_EMULATOR.
- Milestone: M3.
- Severity: S1.
- Evidence: lifecycle event log and the fragment inventory.
- Runtime boundary: `android/app`, `android/data-persistence`.

## AT-46 Permission refusal degrades gracefully

- Requirement: refusal is a supported state (D-RS-12; extends AT-13).
- Preconditions: an Android build; every runtime permission refusable.
- Input: deny each permission individually and all together.
- Steps: deny; use the app; observe.
- Expected result: no crash and no dead end; the dependent feature is disabled with a plain-language reason; unaffected features keep working; nothing is retried silently.
- Automation level: JVM_OR_EMULATOR.
- Milestone: M3, M7.
- Severity: S1.
- Evidence: per-permission screen state and the reason string.
- Runtime boundary: `android/app`.

## AT-47 Real-radio discovery and session establishment

- Requirement: the provisional transport discovers and connects on real hardware (smoke-test gate 1, 2).
- Preconditions: two physical handsets, radios enabled, no internet.
- Input: both devices running the app in range.
- Steps: discover; connect; exchange capabilities.
- Expected result: discovery succeeds offline; a session is established on the intended demo phones.
- Automation level: REAL_RADIO.
- Milestone: M3.
- Severity: S1.
- Evidence: device model list and session logs.
- Runtime boundary: `android/data-transport`.

## AT-48 Real-radio interruption and reconnection

- Requirement: smoke-test gate criteria 3, 4, 5.
- Preconditions: an established real-radio session with a large transfer running.
- Input: physical separation beyond range, then return.
- Steps: transfer; separate; return; resume.
- Expected result: interruption is detected, not hung; reconnection succeeds; the transfer resumes without re-sending verified chunks; the large transfer completes.
- Automation level: REAL_RADIO.
- Milestone: M3.
- Severity: S1.
- Evidence: interruption and resume timestamps, resumed chunk list.
- Runtime boundary: `android/data-transport`.

## AT-49 Vendor and OEM compatibility

- Requirement: smoke-test gate criterion 2 across the demo fleet.
- Preconditions: the intended demo handsets, multiple vendors.
- Input: the same build on each device.
- Steps: run discovery, transfer and permission flows on each pairing.
- Expected result: every intended demo pairing works, or the failure is recorded per device with its OEM and OS version; no undocumented device is claimed as supported.
- Automation level: REAL_RADIO.
- Milestone: M3.
- Severity: S1.
- Evidence: a per-device compatibility matrix.
- Runtime boundary: `android/data-transport`.

## AT-50 Transport smoke-test gate — ten consecutive cold runs

- Requirement: smoke-test gate criterion 7; unlocks the provisional transport.
- Preconditions: AT-47, AT-48, AT-49 passing.
- Input: ten cold starts of the full discovery-to-transfer scenario.
- Steps: run ten times from a cold app start; record every outcome.
- Expected result: ten consecutive successes. Any failure fails the gate and the transport remains provisional.
- Automation level: REAL_RADIO.
- Milestone: M3.
- Severity: S1.
- Evidence: ten timestamped run records.
- Runtime boundary: `android/data-transport`.

## AT-51 Media capture produces the canonical representation set

- Requirement: `MEDIA_PIPELINE.md` representations from a real source.
- Preconditions: a capture source or a committed synthetic fixture.
- Input: one photo, one short video, one audio clip, one text note.
- Steps: capture or load; build representations; chunk; hash.
- Expected result: `thumb`, `preview`, `standard` and `original` are produced where the modality supports them; each is fixed-size chunked and hashed; a representation that cannot be produced is reported unavailable, never silently omitted.
- Automation level: AUTOMATED_LOCAL, JVM_OR_EMULATOR.
- Milestone: M4.
- Severity: S1.
- Evidence: representation manifest and per-chunk hashes.
- Runtime boundary: `android/media`, `shongket_core/media`.

## AT-52 Progressive delivery ordering

- Requirement: D-007 order in a real transfer.
- Preconditions: an object with all four representations queued.
- Input: a transfer to a receiver holding nothing.
- Steps: transfer; record arrival order.
- Expected result: capsule, then manifest, then thumb, then preview, then standard, then original; the receiver can act on the capsule before any media completes.
- Automation level: AUTOMATED_LOCAL, TWO_PROCESS, JVM_OR_EMULATOR.
- Milestone: M4.
- Severity: S1.
- Evidence: ordered arrival log.
- Runtime boundary: `shongket_core/policy`.

## AT-53 Preview playback and unavailable-representation status

- Requirement: the UI shows progressive state honestly.
- Preconditions: an object whose `preview` is present and whose `original` is incomplete.
- Input: open the object.
- Steps: view during and after transfer.
- Expected result: the preview is viewable; the incomplete representation is labelled incomplete, never presented as complete; an unproducible representation shows a clear unavailable status.
- Automation level: JVM_OR_EMULATOR.
- Milestone: M4.
- Severity: S1.
- Evidence: UI state snapshots.
- Runtime boundary: `android/ui`.

## AT-54 Source preservation through capture and transcode

- Requirement: AT-21 extended to the real pipeline.
- Preconditions: known original bytes.
- Input: capture, build representations, transfer, reconstruct.
- Steps: hash the source before and after every stage.
- Expected result: the original bytes and hash are unchanged at every stage; `object_id` still equals SHA-256 of the original source; no derived representation overwrites the original.
- Automation level: AUTOMATED_LOCAL, JVM_OR_EMULATOR.
- Milestone: M4.
- Severity: S1.
- Evidence: before/after source hashes per stage.
- Runtime boundary: `android/media`, `shongket_core`.

## AT-55 Progressive transfer on real devices

- Requirement: M4 on hardware.
- Preconditions: two physical devices, real radio, a real captured object.
- Input: a full progressive transfer.
- Steps: transfer; record arrival order and completion.
- Expected result: the D-007 order holds over a real radio; the original reconstructs and its hash matches.
- Automation level: REAL_RADIO.
- Milestone: M4.
- Severity: S1.
- Evidence: ordered arrival log and reconstruction hash.
- Runtime boundary: `android/data-transport`, `android/media`.

## AT-56 Real-device multi-peer completion

- Requirement: M5 objective; ordinary chunks from ≥ 3 physical peers.
- Preconditions: three or more physical devices, each holding a different partial subset; no peer holds the whole object.
- Input: a receiver requesting missing chunks.
- Steps: encounter each peer; request only missing chunks; reconstruct.
- Expected result: the object completes using chunks from at least two distinct peer IDs; no chunk is fetched twice; no coded reconstruction is involved.
- Automation level: REAL_RADIO.
- Milestone: M5.
- Severity: S1.
- Evidence: fragment-source report with peer IDs.
- Runtime boundary: `android/data-transport`, `shongket_core/store`.

## AT-57 Real-device reconstruction hash verification

- Requirement: M0 criterion 8 on hardware.
- Preconditions: AT-56 completed.
- Input: the reconstructed representation.
- Steps: hash the reconstruction; compare with the manifest.
- Expected result: SHA-256 equals the manifest representation hash exactly.
- Automation level: REAL_RADIO.
- Milestone: M5.
- Severity: S1.
- Evidence: reconstruction hash beside the manifest hash.
- Runtime boundary: `shongket_core/media`.

## AT-58 Semantic extractor interface with a deterministic double

- Requirement: D-RS-09; the interface is testable without a model.
- Preconditions: the `TestDouble` extractor.
- Input: the same source twice.
- Steps: extract; extract again; compare.
- Expected result: identical suggestions both times; no network access; no model file read; no download attempted during any automated test.
- Automation level: AUTOMATED_LOCAL.
- Milestone: M6.
- Severity: S1.
- Evidence: paired extraction outputs and a network-access assertion.
- Runtime boundary: `android/semantic`.

## AT-59 The app is fully usable with no model

- Requirement: D-011; AT-15 extended to the real app.
- Preconditions: the `Unavailable` extractor, which is the default.
- Input: create a capsule manually.
- Steps: open the capture flow; complete the manual form; confirm; publish.
- Expected result: the structured manual form is presented; the capsule is created, confirmed and scheduled; nothing is blocked; no error is surfaced as a failure.
- Automation level: AUTOMATED_LOCAL, JVM_OR_EMULATOR.
- Milestone: M6.
- Severity: S1.
- Evidence: manual-path event log.
- Runtime boundary: `android/semantic`, `android/ui`.

## AT-60 Generated text never replaces source evidence

- Requirement: AGENTS.md scope rule; D-003.
- Preconditions: an extractor producing a suggestion.
- Input: a source object with a suggested capsule.
- Steps: accept the suggestion; inspect stored state.
- Expected result: the original media bytes and hash are unchanged; the suggestion is stored as a capsule referencing the source, never in place of it; `human_confirmed` is required before publish; an unconfirmed suggestion is never forwarded.
- Automation level: AUTOMATED_LOCAL.
- Milestone: M6.
- Severity: S1.
- Evidence: source hash before/after and the capsule linkage.
- Runtime boundary: `android/semantic`, `shongket_core/policy`.

## AT-61 Model packaging and resource limits

- Requirement: `MODEL_EVALUATION_PLAN.md` thresholds on device profiles.
- Preconditions: a benchmark-selected model on target hardware.
- Input: extraction on each device tier.
- Steps: run; measure memory, latency and storage.
- Expected result: the model stays within declared limits for its tier, or the tier is recorded as unsupported; exceeding a limit falls back to the manual form rather than degrading the app.
- Automation level: PHYSICAL_DEVICE.
- Milestone: M6.
- Severity: S2.
- Evidence: per-tier resource measurements.
- Runtime boundary: `android/semantic`.

## AT-62 Bangla extraction quality threshold

- Requirement: `MODEL_EVALUATION_PLAN.md`; separate from protocol acceptance.
- Preconditions: the benchmark corpus on target hardware.
- Input: the Bangla evaluation set.
- Steps: run the benchmark; score against declared thresholds.
- Expected result: declared thresholds are met, or the model is rejected and the manual form remains the path. This test never gates a protocol acceptance test.
- Automation level: PHYSICAL_DEVICE.
- Milestone: M6.
- Severity: S2.
- Evidence: benchmark scores against thresholds.
- Runtime boundary: `android/semantic`.

## AT-63 Background restart mid-transfer

- Requirement: M7 resilience; AT-31 on Android.
- Preconditions: a transfer in progress in a foreground service.
- Input: the OS terminates the process.
- Steps: terminate; relaunch; observe.
- Expected result: durable state is intact; the transfer resumes from the last verified chunk; no duplicate; the user is not asked to restart manually.
- Automation level: JVM_OR_EMULATOR.
- Milestone: M7.
- Severity: S1.
- Evidence: pre/post fragment inventory.
- Runtime boundary: `android/app`, `android/data-persistence`.

## AT-64 Storage pressure in the application

- Requirement: AT-12 rule surfaced in the app; still rejection-only.
- Preconditions: a store near its byte budget.
- Input: an object that does not fit.
- Steps: attempt ingest; inspect state and UI.
- Expected result: refused with `OUT_OF_BUDGET` before mutation; existing fragments intact; byte accounting unchanged; the user sees a clear storage message; **no eviction occurs**.
- Automation level: AUTOMATED_LOCAL, JVM_OR_EMULATOR.
- Milestone: M7.
- Severity: S1.
- Evidence: quota values before and after, plus the UI message.
- Runtime boundary: `shongket_core/store`, `android/ui`.

## AT-65 Low-battery degradation

- Requirement: M7 resilience; `PROTOCOL_SPEC.md` §6 factor 8.
- Preconditions: a real device below the battery threshold.
- Input: a queued mixed-priority transfer.
- Steps: drop below threshold; observe scheduling.
- Expected result: bulk media is deferred, the signal plane keeps flowing, nothing is dropped or corrupted, and the behaviour is reported to the user.
- Automation level: PHYSICAL_DEVICE.
- Milestone: M7.
- Severity: S2.
- Evidence: scheduling log at each battery state.
- Runtime boundary: `android/app`, `shongket_core/policy`.

## AT-66 Integrated denied-permission path

- Requirement: AT-13 and AT-46 in the assembled app.
- Preconditions: the full app with permissions denied.
- Input: attempt a full capture-to-transfer flow.
- Steps: run the flow with each permission denied.
- Expected result: the flow stops at the first genuinely blocked step with a clear reason; already-created content is not lost; the app remains usable for unaffected functions.
- Automation level: JVM_OR_EMULATOR.
- Milestone: M7.
- Severity: S1.
- Evidence: per-permission flow transcript.
- Runtime boundary: `android/app`.

## AT-67 Malformed-input resistance at the application boundary

- Requirement: R-12; extends AT-20 and AT-17 to real inputs.
- Preconditions: the assembled app.
- Input: malformed JSON, invalid UTF-8, oversized frames, truncated frames, duplicate keys, deeply nested payloads, wrong-type fields, unknown versions.
- Steps: feed each through the transport boundary.
- Expected result: every input is rejected with a canonical code before parse or mutation; no crash; no partial state; no unbounded allocation; the app stays responsive.
- Automation level: AUTOMATED_LOCAL, JVM_OR_EMULATOR.
- Milestone: M7.
- Severity: S1.
- Evidence: per-input rejection codes and a state-unchanged assertion.
- Runtime boundary: `shongket_core/validate`, transport adapters.

## AT-68 Private-content consent user experience

- Requirement: D-M1-01/02/03 surfaced in the UI; AGENTS.md consent rule.
- Preconditions: a private object.
- Input: an attempt to forward it.
- Steps: attempt without consent; grant consent explicitly; attempt to a `public_only` peer.
- Expected result: forwarding is blocked until the user consents explicitly; consent is a deliberate action, never a default or a pre-checked control; a `public_only` peer is refused even with consent; the reason is shown plainly.
- Automation level: JVM_OR_EMULATOR.
- Milestone: M7.
- Severity: S1.
- Evidence: UI state and the refusal record naming the failing clause.
- Runtime boundary: `android/ui`, `shongket_core/policy`.

## AT-69 Local data protection and key storage

- Requirement: D-RS-10, D-RS-11.
- Preconditions: an installed app holding content and a key.
- Input: inspection of on-device storage and backup configuration.
- Steps: inspect app storage, the manifest backup flag and the key location.
- Expected result: content lives in app-private storage; `allowBackup=false`; keys are held via the platform keystore abstraction and never in source, assets or preferences; no secret appears in the repository.
- Automation level: AUTOMATED_LOCAL, JVM_OR_EMULATOR.
- Milestone: M7.
- Severity: S1.
- Evidence: storage listing, manifest flag and scan output.
- Runtime boundary: `android/security`.

## AT-70 Diagnostic export contains no sensitive content

- Requirement: D-RS-13; AGENTS.md logging rule.
- Preconditions: a session with capsules, media and peers.
- Input: a user-initiated diagnostic export.
- Steps: export; inspect every field.
- Expected result: the export contains identifiers, counters, codes and ticks only; it contains no capsule text, media bytes, location text, peer-identifying data or key material; export is explicit and never automatic.
- Automation level: AUTOMATED_LOCAL, JVM_OR_EMULATOR.
- Milestone: M7, M9.
- Severity: S1.
- Evidence: the exported document and a field-level scan.
- Runtime boundary: `android/diagnostics`.

## AT-71 Forged metadata and transport impersonation rejected

- Requirement: `PROTOCOL_SPEC.md` §8.
- Preconditions: development signing keys; a signed manifest.
- Input: a manifest signed by an unknown key; a manifest with a valid signature over altered content; a peer claiming another peer's identity.
- Steps: offer each.
- Expected result: each is rejected with `SIGNATURE_INVALID`; nothing is stored or forwarded; the adapter carries no trust of its own.
- Automation level: AUTOMATED_LOCAL.
- Milestone: M7.
- Severity: S1.
- Evidence: rejection records with codes.
- Runtime boundary: `android/security`, `shongket_core/validate`.

## AT-72 Replay and duplicate-flood resistance

- Requirement: R-13, R-22.
- Preconditions: a peer replaying previously accepted objects and flooding duplicates.
- Input: repeated identical objects and fragments at a high rate.
- Steps: replay an expired object; replay a stored object; flood duplicate fragments.
- Expected result: expired replays refused with `EXPIRED`; duplicates deduplicated with no extra storage; per-peer caps engage; memory and storage stay bounded; the app stays responsive.
- Automation level: AUTOMATED_LOCAL.
- Milestone: M7.
- Severity: S1.
- Evidence: dedup counters, per-peer caps and resource ceilings.
- Runtime boundary: `shongket_core/store`, `shongket_core/policy`.

## AT-73 Downgrade attempts rejected

- Requirement: D-M1-05; R-24.
- Preconditions: the schema registry at its current versions.
- Input: payloads at an unknown major, an unregistered minor, and a snapshot newer than the build.
- Steps: offer each.
- Expected result: all refused with `VERSION_UNSUPPORTED`; no partial decode; no silent downgrade; no state change.
- Automation level: AUTOMATED_LOCAL.
- Milestone: M7.
- Severity: S1.
- Evidence: rejection records with declared versions.
- Runtime boundary: `shongket_core/schema`, `shongket_core/migrate`.

## AT-74 Measured benchmark results replace empty tables

- Requirement: M8 objective; DR-EXP-01.
- Preconditions: M7 complete on real devices.
- Input: the `EXPERIMENT_PLAN.md` metric set.
- Steps: run each scenario on real hardware; record measurements.
- Expected result: every "hypothesis" target has a measured number with a confidence interval or an explicit failure note; unmeasured cells stay `UNMEASURED`, never zero; no simulator value is presented as a device measurement.
- Automation level: PHYSICAL_DEVICE.
- Milestone: M8.
- Severity: S1.
- Evidence: filled result tables with device and run metadata.
- Runtime boundary: whole system.

## AT-75 Reproducible release build

- Requirement: D-RS-14.
- Preconditions: a clean checkout at a known commit.
- Input: two independent builds from that commit.
- Steps: build twice; compare artifacts.
- Expected result: byte-identical artifacts apart from the signature block; the build needs no network access for application code; the build script is committed; the development signing config is clearly marked non-production.
- Automation level: AUTOMATED_LOCAL.
- Milestone: M9.
- Severity: S1.
- Evidence: two artifact hashes and the diff of any variance.
- Runtime boundary: build system.

## AT-76 Install, upgrade and state preservation

- Requirement: M9 release readiness; D-M1-06 migration on device.
- Preconditions: a previous version installed with content and in-progress transfers.
- Input: an upgrade install of the new version.
- Steps: install the old build; create state; upgrade; reopen.
- Expected result: the upgrade is transparent; persisted state migrates forward; verified fragments survive; in-progress transfers resume; a second launch performs no further migration; a failed migration rolls back and leaves the old state readable.
- Automation level: JVM_OR_EMULATOR.
- Milestone: M9.
- Severity: S1.
- Evidence: store version before and after, plus the fragment inventory.
- Runtime boundary: `android/data-persistence`, `shongket_core/migrate`.

## AT-77 Repeated demo reliability

- Requirement: M9 acceptance; smoke-test gate criterion 7 at demo scale.
- Preconditions: the demo script and the demo devices.
- Input: ten consecutive cold demo runs.
- Steps: run the scripted demo ten times from cold start.
- Expected result: ten consecutive successes, or the failure and its countermeasure are documented before any public demonstration.
- Automation level: REAL_RADIO.
- Milestone: M9.
- Severity: S1.
- Evidence: ten timestamped run records.
- Runtime boundary: whole system.

## AT-78 Field trial in a partial-connectivity environment

- Requirement: the field-validated release level; the product thesis.
- Preconditions: a real partial-connectivity setting, real participants, informed consent, and a completed manual release decision on trial conduct.
- Input: a scripted crisis-like scenario across separated participants.
- Steps: run the scenario; collect measurements and observations.
- Expected result: capsules reach separated participants; progressive media completes across encounters; measured results are recorded honestly, including failures. **No claim of field validation may be made from any simulator, emulator or lab run.**
- Automation level: FIELD_ONLY.
- Milestone: M9.
- Severity: S1.
- Evidence: field log, measurements and participant consent records.
- Runtime boundary: whole system.

## Remaining-scope classification summary

The category counts below are measured from the definitions. An ID may
appear in more than one category when the same requirement has separate
local, process and emulator proofs.

| Automation level | Acceptance IDs | Count |
|---|---|---:|
| `AUTOMATED_LOCAL` | AT-39, AT-42, AT-43, AT-44, AT-51, AT-52, AT-54, AT-58, AT-59, AT-60, AT-64, AT-67, AT-69, AT-70, AT-71, AT-72, AT-73, AT-75 | 18 |
| `TWO_PROCESS` | AT-38, AT-39, AT-40, AT-41, AT-52 | 5 |
| `JVM_OR_EMULATOR` | AT-39, AT-42, AT-43, AT-45, AT-46, AT-51, AT-52, AT-53, AT-54, AT-59, AT-63, AT-64, AT-66, AT-67, AT-68, AT-69, AT-70, AT-76 | 18 |
| `PHYSICAL_DEVICE` | AT-61, AT-62, AT-65, AT-74 | 4 |
| `REAL_RADIO` | AT-47, AT-48, AT-49, AT-50, AT-55, AT-56, AT-57, AT-77 | 8 |
| `FIELD_ONLY` | AT-78 | 1 |

**Software-complete blockers (28):** AT-38 through AT-46, AT-51
through AT-54, AT-58 through AT-60, AT-63, AT-64, AT-66 through AT-73,
AT-75 and AT-76. Every applicable `AUTOMATED_LOCAL`, `TWO_PROCESS` and
`JVM_OR_EMULATOR` assertion must pass alongside the existing 367 tests.

**Field-validation blockers (10):** AT-47 through AT-50, AT-55 through
AT-57, AT-65, AT-77 and AT-78. They require the declared device, radio
or field boundary and cannot be satisfied by a simulator or emulator.

**Non-blocking research and benchmark evidence (3):** AT-61, AT-62 and
AT-74 must be executed before making the corresponding model-resource,
Bangla-quality or device-benchmark claim. A negative measurement selects
the manual fallback or records an explicit limitation; it does not
invalidate protocol correctness or block the software-complete build.

### Legacy identifier mapping

`MILESTONES.md` previously cited placeholder identifiers that were never
defined. They now map to canonical IDs:

| Legacy | Canonical |
|---|---|
| `AT-PROG-1` … `AT-PROG-3` | AT-51, AT-52, AT-53 (with AT-54, AT-55) |
| `AT-MP-1` … `AT-MP-5` | AT-56, AT-57 |
| `AT-AI-1` … `AT-AI-4` | AT-58, AT-59, AT-60 (with AT-61, AT-62) |

# Separate BDIX domestic-hub acceptance (BH-01 … BH-12)

**Software status: IMPLEMENTED. Field status: NOT RUN.** This catalogue is
governed by `BDIX_HUB_SCOPE.md` and the exact separate approval record in
`PRODUCT_DECISIONS.md`. It does not alter the AT-01 through AT-78 counts or
convert software evidence into a cross-ISP/BDIX claim.

| ID | Software result | Evidence |
|---|---|---|
| BH-01 Cross-client exchange | PASS | WSGI test publishes from one simulated source address and fetches the same capsule from another |
| BH-02 Bounded strict schema | PASS | exact message/location limits, malformed JSON, duplicate/unknown fields, wrong types, unsupported versions, truncation and 8193-byte refusal |
| BH-03 Public confirmation gate | PASS | private, unconfirmed, non-boolean and non-consented requests refused before storage |
| BH-04 Durable restart | PASS | a newly created application opens the same SQLite file and retains capsule/cursor |
| BH-05 Idempotency and conflict | PASS | identical `client_id` replay returns one original row; conflicting replay returns `CLIENT_ID_CONFLICT` |
| BH-06 Expiry and retention | PASS | expiry boundary removes the capsule from results; freed active capacity accepts a new capsule |
| BH-07 Interruption recovery | PASS (software) | bounded local-storage outbox, stable UUID and retryable/terminal separation; a real Chromium exercise joined `BROWSER-TEST`, published with an empty final outbox, reloaded and fetched the same capsule without error |
| BH-08 Abuse/resource boundary | PASS | per-address rate, global active count, per-channel active count and database-byte limit produce bounded refusals |
| BH-09 Content-free operations | PASS | unique capsule marker absent from application stdout/stderr; deployment disables Gunicorn access logging |
| BH-10 Offline application shell | PASS (software) | same-origin manifest/assets, service-worker shell cache and explicit API-cache exclusion |
| BH-11 Deployment readiness | PASS (software) | health API, pinned Gunicorn, loopback systemd unit, bounded TLS proxy example, verified non-overwriting SQLite backup and Linux production smoke workflow |
| BH-12 Honest status | PASS | interface distinguishes domestic hub, nearby mode and total network loss; field state is visibly `NOT RUN` |

Focused local evidence command:

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider \
  tests/test_bdix_hub.py tests/test_bdix_hub_static.py tests/test_bdix_backup.py
```

The automated field gate remains **not passing**. It requires the named
Bangladesh host, two named ISPs and controlled international-route loss in
`BDIX_HUB_SCOPE.md` §8.

## Test-count inventory

Counts are measured from the 78 definitions. The completed M0 and M1
classifications are preserved; no AT-38 through AT-78 result is recorded
as passing.

- **Total acceptance definitions:** 78
  - Milestone 0 catalogue: 21 (AT-01 through AT-21), evidence preserved
  - Milestone 1 catalogue: 16 (AT-22 through AT-37), COMPLETE
  - Remaining-project catalogue: 41 (AT-38 through AT-78), SPECIFIED
- **Definitions with an S1 scope:** 60
  - 20 in AT-01 through AT-21
  - 2 in AT-22 through AT-37 (AT-30 and AT-37)
  - 38 in AT-38 through AT-78
- **Definitions with an S2 scope:** 19
  - AT-12 and AT-14 in the M0 catalogue
  - 14 in the M1 catalogue
  - AT-61, AT-62 and AT-65 in the remaining catalogue

AT-12 is intentionally counted in both severity sets because its
unit-level M0 rule is S2 while its device-side effect is S1. Therefore,
the two severity-set counts overlap and must not be added to infer the
number of definitions.

The 18 Milestone 0 blockers and all 16 Milestone 1 blockers retain their
recorded passing evidence. The remaining catalogue has 28
software-complete blockers, 10 field-validation blockers and 3
non-blocking research/benchmark evidence definitions, as classified
above.

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

## Milestone 0 test inventory (historical)

> Counts in this subsection apply only to AT-01 through AT-21.

- Milestone 0 acceptance definitions: 21
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
