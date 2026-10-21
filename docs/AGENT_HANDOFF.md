# Agent handoff

This document is the fastest safe entry point for a new coding agent.

## Project in one minute

RailConfirm Intelligence is planned as a research-backed web application that estimates final reservation outcomes for Indian Railways WL/RAC tickets. It should produce passenger-level probabilities and, when evidence supports it, group-level probabilities for outcomes such as all passengers CNF or all passengers CNF/RAC.

The repository currently contains specifications and governance documentation. Do not assume a working frontend, API, database, model, dataset or live provider exists just because their interfaces are documented.

The current implementation scope (roadmap Phases 0–7) is local-first: no third-party runtime API, live PNR lookup, polling, news/event feed or hosted inference. The product may implement its own internal API. These external data integrations remain planned core capabilities of the long-term product in roadmap Phases 8–10; do not build them now, but do not remove them from the goal. Agents may research and prepare candidate datasets offline, but every candidate must pass docs/data/DATASET_INTAKE_CHECKLIST.md.

## Read first

1. AGENTS.md
2. Project status
3. Roadmap
4. Product brief and requirements
5. Implementation plan
6. ADR index, especially ADR-0007 (current local-first build boundary) and ADR-0008 (future core integration phases)
7. Dataset intake checklist and data acquisition policy
8. Evaluation protocol

## Non-negotiable constraints

- Do not invent training data, probabilities, evaluation results or source permissions.
- Do not enable unapproved PNR automation.
- Do not collect passenger names for prediction.
- Do not let future observations enter historical feature snapshots.
- Do not claim group outcomes from independent multiplication unless it is clearly an evaluated baseline.
- Show a structured unsupported/abstain result when no validated model or source is available.
- Keep synthetic fixtures clearly labelled and out of real-world performance reporting.
- Update docs/changelog/session log and create a new sequential ADR for material decisions.
- Prefer meaningful commits; do not create a commit count target.

## First task

Read docs/ROADMAP.md and implement Phase 1: the domain contract and status parsing layer with unit tests. In parallel or before model training, have a research agent inventory candidate datasets and submit intake reports; do not integrate any external runtime API in Phases 0–7. Keep later live-status and verified-context integration capabilities represented in the architecture, with source-specific decisions deferred until their roadmap phases. Before finalizing any raw status mapping, verify the intended mapping from an authoritative source and record that reference. Preserve raw input and model unknown values explicitly.

Do not begin with live PNR integration or a complex model. Data rights and historical outcome availability are still explicit project dependencies.

## Expected deliverable from the first implementation session

- typed domain structures for journey and passenger status;
- parsing/normalization functions;
- validation errors and stable reason codes;
- tests for CNF/RAC/WL, unknown codes, missing positions and mixed groups;
- a short developer setup and test command;
- updated project status and session log;
- ADR only if a new material decision is made.

## If blocked

Report the exact missing evidence or provider permission and continue with work that does not depend on it. Do not replace a blocker with a fabricated implementation. If stack, data semantics or targets need a material change, propose and record the decision rather than silently choosing a different direction.
