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
    PROSPECTIVE_COLLECTION_SCHEMA_VERSION,
    ConsentMetadata,
    ProspectiveBatch,
    ProspectivePassenger,
    ProspectiveSubmission,
    ReviewStatus,
    approve_batch_for_research,
    derive_pseudonym,
    export_batch_to_longitudinal,
    intake_prospective_submission,
    scan_for_personal_data,
)
from railconfirm.domain.exceptions import DatasetValidationError, SecurityError
from railconfirm.domain.status import NormalizedStatus


def test_derive_pseudonym_deterministic_and_salted():
    salt = "secret_deployment_salt_123"
    p1 = derive_pseudonym("PNR_4567890123", salt)
    p2 = derive_pseudonym("PNR_4567890123", salt)
    assert p1 == p2
    assert p1.startswith("anon_")

    different_salt = derive_pseudonym("PNR_4567890123", "different_salt_456")
    assert p1 != different_salt

    with pytest.raises(SecurityError, match="cryptographic salt is required"):
        derive_pseudonym("PNR_4567890123", "")


def test_privacy_scanner_detects_personal_data_patterns():
    # 1. 10-digit Indian Railway PNR
    assert scan_for_personal_data({"ref": "My ticket is 2345678901"}) != []
    assert scan_for_personal_data({"ref": "PNR: 234-5678901"}) != []

    # 2. Email address
    assert scan_for_personal_data({"contact": "passenger@example.com"}) != []

    # 3. Phone number
    assert scan_for_personal_data({"mobile": "+919876543210"}) != []
    assert scan_for_personal_data({"mobile": "9876543210"}) != []

    # 4. Aadhaar number
    assert scan_for_personal_data({"id": "1234 5678 9012"}) != []

    # 5. Clean pseudonymous data
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
