# ADR-0049: Deterministic Offline Synthetic Rehearsal of the Prospective Data Lifecycle

- **Status:** Accepted
- **Date:** 2026-11-05
- **Decision owner:** Project maintainers
- **Related:** ADR-0007, ADR-0043, ADR-0044, ADR-0045, ADR-0046, ADR-0047, ADR-0048, docs/data/PROSPECTIVE_COLLECTION_PROTOCOL.md, docs/technical/TESTING_STRATEGY.md

## Context

The prospective collection, review, withdrawal, export, lineage and quarantine machinery (ADR-0044 through ADR-0048) is exercised by unit and CLI tests, but no single run demonstrates that a *complete* lifecycle from intake to readiness reporting behaves as documented, end to end, on one coherent fixture. Operators preparing for the eventual real pilot need a repeatable, offline way to prove the software path — and a report that names which governance steps are still open — before any real participant, PNR or consent is involved.

Constraints that shape the decision:

- The current build is local-first (ADR-0007): no network, provider, polling or hosted inference may be introduced to demonstrate the path.
- Real participant recruitment, real PNRs, personal information and fabricated consent are prohibited. Any rehearsal must be explicitly synthetic and must never be presented as railway evidence.
- The rehearsal must not duplicate business logic. Every transition (review, withdrawal, export, reconciliation, quarantine) must be performed by the same functions a real pilot would call, so a passing rehearsal reflects the production path rather than a parallel implementation.
- Failures must be visible. A gate that runs but proves nothing is not a pass.

## Decision

1. **Add one orchestration module, `railconfirm.data.rehearsal`.** It calls the existing prospective, export, lineage, quarantine, longitudinal, manifest, training and inference APIs; it defines no new lifecycle rule. The module owns a deterministic synthetic fixture (`build_primary_batch`) covering valid, pending, rejected, quarantined and withdrawn submissions, a multi-passenger group, a censored outcome, an unverified outcome and an invalid observation shape used as a negative control.

2. **Model the run as an ordered list of gates with a fail-closed contract.** Each gate records evidence, failures, warnings and required human actions. A gate that records no evidence, or any failure, is reported as `fail`; its `effective_failures()` names the incompleteness. The overall rehearsal passes only when every gate in `REHEARSAL_GATE_ORDER` is present and none failed. Warnings leave the run passing but visible.

3. **Separate the machine verdict from human authorization in the report.** `RehearsalReport` publishes `software_rehearsal_passed` and a fixed `real_world_pilot_authorized: false`, and its readiness statement always distinguishes "SOFTWARE REHEARSAL PASSED/FAILED" from "REAL-WORLD PILOT AUTHORIZED: NO". Passing the rehearsal never implies a pilot may begin.

4. **Expose it through the existing CLI as `python -m railconfirm.data prospective rehearsal <outdir>`**, with optional `--salt`, `--timestamp` and `--json`. The command writes a machine-readable `rehearsal_report.json` and a human-readable `rehearsal_report.txt`, both prefixed with the synthetic marker, and exits non-zero (1) when the rehearsal did not pass. It reuses the package's established exit-code contract (0 success, 1 check failed, 2 usage error).

5. **Keep the run deterministic and offline.** Fixed default timestamp and salt make a default run reproducible byte-for-byte; the prediction gate exercises the ordinary no-promoted-model abstention path, so no artifact, network call or hosted inference is needed. Rehearsal data is proven non-trainable by asserting the training gate refuses it.

## Alternatives considered

- **A standalone script outside the package.** A script would drift from the importable APIs and would not be covered by the package's type checking and import boundaries. Keeping the logic in `railconfirm.data.rehearsal` and surfacing it through the existing CLI reuses the established dispatch, exit codes and documentation structure.
- **Re-implementing the lifecycle inside the rehearsal for clearer assertions.** This would test a parallel implementation, not the production path, and could pass while the real functions regressed. The rehearsal deliberately calls the same functions the pilot would.
- **Reporting only a boolean pass/fail.** A boolean cannot show which gate failed or which human steps remain. The gate contract records per-step evidence, failures, warnings and human actions so a reader can see exactly what was and was not demonstrated.

## Consequences

- A clean local checkout can run the complete synthetic lifecycle offline with one command and receive both a machine- and human-readable readiness report.
- Regression coverage now asserts the full end-to-end path, not only individual primitives; a withdrawal that could survive into a verified-current export, or a gate that silently proves nothing, fails the suite.
- The report makes explicit that passing is a software result, not authorization; consent, legal/privacy review, operator approval and approved real data remain open human steps.
- No new business rule, dependency, network call or data source is introduced.

## Validation

- Regression tests in `backend/tests/data/test_rehearsal.py` cover: every gate present and passing; deterministic output for a repeated run; labelled reports written to disk; withdrawal absent from the verified-current export with stale detection naming the withdrawn records; salt-length and naive-timestamp refusal; the fail-closed gate and report contract (missing gates fail, warnings warn); and the CLI surface (zero exit on pass, parseable JSON, non-zero exit on a naive timestamp or short salt).
- The full backend suite, Ruff, Mypy, repository hygiene and the full-stack smoke check run green with the new module and subcommand.
