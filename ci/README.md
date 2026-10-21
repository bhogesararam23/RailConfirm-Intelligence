# Continuous Integration (CI)

This directory contains the GitHub Actions CI workflow specification:
- `github-actions-ci.yml`: Defines backend tests (pytest, ruff, mypy), frontend build and type-checking, and repository secret/privacy scans.

## To activate on GitHub Actions

Copy `ci/github-actions-ci.yml` into `.github/workflows/ci.yml`:

```bash
mkdir -p .github/workflows
cp ci/github-actions-ci.yml .github/workflows/ci.yml
git add .github/workflows/ci.yml
git commit -m "ci: enable GitHub Actions workflow"
git push origin main
```

*(Requires a Git personal access token or SSH key with the `workflow` scope enabled).*
