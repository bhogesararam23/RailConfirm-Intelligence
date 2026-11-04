# ADR-0047: Standardized Atomic File I/O and Static Typing Conformance

- **Status:** Accepted
- **Date:** 2026-11-05
- **Decision owner:** Project maintainers
- **Related:** ADR-0010, ADR-0043, ADR-0044, ADR-0045, ADR-0046, docs/ROADMAP.md, docs/technical/INGESTION_AND_TRACKING.md

## Context

During a full repository conformance audit following the implementation of ADR-0046, three categories of engineering discrepancies and fragility were uncovered:

1. **Non-atomic file serialization across data boundaries:** While ADR-0046 introduced `atomic_write_json` inside `prospective.py`, critical serialization paths elsewhere in the data layer (`save_longitudinal_dataset` in `longitudinal.py`, `write_manifest` in `manifest.py`, and quarantine sidecar generation in `inspection.py`) still relied on standard, non-atomic `Path.write_text()` or `open("w")`. An unexpected interruption, power event, or disk-full condition during these operations could leave truncated, unparseable, or empty files on disk, corrupting dataset provenance or losing longitudinal observation histories.
2. **Static typing contract violations (`mypy` errors):** Ten static typing errors emerged across `longitudinal.py`, `inspection.py`, and `data/__main__.py`. Specifically, three calls in `StatusObservation.from_dict()`, `FinalOutcome.from_dict()`, and `PassengerReservation.from_dict()` accessed `parsed.category` on `ParsedStatus`, whereas `ParsedStatus` strictly exposes `normalized: NormalizedStatus` and `wl_category: WaitlistCategory | None`. Furthermore, `create_point_in_time_snapshot` called `isoformat()` on an un-narrowed optional `as_of_datetime`, and the CLI subcommands shadowed variable types across unrelated execution branches.
3. **Documentation discrepancies:** The roadmap status contained an accidental corrupted text artifact, and `AGENT_HANDOFF.md` documented "six jobs" in CI when `.github/workflows/ci.yml` declares exactly five jobs.

## Decision

1. **Centralize atomic I/O in `railconfirm.data._io`:**
   - Establish `railconfirm.data._io` providing `atomic_write_text()` and `atomic_write_json()`.
   - All atomic operations write to a temporary file created in the destination directory (`prefix=".tmp_{target.name}_"`) to guarantee same-filesystem placement, flush and sync the file descriptor via `os.fsync()`, and perform an atomic swap using `os.replace()`.
   - In the event of an exception during formatting, writing, or syncing, the temporary file is unlinked immediately, ensuring the destination file (if pre-existing) is never corrupted or partially modified.

2. **Migrate all data package write operations to the atomic abstraction:**
   - `save_longitudinal_dataset()` in `railconfirm.data.longitudinal` now writes through `atomic_write_text()`.
   - `write_manifest()` in `railconfirm.data.manifest` now writes through `atomic_write_text()`.
   - `quarantine_dataset()` in `railconfirm.data.inspection` now writes its cryptographic sidecar through `atomic_write_json()`.
   - `prospective.py` imports and re-exports `atomic_write_json` from `railconfirm.data._io`, eliminating duplicate utility logic while preserving full backward compatibility.

3. **Enforce strict static typing conformance:**
   - Update `longitudinal.py` to access `parsed.normalized` rather than `.category`.
   - Narrow `as_of_datetime` before invoking `isoformat()` in `create_point_in_time_snapshot`.
   - Disambiguate variable names in `data/__main__.py` (`lineage_report` for export lineage checks vs. `report` for audit reports) so `mypy` passes with 0 issues across all 49 backend source files without requiring `# type: ignore`.

4. **Reconcile documentation and CI specifications:**
   - Clean up duplicate line remnants in `docs/ROADMAP.md`.
   - Harmonize CI job counts across `AGENT_HANDOFF.md`, `PROJECT_STATUS.md`, and `.github/workflows/ci.yml` (five verified jobs: `backend-checks`, `frontend-checks`, `full-stack-smoke`, `browser-e2e`, and `repository-hygiene`).

## Alternatives considered

- **In-place writing with backups:** Writing to `.bak` before writing in-place requires manual rollback logic and does not protect against power failure during in-place truncation. Rejected in favor of filesystem-level atomic rename via `os.replace()`.
- **Third-party atomic writing libraries (e.g., `atomicwrites`, `boltons`):** Adding an external dependency violates the project rule to keep dependencies minimal and strictly pinned for local-first builds. The standard library (`tempfile`, `os.replace`, `os.fsync`) provides complete, cross-platform atomic guarantees.

## Consequences

- All dataset and manifest persistence paths are safe against process interruption and partial disk writes.
- Test suite expanded with dedicated unit tests in `tests/data/test_io.py`.
- `mypy` and `ruff check` pass cleanly across the entire codebase.

## Validation

- Tested with `pytest tests/data/test_io.py` including write failure and cleanup verification.
- Validated via full regression suite: 1,259 backend tests, 129 frontend tests, and repository hygiene gates passing cleanly.
