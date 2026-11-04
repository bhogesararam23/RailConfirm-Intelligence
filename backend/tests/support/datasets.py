"""Synthetic dataset fixtures for the training pipeline tests.

Every row is labelled ``is_synthetic=true``. That label is load-bearing: it lets the
full fit → evaluate → registry path be exercised while guaranteeing the resulting
artifact can never be served as a real model. Nothing produced here is railway
evidence, and no test here asserts anything about railway behaviour.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from railconfirm.data.longitudinal import (
    LONGITUDINAL_SCHEMA_VERSION,
    BookingGroup,
    FinalOutcome,
    LabelConfidence,
    LongitudinalDataset,
    LongitudinalJourney,
    PassengerReservation,
    StatusObservation,
    VerificationMethod,
)
from railconfirm.data.manifest import (
    AllowedUses,
    DecisionRecord,
    SourceRecord,
    generate_manifest,
    write_manifest,
)
from railconfirm.data.prospective import (
    DEFAULT_NOTICE_VERSION,
    DEFAULT_RETENTION_POLICY,
    PROSPECTIVE_COLLECTION_SCHEMA_VERSION,
    ConsentMetadata,
    ProspectiveBatch,
    ProspectivePassenger,
    ProspectiveSubmission,
    ReviewStatus,
)
from railconfirm.data.validator import REQUIRED_COLUMNS
from railconfirm.domain.prediction import FEATURE_SCHEMA_VERSION, PredictionTarget
from railconfirm.domain.status import MAPPING_VERSION, NormalizedStatus
from railconfirm.inference.artifacts import (
    ESTIMATOR_HISTORICAL_FREQUENCY,
    PROMOTION_APPROVED,
    ModelArtifactMetadata,
    write_artifact,
)
from railconfirm.inference.baseline import OUTCOME_CLASSES

HEADER = ",".join(
    [*REQUIRED_COLUMNS, "booking_group_id", "passenger_record_id", "is_synthetic"]
)

MOVING_HEADER = ",".join(
    [
        *REQUIRED_COLUMNS,
        "current_status",
        "booking_group_id",
        "passenger_record_id",
        "is_synthetic",
    ]
)

APPROVED_REVIEWER = "synthetic-test-harness"

SYNTHETIC_MARK = "# SYNTHETIC DATA - PIPELINE TEST ONLY - NOT REAL RAILWAY OBSERVATIONS"
"""Written on the first line of every fixture so a reader cannot mistake it for data."""

FITTABLE_COHORTS = {
    ("SL", "GN", "WL"): {"CNF": 70, "RAC": 20, "WL": 10, "CANCELLED": 5, "OTHER": 0},
    ("3A", "GN", "WL"): {"CNF": 30, "RAC": 10, "WL": 60, "CANCELLED": 0, "OTHER": 0},
    ("SL", "GN", "RAC"): {"CNF": 40, "RAC": 40, "WL": 20, "CANCELLED": 0, "OTHER": 0},
}


def build_rows(count: int = 240) -> list[str]:
    """Deterministic rows spanning 12 journey dates and both outcome labels."""
    rows: list[str] = []
    for index in range(count):
        day = index % 12 + 1
        month = 4 + index % 3
        initial = 10 + (index % 40)
        final = "CNF" if index % 3 == 0 else "WL/5"
        rows.append(
            f"1230{index % 3},2026-{month:02d}-{day:02d},"
            f"{'SL' if index % 2 else '3A'},GN,GNWL/{initial},{final},"
            f"2026-03-{(index % 28) + 1:02d},B{index:04d},P{index:04d},true"
        )
    return rows


def write_dataset(directory: Path, *, count: int = 240) -> Path:
    path = Path(directory) / "synthetic-training.csv"
    path.write_text(
        SYNTHETIC_MARK + "\n"
        + HEADER
        + "\n"
        + "\n".join(build_rows(count))
        + "\n",
        encoding="utf-8",
    )
    return path


def build_balanced_rows(count: int = 240) -> list[str]:
    """Rows whose cohort *and* outcome both vary inside every journey date.

    ``write_dataset`` ties the label to the same modulus as the date, so each date —
    and so each partition — carries one class only, which calibration correctly refuses
    to fit on. Here the label cycles on 5 and the class on 7, both coprime with the
    twelve-date cycle, so every date holds a mix of cohorts and of both labels and the
    predicted probability actually varies across the rows being fitted.
    """
    rows: list[str] = []
    for index in range(count):
        day = index % 12 + 1
        position = 10 + (index % 40)
        travel_class = "SL" if index % 7 < 4 else "3A"
        final = "CNF" if index % 5 < 2 else "WL/5"
        rows.append(
            f"1230{index % 3},2026-04-{day:02d},{travel_class},GN,GNWL/{position},{final},"
            f"2026-03-{(index % 28) + 1:02d},B{index:04d},P{index:04d},true"
        )
    return rows


def write_balanced_dataset(directory: Path, *, count: int = 240) -> Path:
    path = Path(directory) / "synthetic-balanced.csv"
    path.write_text(
        SYNTHETIC_MARK + "\n"
        + HEADER
        + "\n"
        + "\n".join(build_balanced_rows(count))
        + "\n",
        encoding="utf-8",
    )
    return path


def build_moving_rows(count: int = 240) -> list[str]:
    """Rows whose status moves between booking and the as-of observation.

    Every third row records a later look and the rest leave ``current_status`` empty,
    so the fixture exercises both halves of the as-of rule in every class: a recorded
    later look wins, and an absent one falls back to the booked status. Nothing here
    is railway evidence.
    """
    rows: list[str] = []
    for index in range(count):
        day = index % 12 + 1
        month = 4 + index % 3
        initial = 10 + (index % 40)
        current = f"RAC {index % 6}" if index % 3 == 0 else ""
        final = "CNF" if index % 4 < 2 else "WL/5"
        rows.append(
            f"1230{index % 3},2026-{month:02d}-{day:02d},"
            f"{'SL' if index % 2 else '3A'},GN,GNWL/{initial},{final},"
            f"2026-03-{(index % 28) + 1:02d},{current},B{index:04d},P{index:04d},true"
        )
    return rows


def write_moving_dataset(directory: Path, *, count: int = 240) -> Path:
    path = Path(directory) / "synthetic-moving.csv"
    path.write_text(
        SYNTHETIC_MARK + "\n"
        + MOVING_HEADER
        + "\n"
        + "\n".join(build_moving_rows(count))
        + "\n",
        encoding="utf-8",
    )
    return path


# ── Gate fixtures: a small file plus one row of every rejected shape ───────────

GATE_ROW_COUNT = 24
"""Clean bookings in :func:`write_gate_dataset` — deliberately below the intake
thresholds, so eligibility has to be argued rather than assumed."""


def gate_row(index: int, *, synthetic: str = "true") -> str:
    """One clean booking: six journey dates, both outcome classes, unique ids."""
    day = index % 6 + 1
    final = "CNF" if index % 2 == 0 else "WL/5"
    return (
        f"12301,2026-04-{day:02d},SL,GN,GNWL/{10 + index},{final},"
        f"2026-03-{index + 1:02d},B{index:04d},P{index:04d},{synthetic}"
    )


def gate_defects(synthetic: str = "true") -> dict[str, str]:
    """One CSV line per row shape the validator must reject, keyed by its reason.

    The synthetic marker follows the caller's choice: a rejected row must not be able
    to decide whether the file as a whole reads as synthetic."""
    mark = synthetic
    return {
        "exact_duplicate_row": gate_row(0, synthetic=mark),
        # Same reservation context as gate_row(1), opposite outcome label, so both
        # sides of the contradiction are rejected.
        "contradictory_labels": f"12301,2026-04-02,SL,GN,GNWL/11,CNF,2026-03-02,B0001,P0001,{mark}",
        "censored_label": f"12301,2026-04-03,SL,GN,GNWL/80,CENSORED,2026-03-03,B9001,P9001,{mark}",
        "unparseable_date": f"12301,04/05/2026,SL,GN,GNWL/81,CNF,2026-03-04,B9002,P9002,{mark}",
        "observation_after_journey": f"12301,2026-04-05,SL,GN,GNWL/82,CNF,2026-04-09,B9003,P9003,{mark}",
        # Same calendar day for both dates: not an ordering violation, but not a
        # forecast input either (ADR-0026).
        "observation_on_journey_date": f"12301,2026-04-06,SL,GN,GNWL/85,CNF,2026-04-06,B9007,P9007,{mark}",
        "invalid_train_number": f"AB1234,2026-04-06,SL,GN,GNWL/83,CNF,2026-03-06,B9004,P9004,{mark}",
        "missing_required_value": f"12301,2026-04-06,,GN,GNWL/84,CNF,2026-03-06,B9005,P9005,{mark}",
        "unknown_initial_status": f"12301,2026-04-06,SL,GN,MYSTERY/4,CNF,2026-03-06,B9006,P9006,{mark}",
    }


def write_gate_dataset(
    directory: Path,
    *,
    count: int = GATE_ROW_COUNT,
    synthetic: str = "true",
    defects: bool = True,
    name: str = "gate.csv",
) -> Path:
    """A structurally valid, small dataset, optionally carrying every defect shape."""
    rows = [gate_row(index, synthetic=synthetic) for index in range(count)]
    if defects:
        rows.extend(gate_defects(synthetic).values())
    path = Path(directory) / name
    path.write_text(SYNTHETIC_MARK + "\n" + HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def approved_source(**overrides) -> SourceRecord:
    base = {
        "publisher": "synthetic test harness",
        "retrieved_on": "2026-04-01",
        "source_register_entry": "tests/support/datasets.py",
        "terms_url": "https://example.invalid/synthetic-terms",
        "licence_name": "synthetic fixture",
        "licence_review_status": "approved",
        "allowed_uses": AllowedUses(
            local_inspection="permitted",
            transformation="permitted",
            model_training="permitted",
            aggregate_metric_publication="permitted",
            commercial_deployment="prohibited",
            redistribution="prohibited",
        ),
        "attribution_requirements": "none",
    }
    base.update(overrides)
    return SourceRecord(**base)


def approved_decision(**overrides) -> DecisionRecord:
    base = {
        "reviewed_by": APPROVED_REVIEWER,
        "reviewed_on": "2026-04-02",
        "decision": "approved",
        "rationale": "Synthetic fixture approved for pipeline testing only.",
    }
    base.update(overrides)
    return DecisionRecord(**base)


def write_approved_manifest(
    dataset_path: Path,
    directory: Path,
    *,
    dataset_id: str = "synthetic-pipeline-fixture",
    source: SourceRecord | None = None,
    decision: DecisionRecord | None = None,
) -> Path:
    """Generate and write a manifest whose decision section satisfies the gate."""
    manifest = generate_manifest(
        dataset_path,
        dataset_id=dataset_id,
        title="Synthetic pipeline fixture",
        retrieved_on="2026-04-01",
        source=source or approved_source(),
        decision=decision if decision is not None else approved_decision(),
    )
    return write_manifest(manifest, Path(directory) / f"{dataset_id}.yaml", overwrite=True)


def artifact_metadata(**overrides) -> ModelArtifactMetadata:
    base = {
        "version": "fixture_v1",
        "target": PredictionTarget.FINAL_CHART_CNF.value,
        "estimator": ESTIMATOR_HISTORICAL_FREQUENCY,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "status_mapping_version": MAPPING_VERSION,
        "outcome_classes": OUTCOME_CLASSES,
        "dataset_id": "synthetic-pipeline-fixture",
        "dataset_sha256": "b" * 64,
        "source_reference": "tests/support/datasets.py",
        "data_approval_status": "approved",
        "is_synthetic": False,
        "min_sample_threshold": 5,
        "laplace_alpha": 1.0,
        "promotion": PROMOTION_APPROVED,
        "limitations": ("Synthetic fixture artifact; not railway evidence.",),
        "trained_from": "2026-04-01",
        "trained_to": "2026-04-12",
    }
    base.update(overrides)
    return ModelArtifactMetadata(**base)


def write_serving_artifact(
    directory: Path,
    *,
    name: str = "fixture_v1",
    cohorts: dict | None = None,
    **meta_overrides,
) -> Path:
    """Write an artifact that the registry will serve, for engine and CLI tests."""
    return write_artifact(
        Path(directory) / f"{name}.json",
        artifact_metadata(**meta_overrides),
        cohorts or FITTABLE_COHORTS,
    )


def build_synthetic_longitudinal_dataset(
    *,
    dataset_id: str = "synthetic-longitudinal-fixture",
    journey_count: int = 4,
    groups_per_journey: int = 3,
    passengers_per_group: int = 2,
    is_synthetic: bool = True,
) -> LongitudinalDataset:
    """Build a deterministic synthetic longitudinal dataset for pipeline testing."""
    journeys: dict[str, LongitudinalJourney] = {}
    booking_groups: list[BookingGroup] = []

    for j_idx in range(journey_count):
        j_date = date(2026, 6, 1) + timedelta(days=j_idx * 3)
        dep_dt = datetime(2026, 6, 1, 16, 0, tzinfo=UTC) + timedelta(days=j_idx * 3)
        chart_dt = dep_dt - timedelta(hours=4)
        j_id = f"J{j_idx:03d}_12301"

        journeys[j_id] = LongitudinalJourney(
            journey_id=j_id,
            train_number="12301",
            journey_date=j_date,
            boarding_station="NDLS",
            destination_station="HWH",
            class_code="SL" if j_idx % 2 == 0 else "3A",
            quota_code="GN",
            scheduled_departure_at=dep_dt,
        )

        for g_idx in range(groups_per_journey):
            bg_id = f"SYN_J{j_idx:02d}_G{g_idx:02d}"
            booking_time = dep_dt - timedelta(days=25)

            passengers: list[PassengerReservation] = []
            for p_idx in range(passengers_per_group):
                pid = f"{bg_id}_P{p_idx + 1}"
                init_pos = 20 + p_idx * 5 + g_idx * 2

                # Observations chronologically advancing
                obs1_time = booking_time + timedelta(days=5)
                obs1 = StatusObservation(
                    observation_id=f"{pid}_OBS1",
                    passenger_record_id=pid,
                    observed_at=obs1_time,
                    status_raw=f"WL/{init_pos - 3}",
                    status_category=NormalizedStatus.WL,
                    status_position=init_pos - 3,
                )

                obs2_time = dep_dt - timedelta(days=3)
                obs2 = StatusObservation(
                    observation_id=f"{pid}_OBS2",
                    passenger_record_id=pid,
                    observed_at=obs2_time,
                    status_raw=f"RAC/{p_idx + 1}",
                    status_category=NormalizedStatus.RAC,
                    status_position=p_idx + 1,
                )

                # Final outcome
                is_confirmed = (j_idx + g_idx + p_idx) % 2 == 0
                outcome = FinalOutcome(
                    outcome_target="final_chart_cnf",
                    outcome_status_raw="CNF" if is_confirmed else f"RAC/{p_idx + 1}",
                    outcome_category=(
                        NormalizedStatus.CNF if is_confirmed else NormalizedStatus.RAC
                    ),
                    outcome_observed_at=chart_dt,
                    verification_method=VerificationMethod.CHART_SNAPSHOT,
                    label_confidence=LabelConfidence.VERIFIED,
                )

                passengers.append(
                    PassengerReservation(
                        passenger_record_id=pid,
                        booking_group_id=bg_id,
                        passenger_sequence=p_idx + 1,
                        original_status_raw=f"GNWL/{init_pos}",
                        original_status_category=NormalizedStatus.WL,
                        original_status_position=init_pos,
                        original_observed_at=booking_time,
                        observations=[obs1, obs2],
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

    return LongitudinalDataset(
        schema_version=LONGITUDINAL_SCHEMA_VERSION,
        dataset_id=dataset_id,
        source_id="synthetic_generator",
        created_at=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
        journeys=journeys,
        booking_groups=booking_groups,
        metadata={"is_synthetic": is_synthetic, "generator": "backend/tests/support/datasets.py"},
    )


def write_synthetic_longitudinal_dataset(
    directory: Path,
    *,
    dataset_id: str = "synthetic-longitudinal-fixture",
    **build_kwargs,
) -> Path:
    """Build and write a synthetic longitudinal JSON dataset file."""
    dataset = build_synthetic_longitudinal_dataset(dataset_id=dataset_id, **build_kwargs)
    path = Path(directory) / f"{dataset_id}.json"
    dataset.save(path)
    return path


def build_synthetic_prospective_batch(
    *,
    batch_id: str = "synthetic-prospective-batch",
    submission_count: int = 4,
    passengers_per_submission: int = 2,
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW,
) -> ProspectiveBatch:
    """Build a deterministic synthetic prospective batch for pipeline testing."""
    consent = ConsentMetadata(
        consent_basis="explicit_opt_in",
        notice_version=DEFAULT_NOTICE_VERSION,
        purpose_records=[
            "confirmation_probability_research",
            "model_calibration",
        ],
        retention_policy=DEFAULT_RETENTION_POLICY,
        collected_at="2026-05-01T10:00:00Z",
    )

    submissions: list[ProspectiveSubmission] = []
    for s_idx in range(submission_count):
        sub_id = f"SUB_{s_idx:04d}"
        pseudo_id = f"anon_synth_{s_idx:04d}"
        j_date = date(2026, 7, 1) + timedelta(days=s_idx * 2)
        dep_dt = datetime(2026, 7, 1, 18, 30, tzinfo=UTC) + timedelta(days=s_idx * 2)

        passengers: list[ProspectivePassenger] = []
        for p_idx in range(passengers_per_submission):
            pid = f"{pseudo_id}_P{p_idx + 1}"
            obs = StatusObservation(
                observation_id=f"OBS_{s_idx}_{p_idx}",
                passenger_record_id=pid,
                observed_at=dep_dt - timedelta(days=5),
                status_raw="WL/8",
                status_category=NormalizedStatus.WL,
                status_position=8,
            )
            outcome = FinalOutcome(
                outcome_target="final_chart_cnf",
                outcome_status_raw="CNF",
                outcome_category=NormalizedStatus.CNF,
                outcome_observed_at=dep_dt - timedelta(hours=4),
                verification_method=VerificationMethod.CHART_SNAPSHOT,
                label_confidence=LabelConfidence.VERIFIED,
            )
            passengers.append(
                ProspectivePassenger(
                    passenger_sequence=p_idx + 1,
                    original_status_raw="GNWL/12",
                    original_status_category=NormalizedStatus.WL,
                    original_status_position=12,
                    observations=[obs],
                    outcome=outcome,
                )
            )

        submissions.append(
            ProspectiveSubmission(
                submission_id=sub_id,
                pseudonym_group_id=pseudo_id,
                train_number="12951",
                journey_date=j_date,
                boarding_station="MMCT",
                destination_station="NDLS",
                class_code="3A",
                quota_code="GN",
                scheduled_departure_at=dep_dt,
                consent=consent,
                passengers=passengers,
                review_status=review_status,
            )
        )

    return ProspectiveBatch(
        batch_id=batch_id,
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        submissions=submissions,
        schema_version=PROSPECTIVE_COLLECTION_SCHEMA_VERSION,
    )


def write_synthetic_prospective_batch(
    directory: Path,
    *,
    batch_id: str = "synthetic-prospective-batch",
    **build_kwargs,
) -> Path:
    """Build and write a synthetic prospective JSON batch file."""
    batch = build_synthetic_prospective_batch(batch_id=batch_id, **build_kwargs)
    path = Path(directory) / f"{batch_id}.json"
    batch.save(path)
    return path
