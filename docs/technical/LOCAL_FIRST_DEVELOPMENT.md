# Local-first development boundaries

Status: current implementation constraint.

Local-first is a sequencing and resilience strategy for the first release, not a permanent limit on the product's intended capabilities. ADR-0008 and roadmap Phases 8–10 retain authorized live status sources and verified current/upcoming contextual feeds as planned core long-term capabilities.

## What local-first means here

The first working version must be useful for development and research using local code, reviewed input files, local/configured storage and versioned model artifacts. It must not require any third-party runtime API to start the app, validate manual inputs, run tests or execute a supported local model.

The application may expose its own backend API between its frontend and backend. That is part of the product, not an external provider dependency.

## Allowed in the current scope

- Agent-assisted source discovery and manual dataset preparation where terms allow it.
- User-provided files, once provenance, rights, privacy and schema are reviewed.
- Local CSV or JSON research files. `backend/railconfirm/data/loader.py` accepts only those two extensions and refuses `.pkl`, `.xlsx` and `.parquet`: a pickle file executes code on load, and an unreviewed binary format would let a dataset arrive in a shape nobody inspected. A new format is added with a reader, tests and a note here.
- Downloaded data files only when their source and intended use are documented and permitted.
- Local model training, evaluation and inference.
- A local database or file-backed storage for the initial development path, selected with an ADR when implemented.
- Internal API endpoints for the web application.
- Synthetic fixtures for software tests, clearly marked and isolated from empirical evaluation.

## Not allowed as a core runtime dependency in the current build

The following are deferred from the first implementation, not removed from the long-term product goal. The roadmap intends to add suitable authorized sources in later phases.

- Live IRCTC or third-party PNR APIs.
- Automatic ticket-status polling.
- News search or live news APIs.
- External holiday/weather/crowd/event APIs.
- Third-party prediction-as-a-service APIs.
- An external LLM call that must succeed for the core form, validation, inference or report to work.
- Silent network calls to collect data when the user opens the app.

This boundary does not mean research agents may never browse websites. Agent-assisted research is an offline preparation activity; it must still respect source terms, document provenance, and produce inspectable artifacts.

## Configuration and offline behavior

- The default app path should not require external credentials.
- Missing local dataset/model artifacts should return a clear setup or unsupported state.
- Tests must use fixtures or explicitly configured local data.
- No test should call a live provider by default.
- External dependency switches, if introduced for later work, must default to disabled and require a documented ADR.
- Do not add API keys to .env.example with real values or commit secrets.

## Data directory policy

Recommended logical layout:
- data/README.md — local data instructions and boundary.
- data/manifests/ — source, licence, checksum, schema and use metadata that is safe to publish.
- data/sample/ — only small, safe, licence-compatible examples or clearly synthetic fixtures.
- local/raw/ and local/processed/ — ignored by Git; use only under source terms and privacy policy.
- artifacts/ — local model/evaluation outputs, ignored by Git unless an intentionally distributable artifact is approved.

The exact directory structure can be finalized by the first data implementation. Do not put private data into a public path merely because .gitignore exists; local files can still be accidentally staged.

## Preparing for later core integrations

Keep source adapters, status observations, source provenance and prediction revision boundaries modular. Do not couple domain normalization or model inference to one provider's JSON schema. This preserves a route to the planned future integrations without adding runtime dependencies to the current local-first app. Do not implement those integrations until their roadmap phase and source-specific review are reached.

## Definition of local-first done

- Fresh environment can start the application without third-party API credentials.
- Manual input validation works without any outside service.
- A supported local model can run without a hosted inference dependency.
- Tests are deterministic and do not require internet access.
- No external API is silently invoked in the normal path.
- Data/model missing states are clear and safe.
