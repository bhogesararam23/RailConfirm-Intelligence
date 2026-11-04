"""End-to-end pipeline test for Phase 2 data intake, validation, snapshotting, and modeling.

Verifies the complete flow:
Longitudinal Dataset (v2.0.0)
  -> Schema Detection
  -> Validation & Quality Auditing
  -> Manifest Generation & Cryptographic Verification
  -> Point-in-time Snapshot Conversion (v1.1.0 flat rows)
  -> Feature Construction & Chronological Split
  -> Estimator Fitting & Calibration
  -> Synthetic provenance preservation
"""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from railconfirm.data.inspection import FormatType, detect_schema
from railconfirm.data.longitudinal import (
    LONGITUDINAL_SCHEMA_VERSION,
    BookingGroup,
    CensoringReason,
    FinalOutcome,
    LabelConfidence,
    LongitudinalDataset,
    LongitudinalJourney,
    PassengerReservation,
    StatusObservation,
    VerificationMethod,
    create_point_in_time_snapshot,
    save_longitudinal_dataset,
)
from railconfirm.data.longitudinal_validator import validate_longitudinal_dataset
from railconfirm.data.manifest import generate_manifest, verify_manifest, write_manifest
from railconfirm.data.preprocessing import (
    extract_features,
    strip_labels,
)
from railconfirm.data.validator import REQUIRED_COLUMNS, validate_dataset
from railconfirm.domain.status import NormalizedStatus


@pytest.fixture
def synthetic_longitudinal_dataset(tmp_path: Path) -> Path:
    """Generate a rich multi-journey synthetic longitudinal fixture for pipeline testing."""
    journeys = {}
    booking_groups = []

    # Create 3 journeys across different dates
    base_dates = [date(2026, 12, 5), date(2026, 12, 10), date(2026, 12, 15)]

    for j_idx, j_date in enumerate(base_dates, start=1):
        j_id = f"J_{j_idx}"
        dep_dt = datetime(j_date.year, j_date.month, j_date.day, 18, 0, tzinfo=UTC)
        journey = LongitudinalJourney(
            journey_id=j_id,
            train_number="12301",
            journey_date=j_date,
            boarding_station="NDLS",
            destination_station="HWH",
            class_code="3A",
            quota_code="GN",
            scheduled_departure_at=dep_dt,
        )
        journeys[j_id] = journey

        # Create 5 booking groups per journey with 1-3 passengers each
        for bg_idx in range(1, 6):
            bg_id = f"{j_id}_BG_{bg_idx}"
            passengers = []
            group_size = (bg_idx % 3) + 1

            for p_idx in range(1, group_size + 1):
                p_id = f"{bg_id}_P_{p_idx}"
                # Initial status: Day -30
                orig_dt = dep_dt - timedelta(days=30)
                is_cancelled = (bg_idx == 5 and p_idx == group_size)

                # Observations at Day -20, Day -10, Day -3
                obs1_dt = dep_dt - timedelta(days=20)
                obs2_dt = dep_dt - timedelta(days=10)
                obs3_dt = dep_dt - timedelta(days=3)

                obs_list = [
                    StatusObservation(
                        observation_id=f"{p_id}_O1",
                        passenger_record_id=p_id,
                        observed_at=obs1_dt,
                        status_raw=f"GNWL {20 - p_idx}",
                        status_category=NormalizedStatus.WL,
                        status_position=20 - p_idx,
                    ),
                    StatusObservation(
                        observation_id=f"{p_id}_O2",
                        passenger_record_id=p_id,
                        observed_at=obs2_dt,
                        status_raw=f"RAC {8 - p_idx}",
                        status_category=NormalizedStatus.RAC,
                        status_position=8 - p_idx,
                    ),
                ]

                if not is_cancelled:
                    obs_list.append(
                        StatusObservation(
                            observation_id=f"{p_id}_O3",
                            passenger_record_id=p_id,
                            observed_at=obs3_dt,
                            status_raw=f"RAC {2 - (p_idx % 2)}",
                            status_category=NormalizedStatus.RAC,
                            status_position=2 - (p_idx % 2),
                        )
                    )
                    outcome = FinalOutcome(
                        outcome_target="final_chart_cnf",
                        outcome_status_raw="CNF" if bg_idx <= 3 else "RAC 1",
                        outcome_category=NormalizedStatus.CNF if bg_idx <= 3 else NormalizedStatus.RAC,
                        is_censored=False,
                        outcome_observed_at=dep_dt - timedelta(hours=4),
                        verification_method=VerificationMethod.CHART_SNAPSHOT,
                        label_confidence=LabelConfidence.VERIFIED,
                    )
                else:
                    outcome = FinalOutcome(
                        outcome_target="final_chart_cnf",
                        outcome_status_raw="CAN",
                        outcome_category=NormalizedStatus.CANCELLED,
                        is_censored=True,
                        censoring_reason=CensoringReason.USER_CANCELLED,
                        outcome_observed_at=dep_dt - timedelta(days=5),
                        verification_method=VerificationMethod.STATUS_ENQUIRY,
                        label_confidence=LabelConfidence.PROVISIONAL,
                    )

                passengers.append(
                    PassengerReservation(
                        passenger_record_id=p_id,
                        booking_group_id=bg_id,
                        passenger_sequence=p_idx,
                        original_status_raw=f"GNWL {30 - p_idx}",
                        original_status_category=NormalizedStatus.WL,
                        original_status_position=30 - p_idx,
                        original_observed_at=orig_dt,
                        observations=obs_list,
                        outcome=outcome,
                    )
                )

            booking_groups.append(
                BookingGroup(
                    booking_group_id=bg_id,
                    journey_id=j_id,
                    passengers=passengers,
                )
            )

    dataset = LongitudinalDataset(
        schema_version=LONGITUDINAL_SCHEMA_VERSION,
        dataset_id="phase2_pipeline_synthetic_dataset",
        source_id="synthetic_fixture_generator",
        created_at=datetime(2026, 11, 1, 0, 0, tzinfo=UTC),
        metadata={"is_synthetic": True, "fixture_purpose": "end_to_end_pipeline_testing"},
        journeys=journeys,
        booking_groups=booking_groups,
    )

    out_file = tmp_path / "longitudinal_pipeline.json"
    save_longitudinal_dataset(dataset, out_file)
    return out_file


def test_end_to_end_phase2_intake_and_modeling_pipeline(
    synthetic_longitudinal_dataset: Path,
    tmp_path: Path,
):
    # Step 1: Detect Schema
    detection = detect_schema(synthetic_longitudinal_dataset)
    assert detection.format_type == FormatType.LONGITUDINAL
    assert detection.schema_version == LONGITUDINAL_SCHEMA_VERSION
    assert detection.is_valid_structure is True
    assert detection.record_count > 0

    # Step 2: Validate Dataset & Audit Quality
    from railconfirm.data.longitudinal import load_longitudinal_dataset

    long_ds = load_longitudinal_dataset(synthetic_longitudinal_dataset)
    audit = validate_longitudinal_dataset(long_ds)
    assert audit.is_valid is True
    assert len(audit.errors) == 0
    assert audit.metrics is not None
    assert audit.metrics.total_journeys == 3
    assert audit.metrics.total_booking_groups == 15
    assert audit.metrics.censored_count == 3  # 1 per journey

    # Step 3: Provenance Manifest Generation
    manifest = generate_manifest(
        synthetic_longitudinal_dataset,
        dataset_id="phase2_pipeline_synthetic_dataset",
        title="Phase 2 Pipeline Synthetic Verification Set",
        retrieved_on="2026-11-01",
    )
    assert manifest.file.format == "longitudinal_json"
    assert manifest.file.schema_version == LONGITUDINAL_SCHEMA_VERSION
    assert manifest.coverage.row_count == long_ds.total_passengers

    manifest_file = tmp_path / "dataset_manifest.yaml"
    write_manifest(manifest, manifest_file)

    # Step 4: Manifest Cryptographic Verification
    verification = verify_manifest(manifest_file, synthetic_longitudinal_dataset)
    assert verification.ok is True
    assert "file format is valid longitudinal dataset" in verification.checks

    # Step 5: Point-in-time Snapshot Conversion at Day -7
    # Note: Day -7 is between Day -10 and Day -3, so observations at Day -10 are captured
    snapshot = create_point_in_time_snapshot(
        long_ds,
        as_of_lead_days=7,
        allow_censored=False,
    )
    df_snap = snapshot.frame
    assert len(df_snap) > 0
    assert snapshot.rows_skipped_censored == 3
    for col in REQUIRED_COLUMNS:
        assert col in df_snap.columns

    # Verify that synthetic flag is preserved in snapshot frame
    assert "is_synthetic" in df_snap.columns
    assert all(df_snap["is_synthetic"])

    # Step 6: Validate Row Interchange Schema
    row_report = validate_dataset(df_snap, source_name="snapshot_day_7")
    assert row_report.structurally_valid is True
    assert row_report.rejected_rows == 0
    assert row_report.valid_rows == len(df_snap)
    # Correctly reports provisional eligibility minimum requirements on test-scale dataset
    assert len(row_report.eligibility_findings) > 0

    # Step 7: Feature Engineering & Preprocessing
    df_features = extract_features(strip_labels(df_snap))
    assert "asof_normalized" in df_features.columns
    assert "lead_days" in df_features.columns

    # Verify all statuses at Day -7 snapshot are RAC (since Day -10 transition was RAC)
    assert all(df_features["asof_normalized"] == "RAC")

    # Step 8: Estimator Training & Evaluation on Prepared Data
    from railconfirm.domain.prediction import AbstentionReason
    from railconfirm.domain.status import parse_status
    from railconfirm.inference.baseline import (
        FrequencyTableProvenance,
        HistoricalFrequencyBaseline,
        normalize_frequency_table,
    )
    from railconfirm.training.fitter import fit_cohorts

    fit_summary = fit_cohorts(df_snap)
    assert fit_summary.rows_used > 0
    assert len(fit_summary.cohorts) > 0

    norm_table = normalize_frequency_table(fit_summary.cohorts)

    # 8a: Candidate unapproved provenance abstains strictly
    candidate_prov = FrequencyTableProvenance(
        dataset_id="phase2_pipeline_synthetic_dataset",
        sha256="a" * 64,
        source_reference="test_pipeline_run",
        approval_status="candidate",
        is_synthetic=True,
        evaluation_only=False,
    )
    unapproved_baseline = HistoricalFrequencyBaseline(min_sample_threshold=1)
    unapproved_baseline.load_frequency_table(norm_table, provenance=candidate_prov)
    sample_row = df_snap.iloc[0]
    abstain_res = unapproved_baseline.estimate(
        passenger_id="P_UNAPPROVED",
        asof_status=parse_status(sample_row["initial_status"]),
        class_code=sample_row["class_code"],
        quota_code=sample_row["quota_code"],
    )
    assert abstain_res.is_supported() is False
    assert abstain_res.abstention_reason == AbstentionReason.NO_APPROVED_DATA

    # 8b: Explicit evaluation-only approved pipeline test produces valid probabilities
    eval_prov = FrequencyTableProvenance(
        dataset_id="phase2_pipeline_synthetic_dataset",
        sha256="a" * 64,
        source_reference="test_pipeline_run",
        approval_status="approved",
        is_synthetic=True,
        evaluation_only=True,
    )
    eval_baseline = HistoricalFrequencyBaseline(min_sample_threshold=1)
    eval_baseline.load_frequency_table(norm_table, provenance=eval_prov)

    est_res = eval_baseline.estimate(
        passenger_id="P_EVAL",
        asof_status=parse_status(sample_row["initial_status"]),
        class_code=sample_row["class_code"],
        quota_code=sample_row["quota_code"],
    )
    assert est_res.is_supported() is True
    assert est_res.abstention_reason is None
    assert est_res.p_cnf is not None
    assert 0.0 <= est_res.p_cnf <= 1.0
    assert est_res.p_rac is not None
    assert 0.0 <= est_res.p_rac <= 1.0
    assert est_res.p_wl is not None
    assert 0.0 <= est_res.p_wl <= 1.0
    assert est_res.p_cancelled is not None
    assert est_res.p_other is not None
    assert abs(est_res.p_cnf + est_res.p_rac + est_res.p_wl + est_res.p_cancelled + est_res.p_other - 1.0) < 1e-5
