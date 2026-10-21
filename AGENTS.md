# Agent operating guide

This file is the repository-wide instruction set for coding agents and automated contributors. Read it before making changes. More specific `AGENTS.md` files may add rules for their directories; they do not silently override the requirements here unless they explicitly explain the scope.

## Working agreement

- Work from the current repository state. Inspect relevant files, existing tests, open issues and recent decisions before editing.
- Do not ask for permission for routine, reversible work that is clearly within the task. Do not make irreversible, external, financial, security-sensitive or access-control changes without explicit authorization.
- Do not claim that a test, build, deployment, data ingestion or model evaluation ran unless it actually ran. Include commands and outcomes in the session summary.
- Do not fabricate sources, datasets, observations, benchmarks, probabilities, API capabilities, provider permissions or commit history.
- Keep documentation in the same style as the project: direct, specific, readable, technically honest, and without marketing filler.
- Prefer a small number of coherent, meaningful commits over artificial commit volume. Never split one change into many commits solely to inflate activity.
- Preserve user changes. Do not force-push, rewrite published history, delete user work, or overwrite files without inspecting them first.
- Use clear commit messages in imperative or Conventional Commit style, consistent with surrounding history.
- Update the changelog and development log for meaningful project milestones. These are not substitutes for commit history.

## Decisions and session records

- Read `docs/adr/README.md` and relevant ADRs before making architectural, data, model, privacy, security, deployment or licensing decisions.
- Create the next sequential ADR (`ADR-0001.md`, `ADR-0002.md`, …) when a material decision is made. ADRs are numbered, append-only records; do not renumber older records.
- One cohesive implementation session may create one ADR covering related decisions. Do not create an ADR for every trivial edit or every tool invocation. If a session introduces multiple independent material decisions, create separate ADRs.
- If an ADR is superseded, retain it and create a new ADR that links to the old one.
- Update `CHANGELOG.md` for user- or developer-visible changes and `docs/DEVELOPMENT_LOG.md` at meaningful session boundaries. Log the actual date, scope, evidence, tests run and unresolved issues; do not invent elapsed time or outcomes.
- For experiments, record a reproducible configuration, dataset provenance, split logic, metric definitions and results. Mark pending work as pending.

## Current execution scope (ADR-0007)

- The current build is local-first and must not depend on third-party runtime APIs or providers.
- Do not implement live PNR lookups, scheduled ticket polling, external news/calendar/weather/event feeds, or hosted model inference in the current roadmap.
- An internal API between the project's own frontend and backend is allowed.
- Agents may research and prepare candidate data files outside the product runtime. Every candidate must pass docs/data/DATASET_INTAKE_CHECKLIST.md and be recorded in docs/data/SOURCE_REGISTER.md before training.
- Agent-sourced data is not automatically approved. Verify source provenance, relevant terms, storage/training/publication rights, privacy, label meaning and schema quality. If a term or right is unclear, mark the dataset quarantined or under review.
- Do not add hidden network calls to app startup, the manual prediction path, unit tests or CI.
- Any proposal to reopen external integrations must be documented in a new sequential ADR before implementation.

## Data and prediction rules

- Treat data provenance, licensing, consent and usage rights as first-class requirements.
- Never scrape or automate a service in a way that bypasses CAPTCHA, authentication, rate limits, technical restrictions or provider terms.
- Never commit PNRs, tokens, credentials, personal passenger details, raw private API responses or non-public training data.
- Synthetic data is allowed for tests and UI development only when clearly labelled. It must never be passed off as historical railway data or used to claim real-world accuracy.
- Keep original status and current status distinct. Preserve observed time, source, status category and verification method.
- Do not use information that became available after the prediction timestamp in historical backtests.
- Never show an unvalidated model output as a trustworthy probability. When suitable data or calibration are missing, report that limitation, abstain, or label the output as a non-production demonstration.
- Distinguish final CNF, RAC and WL outcomes where the target definition and data support them. Do not silently collapse exceptional or censored outcomes.
- A booking's group outcomes are dependent. Do not derive group probabilities by casually multiplying individual probabilities unless independence is a tested and explicitly justified assumption.

## Privacy and security

- Minimize personal data. Passenger names are not required for a confirmation-probability estimate.
- Design PNR handling around explicit purpose, short retention, least privilege, encrypted storage and redacted logs.
- Keep secrets in environment variables or an approved secrets manager; commit only safe examples such as `.env.example`.
- Validate external input and provider responses. Add timeouts, bounded retries and rate limiting for network operations.
- Document any new data collected, why it is needed, who can access it, retention, deletion, and third-party sharing before enabling the feature.

## Engineering expectations

- Write tests for domain logic, edge cases and regressions. Tests must not rely on live provider access unless the test is explicitly an opt-in integration test.
- Separate data ingestion, domain normalization, feature construction, training, evaluation and serving concerns.
- Pin or constrain dependencies appropriately. Avoid adding a dependency for a trivial task.
- Make scripts deterministic where practical. Document required environment variables and local setup.
- Run relevant formatters, linters, type checks and tests available in the repository. Report anything not run and why.
- Do not add CI badges, performance figures, release claims or deployment links until they correspond to real configured systems.
- Keep documentation current with code. If an API or schema changes, update the relevant specification and tests in the same change.

## Session close-out

A completed task should leave:
1. A concise summary of what changed and why.
2. Files or subsystems affected.
3. Tests and checks actually run, including failures.
4. Data, permission, privacy or compatibility implications.
5. Decisions made and the ADR references.
6. Remaining work or blockers.
7. Commit hashes and links when changes were pushed.

## Repository voice

Write in first-person singular only when documenting the project owner's rationale or research notes where that is natural. Prefer direct sentences and concrete claims. Do not mention AI assistance or imply that an automated agent performed work in public-facing prose unless disclosure is specifically required by the context. Never fabricate personal experiences, authored experiments, real-world testing, or conclusions to make the writing appear human-written.
