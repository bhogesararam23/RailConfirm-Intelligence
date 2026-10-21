# RailConfirm Intelligence

An ML-powered Indian Railways ticket confirmation probability predictor for waitlisted (WL) and Reservation Against Cancellation (RAC) tickets, with passenger-wise forecasts, group-level outcome analysis, and historical trend modelling.

RailConfirm is being developed as both a research project and a web application. The goal is not to produce a percentage that looks precise; the goal is to estimate meaningful probabilities, evaluate them against real outcomes, and be clear about where the model does and does not have enough evidence.

> **Project status:** Documentation and research planning. The current roadmap is local-first and has no third-party runtime API dependency. A trained prediction model, production data pipeline, and live PNR integration are not yet claimed to exist. Estimates must not be presented as reliable until validated on held-out real-world outcomes.

## What it is intended to do

- Estimate each passenger's final reservation outcome using information available at a defined prediction time.
- Distinguish confirmed berth (CNF), RAC, and waitlisted outcomes where data and labels support those targets.
- Estimate group outcomes, including the chance that all passengers are confirmed, all receive CNF/RAC, or at least a specified number receive confirmed berths.
- Track how a prediction changes when new, authorized status observations become available.
- Use historical trends and verified context only when they improve out-of-sample performance.
- Report probability calibration, evidence coverage, freshness, and uncertainty rather than relying on unsupported accuracy claims.

## Principles

1. **Evidence before percentages.** Every displayed probability must be traceable to a model version, prediction timestamp, and documented input data.
2. **No invented data.** Synthetic examples may be used for tests and UI development, but must never be presented as real railway history or model performance.
3. **No leakage.** A historical prediction may use only information that would have been available at that prediction time.
4. **Evaluate probabilities, not just labels.** Calibration and proper scoring rules matter.
5. **Broad goals, honest coverage.** The long-term goal includes multiple WL/RAC categories, but support is enabled only when data quality and evaluation justify it.
6. **Authorized access.** Do not bypass access controls or assume that a publicly reachable endpoint permits bulk collection, storage, or model training.
7. **Privacy by design.** Avoid collecting passenger names and other unnecessary personal data. Protect PNRs and define retention before enabling tracking.
8. **Explain limits.** RailConfirm is an estimate, not an official railway decision or a guarantee of a final reservation outcome.

## Current roadmap

The current build is local-first: no third-party runtime APIs, live PNR lookup, automated polling, or live news/event feeds. Research agents may help identify and prepare datasets, but each dataset must pass provenance, licence, privacy, label-quality and leakage checks before training.

See the [detailed roadmap](docs/ROADMAP.md), [dataset intake checklist](docs/data/DATASET_INTAKE_CHECKLIST.md), [dataset manifest template](docs/data/DATASET_MANIFEST_TEMPLATE.yaml), and [local-first development rules](docs/technical/LOCAL_FIRST_DEVELOPMENT.md).

## Documentation

Start with the [documentation map](docs/README.md) for the recommended reading order. The [roadmap](docs/ROADMAP.md) is the canonical execution plan.

**Product:** [Product brief](docs/product/PRODUCT_BRIEF.md) · [Requirements](docs/product/PRODUCT_REQUIREMENTS.md) · [User journeys](docs/product/USER_JOURNEYS.md) · [MVP acceptance criteria](docs/product/MVP_ACCEPTANCE.md)

**Technical:** [System design](docs/technical/SYSTEM_DESIGN.md) · [Domain model](docs/technical/DOMAIN_MODEL.md) · [Storage model](docs/technical/STORAGE_MODEL.md) · [Inference and group probabilities](docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md) · [Ingestion and tracking](docs/technical/INGESTION_AND_TRACKING.md)

**Build and operations:** [Roadmap](docs/ROADMAP.md) · [Agent handoff](docs/AGENT_HANDOFF.md) · [Implementation plan](docs/technical/IMPLEMENTATION_PLAN.md) · [Testing strategy](docs/technical/TESTING_STRATEGY.md) · [Frontend guide](docs/technical/FRONTEND_GUIDE.md) · [Observability](docs/technical/OBSERVABILITY.md) · [Deployment runbook](docs/technical/DEPLOYMENT_RUNBOOK.md) · [Agent handoff](docs/AGENT_HANDOFF.md)

**Research and governance:** [Project status](docs/PROJECT_STATUS.md) · [Research plan](docs/research/RESEARCH_PLAN.md) · [Data acquisition](docs/data/DATA_ACQUISITION.md) · [Data contract](docs/data/DATA_CONTRACT.md) · [Prediction targets](docs/model/PREDICTION_TARGETS.md) · [Evaluation protocol](docs/research/EVALUATION_PROTOCOL.md) · [Security and privacy](docs/SECURITY_AND_PRIVACY.md) · [Architecture Decision Records](docs/adr/README.md)

The current no-third-party-runtime-API boundary is recorded in [ADR-0007](docs/adr/ADR-0007-local-first-no-external-runtime-apis.md). Agent-sourced data remains subject to the dataset intake gate.

Also see [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md), [development log](docs/DEVELOPMENT_LOG.md), and [third-party data policy](THIRD_PARTY_DATA.md).

## License

Software and documentation in this repository are licensed under the Apache License 2.0 unless a file or directory says otherwise. This license does not grant rights to third-party datasets, railway systems, trademarks, APIs, or service content. See [LICENSE](LICENSE) and [THIRD_PARTY_DATA.md](THIRD_PARTY_DATA.md).

## Disclaimer

RailConfirm Intelligence is an independent research and software project. It is not an official Indian Railways or IRCTC service and should not be represented as affiliated with, endorsed by, or operated by either. Final reservation status is determined by the relevant railway systems and applicable rules. Do not make travel or financial decisions solely on an unvalidated prediction.
