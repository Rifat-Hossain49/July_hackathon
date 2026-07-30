# Shongket — Experiment Plan (Draft 1)

Experiment specification and recorded M0/M1 evidence. No device,
radio, model or field number is inferred from the simulator, and no
unmeasured cell is filled with zero.

---

## 1. Hypotheses

Each hypothesis is falsifiable. "Unverified" means no measurement yet.

| ID | Hypothesis |
|---|---|
| H-SEM-1 | For any object, the semantic capsule is delivered to a peer before the bulk media representations of the same object. |
| H-PRE-1 | A newly created critical capsule preempts an in-progress bulk transfer for the same or a different object, within a measurable latency bound. |
| H-RES-1 | After an interrupted transfer, the receiver retains verified fragments and resumes from the last verified chunk index. |
| H-MP-1 | A receiver can reconstruct a representation using fragments sourced from ≥ 2 distinct simulated peers. |
| H-DED-1 | Duplicate chunks (same content ID + chunk index + hash) are not stored twice. |
| H-COR-1 | Corrupted chunks (hash mismatch) are rejected without blocking later valid chunks of the same object. |
| H-SCHED-1 | The deterministic scheduler outperforms a full-file baseline on time-to-first-actionable-meaning. |
| H-SCHED-2 | Preempted bulk transfer resumes without re-sending already-acked chunks. |
| H-INV-1 (later research) | A separately approved probabilistic inventory may be compared with the exact inventory; no Bloom implementation or M0 result exists. |
| H-MEDIA-1 | Smaller fixed-size chunks reduce unused bytes at end of encounter but increase metadata overhead; the optimum is in the 32 KB–256 KB band. |
| H-FWD-1 | Deterministic forwarding policy achieves ≥ X% of the utility-based policy on reach, on the M0 corpus (utility-based is a **later experiment**, not M0). |
| H-RESTART-1 | After a simulated restart, an in-progress transfer's verified state is intact. |

A hypothesis marked "later" in the above list is **not** M0-scored.

---

## 2. Baselines

| Baseline | Description |
|---|---|
| B1 | Ordinary full-file transfer (one object = one transfer). |
| B2 | Ordinary resumable chunk transfer (chunked, no priority). |
| B3 | Progressive representations without semantic priority. |
| B4 | Shongket scheduling (deterministic, semantic-aware). |
| B5 | Multi-peer ordinary-chunk completion (M0). |
| B6 (later) | Coded reconstruction (Reed-Solomon / RaptorQ) — **explicitly NOT M0**. |
| B7 (later) | Utility-based forwarding — **explicitly NOT M0**. |

---

## 3. Testbeds (M0 is simulation; later milestones use real devices)

### 3.1 Simulated (M0)

- 1 sender, 1 receiver.
- 1 sender, 2 receivers.
- 1 sender, 3 receivers.
- 1 receiver, 2 partial senders (multi-peer reconstruction).
- 1 receiver, 3 partial senders (multi-peer reconstruction).
- Repeated short encounters (encounter window << total transfer).
- Peer departure mid-transfer.
- Peer rejoin after gap.
- Transfer interruption (simulated).
- Duplicate fragments injected.
- Corrupted fragments injected.
- Low storage (5% headroom).
- Low battery (under threshold).
- Mixed priorities in flight.
- Simultaneous critical + bulk content.
- Application restart.

### 3.2 Real device (M3+)

- The same scenarios on actual phones, gated by the transport
  smoke-test gate in `RESEARCH_LOG.md` §Transport.

### 3.3 Vendor-specific transport experiments (M3)

Real-device transport selection and Android vendor testing belong to
**Milestone 3**, not Milestone 2.

These experiments are outside Milestone 0 and Milestone 2:

- Nearby Connections smoke testing;
- Wi-Fi Direct evaluation;
- local-hotspot evaluation;
- Android permission behavior;
- vendor compatibility;
- interruption and reconnection on real devices;
- repeated demo-device reliability testing.

### 3.4 Later coded-delivery experiments (research extension)

These experiments are outside Milestone 0:

- Reed-Solomon recovery;
- fountain-code recovery;
- RaptorQ recovery;
- arbitrary repair-symbol collection.

No coded-delivery performance result may be reported before the
relevant strategy is actually implemented.

### 3.5 Result-source labels

Result source:

- `[SIMULATION]` — M0/M1 simulator runs.
- `[LOCAL_PROCESS]` — M2 two-process harness runs.
- `[JVM_OR_EMULATOR]` — Android JVM/emulator with no radio claim.
- `[PHYSICAL_DEVICE]` — real handset measurement without a radio claim.
- `[REAL_RADIO]` — named handsets communicating over the named radio.
- `[FIELD_ONLY]` — consented partial-connectivity field setting.

### 3.6 M0 measurement caveat

These results are simulator outputs. They do not represent real
wireless throughput, Android battery use, device compatibility or
guaranteed multimedia rates.

---

## 4. Measured metrics (M0 simulator)

| Metric | Definition |
|---|---|
| TTFA | Time to first actionable meaning (capsule received) |
| TTFT | Time to first thumbnail |
| TTP | Time to first playable preview |
| TTS | Time to complete standard representation |
| TTO | Time to original-quality reconstruction |
| Throughput | local bytes / second |
| Useful bytes per encounter | bytes received that advanced reconstruction |
| Critical preemption latency | ms from critical arrival to bulk pause |
| Reconstruction success rate | objects successfully reconstructed / total |
| Duplicate bytes avoided | bytes not stored because already present |
| Protocol overhead | metadata bytes / total bytes |
| Peak memory | MB during transfer |
| Energy use | Joules per transfer (simulated only) |
| Storage consumption | MB stored per object |
| AI inference latency | ms (manual form in M0; measured only when M6 enabled) |

---

## 5. Result tables (filled by the M0 harness)

`[SIMULATION]` — every value below is produced by the M0 simulator in
`app/simulator/`, per DR-EXP-01 (tables are filled by harness logs
only). Each scenario was run twice and its serialized metrics compared
byte-for-byte; only reproducible values are recorded.

**Time unit.** M0 timing is measured in **deterministic simulator
ticks**, not milliseconds or seconds. The simulator has no wall-clock
time base, so no seconds-denominated figure can be produced here. The
§3.6 measurement caveat applies to every row: these are simulator
outputs, not real wireless, battery or device measurements.

Cells reading `UNMEASURED — requires later device/runtime milestone`
have no M0 value and are deliberately not filled with zero.

### 5.1 End-to-end timing (ticks)

| Scenario | TTFA | TTFT | TTP | TTS | TTO |
|---|---|---|---|---|---|
| 1 sender, 1 receiver, no contention | 4 | 8 | 10 | 14 | 22 |
| 1 sender, 2 receivers | UNMEASURED — scenario not implemented in the M0 harness | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED |
| Critical preempts bulk | 8 | 4 | 10 | 20 | 46 |
| Multi-peer reconstruction | n/a — scenario carries no capsule | n/a | n/a | n/a | 21 |
| Restart-survives | 4 | 8 | 12 | 27 | 53 |

Notes. Row 1 is the CLI scenario (`--seed 42 --chunk-size 65536`, 8
chunks). Rows 3–5 use `--chunk-size 16384` (21 chunks), so their tick
values are not comparable with row 1. In "Critical preempts bulk" the
capsule is injected after two bulk chunks by design, which is why TTFA
(8) follows TTFT (4) in that row only. "Multi-peer reconstruction"
transfers one representation between peers and schedules no capsule, so
the capsule- and layer-timing columns do not apply.

### 5.2 Robustness

| Scenario | Reconstruction success rate | Duplicate avoided (bytes) | Corrupted rejected (count) |
|---|---|---|---|
| Duplicate injection | 1/1 representations | 200000 | 0 |
| Corruption injection | 1/1 representations (13/13 chunks stored after rejections) | 0 | 3 |
| Peer departure | 4/4 representations | 0 | 0 |
| Short encounters | UNMEASURED — scenario not implemented in the M0 harness | UNMEASURED | UNMEASURED |

Notes. "Duplicate injection" offers all 13 chunks twice: the second pass
stores nothing and avoids 200000 bytes. "Corruption injection" rejects 3
tampered chunks on hash mismatch and then accepts all 13 valid chunks,
confirming corruption does not halt the transfer (AT-10); its
completion is verified from store counters. "Peer departure" interrupts
after 7 of 21 chunks and completes from a second peer.

### 5.3 Scheduler

| Scenario | Preemption latency | Useful bytes per encounter | Overhead % |
|---|---|---|---|
| Mixed priorities | n/a — no preemption in this scenario | 322880 | 0.7988 |
| Critical + bulk | 1 tick (ms: UNMEASURED — requires later device/runtime milestone) | 322880 | 0.2758 |
| Expired content present | n/a — nothing scheduled | 0 (1 expiry refusal, 0 bytes forwarded) | n/a |

Notes. Overhead % is signal-plane bytes over total bytes transferred,
computed from the serialized metrics. The canonical column header asks
for milliseconds; M0 can only produce ticks, so the millisecond value is
marked unmeasured rather than converted.

### 5.4 Inventory

| Scenario | Bloom FPR | False negatives |
|---|---|---|
| 100 objects / peer | UNMEASURED — Bloom-filter inventory is not implemented in M0 (QP-01: explicit list; DR-SPEC-03) | UNMEASURED |
| 1000 objects / peer | UNMEASURED — as above | UNMEASURED |
| 10000 objects / peer | UNMEASURED — as above | UNMEASURED |

### 5.5 Harness run evidence

| Item | Value |
|---|---|
| Tests collected | 125 |
| Tests passed | 125 |
| Tests failed | 0 |
| Tests skipped | 0 |
| M0-blocking acceptance IDs covered | 18 of 18 |
| CLI event-log SHA-256 | `D5AC79B18B6B3329A2788CDCCF45A92D10534639B20079039D1902D7F82CB4DF` |
| CLI event-log size | 3114 bytes |
| Serialized metrics SHA-256 | `E10E11D4AEF1788E92CC907060C48CA06A3E76913C2BDD58ABF43858B8891B28` |
| Serialized metrics size | 1580 bytes |
| Multi-peer contributing peer IDs | `peer-A`, `peer-B` |
| Runtime dependencies | Python standard library only |

Both hashes were produced by running the same command twice and
comparing the output byte-for-byte.

### 5.5a Milestone 1 conformance evidence

Complete M1 run: **367 passed, 0 failed, 0 skipped** (242 M1 tests plus
the 125 M0 regression tests). All sixteen M1-blocking IDs implemented.

| Evidence | Source test | Value |
|---|---|---|
| Canonical serialization SHA-256 per schema | AT-22 | capsule `8b0a3231…` (555 B); content manifest `d61e057b…` (464 B); fragment descriptor `8eea53cc…` (283 B); non-ASCII capsule `028d7ab7…` (297 B) |
| Insertion-order independence | AT-22 | reversed-order manifest hashes to `d61e057b…`, identical to the ordered manifest |
| Identity excludes forwarding state | AT-22 | manifest carrying `hop_count` / `remaining_copy_budget` yields identity hash `d61e057b…`, equal to the manifest without them |
| Registered-minor acceptance log | AT-23 | `shongket.content.v1.1` accepted via registered compatibility; ignored field reported as `("a_field_from_the_future",)` |
| `VERSION_UNSUPPORTED` rejection log | AT-24 | major `2` rejected; major `2` + malformed rejected as `VERSION_UNSUPPORTED` (not `SCHEMA_INVALID`); unregistered minor `1.7` rejected; 8 malformed identifier forms rejected |
| Migration input/output SHA-256 | AT-25 | v0.9 input `b8a72f83…` (1365 B) → v1.0 output; two runs from identical bytes produced identical output |
| Per-stage crash-recovery log | AT-26 | 4 interruption stages injected; after temp write / temp fsync the previous document survives, after replace / before parent fsync the new one does; 0 blended reads; parent-dir sync outcome recorded per platform |
| Partial-write recovery log | AT-27 | Truncated temp discarded by name; previous snapshot loaded intact; 3 stray temps in the multi-artefact case all removed |
| Quarantine path + integrity report | AT-28 | Corrupt primary renamed to `*.quarantine-0` and still readable; fallback loaded; in case (b) 1 of 4 fragments dropped, 3 preserved |
| Pre/post rollback SHA-256 | AT-29 | Original document byte-identical before and after a failed migration; still stamped `shongket.snapshot.v0.9`; failure classified retryable |
| Fragment inventory + byte accounting | AT-30 | All 5 recovery paths preserve every fragment digest; `used_bytes == recompute_used_bytes()` in every case |
| Restart event-log SHA-256 (×2) | AT-31 | Two independent runs produced identical evidence digests and identical stores; resume requested exactly indexes 3–7 of 0–7 |
| Error-code coverage matrix | AT-32 | 16 enum members; 13 triggered by executable probes; 3 recorded unreachable-by-design (`SIGNATURE_INVALID`, `UNKNOWN_OBJECT`, `INTERNAL`) with reasons |
| Paired retryable/terminal attempt logs | AT-33 | Terminal repeated 3× with one distinct code and one distinct detail, no state change; retryable `OUT_OF_BUDGET` succeeded after capacity freed |
| Privacy migration log + AT-16 re-run | AT-34 | 3 legacy mappings; 8 malformed `visibility` → `SCHEMA_INVALID`; 6 non-boolean consent → `CONSENT_REQUIRED`; AT-16 refusal matrix green post-migration |
| `PEER_REFUSES_PRIVATE` refusal evidence | AT-35 | Private + valid consent → refused at clause `peer_public_only`; ordinary peer and public object both admitted; manifest unmutated |
| Store version before/after + resumed chunks | AT-36 | v0.9 → v1.0; resumed indexes (3, 4, 5) without re-requesting 0–2; second open reported `migrated=False`, 0 steps |
| M0 regression counts, import scan, both hashes | AT-37 | 125 M0 tests pass unchanged in a subprocess; AST scan finds 0 non-stdlib and 0 adapter imports; CLI `D5AC79B1…2CB4DF` and metrics `E10E11D4…891B28` unchanged; `git diff` shows `app/` untouched |

AT-37 additionally re-verifies the M0 values already recorded in §5.5:
125 passing tests and the two determinism hashes. Those are the M0
results; they are not restated here as M1 evidence.

### 5.6 Metrics not produced by M0

Four metrics from §4 are deliberately absent rather than estimated:

| Metric | Reason |
|---|---|
| Throughput (local bytes/second) | No wall-clock time base in the simulator. Raw inputs (bytes transferred, tick counts) are reported instead. |
| Peak memory (MB) | Requires process instrumentation; measured from M3+. |
| Energy use (Joules) | Requires device measurement; measured from M3+. |
| AI inference latency (ms) | M0 uses the manual form and runs no model (AT-15); measured only when M6 is enabled, as §4 already states. |

### 5.7 Remaining device and field result table

The software-complete implementation may commit runners, schemas and
empty evidence templates. Only the declared runtime boundary may replace
`UNMEASURED`.

| Acceptance/evidence | Required source | Current result |
|---|---|---|
| AT-47 through AT-50 transport gate | `[REAL_RADIO]` | UNMEASURED |
| AT-55 progressive radio delivery | `[REAL_RADIO]` | UNMEASURED |
| AT-56, AT-57 multi-peer completion | `[REAL_RADIO]`, ≥3 devices | UNMEASURED |
| AT-61 model resource limits | `[PHYSICAL_DEVICE]` | UNMEASURED — optional-model evidence |
| AT-62 Bangla quality | `[PHYSICAL_DEVICE]` | UNMEASURED — optional-model evidence |
| AT-65 low-battery behaviour | `[PHYSICAL_DEVICE]` | UNMEASURED |
| AT-74 benchmark suite | `[PHYSICAL_DEVICE]` and `[REAL_RADIO]` where applicable | UNMEASURED |
| AT-77 repeated demonstration | `[REAL_RADIO]` | UNMEASURED |
| AT-78 field trial | `[FIELD_ONLY]` | UNMEASURED |

AT-74 passes when every required metric has a reproducible measurement
with run metadata and uncertainty, or an explicit failure note. It does
not require a favourable number and never converts simulator ticks into
device seconds.

---

## 6. Targets (clearly labeled)

Each target is one of:

- **requirement** — must hold for M0 to be considered successful.
- **hypothesis** — expected to hold, must be falsifiable.
- **aspirational** — desirable but not required.
- **unresolved** — no number exists; placeholder.

| Target | Label | Notes |
|---|---|---|
| Semantic capsule before bulk media | requirement | H-SEM-1; tested in M0 |
| Critical preemption latency ≤ 100 ms (simulated) | hypothesis | subject to instrumentation |
| Resume bulk transfer from last acked chunk | requirement | H-SCHED-2 |
| Reconstruct using ≥ 2 peers | requirement | H-MP-1 |
| Duplicate chunks stored once | requirement | H-DED-1 |
| Corrupted chunks rejected without halting | requirement | H-COR-1 |
| Reconstructed hash equals manifest hash | requirement | M0 success criterion 8 |
| Expired content not forwarded | requirement | M0 success criterion 9 |
| Bloom FPR ≤ 1% at 1000 objects | later research only | H-INV-1; no M0–M9 implementation claim |
| Time-to-first-meaning improvement over B1 | hypothesis | requires B1 timing |
| Energy per inference on Tier B | unresolved | M0 uses manual form |
| Throughput on real devices | unresolved | requires M3+ |
| Multi-day demo reliability | unresolved | requires M9 |

---

## 7. Decision records

### DR-EXP-01 — Empty result tables are honest

- Decision: result tables are empty in M0 and are filled by the
  harness's logs only.
- Alternatives: pre-fill with placeholders.
- Recommended: empty in this plan.
- Reason: avoid invented numbers (per AGENTS research rules).
- Evidence required: harness log output.
- Trade-offs: less impressive visual.
- Risks: reviewers may infer that M0 has no data.
- Validation: README status table explicitly notes "simulated,
  measurements pending M0 harness run."
- Revisit condition: M0 harness run.

### DR-EXP-02 — Coded reconstruction is a later experiment

- Decision: B6 (coded reconstruction) is not in M0.
- Alternatives: include in M0.
- Recommended: later.
- Reason: do not describe unimplemented behavior as implemented.
- Evidence required: M5+ implementation.
- Trade-offs: M0 cannot claim coding benefits.
- Risks: evaluators may confuse multi-peer ordinary with coded.
- Validation: README, MILESTONES, PROTOCOL_SPEC all use distinct
  language.
- Revisit condition: M5+.

### DR-EXP-03 — Utility-based forwarding is a later experiment

- Decision: B7 (utility forwarding) is not in M0.
- Alternatives: include in M0.
- Recommended: later.
- Reason: M0 forwarding is deterministic (per DR-ARCH-02 / DR-SPEC-02).
- Evidence required: M5+ implementation.
- Trade-offs: less adaptivity in M0.
- Risks: people may compare M0 forwarding to learned policies.
- Validation: README + MILESTONES call out deferred status.
- Revisit condition: M5+.

## H-SCHED-1

H-SCHED-1 is a hypothesis to be measured by the experiment; it is **not**
a prerequisite assumed true before the simulator runs. The simulator
executes against all protocol logic regardless of whether the
comparative hypothesis is supported.

## Milestone 0 completion under disproved hypotheses

Milestone 0 can still complete when a comparative hypothesis
(e.g. H-SCHED-1) is disproved, provided all of the following hold:

- the experiment executes correctly end-to-end;
- the result is honestly recorded in the experiment report;
- every deterministic functional success criterion in
  `ACCEPTANCE_TESTS.md` that is in the Milestone 0 scope passes.

A disproved hypothesis is a research finding, not a failure of the
Milestone 0 deliverable.
