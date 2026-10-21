# Documentation map

Start here if this is your first time working on RailConfirm Intelligence.

## Recommended reading order

1. [Repository README](../README.md) — project purpose and current status.
2. [Roadmap](ROADMAP.md) — phased delivery plan and exit gates.
3. [Product brief](product/PRODUCT_BRIEF.md) — the problem, intended users and product position.
4. [Product requirements](product/PRODUCT_REQUIREMENTS.md) — scope, priorities and acceptance criteria.
5. [User journeys](product/USER_JOURNEYS.md) and [MVP acceptance criteria](product/MVP_ACCEPTANCE.md).
6. [Agent handoff](AGENT_HANDOFF.md) — exact entry point and first recommended coding task.
7. [Architecture overview](architecture/OVERVIEW.md) and [system design](technical/SYSTEM_DESIGN.md).
8. [Domain model](technical/DOMAIN_MODEL.md) and [storage model](technical/STORAGE_MODEL.md).
9. [API contract](architecture/API_CONTRACT.md) and [frontend guide](technical/FRONTEND_GUIDE.md).
10. [Data contract](data/DATA_CONTRACT.md) and [data acquisition](data/DATA_ACQUISITION.md).
11. [Prediction targets](model/PREDICTION_TARGETS.md) and [inference/group probabilities](technical/INFERENCE_AND_GROUP_PROBABILITIES.md).
12. [Evaluation protocol](research/EVALUATION_PROTOCOL.md) and [testing strategy](technical/TESTING_STRATEGY.md).
13. [Implementation plan](technical/IMPLEMENTATION_PLAN.md), [observability](technical/OBSERVABILITY.md) and [deployment runbook](technical/DEPLOYMENT_RUNBOOK.md).

## Roadmap and execution

- [Roadmap](ROADMAP.md)
- [ADR-0008: planned live-data integrations](adr/ADR-0008-live-data-integrations-as-long-term-core-capability.md)
- [Agent handoff](AGENT_HANDOFF.md)
- [Dataset intake checklist](data/DATASET_INTAKE_CHECKLIST.md)
- [Dataset manifest template](data/DATASET_MANIFEST_TEMPLATE.yaml)
- [Local-first development rules](technical/LOCAL_FIRST_DEVELOPMENT.md)
- [Local-first scope decision, ADR-0007](adr/ADR-0007-local-first-no-external-runtime-apis.md)

## Product documents

- [Product brief](product/PRODUCT_BRIEF.md)
- [Product requirements](product/PRODUCT_REQUIREMENTS.md)
- [User journeys](product/USER_JOURNEYS.md)
- [MVP acceptance criteria](product/MVP_ACCEPTANCE.md)

## Technical documents

- [System design](technical/SYSTEM_DESIGN.md)
- [Domain model](technical/DOMAIN_MODEL.md)
- [Storage model](technical/STORAGE_MODEL.md)
- [Inference and group probabilities](technical/INFERENCE_AND_GROUP_PROBABILITIES.md)
- [Ingestion and tracking](technical/INGESTION_AND_TRACKING.md) — planned core capability for later phases
- [Frontend guide](technical/FRONTEND_GUIDE.md)
- [API contract](architecture/API_CONTRACT.md)
- [Testing strategy](technical/TESTING_STRATEGY.md)
- [Observability](technical/OBSERVABILITY.md)
- [Deployment and operations](technical/DEPLOYMENT_RUNBOOK.md)
- [Implementation plan](technical/IMPLEMENTATION_PLAN.md)
- [Local-first development rules](technical/LOCAL_FIRST_DEVELOPMENT.md)
- [Agent handoff](AGENT_HANDOFF.md)

## Research, data and governance

- [Research plan](research/RESEARCH_PLAN.md)
- [Evaluation protocol](research/EVALUATION_PROTOCOL.md)
- [Data source register](data/SOURCE_REGISTER.md)
- [Data acquisition](data/DATA_ACQUISITION.md)
- [Dataset intake checklist](data/DATASET_INTAKE_CHECKLIST.md)
- [Data contract](data/DATA_CONTRACT.md)
- [Status glossary](model/STATUS_GLOSSARY.md)
- [Model card template](model/MODEL_CARD_TEMPLATE.md)
- [Security and privacy](SECURITY_AND_PRIVACY.md)
- [Third-party data policy](../THIRD_PARTY_DATA.md)
- [ADR index](adr/README.md)
- [Project canvas](CANVAS.md)
- [Definition of done](DEFINITION_OF_DONE.md)
- [Development/session log](DEVELOPMENT_LOG.md)
- [Experiment template](EXPERIMENT_TEMPLATE.md)

## Status convention

The documents describe a proposed design unless a section explicitly says it is implemented and verified. A requirement, API example, schema draft or architecture diagram is not proof that code exists. Current implementation status belongs in [Project status](PROJECT_STATUS.md).
