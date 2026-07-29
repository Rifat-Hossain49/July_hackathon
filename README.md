# Shongket

Shongket is a proposed semantic-first, disruption-tolerant multimedia
distribution protocol for partial-connectivity crises.

It is designed to deliver human-confirmed critical meaning first,
followed by progressive previews and, eventually, original-quality
media completed from verified chunks collected across multiple peer
encounters.

**Status:** Planning-only. No implementation code is in this
repository. Pre-implementation decisions live in `PRODUCT_DECISIONS.md`
(currently `IMPLEMENTATION_STATUS: NOT_APPROVED`); implementation work
will not begin until that status changes.

> **Public tag discipline:** throughout this document, every
> capability is labelled as

> [IMPLEMENTED] / [PLANNED].
> **M0 is PLANNED, not SIMULATED, until the harness has actually run.**
> **Nothing in this README is a claim about measurements;**
> **measurements come from real-device runs in later milestones.**

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

[PLANNED — full implementation begins after M0 approval]

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
| Milestone 0 simulator | PLANNED |
| Multi-peer simulator run | PLANNED |
| Android peer transfer | PLANNED |
| Progressive real-media transfer | PLANNED |
| Offline AI extraction | PLANNED |
| Reed-Solomon / RaptorQ | RESEARCH ONLY |

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

- M0 is a protocol simulator; it does not demonstrate real-world throughput.
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

- M0: executable protocol simulator.
- M1: production-quality deterministic core.
- M2: local two-process transfer.
- M3: Android direct peer transport (gated by the transport smoke-test gate).
- M4: progressive media transfer on real devices.
- M5: real-device multi-peer completion (ordinary verified chunks).
- M6: offline semantic extraction.
- M7: integration and resilience.
- M8: benchmarking.
- M9: demo and public release.

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
[AI_USAGE.md](./AI_USAGE.md), AI assistance was used for planning
drafts. No model has been chosen; model selection is benchmark-driven
per [MODEL_EVALUATION_PLAN.md](./MODEL_EVALUATION_PLAN.md).

---

## 14. Contribution

This repository is planning-only. Implementation is gated on
`PRODUCT_DECISIONS.md` approval. Until then, contributions are
review-only against the planning documents.

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
