# ADR-0048: Atomic Quarantine Ingestion, Snapshot Persistence, and CI Conformance Reconciliation

- **Status:** Accepted
- **Date:** 2026-11-05
- **Decision owner:** Project maintainers
- **Related:** ADR-0010, ADR-0041, ADR-0043, ADR-0046, ADR-0047, docs/ROADMAP.md, docs/technical/TESTING_STRATEGY.md

## Context

Following the standardization of atomic text and JSON writes in ADR-0047, a complete audit of all remaining file-writing paths in the data package and documentation revealed three critical integrity gaps:

1. **Quarantine copy and pair atomicity gap:** `quarantine_dataset()` in `railconfirm.data.inspection` utilized standard `shutil.copy2()` to duplicate candidate files into `data/quarantine/`. If a copy was interrupted midway (e.g., SIGINT, OS termination, disk quota exhaustion), an unparseable, partial file remained in quarantine. Additionally, if the subsequent cryptographic sidecar report write failed, an orphaned quarantined file was left without cryptographic provenance or justification metadata.
2. **Snapshot CSV truncation vulnerability:** In `railconfirm.data.__main__::_snapshot()`, point-in-time snapshot DataFrames were persisted directly via `snap_res.frame.to_csv(args.output, index=False)`. A write interruption or flush failure would truncate training snapshot interchange files on disk.
3. **Cross-platform `fsync` file descriptor semantics:** On Windows (NTFS / MSVCRT), invoking `os.fsync()` on a file descriptor opened with `"rb"` raises `OSError: [Errno 9] Bad file descriptor`. File descriptors must be opened with write/update access (`"r+b"`) for `_commit` / `fsync` to operate correctly across platforms.
4. **Documentation and CI specification drift:** `README.md` and `docs/technical/TESTING_STRATEGY.md` contained obsolete test counts (1043 / 1195 backend tests) and stated that CI runs four jobs, omitting the headless Chromium Playwright browser E2E test job (`browser-e2e`) formalized under ADR-0041. `docs/PROJECT_STATUS.md` retained a stale review header citing ADR-0046.

## Decision

1. **Implement `atomic_copy_file()` in `railconfirm.data._io`:**
   - Copies the source file into a temporary file in the destination's parent directory (`prefix=".tmp_{dst.name}_"`).
   - Opens the temporary file with `"r+b"` mode to execute `os.fsync(f.fileno())` safely across both POSIX and Windows.
   - Atomically swaps the temporary file into place via `os.replace()`.
   - On any failure or interruption, immediately unlinks the temporary file and guarantees the pre-existing destination file (if any) remains unaltered.

2. **Implement transactional pair-atomicity in `quarantine_dataset()`:**
   - Invokes `atomic_copy_file()` to stage the quarantined file safely.
   - Generates the `.quarantine.json` cryptographic sidecar report using `atomic_write_json()`.
   - Wraps sidecar generation in an exception handler: if writing the sidecar fails, the quarantined file is deleted, ensuring that quarantine artifacts are all-or-nothing.

3. **Implement `atomic_write_csv()` in `railconfirm.data._io`:**
   - Accepts a `pandas.DataFrame`, serializes it to formatted CSV text, and delegates persistence to `atomic_write_text()`.
   - Replaces direct `frame.to_csv()` in `backend/railconfirm/data/__main__.py::_snapshot()` with `atomic_write_csv()` and structured error handling.

4. **Reconcile CI job expectations and documentation baselines:**
   - Update `docs/technical/TESTING_STRATEGY.md` to define all 5 declared CI jobs: `backend-checks`, `frontend-checks`, `full-stack-smoke`, `browser-e2e`, and `repository-hygiene`.
   - Reconcile `README.md`, `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, and `docs/AGENT_HANDOFF.md` to reflect the verified baseline of 1,266 backend pytest tests, 129 frontend Vitest tests, and 6 Playwright browser E2E tests with 93.5% branch coverage.

## Alternatives considered

- **In-place copy with cleanup heuristics:** Allowing `shutil.copy2()` to copy directly and attempting post-hoc cleanup on errors leaves race conditions where externally killed processes leave half-written files. Atomic temporary file swap guarantees zero partial writes at the directory entry level.
- **External database for quarantine audit tracking:** Retaining SQLite or a dedicated database for quarantine sidecars would violate the local-first, decoupled filesystem design of Phase 2 data tooling. Self-contained cryptographic sidecars (`.quarantine.json`) beside the quarantined data files remain the most portable format.

## Consequences

- All file serialization and duplication paths in `railconfirm.data` are atomic, safe against partial writes, and clean up temporary artifacts on failure.
- Quarantine operations are guaranteed pair-atomic (file + sidecar).
- Documentation, CI workflow definitions, and test counts are in 100% agreement with the running codebase.

## Validation

- Comprehensive regression tests in `backend/tests/data/test_io.py` testing `atomic_copy_file`, `atomic_write_csv`, failure injection, destination preservation, and pair-atomicity rollback.
- CLI regression tests in `backend/tests/data/test_intake_cli.py` testing snapshot atomic write safety and error handling.
- Full stack verification: 1,266 backend tests, 129 frontend tests, 6 browser E2E tests, and repository hygiene gates passing green.

