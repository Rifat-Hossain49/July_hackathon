# Shongket — Media Pipeline

**Status:** synthetic M0 media behaviour is implemented. The
source-preserving platform pipeline is scope-frozen for M4; real codec,
device and radio behaviour remains unvalidated.

## 1. Principles

The pipeline must:

1. Preserve the original source bytes and content hash. Derived
   representations and semantic suggestions never replace the source.
2. Be **resumable** across short, interrupted encounters.
3. **Deduplicate** so the same fragment is not stored twice.
4. Be **interruption-tolerant** at any stage.
5. Be **honest** about what the runtime supports — no assumed
   capabilities (no SVC support assumed in M0).
6. Stay **independent** of transport; see `SYSTEM_ARCHITECTURE.md` §6.

Pipeline ordering per modality:

```
Input
  → metadata extraction
  → semantic extraction (suggestion-only, uncertainty-flagged)
  → human correction / confirmation
  → progressive representations
  → chunking (FixedSize SHA-256 in M0)
  → hashing (per chunk and per representation)
  → storage (content-addressed)
  → transfer (signal first, media second per priority)
  → reconstruction (multi-peer missing-chunk completion in M0)
  → validation (hash check)
  → playback or display
```

---

## 2. Per-modality flow

For M4 wire manifests the canonical representation IDs are `thumb`,
`preview`, `standard` and `original`. Names such as `transcript`,
`audio_low`, `poster` and `keyframe_set` below describe modality
profiles that map into those four IDs; they are not additional wire IDs
unless a future schema change is separately approved.

### 2.1 Text

- Input: typed note or transcribed short message.
- Metadata: language tag (bn / en / bn-en-mix), length.
- Semantic extraction: short Bangla summary, structured fields.
- Representations:
  - `text_short` — original text (capsule-adjacent; in signal plane).
- Chunking: text is small; either unchunked or chunked at line
  boundary; same SHA-256 scheme.
- Validation: hash; multi-peer completion only when chunked.

### 2.2 Voice

- Input: audio recording.
- Metadata: duration, sample rate, language hint.
- Semantic extraction: STT → structured fields (model-evaluated, not
  selected in M0).
- Representations:
  - `transcript` (text);
  - `audio_low` (low bitrate Opus or similar — not assumed
    available; revisit at M1 with research);
  - `audio_original`.
- Chunking: fixed-size, sequence-numbered so reorder is detectable.
- Validation: hash; out-of-order tolerant.

### 2.3 Photo

- Input: image.
- Metadata: capture time hint, dimensions.
- Representations:
  - `thumb` (small JPEG/PNG);
  - `preview` (medium-resolution);
  - `standard`;
  - `original` (rarely needed for life-critical content).
- Chunking: fixed-size byte ranges; reassembly yields identical bytes.
- Validation: hash; EXIF stripped by default in shared content.

### 2.4 Video

- Input: video file.
- Metadata: duration, dimensions, container.
- Representations:
  - `poster` (single keyframe);
  - `keyframe_set` (selected keyframes);
  - `preview_clip` (short low-bitrate clip);
  - `standard`;
  - `original`.
- Chunking: fixed-size byte ranges; keyframe-aligned chunking is a
  later research option behind `FragmentationStrategy`.
- Validation: hash; assembly must yield identical bytes.

### 2.5 Document

- Input: PDF or document file.
- Representations:
  - `thumb` (first-page render);
  - `preview` (low-res pages or extracted text);
  - `standard` (compressed original);
  - `original`.
- Chunking: fixed-size byte ranges.
- Validation: hash.

---

## 3. Chunking strategy comparison

| Strategy | Resumability | Dedupe | CPU | Implementation | M0 plan |
|---|---|---|---|---|---|
| Fixed-size | high (simple byte ranges) | high if no edits | low | simple | **default in M0** |
| Content-defined (Rabin / rolling hash) | high | strong across edits | medium | medium | later research |
| Container-aware media segmentation | high | medium | low (parser-specific) | medium | later research |
| Video segment (CMAF / fMP4) | high | medium | medium | medium | later research |
| Keyframe-aligned | high | strong per-clip | high | high | later research |

Decision: M0 = fixed-size. CDC and keyframe-aligned are behind
`FragmentationStrategy` for later research and are not assumed to be
implemented in M0.

---

## 4. Progressive strategy comparison

| Strategy | Usefulness with very few chunks | Complexity | M0 plan |
|---|---|---|---|
| Thumbnail only | medium | low | yes |
| Selected keyframes only | high for video | medium | yes |
| Short critical clip | very high | medium | yes |
| Low-res transcode | high | medium-high | yes |
| Scalable Video Coding (SVC) | very high | very high | **not assumed in M0** |
| Multiple representations | medium | medium | yes (encapsulates the above) |
| Partial file playback | low for proprietary codecs | high | **not assumed in M0** |

Independence from SVC: the architecture does not require SVC. M0 may
ship "thumbnail + keyframe set + short clip" as three separate
representations, and treat SVC adoption as a research question.

---

## 5. Trade-off matrix

| Concern | Effect |
|---|---|
| Transfer resumability | smaller chunks = more granular resumption, more overhead |
| Deduplication | content-defined chunks > fixed-size for edits; equal for new objects |
| Fragment size | median chunk ~16–256 KB depending on modality; M0 default 64 KB |
| Metadata overhead | small compared to fragment sizes; manifest ≤ 32 KB |
| Short contact duration | smaller chunks + priority queue help |
| Reconstruction cost | linear in chunks; trivial in M0 |
| Phone memory | one object can balloon if representations are large |
| Battery | per-chunk verification cost; SHA-256 is cheap |

M0 defaults: 64 KB chunk size for binary modalities; unchunked or
small chunks for text. Per-representation SHA-256 final check.

---

## 6. Implemented baseline and remaining media scope

In M0:

- Representations: `thumb`, `preview` (medium-res or short clip),
  `original`. Standard-quality may be `preview` if no separate
  representation is built.
- Chunking: `FragmentationStrategy` interface; default `FixedSize(64KB)`.
- Hashing: SHA-256 per chunk and per representation.
- Reconstruction: ordinary missing-chunk completion across peers.
- No SVC. No partial-file playback.

M1 hardened canonical chunk, identity, persistence and policy behaviour;
it did **not** add Android codecs or new media functionality.

M4 software scope:

- Source adapters for photo, short video, audio, text and document.
- A `MediaPipeline` platform port with deterministic synthetic fixtures.
- Canonical availability metadata for `thumb`, `preview`, `standard`
  and `original`; unsupported representations are explicit.
- Platform encoding is separate from fixed-size chunking, SHA-256,
  identity, ordering and transport.
- Preview/playback state never presents an incomplete representation as
  complete.
- Local/emulator proof is AT-51 through AT-54. Real-radio proof is
  AT-55 and cannot be claimed from an emulator.

---

## 7. Research pipeline (M5+)

- Content-defined chunking for better dedup after edits.
- Keyframe-aligned chunking for video.
- Container-aware segmentation when parsers are available and
  license-compatible.
- SVC adoption **only after** a small, license-clean, runtime-feasible
  encoder/decoder is selected and benchmarked.
- Erasure coding for robustness — see `RESEARCH_LOG.md` §Coded delivery.

---

## 8. Decision records

### DR-MEDIA-01 — Fixed-size M0 chunking

- Decision: M0 uses fixed-size chunks behind `FragmentationStrategy`.
- Alternatives: CDC, keyframe-aligned, container-aware.
- Recommended: fixed-size in M0; alternatives behind the same
  interface for later research.
- Reason: simplest correct boundary; minimal assumptions about
  runtime parsers.
- Evidence required: AT-10, AT-21, AT-51 and AT-54.
- Trade-offs: weaker dedup across edits than CDC.
- Risks: re-chunking on small edits → revisit at M5+.
- Validation: `EXPERIMENT_PLAN.md` H-MEDIA-1.
- Revisit condition: dedup measurements justify CDC.

### DR-MEDIA-02 — Progressive representations without SVC

- Decision: M0 progressive delivery does not require SVC.
- Alternatives: SVC, multiple representations.
- Recommended: multiple representations in M0; SVC explicitly
  deferred.
- Reason: SVC requires specific codec availability that this plan does
  not assume.
- Evidence required: AT-51, AT-52, AT-53 and AT-55.
- Trade-offs: more representations to maintain; small metadata cost.
- Risks: if no runtime encoder is available at M3, the "preview" must
  fall back to "thumbnail only."
- Validation: explicit status table row in README.
- Revisit condition: once a license-clean SVC candidate is evaluated
  (see `MODEL_EVALUATION_PLAN.md` for device feasibility).

### DR-MEDIA-03 — Multi-peer reconstruction uses ordinary missing chunks in M0

- Decision: M0 reconstruction does not use erasure / rateless codes.
- Alternatives: Reed-Solomon, fountain codes, RaptorQ.
- Recommended: ordinary missing-chunk completion in M0.
- Reason: do not claim coding that isn't implemented.
- Evidence required: M0 success criterion 5.
- Trade-offs: lower robustness to peer dropout than coded.
- Risks: docs confusing "multi-peer" with "coded."
- Validation: explicit separation in README, EXPERIMENT_PLAN, MILESTONES.
- Revisit condition: post-M5 review of coding extension.

### DR-MEDIA-04 — Source media always preserved

- Decision: AI-extracted summaries never replace the source media.
- Alternatives: "summary only" mode.
- Recommended: source media preserved and linked to capsule.
- Reason: D-004 + auditability + falsifiability.
- Evidence required: AT-21, AT-54 and AT-60.
- Trade-offs: storage cost.
- Risks: storage pressure on low-end devices → eviction policy.
- Validation: explicit status table row in README.
- Revisit condition: storage targets met or relaxed.
