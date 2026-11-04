"""Unit and property tests for longitudinal data contract and snapshot conversion."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from railconfirm.data.longitudinal import (
    LONGITUDINAL_SCHEMA_VERSION,
    BookingGroup,
    CensoringReason,
    FinalOutcome,
    LabelConfidence,
    LongitudinalDataset,
    LongitudinalJourney,
    PassengerReservation,
    SnapshotResult,
    StatusObservation,
    VerificationMethod,
    create_point_in_time_snapshot,
    load_longitudinal_dataset,
    save_longitudinal_dataset,
)
from railconfirm.data.validator import REQUIRED_COLUMNS
from railconfirm.domain.exceptions import DatasetValidationError, TemporalIntegrityError
from railconfirm.domain.status import NormalizedStatus


@pytest.fixture
def sample_dataset() -> LongitudinalDataset:
    journey_date = date(2026, 11, 20)
    created_at = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)

    journey = LongitudinalJourney(
        journey_id="J1",
        train_number="12301",
        journey_date=journey_date,
        boarding_station="NDLS",
        destination_station="HWH",
        class_code="3A",
        quota_code="GN",
    )

    bg = BookingGroup(
        booking_group_id="B1",
        journey_id="J1",
        booking_created_at=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        collection_basis="research_consented",
    )

    p1 = PassengerReservation(
        passenger_record_id="P1",
        booking_group_id="B1",
        passenger_sequence=1,
        original_status_raw="GNWL/45",
        original_status_category=NormalizedStatus.WL,
        original_status_position=45,
        original_observed_at=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
        outcome=FinalOutcome(
            outcome_target="final_chart_cnf",
            outcome_status_raw="CNF",
            outcome_category=NormalizedStatus.CNF,
            outcome_observed_at=datetime(2026, 11, 20, 6, 0, tzinfo=UTC),
            verification_method=VerificationMethod.CHART_SNAPSHOT,
            label_confidence=LabelConfidence.VERIFIED,
        ),
    )

    # Observations at Day -20, Day -10, Day -3
    p1.add_observation(
        StatusObservation(
            observation_id="O1",
            passenger_record_id="P1",
            observed_at=datetime(2026, 10, 31, 14, 0, tzinfo=UTC),  # 20 days before
            status_raw="GNWL/25",
            status_category=NormalizedStatus.WL,
            status_position=25,
        )
    )
    p1.add_observation(
        StatusObservation(
            observation_id="O2",
            passenger_record_id="P1",
            observed_at=datetime(2026, 11, 10, 14, 0, tzinfo=UTC),  # 10 days before
            status_raw="RAC 12",
            status_category=NormalizedStatus.RAC,
            status_position=12,
        )
    )
    p1.add_observation(
        StatusObservation(
            observation_id="O3",
            passenger_record_id="P1",
            observed_at=datetime(2026, 11, 17, 14, 0, tzinfo=UTC),  # 3 days before
            status_raw="CNF",
            status_category=NormalizedStatus.CNF,
        )
    )

    # Passenger 2 with censored outcome
    p2 = PassengerReservation(
        passenger_record_id="P2",
        booking_group_id="B1",
        passenger_sequence=2,
        original_status_raw="GNWL/46",
        original_status_category=NormalizedStatus.WL,
        original_status_position=46,
        outcome=FinalOutcome(
            outcome_target="final_chart_cnf",
            outcome_status_raw="CAN",
            outcome_category=NormalizedStatus.CANCELLED,
            is_censored=True,
            censoring_reason=CensoringReason.USER_CANCELLED,
        ),
    )
    p2.add_observation(
        StatusObservation(
            observation_id="O4",
            passenger_record_id="P2",
            observed_at=datetime(2026, 10, 31, 14, 0, tzinfo=UTC),
            status_raw="GNWL/26",
            status_category=NormalizedStatus.WL,
            status_position=26,
        )
    )

    bg.add_passenger(p1)
    bg.add_passenger(p2)

    dataset = LongitudinalDataset(
        dataset_id="test_set_001",
        source_id="synthetic_research_v1",
        created_at=created_at,
        metadata={"is_synthetic": True, "description": "Unit test dataset"},
    )
    dataset.add_journey(journey)
    dataset.add_booking_group(bg)
    return dataset


def test_longitudinal_dataset_structure_and_counts(sample_dataset: LongitudinalDataset):
    assert sample_dataset.schema_version == LONGITUDINAL_SCHEMA_VERSION
    assert sample_dataset.total_passengers == 2
    assert sample_dataset.total_observations == 4
    assert len(sample_dataset.journeys) == 1
    assert len(sample_dataset.booking_groups) == 1


def test_status_observation_requires_timezone_aware():
    with pytest.raises(TemporalIntegrityError, match="observed_at.*has no timezone"):
        StatusObservation(
            observation_id="O_ERR",
            passenger_record_id="P1",
            observed_at=datetime(2026, 10, 1, 12, 0),  # noqa: DTZ001
            status_raw="GNWL 10",
            status_category=NormalizedStatus.WL,
        )


def test_final_outcome_censored_requires_reason():
    with pytest.raises(DatasetValidationError, match="Censored outcome must provide censoring_reason"):
        FinalOutcome(
            outcome_target="final_chart_cnf",
            outcome_status_raw="CAN",
            outcome_category=NormalizedStatus.CANCELLED,
            is_censored=True,
            censoring_reason=None,
        )


def test_dataset_json_roundtrip(sample_dataset: LongitudinalDataset, tmp_path: Path):
    file_path = tmp_path / "longitudinal.json"
    save_longitudinal_dataset(sample_dataset, file_path)

    loaded = load_longitudinal_dataset(file_path)
    assert loaded.dataset_id == sample_dataset.dataset_id
    assert loaded.source_id == sample_dataset.source_id
    assert loaded.total_passengers == sample_dataset.total_passengers
    assert loaded.total_observations == sample_dataset.total_observations

    # Check journey details
    j_orig = sample_dataset.journeys["J1"]
    j_loaded = loaded.journeys["J1"]
    assert j_loaded.train_number == j_orig.train_number
    assert j_loaded.journey_date == j_orig.journey_date
    assert j_loaded.class_code == j_orig.class_code

    # Check passenger observations
    p_orig = sample_dataset.booking_groups[0].passengers[0]
    p_loaded = loaded.booking_groups[0].passengers[0]
    assert p_loaded.passenger_record_id == p_orig.passenger_record_id
    assert len(p_loaded.observations) == 3
    assert p_loaded.observations[1].status_raw == "RAC 12"
    assert p_loaded.outcome is not None
    assert p_loaded.outcome.outcome_status_raw == "CNF"


def test_snapshot_by_lead_days_filters_future_observations(sample_dataset: LongitudinalDataset):
    # Snapshot at 5 lead days before 2026-11-20 (Cutoff is 2026-11-15)
    # P1 has observations at:
    # - 2026-10-31 (Day -20): GNWL/25
    # - 2026-11-10 (Day -10): RAC 12
    # - 2026-11-17 (Day -3): CNF (MUST BE EXCLUDED from the Day -5 snapshot!)
    result = create_point_in_time_snapshot(sample_dataset, as_of_lead_days=5)

    assert isinstance(result, SnapshotResult)
    assert result.rows_emitted == 1  # P2 is censored and excluded by default
    assert result.rows_skipped_censored == 1

    df = result.frame
    assert len(df) == 1
    for col in REQUIRED_COLUMNS:
        assert col in df.columns

    row = df.iloc[0]
    assert row["train_number"] == "12301"
    assert row["journey_date"] == "2026-11-20"
    assert row["initial_status"] == "GNWL/45"
    # Latest observation prior to Day -5 was Day -10 (RAC 12)
    assert row["current_status"] == "RAC 12"
    assert row["final_chart_status"] == "CNF"
    assert row["observation_date"] == "2026-11-15"
    assert bool(row["is_synthetic"]) is True


def test_snapshot_lead_days_horizon_at_day_15_captures_earlier_state(sample_dataset: LongitudinalDataset):
    # Snapshot at 15 lead days before 2026-11-20 (Cutoff is 2026-11-05)
    # Day -20 (2026-10-31) was GNWL/25
    result = create_point_in_time_snapshot(sample_dataset, as_of_lead_days=15)
    assert result.rows_emitted == 1
    row = result.frame.iloc[0]
    assert row["current_status"] == "GNWL/25"
    assert row["observation_date"] == "2026-11-05"


def test_snapshot_by_exact_datetime_timestamp(sample_dataset: LongitudinalDataset):
    # Cutoff at 2026-11-12 12:00:00 UTC (between Day -10 RAC 12 and Day -3 CNF)
    cutoff = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
    result = create_point_in_time_snapshot(sample_dataset, as_of_datetime=cutoff)

    assert result.rows_emitted == 1
    row = result.frame.iloc[0]
    assert row["current_status"] == "RAC 12"
    assert row["observation_date"] == "2026-11-12"


def test_snapshot_refuses_same_day_or_retrodiction_cutoff(sample_dataset: LongitudinalDataset):
    with pytest.raises(TemporalIntegrityError, match="less than MIN_LEAD_DAYS"):
        create_point_in_time_snapshot(sample_dataset, as_of_lead_days=0)


def test_snapshot_mutual_exclusion_of_parameters(sample_dataset: LongitudinalDataset):
    with pytest.raises(ValueError, match="Must specify exactly one"):
        create_point_in_time_snapshot(sample_dataset)

    with pytest.raises(ValueError, match="Must specify exactly one"):
        create_point_in_time_snapshot(
            sample_dataset,
            as_of_lead_days=5,
            as_of_datetime=datetime(2026, 11, 10, tzinfo=UTC),
        )


def test_snapshot_can_optionally_include_censored_records(sample_dataset: LongitudinalDataset):
    result = create_point_in_time_snapshot(
        sample_dataset, as_of_lead_days=5, allow_censored=True
    )
    assert result.rows_emitted == 2
    assert result.rows_skipped_censored == 0
    df = result.frame
    assert set(df["passenger_record_id"]) == {"P1", "P2"}
    p2_row = df[df["passenger_record_id"] == "P2"].iloc[0]
    assert p2_row["censoring_reason"] == CensoringReason.USER_CANCELLED.value
