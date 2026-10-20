# Deployment and operations runbook

Status: deployment guide template. No live deployment is configured by this document.

## Deployment shape

The initial application may deploy the web client and API separately. Source ingestion/tracking workers and model training should be separable from public inference. Prefer the fewest services that meet actual needs; do not add a scheduler, queue or model server before the workload requires it.

Potential logical components:
- web client;
- API service;
- relational database;
- background worker for approved ingestion/tracking;
- model artifact storage/registry;
- scheduled research/training environment;
- redacted monitoring/logging.

The selected vendors, hosting region, budgets and production topology remain decisions to make after implementation and data-provider requirements are known.

## Environments

- **Local:** synthetic or explicitly approved development data; no production credentials by default.
- **Test/CI:** isolated services and fake provider adapters.
- **Research:** access-controlled datasets and reproducible experiment environment.
- **Production:** least-privilege service credentials, audited provider configuration and controlled release process.

Do not copy production PNR records into developer laptops or CI to make tests convenient.

## Required configuration

Document actual values and secrets in the deployment platform, not in Git:
- runtime environment;
- database connection through a secret store;
- model artifact URI/version;
- feature schema and target version;
- logging level;
- source adapter enable/disable switches;
- provider credentials only where approved;
- retention settings;
- request limits/timeouts;
- health-check configuration.

Keep .env.example safe and synchronized with configuration code.

## Pre-deploy checklist

- [ ] Source access terms and intended use are verified.
- [ ] Database migrations have been reviewed and tested.
- [ ] Required tests and static checks pass.
- [ ] Model artifact matches feature and target schema.
- [ ] Model evaluation report and model card are available.
- [ ] Probability checks and abstention responses work.
- [ ] Secrets exist only in the approved secret store.
- [ ] PNR data and sensitive provider fields are redacted from logs.
- [ ] Retention/deletion paths are tested.
- [ ] Live tracking can be disabled independently.
- [ ] Public copy identifies estimates and limitations.
- [ ] Rollback path is documented.

## Release process

1. Record the intended version and code revision.
2. Deploy to the test environment.
3. Run health, contract and integration checks.
4. Run a smoke test with synthetic/non-sensitive data.
5. Confirm model and schema compatibility.
6. Deploy gradually where the platform supports it.
7. Observe API errors, source freshness, abstention and model-output validity.
8. Roll back if a critical error, bad artifact, schema mismatch or unexpected provider behavior appears.
9. Record release notes and update the changelog.

## Rollback

Rollback should restore the last known compatible application/API/model combination. Model artifacts and API contracts must be versioned so code does not load an incompatible feature schema. Disable a problematic provider adapter without disabling manual entry. Never erase observation history merely to roll back a software release.

## Incident notes

Record when the incident occurred, impact, affected components, evidence, mitigation, data/privacy impact and follow-up. Do not include raw PNRs, tokens or private API payloads in the incident document.

## Costs and reliability

Do not choose a production provider based on a guessed free tier. Before deployment, measure expected traffic, model size, database volume, refresh frequency and data retention. Verify current pricing and quotas, and establish a budget/disable mechanism for paid APIs.
