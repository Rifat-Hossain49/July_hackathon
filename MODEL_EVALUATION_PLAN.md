# Shongket — Model Evaluation Plan (Draft 1)

Evaluation specification. No model is selected, bundled or approved by
this document. The software-complete app defaults to the manual path and
must remain usable without a model.

---

## 1. Responsibilities of the offline intelligence componen

The component's job is to **suggest** structured fields, never to
declare truth. Per `PRODUCT_DECISIONS.md` D-003 and D-011:

1. Propose: event type, location text, urgency, affected people,
   required action, required resource, short Bangla summary,
   Bangla-English code-switched summary, important timestamps from
   audio or video, key video frames, uncertain or missing fields.
2. Mark every field with an uncertainty flag.
3. Hand the result to a human review step (D-003).
4. If unavailable, slow, or invalid, fall back to a manual form
   (D-011).

### 1.1 What the model is NOT allowed to do

- Publish a capsule autonomously.
- Mark a field as "verified truth."
- Strip or replace the source media.
- Hide uncertainty to look confident.
- Send data off-device.

---

## 2. Candidate categories (to be evaluated, not selected here)

| Category | Strengths | Risks |
|---|---|---|
| Rule-based extraction | tiny, fast, predictable | brittle; weak on Bangla |
| Small multilingual text model | compact; useful for short text | limited modality coverage |
| Small Bangla-specialized text model | Bangla-strong | small context, weak multimodal |
| STT + small text extraction | covers voice; smaller than full MM | STT quality on noisy crisis audio |
| Lightweight vision model | image labels | weak Bangla captions |
| Multimodal model | covers text+image+audio | RAM, energy, license risk |
| Device-tier-dependent routing | adapts | routing complexity |

### 2.1 Per-candidate criteria

For each category (filled at evaluation time, not now):

| Criterion | Definition |
|---|---|
| Bangla support | tokenization, summarization quality |
| Bangla-English code-switching | mixed-language robustness |
| Noisy speech | ASR WER on noisy crisis audio |
| Low-light images | captioning on dark / blurred images |
| Crisis terminology | recall on domain-specific terms |
| Structured-output reliability | percentage of outputs that parse cleanly |
| Inference latency | ms to first token / full output |
| RAM | peak working-set |
| Storage | on-disk model size |
| CPU / GPU / NPU requirements | accelerators required |
| Energy consumption | Joules per inference (measured, not estimated) |
| Licensing | permissive vs restrictive |
| Offline availability | runs without network |
| Android deployment complexity | build / packaging risk |

---

## 3. Evaluation datase

Synthetic + de-identified real samples (when permissions allow). Each
example includes ground-truth fields and uncertainty markers.

### 3.1 Categories

- Normal crisis reports.
- Ambiguous reports ("there is some smoke near the river").
- Negation ("there is no fire here").
- Uncertain locations ("near the old bridge").
- Approximate counts ("maybe 20–30 people").
- Bangla-English code-switching.
- Background noise in audio.
- Misleading media (an old photo presented as new).
- Irrelevant content (a meme forwarded during crisis).
- Low-quality / dark / blurry images.
- Non-crisis content (routine social posts).
- Missing fields (no location, no count).

### 3.2 Construction rules

- Ground truth authored by ≥2 reviewers; disagreements resolved.
- All personally identifying information stripped.
- Synthetic media generated for any example that would otherwise
  require identifiable faces / voices.
- No fabricated performance numbers; only measured.

---

## 4. Metrics

| Metric | Definition | Why it matters |
|---|---|---|
| Event-type F1 | precision/recall on `event_type` | routing & preemption correctness |
| Location-text accuracy | exact-match + token-overlap | utility for receivers |
| Critical-field recall | recall on the top-K fields | minimum useful extraction |
| Critical omission rate | rate of missing required fields | avoid silent gaps |
| Fabricated-field rate | rate of invented fields unsupported by input | honesty |
| Valid-schema rate | outputs that parse cleanly | reliability |
| Summary faithfulness | human-rated correctness vs source | prevent misleading summaries |
| Uncertainty calibration | Brier score on confidence vs correctness | honesty |
| Human-correction rate | % of fields edited before confirmation | real-world usefulness |
| Inference latency | end-to-end ms | responsiveness |
| Peak memory | MB during inference | phone survivability |
| Model size | MB on disk | storage cost |
| Energy per inference | Joules / inference (measured) | battery impact |

---

## 5. Device profiles and thresholds

### 5.1 Profiles

| Profile | RAM | SoC class | Examples |
|---|---|---|---|
| Low-end (Tier A) | 2–3 GB | entry-level | older Samsung A-series, generic |
| Mid-range (Tier B) | 4–6 GB | mainstream | current mid-tier |
| High-end (Tier C) | 8+ GB | NPU available | current flagships |

### 5.2 Minimum acceptable thresholds

To be filled at evaluation time, not invented here. Candidates:

- Event-type F1 ≥ X (TBD at evaluation; X is decided by measurement,
  not guessed).
- Critical-field recall ≥ Y (TBD).
- Critical omission rate ≤ Z (TBD).
- Valid-schema rate ≥ W (TBD).
- Peak memory ≤ 800 MB on Tier A.
- Latency ≤ 5 s for short text on Tier B.

Any threshold marked TBD in this draft is unresolved; the plan does
**not** claim or invent them.

### 5.3 Rejection criteria

A model candidate is rejected if:

- It cannot run on Tier A within the device profile thresholds.
- It fails the license / offline-only constraint.
- Its Bangla support or code-switching support is below threshold.
- It fabricates fields more than the omission threshold.
- Its energy per inference is unacceptable on Tier A.

### 5.4 Manual fallback (D-011)

When a candidate is rejected, unavailable, slow, or invalid, the user
sees a **compact structured manual form** that captures the same
fields. The form is the default path in M0; AI is later layered on
top.

### 5.5 Separation from protocol and software correctness

AT-58 through AT-60 gate the extractor interface, offline/manual path,
human confirmation and source preservation. They use only
`Unavailable` and a deterministic `TestDouble`.

AT-61 and AT-62 are physical-device research evidence. A model tha
misses a resource or Bangla-quality threshold is rejected and the app
selects the manual fallback; that negative measurement does not fail the
protocol or invalidate the software-complete release candidate. No
automated test downloads a model.

---

## 6. Decision records

### DR-MODEL-01 — No model selected in this plan

- Decision: no specific model is picked in M0 planning.
- Alternatives: pick a popular multilingual model; pick a Bangla
  specialist; pick a multimodal model.
- Recommended: defer selection until benchmark results exist.
- Reason: avoid premature commitment; respect D-003 / D-011.
- Evidence required: dataset + metrics from §3 / §4.
- Trade-offs: delays M6 timeline.
- Risks: never actually evaluates — mitigated by M6 entry criteria
  requiring benchmark run.
- Validation: M6 acceptance tests reference this document.
- Revisit condition: when M6 begins with a defined benchmark corpus.

### DR-MODEL-02 — Manual form is the M0 default path

- Decision: the M0 default for capsule creation is the manual form.
- Alternatives: force AI; ship without any extraction.
- Recommended: manual form in M0.
- Reason: removes AI runtime as a blocker for M0; honest default per
  D-011.
- Evidence required: AT-15, AT-58 and AT-59 in
  `ACCEPTANCE_TESTS.md`.
- Trade-offs: less demo glamor.
- Risks: users may leave fields blank → mitigated by required-field
  validation in UI.
- Validation: AT-15 and AT-59; status table in README.
- Revisit condition: when an M6 benchmark selects a viable model.

### DR-MODEL-03 — Bangla support is a first-class criterion

- Decision: Bangla + Bangla-English code-switching are scored, no
  assumed.
- Alternatives: assume English-only captions.
- Recommended: Bangla scored.
- Reason: crisis context per `HACKATHON_BRIEF.md`.
- Evidence required: dataset subsections for code-switching.
- Trade-offs: harder to find high-scoring models.
- Risks: rejection criteria may drop popular candidates.
- Validation: model selection gate in M6.
- Revisit condition: none — Bangla scoring is non-negotiable.
