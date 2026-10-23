"""One as-of status for fitting, scoring and serving.

The baseline used to be fitted from ``initial_status`` while evaluation and the
served request read ``current_status``: the same reservation was counted in one
cohort and looked up in another. These tests pin the shared rule in all three places
with rows whose booked and observed statuses differ, whose queue positions move,
whose later look is absent or unmappable, and whose cohort exists only as a broad
fallback.

Every row here is synthetic; nothing in this file is railway evidence.
"""

from datetime import UTC, date, datetime

import pandas as pd
import pytest

from railconfirm.data.loader import load_dataset_file
from railconfirm.data.preprocessing import asof_statuses, require_status_columns
from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.journey import make_journey
from railconfirm.domain.passenger import make_observation
from railconfirm.domain.status import MAPPING_VERSION
from railconfirm.inference.baseline import (
    BROAD_COHORT_STATUS,
    FrequencyTableProvenance,
    cohort_key,
)
from railconfirm.inference.engine import InferenceEngine
from railconfirm.inference.registry import ModelRegistry
from railconfirm.training.fitter import fit_cohorts
from railconfirm.training.metrics import build_estimator, score_partition
from tests.support.artifacts import write_fixture_artifact as write_artifact
from tests.support.datasets import write_moving_dataset

WL_CELL = {"CNF": 90, "RAC": 0, "WL": 10, "CANCELLED": 0, "OTHER": 0}
RAC_CELL = {"CNF": 10, "RAC": 90, "WL": 5, "CANCELLED": 0, "OTHER": 0}
TABLE = {("SL", "GN", "WL"): WL_CELL, ("SL", "GN", "RAC"): RAC_CELL}

JOURNEY = make_journey(
    train_number="12301",
    journey_date=date(2026, 11, 15),
    boarding_station="NDLS",
    destination_station="HWH",
    class_code="SL",
    quota_code="GN",
)
AS_OF = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
OBSERVED_AT = datetime(2026, 10, 21, 7, 30, tzinfo=UTC)

PREVALENCE = {"CNF": 0.5, "RAC": 0.0, "WL": 0.5, "CANCELLED": 0.0, "OTHER": 0.0}


def rows(specs: list[tuple]) -> pd.DataFrame:
    """(initial_status, current_status, class_code, final_chart_status) rows."""
    return pd.DataFrame(
        [
            {
                "train_number": "12301",
                "journey_date": "2026-11-01",
                "class_code": class_code,
                "quota_code": "GN",
                "initial_status": initial,
                "current_status": current,
                "final_chart_status": label,
                "observation_date": "2026-10-20",
                "passenger_record_id": f"P{index:04d}",
            }
            for index, (initial, current, class_code, label) in enumerate(specs)
        ]
    )


def estimator(table=TABLE, min_sample_threshold: int = 10):
    return build_estimator(
        table,
        FrequencyTableProvenance(
            dataset_id="parity-fixture",
            sha256="e" * 64,
            source_reference="test",
            approval_status="approved",
            is_synthetic=True,
            mapping_version=MAPPING_VERSION,
            evaluation_only=True,
        ),
        min_sample_threshold=min_sample_threshold,
        laplace_alpha=1.0,
    )


def serving_engine(tmp_path, table=TABLE):
    write_artifact(tmp_path, cohorts=dict(table))
    return InferenceEngine(
        registry=ModelRegistry(models_dir=tmp_path, active_version="fixture_v1")
    )


def served(engine, *, original="GNWL/12", current="RAC 4"):
    booked = make_observation(original, source="fixture", observed_at=OBSERVED_AT, ingested_at=AS_OF)
    latest = make_observation(current, source="fixture", observed_at=OBSERVED_AT, ingested_at=AS_OF)
    return engine.predict(
        JOURNEY,
        [{"passenger_id": "p-1", "original_obs": booked, "current_obs": latest}],
        prediction_at=AS_OF,
    )


def _smoothed(cell: dict[str, int], outcome: str) -> float:
    """alpha 1.0 over five classes, as the estimator applies it."""
    return (cell[outcome] + 1) / (sum(cell.values()) + 5)


def _brier(cell: dict[str, int], truth: str) -> float:
    return sum(
        (_smoothed(cell, outcome) - (1.0 if outcome == truth else 0.0)) ** 2
        for outcome in WL_CELL
    )


# ── Fitting ────────────────────────────────────────────────────────────────────


def test_a_moved_reservation_is_counted_in_the_cohort_it_was_observed_in():
    summary = fit_cohorts(rows([("GNWL/40", "RAC 2", "SL", "CNF")]))
    exact = {cohort for cohort in summary.cohorts if cohort[2] != BROAD_COHORT_STATUS}
    assert exact == {("SL", "GN", "RAC")}
    assert summary.cohorts[("SL", "GN", BROAD_COHORT_STATUS)]["CNF"] == 1


def test_a_row_with_no_later_look_is_counted_in_its_booked_cohort():
    summary = fit_cohorts(rows([("GNWL/40", "", "SL", "CNF"), ("GNWL/41", None, "SL", "WL/3")]))
    assert set(summary.cohorts) == {
        ("SL", "GN", "WL"),
        ("SL", "GN", BROAD_COHORT_STATUS),
    }


def test_an_unmappable_observed_status_is_not_borrowed_from_the_booked_one():
    summary = fit_cohorts(
        rows([("GNWL/40", "MYSTERY/4", "SL", "CNF"), ("GNWL/41", "RAC 2", "SL", "CNF")])
    )
    assert summary.excluded.get("asof_status_unknown") == 1
    assert summary.rows_used == 1
    assert ("SL", "GN", "UNKNOWN") not in summary.cohorts


def test_queue_position_movement_does_not_change_the_cohort():
    """Only the status category keys a cohort; the position is a separate feature."""
    summary = fit_cohorts(rows([("RLWL/80", "GNWL/3", "SL", "CNF")]))
    assert ("SL", "GN", "WL") in summary.cohorts


# ── Scoring ────────────────────────────────────────────────────────────────────


def test_scoring_queries_the_cohort_the_row_was_fitted_into():
    """Hand check on the RAC cell: counts 10/90/5/0/0, alpha 1 → denominator 110."""
    card = score_partition(
        rows([("GNWL/40", "RAC 1", "SL", "CNF")]),
        estimator(),
        prevalence=PREVALENCE,
        partition="test",
    )
    assert card.scored_rows == 1
    assert card.brier == pytest.approx(_brier(RAC_CELL, "CNF"), abs=1e-6)
    assert card.brier != pytest.approx(_brier(WL_CELL, "CNF"), abs=1e-6)


def test_scoring_a_row_without_a_later_look_uses_the_booked_cohort():
    card = score_partition(
        rows([("GNWL/40", "", "SL", "CNF")]), estimator(), prevalence=PREVALENCE, partition="test"
    )
    assert card.brier == pytest.approx(_brier(WL_CELL, "CNF"), abs=1e-6)


def test_scoring_an_unmappable_observed_status_abstains():
    card = score_partition(
        rows([("GNWL/40", "MYSTERY/4", "SL", "CNF")]),
        estimator(),
        prevalence=PREVALENCE,
        partition="test",
    )
    assert card.abstained_rows == 1
    assert card.scored_rows == 0
    assert card.brier is None


def test_a_missing_exact_cohort_falls_back_to_the_broad_cell_and_is_scored():
    table = {("3A", "GN", BROAD_COHORT_STATUS): {"CNF": 50, "RAC": 10, "WL": 40, "CANCELLED": 0, "OTHER": 0}}
    card = score_partition(
        rows([("GNWL/40", "RAC 1", "3A", "CNF")]),
        estimator(table),
        prevalence=PREVALENCE,
        partition="test",
    )
    assert card.scored_rows == 1
    assert card.brier == pytest.approx(_brier(table[("3A", "GN", BROAD_COHORT_STATUS)], "CNF"), abs=1e-6)


def test_segments_name_both_the_booked_and_the_observed_status():
    card = score_partition(
        rows([("GNWL/40", "RAC 1", "SL", "CNF")]),
        estimator(),
        prevalence=PREVALENCE,
        partition="test",
    )
    dimensions = {segment.dimension for segment in card.segments}
    assert {"asof_status", "initial_status", "class_code", "quota_code"} <= dimensions
    asof = {segment.value for segment in card.segments if segment.dimension == "asof_status"}
    initial = {segment.value for segment in card.segments if segment.dimension == "initial_status"}
    assert asof == {"RAC"}
    assert initial == {"WL"}


def test_a_frame_with_no_status_column_cannot_be_scored():
    frame = rows([("GNWL/10", "", "SL", "CNF")]).drop(columns=["initial_status", "current_status"])
    with pytest.raises(DatasetValidationError, match="as-of status"):
        score_partition(frame, estimator(), prevalence=PREVALENCE, partition="test")


# ── Serving ────────────────────────────────────────────────────────────────────


def test_a_served_request_is_answered_from_the_observed_status(tmp_path):
    record = served(serving_engine(tmp_path))
    outcome = record.passenger_outcomes[0]
    assert outcome.is_supported()
    assert outcome.p_cnf == pytest.approx(_smoothed(RAC_CELL, "CNF"))
    assert "SL/GN/RAC" in outcome.basis


def test_a_served_request_with_no_later_look_uses_its_booked_status(tmp_path):
    record = served(serving_engine(tmp_path), current="GNWL/12")
    outcome = record.passenger_outcomes[0]
    assert outcome.p_cnf == pytest.approx(_smoothed(WL_CELL, "CNF"))
    assert "SL/GN/WL" in outcome.basis


def test_a_served_request_with_an_unreadable_status_abstains(tmp_path):
    record = served(serving_engine(tmp_path), current="MYSTERY/4")
    outcome = record.passenger_outcomes[0]
    assert not outcome.is_supported()
    assert outcome.p_cnf is None


# ── The three paths together ───────────────────────────────────────────────────


def test_every_row_of_a_moving_dataset_is_scored_by_the_table_fitted_from_it(tmp_path):
    """Fit and score the same fixture: coverage can only be 100% if the keys agree."""
    frame = load_dataset_file(write_moving_dataset(tmp_path))
    summary = fit_cohorts(frame)
    card = score_partition(
        frame,
        estimator(summary.cohorts, min_sample_threshold=1),
        prevalence={"CNF": 0.5, "RAC": 0.0, "WL": 0.5, "CANCELLED": 0.0, "OTHER": 0.0},
        partition="test",
    )
    assert card.coverage == 1.0
    assert card.abstained_rows == 0
    assert card.rows == len(frame)


def test_fitted_keys_and_query_keys_use_one_normalisation(tmp_path):
    frame = load_dataset_file(write_moving_dataset(tmp_path))
    summary = fit_cohorts(frame)
    statuses = asof_statuses(frame)
    for index, row in frame.iterrows():
        assert cohort_key(str(row["class_code"]), "gn", statuses[index].normalized.value) in summary.cohorts


def test_a_frame_without_any_status_column_is_refused_before_fitting():
    frame = rows([("GNWL/10", "", "SL", "CNF")]).drop(columns=["initial_status", "current_status"])
    with pytest.raises(DatasetValidationError, match="as-of status"):
        require_status_columns(frame, where="fit_cohorts")
    with pytest.raises(DatasetValidationError, match="as-of status"):
        fit_cohorts(frame)
