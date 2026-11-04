"""Tests for longitudinal dataset validation and quality auditing."""

import json
from datetime import UTC, date, datetime

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
    StatusObservation,
    VerificationMethod,
)
from railconfirm.data.longitudinal_validator import (
    validate_longitudinal_dataset,
)
from railconfirm.domain.status import NormalizedStatus


@pytest.fixture
def valid_dataset() -> LongitudinalDataset:
    journey_date = date(2026, 12, 1)
    dep_time = datetime(2026, 12, 1, 16, 30, tzinfo=UTC)

    journey = LongitudinalJourney(
        journey_id="J1",
        train_number="12301",
        journey_date=journey_date,
        boarding_station="NDLS",
        destination_station="HWH",
        class_code="3A",
        quota_code="GN",
        scheduled_departure_at=dep_time,
    )

    p1 = PassengerReservation(
        passenger_record_id="P1",
        booking_group_id="BG1",
        passenger_sequence=1,
        original_status_raw="GNWL 25",
        original_status_category=NormalizedStatus.WL,
        original_status_position=25,
        original_observed_at=datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
        observations=[
            StatusObservation(
                observation_id="O1",
                passenger_record_id="P1",
                observed_at=datetime(2026, 11, 10, 10, 0, tzinfo=UTC),
                status_raw="GNWL 15",
                status_category=NormalizedStatus.WL,
                status_position=15,
            ),
            StatusObservation(
                observation_id="O2",
                passenger_record_id="P1",
                observed_at=datetime(2026, 11, 25, 10, 0, tzinfo=UTC),
                status_raw="RAC 5",
                status_category=NormalizedStatus.RAC,
                status_position=5,
            ),
        ],
        outcome=FinalOutcome(
            outcome_target="final_chart_cnf",
            outcome_status_raw="CNF",
            outcome_category=NormalizedStatus.CNF,
            is_censored=False,
            outcome_observed_at=datetime(2026, 12, 1, 12, 0, tzinfo=UTC),
            verification_method=VerificationMethod.CHART_SNAPSHOT,
            label_confidence=LabelConfidence.VERIFIED,
        ),
    )

    # A second passenger who cancelled (censored)
    p2 = PassengerReservation(
        passenger_record_id="P2",
        booking_group_id="BG1",
        passenger_sequence=2,
        original_status_raw="GNWL 26",
        original_status_category=NormalizedStatus.WL,
        original_status_position=26,
        original_observed_at=datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
        observations=[
            StatusObservation(
                observation_id="O3",
                passenger_record_id="P2",
                observed_at=datetime(2026, 11, 10, 10, 0, tzinfo=UTC),
                status_raw="GNWL 16",
                status_category=NormalizedStatus.WL,
                status_position=16,
            ),
        ],
        outcome=FinalOutcome(
            outcome_target="final_chart_cnf",
            outcome_status_raw="CAN",
            outcome_category=NormalizedStatus.CANCELLED,
            is_censored=True,
            censoring_reason=CensoringReason.USER_CANCELLED,
            outcome_observed_at=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
            verification_method=VerificationMethod.STATUS_ENQUIRY,
            label_confidence=LabelConfidence.PROVISIONAL,
        ),
    )

    group = BookingGroup(
        booking_group_id="BG1",
        journey_id="J1",
        booking_created_at=datetime(2026, 11, 1, 9, 30, tzinfo=UTC),
        passengers=[p1, p2],
    )

    return LongitudinalDataset(
        schema_version=LONGITUDINAL_SCHEMA_VERSION,
        dataset_id="test_ds_001",
        source_id="test_provider",
        created_at=datetime(2026, 12, 2, 0, 0, tzinfo=UTC),
        metadata={"is_synthetic": True, "source_type": "local_synthetic_fixture"},
        journeys={"J1": journey},
        booking_groups=[group],
    )


def test_validate_clean_dataset(valid_dataset: LongitudinalDataset):
    report = validate_longitudinal_dataset(valid_dataset)
    assert report.is_valid is True
    assert len(report.errors) == 0
    assert report.metrics is not None
    m = report.metrics
    assert m.total_journeys == 1
    assert m.total_booking_groups == 1
    assert m.total_passengers == 2
    assert m.total_observations == 3
    assert m.censored_count == 1
    assert m.censored_percentage == 50.0
    assert m.group_size_distribution == {2: 1}
    assert m.transition_anomaly_count == 0


def test_validate_detects_out_of_order_observations(valid_dataset: LongitudinalDataset):
    # Reverse observation timestamps on P1
    p1 = valid_dataset.booking_groups[0].passengers[0]
    p1.observations[1] = StatusObservation(
        observation_id="O2",
        passenger_record_id="P1",
        observed_at=datetime(2026, 11, 5, 0, 0, tzinfo=UTC),  # Earlier than O1 (Nov 10)!
        status_raw="RAC 5",
        status_category=NormalizedStatus.RAC,
        status_position=5,
    )

    report = validate_longitudinal_dataset(valid_dataset)
    assert report.is_valid is False
    assert any("not strictly after previous observation" in err for err in report.errors)


def test_validate_detects_observation_after_departure(valid_dataset: LongitudinalDataset):
    # Observation after departure on Dec 2
    p1 = valid_dataset.booking_groups[0].passengers[0]
    p1.observations.append(
        StatusObservation(
            observation_id="O_POST",
            passenger_record_id="P1",
            observed_at=datetime(2026, 12, 2, 0, 0, tzinfo=UTC),  # After departure!
            status_raw="CNF",
            status_category=NormalizedStatus.CNF,
        )
    )

    report = validate_longitudinal_dataset(valid_dataset)
    assert report.is_valid is False
    assert any("occurred after scheduled departure" in err for err in report.errors)


def test_validate_detects_transition_anomaly(valid_dataset: LongitudinalDataset):
    # RAC -> WL regression
    p1 = valid_dataset.booking_groups[0].passengers[0]
    p1.observations.append(
        StatusObservation(
            observation_id="O_REGRESS",
            passenger_record_id="P1",
            observed_at=datetime(2026, 11, 28, 10, 0, tzinfo=UTC),
            status_raw="GNWL 20",  # Regressed from RAC 5!
            status_category=NormalizedStatus.WL,
            status_position=20,
        )
    )

    # In strict mode: raises error
    report_strict = validate_longitudinal_dataset(valid_dataset, strict=True)
    assert report_strict.is_valid is False
    assert any("RAC reservation regressed to Waitlist" in err for err in report_strict.errors)

    # In non-strict mode: generates warning
    report_lenient = validate_longitudinal_dataset(valid_dataset, strict=False)
    assert report_lenient.is_valid is True
    assert any("RAC reservation regressed to Waitlist" in w for w in report_lenient.warnings)


def test_validate_detects_unknown_journey_reference(valid_dataset: LongitudinalDataset):
    valid_dataset.booking_groups[0].journey_id = "NON_EXISTENT_JOURNEY"

    report = validate_longitudinal_dataset(valid_dataset)
    assert report.is_valid is False
    assert any("references unknown journey_id 'NON_EXISTENT_JOURNEY'" in err for err in report.errors)


def test_validate_detects_passenger_id_mismatch_in_observation(valid_dataset: LongitudinalDataset):
    p1 = valid_dataset.booking_groups[0].passengers[0]
    p1.observations[0] = StatusObservation(
        observation_id="O1",
        passenger_record_id="WRONG_PASSENGER_ID",
        observed_at=datetime(2026, 11, 10, 10, 0, tzinfo=UTC),
        status_raw="GNWL 15",
        status_category=NormalizedStatus.WL,
        status_position=15,
    )

    report = validate_longitudinal_dataset(valid_dataset)
    assert report.is_valid is False
    assert any("does not match parent passenger" in err for err in report.errors)


def test_audit_report_serialization_roundtrip(valid_dataset: LongitudinalDataset):
    report = validate_longitudinal_dataset(valid_dataset)
    d = report.to_dict()

    json_str = json.dumps(d)
    parsed = json.loads(json_str)

    assert parsed["dataset_id"] == "test_ds_001"
    assert parsed["is_valid"] is True
    assert parsed["metrics"]["total_passengers"] == 2
    assert parsed["metrics"]["censored_count"] == 1
