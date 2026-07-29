# AI Usage

## Status

Planning-only. This repository contains planning documents. No
implementation code has been authored yet (see
[PRODUCT_DECISIONS.md](./PRODUCT_DECISIONS.md) `IMPLEMENTATION_STATUS`).

## Planning assistance

Drafting of the planning documents in this repository was assisted
by Claude Opus 4.8 (Anthropic), used as a planning-aid tool under
human direction. The human product owner / principal architect
remains responsible for every claim, every architectural decision,
and every boundary stated in this plan.

## What the AI was used for

- structuring and tightening the planning documents;
- surfacing terminology contradictions (e.g. "coded reconstruction"
  vs "multi-peer completion") and proposing consistent wording;
- enumerating risks, acceptance tests, and milestones so that they
  could be reviewed by the human owner;
- drafting experiment hypotheses that the human owner then accepted,
  modified, or rejected.

## What the AI was NOT used for

- selecting an Android transport (selection is gated by the M3
  transport smoke-test gate);
- selecting an on-device AI model (selection is benchmark-driven per
  [MODEL_EVALUATION_PLAN.md](./MODEL_EVALUATION_PLAN.md));
- determining real-world Bangla performance (this requires M6+
  measurements and is currently an **unverified hypothesis**);
- fabricating device support or library capabilities that have not
  been verified (see [RESEARCH_LOG.md](./RESEARCH_LOG.md)).

## Determinism rule

Deterministic protocol logic (priority ordering, fragmentation
indexing, content hashing, expiry handling, duplicate detection,
restart recovery) is **not** delegated to an AI. Where this plan
describes such logic, it is specified by the protocol owner, not
inferred from a model.

## Acceptance

The human owner has reviewed each planning document and accepts
responsibility for the boundary between AI-assisted drafting and
human-authored product decisions. See
[PRODUCT_DECISIONS.md](./PRODUCT_DECISIONS.md) for the current
approval status.
