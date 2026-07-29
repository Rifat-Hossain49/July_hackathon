# AGENTS.md

## Project

Shongket is a semantic-first, disruption-tolerant multimedia distribution
protocol for partial-connectivity crisis environments.

Read these files before performing any substantial task:

1. HACKATHON_BRIEF.md
2. RUBRIC.md
3. PRODUCT_DECISIONS.md
4. ACCEPTANCE_TESTS.md
5. SYSTEM_ARCHITECTURE.md
6. PROTOCOL_SPEC.md

## Implementation gate

The allowed implementation statuses are:

- `NOT_APPROVED`
- `APPROVED_FOR_MILESTONE_0`
- `APPROVED_FOR_MILESTONE_1`
- milestone-specific approvals added later

`APPROVED` by itself is not a valid status.

When the status is `NOT_APPROVED`:

- planning and documentation changes are allowed;
- implementation code must not be created or modified.

When the status is `APPROVED_FOR_MILESTONE_0`:

- only Milestone 0 work defined in `MILESTONES.md` is permitted;
- Milestone 1 and later work remains prohibited;
- no Android, wireless transport, production AI, production encryption,
  Reed-Solomon, fountain-code or RaptorQ implementation is permitted.

Approval for one milestone must never be interpreted as approval for later
milestones.

## Workflow verification

Before implementation, verify that PRODUCT_DECISIONS.md contains the exact
milestone-specific approval required for the requested work.

## Required working process

For every substantial task:

1. Inspect the relevant repository files.
2. Restate the task and acceptance criteria.
3. Identify assumptions and unresolved questions.
4. List files that will be created or modified.
5. Propose the smallest valid change.
6. Make the change only after the task allows implementation.
7. Run relevant verification.
8. Report results, limitations and remaining risks.

## Scope rules

- Do not turn the project into a generic chat application.
- Do not add authentication, maps, dashboards or cloud services unless
  explicitly approved.
- Do not introduce multi-agent architecture merely for complexity.
- Do not add AI features without a measurable purpose.
- Do not make cloud AI part of the offline core.
- Do not silently replace original media with generated content.
- Do not describe nearby peer-to-peer transfer as global internet access.
- Do not claim guaranteed delivery.
- Do not describe application-level relaying as standards-based mesh
  networking unless it actually implements the relevant standard.

## Architecture rules

- Keep protocol logic independent from Android transport APIs.
- Keep semantic extraction independent from networking.
- Keep media processing independent from transport.
- Prefer interfaces around transport, storage and model runtimes.
- Pure protocol logic should be testable without physical devices.
- Deterministic logic must not be delegated to an LLM.
- All network payloads require schema validation and size limits.
- All media fragments require integrity verification.

## Research rules

For changing or specialized technical claims:

- consult primary documentation, standards or papers;
- record the source in RESEARCH_LOG.md;
- state the date accessed;
- separate verified facts from design assumptions;
- do not invent library capabilities or device support.

## Security and privacy

- Never commit secrets or credentials.
- Do not log private message content by default.
- Validate all received payloads.
- Limit payload sizes and resource consumption.
- Clearly distinguish signed identity from factual verification.
- Require user confirmation before publicly forwarding private content.
- Treat all peer input as untrusted.

## Dependency rules

Before adding a dependency, document:

- its purpose;
- license;
- maintenance status;
- binary size;
- offline behavior;
- platform requirements;
- whether a smaller alternative exists.

Do not add a dependency solely to avoid implementing a small deterministic
component.

## Testing rules

Tests must cover:

- interrupted transfer;
- duplicate fragments;
- corrupted fragments;
- expired content;
- restart recovery;
- critical-message preemption;
- partial reconstruction;
- low-storage conditions;
- unsupported transport;
- denied permissions;
- malformed peer payloads.

## Completion report

Every completed task must report:

- files changed;
- behavioral changes;
- tests executed;
- results;
- assumptions;
- unresolved issues;
- next recommended task.