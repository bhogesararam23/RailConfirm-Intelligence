# Changelog

Notable changes to RailConfirm Intelligence are recorded here. This project has not released a working prediction model or live-tracking service yet.

The format is inspired by Keep a Changelog; dates use ISO 8601.

## [Unreleased]

### Added
- Initial project overview and research scope.
- Repository-wide agent operating rules and contribution guidance.
- Product brief, product requirements, user journeys, MVP acceptance criteria and phased local-first roadmap.
- Agent-assisted dataset intake checklist, manifest template and local data workspace guidance.
- Agent handoff and a central documentation map.
- Detailed system design, domain model, storage model and API/frontend contracts.
- Inference and group-probability behavior, ingestion/tracking lifecycle and model output requirements.
- Testing strategy, observability, deployment runbook and phased implementation plan.
- Data acquisition policy, data contract and source register.
- Prediction-target definitions and chronological evaluation/calibration protocol.
- Architecture Decision Records and session/experiment templates.
- Privacy/security baseline, third-party data policy, local-first development constraints and ADR-0007.
- Apache License 2.0 for original repository materials.

### Notes
- The current implementation scope explicitly excludes third-party runtime APIs, live PNR polling, external context feeds and hosted inference. Data may be researched/prepared by agents, but must pass source, rights, privacy and quality review.
- The repository remains a documentation and planning baseline. A running frontend/API, trained model, verified performance figures, production data pipeline and live PNR integration are not claimed by these documents.
- Dataset rights and access availability remain subject to source-by-source verification.
- Proposed schemas and API examples must be implemented and tested before being treated as a functioning contract.
