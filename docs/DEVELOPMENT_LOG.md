# Development and session log

This is a durable record of meaningful development sessions, including decisions, checks and open questions. It is not intended to replace Git history.

## 2026-10-21 — Repository foundation

### Scope
Initialized the empty public repository with project, research, data governance, agent workflow, security and licensing documentation.

### Added
- Project README and status page.
- Research plan and prediction/evaluation specifications.
- Data acquisition plan, data contract and source register.
- Architecture overview and privacy/security baseline.
- Contributor and agent instructions.
- Changelog, third-party data note and notice.
- ADR process and ADR-0001 through ADR-0006.

### Decisions
- Documentation and data-readiness gates precede model performance claims.
- Initial web/API/ML stack is a candidate direction, not a deployed implementation.
- Passenger outcomes distinguish CNF, RAC and WL where data supports those targets.
- Group outcomes should account for dependence between passengers.
- Backtesting must be chronological and leakage-resistant.
- Data access and PNR retention require source-specific authorization and privacy controls.
- Apache-2.0 applies to original repository materials; third-party data remains separately governed.

### Checks
- Repository was confirmed public, writable and empty before initialization.
- File creation was performed through GitHub's contents API, producing separate commits.
- No code, model training, dataset ingestion, automated tests or deployment was run during this documentation session.

### Open items
- Verify candidate datasets, licences, label semantics, historical outcome coverage and costs.
- Decide which sources are usable for model training and which are reference-only.
- Implement schemas and their validation tests.
- Implement a baseline and chronological evaluation.
- Validate the proposed technology stack in the first vertical slice.
- Keep live PNR tracking disabled until provider permissions and controls are verified.
