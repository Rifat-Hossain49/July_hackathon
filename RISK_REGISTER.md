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
| R-13 | Fragment flooding / resource exhaustion | M | M | high | deterministic per-peer in-flight frame and pending-byte caps; size limits; dedup | refuse excess input and retain bounded state | Protocol lead | M2, M7 | no |
| R-14 | Battery drain during transfers | M | M | medium | battery-aware scheduler; tier profile | default to lower rate under threshold | Android lead | M7 | no |
| R-15 | Storage exhaustion on low-end devices | H | M | high | rejection-only budget; explicit unavailable/storage UX; device measurement | refuse before mutation; user frees space | Product lead | M3, M7 | no |
| R-16 | Video transcode latency too high on Tier A | M | M | high | modular transcode; allow skipping preview | preview unavailable, show clear status | Media lead | M4, M6 | no |
| R-17 | Failed multi-peer reconstruction | M | H | medium | sufficient peer count assumed; multi-peer telemetry | fall back to single-peer; surface error | Protocol lead | M5 | yes |
| R-18 | Demo-device incompatibility | M | H | medium | smoke-test gate; backup devices | use backup devices | Demo lead | M9 | yes |
| R-19 | Public claims exceeding measurements | M | H | medium | D-012 status tags; cite measurement | remove claim; revise README | Product lead | M9 | yes |
| R-20 | Transport smoke-test gate failure (no adapter passes) | M | H | high | multiple adapters in research | block M3; prototype with alt adapter | Android lead | M3 | yes |
| R-21 | Hash collision (SHA-256) | L | H | low | SHA-256 standard; collision-handling policy | reject and surface error | Security lead | M1+ | no |
| R-22 | Replay / out-of-order fragments | M | M | medium | sequence numbers; expiry; per-object monotonic IDs | reject + counter | Protocol lead | M1+ | no |
| R-23 | Manifest poisoning (signed by an untrusted signer) | M | H | medium | signature verification; trust anchor list | reject; flag signer | Security lead | M1+ | no |
| R-24 | Manifest / schema mismatch across versions | M | M | high | explicit versioning; clear errors | reject; surface error | Protocol lead | M1+ | no |
| R-25 | A future probabilistic inventory produces harmful false positives | M | M | high | exact inventory remains canonical; separate experiment and approval required | keep exact-list/bitmap implementation | Protocol lead | Later research | no |
| R-26 | Demo flakiness on first attempt | H | H | medium | repeated demo reliability test | rehearse + scripted fallback | Demo lead | M9 | yes |
| R-27 | Over-trust of AI by reviewers / users | M | M | medium | explicit "AI is suggestion" language | human-confirm gate | Responsible-AI lead | M6, M9 | no |
| R-28 | Ethical risk: misuse for disinformation | L | H | low | signer identity ≠ fact distinction; expiry | revocation + log | Responsible-AI lead | M7, M9 | no |
| R-29 | Storage of private media on shared infrastructure | L | H | low | no cloud by default; local-only | explicit deletion | Product lead | M1+ | no |
| R-30 | Development test keys used outside tests | L | H | high | unmistakable fixtures, release scan and separate key-store port | block release and generate a new production trust root manually | Security lead | M7, M9 | yes |
| R-31 | M1 refactor silently breaks M0 evidence | M | H | high | AT-37 gates on all 125 M0 tests unchanged plus recorded CLI/metrics hashes | revert slice; `main` retains merged M0 | Protocol lead | M1 | yes |
| R-32 | Migration corrupts in-progress transfer state | L | H | medium | retain pre-migration document until migrated one is durable; AT-25, AT-29 | original document still loads unchanged | Protocol lead | M1 | yes |
| R-33 | Version-format change alters serialized bytes | M | M | high | `…v1` read as `…v1.0`; compare CLI hash each slice (AT-22) | revert versioning slice | Protocol lead | M1 | yes |
| R-34 | Platform-divergent fsync / rename semantics | M | M | medium | test on target platform; document POSIX vs Windows differences; AT-26 | retain M0 write path | Protocol lead | M1, M2 | no |
| R-35 | M1 scope creep into M2+ behaviour | M | H | high | every slice maps to a canonical requirement; hop/copy enforcement explicitly confirmed as completing PROTOCOL_SPEC §6.0 | revert slice; re-scope | Product lead | M1 | yes |
| R-36 | Kotlin behaviour drifts from the canonical Python core | M | H | high | committed language-neutral vectors; AT-39 on every build | reject the Kotlin change; Python remains canonical | Protocol lead | M3+ | yes |
| R-37 | Android background restriction silently abandons a transfer | M | H | medium | platform-permitted coordinator, durable state and restart tests | resume on next launch; never claim uninterrupted survival | Android lead | M3, M7 | yes |
| R-38 | Emulator result is presented as device or radio evidence | M | H | high | six explicit automation levels and separate A/B gates | retract claim; rerun on the required boundary | Product lead | M3–M9 | yes |
| R-39 | Backup or device-transfer path exposes private local state | L | H | medium | app-private storage, backup/data-extraction exclusions and target-device inspection | block release; clear affected state and revise rules | Security lead | M7, M9 | yes |
| R-40 | Diagnostic export contains capsule, media, peer or key material | L | H | high | allow-list schema, content-free evidence and field-level scan | disable export and block release | Security lead | M7, M9 | yes |
| R-41 | Build requires unavailable network dependencies during crisis use | M | M | high | pinned dependency inventory and offline runtime test; no runtime cloud dependency | ship manual/core subset only | Release lead | M3, M9 | yes |
| R-42 | Production signing or trust-root choice is embedded prematurely | L | H | high | manual release decision; no production material in repository | revoke material and block publication | Product owner | M9 | yes |
| R-43 | Field trial proceeds without site, participant or privacy approval | L | H | high | MRD-05 and AT-78 informed-consent gate | cancel trial; retain lab/software evidence only | Product owner | M9 | yes |
| R-44 | Optional offline model blocks app usability | M | H | high | `Unavailable` default and manual form; AT-59 | remove model package and use manual path | Model lead | M6 | yes |
| R-45 | Bangladesh host is not reachable through one or more target ISPs/BDIX | H | H | high | named-host/two-ISP field gate; route evidence before publication | report unsupported ISP; move to a proven domestic provider or use nearby mode | Network operator | BDIX hub | yes |
| R-46 | Domestic DNS or TLS renewal fails during a global outage | M | H | medium | domestically reachable authoritative DNS; provision certificate before outage; documented IP/hosts fallback with no warning bypass | distribute corrected hostname/IP mapping before disruption; keep nearby fallback | Network operator | BDIX hub | yes |
| R-47 | Public hub is abused for spam, dangerous claims or resource exhaustion | H | H | high | public-only warning, expiry, strict schema, rate/channel/global/database caps and operator retention decision | reduce caps, restrict announced channels or take hub offline; never present content as verified fact | Product owner / Operator | BDIX hub | yes |
| R-48 | Users mistake a public incident code for a private room | M | H | high | UI states PUBLIC repeatedly; literal public acknowledgement; server refuses private visibility | remove affected public content under operator policy; revise channel instructions | Product owner | BDIX hub | yes |
| R-49 | Central hub observation or seizure exposes public message/location data | M | H | high | collect no account, GPS, contact or analytics data; HTTPS; short expiry; no content in ops logs | stop collection, preserve incident evidence lawfully and notify affected operators under the chosen policy | Security lead / Operator | BDIX hub | yes |
| R-50 | Software evidence is presented as blackout or BDIX field validation | M | H | high | BH software/field statuses separated in UI, docs and acceptance catalogue | retract the claim and execute the named-host/two-ISP gate | Product lead | BDIX hub | yes |
| R-51 | Friendly `.local` name does not resolve on a client or access point | H | M | high | numeric Wi-Fi URL is primary; mDNS is optional and visibly device-dependent | try named Android/iPad devices; retain numeric URL | Product lead | Local access point | yes |
| R-52 | Laptop receives a different DHCP address after reconnecting | H | M | high | detect and print the current private address at every start | reserve the laptop Wi-Fi MAC/address in the access point DHCP settings | Network operator | Local access point | yes |
| R-53 | Guest/client isolation prevents peers reaching the laptop | M | H | high | explicit same-link boundary and health status; no bypass claim | disable isolation on a trusted AP or use a controlled travel router | Network operator | Local access point | yes |
| R-APPROVAL-01 | Misreading a global or out-of-scope approval as permission for code work | M | H | medium | exact per-milestone software ledger plus preserved `IMPLEMENTATION_STATUS`; AGENTS.md verification requires both scope and exclusions | revert unauthorized code; re-confirm ledger boundary; notify product owner | Product owner / Principal architect | All | yes |

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
