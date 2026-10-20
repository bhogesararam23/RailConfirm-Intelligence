# ADR-0002: Initial application and ML stack

- **Status:** Accepted as initial direction
- **Date:** 2026-10-21
- **Decision owner:** Project maintainer
- **Related:** ADR-0001

## Context

The project needs a browser-based manual-input experience, API validation, reliable data processing, reproducible training and a path to separately deploy live-provider adapters. No code or infrastructure is in place yet, and the right runtime size depends on data-source requirements.

## Decision

Use the following as the starting stack, subject to evidence from the first implementation:
- TypeScript with React or Next.js and Tailwind CSS for the web application.
- Python with FastAPI for prediction and data APIs.
- PostgreSQL for structured metadata and permitted time-stamped observations.
- Python tooling for validation, feature construction, model training and evaluation.
- Separate ingestion/training workloads from the public inference path.

No cloud provider or paid service is selected by this ADR. Prefer low-cost, simple deployment until reliability or workload requires more.

## Alternatives considered

- **All-in-one JavaScript ML stack:** Not selected as the starting point because the research/data ecosystem and model evaluation will primarily be Python-based.
- **Notebook-only product:** Rejected because it does not provide a reusable passenger/group-facing application interface.
- **Microservices from day one:** Rejected as unnecessary complexity before source and workload needs are known.

## Consequences

- Domain and prediction contracts should be independent of the UI framework.
- API and model dependencies can evolve without requiring frontend rewrites.
- Deployment and database costs remain uncommitted.
- The stack should be revisited if a proven data provider, measured load, or maintainability needs alter the trade-off.

## Validation

Review after the first vertical slice and after data-provider requirements are known. Any change to the selected production stack should be recorded in a superseding ADR rather than treating this initial direction as immutable.
