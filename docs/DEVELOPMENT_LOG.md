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
- Documentation changes were committed through the GitHub repository API.
- No code, model training, dataset ingestion, automated tests or deployment was run during this documentation session.

### Open items
- Verify candidate datasets, licences, label semantics, historical outcome coverage and costs.
- Decide which sources are usable for model training and which are reference-only.
- Implement schemas and their validation tests.
- Implement a baseline and chronological evaluation.
- Validate the proposed technology stack in the first vertical slice.
- Keep live PNR tracking disabled until provider permissions and controls are verified.

## 2026-10-21 — Product and technical specification

### Scope
Expanded the documentation from project/research principles into implementation-oriented product and engineering contracts.

### Added
- Product brief, requirements, user journeys and MVP acceptance criteria.
- Central documentation index and agent handoff.
- System design, domain model and logical storage model.
- Inference and group-probability specification.
- Source ingestion/tracking lifecycle.
- Frontend interaction/accessibility guide.
- Testing strategy, observability and deployment runbook.
- Ordered implementation plan.
- Updated README, changelog and documentation index.

### Decisions and boundaries
- Manual entry remains the first product path.
- Live tracking stays disabled until an authorized source and retention policy are verified.
- No unsupported probability is returned as if it were a trained prediction.
- The first code task should be the status/domain contract and tests, subject to authoritative verification of status mappings.
- No new material architecture decision was made beyond elaborating the existing ADRs.

### Checks
- Verified the new and updated files on the repository's main branch.
- Confirmed the docs contain proposed behavior and implementation gates rather than claims of completed software.
- No application tests, model runs, dataset ingestion or deployment were performed; there is no implementation to validate yet.

### Remaining work
- Implement the domain contract and status normalization with tests.
- Complete source/terms feasibility review.
- Build the manual-entry API/UI shell with an explicit no-model response.
- Establish a reproducible baseline once permitted labelled data is available.


## 2026-10-21 — Local-first roadmap

### Scope
Converted the staged implementation plan into a single phased roadmap and made the current runtime boundary explicit.

### Added
- Local-first roadmap with phase deliverables and exit gates.
- ADR-0007 for no third-party runtime APIs in the current build.
- Dataset intake checklist and manifest template for agent-prepared candidate data.
- Local data workspace instructions and ignored local dataset paths.
- Updated product, implementation, agent and project status documentation.

### Decisions
- The current application has no third-party runtime API dependency; an internal frontend/backend API remains allowed.
- Agents may research and prepare candidate data, but files are not approved for training until source rights, provenance, privacy, labels and quality pass review.
- Live PNR lookup/polling, news/context feeds and hosted inference are deferred beyond the current roadmap and require a new ADR to reopen.

### Checks
- Confirmed the new files were committed to the repository's default branch.
- No dataset was downloaded or approved in this session.
- No application code, training, automated tests or deployment was run in this documentation session.

### Next step
Implement Phase 1 of docs/ROADMAP.md: domain/status schema and parsing tests. Continue agent-assisted dataset discovery as a separately tracked task, completing a manifest and intake report for each candidate.
