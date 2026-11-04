"""Tests for prospective collection, privacy scanner, and operator governance."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from railconfirm.data.longitudinal import (
    LONGITUDINAL_SCHEMA_VERSION,
    FinalOutcome,
    LabelConfidence,
    StatusObservation,
    VerificationMethod,
)
from railconfirm.data.prospective import (
    DEFAULT_NOTICE_VERSION,
    MIN_SALT_LENGTH,
    PROSPECTIVE_COLLECTION_SCHEMA_VERSION,
    ConsentMetadata,
    ExportLineageReport,
    LineageStatus,
    ProspectiveBatch,
    ProspectivePassenger,
    ProspectiveSubmission,
    ReviewStatus,
    WithdrawalAuditRecord,
    approve_batch_for_research,
    atomic_write_json,
    derive_pseudonym,
    export_batch_to_longitudinal,
    generate_prospective_template,
    get_configured_pseudonym_salt,
    intake_prospective_submission,
    mask_sensitive_token,
    reconcile_and_regenerate_export,
    review_batch,
    scan_for_personal_data,
    validate_prospective_batch,
    verify_export_lineage,
    withdraw_submission,
)
from railconfirm.domain.exceptions import DatasetValidationError, SecurityError
from railconfirm.domain.status import NormalizedStatus


def test_derive_pseudonym_deterministic_and_salted():
    salt = "secret_deployment_salt_123456789012"
    p1 = derive_pseudonym("PNR_4567890123", salt)
    p2 = derive_pseudonym("PNR_4567890123", salt)
    assert p1 == p2
    assert p1.startswith("anon_")

    different_salt = derive_pseudonym("PNR_4567890123", "different_salt_456789012345678901")
    assert p1 != different_salt

    with pytest.raises(SecurityError, match="cryptographic salt is required"):
        derive_pseudonym("PNR_4567890123", "")

    # Short salt must be refused to resist brute force over finite PNR space
    with pytest.raises(SecurityError, match=f"must be at least {MIN_SALT_LENGTH} characters"):
        derive_pseudonym("PNR_4567890123", "short_salt_under_32_chars")


def test_privacy_scanner_detects_personal_data_patterns():
    # 1. 10-digit Indian Railway PNR (string and numeric)
    assert scan_for_personal_data({"ref": "My ticket is 2345678901"}) != []
    assert scan_for_personal_data({"ref": "PNR: 234-5678901"}) != []
    assert scan_for_personal_data({"pnr_num": 2345678901}) != []

    # 2. Email address
    assert scan_for_personal_data({"contact": "passenger@example.com"}) != []

    # 3. Phone number
    assert scan_for_personal_data({"mobile": "+919876543210"}) != []
    assert scan_for_personal_data({"mobile": "9876543210"}) != []

    # 4. Aadhaar number
    assert scan_for_personal_data({"id": "1234 5678 9012"}) != []

    # 5. PAN card tax ID
    assert scan_for_personal_data({"pan": "ABCDE1234F"}) != []

    # 6. Passport number
    assert scan_for_personal_data({"passport": "A1234567"}) != []

    # 7. URL query token / credentials
    assert scan_for_personal_data({"url": "https://api.example.com?pnr=2345678901&auth=xyz"}) != []

    # 8. Clean pseudonymous data
    clean = {
        "submission_id": "sub_001",
        "pseudonym_group_id": "anon_a1b2c3d4e5f60718",
        "train_number": "12301",
        "journey_date": "2026-12-01",
        "class_code": "3A",
    }
    assert scan_for_personal_data(clean) == []


def test_consent_metadata_validation():
    valid = ConsentMetadata(
        consent_basis="explicit_opt_in",
        notice_version=DEFAULT_NOTICE_VERSION,
        purpose_records=["confirmation_probability_research"],
    )
    assert valid.consent_basis == "explicit_opt_in"
    assert valid.withdrawn is False

    with pytest.raises(DatasetValidationError, match="Invalid consent_basis"):
        ConsentMetadata(
            consent_basis="unconsented_scrape",
            notice_version="1.0",
            purpose_records=["confirmation_probability_research"],
        )

    with pytest.raises(DatasetValidationError, match="Invalid purpose"):
        ConsentMetadata(
            consent_basis="explicit_opt_in",
            notice_version="1.0",
            purpose_records=["commercial_ad_targeting"],
        )

    with pytest.raises(DatasetValidationError, match="Withdrawn consent must specify withdrawn_at"):
        ConsentMetadata(
            consent_basis="explicit_opt_in",
            notice_version=DEFAULT_NOTICE_VERSION,
            purpose_records=["confirmation_probability_research"],
            withdrawn=True,
            withdrawn_at=None,
        )


@pytest.fixture
def sample_submission() -> ProspectiveSubmission:
    consent = ConsentMetadata(
        consent_basis="user_initiated_submission",
        notice_version=DEFAULT_NOTICE_VERSION,
        purpose_records=["confirmation_probability_research", "model_calibration"],
    )

    passenger = ProspectivePassenger(
        passenger_sequence=1,
        original_status_raw="GNWL 15",
        original_status_category=NormalizedStatus.WL,
        original_status_position=15,
        observations=[
            StatusObservation(
                observation_id="OBS_1",
                passenger_record_id="placeholder",
                observed_at=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
                status_raw="RAC 4",
                status_category=NormalizedStatus.RAC,
                status_position=4,
            )
        ],
        outcome=FinalOutcome(
            outcome_target="final_chart_cnf",
            outcome_status_raw="CNF",
            outcome_category=NormalizedStatus.CNF,
            outcome_observed_at=datetime(2026, 12, 1, 12, 0, tzinfo=UTC),
            verification_method=VerificationMethod.CHART_SNAPSHOT,
            verification_source="irctc_online_charts:verified",
            label_confidence=LabelConfidence.VERIFIED,
        ),
    )

    return ProspectiveSubmission(
        submission_id="SUB_20261101_001",
        pseudonym_group_id="anon_group_88a91c",
        train_number="12301",
        journey_date=date(2026, 12, 1),
        boarding_station="NDLS",
        destination_station="HWH",
        class_code="3A",
        quota_code="GN",
        scheduled_departure_at=datetime(2026, 12, 1, 16, 55, tzinfo=UTC),
        consent=consent,
        passengers=[passenger],
    )


def test_intake_submission_pii_quarantine(sample_submission: ProspectiveSubmission):
    # Clean submission passes
    ok, diag = intake_prospective_submission(sample_submission)
    assert ok is True
    assert len(diag) == 0

    # Submission with PII pattern is quarantined
    sample_submission.review_notes = "Passenger phone: 9876543210"
    ok, diag = intake_prospective_submission(sample_submission)
    assert ok is False
    assert sample_submission.review_status == ReviewStatus.QUARANTINED
    assert len(diag) > 0


def test_prospective_batch_roundtrip(sample_submission: ProspectiveSubmission, tmp_path: Path):
    batch = ProspectiveBatch(
        batch_id="BATCH_20261101",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sample_submission],
    )

    batch_file = tmp_path / "prospective_batch.json"
    batch.save(batch_file)

    loaded = ProspectiveBatch.load(batch_file)
    assert loaded.batch_id == batch.batch_id
    assert loaded.schema_version == PROSPECTIVE_COLLECTION_SCHEMA_VERSION
    assert len(loaded.submissions) == 1
    sub = loaded.submissions[0]
    assert sub.pseudonym_group_id == "anon_group_88a91c"
    assert sub.train_number == "12301"
    assert sub.consent.consent_basis == "user_initiated_submission"


def test_approve_and_export_batch(sample_submission: ProspectiveSubmission):
    batch = ProspectiveBatch(
        batch_id="BATCH_20261101",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sample_submission],
    )

    # Attempt export while PENDING_REVIEW should fail
    with pytest.raises(DatasetValidationError, match="only APPROVED submissions can be exported"):
        export_batch_to_longitudinal(batch, dataset_id="ds_export", source_id="prospective_test")

    # Operator approves batch
    approve_batch_for_research(
        batch,
        reviewer="lead_engineer",
        rationale="All consent records verified and PII scan clean.",
    )
    assert sample_submission.review_status == ReviewStatus.APPROVED
    assert sample_submission.reviewed_by == "lead_engineer"

    # Export now succeeds
    long_ds = export_batch_to_longitudinal(
        batch,
        dataset_id="ds_export_001",
        source_id="prospective_collection_pilot",
    )
    assert long_ds.schema_version == LONGITUDINAL_SCHEMA_VERSION
    assert long_ds.dataset_id == "ds_export_001"
    assert len(long_ds.journeys) == 1
    assert len(long_ds.booking_groups) == 1
    p = long_ds.booking_groups[0].passengers[0]
    assert p.original_status_raw == "GNWL 15"
    assert len(p.observations) == 1
    assert p.observations[0].passenger_record_id == "anon_group_88a91c_P1"


def test_validate_prospective_batch_clean_and_diagnostics(
    sample_submission: ProspectiveSubmission,
):
    batch = ProspectiveBatch(
        batch_id="BATCH_VALID_001",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sample_submission],
    )
    report = validate_prospective_batch(batch)
    assert report.is_valid is True
    assert report.total_submissions == 1
    assert report.total_passengers == 1
    assert report.total_observations == 1
    assert report.review_status_counts[ReviewStatus.PENDING_REVIEW.value] == 1
    assert len(report.pii_violations) == 0
    assert "Valid: yes" in report.summary()
    assert report.threshold_feasibility_pilot is False  # 1 passenger < 30


def test_validate_prospective_batch_detects_pii_and_structural_errors(
    sample_submission: ProspectiveSubmission,
):
    # Contaminate with PNR leak and duplicate submission ID
    sub_pii = ProspectiveSubmission.from_dict(sample_submission.to_dict())
    sub_pii.review_notes = "Ticket PNR is 1234567890"

    batch = ProspectiveBatch(
        batch_id="BATCH_INVALID_002",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sample_submission, sub_pii],
    )
    report = validate_prospective_batch(batch)
    assert report.is_valid is False
    assert len(report.pii_violations) > 0
    assert any("PNR" in v for v in report.pii_violations)
    assert any("Duplicate submission_id" in err for err in report.structural_errors)
    assert "Valid: no" in report.summary()


def test_review_batch_actions_and_pii_safeguard(
    sample_submission: ProspectiveSubmission,
):
    batch = ProspectiveBatch(
        batch_id="BATCH_REVIEW_003",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sample_submission],
    )

    # 1. Review with rejection
    review_batch(
        batch,
        action=ReviewStatus.REJECTED,
        reviewer="auditor_1",
        rationale="Missing outcome evidence.",
    )
    assert batch.submissions[0].review_status == ReviewStatus.REJECTED
    assert batch.submissions[0].reviewed_by == "auditor_1"

    # 2. Review with quarantine
    review_batch(
        batch,
        action=ReviewStatus.QUARANTINED,
        reviewer="auditor_2",
        rationale="Needs verification.",
    )
    assert batch.submissions[0].review_status == ReviewStatus.QUARANTINED

    # 3. Validation on required reviewer/rationale
    with pytest.raises(DatasetValidationError, match="named human reviewer"):
        review_batch(batch, action=ReviewStatus.APPROVED, reviewer="", rationale="Ok")
    with pytest.raises(DatasetValidationError, match="non-empty rationale"):
        review_batch(batch, action=ReviewStatus.APPROVED, reviewer="auditor", rationale="")

    # 4. Refuse approval when contaminated with PII
    batch.submissions[0].review_notes = "Passenger phone: 9876543210"
    with pytest.raises(SecurityError, match="unresolved personal data"):
        review_batch(
            batch,
            action=ReviewStatus.APPROVED,
            reviewer="auditor_3",
            rationale="Trying to approve with phone",
        )


def test_participant_consent_withdrawal_lifecycle(sample_submission: ProspectiveSubmission):
    batch = ProspectiveBatch(
        batch_id="BATCH_WITHDRAWAL_001",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sample_submission],
    )

    # Withdraw participant consent
    updated_sub = withdraw_submission(
        batch,
        submission_id=sample_submission.submission_id,
        reason="Participant requested erasure prior to dataset release.",
        operator="operator_lead",
    )
    assert updated_sub.review_status == ReviewStatus.WITHDRAWN
    assert updated_sub.consent.withdrawn is True
    assert updated_sub.consent.withdrawn_at is not None
    assert "erasure" in updated_sub.consent.withdrawal_reason

    # Reviewing with approval must be refused
    with pytest.raises(SecurityError, match="participant consent was withdrawn"):
        review_batch(
            batch,
            action=ReviewStatus.APPROVED,
            reviewer="lead",
            rationale="Trying to override withdrawal",
        )

    # Exporting must be refused
    with pytest.raises(DatasetValidationError, match="withdrawn participant consent"):
        export_batch_to_longitudinal(
            batch,
            dataset_id="long_withdrawn",
            source_id="test_source",
            require_all_approved=True,
        )

    # Withdrawal log verification
    assert len(batch.withdrawal_log) == 1
    log1 = batch.withdrawal_log[0]
    assert isinstance(log1, WithdrawalAuditRecord)
    assert log1.submission_id == sample_submission.submission_id
    assert log1.pseudonym_group_id == sample_submission.pseudonym_group_id
    assert log1.prior_review_status == ReviewStatus.PENDING_REVIEW.value
    assert log1.operator == "operator_lead"

    # Idempotent second withdrawal preserves original timestamp
    orig_withdrawn_at = updated_sub.consent.withdrawn_at
    second_sub = withdraw_submission(
        batch,
        submission_id=sample_submission.submission_id,
        reason="Repeated request by participant confirmation.",
        operator="operator_deputy",
    )
    assert second_sub.consent.withdrawn_at == orig_withdrawn_at
    assert len(batch.withdrawal_log) == 2
    log2 = batch.withdrawal_log[1]
    assert log2.prior_review_status == ReviewStatus.WITHDRAWN.value
    assert log2.operator == "operator_deputy"

    # Batch serialization roundtrips withdrawal_log
    d = batch.to_dict()
    assert "withdrawal_log" in d
    assert len(d["withdrawal_log"]) == 2
    loaded = ProspectiveBatch.from_dict(d)
    assert len(loaded.withdrawal_log) == 2
    assert loaded.withdrawal_log[0].submission_id == sample_submission.submission_id


def test_withdraw_approved_submission(sample_submission: ProspectiveSubmission):
    # Approve submission first
    sample_submission.review_status = ReviewStatus.APPROVED
    sample_submission.reviewed_by = "lead_evaluator"
    sample_submission.review_notes = "Approved for research"
    sample_submission.reviewed_at = datetime.now(tz=UTC).isoformat()

    batch = ProspectiveBatch(
        batch_id="BATCH_WITHDRAWAL_002",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sample_submission],
    )

    # Participant withdraws consent after approval
    withdrawn = withdraw_submission(
        batch,
        submission_id=sample_submission.submission_id,
        reason="Revoking research permission after travel completed",
        operator="privacy_officer",
    )
    assert withdrawn.review_status == ReviewStatus.WITHDRAWN
    assert withdrawn.consent.withdrawn is True
    assert len(batch.withdrawal_log) == 1
    assert batch.withdrawal_log[0].prior_review_status == ReviewStatus.APPROVED.value
    assert batch.withdrawal_log[0].operator == "privacy_officer"

    # Export must now fail
    with pytest.raises(DatasetValidationError, match="withdrawn participant consent"):
        export_batch_to_longitudinal(
            batch,
            dataset_id="long_withdrawn_post_approval",
            source_id="test_source",
        )



def test_passenger_and_journey_invariants(sample_submission: ProspectiveSubmission):
    # 1. Same boarding and destination station
    with pytest.raises(DatasetValidationError, match="must be different"):
        ProspectiveSubmission(
            submission_id="SUB_SAME_STN",
            pseudonym_group_id="anon_g1",
            train_number="12301",
            journey_date=date(2026, 12, 1),
            boarding_station="NDLS",
            destination_station="NDLS",
            class_code="3A",
            quota_code="GN",
            consent=sample_submission.consent,
            passengers=sample_submission.passengers,
        )

    # 2. Passenger sequence bounds (>6 rejected)
    with pytest.raises(DatasetValidationError, match="passenger_sequence must be between 1 and 6"):
        ProspectivePassenger(
            passenger_sequence=7,
            original_status_raw="GNWL 10",
            original_status_category=NormalizedStatus.WL,
        )

    # 3. Non-contiguous passenger sequences
    pax_non_contig = [
        ProspectivePassenger(
            passenger_sequence=1,
            original_status_raw="GNWL 10",
            original_status_category=NormalizedStatus.WL,
        ),
        ProspectivePassenger(
            passenger_sequence=3,
            original_status_raw="GNWL 11",
            original_status_category=NormalizedStatus.WL,
        ),
    ]
    with pytest.raises(DatasetValidationError, match="contiguous sequences starting at 1"):
        ProspectiveSubmission(
            submission_id="SUB_NON_CONTIG",
            pseudonym_group_id="anon_g3",
            train_number="12301",
            journey_date=date(2026, 12, 1),
            boarding_station="NDLS",
            destination_station="HWH",
            class_code="3A",
            quota_code="GN",
            consent=sample_submission.consent,
            passengers=pax_non_contig,
        )

    # 4. Out-of-order observations
    with pytest.raises(DatasetValidationError, match="strictly chronologically ordered"):
        ProspectivePassenger(
            passenger_sequence=1,
            original_status_raw="GNWL 10",
            original_status_category=NormalizedStatus.WL,
            observations=[
                StatusObservation(
                    observation_id="OBS_1",
                    passenger_record_id="p1",
                    observed_at=datetime(2026, 11, 25, 10, 0, tzinfo=UTC),
                    status_raw="RAC 10",
                    status_category=NormalizedStatus.RAC,
                ),
                StatusObservation(
                    observation_id="OBS_2",
                    passenger_record_id="p1",
                    observed_at=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),  # earlier than OBS_1
                    status_raw="RAC 5",
                    status_category=NormalizedStatus.RAC,
                ),
            ],
        )

    # 5. Verified outcome without verification source
    with pytest.raises(DatasetValidationError, match="verified outcome must document verification_source"):
        ProspectivePassenger(
            passenger_sequence=1,
            original_status_raw="GNWL 10",
            original_status_category=NormalizedStatus.WL,
            outcome=FinalOutcome(
                outcome_target="final_chart_cnf",
                outcome_status_raw="CNF",
                outcome_category=NormalizedStatus.CNF,
                verification_method=VerificationMethod.CHART_SNAPSHOT,
                verification_source="",  # empty source
                label_confidence=LabelConfidence.VERIFIED,
            ),
        )


def test_generate_prospective_template_roundtrip(tmp_path: Path):
    template_path = tmp_path / "pilot_template.json"
    written = generate_prospective_template(template_path, submission_count=2, multi_passenger=True)
    assert written == template_path
    assert template_path.is_file()

    # Re-generating without overwrite must raise FileExistsError
    with pytest.raises(FileExistsError, match="already exists"):
        generate_prospective_template(template_path, overwrite=False)

    # Load and validate
    batch = ProspectiveBatch.load(template_path)
    assert batch.schema_version == PROSPECTIVE_COLLECTION_SCHEMA_VERSION
    assert len(batch.submissions) == 2
    assert len(batch.submissions[1].passengers) == 2

    # Validation must pass cleanly with 0 PII violations
    report = validate_prospective_batch(batch)
    assert report.is_valid is True
    assert len(report.pii_violations) == 0


def test_pii_token_masking_and_circular_protection():
    # Masking tests
    assert mask_sensitive_token("12") == "****"
    assert mask_sensitive_token("user@example.com") == "us****@example.com"
    assert mask_sensitive_token("u@example.com") == "****@example.com"
    assert mask_sensitive_token("9876543210") == "98****10"

    # PII scanner reports masked tokens (matches both 10-digit PNR and Indian mobile)
    pnr_violations = scan_for_personal_data({"ticket": "My ticket is 9876543210"})
    assert len(pnr_violations) >= 1
    assert all("98****10" in v for v in pnr_violations)
    assert not any("9876543210" in v for v in pnr_violations)

    email_violations = scan_for_personal_data({"contact": "alice@company.org"})
    assert len(email_violations) == 1
    assert "al****@company.org" in email_violations[0]
    assert "alice@company.org" not in email_violations[0]

    # Circular data structure protection (no infinite recursion or RecursionError)
    circular_dict: dict = {"key": "safe_val"}
    circular_dict["self"] = circular_dict
    assert scan_for_personal_data(circular_dict) == []

    circular_list: list = [1, 2]
    circular_list.append(circular_list)
    assert scan_for_personal_data(circular_list) == []


def test_configured_pseudonym_salt(monkeypatch):
    valid_salt = "super_secret_deployment_salt_0123456789"
    monkeypatch.setenv("RAILCONFIRM_PSEUDONYM_SALT", valid_salt)

    assert get_configured_pseudonym_salt() == valid_salt
    derived = derive_pseudonym("PNR_12345")
    assert derived.startswith("anon_")
    assert derived == derive_pseudonym("PNR_12345", salt=valid_salt)

    # Missing salt raises SecurityError
    monkeypatch.delenv("RAILCONFIRM_PSEUDONYM_SALT", raising=False)
    with pytest.raises(SecurityError, match="No cryptographic salt configured"):
        get_configured_pseudonym_salt()
    with pytest.raises(SecurityError, match="No cryptographic salt configured"):
        derive_pseudonym("PNR_12345")

    # Short salt raises SecurityError
    monkeypatch.setenv("RAILCONFIRM_PSEUDONYM_SALT", "too_short_salt")
    with pytest.raises(SecurityError, match="too weak"):
        get_configured_pseudonym_salt()


def test_atomic_write_json_roundtrip_and_safety(tmp_path: Path):
    target = tmp_path / "subdir" / "record.json"
    data = {"batch_id": "BATCH_001", "records": [1, 2, 3]}

    # Successful atomic write creates directory and writes file
    written = atomic_write_json(target, data, indent=2)
    assert written == target
    assert target.is_file()

    import json
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded == data

    # Failure during serialization does not corrupt existing file
    bad_data = {"batch_id": "BATCH_002", "unserializable": object()}
    with pytest.raises(TypeError):
        atomic_write_json(target, bad_data)

    # File should remain uncorrupted with original content
    intact = json.loads(target.read_text(encoding="utf-8"))
    assert intact == data

    # No leftover temporary files
    temp_files = list(target.parent.glob(".tmp_*"))
    assert len(temp_files) == 0


def test_export_lineage_metadata_and_deterministic_ordering(sample_submission: ProspectiveSubmission):
    sub1 = sample_submission
    sub1.review_status = ReviewStatus.APPROVED

    # Create sub2 with a distinct group ID and train
    sub2 = ProspectiveSubmission(
        submission_id="SUB_EXPORT_002",
        pseudonym_group_id="anon_group_002",
        train_number="12951",
        journey_date=date(2026, 12, 10),
        boarding_station="MMCT",
        destination_station="NDLS",
        class_code="2A",
        quota_code="GN",
        consent=sub1.consent,
        passengers=sub1.passengers,
        review_status=ReviewStatus.APPROVED,
    )

    batch_a = ProspectiveBatch(
        batch_id="BATCH_LINEAGE_001",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sub2, sub1],  # sub2 first
    )

    fixed_time = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
    exp_a = export_batch_to_longitudinal(
        batch_a,
        dataset_id="long_a",
        source_id="src_a",
        export_timestamp=fixed_time,
    )

    assert "lineage" in exp_a.metadata
    lineage = exp_a.metadata["lineage"]
    assert lineage["source_batch_id"] == "BATCH_LINEAGE_001"
    assert lineage["total_considered"] == 2
    assert lineage["total_included"] == 2
    assert lineage["total_excluded"] == 0
    assert lineage["included_submissions"] == sorted([sub1.submission_id, sub2.submission_id])

    # Invert input order in batch_b
    batch_b = ProspectiveBatch(
        batch_id="BATCH_LINEAGE_001",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sub1, sub2],  # sub1 first
    )
    exp_b = export_batch_to_longitudinal(
        batch_b,
        dataset_id="long_a",
        source_id="src_a",
        export_timestamp=fixed_time,
    )

    # Booking groups must be deterministically sorted by booking_group_id
    assert [bg.booking_group_id for bg in exp_a.booking_groups] == [
        bg.booking_group_id for bg in exp_b.booking_groups
    ]
    # Byte-for-byte serialization must be identical
    import json
    json_a = json.dumps(exp_a.to_dict(), sort_keys=True)
    json_b = json.dumps(exp_b.to_dict(), sort_keys=True)
    assert json_a == json_b


def test_verify_export_lineage_and_stale_detection(sample_submission: ProspectiveSubmission):
    sample_submission.review_status = ReviewStatus.APPROVED
    batch = ProspectiveBatch(
        batch_id="BATCH_LINEAGE_002",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sample_submission],
    )

    exp = export_batch_to_longitudinal(
        batch,
        dataset_id="long_sync_test",
        source_id="src_test",
    )

    # 1. Initially verified in sync
    report = verify_export_lineage(batch, exp)
    assert isinstance(report, ExportLineageReport)
    assert report.is_synced is True
    assert report.status == LineageStatus.VERIFIED_IN_SYNC
    assert "Lineage Status: verified_in_sync" in report.summary()

    # 2. Incompatible batch ID
    other_batch = ProspectiveBatch(
        batch_id="BATCH_OTHER_999",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sample_submission],
    )
    incompat_report = verify_export_lineage(other_batch, exp)
    assert incompat_report.is_synced is False
    assert incompat_report.status == LineageStatus.INCOMPATIBLE

    # 3. Withdrawal after export triggers STALE_WITHDRAWN_RECORDS_PRESENT
    withdraw_submission(
        batch,
        submission_id=sample_submission.submission_id,
        reason="Revoking research consent after export",
        operator="data_officer",
    )
    stale_report = verify_export_lineage(batch, exp)
    assert stale_report.is_synced is False
    assert stale_report.status == LineageStatus.STALE_WITHDRAWN_RECORDS_PRESENT
    assert sample_submission.pseudonym_group_id in stale_report.withdrawn_groups_present
    assert "CRITICAL: 1 withdrawn booking group(s) present in export" in stale_report.summary()


def test_reconcile_and_regenerate_export(tmp_path: Path, sample_submission: ProspectiveSubmission):
    sample_submission.review_status = ReviewStatus.APPROVED
    sub2 = ProspectiveSubmission(
        submission_id="SUB_RECON_002",
        pseudonym_group_id="anon_recon_group_002",
        train_number="12951",
        journey_date=date(2026, 12, 10),
        boarding_station="MMCT",
        destination_station="NDLS",
        class_code="2A",
        quota_code="GN",
        consent=sample_submission.consent,
        passengers=sample_submission.passengers,
        review_status=ReviewStatus.APPROVED,
    )
    batch = ProspectiveBatch(
        batch_id="BATCH_RECON_001",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sample_submission, sub2],
    )

    # Initial export with 2 submissions
    out_file = tmp_path / "longitudinal_recon.json"
    initial_exp = export_batch_to_longitudinal(
        batch,
        dataset_id="long_recon",
        source_id="src_recon",
    )
    atomic_write_json(out_file, initial_exp.to_dict())

    # Withdraw first submission
    withdraw_submission(
        batch,
        submission_id=sample_submission.submission_id,
        reason="Withdrawing first submission",
        operator="op_lead",
    )

    # Export is now stale
    stale_report = verify_export_lineage(batch, initial_exp)
    assert stale_report.is_synced is False

    # Reconcile and regenerate
    fixed_time = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)
    reconciled_ds, clean_report = reconcile_and_regenerate_export(
        batch,
        initial_exp,
        out_file,
        overwrite=True,
        export_timestamp=fixed_time,
    )
    assert clean_report.is_synced is True
    assert clean_report.status == LineageStatus.VERIFIED_IN_SYNC
    assert len(reconciled_ds.booking_groups) == 1
    assert reconciled_ds.booking_groups[0].booking_group_id == sub2.pseudonym_group_id
    assert sample_submission.pseudonym_group_id not in [bg.booking_group_id for bg in reconciled_ds.booking_groups]


def test_audit_report_decoupled_dimensions_and_accounting(sample_submission: ProspectiveSubmission):
    # Setup sub1 as approved with 1 passenger, 1 observation, verified outcome
    sub1 = sample_submission
    sub1.review_status = ReviewStatus.APPROVED

    # Setup sub2 with missing observation and missing outcome
    p2 = ProspectivePassenger(
        passenger_sequence=1,
        original_status_raw="RLWL 2",
        original_status_category=NormalizedStatus.WL,
        observations=[],  # missing observation
        outcome=None,  # missing outcome
    )
    sub2 = ProspectiveSubmission(
        submission_id="SUB_DIAG_002",
        pseudonym_group_id="anon_diag_group_002",
        train_number="12951",
        journey_date=date(2026, 12, 10),
        boarding_station="MMCT",
        destination_station="NDLS",
        class_code="2A",
        quota_code="GN",
        consent=sub1.consent,
        passengers=[p2],
        review_status=ReviewStatus.PENDING_REVIEW,
    )

    batch = ProspectiveBatch(
        batch_id="BATCH_DIAG_001",
        created_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        submissions=[sub1, sub2],
    )

    report = validate_prospective_batch(batch)

    # 1. Submission accounting
    assert report.total_submissions == 2
    assert report.total_passengers == 2
    assert report.eligible_submissions == 1  # only sub1 is approved
    assert report.pending_submissions == 1  # sub2 is pending
    assert report.withdrawn_submissions == 0
    assert report.rejected_submissions == 0
    assert report.quarantined_submissions == 0

    # 2. Missing data diagnostics
    assert report.missing_observation_count == 1  # p2 has no observations
    assert report.missing_outcome_count == 1  # p2 has no outcome
    assert report.unverified_outcome_count == 0  # sub1's pax is verified
    assert report.censored_outcome_count == 0

    # 3. Eight decoupled governance dimensions
    assert report.is_structurally_valid is True
    assert report.is_privacy_clean is True
    assert report.is_consent_valid is True
    assert report.is_operator_approved is False  # sub2 is pending, so not fully approved
    assert report.is_legally_reviewed is True
    assert report.is_technically_eligible is False  # < 50 passengers
    assert report.is_scientifically_adequate is False  # < 30 passengers
    assert report.is_model_training_approved is False  # blocked by unapproved and insufficient data

    # 4. Summary presentation contains governance dimensions and accounting
    summ = report.summary()
    assert "Governance Dimensions (8 Gates):" in summ
    assert "Structurally Valid:       PASS" in summ
    assert "Operator Approved:        FAIL" in summ
    assert "Model Training Approved:  BLOCKED" in summ
    assert "Missing Observations: 1" in summ
    assert "Missing Outcomes:     1" in summ
    assert "Accounting: eligible=1, pending=1" in summ




