# ADR-0010: Declared lint and type-check rule sets, constrained tool ranges, and a real hygiene gate

- **Status:** Accepted
- **Date:** 2026-10-23
- **Decision owner:** Project maintainer
- **Related:** ADR-0002, ADR-0007, ADR-0009, `ci/README.md`, `.github/workflows/ci.yml`

## Context

On 2026-10-22 commit `a87afc1` passed `ruff check`, `mypy` and 217 tests locally and failed the CI lint job on the same tree. The cause was not the code.

- `backend/pyproject.toml` declared only `[tool.ruff] line-length = 100`. Ruff's default rule set comes from its version, so local ruff 0.16.9 enabled `DTZ001` (naive datetime) while CI's `ruff>=0.4.0` resolved 0.17.2, which does not. The `# noqa: DTZ001` markers added to satisfy local lint became `RUF100` unused-noqa failures in CI.
- CI resolved a materially different stack from the one developers run: pandas 3.1.0 vs 2.3.3, numpy 2.4.6 vs 2.4.0, FastAPI 0.161.1 vs 0.135.1, mypy 2.4.0 vs 1.19.1, pytest 9.1.1 vs 8.4.2. A green CI run was therefore evidence about a different environment, and a red one could not be assumed to describe the code.
- The workflow's "secret and private data" check was `grep -r "pnr" … | grep -v … | head -5` inside `if …; then`. A pipeline's status is its last command's status, and `head` exits 0 on empty input, so the condition was always true and the step could never fail on any finding. It printed a warning for every commit and prevented nothing.
- `ci/README.md` linked a deleted mirror file, which the broken scan could not see because no link check existed.

## Decision

**Declare the checks instead of inheriting them.**

- `backend/pyproject.toml` now lists `[tool.ruff.lint] select` explicitly, including `DTZ`. Timezone discipline is a product requirement here — an as-of timestamp decides which evidence may be used — so the rule stays selected regardless of what a future Ruff default says. `RUF100` is selected so a suppression cannot outlive the rule it silenced. `RUF001`-`RUF003` (ambiguous-unicode in prose) are not selected: the project writes en-dashes in user-visible messages deliberately.
- Mypy configuration moved into `pyproject.toml` (`files`, `check_untyped_defs`, `warn_unused_ignores`, `no_implicit_optional`, `python_version`), and CI runs plain `mypy`. The pydantic mypy plugin is not enabled because it has not been run against the versions CI resolves; an unverifiable check is not a gate.
- Development tool ranges are constrained (`ruff>=0.16.9,<0.18`, `mypy>=1.19,<3`, `pytest>=8.2,<10`, `coverage>=7.5,<8`) so a lint or type result is reproducible across machines. Runtime libraries are bounded by major version. This is deliberate over-constraint of *tools only*; application dependencies stay on ranges because a green run on pandas 2.3 and pandas 3.1 is useful evidence, not a risk to remove.
- The hygiene checks move from inline shell into `scripts/check_repository_hygiene.py`, which runs identically locally and in CI and exits non-zero on findings: required documentation present, relative Markdown links resolve, no private-key/token patterns, no `.env`, no tracked file above 2 MB, and no PNR-shaped value in a file that does not declare its data synthetic.
- The workflow requests `permissions: contents: read`, cancels superseded runs on the same ref, and enforces `--cov-fail-under=90` for backend coverage (branch coverage enabled).

## Alternatives considered

- **Leave Ruff and Mypy on version defaults.** Rejected: the same commit then means different things on different machines, which is exactly the failure observed.
- **Pin every dependency exactly, or commit a lock file.** Rejected for runtime libraries today: CI demonstrating that the suite passes on both pandas 2.3 and 3.1 is stronger evidence than a single frozen version, and a lock file needs a resolver workflow the project does not yet have. Revisit when a real dataset enters training, where reproducibility of numeric behaviour matters more than tool convenience.
- **Drop the `# noqa: DTZ001` markers instead of selecting `DTZ`.** Rejected: those three tests deliberately construct naive timestamps to prove they are rejected. Silencing the rule globally to hide them would remove the check that protects the rest of the codebase.
- **Keep the secret scan in shell.** Rejected: the shell form was structurally incapable of failing, and a check that cannot fail is decoration.
- **Add a frontend test framework in the same change.** Deferred: the frontend's contract mismatch needs fixing first (see the frontend work in the development log), and a test framework added on top of invented types would only certify the wrong shape.

## Consequences

- A Ruff or Mypy upgrade is now a deliberate act with a visible diff, not a silent change in which rules ran.
- The hygiene script is a starting set of checks, not a security audit. A rotated secret still has to be revoked at the source, and the PNR heuristic is accident prevention.
- `--cov-fail-under=90` will block a commit that adds untested code paths. Current per-module weakest points are `data/loader.py` 61%, `data/validator.py` 62% and `data/manifest.py` 70%; these are scheduled for rewrite in the data-milestone work.
- The workflow file now needs the `workflow` OAuth scope to push, which the maintainer's credential has.
- `ci/README.md` documents each job as it actually runs, including the frontend gap.

## Validation

- Reproduced the failure: local `ruff 0.16.9` reported `DTZ001`, CI log for run `39865661797` reports `RUF100 … non-enabled: DTZ001` with `ruff==0.17.2` installed, so the divergence is measured rather than inferred.
- `python scripts/check_repository_hygiene.py` on the pre-fix tree reported exactly one finding (`ci/README.md` broken link), which was then fixed; the script exits 0 now and 1 when a link is broken (verified by reintroducing the bad link and re-running).
- `ruff check`, `mypy` and `pytest --cov-fail-under=90` run clean locally at 92% branch coverage.
- CI must be observed green on the pushed commit; the result is recorded in `docs/DEVELOPMENT_LOG.md` rather than assumed.
