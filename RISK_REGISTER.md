# Shongket — Risk Register (Draft 1)

Each risk: ID / description / probability / impact / detectability /
mitigation / contingency / owner role / milestone / implementation-blocking.

Probabilities and impacts are coarse (L/M/H).

| ID | Description | P | Impact | Detectability | Mitigation | Contingency | Owner | Milestone | Blocking? |
|---|---|---|---|---|---|---|---|---|---|
| R-01 | Novelty overclaim ("replaces internet") | M | H | medium | public-status table; D-006; D-012 tags | tighten README + presenter script | Product lead | M9 | yes |
| R-02 | "Internet replacement" confusion in demo | M | H | high | script + status table | rule script before demo | Demo lead | M9 | yes |
| R-03 | Android vendor fragmentation breaking transport | H | H | medium | smoke-test gate | fall back to adapter that passes; else block M3 | Android lead | M3 | yes |
| R-04 | Wi-Fi Direct permission complexity (location, nearby-devices) | H | M | high | explicit permission doc; UI surface | document workaround | Android lead | M3 | no |
| R-05 | Nearby Connections dependency on Play Services | H | M | high | adapter abstraction; alt adapter ready | use alt adapter (LAN sockets) | Android lead | M3 | no |
| R-06 | Unsupported devices (low-end, no Nearby) | M | M | high | device-tier profile; fallback UI | shrink feature set on low tier | Product lead | M3, M7 | no |
| R-07 | Model too large for low-tier phones | M | H | high | `MODEL_EVALUATION_PLAN.md` thresholds; manual form fallback | manual form (D-011) | Model lead | M6 | yes |
| R-08 | Weak Bangla extraction | M | H | medium | Bangla scored in benchmark | reject model; manual form | Model lead | M6 | yes |
| R-09 | Semantic omissions of critical fields | M | H | medium | critical-field recall metric; required-field validation | reject + manual form | Model lead | M6 | yes |
| R-10 | False urgency (model inflates priority) | M | H | medium | human-confirm required (D-003); uncertainty flagging | default to lower priority until confirmed | Product lead | M6 | yes |
| R-11 | Private content spreading without consent | L | H | low | explicit consent gate per object class | revoke + log | Product lead | M5, M7 | yes |
| R-12 | Malicious payloads from peer | M | H | high | schema validation; size limits; signature checks | reject + counter signal | Security lead | M1+ | no |
| R-13 | Fragment flooding / resource exhaustion | M | M | high | per-peer caps; rate limits; object caps | per-peer block list | Protocol lead | M1, M3 | no |
| R-14 | Battery drain during transfers | M | M | medium | battery-aware scheduler; tier profile | default to lower rate under threshold | Android lead | M7 | no |
| R-15 | Storage exhaustion on low-end devices | H | M | high | eviction policy; storage caps | evict routine priority first | Product lead | M3, M7 | no |
| R-16 | Video transcode latency too high on Tier A | M | M | high | modular transcode; allow skipping preview | preview unavailable, show clear status | Media lead | M4, M6 | no |
| R-17 | Failed multi-peer reconstruction | M | H | medium | sufficient peer count assumed; multi-peer telemetry | fall back to single-peer; surface error | Protocol lead | M5 | yes |
| R-18 | Demo-device incompatibility | M | H | medium | smoke-test gate; backup devices | use backup devices | Demo lead | M9 | yes |
| R-19 | Public claims exceeding measurements | M | H | medium | D-012 status tags; cite measurement | remove claim; revise README | Product lead | M9 | yes |
| R-20 | Transport smoke-test gate failure (no adapter passes) | M | H | high | multiple adapters in research | block M3; prototype with alt adapter | Android lead | M3 | yes |
| R-21 | Hash collision (SHA-256) | L | H | low | SHA-256 standard; collision-handling policy | reject and surface error | Security lead | M1+ | no |
| R-22 | Replay / out-of-order fragments | M | M | medium | sequence numbers; expiry; per-object monotonic IDs | reject + counter | Protocol lead | M1+ | no |
| R-23 | Manifest poisoning (signed by an untrusted signer) | M | H | medium | signature verification; trust anchor list | reject; flag signer | Security lead | M1+ | no |
| R-24 | Manifest / schema mismatch across versions | M | M | high | explicit versioning; clear errors | reject; surface error | Protocol lead | M1+ | no |
| R-25 | Bloom filter false-positive rate too high | M | M | high | M0 inventory profiling; tunable params | switch to explicit-list fallback | Protocol lead | M0, M5 | no |
| R-26 | Demo flakiness on first attempt | H | H | medium | repeated demo reliability test | rehearse + scripted fallback | Demo lead | M9 | yes |
| R-27 | Over-trust of AI by reviewers / users | M | M | medium | explicit "AI is suggestion" language | human-confirm gate | Responsible-AI lead | M6, M9 | no |
| R-28 | Ethical risk: misuse for disinformation | L | H | low | signer identity ≠ fact distinction; expiry | revocation + log | Responsible-AI lead | M7, M9 | no |
| R-29 | Storage of private media on shared infrastructure | L | H | low | no cloud by default; local-only | explicit deletion | Product lead | M1+ | no |
| R-30 | Compromised test keys used outside M0 | L | M | low | clear test/prod separation | rotate keys before release | Security lead | M0, M1 | no |
| R-31 | M1 refactor silently breaks M0 evidence | M | H | high | AT-37 gates on all 125 M0 tests unchanged plus recorded CLI/metrics hashes | revert slice; `main` retains merged M0 | Protocol lead | M1 | yes |
| R-32 | Migration corrupts in-progress transfer state | L | H | medium | retain pre-migration document until migrated one is durable; AT-25, AT-29 | original document still loads unchanged | Protocol lead | M1 | yes |
| R-33 | Version-format change alters serialized bytes | M | M | high | `…v1` read as `…v1.0`; compare CLI hash each slice (AT-22) | revert versioning slice | Protocol lead | M1 | yes |
| R-34 | Platform-divergent fsync / rename semantics | M | M | medium | test on target platform; document POSIX vs Windows differences; AT-26 | retain M0 write path | Protocol lead | M1, M2 | no |
| R-35 | M1 scope creep into M2+ behaviour | M | H | high | every slice maps to a canonical requirement; hop/copy enforcement explicitly confirmed as completing PROTOCOL_SPEC §6.0 | revert slice; re-scope | Product lead | M1 | yes |
| R-APPROVAL-01 | Misreading a global "APPROVED" or out-of-scope milestone approval as permission for code work | M | H | medium | `IMPLEMENTATION_STATUS` only accepts `NOT_APPROVED`, `APPROVED_FOR_MILESTONE_0`, `APPROVED_FOR_MILESTONE_1`, etc.; AGENTS.md "Workflow verification" requires per-milestone approval match | revert any unauthorized code; re-confirm milestone boundary; notify product owner | Product owner / Principal architect | All | yes |

---

## Decision records

### DR-RISK-01 — Risks above implementation-blocking threshold must close before milestone approval

- Decision: any risk marked **yes** in the Blocking column must have
  mitigation documented before the milestone's implementation approval.
- Alternatives: approve and accept risk.
- Recommended: gate approval on blocking risks.
- Reason: avoid approving milestones with known unacceptable risks.
- Evidence required: documented mitigation.
- Trade-offs: slower approval.
- Risks: gate becomes the bottleneck.
- Validation: per-milestone approval checklist.
- Revisit condition: none.

### DR-RISK-02 — Demo risks gate M9

- Decision: R-18, R-19, R-26 must be at acceptable residual levels
  before M9.
- Alternatives: run demo anyway.
- Recommended: gate.
- Reason: live-demo reliability is a rubric criterion.
- Evidence required: 10× repeated runs.
- Trade-offs: time pressure near demo.
- Risks: gate fails too late to recover.
- Validation: rehearsal schedule.
- Revisit condition: M9 readiness review.
