# Continuous Integration (CI)

The GitHub Actions CI workflow specification is maintained at:
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
- [`ci/github-actions-ci.yml`](github-actions-ci.yml)

It defines:
- **Backend Checks**: Python 3.11 linting (`ruff`), strict type-checking (`mypy`), and test suite with coverage reporting (`pytest --cov=railconfirm`).
- **Frontend Checks**: Node.js 20 clean install (`npm ci`), TypeScript type-checking (`tsc --noEmit`), linting (`next lint`), and production build (`next build`).
- **Docs & Security Checks**: Repository documentation completeness and secret/privacy protection scans (no live PNRs or unredacted credentials).

> [!NOTE]
> If pushing `.github/workflows/ci.yml` directly is restricted by GitHub OAuth token scopes (requiring the `workflow` scope), the workflow file `ci/github-actions-ci.yml` in this directory mirrors the active specification and can be promoted to `.github/workflows/ci.yml` via any token with workflow permissions or the GitHub web interface.
