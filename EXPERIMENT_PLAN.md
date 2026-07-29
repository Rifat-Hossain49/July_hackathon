# Shongket — Experiment Plan (Draft 1)

Planning-only. No invented benchmark numbers.

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
| H-INV-1 | Bloom-filter inventory with placeholder parameters produces ≤ FPR% false positives on the M0 synthetic corpus. |
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
- `[REAL_DEVICE]` — M3+ on real hardware.

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

## 5. Result-table templates (empty, to be filled by M0)

### 5.1 End-to-end timing

| Scenario | TTFA | TTFT | TTP | TTS | TTO |
|---|---|---|---|---|---|
| 1 sender, 1 receiver, no contention |  |  |  |  |  |
| 1 sender, 2 receivers |  |  |  |  |  |
| Critical preempts bulk |  |  |  |  |  |
| Multi-peer reconstruction |  |  |  |  |  |
| Restart-survives |  |  |  |  |  |

### 5.2 Robustness

| Scenario | Reconstruction success rate | Duplicate avoided (bytes) | Corrupted rejected (count) |
|---|---|---|---|
| Duplicate injection |  |  |  |
| Corruption injection |  |  |  |
| Peer departure |  |  |  |
| Short encounters |  |  |  |

### 5.3 Scheduler

| Scenario | Preemption latency (ms) | Useful bytes per encounter | Overhead % |
|---|---|---|---|
| Mixed priorities |  |  |  |
| Critical + bulk |  |  |  |
| Expired content present |  |  |  |

### 5.4 Inventory

| Scenario | Bloom FPR | False negatives |
|---|---|---|
| 100 objects / peer |  |  |
| 1000 objects / peer |  |  |
| 10000 objects / peer |  |  |

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
| Bloom FPR ≤ 1% at 1000 objects | hypothesis | H-INV-1 |
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
