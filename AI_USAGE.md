# AI Usage

## Status

This repository contains implemented M0/M1 code and planning for the
remaining milestones. M0/M1 implementation evidence is recorded in
`ACCEPTANCE_TESTS.md`; authorisation remains governed by
[PRODUCT_DECISIONS.md](./PRODUCT_DECISIONS.md).

## Planning assistance

Drafting and review of repository documentation and implementation was assisted
by Claude Opus 4.8 (Anthropic), used as a planning-aid tool under
human direction. The human product owner / principal architec
remains responsible for every claim, every architectural decision,
and every boundary stated in this plan.

The interrupted remaining-scope recovery, scope freeze and approval
documentation were completed with OpenAI Codex. This documentation task
did not write or modify application code.

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
- fabricating device support or library capabilities that have no
  been verified (see [RESEARCH_LOG.md](./RESEARCH_LOG.md)).

## Determinism rule

Deterministic protocol logic (priority ordering, fragmentation
indexing, content hashing, expiry handling, duplicate detection,
restart recovery) is **not** delegated to an AI. Where this plan
describes such logic, it is specified by the protocol owner, no
inferred from a model.

## Acceptance

The human owner has reviewed each planning document and accepts
responsibility for the boundary between AI-assisted drafting and
human-authored product decisions. See
[PRODUCT_DECISIONS.md](./PRODUCT_DECISIONS.md) for the curren
approval status.
