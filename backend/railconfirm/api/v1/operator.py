"""Operator endpoints for local prospective data governance and rehearsal."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from railconfirm.api.dependencies import get_operator_service, require_local_operator
from railconfirm.api.problems import ApiProblem
from railconfirm.api.v1.schemas import (
    BatchInspectionResponse,
    BatchListResponse,
    BatchSummarySchema,
    ExportExecutionRequestBody,
    ExportExecutionResponse,
    ExportPreviewResponse,
    LineageInspectionResponse,
    OperatorStatusResponse,
    ReconcileExecutionResponse,
    RehearsalRunRequestBody,
    RehearsalRunResponse,
    ReviewSubmissionRequestBody,
    ReviewSubmissionResponse,
    WithdrawSubmissionRequestBody,
    WithdrawSubmissionResponse,
)
from railconfirm.data.operator import OperatorService
from railconfirm.domain.exceptions import DatasetValidationError, SecurityError

router = APIRouter(
    prefix="/operator",
    tags=["operator"],
    dependencies=[Depends(require_local_operator)],
)


@router.get(
    "/status",
    response_model=OperatorStatusResponse,
    summary="Get operator workbench status and workspace counts",
)
def get_operator_status(
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> OperatorStatusResponse:
    status_data = service.get_status()
    return OperatorStatusResponse(**status_data)


@router.get(
    "/batches",
    response_model=BatchListResponse,
    summary="List prospective collection batches in operator workspace",
)
def list_batches(
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> BatchListResponse:
    summaries = service.list_batches()
    return BatchListResponse(
        batches=[BatchSummarySchema(**s.to_dict()) for s in summaries],
        count=len(summaries),
    )


@router.post(
    "/batches/seed",
    response_model=BatchSummarySchema,
    status_code=status.HTTP_201_CREATED,
    summary="Seed clean synthetic fixture batch for operator inspection",
)
def seed_synthetic_batch(
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> BatchSummarySchema:
    summary = service.seed_synthetic_fixture()
    return BatchSummarySchema(**summary.to_dict())


@router.get(
    "/batches/{batch_id}",
    response_model=BatchInspectionResponse,
    summary="Inspect prospective batch with PII scan and governance audit",
)
def inspect_batch(
    batch_id: str,
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> BatchInspectionResponse:
    try:
        result = service.inspect_batch(batch_id)
    except DatasetValidationError as exc:
        raise ApiProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BATCH_NOT_FOUND",
            message=str(exc),
        ) from exc
    return BatchInspectionResponse(
        summary=BatchSummarySchema(**result.summary.to_dict()),
        pii_scan=result.pii_scan,
        audit_report=result.audit_report,
        submissions=result.submissions,
        withdrawal_log=result.withdrawal_log,
    )


@router.post(
    "/batches/{batch_id}/review",
    response_model=ReviewSubmissionResponse,
    summary="Record operator review decision for a submission",
)
def review_submission(
    batch_id: str,
    body: ReviewSubmissionRequestBody,
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> ReviewSubmissionResponse:
    try:
        res = service.review_submission(
            batch_id,
            submission_id=body.submission_id,
            action=body.action,
            reviewer=body.reviewer,
            rationale=body.rationale,
        )
    except SecurityError as exc:
        raise ApiProblem(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="PERSONAL_DATA_DETECTED",
            message=str(exc),
        ) from exc
    except DatasetValidationError as exc:
        code = (
            "BATCH_NOT_FOUND"
            if "not found in workspace" in str(exc)
            else "SUBMISSION_NOT_FOUND"
            if "Submission" in str(exc) and "not found" in str(exc)
            else "INVALID_OPERATOR_INPUT"
        )
        http_status = (
            status.HTTP_404_NOT_FOUND
            if code in ("BATCH_NOT_FOUND", "SUBMISSION_NOT_FOUND")
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise ApiProblem(
            status_code=http_status,
            code=code,
            message=str(exc),
        ) from exc

    return ReviewSubmissionResponse(
        submission_id=res.submission_id,
        action=res.action,
        reviewer=res.reviewer,
        reviewed_at=res.reviewed_at,
        rationale=res.rationale,
        batch_sha256=res.batch_sha256,
        batch_summary=BatchSummarySchema(**res.batch_summary.to_dict()),
    )


@router.post(
    "/batches/{batch_id}/withdraw",
    response_model=WithdrawSubmissionResponse,
    summary="Record participant consent withdrawal",
)
def withdraw_submission(
    batch_id: str,
    body: WithdrawSubmissionRequestBody,
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> WithdrawSubmissionResponse:
    try:
        res = service.withdraw_submission(
            batch_id,
            submission_id=body.submission_id,
            reason=body.reason,
            operator=body.operator,
        )
    except DatasetValidationError as exc:
        code = (
            "BATCH_NOT_FOUND"
            if "not found in workspace" in str(exc)
            else "SUBMISSION_NOT_FOUND"
            if "Submission" in str(exc) and "not found" in str(exc)
            else "INVALID_OPERATOR_INPUT"
        )
        http_status = (
            status.HTTP_404_NOT_FOUND
            if code in ("BATCH_NOT_FOUND", "SUBMISSION_NOT_FOUND")
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise ApiProblem(
            status_code=http_status,
            code=code,
            message=str(exc),
        ) from exc

    return WithdrawSubmissionResponse(
        submission_id=res.submission_id,
        operator=res.operator,
        reason=res.reason,
        withdrawn_at=res.withdrawn_at,
        batch_sha256=res.batch_sha256,
        audit_record=res.audit_record,
        batch_summary=BatchSummarySchema(**res.batch_summary.to_dict()),
    )


@router.get(
    "/batches/{batch_id}/export-preview",
    response_model=ExportPreviewResponse,
    summary="Preview longitudinal export counts and booking groups without saving",
)
def preview_export(
    batch_id: str,
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> ExportPreviewResponse:
    try:
        res = service.preview_export(batch_id)
    except DatasetValidationError as exc:
        raise ApiProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BATCH_NOT_FOUND",
            message=str(exc),
        ) from exc
    return ExportPreviewResponse(**res.to_dict())


@router.post(
    "/batches/{batch_id}/export",
    response_model=ExportExecutionResponse,
    summary="Export approved submissions to longitudinal dataset file",
)
def execute_export(
    batch_id: str,
    body: ExportExecutionRequestBody,
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> ExportExecutionResponse:
    try:
        res = service.execute_export(
            batch_id,
            dataset_id=body.dataset_id,
            source_id=body.source_id,
        )
    except DatasetValidationError as exc:
        raise ApiProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BATCH_NOT_FOUND",
            message=str(exc),
        ) from exc
    return ExportExecutionResponse(**res.to_dict())


@router.get(
    "/batches/{batch_id}/lineage",
    response_model=LineageInspectionResponse,
    summary="Verify lineage between source batch and exported dataset",
)
def inspect_lineage(
    batch_id: str,
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> LineageInspectionResponse:
    try:
        res = service.inspect_lineage(batch_id)
    except DatasetValidationError as exc:
        code = "BATCH_NOT_FOUND" if "batch" in str(exc).lower() else "EXPORT_NOT_FOUND"
        raise ApiProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            code=code,
            message=str(exc),
        ) from exc
    return LineageInspectionResponse(**res.to_dict())


@router.post(
    "/batches/{batch_id}/reconcile",
    response_model=ReconcileExecutionResponse,
    summary="Safely reconcile and regenerate export to eliminate withdrawn records",
)
def reconcile_export(
    batch_id: str,
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> ReconcileExecutionResponse:
    try:
        res = service.reconcile_export(batch_id)
    except DatasetValidationError as exc:
        raise ApiProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="RECONCILIATION_FAILED",
            message=str(exc),
        ) from exc
    return ReconcileExecutionResponse(
        batch_id=res.batch_id,
        export_path=res.export_path,
        reconciled_booking_groups=res.reconciled_booking_groups,
        lineage=LineageInspectionResponse(**res.lineage.to_dict()),
    )


@router.post(
    "/rehearsal/run",
    response_model=RehearsalRunResponse,
    summary="Run offline deterministic synthetic lifecycle rehearsal",
)
def run_rehearsal(
    body: RehearsalRunRequestBody,
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> RehearsalRunResponse:
    report = service.run_rehearsal(
        salt=body.salt,
        run_timestamp=body.run_timestamp,
    )
    return RehearsalRunResponse(
        report=report.to_dict(),
        summary_text=report.summary(),
    )


@router.get(
    "/rehearsal/latest",
    response_model=dict[str, Any],
    summary="Get latest rehearsal report if one exists",
)
def get_latest_rehearsal(
    service: Annotated[OperatorService, Depends(get_operator_service)],
) -> dict[str, Any]:
    report = service.get_latest_rehearsal()
    if report is None:
        raise ApiProblem(
            status_code=status.HTTP_404_NOT_FOUND,
            code="REHEARSAL_NOT_FOUND",
            message="No prior rehearsal report exists in the operator workspace.",
        )
    return report
