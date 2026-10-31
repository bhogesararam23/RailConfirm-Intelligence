# Open-source ecosystem and technical landscape

**Last reviewed: 2026-10-31**
**Scope: Workstream H — open-source and technical ecosystem review**

This document evaluates open-source projects and technical components that could
materially help RailConfirm, and records the dependency/integration recommendations.
Reuse is evaluated on: actual repository and maintainer; current maintenance activity;
licence; dependency requirements; security status; compatibility with Python 3.11+ and
the current backend/frontend; technical and legal appropriateness. Dependencies are not
added merely because a project exists; they are added only when the benefit is
measured and the licence is compatible.

---

## 1. Candidate libraries

### 1.1 Survival analysis

| Project | Repo / maintainer | Maintenance | Licence | Python compat | Notes | Verdict |
|---|---|---|---|---|---|---|
| scikit-survival | `sebp/scikit-survival` | Actively maintained | BSD-style (scikit-learn ecosystem) | Python 3.11+; pandas 2.2+; scikit-learn 1.9 | Survival regression, discrete-time hazard, right/interval censoring | **Candidate for future H1/H2 work**; evaluate per-version |
| lifelines | `CamDavidsonPilon/lifelines` | Actively maintained | MIT | Python 3.8+ | Survival regression, parametric, discrete survival models | Candidate; lighter alternative |
| SurvivalEVAL | `shi-ang/SurvivalEVAL` | Maintained | MIT | Python 3.10+ | Evaluation of survival predictions (censoring-aware) | Evaluation-support candidate |

**Assessment:** All three are appropriate for the planned survival/hazard and
time-to-chart modelling (H1/H2) and are compatible with the current Python stack.
None is used yet; the project must stay local-first and no dependency is added until
the relevant experiment is justified.

### 1.2 Probabilistic tabular and calibration

| Project | Repo / maintainer | Notes | Licence | Verdict |
|---|---|---|---|---|
| scikit-learn | `scikit-learn/scikit-learn` | Core of the ML stack | BSD-3-Clause | Already in use; introduced for models if any |
| SciPy / NumPy / pandas | — | Numeric stack | BSD/BSD/BSD | Already in use |

**Assessment:** No new dependency needed for calibration; the project already
implements Platt scaling via a logistic model and ADR-0017 measures subgroup
calibration. Calibration libraries are not needed.

### 1.3 Time-series / temporal

| Project | Repo / maintainer | Notes | Licence | Verdict |
|---|---|---|---|---|
| pandas | — | Already used | BSD | Already in use |
| NumPy | — | Already used | BSD | Already in use |
| statsmodels | — | Statistical models | BSD | Optional future |

**Assessment:** No new dependency needed for temporal evaluation; the project already
has a rolling-origin and frozen-artifact pipeline.

### 1.4 Data validation and provenance

| Project | Repo / maintainer | Notes | Licence | Verdict |
|---|---|---|---|---|
| pandera / Great Expectations | community | Data validation | BSD | Optional; not needed yet |

**Assessment:** Data validation is already implemented in the repository (`validator.py`,
`manifest.py`, dataset gate). External validation libraries are not required for the
local-first build.

### 1.5 Model monitoring and evaluation

| Project | Repo / maintainer | Notes | Licence | Verdict |
|---|---|---|---|---|
| volcado / model-monitoring tools | — | Not needed | — | Not used yet |

**Assessment:** Evaluation is already handled within the repo's temporal evaluation
(ADR-0013/0014/0018). Standard monitoring tools are not a substitute for a
well-defined local evaluation protocol.

### 1.6 Browser-based end-to-end testing

| Project | Notes | Licence | Verdict |
|---|---|---|---|
| Playwright / Cypress | E2E browser testing | MIT / MIT | Already used for smoke tests; consider Playwright for future full-stack |

**Assessment:** The cross-stack smoke gate (ADR-0027) already runs the API and the
built frontend against loopback ports. Playwright is the obvious E2E driver for
interaction/accessibility coverage if the product moves to a public deployment.

### 1.7 Railway and transport data parsers

| Project | Notes | Licence | Verdict |
|---|---|---|---|
| NTES clients (ntes-client, freakynit/ntes-client, x64vbhv/ntes-client) | Unofficial Python clients for NTES; reverse-engineered mobile protocol; PNR captcha-gated | Varying | **Not recommended**; unofficial, reverse-engineered, security/terms risk |

**Assessment:** The unofficial NTES clients are reverse-engineered from mobile apps,
inconsistent with the project's respect for access restrictions, and no
long-term relationship. Also, NTES is current/near-future only, so no historical
outcome data is available from it regardless. Not adopted.

### 1.8 Networking / security tooling

| Project | Notes | Licence | Verdict |
|---|---|---|---|
| httpx | HTTP client | BSD | Already used |
| pydantic | Validation, schemas | MIT | Already used |
| pytest / ruff / mypy | Testing, lint, types | MIT / MIT / MIT | Already used |

**Assessment:** The stack is already aligned and dependency-light.

---

## 2. Architecture patterns identified

1. **Immutable, dated dataset manifests + intake gate + versioned artifacts** — the
   pattern in `DATA_CONTRACT.md`, `DATASET_MANIFEST_TEMPLATE.yaml`, `loader.py`,
   `validator.py`, `manifest.py` and the training gate. This is the repository's
   proven pattern for data governance.
2. **Survival-style time-to-chart as a future method** — the codebase already
   reconstructs features only available at `prediction_at`, which is the key
   architectural decision for a leakage-free time-to-event model. scikit-survival or
   lifelines are the appropriate tools when the approved dataset arrives.
3. **Dependent joint outcomes via Poisson-binomial** — ADR-0003/0016 define the
   exact `P(K=k)`/`P(K>=k)` distribution and comonotonic bounds. These are the
   correct baselines for group outcomes.
4. **Temporal ablation discipline** — every feature group is a candidate until a
   temporal holdout ablation is published; this is the single most important pattern
   for avoiding leakage and overfitting.
5. **Two-gate promotion + frozen-artifact decay** — ADR-0009/0013/0018/0030 implement
   trust boundaries and a single, reproducible evaluation protocol.

---

## 3. Dependency/integration recommendations

**Nothing is added in this campaign** — no new runtime dependency is required. The
recommendations are forward-looking:

| Recommendation | Status | Condition |
|---|---|---|
| Adopt scikit-survival or lifelines for H1/H2 experiments | Future | Approved dataset + evidence that status trajectory adds signal |
| Adopt a data-validation library only if the core validator is extended | Optional | Selective use only |
| Playwright for E2E | Optional | When a public deployment is planned |
| NTES unofficial clients | **Reject** | Reverse-engineered, security/terms risk |

**Dependency hygiene rule:** every new dependency is documented with its licence,
version constraints, security status, Python compatibility and whether the benefit is
measured. No dependency is added merely because a project exists.
