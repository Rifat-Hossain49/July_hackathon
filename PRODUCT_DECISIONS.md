# Shongket Product Decisions

## Current status

IMPLEMENTATION_STATUS: APPROVED_FOR_MILESTONE_0

Implementation must not begin until this value is changed to
APPROVED_FOR_MILESTONE_0 (or later milestone-scoped approval).

### Milestone 0 implementation evidence

Milestone 0 work authorised by the boundary below is implemented in
`app/simulator/` and covered by 125 passing automated tests (0 failed, 0
skipped) across the 18 M0-blocking acceptance IDs. Evidence is recorded
in `ACCEPTANCE_TESTS.md` and `EXPERIMENT_PLAN.md`.

This status value is unchanged by that work. Milestone 1 and later work
remains unauthorised, and no later-milestone status has been granted.

## Implementation approval policy

Implementation approval is milestone-specific.

A global `IMPLEMENTATION_STATUS: APPROVED` value is prohibited.

Valid approval values include:

- `NOT_APPROVED`
- `APPROVED_FOR_MILESTONE_0`
- `APPROVED_FOR_MILESTONE_1`

Approval for Milestone 0 does not authorize Milestone 1 or later work.

## Milestone 0 approval boundary

When Milestone 0 is approved, it authorizes only:

- an executable protocol simulator;
- synthetic deterministic media;
- simulated peers and encounters;
- deterministic priority scheduling;
- fixed-size chunks;
- SHA-256 integrity verification;
- ordinary multi-peer chunk completion;
- simulated interruption and restart recovery;
- lightweight persistence;
- metrics required by EXPERIMENT_PLAN.md.

It does not authorize:

- Android development;
- Nearby Connections;
- Wi-Fi Direct;
- local hotspot networking;
- physical wireless experiments;
- offline AI model integration;
- production cryptographic identity;
- production encryption;
- content-defined chunking;
- Reed-Solomon;
- fountain coding;
- RaptorQ;
- Milestone 1 or later implementation.

## Product thesis

Shongket is a semantic-first, content-centric and disruption-tolerant
multimedia distribution protocol for partial-connectivity crises.

It immediately distributes a compact, human-confirmed semantic capsule,
then progressively distributes previews and original-quality multimedia
through nearby peer-to-peer connections and store-carry-forward relays.

## Locked decisions

### D-001: Not a messenger

Shongket is not a generic Bluetooth, Wi-Fi Direct or mesh chat application.

Its primary networking unit is a content object containing:

1. a semantic capsule;
2. progressive media representations;
3. integrity metadata;
4. independently transferable media fragments.

### D-002: Dual-plane design

Shongket has two logical planes:

- Signal plane: semantic capsules, manifests, priorities and inventories.
- Media plane: thumbnails, keyframes, previews and original media fragments.

### D-003: Human-confirmed intelligence

An offline model may extract:

- event type;
- location;
- urgency suggestion;
- affected people;
- requested action;
- short Bangla summary;
- significant media timestamps.

The user must be able to review and correct these fields before publishing.

The model must not independently declare that a report is true.

### D-004: Original media preservation

AI-generated summaries never replace the source media.

The source media must remain:

- content-addressed;
- integrity-verifiable;
- reconstructable;
- clearly linked to its semantic capsule.

### D-005: Transport-independent core

Protocol and scheduling logic must not depend directly on one transport API.

Initial candidate transports:

- Nearby Connections;
- Wi-Fi Direct;
- local Wi-Fi sockets.

Additional transports may be explored later.

### D-006: Nearby high-rate transfer

Shongket may provide high-rate multimedia transfer between nearby devices.

It must not claim guaranteed broadband or real-time HD delivery between
distant users when no continuous high-bandwidth path exists.

### D-007: Progressive usefulness

The receiver should obtain information in this order:

1. critical semantic capsule;
2. thumbnail or keyframe;
3. short low-resolution preview;
4. standard representation;
5. original-quality representation.

### D-008: Interruption tolerance

A transfer interrupted after a short encounter must still preserve all
verified fragments already received.

The receiver may continue reconstruction using fragments obtained from
other peers.

### D-009: Critical preemption

A newly created critical capsule must be able to preempt a lower-priority
bulk media transfer.

### D-010: Offline core

Core capture, semantic review, storage, synchronization and reconstruction
must not require cloud connectivity.

### D-011: AI fallback

If the local model is unavailable or too slow, the user must be able to
create the semantic capsule through a compact structured form.

### D-012: Honest demonstration

Every feature must be classified as:

- fully implemented;
- experimentally implemented;
- simulated;
- planned.

Simulated behavior must never be presented as real networking behavior.

## Open decisions

- Android transport for the first prototype
- Initial chunk size
- Erasure/fountain coding implementation
- Content inventory representation
- Offline model and runtime
- Video keyframe extraction approach
- Private versus public content encryption
- Device compatibility target
- Measurable throughput target

The following surfaced during Milestone 0 implementation and are
recorded here as open, not resolved:

- **Canonical private/consent field names.** `PROTOCOL_SPEC.md` §8
  requires explicit consent before forwarding private content, and
  AT-16 assumes a "private marker", but no §3 schema names the fields
  that carry either. The M0 simulator uses provisional manifest fields
  `private` and `forwarding_consent`; the names need freezing in the
  schema before M1.
- **`PeerCapabilities.public_only` interaction.** §3.5 declares this
  peer property, but no document defines how it composes with an
  object's private marker and consent. M0 implements the object-side
  gate only and leaves the interaction unspecified.
- **Device-side storage eviction.** AT-12 splits into an M0 rule and an
  M5+ effect. M0 implements refusal with the canonical `out_of_budget`
  status; which content is evicted under real device pressure, and in
  what order, is undecided.
- **Later Android transport choices.** Unchanged and still open; M0
  asserts nothing about any radio transport.