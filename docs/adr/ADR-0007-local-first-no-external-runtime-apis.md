# ADR-0007: Local-first MVP without third-party runtime APIs

- **Status:** Accepted
- **Date:** 2026-10-21
- **Decision owner:** Project maintainer
- **Related:** ADR-0001, ADR-0005, docs/ROADMAP.md

## Context

The project needs a concrete initial execution scope while historical outcome data is still being investigated. Building around live railway APIs, news feeds or external services would add cost, authorization, reliability and privacy dependencies before the local data/model path has been proven.

The maintainer has selected a local-first approach for the current build. Research agents may help discover, prepare and document data, but the project must still verify the source, permitted use, labels, data quality and privacy implications.

## Decision

The current roadmap will not include third-party runtime API integrations or external provider dependencies.

The first release must support:
- manual journey and passenger-status input;
- a local/internal application API where needed;
- approved local datasets and versioned model artifacts;
- local data validation, training, evaluation and inference;
- deterministic tests that do not require external network access;
- clear no-data/no-model/unsupported responses.

Agent-assisted data discovery and preparation is allowed only within the source's terms. Data brought by an agent is a candidate, not automatically an approved dataset. Its source, retrieval date, licence/terms, permitted uses, schema, checksum, privacy review and validation results must be recorded before training.

Live PNR lookups, automatic ticket polling, live news/calendar/weather feeds and third-party hosted inference are deferred. Reconsider any of them only through a new ADR that documents a concrete need, provider rights, cost, privacy/security, failure behavior and incremental value.

## Alternatives considered

- **Start with live APIs:** Rejected for the current scope because authorization and recurring service dependencies are not prerequisites for implementing the local model and manual workflow.
- **Let the agent supply data without a review gate:** Rejected because data availability does not establish licence, label quality, provenance or training rights.
- **Avoid all data work until official historical data is handed over:** Rejected; agents can investigate permitted candidate datasets and the domain/UI work can proceed without falsely claiming that training data is ready.
- **Build only notebooks and postpone the app:** Rejected; a manual local application can be built once the internal contracts and supported inference path are defined.

## Consequences

- No third-party API credentials are required for the first working local demo.
- Data intake and source documentation become explicit roadmap phases.
- The product may initially return no prediction for unsupported cases.
- External live features are out of scope unless a later ADR reopens the decision.
- Research notes and local datasets must remain traceable and cleanly separated from synthetic fixtures.
- The internal backend API is still permitted; this decision concerns external APIs and providers.

## Validation

The decision is satisfied when a clean environment can run the manual workflow, tests, and any supported local inference without external API credentials or network calls. Dataset approval must use docs/data/DATASET_INTAKE_CHECKLIST.md. No model-performance claim is authorized by this ADR.
