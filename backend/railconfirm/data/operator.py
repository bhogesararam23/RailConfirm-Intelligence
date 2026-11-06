"""Local operator service layer for prospective data lifecycle management.

This module provides a typed, local-only service interface for inspecting,
reviewing, withdrawing, exporting, and reconciling prospective batches and
running lifecycle rehearsals. It orchestrates the existing domain and data
primitives without duplicating their business rules.

Guarantees:
- Local-first & offline: no external network calls or third-party providers.
- Privacy-preserving: no raw PNRs, names, phone numbers or credentials.
- Fail-closed: strict validation of actions, reviewers, and rationales.
- Atomic I/O: updates are written crash-safely.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from railconfirm.data.longitudinal import (
    load_longitudinal_dataset,
)
from railconfirm.data.prospective import (
    ProspectiveBatch,
    ReviewStatus,
    compute_canonical_batch_sha256,
    export_batch_to_longitudinal,
    reconcile_and_regenerate_export,
    review_batch,
    scan_for_personal_data,
    validate_prospective_batch,
    verify_export_lineage,
    withdraw_submission,
)
from railconfirm.data.rehearsal import (
    DEFAULT_REHEARSAL_SALT,
    RehearsalReport,
    build_primary_batch,
    run_prospective_rehearsal,
)
from railconfirm.domain.exceptions import DatasetValidationError, SecurityError


@dataclass
class BatchSummary:
    """High-level summary of a prospective batch."""

    batch_id: str
    file_path: str
    schema_version: str
    created_at: str
    total_submissions: int
    approved_count: int
    rejected_count: int
    quarantined_count: int
    pending_count: int
    withdrawn_count: int
    canonical_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchInspectionResult:
    """Detailed inspection of a prospective batch with governance and PII audit."""

    summary: BatchSummary
    pii_scan: dict[str, Any]
    audit_report: dict[str, Any]
    submissions: list[dict[str, Any]]
    withdrawal_log: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "pii_scan": self.pii_scan,
            "audit_report": self.audit_report,
            "submissions": self.submissions,
            "withdrawal_log": self.withdrawal_log,
        }


@dataclass
class ReviewSubmissionResult:
    """Result of reviewing a prospective submission."""

    submission_id: str
    action: str
    reviewer: str
    reviewed_at: str
    rationale: str
    batch_sha256: str
    batch_summary: BatchSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "action": self.action,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
            "rationale": self.rationale,
            "batch_sha256": self.batch_sha256,
            "batch_summary": self.batch_summary.to_dict(),
        }


@dataclass
class WithdrawSubmissionResult:
    """Result of withdrawing a prospective submission."""

    submission_id: str
    operator: str
    reason: str
    withdrawn_at: str
    batch_sha256: str
    audit_record: dict[str, Any]
    batch_summary: BatchSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "operator": self.operator,
            "reason": self.reason,
            "withdrawn_at": self.withdrawn_at,
            "batch_sha256": self.batch_sha256,
            "audit_record": self.audit_record,
            "batch_summary": self.batch_summary.to_dict(),
        }


@dataclass
class ExportPreviewResult:
    """Preview of longitudinal export before persistence."""

    batch_id: str
    total_considered: int
    approved_count: int
    excluded_count: int
    booking_groups_count: int
    passenger_reservations_count: int
    preview_booking_groups: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExportExecutionResult:
    """Result of executing an export to longitudinal dataset."""

    batch_id: str
    dataset_id: str
    export_path: str
    source_batch_sha256: str
    booking_groups_count: int
    passenger_reservations_count: int
    lineage_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LineageInspectionResult:
    """Lineage verification status between source batch and export."""

    batch_id: str
    export_path: str
    is_synced: bool
    status: str
    source_sha256_matches: bool
    recorded_source_sha256: str
    current_source_sha256: str
    withdrawn_groups_present: list[str]
    unapproved_groups_present: list[str]
    new_approved_groups_missing: list[str]
    violations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReconcileExecutionResult:
    """Result of safely reconciling an export after source modifications."""

    batch_id: str
    export_path: str
    reconciled_booking_groups: int
    lineage: LineageInspectionResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "export_path": self.export_path,
            "reconciled_booking_groups": self.reconciled_booking_groups,
            "lineage": self.lineage.to_dict(),
        }


class OperatorWorkspace:
    """Filesystem manager for local operator prospective artifacts."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root = Path(root_dir).resolve()
        self.batches_dir = self.root / "batches"
        self.exports_dir = self.root / "exports"
        self.quarantine_dir = self.root / "quarantine"
        self.rehearsals_dir = self.root / "rehearsals"

    def initialize(self) -> None:
        """Ensure all required subdirectories exist."""
        for d in (self.batches_dir, self.exports_dir, self.quarantine_dir, self.rehearsals_dir):
            d.mkdir(parents=True, exist_ok=True)

    def list_batch_files(self) -> list[Path]:
        """Find all prospective batch JSON files in the workspace."""
        if not self.batches_dir.is_dir():
            return []
        return sorted(
            [p for p in self.batches_dir.glob("*.json") if not p.name.startswith(".tmp_")],
            key=lambda p: p.name,
        )

    def get_batch_path(self, batch_id: str) -> Path:
        """Resolve path for a batch by identifier or filename."""
        clean_id = batch_id.strip()
        if not clean_id or "/" in clean_id or "\\" in clean_id or clean_id.startswith("."):
            raise DatasetValidationError(f"Invalid batch identifier format: '{batch_id}'.")
        # Try direct id as filename, or filename with .json, or match by batch_id content
        direct = self.batches_dir / f"{clean_id}.json"
        if direct.is_file():
            return direct
        named = self.batches_dir / clean_id
        if named.is_file() and named.suffix == ".json":
            return named
        for path in self.list_batch_files():
            try:
                batch = ProspectiveBatch.load(path)
                if batch.batch_id == clean_id:
                    return path
            except Exception:
                continue
        raise DatasetValidationError(f"Prospective batch '{clean_id}' not found in workspace.")

    def get_export_path(self, batch_id: str) -> Path:
        """Resolve default export path for a batch."""
        clean_id = batch_id.strip()
        return self.exports_dir / f"export_{clean_id}.json"


class OperatorService:
    """Local-first operator service orchestrating data governance operations."""

    def __init__(self, workspace: OperatorWorkspace) -> None:
        self.workspace = workspace
        self.workspace.initialize()

    @classmethod
    def from_directory(cls, directory: Path | str) -> OperatorService:
        return cls(OperatorWorkspace(directory))

    def get_status(self) -> dict[str, Any]:
        """Return workspace overview: counts, storage locations, and readiness."""
        batch_files = self.workspace.list_batch_files()
        batches = [self._summarize_batch(ProspectiveBatch.load(p), p) for p in batch_files]
        latest_rehearsal = self.get_latest_rehearsal()
        return {
            "operator_enabled": True,
            "workspace_root": str(self.workspace.root),
            "batches_count": len(batches),
            "total_submissions": sum(b.total_submissions for b in batches),
            "total_pending_review": sum(b.pending_count for b in batches),
            "total_approved": sum(b.approved_count for b in batches),
            "total_withdrawn": sum(b.withdrawn_count for b in batches),
            "latest_rehearsal_passed": (
                latest_rehearsal.get("software_rehearsal_passed") if latest_rehearsal else None
            ),
            "is_synthetic_environment": True,
        }

    def seed_synthetic_fixture(
        self, batch_id: str = "SYNTHETIC_BATCH_001", *, salt: str = DEFAULT_REHEARSAL_SALT
    ) -> BatchSummary:
        """Seed a clean synthetic batch fixture into the operator workspace."""
        batch = build_primary_batch(salt=salt)
        batch.batch_id = batch_id
        path = self.workspace.batches_dir / f"{batch_id}.json"
        batch.save(path)
        return self._summarize_batch(batch, path)

    def list_batches(self) -> list[BatchSummary]:
        """List summaries of all available batches in the workspace."""
        summaries: list[BatchSummary] = []
        for path in self.workspace.list_batch_files():
            try:
                batch = ProspectiveBatch.load(path)
                summaries.append(self._summarize_batch(batch, path))
            except Exception:
                continue
        return summaries

    def inspect_batch(self, batch_id: str) -> BatchInspectionResult:
        """Inspect a prospective batch, running validation and PII scan."""
        path = self.workspace.get_batch_path(batch_id)
        batch = ProspectiveBatch.load(path)
        summary = self._summarize_batch(batch, path)

        # 1. PII Scan across all text fields
        pii_findings: list[str] = []
        for s in batch.submissions:
            if s.review_notes:
                for found in scan_for_personal_data(s.review_notes):
                    pii_findings.append(f"Submission {s.submission_id}: {found}")

        pii_scan = {
            "passed": len(pii_findings) == 0,
            "findings_count": len(pii_findings),
            "findings": pii_findings,
        }

        # 2. Schema and scientific audit
        audit_report_obj = validate_prospective_batch(batch)
        audit_report = {
            "batch_id": audit_report_obj.batch_id,
            "total_submissions": audit_report_obj.total_submissions,
            "total_passengers": audit_report_obj.total_passengers,
            "unique_trains": sorted(audit_report_obj.unique_trains),
            "unique_journey_dates": sorted(audit_report_obj.unique_journey_dates),
            "class_distribution": dict(audit_report_obj.class_distribution),
            "quota_distribution": dict(audit_report_obj.quota_distribution),
            "quality_warnings": list(audit_report_obj.quality_warnings),
            "structural_errors": list(audit_report_obj.structural_errors),
            "is_technically_eligible": audit_report_obj.is_technically_eligible,
            "is_scientifically_adequate": audit_report_obj.is_scientifically_adequate,
            "is_model_training_approved": audit_report_obj.is_model_training_approved,
        }

        # 3. Submissions serialized safely
        submissions_dict: list[dict[str, Any]] = [s.to_dict() for s in batch.submissions]
        withdrawal_log_dict: list[dict[str, Any]] = [w.to_dict() for w in batch.withdrawal_log]

        return BatchInspectionResult(
            summary=summary,
            pii_scan=pii_scan,
            audit_report=audit_report,
            submissions=submissions_dict,
            withdrawal_log=withdrawal_log_dict,
        )

    def review_submission(
        self,
        batch_id: str,
        *,
        submission_id: str,
        action: str,
        reviewer: str,
        rationale: str,
    ) -> ReviewSubmissionResult:
        """Record an operator review decision for a single submission."""
        path = self.workspace.get_batch_path(batch_id)
        batch = ProspectiveBatch.load(path)

        clean_sub_id = submission_id.strip()
        target_sub = next((s for s in batch.submissions if s.submission_id == clean_sub_id), None)
        if target_sub is None:
            raise DatasetValidationError(
                f"Submission '{clean_sub_id}' not found in batch '{batch_id}'."
            )

        clean_reviewer = reviewer.strip()
        if not clean_reviewer:
            raise DatasetValidationError("Reviewer identifier is required.")

        clean_rationale = rationale.strip()
        if not clean_rationale:
            raise DatasetValidationError("Review rationale is required.")

        try:
            review_action = ReviewStatus(action.lower().strip())
        except ValueError as exc:
            raise DatasetValidationError(
                f"Invalid review action: '{action}'. Permitted actions: {[s.value for s in ReviewStatus]}"
            ) from exc

        # If action is approved, ensure notes carry no PII before saving
        if review_action is ReviewStatus.APPROVED:
            for text_val in (clean_rationale, target_sub.review_notes):
                if text_val:
                    pii = scan_for_personal_data(text_val)
                    if pii:
                        raise SecurityError(
                            f"Cannot approve submission: personal data detected: {pii}"
                        )

        # Apply domain review
        review_batch(
            batch,
            action=review_action,
            reviewer=clean_reviewer,
            rationale=clean_rationale,
            submission_id=clean_sub_id,
        )
        batch.save(path)

        now_iso = datetime.now(tz=UTC).isoformat()
        return ReviewSubmissionResult(
            submission_id=clean_sub_id,
            action=review_action.value,
            reviewer=clean_reviewer,
            reviewed_at=now_iso,
            rationale=clean_rationale,
            batch_sha256=compute_canonical_batch_sha256(batch),
            batch_summary=self._summarize_batch(batch, path),
        )

    def withdraw_submission(
        self,
        batch_id: str,
        *,
        submission_id: str,
        reason: str,
        operator: str,
    ) -> WithdrawSubmissionResult:
        """Record a participant consent withdrawal."""
        path = self.workspace.get_batch_path(batch_id)
        batch = ProspectiveBatch.load(path)

        clean_sub_id = submission_id.strip()
        target_sub = next((s for s in batch.submissions if s.submission_id == clean_sub_id), None)
        if target_sub is None:
            raise DatasetValidationError(
                f"Submission '{clean_sub_id}' not found in batch '{batch_id}'."
            )

        clean_op = operator.strip()
        if not clean_op:
            raise DatasetValidationError("Operator identifier is required.")

        clean_reason = reason.strip()
        if not clean_reason:
            raise DatasetValidationError("Withdrawal reason is required.")

        withdraw_submission(
            batch,
            submission_id=clean_sub_id,
            reason=clean_reason,
            operator=clean_op,
        )
        batch.save(path)

        latest_record = batch.withdrawal_log[-1] if batch.withdrawal_log else None
        record_dict = latest_record.to_dict() if latest_record else {}

        return WithdrawSubmissionResult(
            submission_id=clean_sub_id,
            operator=clean_op,
            reason=clean_reason,
            withdrawn_at=datetime.now(tz=UTC).isoformat(),
            batch_sha256=compute_canonical_batch_sha256(batch),
            audit_record=record_dict,
            batch_summary=self._summarize_batch(batch, path),
        )

    def preview_export(self, batch_id: str) -> ExportPreviewResult:
        """Preview longitudinal export without writing to disk."""
        path = self.workspace.get_batch_path(batch_id)
        batch = ProspectiveBatch.load(path)

        # Generate in-memory longitudinal dataset
        dataset = export_batch_to_longitudinal(
            batch,
            dataset_id=f"PREVIEW_{batch.batch_id}",
            source_id="operator_preview",
            require_all_approved=False,
            export_timestamp=datetime.now(tz=UTC),
        )

        total_passengers = sum(len(bg.passengers) for bg in dataset.booking_groups)
        preview_groups: list[dict[str, Any]] = [
            bg.to_dict() for bg in dataset.booking_groups[:10]
        ]

        approved_count = sum(
            1 for s in batch.submissions if s.review_status is ReviewStatus.APPROVED
        )
        excluded_count = len(batch.submissions) - approved_count

        return ExportPreviewResult(
            batch_id=batch.batch_id,
            total_considered=len(batch.submissions),
            approved_count=approved_count,
            excluded_count=excluded_count,
            booking_groups_count=len(dataset.booking_groups),
            passenger_reservations_count=total_passengers,
            preview_booking_groups=preview_groups,
        )

    def execute_export(
        self,
        batch_id: str,
        *,
        dataset_id: str | None = None,
        source_id: str | None = None,
    ) -> ExportExecutionResult:
        """Atomically export approved submissions to a longitudinal dataset."""
        path = self.workspace.get_batch_path(batch_id)
        batch = ProspectiveBatch.load(path)

        export_path = self.workspace.get_export_path(batch.batch_id)
        effective_dataset_id = dataset_id or f"EXPORT_{batch.batch_id}"
        effective_source_id = source_id or f"operator_batch_{batch.batch_id}"

        dataset = export_batch_to_longitudinal(
            batch,
            dataset_id=effective_dataset_id,
            source_id=effective_source_id,
            require_all_approved=False,
            export_timestamp=datetime.now(tz=UTC),
        )
        dataset.save(export_path)

        lineage = verify_export_lineage(batch, dataset)
        total_passengers = sum(len(bg.passengers) for bg in dataset.booking_groups)

        return ExportExecutionResult(
            batch_id=batch.batch_id,
            dataset_id=effective_dataset_id,
            export_path=str(export_path),
            source_batch_sha256=compute_canonical_batch_sha256(batch),
            booking_groups_count=len(dataset.booking_groups),
            passenger_reservations_count=total_passengers,
            lineage_status=lineage.status.value,
        )

    def inspect_lineage(
        self, batch_id: str, export_path: Path | str | None = None
    ) -> LineageInspectionResult:
        """Verify export lineage against the current source batch."""
        path = self.workspace.get_batch_path(batch_id)
        batch = ProspectiveBatch.load(path)

        resolved_export = (
            Path(export_path).resolve()
            if export_path
            else self.workspace.get_export_path(batch.batch_id)
        )
        if not resolved_export.is_file():
            raise DatasetValidationError(
                f"Export dataset not found at '{resolved_export}'. Generate an export first."
            )

        dataset = load_longitudinal_dataset(resolved_export)
        lineage = verify_export_lineage(batch, dataset)
        recorded_sha = str(dataset.metadata.get("source_batch_sha256", ""))
        current_sha = compute_canonical_batch_sha256(batch)

        return LineageInspectionResult(
            batch_id=batch.batch_id,
            export_path=str(resolved_export),
            is_synced=lineage.is_synced,
            status=lineage.status.value,
            source_sha256_matches=lineage.source_sha256_matches,
            recorded_source_sha256=recorded_sha,
            current_source_sha256=current_sha,
            withdrawn_groups_present=list(lineage.withdrawn_groups_present),
            unapproved_groups_present=list(lineage.unapproved_groups_present),
            new_approved_groups_missing=list(lineage.new_approved_groups_missing),
            violations=list(lineage.violations),
        )

    def reconcile_export(
        self, batch_id: str, export_path: Path | str | None = None
    ) -> ReconcileExecutionResult:
        """Safely reconcile and regenerate export to eliminate withdrawn or unapproved records."""
        path = self.workspace.get_batch_path(batch_id)
        batch = ProspectiveBatch.load(path)

        resolved_export = (
            Path(export_path).resolve()
            if export_path
            else self.workspace.get_export_path(batch.batch_id)
        )
        if not resolved_export.is_file():
            raise DatasetValidationError(
                f"Export dataset not found at '{resolved_export}'. Reconcile requires an existing export."
            )

        current_dataset = load_longitudinal_dataset(resolved_export)
        reconciled, lineage = reconcile_and_regenerate_export(
            batch,
            current_dataset,
            resolved_export,
            overwrite=True,
            export_timestamp=datetime.now(tz=UTC),
        )
        recorded_sha = str(reconciled.metadata.get("source_batch_sha256", ""))
        current_sha = compute_canonical_batch_sha256(batch)

        lineage_res = LineageInspectionResult(
            batch_id=batch.batch_id,
            export_path=str(resolved_export),
            is_synced=lineage.is_synced,
            status=lineage.status.value,
            source_sha256_matches=lineage.source_sha256_matches,
            recorded_source_sha256=recorded_sha,
            current_source_sha256=current_sha,
            withdrawn_groups_present=list(lineage.withdrawn_groups_present),
            unapproved_groups_present=list(lineage.unapproved_groups_present),
            new_approved_groups_missing=list(lineage.new_approved_groups_missing),
            violations=list(lineage.violations),
        )

        return ReconcileExecutionResult(
            batch_id=batch.batch_id,
            export_path=str(resolved_export),
            reconciled_booking_groups=len(reconciled.booking_groups),
            lineage=lineage_res,
        )

    def run_rehearsal(
        self,
        *,
        salt: str | None = None,
        run_timestamp: datetime | None = None,
    ) -> RehearsalReport:
        """Execute a deterministic offline synthetic rehearsal in the workspace."""
        rehearsal_ws = self.workspace.rehearsals_dir / "latest"
        rehearsal_ws.mkdir(parents=True, exist_ok=True)
        return run_prospective_rehearsal(
            rehearsal_ws,
            salt=salt,
            run_timestamp=run_timestamp,
        )

    def get_latest_rehearsal(self) -> dict[str, Any] | None:
        """Read the latest rehearsal report if present."""
        report_path = (
            self.workspace.rehearsals_dir / "latest" / "reports" / "rehearsal_report.json"
        )
        if not report_path.is_file():
            return None
        try:
            return json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _summarize_batch(self, batch: ProspectiveBatch, path: Path) -> BatchSummary:
        approved = sum(1 for s in batch.submissions if s.review_status is ReviewStatus.APPROVED)
        rejected = sum(1 for s in batch.submissions if s.review_status is ReviewStatus.REJECTED)
        quarantined = sum(1 for s in batch.submissions if s.review_status is ReviewStatus.QUARANTINED)
        pending = sum(1 for s in batch.submissions if s.review_status is ReviewStatus.PENDING_REVIEW)
        withdrawn = sum(1 for s in batch.submissions if s.review_status is ReviewStatus.WITHDRAWN)

        return BatchSummary(
            batch_id=batch.batch_id,
            file_path=str(path),
            schema_version=batch.schema_version,
            created_at=batch.created_at.isoformat(),
            total_submissions=len(batch.submissions),
            approved_count=approved,
            rejected_count=rejected,
            quarantined_count=quarantined,
            pending_count=pending,
            withdrawn_count=withdrawn,
            canonical_sha256=compute_canonical_batch_sha256(batch),
        )
