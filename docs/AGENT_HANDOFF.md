# Agent handoff

This is the fastest safe entry point for a new coding agent working on this repository.

## Project in one minute

RailConfirm Intelligence estimates final reservation outcomes for Indian Railways WL/RAC tickets: passenger-level probabilities and, where evidence supports it, group-level outcomes such as all passengers CNF.

The repository now contains a **working local-first application core**: a FastAPI backend, a Next.js frontend, a dataset intake pipeline, and a model registry. It contains **no approved dataset, no trained model and no evaluation results**, so every prediction currently returns a structured abstention. That is the designed behaviour, not a stub.

Do not assume any of the following exist, because none do: an accuracy figure, a calibration result, a database, prediction history, a deployment, or a live data provider.

## Current state, precisely

| Exists and is tested | Exists but is unverified against real data | Does not exist |
|---|---|---|
| Domain contracts, status mapping v1.1.0, temporal integrity rules, abstention reasons, API contract and error envelope, dataset loader/validator/manifest/verification, chronological splitting, artifact registry and promotion gate, CI | Historical-frequency baseline (never loaded with real data), group outcomes (independence baseline only), the frontend (types do not match the backend) | Training pipeline, evaluation metrics, calibration, persistence, prediction history, frontend tests, approved dataset, promoted artifact |

384 backend tests, 96% branch coverage, CI green on `main`.

## Read first

1. `AGENTS.md`
2. `docs/PROJECT_STATUS.md` — the honest area-by-area state
3. `docs/DEVELOPMENT_LOG.md` — the most recent session, including what was found broken
4. `docs/ROADMAP.md`
5. `docs/architecture/API_CONTRACT.md` — matches the shipped surface
6. `docs/data/DATA_CONTRACT.md` and `docs/data/DATASET_INTAKE_CHECKLIST.md`
7. ADR index, especially ADR-0007 (local-first boundary), ADR-0008 (future integration phases), ADR-0009 (artifact trust boundaries) and ADR-0010 (declared check configurations)
8. `docs/research/EVALUATION_PROTOCOL.md` before writing any metric code

## Working here

```bash
cd backend
pip install -e ".[dev]"
pytest tests/ --cov=railconfirm --cov-fail-under=90
ruff check railconfirm/ tests/
mypy
python -m railconfirm.data validate tests/fixtures/synthetic_dataset.csv   # exits 1: not eligible
cd ..
python scripts/check_repository_hygiene.py
cd frontend && npm ci && npm run type-check && npm run lint && npm run build
```

Run the app locally: `uvicorn railconfirm.api.app:app --port 8000` from `backend/`, then
`npm run dev` from `frontend/`. The backend allows CORS only from origins listed in
`RAILCONFIRM_CORS_ALLOWED_ORIGINS`; `:3000` is the default and is a Grafana on the
maintainer's machine, so pick a different frontend port and list that origin.

## Highest-value next tasks

In order, based on the actual repository:

1. **Fix the frontend against the real API contract.** `frontend/src/lib/types.ts`
   declares an `observed_status` object the backend never sends, so observed statuses
   are never displayed. `(x || 0) * 100` renders a fabricated `0.0%` for a null
   probability. `p_cancelled` is never rendered, so the probability bar cannot sum to
   100%. The error shape does not match `{error, details[], request_id}`. Then add a
   frontend test framework and contract tests.
2. **Intake a real candidate dataset** — research, review licence and privacy, record
   in `docs/data/SOURCE_REGISTER.md`, run `python -m railconfirm.data manifest`, and
   have a named person record the decision. Nothing may be approved by a script.
3. **Training and evaluation pipelines** (Milestones C and D) once step 2 yields an
   approved dataset. The splitter, artifact format and promotion gate are ready; a
   trainer must emit an artifact that declares its dataset SHA-256 and target.
4. **Persistence** only when a real product behaviour needs it. Nothing is stored today.

## Non-negotiable constraints

- Do not invent training data, probabilities, evaluation results or source permissions.
- Do not enable unapproved PNR automation, or bypass CAPTCHAs, logins or rate limits.
- Do not collect passenger names for prediction.
- Do not let future observations enter historical feature snapshots; `extract_features` refuses label columns and `chronological_split` refuses to fake a holdout — use them rather than reimplementing.
- Do not claim group outcomes from independent multiplication as validated.
- Show a structured abstention when no validated model or source is available; never return `200 OK` with a fabricated probability.
- Keep synthetic fixtures labelled and out of any real-world performance claim.
- Update the changelog and session log; create a sequential ADR for material decisions.
- Prefer meaningful commits; never manufacture commit count.
- Report a command's actual exit code and output. A local green run is not evidence about CI: they resolve different package versions, which is why `pyproject.toml` now pins the tools.

## If blocked

Report the exact missing evidence, permission or dataset and continue with work that does not depend on it. Do not replace a blocker with a fabricated implementation, and do not weaken a check to get a green result — the last session's failed CI runs were fixed by correcting the code and the tests, and each failure is recorded in `docs/DEVELOPMENT_LOG.md`.
