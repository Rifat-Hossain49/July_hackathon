# Shongket

Shongket is a proposed semantic-first, disruption-tolerant multimedia
distribution protocol for partial-connectivity crises.

It is designed to deliver human-confirmed critical meaning first,
followed by progressive previews and, eventually, original-quality
media completed from verified chunks collected across multiple peer
encounters.

**Status:** Milestone 0 is implemented in `app/simulator/`; Milestone 1
is implemented in `shongket_core/`. The combined baseline is **367
passing tests, 0 failed, 0 skipped**. `PRODUCT_DECISIONS.md` is the
canonical authorisation source and currently reads
`IMPLEMENTATION_STATUS: APPROVED_FOR_MILESTONE_1`. The M2–M9 scope is
frozen in `REMAINING_SCOPE.md`. A separate descendant ledger authorizes
the exact software/evidence-tooling subset while leaving device, radio
and field validation unapproved.

**This repository contains a protocol simulator, not a deployable
mobile application.** There is no Android app, no radio transport and
no offline AI inference. See section 9 for the full boundary between
what is done and what is not.

> **Public tag discipline:** throughout this document, every
> capability is labelled as

> [IMPLEMENTED] / [SIMULATED] / [PLANNED].
> **The complete baseline has run: 367 automated tests pass (0 failed,**
> **0 skipped): 125 M0 tests plus 242 M1 tests.**
> **Every M0 number in this repository is a simulator measurement in**
> **deterministic ticks, never a wall-clock or real-device figure;**
> **real-device measurements come from later milestones.**

---

## 1. One-sentence pitch

Shongket is a proposed content-centric, peer-to-peer protocol that
distributes human-confirmed semantic meaning first, progressive
previews next, and original-quality media last, so that the most
actionable information arrives even when typical channels are
disrupted.

---

## 2. Crisis context

The motivating scenario is a climate-induced disruption similar to
the July 2024 Bangladesh event: voice / SMS remained partially
functional while high-bandwidth internet failed. In that situation,
people still needed to know what is happening, where it is
happening, and what to do next. Conventional messaging or
content-delivery apps assume either (a) full internet connectivity
or (b) tiny text bursts; they are not optimised for "the wire is
up, but slow and unreliable, and the people who can carry bits
between villages are themselves moving."

Shongket designs for that in-between state.

---

## 3. What existing offline-first approaches don't solve

- Most offline messengers prioritise content equally and treat
  "delivery" as a binary.
- Most P2P file-sharing tools do not preserve original media with
  predictable recovery.
- Most broadcasting systems do not adapt to short, intermittent
  peer encounters.
- Most AI pipelines assume cloud connectivity and a single trusted
  source.

---

## 4. What Shongket proposes

- **Semantic-first delivery.** A small human-confirmed capsule
  (what, where, who, when, what to do) is scheduled before any
  bulk media.
- **Progressive media.** Thumbnails and previews precede full media.
- **Multi-peer reconstruction.** Missing fragments are pulled from
  whichever peer has them.
- **Critical preemption.** A new critical capsule can interrupt
  in-flight bulk transfers.
- **Content addressing.** Objects are identified by their hash;
  duplicates are not re-stored.
- **Offline-first.** All transfers are peer-to-peer with no
  required infrastructure.
- **Human-confirmed AI.** AI suggestions are proposals until a
  human confirms them.
- **Manual fallback.** When the offline model is disabled or
  low-confidence, a structured manual form is used.

---

## 5. Architecture (high level)

[SIMULATED — the M0 slice of this architecture is implemented in
`app/simulator/`; the capture, semantic-engine and transport-adapter
boxes remain PLANNED]

```
Capture ── Semantic engine (offline) ── Human review ── Confirmed capsule
                              │
                              ▼
                       Media pipeline
                              │
                              ▼
       Content-addressed store + Fragmenter + Integrity verifier
                              │
                              ▼
            Priority scheduler (signal plane first)
                              │
                              ▼
        Transport adapter (peer-to-peer; transport TBD)
                              │
                              ▼
                    Peer fragment inventory
                              │
                              ▼
                Reconstruction engine (multi-peer)
```

The full architecture with components, planes, and trust boundaries
is in [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md).

---

## 6. Example scenario (illustrative)

1. A volunteer enters a short note: "Flood water rising in
   [location]. Move to school 2 km north."
2. Confirms.
3. The capsule is queued as critical.
4. A photo of the same scene is attached as progressive media.
5. As the volunteer moves, the capsule is exchanged with the next
   peer; the photo is incomplete.
6. The next peer offers only a partial photo set.
7. The receiver's planner combines the two sources.
8. The full photo is reconstructed.
9. The receiver's UI shows: capsule first, photo preview second,
   full photo when complete.

This is a **scenario**, not a measurement. Whether the protocol
achieves this in < 30 s on a real phone is a measurement question
left to M3+.

---

## 7. Current project status

| Component | Status |
|---|---|
| Product concept | IMPLEMENTED |
| Architecture documents | IMPLEMENTED |
| Protocol specification | IMPLEMENTED |
| Acceptance-test specification | IMPLEMENTED |
| Milestone 0 simulator | IMPLEMENTED |
| Milestone 1 deterministic protocol core | IMPLEMENTED |
| Durable crash-safe persistence (in-process) | IMPLEMENTED |
| Multi-peer simulator run | SIMULATED (deterministic simulated multi-peer completion) |
| Android peer transfer | PLANNED |
| Progressive real-media transfer | PLANNED |
| Offline AI extraction | PLANNED |
| Reed-Solomon / RaptorQ | RESEARCH ONLY |

Labels follow D-012 in `PRODUCT_DECISIONS.md`. **IMPLEMENTED** means the
code exists and is covered by passing automated tests; **SIMULATED**
means the behaviour is demonstrated between in-process simulated peers
only. No row above asserts real-device or real-radio behaviour.

---

## 8. What Shongket does not claim

Shongket does not currently claim:

- global broadband without infrastructure;
- guaranteed delivery;
- guaranteed multimedia transfer rates;
- tested Android compatibility;
- tested battery performance;
- implemented coded reconstruction;
- automatic verification of factual truth.

---

## 9. Limitations

### 9.1 What is completed

All of the following are implemented in `app/simulator/` and covered by
passing automated tests. Every one is **simulated protocol behaviour**
between in-process peers:

- deterministic Python M0 simulator with a reproducible CLI;
- fixed-size chunking;
- SHA-256 verification per chunk and per representation;
- deterministic simulated multi-peer completion;
- interruption and resume;
- restart persistence;
- priority scheduling and critical preemption;
- expiry enforcement;
- storage-budget rule;
- manual model-fallback path;
- private-content consent gate;
- oversized-payload rejection;
- deterministic metrics generation;
- all 18 M0-blocking acceptance IDs.

The platform-neutral `shongket_core/` also implements the complete M1
scope:

- canonical serialization, schema registry and explicit versions;
- durable checksummed snapshots, crash recovery and advisory locking;
- deterministic migration and rollback;
- canonical errors and the six-clause forwarding policy;
- language-neutral golden vectors;
- all 16 M1-blocking acceptance IDs.

### 9.2 What is NOT completed

None of the following exists in this repository:

- Android application;
- user-facing mobile UI;
- Bluetooth;
- Wi-Fi Direct;
- Nearby Connections;
- any real radio transport;
- real camera or audio capture pipeline;
- production encryption and cryptographic identity;
- real offline model inference;
- Bloom-filter inventory;
- coded reconstruction (Reed-Solomon / fountain / RaptorQ);
- field testing;
- Milestone 2 or later implementation.

### 9.3 Standing caveats

- M0 is a protocol simulator; it does not demonstrate real-world throughput.
- M0 timing is expressed in deterministic simulator ticks, not seconds.
  No bytes-per-second figure exists, because the simulator has no
  wall-clock time base.
- No transport is locked.
- No model is locked.
- No claim is made about Android vendor compatibility until M3.
- No claim is made about battery performance until M3.
- No claim is made about real-world Bangla performance until M6+.

---

## 10. Research basis

See [RESEARCH_LOG.md](./RESEARCH_LOG.md) for cited sources on
transport, content-addressing, store-carry-forward, and coding. The
log explicitly distinguishes what this plan borrows from prior art
from what it is **proposing** (semantic-first priority, critical
preemption, manual-form fallback for AI), and what remains an
**unverified hypothesis** until measurements are produced.

---

## 11. Roadmap

See [MILESTONES.md](./MILESTONES.md). Milestones:

- M0: executable protocol simulator. **Implemented.**
- M1: production-quality deterministic core. **Implemented** in
  `shongket_core/` — canonical serialization, schema registry and
  versioning, durable crash-safe persistence, migration and rollback,
  forwarding policy and a canonical error taxonomy. All sixteen
  M1-blocking acceptance tests pass alongside the 125 M0 tests. Still a
  deterministic in-process core: no Android, radio, AI or production
  security. See [M1_SCOPE_FREEZE.md](./M1_SCOPE_FREEZE.md).
- M2: local two-process transfer.
- M3: Android direct peer transport (gated by the transport smoke-test gate).
- M4: progressive media transfer on real devices.
- M5: real-device multi-peer completion (ordinary verified chunks).
- M6: offline semantic extraction.
- M7: integration and resilience.
- M8: benchmarking.
- M9: demo and public release.

The remaining roadmap distinguishes a software-complete release
candidate from a field-validated release. Software, JVM/emulator and
two-process evidence cannot be used to claim physical-device,
real-radio or field success.

For experiments, see [EXPERIMENT_PLAN.md](./EXPERIMENT_PLAN.md). For
test definitions, see [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md).
For risks, see [RISK_REGISTER.md](./RISK_REGISTER.md). For protocol
detail, see [PROTOCOL_SPEC.md](./PROTOCOL_SPEC.md). For media
pipeline, see [MEDIA_PIPELINE.md](./MEDIA_PIPELINE.md).

---

## 12. Ethical and privacy principles

- Human in the loop. AI output is **never** published without
  human confirmation.
- Source = trust. Signed publishers are trusted as identities,
  but signer ≠ truth; freshness and accuracy still require
  confirmation.
- Private content never auto-forwards.
- Uploads are size-limited and integrity-checked.
- The system must not amplify fear, fake urgency, or fabricated
  facts.

These are stated in [PRODUCT_DECISIONS.md](./PRODUCT_DECISIONS.md)
(D-002, D-003, D-007, D-009).

---

## 13. AI assistance disclosure

Per [HACKATHON_BRIEF.md](./HACKATHON_BRIEF.md) and
[AI_USAGE.md](./AI_USAGE.md), AI assistance was used for planning and
implementation support. No model has been chosen; model selection is benchmark-driven
per [MODEL_EVALUATION_PLAN.md](./MODEL_EVALUATION_PLAN.md).

---

## 14. Contribution

Implementation is gated by the exact milestone/scope ledger in
`PRODUCT_DECISIONS.md`. M0 and M1 are complete. M2–M9 software work is
authorized only for the modules and acceptance IDs in the descendant
ledger referencing scope-freeze commit `f85a7c5`. Physical-device,
real-radio and field-validation success claims, production signing/trust
decisions and public-store deployment remain unauthorized.

Run the complete baseline with:

```
python -m pytest -q
```

---

## 15. License

TBD. No license is asserted in this draft.

---

## 16. Manifesto summary

> Semantic-first.
> Human-confirmed.
> Offline-first.
> Crisis-shaped.
> Honest about what is measured.
> Honest about what is not.
