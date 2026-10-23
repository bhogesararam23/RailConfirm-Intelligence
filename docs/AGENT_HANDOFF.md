# Agent handoff

This is the fastest safe entry point for a new coding agent working on this repository.

## Project in one minute

RailConfirm Intelligence estimates final reservation outcomes for Indian Railways WL/RAC tickets: passenger-level probabilities and, where evidence supports it, group-level outcomes such as all passengers CNF.

The repository now contains a **working local-first application core**: a FastAPI backend, a Next.js frontend, a dataset intake pipeline, and a model registry. It contains **no approved dataset, no trained model and no evaluation results**, so every prediction currently returns a structured abstention. That is the designed behaviour, not a stub.

Do not assume any of the following exist, because none do: an accuracy figure, a calibration result, an approved dataset, a promoted artifact, a deployment, or a live data provider. Opt-in local prediction history does exist (ADR-0012) but is disabled by default.

## Current state, precisely

| Exists and is tested | Exists but is unverified against real data | Does not exist |
|---|---|---|
| Domain contracts, status mapping v1.1.0, temporal integrity rules, abstention reasons, API contract and error envelope (including unrouted paths), dataset loader/validator/manifest/verification, a training gate that enforces **technical eligibility** and passes on only validated rows, chronological splitting, one shared as-of status rule across fit/score/serve, artifact registry with promotion gate and load-time cohort-contract check, baseline fitting and target-event evaluation with deterministic reports, opt-in prediction history, frontend written and tested against the shipped contract, CI | Historical-frequency baseline (never loaded with real data), the training and evaluation pipeline (never run on approved data), group outcomes (independence baseline only), prediction history (never enabled by default, so untested against concurrent real users) | Calibration fitting, rolling-origin evaluation, dependence-aware group model, label feedback on stored reports, approved dataset, promoted artifact |

563 backend tests at 96.03% branch coverage, 93 frontend tests. CI was green on `main` at the last recorded push — re-check rather than trust this line.

## Read first

1. `AGENTS.md`
2. `docs/PROJECT_STATUS.md` — the honest area-by-area state
3. `docs/DEVELOPMENT_LOG.md` — the most recent session, including what was found broken
4. `docs/ROADMAP.md`
5. `docs/architecture/API_CONTRACT.md` — matches the shipped surface
6. `docs/data/DATA_CONTRACT.md` and `docs/data/DATASET_INTAKE_CHECKLIST.md`
7. ADR index, especially ADR-0007 (local-first boundary), ADR-0008 (future integration phases), ADR-0009 (artifact trust boundaries), ADR-0010 (declared check configurations), ADR-0011 (training gate and target-event scoring), ADR-0012 (prediction history and its retention rules) and ADR-0013 (the eligibility-enforced gate and the single as-of cohort rule)
8. `docs/research/EVALUATION_PROTOCOL.md` before writing any metric code

## Working here

```bash
cd backend
pip install -e ".[dev]"
pytest tests/ --cov=railconfirm --cov-fail-under=90
ruff check railconfirm/ tests/
mypy
python -m railconfirm.data validate tests/fixtures/synthetic_dataset.csv   # exits 1: not eligible
python -m railconfirm.training fit --help    # gated fitting; see ADR-0011
cd ..
python scripts/check_repository_hygiene.py
cd frontend && npm ci && npm test && npm run type-check && npm run lint && npm run build
```

Run the app locally: `uvicorn railconfirm.api.app:app --port 8000` from `backend/`, then
`npm run dev` from `frontend/`. The backend allows CORS only from origins listed in
`RAILCONFIRM_CORS_ALLOWED_ORIGINS`; `:3000` is the default and is a Grafana on the
maintainer's machine, so pick a different frontend port and list that origin. The frontend
inlines `NEXT_PUBLIC_API_URL` at build time, so export it before starting `next dev` and
restart it after changing the backend port.

Prediction history is off by default. To exercise `/prediction/[id]`, start the backend with
`RAILCONFIRM_PERSIST_PREDICTIONS=true` (and a `RAILCONFIRM_STORAGE_DIR` outside the repository
if you do not want `data/storage/` to appear locally) and send `"persist": true` — the
checkbox on the form does that. `GET /v1/health` shows which state the server is in.

## Highest-value next tasks

In order, based on the actual repository:

1. **Intake a real candidate dataset** — research, review licence and privacy, record
   in `docs/data/SOURCE_REGISTER.md`, run `python -m railconfirm.data manifest`, and
   have a named person record the decision. Nothing may be approved by a script. This
   is the only scientific blocker: the trainer, the splitter, the artifact format and
   the scorer all exist and are tested, but every number they produce today comes from
   synthetic rows.
2. **Fit and evaluate on that dataset** with `python -m railconfirm.training fit` /
   `evaluate`, then decide promotion from the report instead of from the code.
3. **Close the evaluation gaps** the protocol describes and the code does not:
   rolling-origin evaluation across multiple cutoffs, and calibration fitted on the
   validation period and measured on a locked test period. Reliability bands are a
   description today; `calibrated` is always false and the report says so.
4. **Dependence-aware group outcomes** (ADR-0003). The engine still multiplies under an
   independence assumption and labels it; group-event metrics are not scored.
5. **Label feedback on stored reports.** History now exists, so "what did the chart
   actually say?" has something to attach to. Design the consent, retention, sampling-bias
   and verification story before writing the route — ADR-0012 lists this as a consequence
   of storage, not as permission to collect.
6. **Per-row deletion** for history, and any access boundary that would let history be
   enabled by default. Neither is needed while the feature is off and single-operator.

## Non-negotiable constraints

- Do not invent training data, probabilities, evaluation results or source permissions.
- Do not enable unapproved PNR automation, or bypass CAPTCHAs, logins or rate limits.
- Do not collect passenger names for prediction.
- Do not let future observations enter historical feature snapshots; `extract_features` refuses label columns and `chronological_split` refuses to fake a holdout — use them rather than reimplementing.
- Do not bypass the dataset gate. `load_approved_dataset` is the only way training should read a file: it enforces technical eligibility, drops the rows validation rejected, and refuses synthetic relaxation for data that does not declare `is_synthetic`. If a check is in your way, the finding is the answer, not an obstacle.
- The as-of status has exactly one definition, `preprocessing.asof_statuses()` (`current_status` when recorded, otherwise `initial_status`). Fitting, scoring and serving must keep calling it; a cohort keyed by one column and queried by another produces metrics describing a lookup the product never performs (ADR-0013).
- Do not claim group outcomes from independent multiplication as validated.
- Show a structured abstention when no validated model or source is available; never return `200 OK` with a fabricated probability.
- Keep synthetic fixtures labelled and out of any real-world performance claim.
- Do not make storage happen by one switch. A report is kept only when the server enables history *and* the request asks; do not default `RAILCONFIRM_PERSIST_PREDICTIONS` on, do not store by default in tests that a reader might mistake for the product, and never widen `DENIED_KEYS` without a recorded privacy decision.
- Update the changelog and session log; create a sequential ADR for material decisions.
- Prefer meaningful commits; never manufacture commit count.
- Report a command's actual exit code and output. A local green run is not evidence about CI: they resolve different package versions, which is why `pyproject.toml` now pins the tools.

## If blocked

Report the exact missing evidence, permission or dataset and continue with work that does not depend on it. Do not replace a blocker with a fabricated implementation, and do not weaken a check to get a green result — the last session's failed CI runs were fixed by correcting the code and the tests, and each failure is recorded in `docs/DEVELOPMENT_LOG.md`.
