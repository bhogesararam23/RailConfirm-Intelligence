# Continuous integration

The active workflow is [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). There is no second mirror of the specification: an earlier copy of this directory held `github-actions-ci.yml`, which was deleted when the workflow landed, and the links below describe the file that runs.

## Jobs

| Job | Runs | Gate |
|---|---|---|
| Backend | `ruff check railconfirm/ tests/`, `mypy` (configured in `backend/pyproject.toml`), `pytest --cov=railconfirm --cov-fail-under=90` | Lint, types, tests and branch coverage must all pass |
| Frontend | `npm ci`, `npm run type-check`, `npm run lint`, `npm run build` | Type-check, ESLint and a production build |
| Repository hygiene | `python scripts/check_repository_hygiene.py` | Required docs present, relative Markdown links resolve, no secret material or oversized tracked files, no PNR-shaped value in a file that does not declare its data synthetic |

Triggers: pushes to `main`, pull requests targeting `main`, and manual dispatch. The workflow requests `contents: read` only; it needs no write scope.

Tool versions come from `backend/pyproject.toml`, where the Ruff rule set and the Mypy configuration are declared rather than inherited from a version default. That is deliberate: on 2026-10-22 the same commit passed locally and failed CI because the two environments resolved different Ruff versions and neither configuration selected its rules explicitly.

## Running the same checks locally

```bash
cd backend
ruff check railconfirm/ tests/
mypy
pytest tests/ --cov=railconfirm --cov-fail-under=90

cd ..
python scripts/check_repository_hygiene.py

cd frontend
npm ci
npm run type-check && npm run lint && npm run build
```

## Known gaps

- The frontend job has no test step because no frontend test framework is configured yet. Type-checking and ESLint cannot detect an API response shape that does not match the backend, so the contract between `frontend/src/lib/types.ts` and `backend/railconfirm/api/v1/schemas.py` is not machine-checked.
- The hygiene scan inspects tracked files in the working tree; it is accident prevention, not a credential audit, and a rotated secret still has to be revoked at the provider.
- Coverage is a statement-and-branch floor across the backend package, not a guarantee that any specific behaviour is tested.
