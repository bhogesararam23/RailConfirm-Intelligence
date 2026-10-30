# Agent handoff

This is the fastest safe entry point for a new coding agent working on this repository.

## Project in one minute

RailConfirm Intelligence estimates final reservation outcomes for Indian Railways WL/RAC tickets: passenger-level probabilities and, where evidence supports it, group-level outcomes such as all passengers CNF.

The repository now contains a **working local-first application core**: a FastAPI backend, a Next.js frontend, a dataset intake pipeline, and a model registry. It contains **no approved dataset, no trained model and no evaluation results**, so every prediction currently returns a structured abstention. That is the designed behaviour, not a stub.

Do not assume any of the following exist, because none do: an accuracy figure, a calibration fitted on real data, an approved dataset, a promoted artifact, a deployment, or a live data provider. Opt-in local prediction history exists (ADR-0012): kept reports can be listed and deleted individually (ADR-0015). History is disabled by default.

## Current state, precisely

| Exists and is tested | Exists but is unverified against real data | Does not exist |
|---|---|---|
| Domain contracts, status mapping v1.1.0, temporal integrity rules, abstention reasons, API contract and error envelope (including unrouted paths), dataset loader/validator/manifest/verification, a training gate that enforces **technical eligibility** and passes on only validated rows, chronological splitting, **rolling-origin evaluation with per-cutoff refitting**, **frozen-artifact decay across successive horizons (ADR-0018)**, **paired baseline-vs-candidate comparison judged on the locked period with a pre-declared exact sign test (ADR-0021, ADR-0039)**, one shared as-of status rule across fit/score/serve, **two estimators behind one response shape, with a second artifact format and load-time estimator/format/band agreement (ADR-0020)**, artifact registry with promotion gate and load-time cohort-contract check, baseline fitting and target-event evaluation with deterministic reports, **logistic calibration fitted on the validation partition, embedded only when it strictly improves it and always measured on the locked test (ADR-0017)**, **subgroup calibration measured per segment with a row floor on the claim (ADR-0019)**, opt-in prediction history with list and per-row deletion, **group outcome distribution & queue-clearing bounds (ADR-0016)**, **group-event scoring in scorecards**, frontend written and tested against the shipped contract, CI | Historical-frequency baseline and the cohort-position estimator (neither ever loaded with real data), the training and evaluation pipeline (never run on approved data), calibration (fitted only on labelled synthetic rows, so no railway probability has ever been corrected), frozen-artifact decay (the ordering is measurable now, but only ever over synthetic periods), group outcomes (Poisson-binomial baseline and queue bounds, never evaluated on real multi-passenger data), prediction history (never enabled by default, so untested against concurrent real users) | A per-segment calibration correction, empirical copula/correlation group model, label feedback on stored reports, approved dataset, promoted artifact |

1121 backend tests at 96.47% total coverage (4967 statements, 114 missed; 1330 branches, 106 partial), 118 frontend tests, 5 live cross-stack tests behind their own command. CI runs four jobs, one of which starts the real API and a production frontend build and checks them over sockets (ADR-0027). It was green on `main` at the last recorded push — re-check rather than trust this line.

## Read first

1. `AGENTS.md`
2. `docs/PROJECT_STATUS.md` — the honest area-by-area state
3. `docs/DEVELOPMENT_LOG.md` — the most recent session, including what was found broken
4. `docs/ROADMAP.md`
5. `docs/architecture/API_CONTRACT.md` — matches the shipped surface
6. `docs/data/DATA_CONTRACT.md` and `docs/data/DATASET_INTAKE_CHECKLIST.md`
7. ADR index, especially ADR-0007 (local-first boundary), ADR-0008 (future integration phases), ADR-0009 (artifact trust boundaries), ADR-0010 (declared check configurations), ADR-0011 (training gate and target-event scoring), ADR-0012 (prediction history and its retention rules), ADR-0013 (the eligibility-enforced gate and the single as-of cohort rule), ADR-0014 (rolling-origin evaluation and what a single cutoff cannot show), ADR-0015 (history listing and per-row deletion), and ADR-0016 (dependent group outcomes, Poisson-binomial distribution, queue bounds, and group evaluation), and ADR-0017 (logistic calibration fitted on validation, embedded only when it helps, always measured on the locked test) and ADR-0018 (frozen-artifact decay: the artifact's own cutoff, one frozen baseline, two horizons minimum), and ADR-0019 (subgroup calibration measured per segment, with the row floor that decides what may be claimed from it), and ADR-0020 (the second estimator: cohort cells split by fixed as-of queue position bands, and the artifact contract that keeps the two apart), and ADR-0021 (the paired comparison: one split or no comparison, rows paired by position, coverage as a condition, verdict on the locked period only), and ADR-0026 (the eligible prediction horizon is one clear day, enforced by the gate and by serving from one constant) and ADR-0027 (the cross-stack smoke gate: two real processes, the client's own module, and no suite that skips itself), and ADR-0036 (a served report publishes the target's own event probability and the definition that names it, so the wording and the arithmetic cannot describe different questions), and ADR-0037 (a scorecard refuses pre-scored rows walked under another target, another calibration or another partition), and ADR-0038 (a report conclusion names only the measurements it holds: the partition's own target's event, a disagreement only when both verdicts exist, event counts that count event readings, and no `None` or zero denominator formatted as a result), and ADR-0039 (a paired win must beat chance: an exact two-sided sign test at a pre-declared 0.05 with a six-discordant-row floor is an additional promotion condition, published with its p-value and stated dependence approximation), and ADR-0040 (expiry governs what a delete may confirm: only a report retention still serves answers 204, an expired row is cleared without confirmation, and its id answers the same 404 as an unknown one)
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
python -m railconfirm.training fit ... --calibrate    # correction fitted on validation only; ADR-0017
python -m railconfirm.training decay ... --artifact models/<v>.json  # one frozen table, later horizons; ADR-0018
cd ..
python scripts/check_repository_hygiene.py
cd frontend && npm ci && npm test && npm run type-check && npm run lint && npm run build
# cross-stack, from the repository root; needs the build above with the backend origin inlined
NEXT_PUBLIC_API_URL=http://127.0.0.1:8010 npm --prefix frontend run build
python scripts/smoke_full_stack.py
```

The smoke script is the only check that starts both halves together (ADR-0027). It uses
fixed loopback ports (backend 8010, frontend 3010) because the frontend inlines its API
origin at build time; `--skip-frontend` and `--skip-client` narrow it when one half is
not the thing you changed, and `RAILCONFIRM_SMOKE_LOG_DIR` keeps the server logs.
`npm test` excludes `src/lib/__tests__/liveApi.test.ts` on purpose — that file needs a
server, and it refuses to run rather than skipping.

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
   `evaluate`, check the verdict across cutoffs with `python -m railconfirm.training
   origins` and how one artifact holds up as the calendar moves with
   `python -m railconfirm.training decay`, then decide promotion from the reports instead
   of from the code. A dataset long enough for several windows is a real intake requirement,
   not just a nice-to-have: both temporal paths refuse below two windows, and the current
   intake minimum of four distinct journey dates barely supports two.
3. **Calibrate on real data.** The mechanism exists (ADR-0017): `fit --calibrate` fits a
   logistic correction on the validation partition, embeds it only when it strictly reduces
   validation event Brier, and reports the locked-test effect whichever way it goes. On the
   synthetic fixture the change is under 0.001 event Brier, which is a mechanism check, not a
   result. Whether one slope generalises across later journey dates is now measurable —
   `decay` carries the artifact's calibration block into every horizon unchanged (ADR-0018) —
   but it has never been answered on real data. Subgroup calibration is measured now —
   every scorecard publishes the observed-minus-predicted gap per class, quota and status with
   its row count (ADR-0019) — and what remains is to read those gaps on approved data, where a
   cohort with fewer than 25 rows may not carry a claim in either direction.
4. **Read the comparison on real data.** `python -m railconfirm.training compare`
   exists (ADR-0021, ADR-0039): one split or no comparison, one prevalence baseline, rows
   paired by position, coverage as a condition, a pre-declared exact sign test at 0.05 on the
   paired advantage (at least six discordant rows), and the verdict taken from the locked
   period only. On purpose-built synthetic fixtures it has already said `candidate` (validation
   delta +0.070624, locked -0.038673) and `baseline` (locked +0.172314, 32 wins against
   48 losses) with the same code — which is the mechanism working, not a result. What
   promotion needs is the same run over an approved dataset.
5. **Dependence-aware group outcomes** (ADR-0003, ADR-0016). Poisson-binomial PMF/tail
   distributions and sequential queue-clearing comonotonic bounds are implemented and
   evaluated with group Brier scores in `score_partition()`. Once real multi-passenger booking
   data is approved, fit and evaluate parametric joint models against real correlation.
6. **Label feedback on stored reports.** History now exists, so "what did the chart
   actually say?" has something to attach to. Design the consent, retention, sampling-bias
   and verification story before writing the route — ADR-0012 lists this as a consequence
   of storage, not as permission to collect.
7. **Multi-user access boundaries for history**, if history is ever to be enabled by
   default. Listing and per-row deletion are implemented (ADR-0015); multi-user isolation
   or authentication is what would be needed before enabling history by default.

## Non-negotiable constraints

- Do not invent training data, probabilities, evaluation results or source permissions.
- Do not enable unapproved PNR automation, or bypass CAPTCHAs, logins or rate limits.
- Do not collect passenger names for prediction.
- Do not let future observations enter historical feature snapshots; `extract_features` refuses label columns and `chronological_split` refuses to fake a holdout — use them rather than reimplementing.
- Do not bypass the dataset gate. `load_approved_dataset` is the only way training should read a file: it enforces technical eligibility, drops the rows validation rejected, and refuses synthetic relaxation for data that does not declare `is_synthetic`. If a check is in your way, the finding is the answer, not an obstacle.
- The as-of status has exactly one definition, `preprocessing.asof_statuses()` (`current_status` when recorded, otherwise `initial_status`). Fitting, scoring and serving must keep calling it; a cohort keyed by one column and queried by another produces metrics describing a lookup the product never performs (ADR-0013).
- Calibration is fitted on the validation partition, never on the locked test, and it is embedded only when it strictly improves validation (ADR-0017). `inference.calibration.apply_calibration` is the only correction path: evaluator and serving engine both call it, because a probability served through different arithmetic from the one measured is not the number the report scored.
- A served report's `target_definition` and its per-passenger `p_target_event` must name the same event, and the sum comes from `PassengerOutcome.probability_of(EVENT_CLASSES_BY_TARGET[...])`, never from a client adding two classes (ADR-0036). If you add a target, add its classes, its definition and its event figure in the same change, or the report will answer one question and caption another.
- A `Scorecard`'s labels must describe the rows it was handed. `score_rows` records the target and whether a calibration was applied, and `score_partition` refuses a `pre_scored` set that disagrees on target, calibration or row count (ADR-0037). Do not walk a frame with one target, one calibration or one partition and print the card for another.
- An artifact declares its estimator, and everything about it has to agree: `artifact_format`, `estimator`, `features_used` and the presence or absence of band cells (ADR-0020). Build estimators only through `LoadedArtifact.estimator()` / `estimator_for(provenance)` — never by handing a cohort table to whichever class was imported — because decay and `evaluate` once did exactly that and reported a position artifact as identical to the flat model. The band a request is answered from belongs in `basis`; an absent position stays unknown rather than being banded as first in the queue.
- `decay` and `origins` answer different questions; do not quote one as the other. Decay takes its cutoff from the artifact's own `trained_to`, freezes the cohort table, the prevalence baseline and any calibration layer, and refuses below two usable horizons (ADR-0018). Origins refit both the table and the baseline at every cutoff (ADR-0014). Each report publishes its `evaluation_method` so a refit result cannot be pasted into a decay claim.
- Do not claim group outcomes from independent multiplication as validated.
- Show a structured abstention when no validated model or source is available; never return `200 OK` with a fabricated probability.
- Keep synthetic fixtures labelled and out of any real-world performance claim.
- Do not make storage happen by one switch. A report is kept only when the server enables history *and* the request asks; do not default `RAILCONFIRM_PERSIST_PREDICTIONS` on, do not store by default in tests that a reader might mistake for the product, and never widen `DENIED_KEYS` without a recorded privacy decision.
- Update the changelog and session log; create a sequential ADR for material decisions.
- Prefer meaningful commits; never manufacture commit count.
- Report a command's actual exit code and output. A local green run is not evidence about CI: they resolve different package versions, which is why `pyproject.toml` now pins the tools.

## If blocked

Report the exact missing evidence, permission or dataset and continue with work that does not depend on it. Do not replace a blocker with a fabricated implementation, and do not weaken a check to get a green result — the last session's failed CI runs were fixed by correcting the code and the tests, and each failure is recorded in `docs/DEVELOPMENT_LOG.md`.
