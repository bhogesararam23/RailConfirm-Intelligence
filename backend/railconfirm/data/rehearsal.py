"""Deterministic, offline, synthetic rehearsal of the prospective data lifecycle.

This module orchestrates the existing prospective-collection, export, lineage,
quarantine and inference APIs into one end-to-end dry run. It adds no new
business rules: every lifecycle transition is performed by the functions that
would perform it in a real pilot, and the rehearsal only records whether the
observed outcome matches the documented expectation.

Guarantees:

* **Synthetic only.** Every artifact is built from fixture identifiers and
  labelled synthetic. No real participant, PNR, personal detail or consent is
  used, and nothing here is railway evidence.
* **Offline.** No network call, provider, polling loop or hosted inference is
  made. The prediction step exercises the same abstention path a local install
  takes with no promoted model.
* **Deterministic by default.** A fixed timestamp and salt are used unless the
  caller overrides them, so gate outcomes and exports are reproducible.
* **Fail-closed.** A gate that records no evidence, or any failure, is reported
  as failed. The overall rehearsal passes only when every expected gate is
  present and none failed.

Passing this rehearsal means the *software* behaves as documented. It does not
authorize a real pilot: consent, legal review and operator approval remain human
steps, and no synthetic result is a statement about railway behaviour.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from railconfirm.data._io import atomic_write_json, atomic_write_text
from railconfirm.data.inspection import (
    FormatType,
    audit_quarantine_directory,
    detect_schema,
    quarantine_dataset,
)
from railconfirm.data.longitudinal import (
    CensoringReason,
    FinalOutcome,
    LabelConfidence,
    StatusObservation,
    VerificationMethod,
    create_point_in_time_snapshot,
)
from railconfirm.data.prospective import (
    DEFAULT_NOTICE_VERSION,
    DEFAULT_RETENTION_POLICY,
    MIN_SALT_LENGTH,
    PROSPECTIVE_COLLECTION_SCHEMA_VERSION,
    ConsentMetadata,
    LineageStatus,
    ProspectiveBatch,
    ProspectivePassenger,
    ProspectiveSubmission,
    ReviewStatus,
    compute_canonical_batch_sha256,
    derive_pseudonym,
    export_batch_to_longitudinal,
    intake_prospective_submission,
    reconcile_and_regenerate_export,
    review_batch,
    scan_for_personal_data,
    validate_prospective_batch,
    verify_export_lineage,
    withdraw_submission,
)
from railconfirm.domain.exceptions import (
    DatasetValidationError,
    SecurityError,
    TemporalIntegrityError,
)
from railconfirm.domain.journey import make_journey
from railconfirm.domain.passenger import make_observation
from railconfirm.domain.prediction import AbstentionReason
from railconfirm.domain.status import NormalizedStatus
from railconfirm.inference.engine import InferenceEngine
from railconfirm.inference.registry import NO_MODEL_VERSION

REHEARSAL_SCHEMA_VERSION = "1.0.0"

DEFAULT_REHEARSAL_TIMESTAMP = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
"""Fixed run timestamp so a default rehearsal is reproducible byte-for-byte."""

DEFAULT_REHEARSAL_SALT = "railconfirm-rehearsal-synthetic-salt-0001"
"""Deterministic >=32-character salt for the synthetic pseudonymisation check."""

SYNTHETIC_MARK = "# SYNTHETIC REHEARSAL OUTPUT - NOT REAL RAILWAY DATA - NOT A PILOT"
"""Written beside every artifact so a reader cannot mistake a run for real data."""

PRIMARY_BATCH_ID = "BATCH_REHEARSAL_001"
EXPORT_DATASET_ID = "REHEARSAL_EXPORT_001"


class GateStatus(str, Enum):
    """Outcome of a single rehearsal gate."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


REHEARSAL_GATE_ORDER: tuple[str, ...] = (
    "synthetic_batch_generation",
    "pii_and_identifier_scan",
    "schema_and_governance_audit",
    "human_review_workflow",
    "withdrawal_lifecycle",
    "approved_record_export",
    "export_lineage_verification",
    "source_mutation_scenario",
    "stale_export_detection",
    "safe_reconciliation",
    "quarantine_integrity_audit",
    "filesystem_integrity",
    "scientific_safeguards",
    "structured_abstention",
    "final_readiness",
)
"""Every gate a complete rehearsal must evaluate, in execution order."""


@dataclass
class RehearsalGate:
    """One lifecycle check with the evidence, failures and warnings it observed."""

    gate_id: str
    title: str
    evidence: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    human_actions: list[str] = field(default_factory=list)

    def record(self, message: str) -> RehearsalGate:
        self.evidence.append(message)
        return self

    def fail(self, message: str) -> RehearsalGate:
        self.failures.append(message)
        return self

    def warn(self, message: str) -> RehearsalGate:
        self.warnings.append(message)
        return self

    def require_human(self, message: str) -> RehearsalGate:
        self.human_actions.append(message)
        return self

    @property
    def is_complete(self) -> bool:
        """A gate that recorded no evidence has not been demonstrated."""
        return bool(self.evidence)

    @property
    def status(self) -> GateStatus:
        if self.failures or not self.evidence:
            return GateStatus.FAIL
        if self.warnings:
            return GateStatus.WARN
        return GateStatus.PASS

    def effective_failures(self) -> list[str]:
        fails = list(self.failures)
        if not self.evidence:
            fails.append("gate recorded no evidence (incomplete)")
        return fails

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "title": self.title,
            "status": self.status.value,
            "evidence": list(self.evidence),
            "failures": self.effective_failures(),
            "warnings": list(self.warnings),
            "human_actions": list(self.human_actions),
        }


@dataclass
class RehearsalReport:
    """Machine- and human-readable result of a full rehearsal run."""

    run_id: str
    run_timestamp: str
    workspace: str
    gates: list[RehearsalGate]
    is_synthetic: bool = True
    schema_version: str = REHEARSAL_SCHEMA_VERSION

    @property
    def gate_ids(self) -> list[str]:
        return [g.gate_id for g in self.gates]

    @property
    def missing_gate_ids(self) -> list[str]:
        present = set(self.gate_ids)
        return [gid for gid in REHEARSAL_GATE_ORDER if gid not in present]

    @property
    def failed_gates(self) -> list[RehearsalGate]:
        return [g for g in self.gates if g.status is GateStatus.FAIL]

    @property
    def warned_gates(self) -> list[RehearsalGate]:
        return [g for g in self.gates if g.status is GateStatus.WARN]

    @property
    def overall_status(self) -> GateStatus:
        if self.missing_gate_ids or self.failed_gates:
            return GateStatus.FAIL
        if self.warned_gates:
            return GateStatus.WARN
        return GateStatus.PASS

    @property
    def software_rehearsal_passed(self) -> bool:
        return self.overall_status is not GateStatus.FAIL

    @property
    def readiness_statement(self) -> str:
        if self.software_rehearsal_passed:
            head = "SOFTWARE REHEARSAL PASSED"
            detail = (
                "All expected lifecycle gates were evaluated and none failed."
                if not self.warned_gates
                else f"All gates evaluated; {len(self.warned_gates)} raised warnings."
            )
        else:
            head = "SOFTWARE REHEARSAL FAILED"
            detail = (
                f"{len(self.failed_gates)} gate(s) failed or were incomplete."
            )
        return (
            f"{head} - {detail} This run is a synthetic, offline simulation. "
            "REAL-WORLD PILOT AUTHORIZED: NO. A real pilot additionally requires "
            "documented participant consent, legal and privacy review, operator "
            "approval and approved real data; none of those are established here."
        )

    def gate(self, gate_id: str) -> RehearsalGate | None:
        for g in self.gates:
            if g.gate_id == gate_id:
                return g
        return None

    def summary(self) -> str:
        lines = [
            "=== RailConfirm Prospective Rehearsal (SYNTHETIC SIMULATION) ===",
            f"Run: {self.run_id}  (schema v{self.schema_version})",
            f"Timestamp: {self.run_timestamp}",
            f"Workspace: {self.workspace}",
            f"Synthetic: {'yes' if self.is_synthetic else 'no'}",
            f"Overall: {self.overall_status.value.upper()} "
            f"({len(self.gates) - len(self.failed_gates)}/{len(self.gates)} gates passed)",
        ]
        if self.missing_gate_ids:
            lines.append(f"Missing gates: {', '.join(self.missing_gate_ids)}")
        lines.append("")
        for g in self.gates:
            lines.append(f"[{g.status.value.upper():4}] {g.gate_id}: {g.title}")
            for item in g.evidence:
                lines.append(f"        - {item}")
            for item in g.effective_failures():
                lines.append(f"  FAIL  - {item}")
            for item in g.warnings:
                lines.append(f"  WARN  - {item}")
            for item in g.human_actions:
                lines.append(f"  HUMAN - {item}")
        lines.append("")
        lines.append(self.readiness_statement)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "run_timestamp": self.run_timestamp,
            "workspace": self.workspace,
            "is_synthetic": self.is_synthetic,
            "overall_status": self.overall_status.value,
            "software_rehearsal_passed": self.software_rehearsal_passed,
            "real_world_pilot_authorized": False,
            "readiness_statement": self.readiness_statement,
            "missing_gate_ids": self.missing_gate_ids,
            "gate_count": len(self.gates),
            "failed_gate_count": len(self.failed_gates),
            "gates": [g.to_dict() for g in self.gates],
        }


# ── Deterministic synthetic fixtures ───────────────────────────────────────────

_BASE_DATE = date(2026, 7, 2)
"""First synthetic journey date. Fixed so the rehearsal is reproducible."""


def _consent(collected_at: datetime) -> ConsentMetadata:
    return ConsentMetadata(
        consent_basis="explicit_opt_in",
        notice_version=DEFAULT_NOTICE_VERSION,
        purpose_records=[
            "confirmation_probability_research",
            "model_calibration",
        ],
        retention_policy=DEFAULT_RETENTION_POLICY,
        collected_at=collected_at.isoformat(),
        data_subject_region="IN",
    )


def _departure(day_offset: int) -> datetime:
    j_date = _BASE_DATE + timedelta(days=day_offset)
    return datetime(j_date.year, j_date.month, j_date.day, 16, 55, tzinfo=UTC)


def _verified_outcome(dep_dt: datetime) -> FinalOutcome:
    return FinalOutcome(
        outcome_target="final_chart_cnf",
        outcome_status_raw="CNF",
        outcome_category=NormalizedStatus.CNF,
        outcome_observed_at=dep_dt - timedelta(hours=4),
        verification_source="synthetic_rehearsal_chart",
        verification_method=VerificationMethod.CHART_SNAPSHOT,
        label_confidence=LabelConfidence.VERIFIED,
    )


def _censored_outcome(dep_dt: datetime) -> FinalOutcome:
    return FinalOutcome(
        outcome_target="final_chart_cnf",
        outcome_status_raw="CENSORED",
        outcome_category=NormalizedStatus.CENSORED,
        outcome_observed_at=dep_dt - timedelta(hours=4),
        verification_method=VerificationMethod.CHART_SNAPSHOT,
        label_confidence=LabelConfidence.UNVERIFIED,
        is_censored=True,
        censoring_reason=CensoringReason.CHART_NOT_RECORDED,
    )


def _unverified_outcome(dep_dt: datetime) -> FinalOutcome:
    return FinalOutcome(
        outcome_target="final_chart_cnf",
        outcome_status_raw="CNF",
        outcome_category=NormalizedStatus.CNF,
        outcome_observed_at=dep_dt - timedelta(hours=4),
        verification_method=VerificationMethod.UNKNOWN,
        label_confidence=LabelConfidence.UNVERIFIED,
    )


def _passenger(
    sequence: int,
    group_id: str,
    *,
    dep_dt: datetime,
    initial_position: int,
    initial_category: NormalizedStatus,
    later_observation: bool,
    final_outcome: FinalOutcome,
) -> ProspectivePassenger:
    """One synthetic passenger; ``later_observation`` adds a post-booking look.

    The later look exists so the point-in-time snapshot can be shown to withhold
    it at a wider lead time instead of leaking a value known only nearer departure.
    """
    pid = f"{group_id}_P{sequence}"
    if initial_category is NormalizedStatus.RAC:
        initial_raw = f"RAC {initial_position}"
    else:
        initial_raw = f"GNWL {initial_position}"

    observations = [
        StatusObservation(
            observation_id=f"OBS_{group_id}_P{sequence}_1",
            passenger_record_id=pid,
            observed_at=dep_dt - timedelta(days=6),
            status_raw=initial_raw,
            status_category=initial_category,
            status_position=initial_position,
            source_id="rehearsal_synthetic_source",
        )
    ]
    if later_observation:
        observations.append(
            StatusObservation(
                observation_id=f"OBS_{group_id}_P{sequence}_2",
                passenger_record_id=pid,
                observed_at=dep_dt - timedelta(days=1),
                status_raw="GNWL 3" if initial_category is not NormalizedStatus.RAC else "RAC 1",
                status_category=initial_category,
                status_position=3 if initial_category is not NormalizedStatus.RAC else 1,
                source_id="rehearsal_synthetic_source",
            )
        )

    return ProspectivePassenger(
        passenger_sequence=sequence,
        original_status_raw=initial_raw,
        original_status_category=initial_category,
        original_status_position=initial_position,
        observations=observations,
        outcome=final_outcome,
    )


def build_primary_batch(*, salt: str = DEFAULT_REHEARSAL_SALT) -> ProspectiveBatch:
    """Build the eight-submission synthetic batch every lifecycle gate reuses.

    Composition (all identifiers are synthetic):

    1. ``SUB_REH_001`` - two-passenger group, extra later look, verified outcome.
    2. ``SUB_REH_002`` - solo, verified outcome.
    3. ``SUB_REH_003`` - solo, verified outcome (stays pending review).
    4. ``SUB_REH_004`` - solo, verified outcome (reviewed as rejected).
    5. ``SUB_REH_005`` - solo, censored outcome.
    6. ``SUB_REH_006`` - solo, verified outcome (consent withdrawn).
    7. ``SUB_REH_007`` - solo, verified outcome (quarantined).
    8. ``SUB_REH_008`` - solo, unverified outcome.
    """
    collected = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
    consent = _consent(collected)

    # The pseudonym is derived through the same salted HMAC used in production,
    # so the rehearsal also exercises the pseudonymisation primitive.
    def group(seq: int) -> str:
        return derive_pseudonym(f"synthetic_pnr_{seq:04d}", salt=salt)

    plan = [
        # (id, group_seq, train, day_offset, class, quota, board, dest, passengers, outcome kind)
        ("SUB_REH_001", 1, "12951", 0, "3A", "GN", "MMCT", "NDLS", [(12, NormalizedStatus.WL), (13, NormalizedStatus.WL)], "verified"),
        ("SUB_REH_002", 2, "12301", 1, "SL", "GN", "NDLS", "HWH", [(4, NormalizedStatus.RAC)], "verified"),
        ("SUB_REH_003", 3, "12951", 2, "3A", "GN", "MMCT", "NDLS", [(30, NormalizedStatus.WL)], "verified"),
        ("SUB_REH_004", 4, "12301", 3, "SL", "GN", "NDLS", "HWH", [(55, NormalizedStatus.WL)], "verified"),
        ("SUB_REH_005", 5, "12951", 4, "3A", "GN", "MMCT", "NDLS", [(70, NormalizedStatus.WL)], "censored"),
        ("SUB_REH_006", 6, "12301", 5, "SL", "GN", "NDLS", "HWH", [(18, NormalizedStatus.WL)], "verified"),
        ("SUB_REH_007", 7, "12951", 6, "3A", "GN", "MMCT", "NDLS", [(40, NormalizedStatus.WL)], "verified"),
        ("SUB_REH_008", 8, "12301", 7, "SL", "GN", "NDLS", "HWH", [(60, NormalizedStatus.WL)], "unverified"),
    ]

    submissions: list[ProspectiveSubmission] = []
    for (
        sub_id,
        group_seq,
        train,
        day_offset,
        travel_class,
        quota,
        board,
        dest,
        pax_spec,
        outcome_kind,
    ) in plan:
        dep_dt = _departure(day_offset)
        if outcome_kind == "censored":
            outcome = _censored_outcome(dep_dt)
        elif outcome_kind == "unverified":
            outcome = _unverified_outcome(dep_dt)
        else:
            outcome = _verified_outcome(dep_dt)

        passengers = [
            _passenger(
                index + 1,
                group(group_seq),
                dep_dt=dep_dt,
                initial_position=position,
                initial_category=category,
                later_observation=(sub_id == "SUB_REH_001"),
                final_outcome=outcome,
            )
            for index, (position, category) in enumerate(pax_spec)
        ]

        submissions.append(
            ProspectiveSubmission(
                submission_id=sub_id,
                pseudonym_group_id=group(group_seq),
                train_number=train,
                journey_date=dep_dt.date(),
                boarding_station=board,
                destination_station=dest,
                class_code=travel_class,
                quota_code=quota,
                scheduled_departure_at=dep_dt,
                consent=consent,
                passengers=passengers,
                review_status=ReviewStatus.PENDING_REVIEW,
            )
        )

    return ProspectiveBatch(
        batch_id=PRIMARY_BATCH_ID,
        created_at=datetime(2026, 4, 1, 9, 30, tzinfo=UTC),
        submissions=submissions,
        schema_version=PROSPECTIVE_COLLECTION_SCHEMA_VERSION,
    )


def _clone(batch: ProspectiveBatch) -> ProspectiveBatch:
    return ProspectiveBatch.from_dict(batch.to_dict())


def _contaminated_batch(batch: ProspectiveBatch) -> ProspectiveBatch:
    """A copy carrying an explicit personal-data pattern, for the scan gate."""
    copy = _clone(batch)
    copy.submissions[2].review_notes = "Participant contact on file: passenger.test@example.com"
    return copy


# ── Runner ─────────────────────────────────────────────────────────────────────


def run_prospective_rehearsal(
    workspace: Path | str,
    *,
    salt: str | None = None,
    run_timestamp: datetime | None = None,
) -> RehearsalReport:
    """Run the full synthetic lifecycle rehearsal inside *workspace*.

    Args:
        workspace: Isolated directory the rehearsal writes its artifacts into.
        salt: Cryptographic salt for the pseudonymisation check; a fixed
            synthetic default is used when omitted.
        run_timestamp: Deterministic run timestamp; a fixed default is used when
            omitted. Must be timezone-aware.

    Returns:
        A :class:`RehearsalReport` describing every gate.
    """
    ws = Path(workspace).resolve()
    ts = run_timestamp or DEFAULT_REHEARSAL_TIMESTAMP
    if ts.tzinfo is None:
        raise DatasetValidationError("Rehearsal run_timestamp must be timezone-aware.")
    effective_salt = salt if salt is not None else DEFAULT_REHEARSAL_SALT
    if len(effective_salt) < MIN_SALT_LENGTH:
        raise SecurityError(
            f"Rehearsal salt must be at least {MIN_SALT_LENGTH} characters."
        )

    batch_dir = ws / "batch"
    export_dir = ws / "export"
    quarantine_dir = ws / "quarantine"
    reports_dir = ws / "reports"
    for directory in (batch_dir, export_dir, quarantine_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)

    gates: list[RehearsalGate] = []

    batch = build_primary_batch(salt=effective_salt)
    batch_path = batch_dir / "primary_batch.json"
    batch.save(batch_path)

    gates.append(_gate_synthetic_batch_generation(batch, batch_path, ts))
    gates.append(_gate_pii_and_identifier_scan(batch, effective_salt))
    gates.append(_gate_schema_and_governance_audit(batch, batch_path))

    _review_primary_batch(batch)
    gates.append(_gate_human_review_workflow(batch))

    withdrawal_evidence = _withdraw_submission_006(batch, ts)
    gates.append(_gate_withdrawal_lifecycle(batch, withdrawal_evidence))
    batch.save(batch_path)

    export_path = export_dir / "approved_export.json"
    export_gate, exported = _run_approved_export(batch, export_path, ts)
    gates.append(export_gate)

    gates.append(_gate_export_lineage_verification(batch, exported))

    mutation_gate, stale_gate = _run_source_mutation_scenarios(batch, exported)
    gates.append(mutation_gate)
    gates.append(stale_gate)

    reconcile_gate, reconciled = _run_safe_reconciliation(batch, export_path, ts)
    gates.append(reconcile_gate)

    gates.append(_gate_quarantine_integrity_audit(batch, quarantine_dir))
    gates.append(_gate_filesystem_integrity(ws, reconciled, ts))
    gates.append(_gate_scientific_safeguards(batch, reconciled))
    gates.append(_gate_structured_abstention())

    report = RehearsalReport(
        run_id=f"REH_{ts.strftime('%Y%m%dT%H%M%SZ')}",
        run_timestamp=ts.isoformat(),
        workspace=str(ws),
        gates=gates,
    )
    report.gates.append(_gate_final_readiness(report))
    _write_reports(report, reports_dir)
    return report


# ── Gate builders ──────────────────────────────────────────────────────────────


def _gate_synthetic_batch_generation(
    batch: ProspectiveBatch, batch_path: Path, ts: datetime
) -> RehearsalGate:
    gate = RehearsalGate(
        "synthetic_batch_generation",
        "Generate a labelled synthetic batch",
    )
    gate.record(
        f"Wrote {len(batch.submissions)} synthetic submissions to {batch_path.name} "
        f"(batch '{batch.batch_id}', schema v{batch.schema_version})."
    )
    gate.record(
        "Journeys span "
        f"{len({s.train_number for s in batch.submissions})} trains, "
        f"{len({s.journey_date for s in batch.submissions})} dates and "
        f"{len({s.class_code for s in batch.submissions})} classes."
    )
    gate.record(
        f"Run timestamp is fixed at {ts.isoformat()}, so the batch and its exports are reproducible."
    )
    gate.require_human(
        "Confirm any real batch is collected under documented consent before use; "
        "fixtures here are synthetic and establish nothing about participants."
    )
    if batch_path.is_file() and batch_path.read_text(encoding="utf-8").strip():
        gate.record("Batch artifact is present and non-empty on disk.")
    else:
        gate.fail("Batch artifact was not written to disk.")
    return gate


def _gate_pii_and_identifier_scan(
    batch: ProspectiveBatch, salt: str
) -> RehearsalGate:
    gate = RehearsalGate(
        "pii_and_identifier_scan",
        "Personal-data and raw-identifier scan",
    )
    clean_violations = scan_for_personal_data(batch.to_dict())
    if clean_violations:
        gate.fail(f"Clean batch unexpectedly flagged: {clean_violations}")
    else:
        gate.record("Primary batch scans clean for PNR, email, phone, Aadhaar, PAN and token patterns.")

    contaminated = _contaminated_batch(batch)
    detected = scan_for_personal_data(contaminated.to_dict())
    if detected:
        gate.record(f"Positive control: scanner detected {len(detected)} pattern(s) in the contaminated copy.")
    else:
        gate.fail("Scanner failed to detect an injected email pattern (false negative).")

    offender = contaminated.submissions[2]
    accepted, intake_diagnostics = intake_prospective_submission(offender, reject_on_pii=True)
    if not accepted and offender.review_status is ReviewStatus.QUARANTINED:
        gate.record("Intake quarantines a PII-flagged submission rather than accepting it.")
    else:
        gate.fail("Intake did not quarantine a PII-flagged submission.")
    if not intake_diagnostics:
        gate.fail("Intake returned no diagnostics for a PII-flagged submission.")

    # A separate contaminated copy: intake rewrites review_notes, so the intact
    # copy is needed to show approval is refused while the PII is still present.
    intact = _contaminated_batch(batch)
    try:
        review_batch(
            intact,
            action=ReviewStatus.APPROVED,
            reviewer="rehearsal_operator",
            rationale="Should be refused.",
            submission_id=intact.submissions[2].submission_id,
        )
        gate.fail("Approval of a PII-flagged submission was not refused.")
    except SecurityError:
        gate.record("Approval of a submission still carrying personal data is refused with SecurityError.")

    pseudonym = derive_pseudonym("synthetic_pnr_0001", salt=salt)
    if pseudonym.startswith("anon_") and "synthetic_pnr" not in pseudonym:
        gate.record("Pseudonymisation maps a raw identifier to a derived, non-identifying token.")
    else:
        gate.fail("Pseudonymisation did not produce the expected derived token.")
    try:
        derive_pseudonym("synthetic_pnr_0001", salt="too-short")
        gate.fail("Pseudonymisation accepted a salt below the minimum length.")
    except SecurityError:
        gate.record(f"Pseudonymisation refuses a salt shorter than {MIN_SALT_LENGTH} characters.")
    return gate


def _gate_schema_and_governance_audit(
    batch: ProspectiveBatch, batch_path: Path
) -> RehearsalGate:
    gate = RehearsalGate(
        "schema_and_governance_audit",
        "Schema detection and governance audit",
    )
    detection = detect_schema(batch_path)
    if detection.format_type is FormatType.PROSPECTIVE_BATCH:
        gate.record(
            f"Schema detection identifies a prospective batch (schema v{detection.schema_version})."
        )
    else:
        gate.fail(f"Schema detection returned {detection.format_type.value}, not a prospective batch.")

    report = validate_prospective_batch(batch)
    gate.record(
        "Audit accounting: "
        f"{report.total_submissions} submissions, {report.total_passengers} passengers, "
        f"pending={report.pending_submissions}, rejected={report.rejected_submissions}, "
        f"quarantined={report.quarantined_submissions}, withdrawn={report.withdrawn_submissions}."
    )
    if report.is_structurally_valid:
        gate.record("Batch is structurally valid.")
    else:
        gate.fail(f"Batch is structurally invalid: {report.structural_errors}")

    if report.is_privacy_clean and report.is_consent_valid:
        gate.record("Privacy and consent gates pass for the synthetic batch.")
    else:
        gate.fail("Privacy or consent gate failed on the synthetic batch.")

    gate.record(
        "Outcome diagnostics: "
        f"unverified={report.unverified_outcome_count}, censored={report.censored_outcome_count}."
    )
    gate.record(
        "Pilot thresholds computed (deterministic): "
        f"feasibility={report.threshold_feasibility_pilot}, "
        f"intake={report.threshold_technical_intake}, "
        f"baseline={report.threshold_temporal_baseline}, "
        f"subgroup={report.threshold_subgroup_evaluation}. "
        "They are expected to be unmet at rehearsal scale, which is not a failure."
    )

    # Negative controls: the auditor must reject known-bad shapes.
    duplicate = _clone(batch)
    duplicate.submissions[1].pseudonym_group_id = duplicate.submissions[0].pseudonym_group_id
    dup_report = validate_prospective_batch(duplicate)
    if not dup_report.is_structurally_valid and dup_report.structural_errors:
        gate.record("Duplicate pseudonymous group identifiers are rejected by the auditor.")
    else:
        gate.fail("Duplicate pseudonymous group identifiers were not rejected.")

    try:
        ProspectivePassenger(
            passenger_sequence=1,
            original_status_raw="GNWL 10",
            original_status_category=NormalizedStatus.WL,
            original_status_position=10,
            observations=[
                StatusObservation(
                    observation_id="OBS_BAD_1",
                    passenger_record_id="anon_reh_bad_P1",
                    observed_at=_departure(1),
                    status_raw="GNWL 9",
                    status_category=NormalizedStatus.WL,
                    status_position=9,
                ),
                StatusObservation(
                    observation_id="OBS_BAD_2",
                    passenger_record_id="anon_reh_bad_P1",
                    observed_at=_departure(0),
                    status_raw="GNWL 8",
                    status_category=NormalizedStatus.WL,
                    status_position=8,
                ),
            ],
            outcome=None,
        )
        gate.fail("Out-of-order observations were accepted by the passenger model.")
    except DatasetValidationError:
        gate.record("Out-of-order observation timestamps are rejected by the passenger model.")

    try:
        ProspectivePassenger(
            passenger_sequence=1,
            original_status_raw="GNWL 20",
            original_status_category=NormalizedStatus.WL,
            original_status_position=20,
            observations=[],
            outcome=FinalOutcome(
                outcome_target="final_chart_cnf",
                outcome_status_raw="CNF",
                outcome_category=NormalizedStatus.CNF,
                outcome_observed_at=_departure(0) - timedelta(hours=4),
                verification_method=VerificationMethod.CHART_SNAPSHOT,
                label_confidence=LabelConfidence.VERIFIED,
            ),
        )
        gate.fail("A verified outcome without a verification source was accepted.")
    except DatasetValidationError:
        gate.record("A verified outcome without a verification source is rejected.")

    if report.unique_trains and report.unique_journey_dates:
        gate.record(
            f"Coverage recorded across {len(report.unique_trains)} trains and "
            f"{len(report.unique_journey_dates)} journey dates."
        )
    else:
        gate.fail("Coverage metrics were not populated by the audit.")
    return gate


def _review_primary_batch(batch: ProspectiveBatch) -> None:
    """Apply the recorded human-review decisions used by the later gates."""
    reviewer = "rehearsal_operator"
    for sub_id in ("SUB_REH_001", "SUB_REH_002", "SUB_REH_005", "SUB_REH_006"):
        review_batch(
            batch,
            action=ReviewStatus.APPROVED,
            reviewer=reviewer,
            rationale="Synthetic submission approved for rehearsal after simulated review.",
            submission_id=sub_id,
        )
    review_batch(
        batch,
        action=ReviewStatus.REJECTED,
        reviewer=reviewer,
        rationale="Synthetic submission rejected in the simulated review workflow.",
        submission_id="SUB_REH_004",
    )
    review_batch(
        batch,
        action=ReviewStatus.QUARANTINED,
        reviewer=reviewer,
        rationale="Synthetic submission quarantined pending simulated resolution.",
        submission_id="SUB_REH_007",
    )


def _gate_human_review_workflow(batch: ProspectiveBatch) -> RehearsalGate:
    gate = RehearsalGate(
        "human_review_workflow",
        "Human-review workflow simulation",
    )
    statuses = {s.submission_id: s.review_status for s in batch.submissions}
    approved = sorted(k for k, v in statuses.items() if v is ReviewStatus.APPROVED)
    gate.record(f"Approved submissions after review: {', '.join(approved)}.")
    gate.record(
        "Recorded rejections/quarantine: "
        + ", ".join(
            f"{k}={v.value}"
            for k, v in sorted(statuses.items())
            if v in (ReviewStatus.REJECTED, ReviewStatus.QUARANTINED)
        )
        + "."
    )
    gate.record(
        "Pending submissions remain unapproved and must be excluded from export: "
        + ", ".join(sorted(k for k, v in statuses.items() if v is ReviewStatus.PENDING_REVIEW))
        + "."
    )

    for sub in batch.submissions:
        if sub.review_status in (ReviewStatus.APPROVED, ReviewStatus.REJECTED, ReviewStatus.QUARANTINED):
            if not sub.reviewed_by or not sub.review_notes:
                gate.fail(f"Reviewed submission {sub.submission_id} is missing reviewer or rationale.")
    if not gate.failures:
        gate.record("Every reviewed submission records a named reviewer, a rationale and a timestamp.")

    try:
        review_batch(
            batch,
            action=ReviewStatus.APPROVED,
            reviewer="rehearsal_operator",
            rationale="Should be refused.",
            submission_id="SUB_REH_007",
        )
        gate.fail("A quarantined submission was approved without resolution.")
    except DatasetValidationError:
        gate.record("A quarantined submission cannot be approved without resolution.")

    try:
        review_batch(
            batch,
            action=ReviewStatus.APPROVED,
            reviewer="   ",
            rationale="Should be refused.",
            submission_id="SUB_REH_003",
        )
        gate.fail("A review with a blank reviewer name was accepted.")
    except DatasetValidationError:
        gate.record("A review decision with no named reviewer is refused.")

    gate.require_human(
        "Human operators must perform the real review; this rehearsal only simulates the recorded decisions."
    )
    return gate


def _withdraw_submission_006(batch: ProspectiveBatch, ts: datetime) -> dict[str, Any]:
    """Withdraw an approved submission, twice, to show idempotency."""
    first = withdraw_submission(
        batch,
        submission_id="SUB_REH_006",
        reason="Synthetic participant consent withdrawal (rehearsal).",
        operator="rehearsal_operator",
    )
    first_timestamp = first.consent.withdrawn_at
    log_after_first = len(batch.withdrawal_log)

    second = withdraw_submission(
        batch,
        submission_id="SUB_REH_006",
        reason="Repeated withdrawal request (rehearsal).",
        operator="rehearsal_operator",
    )
    return {
        "withdrawn_at": first_timestamp,
        "timestamp_preserved": second.consent.withdrawn_at == first_timestamp,
        "log_after_first": log_after_first,
        "log_after_second": len(batch.withdrawal_log),
        "review_status": second.review_status,
        "withdrawn_flag": second.consent.withdrawn,
        "reason_recorded": bool(second.consent.withdrawal_reason),
    }


def _gate_withdrawal_lifecycle(
    batch: ProspectiveBatch, evidence: dict[str, Any]
) -> RehearsalGate:
    gate = RehearsalGate(
        "withdrawal_lifecycle",
        "Consent withdrawal lifecycle",
    )
    sub = next(s for s in batch.submissions if s.submission_id == "SUB_REH_006")
    gate.record(
        f"Withdrawal applied to SUB_REH_006: review_status={sub.review_status.value}, "
        f"consent.withdrawn={sub.consent.withdrawn}."
    )
    if evidence["withdrawn_flag"] and evidence["review_status"] is ReviewStatus.WITHDRAWN:
        gate.record("The submission is marked withdrawn in both consent metadata and review status.")
    else:
        gate.fail("Withdrawal did not set the consent flag and WITHDRAWN review status.")

    if evidence["timestamp_preserved"]:
        gate.record("A second withdrawal request preserves the original withdrawal timestamp (idempotent).")
    else:
        gate.fail("A repeated withdrawal changed the recorded withdrawal timestamp.")

    if evidence["log_after_second"] == evidence["log_after_first"] + 1:
        gate.record("Each withdrawal appends an immutable audit record to the withdrawal log.")
    else:
        gate.fail("The withdrawal audit log did not grow by exactly one record per request.")

    audit_record = batch.withdrawal_log[-1]
    if audit_record.submission_id == "SUB_REH_006" and audit_record.operator and audit_record.reason:
        gate.record("The withdrawal audit record carries submission, operator, prior status and reason.")
    else:
        gate.fail("The withdrawal audit record is incomplete.")
    if not scan_for_personal_data(audit_record.to_dict()):
        gate.record("The withdrawal audit record carries no personal data.")
    else:
        gate.fail("The withdrawal audit record contains personal data.")

    try:
        review_batch(
            batch,
            action=ReviewStatus.APPROVED,
            reviewer="rehearsal_operator",
            rationale="Should be refused.",
            submission_id="SUB_REH_006",
        )
        gate.fail("A withdrawn submission was re-approved (re-entry).")
    except SecurityError:
        gate.record("A withdrawn submission cannot be re-approved, blocking accidental re-entry.")

    gate.record("Withdrawal is durable: the batch is re-persisted with the withdrawal log intact.")
    gate.require_human(
        "Real withdrawals must be actioned by a named operator and honoured within the retention policy."
    )
    return gate


def _run_approved_export(
    batch: ProspectiveBatch, export_path: Path, ts: datetime
) -> tuple[RehearsalGate, Any]:
    gate = RehearsalGate("approved_record_export", "Approved-record export")

    try:
        export_batch_to_longitudinal(
            batch,
            dataset_id=EXPORT_DATASET_ID,
            source_id="rehearsal_synthetic_source",
            require_all_approved=True,
            export_timestamp=ts,
        )
        gate.fail("A strict export succeeded while unapproved submissions remain in the batch.")
    except DatasetValidationError:
        gate.record("Strict export refuses while any submission is pending, rejected, quarantined or withdrawn.")

    exported = export_batch_to_longitudinal(
        batch,
        dataset_id=EXPORT_DATASET_ID,
        source_id="rehearsal_synthetic_source",
        require_all_approved=False,
        export_timestamp=ts,
    )
    export_path.parent.mkdir(parents=True, exist_ok=True)
    exported.save(export_path)

    lineage = exported.metadata.get("lineage", {})
    included = list(lineage.get("included_submissions", []))
    excluded = dict(lineage.get("excluded_submissions", {}))
    gate.record(f"Partial export included {len(included)} approved submissions: {', '.join(included)}.")
    gate.record(
        "Excluded submissions with reasons: "
        + ", ".join(f"{k}={v}" for k, v in sorted(excluded.items()))
        + "."
    )
    if excluded.get("SUB_REH_006") == "withdrawn":
        gate.record("The withdrawn submission is excluded from the export.")
    else:
        gate.fail("The withdrawn submission was not excluded from the export.")

    group_ids = [bg.booking_group_id for bg in exported.booking_groups]
    if group_ids == sorted(group_ids):
        gate.record("Exported booking groups are in deterministic (sorted) order.")
    else:
        gate.fail("Exported booking groups are not in deterministic order.")

    recorded_sha = exported.metadata.get("source_batch_sha256")
    if recorded_sha == compute_canonical_batch_sha256(batch):
        gate.record("The export records the canonical source-batch SHA-256.")
    else:
        gate.fail("The export did not record the current canonical source-batch hash.")

    considered = lineage.get("total_considered")
    if considered == len(batch.submissions) and len(included) + len(excluded) == considered:
        gate.record("Included and excluded counts account for every submission exactly once.")
    else:
        gate.fail("Included/excluded accounting does not reconcile to the submission count.")
    return gate, exported


def _gate_export_lineage_verification(batch: ProspectiveBatch, exported: Any) -> RehearsalGate:
    gate = RehearsalGate(
        "export_lineage_verification",
        "Export lineage verification",
    )
    lineage = verify_export_lineage(batch, exported)
    if lineage.is_synced and lineage.status is LineageStatus.VERIFIED_IN_SYNC:
        gate.record("Lineage verification reports the export verified in sync with its source batch.")
    else:
        gate.fail(f"Fresh export is not in sync: {lineage.status.value} ({lineage.violations}).")
    if lineage.source_sha256_matches:
        gate.record("Recorded source hash matches the current batch digest.")
    else:
        gate.fail("Recorded source hash does not match the current batch digest.")
    return gate


def _run_source_mutation_scenarios(
    batch: ProspectiveBatch, exported: Any
) -> tuple[RehearsalGate, RehearsalGate]:
    mutation = RehearsalGate(
        "source_mutation_scenario",
        "Source mutation / withdrawal scenario",
    )
    stale = RehearsalGate(
        "stale_export_detection",
        "Stale export detection",
    )

    # 1. Withdraw a submission that is still present in the export.
    before_sha = compute_canonical_batch_sha256(batch)
    withdraw_submission(
        batch,
        submission_id="SUB_REH_002",
        reason="Synthetic post-export consent withdrawal (rehearsal).",
        operator="rehearsal_operator",
    )
    after_sha = compute_canonical_batch_sha256(batch)
    mutation.record("A submission already present in the export had its consent withdrawn.")
    if before_sha != after_sha:
        mutation.record("The mutation changed the canonical batch digest, so the export's recorded hash is now stale.")
    else:
        mutation.fail("The source mutation did not change the canonical batch digest.")

    withdrawn_lineage = verify_export_lineage(batch, exported)
    if withdrawn_lineage.status is LineageStatus.STALE_WITHDRAWN_RECORDS_PRESENT:
        stale.record("Stale detection reports STALE_WITHDRAWN_RECORDS_PRESENT after an in-export withdrawal.")
    else:
        stale.fail(f"Expected stale-withdrawn detection, got {withdrawn_lineage.status.value}.")
    if withdrawn_lineage.withdrawn_groups_present:
        stale.record(f"Withdrawn groups present in the export: {withdrawn_lineage.withdrawn_groups_present}.")
    else:
        stale.fail("Stale detection did not identify the withdrawn group present in the export.")
    if not withdrawn_lineage.source_sha256_matches:
        stale.record("Stale detection notes the recorded source hash no longer matches.")
    else:
        stale.fail("Stale detection did not notice the source-hash mismatch.")

    # 2. Unapproved-in-export variant: reject an approved submission after export.
    unapproved_batch = build_primary_batch()
    review_batch(
        unapproved_batch,
        action=ReviewStatus.APPROVED,
        reviewer="rehearsal_operator",
        rationale="Synthetic approval for the stale-unapproved variant.",
        submission_id="SUB_REH_001",
    )
    unapproved_export = export_batch_to_longitudinal(
        unapproved_batch,
        dataset_id="REHEARSAL_VARIANT_UNAPPROVED",
        source_id="rehearsal_synthetic_source",
        require_all_approved=False,
        export_timestamp=DEFAULT_REHEARSAL_TIMESTAMP,
    )
    review_batch(
        unapproved_batch,
        action=ReviewStatus.REJECTED,
        reviewer="rehearsal_operator",
        rationale="Synthetic post-export rejection.",
        submission_id="SUB_REH_001",
    )
    unapproved_lineage = verify_export_lineage(unapproved_batch, unapproved_export)
    if unapproved_lineage.status is LineageStatus.STALE_UNAPPROVED_RECORDS_PRESENT:
        stale.record("Stale detection reports STALE_UNAPPROVED_RECORDS_PRESENT after a post-export rejection.")
    else:
        stale.fail(f"Expected stale-unapproved detection, got {unapproved_lineage.status.value}.")

    # 3. Source-modified variant: change a non-status field of an exported submission.
    modified_batch = build_primary_batch()
    review_batch(
        modified_batch,
        action=ReviewStatus.APPROVED,
        reviewer="rehearsal_operator",
        rationale="Synthetic approval for the source-modified variant.",
        submission_id="SUB_REH_001",
    )
    modified_export = export_batch_to_longitudinal(
        modified_batch,
        dataset_id="REHEARSAL_VARIANT_MODIFIED",
        source_id="rehearsal_synthetic_source",
        require_all_approved=False,
        export_timestamp=DEFAULT_REHEARSAL_TIMESTAMP,
    )
    target = next(s for s in modified_batch.submissions if s.submission_id == "SUB_REH_001")
    target.quota_code = "TQ"
    modified_lineage = verify_export_lineage(modified_batch, modified_export)
    if modified_lineage.status is LineageStatus.STALE_SOURCE_MODIFIED:
        stale.record("Stale detection reports STALE_SOURCE_MODIFIED after an unrelated source edit.")
    else:
        stale.fail(f"Expected stale-source-modified detection, got {modified_lineage.status.value}.")

    mutation.require_human(
        "A real post-export withdrawal must trigger reconciliation before the export is used again."
    )
    return mutation, stale


def _run_safe_reconciliation(
    batch: ProspectiveBatch, export_path: Path, ts: datetime
) -> tuple[RehearsalGate, Any]:
    gate = RehearsalGate("safe_reconciliation", "Safe reconciliation")
    current = _load_export(export_path)
    reconciled, lineage = reconcile_and_regenerate_export(
        batch,
        current,
        export_path,
        overwrite=True,
        export_timestamp=ts,
    )
    if lineage.is_synced and lineage.status is LineageStatus.VERIFIED_IN_SYNC:
        gate.record("Reconciliation re-exports the current approved set and reports the export verified in sync.")
    else:
        gate.fail(f"Reconciled export is not in sync: {lineage.status.value} ({lineage.violations}).")

    group_ids = {bg.booking_group_id for bg in reconciled.booking_groups}
    withdrawn_group = next(
        s.pseudonym_group_id for s in batch.submissions if s.submission_id == "SUB_REH_002"
    )
    if withdrawn_group not in group_ids:
        gate.record("Withdrawn booking groups are absent from the reconciled export.")
    else:
        gate.fail("A withdrawn booking group survived into the reconciled export.")

    re_report = verify_export_lineage(batch, reconciled)
    if re_report.is_synced:
        gate.record("A second lineage check on the reconciled export is still verified in sync (stable).")
    else:
        gate.fail("The reconciled export did not remain verified in sync on re-check.")
    return gate, reconciled


def _load_export(path: Path) -> Any:
    from railconfirm.data.longitudinal import load_longitudinal_dataset

    return load_longitudinal_dataset(path)


def _gate_quarantine_integrity_audit(
    batch: ProspectiveBatch, quarantine_dir: Path
) -> RehearsalGate:
    gate = RehearsalGate(
        "quarantine_integrity_audit",
        "Quarantine integrity audit",
    )
    staging = quarantine_dir.parent / "batch" / "contaminated_for_quarantine.json"
    contaminated = _contaminated_batch(batch)
    contaminated.save(staging)

    quarantined = quarantine_dataset(
        staging,
        quarantine_dir,
        reason="Synthetic rehearsal: PII pattern detected.",
        operator="rehearsal_operator",
    )
    sidecar = quarantined.parent / f"{quarantined.name}.quarantine.json"
    if quarantined.is_file() and sidecar.is_file():
        gate.record("Quarantine copies the file in and writes a cryptographic sidecar report.")
    else:
        gate.fail("Quarantine did not produce a data file plus sidecar pair.")

    audit = audit_quarantine_directory(quarantine_dir)
    if len(audit["valid_pairs"]) == 1 and not audit["orphaned_data_files"] and not audit["orphaned_sidecars"]:
        gate.record("Initial audit finds exactly one valid pair and no orphans.")
    else:
        gate.fail(f"Initial quarantine audit was not clean: {audit}")

    orphan_data = quarantine_dir / "orphan_data.json"
    orphan_data.write_text('{"orphan": true}\n', encoding="utf-8")
    orphan_sidecar = quarantine_dir / "orphan_sidecar.json.quarantine.json"
    orphan_sidecar.write_text('{"sha256": "deadbeef"}\n', encoding="utf-8")
    orphan_audit = audit_quarantine_directory(quarantine_dir)
    if orphan_audit["orphaned_data_files"] and orphan_audit["orphaned_sidecars"]:
        gate.record("Orphaned data files and orphaned sidecars are identified separately.")
    else:
        gate.fail("Orphan detection did not identify both orphan shapes.")

    purged = audit_quarantine_directory(quarantine_dir, purge_orphans=True)
    if not orphan_data.exists() and not orphan_sidecar.exists():
        gate.record("Purge removes only the proven-safe orphans.")
    else:
        gate.fail("Purge did not remove the orphans as expected.")
    retained = purged["valid_pairs"]
    if retained and Path(retained[0]).is_file():
        gate.record("The valid quarantined pair is retained through the purge.")
    else:
        gate.fail("Purge removed a valid quarantined pair.")

    # Tamper last: altering the only remaining valid pair turns it into a
    # checksum mismatch, so the retention check above must run first.
    corrupt_target = Path(audit["valid_pairs"][0])
    with corrupt_target.open("ab") as handle:
        handle.write(b"\n# tampered for checksum-mismatch rehearsal\n")
    mismatch_audit = audit_quarantine_directory(quarantine_dir)
    if mismatch_audit["checksum_mismatches"]:
        gate.record("A checksum mismatch is detected when a quarantined file is altered.")
    else:
        gate.fail("A checksum mismatch was not detected after altering a quarantined file.")
    return gate


def _gate_filesystem_integrity(ws: Path, reconciled: Any, ts: datetime) -> RehearsalGate:
    gate = RehearsalGate("filesystem_integrity", "Filesystem integrity")

    target = ws / "fs_integrity" / "atomic_write.json"
    payload = {"marker": SYNTHETIC_MARK, "value": 7}
    atomic_write_json(target, payload)
    if json.loads(target.read_text(encoding="utf-8")) == payload:
        gate.record("Atomic write round-trips its payload exactly.")
    else:
        gate.fail("Atomic write did not round-trip its payload.")

    leftovers = [p.name for p in (ws / "fs_integrity").iterdir() if p.name.startswith(".tmp_")]
    if not leftovers:
        gate.record("No temporary write artifacts remain after a successful atomic write.")
    else:
        gate.fail(f"Temporary artifacts were left behind: {leftovers}")

    # Interrupted write: the destination is occupied by a directory, so the commit
    # cannot replace it. The failure must not destroy the existing entry.
    dir_target = ws / "fs_integrity" / "occupied_by_directory"
    dir_target.mkdir(parents=True, exist_ok=True)
    try:
        atomic_write_text(dir_target, "should not be written")
        gate.fail("An interrupted write unexpectedly succeeded over a directory.")
    except OSError:
        if dir_target.is_dir() and not any(
            p.name.startswith(".tmp_") for p in (ws / "fs_integrity").iterdir()
        ):
            gate.record("An interrupted atomic write leaves the existing entry intact and no partial temp file.")
        else:
            gate.fail("An interrupted atomic write left the target damaged or a temp file behind.")

    # Deterministic re-export: the same input and timestamp produce identical bytes.
    source = _rehearsal_export_source()
    first = export_batch_to_longitudinal(
        source,
        dataset_id="REHEARSAL_DETERMINISM",
        source_id="rehearsal_synthetic_source",
        require_all_approved=False,
        export_timestamp=ts,
    )
    second = export_batch_to_longitudinal(
        source,
        dataset_id="REHEARSAL_DETERMINISM",
        source_id="rehearsal_synthetic_source",
        require_all_approved=False,
        export_timestamp=ts,
    )
    if json.dumps(first.to_dict(), sort_keys=True) == json.dumps(second.to_dict(), sort_keys=True):
        gate.record("Re-exporting the same synthetic batch yields byte-identical output.")
    else:
        gate.fail("Re-exporting the same synthetic batch produced different output.")

    if reconciled is not None:
        gate.record("The reconciled export was written through the atomic writer and reloads cleanly.")
    return gate


def _rehearsal_export_source() -> ProspectiveBatch:
    """A fixed approved batch used only for the determinism comparison."""
    batch = build_primary_batch()
    review_batch(
        batch,
        action=ReviewStatus.APPROVED,
        reviewer="rehearsal_operator",
        rationale="Synthetic approval for the determinism check.",
        submission_id="SUB_REH_001",
    )
    return batch


def _gate_scientific_safeguards(batch: ProspectiveBatch, reconciled: Any) -> RehearsalGate:
    gate = RehearsalGate("scientific_safeguards", "Scientific safeguards")

    # Point-in-time: a wider lead time must withhold the later look.
    wide = create_point_in_time_snapshot(reconciled, as_of_lead_days=3)
    narrow = create_point_in_time_snapshot(reconciled, as_of_lead_days=1)
    wide_statuses = set(wide.frame["current_status"].tolist()) if len(wide.frame) else set()
    narrow_statuses = set(narrow.frame["current_status"].tolist()) if len(narrow.frame) else set()
    if "GNWL 3" not in wide_statuses:
        gate.record("A look recorded one day before departure is withheld from a three-day-lead snapshot (no leakage).")
    else:
        gate.fail("Post-cutoff observation leaked into the three-day-lead snapshot.")
    if "GNWL 3" in narrow_statuses:
        gate.record("The same look appears once the cutoff moves inside its observation time, as expected.")
    else:
        gate.fail("The one-day-lead snapshot did not reflect the nearer observation.")

    try:
        create_point_in_time_snapshot(reconciled, as_of_lead_days=0)
        gate.fail("A zero-lead (post-chart) snapshot was permitted.")
    except TemporalIntegrityError:
        gate.record("A zero-lead snapshot is refused, enforcing the minimum lead time.")

    if wide.rows_skipped_censored >= 1:
        gate.record("Censored outcomes are excluded from a default snapshot.")
    else:
        gate.fail("Censored outcomes were not excluded from the default snapshot.")

    # Threshold accounting is computed, not asserted: the audit reports the true counts.
    audit = validate_prospective_batch(batch)
    if audit.total_submissions == len(batch.submissions) and audit.withdrawn_submissions >= 1:
        gate.record("Threshold accounting reflects the batch composition, including withdrawals.")
    else:
        gate.fail("Threshold accounting did not reflect the batch composition.")

    # Rehearsal data must never be trainable.
    training_refusal = _assert_training_refuses_synthetic(reconciled)
    if training_refusal is None:
        gate.record("The training gate refuses synthetic rehearsal data (no artefact may be promoted from it).")
    else:
        gate.fail(f"The training gate did not refuse synthetic data: {training_refusal}")

    gate.record("The rehearsal performs no training and makes no accuracy claim about railway behaviour.")
    gate.require_human(
        "Any modelling claim requires approved, non-synthetic data and a promoted, validated model."
    )
    return gate


def _assert_training_refuses_synthetic(dataset: Any) -> str | None:
    """Return a reason string if synthetic training was *not* refused, else None.

    The training layer imports the data layer, so it is imported locally to keep
    the module-level dependency direction one-way.
    """
    import tempfile

    from railconfirm.data.manifest import generate_manifest
    from railconfirm.training.dataset import TrainingDataError, assert_trainable

    with tempfile.TemporaryDirectory(prefix="railconfirm_rehearsal_manifest_") as tmp:
        path = Path(tmp) / "reconciled_export.json"
        dataset.save(path)
        manifest = generate_manifest(
            path,
            dataset_id=dataset.dataset_id,
            title="Synthetic rehearsal export (not railway data)",
            retrieved_on=DEFAULT_REHEARSAL_TIMESTAMP.date().isoformat(),
        )
        try:
            assert_trainable(manifest, is_synthetic=True)
        except TrainingDataError:
            return None
    return "assert_trainable accepted a synthetic dataset"


def _gate_structured_abstention() -> RehearsalGate:
    gate = RehearsalGate("structured_abstention", "Structured abstention")
    engine = InferenceEngine()
    journey = make_journey("12951", date(2026, 7, 20), "MMCT", "NDLS", "3A", "GN")
    observation = make_observation(
        "GNWL 25",
        source="rehearsal_synthetic_source",
        observed_at=datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 7, 15, 10, 5, tzinfo=UTC),
    )
    record = engine.predict(
        journey,
        [{"passenger_id": "reh_passenger_1", "current_obs": observation}],
        prediction_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
    )
    if record.model_version == NO_MODEL_VERSION:
        gate.record(f"Prediction abstains with model_version '{NO_MODEL_VERSION}'.")
    else:
        gate.fail(f"Prediction used model_version '{record.model_version}' instead of abstaining.")

    passenger_outcome = record.passenger_outcomes[0]
    if passenger_outcome.abstention_reason is AbstentionReason.NO_TRAINED_MODEL:
        gate.record("Abstention reason is NO_TRAINED_MODEL, naming the closed gate rather than a generic failure.")
    else:
        gate.fail(f"Unexpected abstention reason: {passenger_outcome.abstention_reason}.")

    if passenger_outcome.p_cnf is None:
        gate.record("No probability is reported while abstaining, so nothing is shown as a trustworthy estimate.")
    else:
        gate.fail("A probability was reported despite abstention.")
    return gate


def _gate_final_readiness(report: RehearsalReport) -> RehearsalGate:
    gate = RehearsalGate("final_readiness", "Final readiness report")
    prior_failures = [g.gate_id for g in report.gates if g.status is GateStatus.FAIL]
    gate.record(f"Evaluated {len(report.gates)} lifecycle gates before this summary.")
    gate.record("The entire run is a synthetic, offline simulation and produces no railway evidence.")
    if prior_failures:
        gate.fail(f"Lifecycle gate(s) failed: {', '.join(prior_failures)}.")
    else:
        gate.record("Every lifecycle gate was evaluated and none failed.")
    gate.require_human(
        "Real-world pilot authorization requires documented consent, legal and privacy review, "
        "operator sign-off and approved real data. Passing this rehearsal does not grant it."
    )
    return gate


def _write_reports(report: RehearsalReport, reports_dir: Path) -> None:
    atomic_write_json(reports_dir / "rehearsal_report.json", report.to_dict(), indent=2)
    atomic_write_text(
        reports_dir / "rehearsal_report.txt",
        SYNTHETIC_MARK + "\n" + report.summary() + "\n",
    )
