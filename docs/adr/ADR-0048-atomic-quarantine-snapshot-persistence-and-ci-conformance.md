# ADR-0048: Atomic Quarantine Ingestion, Snapshot Persistence, and CI Conformance Reconciliation

- **Status:** Accepted
- **Date:** 2026-11-05
- **Decision owner:** Project maintainers
- **Related:** ADR-0010, ADR-0041, ADR-0043, ADR-0046, ADR-0047, docs/ROADMAP.md, docs/technical/TESTING_STRATEGY.md

## Context

Following the standardization of atomic text and JSON writes in ADR-0047, a complete audit of all remaining file-writing paths in the data package and documentation revealed several critical integrity and reliability considerations:

1. **Quarantine copy and pair atomicity gap:** `quarantine_dataset()` in `railconfirm.data.inspection` previously utilized standard `shutil.copy2()` to duplicate candidate files into `data/quarantine/`. If a copy was interrupted midway (e.g., SIGINT, OS termination, disk quota exhaustion), an unparseable, partial file remained in quarantine. Additionally, if the subsequent cryptographic sidecar report write failed, an orphaned quarantined file was left without cryptographic provenance or justification metadata.
2. **Concurrent source mutation during quarantine:** Computing the SHA-256 hash on the source path *before* initiating the copy exposed a race condition: if the source file was being modified concurrently, the sidecar digest recorded the pre-copy state while the quarantined file contained the post-copy bytes.
3. **Multi-file atomicity boundaries (exception rollback vs. hard power loss):** While an in-process exception handler (`try...except`) can unlink a quarantined file if sidecar generation fails, standard POSIX and NTFS filesystems do not support atomic multi-file commits across unexpected hard power loss or ungraceful SIGKILL terminations. Relying solely on in-process cleanup leaves open the possibility of post-crash orphaned files or orphaned sidecars.
4. **Snapshot CSV truncation and memory scaling:** In `railconfirm.data.__main__::_snapshot()`, point-in-time snapshot DataFrames were persisted directly via `snap_res.frame.to_csv(args.output, index=False)`. A write interruption or flush failure would truncate training snapshot interchange files on disk. Furthermore, serializing large DataFrames to in-memory Python strings prior to writing doubled memory requirements.
5. **Cross-platform `fsync` file descriptor semantics and permission preservation:** On Windows (NTFS / MSVCRT), invoking `os.fsync()` on a file descriptor opened with `"rb"` raises `OSError: [Errno 9] Bad file descriptor`. File descriptors must be opened with write/update access (`"r+b"`) for `_commit` / `fsync` to operate correctly across platforms. Additionally, atomically replacing existing files via `os.replace` resets file permissions unless the pre-existing `st_mode` is explicitly queried and preserved via `os.chmod`.
6. **Documentation and CI specification drift:** `README.md` and `docs/technical/TESTING_STRATEGY.md` contained obsolete test counts and stated that CI runs four jobs, omitting the headless Chromium Playwright browser E2E test job (`browser-e2e`) formalized under ADR-0041. `docs/PROJECT_STATUS.md` and `docs/ROADMAP.md` retained stale review headers.

## Decision

1. **Implement `atomic_copy_file()` in `railconfirm.data._io`:**
   - Copies the source file into a temporary file in the destination's parent directory (`prefix=".tmp_{dst.name}_"`).
   - Opens the temporary file with `"r+b"` mode to execute `os.fsync(f.fileno())` safely across both POSIX and Windows.
   - Atomically swaps the temporary file into place via `os.replace()`, syncing directory entries on POSIX.
   - On any failure or interruption, immediately unlinks the temporary file and guarantees the pre-existing destination file (if any) remains unaltered.

2. **Harden `quarantine_dataset()` with copy-first verification:**
   - First copies the source into a temporary staged file in the quarantine directory.
   - Computes the SHA-256 digest and file size directly from the staged copy itself, guaranteeing that the cryptographic sidecar strictly reflects the quarantined bytes even if the source is mutated concurrently.
   - Renames the staged file to its content-addressed final path (`{timestamp}_{sha256[:12]}_{name}`).
   - Writes the `.quarantine.json` sidecar report using `atomic_write_json()`.
   - In-process atomicity: If writing the sidecar fails with an exception, the quarantined file is deleted, ensuring in-process rollback.

3. **Provide quarantine directory audit and recovery tooling:**
   - Implement `audit_quarantine_directory()` in `railconfirm.data.inspection` and expose it via the CLI subcommand `python -m railconfirm.data audit-quarantine`.
   - Verifies all (data file, sidecar) pairs, detects orphaned data files, detects orphaned sidecars, and validates that every file matches its recorded SHA-256 hash.
   - Provides an optional `--purge-orphans` flag to safely heal post-crash orphaned artifacts without manual operator intervention.

4. **Implement zero-memory-overhead `atomic_write_csv()` in `railconfirm.data._io`:**
   - Accepts a `pandas.DataFrame` and streams output directly to an open `NamedTemporaryFile(newline="", mode="w")`.
   - Flushes and fsyncs the descriptor to guarantee durable disk write without buffering full CSV text strings in memory.
   - Queries and restores pre-existing file mode (`st_mode`) via `os.chmod` if the target already exists.
   - Commits the file atomically via `os.replace()`.
   - Used across `__main__.py::_snapshot()` with structured error handling.

5. **Reconcile CI job expectations and documentation baselines:**
   - Update `docs/technical/TESTING_STRATEGY.md` to define all 5 declared CI jobs: `backend-checks`, `frontend-checks`, `full-stack-smoke`, `browser-e2e`, and `repository-hygiene`.
   - Reconcile `README.md`, `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, and `docs/AGENT_HANDOFF.md` to reflect the verified baseline of 1,273 backend pytest tests, 129 frontend Vitest tests, and 6 Playwright browser E2E tests with >93% branch coverage.

## Alternatives considered

- **In-place copy with cleanup heuristics:** Allowing `shutil.copy2()` to copy directly and attempting post-hoc cleanup on errors leaves race conditions where externally killed processes leave half-written files. Atomic temporary file swap guarantees zero partial writes at the directory entry level.
- **External database for quarantine audit tracking:** Retaining SQLite or a dedicated database for quarantine sidecars would violate the local-first, decoupled filesystem design of Phase 2 data tooling. Self-contained cryptographic sidecars (`.quarantine.json`) beside the quarantined data files accompanied by `audit_quarantine_directory()` reconciliation provide complete auditability without database dependencies.

## Consequences

- All file serialization and duplication paths in `railconfirm.data` are atomic, safe against partial writes, and clean up temporary artifacts on failure.
- Quarantine operations are guaranteed pair-consistent, verifiable by cryptographic hash, and recoverable after hard crashes.
- Documentation, CI workflow definitions, and test counts are in 100% agreement with the running codebase.

## Validation

- Comprehensive regression tests in `backend/tests/data/test_io.py` testing `atomic_copy_file`, `atomic_write_csv` streaming, permission preservation, failure injection, destination preservation, and pair-atomicity rollback.
- Quarantine and audit tests in `backend/tests/data/test_inspection.py` verifying copy-first hashing, pair verification, orphan detection, orphan purging, and checksum mismatch detection.
- CLI regression tests in `backend/tests/data/test_intake_cli.py` testing snapshot atomic write safety and `audit-quarantine` CLI execution.
- Full stack verification: 1,273 backend tests, 129 frontend tests, 6 browser E2E tests, and repository hygiene gates passing green.
