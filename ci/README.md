# Continuous integration

The active workflow is [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). There is no second mirror of the specification: an earlier copy of this directory held `github-actions-ci.yml`, which was deleted when the workflow landed, and the links below describe the file that runs.

## Jobs

| Job | Runs | Gate |
|---|---|---|
| Backend | `ruff check railconfirm/ tests/`, `mypy` (configured in `backend/pyproject.toml`), `pytest --cov=railconfirm --cov-fail-under=90` | Lint, types, tests and branch coverage must all pass |
| Frontend | `npm ci`, `npm run type-check`, `npm run lint`, `npm test`, `npm run build` | Vitest unit and contract tests, TypeScript, ESLint and a production build |
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
npm run type-check && npm run lint && npm test && npm run build
```

## Known gaps

- The frontend contract tests assert the shape the client expects against fixtures copied from `backend/railconfirm/api/v1/schemas.py`. They catch a client that has drifted from the documented contract; they do not talk to a running backend, so a server-side change can still pass until its own schema tests are updated. A live cross-stack contract check is not configured.
- No end-to-end browser test runs in CI: that needs both servers up, so the full flow was verified manually against a local uvicorn and `next dev` instead, and the result is recorded in `docs/DEVELOPMENT_LOG.md`.
- The hygiene scan inspects tracked files in the working tree; it is accident prevention, not a credential audit, and a rotated secret still has to be revoked at the provider.
- Coverage is a statement-and-branch floor across the backend package, not a guarantee that any specific behaviour is tested.
