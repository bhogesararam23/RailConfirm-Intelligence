"""Fitting, scoring and serving one model, with the queue position in all three.

Synthetic rows only. The rule this file exists to enforce is the one ADR-0013 taught the
repository: the inputs a model is fitted with, the inputs it is scored with, and the inputs a
request supplies must be the same values. A second estimator multiplies the ways that can go
wrong, so each of the three paths is asserted here rather than assumed.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from railconfirm.data.preprocessing import chronological_split
from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.domain.journey import make_journey
from railconfirm.domain.passenger import make_observation
from railconfirm.domain.prediction import AbstentionReason, PredictionTarget
from railconfirm.domain.status import MAPPING_VERSION, parse_status
from railconfirm.inference.artifacts import (
    ESTIMATOR_HISTORICAL_FREQUENCY,
    load_artifact,
)
from railconfirm.inference.baseline import COHORT_FEATURES
from railconfirm.inference.engine import InferenceEngine
from railconfirm.inference.queue import (
    QUEUE_ESTIMATOR_ID,
    QUEUE_FEATURES,
)
from railconfirm.inference.registry import ModelRegistry
from railconfirm.training.dataset import load_approved_dataset
from railconfirm.training.decay import run_frozen_decay
from railconfirm.training.fitter import (
    fit_baseline,
    fit_cohorts,
    write_fitted_artifact,
)
from railconfirm.training.metrics import (
    evaluation_provenance,
    score_partition,
    score_rows,
)
from railconfirm.training.report import build_report
from tests.support.artifacts import POSITION_BANDS
from tests.support.artifacts import write_fixture_artifact as write
from tests.support.datasets import (
    HEADER,
    SYNTHETIC_MARK,
    write_approved_manifest,
)

JOURNEY = make_journey(
    train_number="12301",
    journey_date=date(2026, 11, 15),
    boarding_station="NDLS",
    destination_station="HWH",
    class_code="SL",
    quota_code="GN",
)


def write_position_dataset(directory: Path, rows: list[tuple[str, str, str]]) -> Path:
    """Rows of (journey_date, initial_status, final_chart_status), labelled synthetic."""
    lines = [
        f"12301,{date},SL,GN,{status},{final},2026-03-01,B{index:04d},P{index:04d},true"
        for index, (date, status, final) in enumerate(rows)
    ]
    path = directory / "synthetic-positions.csv"
    path.write_text(
        SYNTHETIC_MARK + "\n" + HEADER + "\n" + "\n".join(lines) + "\n", encoding="utf-8"
    )
    return path


def fitted(tmp_path: Path, rows: list[tuple[str, str, str]], **kwargs):
    csv = write_position_dataset(tmp_path, rows)
    manifest = write_approved_manifest(
        csv, tmp_path, dataset_id="synthetic-positions"
    )
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    defaults = {"version": "pos_v1", "min_sample_threshold": 1}
    defaults.update(kwargs)
    return fit_baseline(dataset, **defaults), dataset


def cycle_rows(date: str, positions: list[int], *, label_every: int = 2):
    """One row per position, confirming on every `label_every`-th row."""
    return [
        (
            date,
            f"GNWL/{position}",
            "CNF" if index % label_every == 0 else "WL/5",
        )
        for index, position in enumerate(positions)
    ]


# ── Fitting the bands ──────────────────────────────────────────────────────────


def frame_of(entries: list[tuple[int | None, str]]) -> pd.DataFrame:
    """One row per (as-of position, final label), all in the SL/GN cohort on one date."""
    return pd.DataFrame(
        [
            {
                "train_number": "12301",
                "journey_date": "2026-04-01",
                "class_code": "SL",
                "quota_code": "GN",
                "initial_status": "GNWL" if position is None else f"GNWL/{position}",
                "current_status": "",
                "final_chart_status": label,
                "observation_date": "2026-03-01",
                "booking_group_id": f"B{index:04d}",
                "passenger_record_id": f"P{index:04d}",
            }
            for index, (position, label) in enumerate(entries)
        ]
    )


def test_the_position_estimator_fills_one_cell_per_band():
    summary = fit_cohorts(
        frame_of([(1, "CNF"), (2, "WL/5"), (5, "CNF"), (10, "WL/5"), (20, "CNF"), (40, "WL/5")]),
        with_bands=True,
    )
    assert {key[3] for key in summary.bands} == {
        "1",
        "2-3",
        "4-7",
        "8-15",
        "16-31",
        "32-63",
    }
    assert summary.bands[("SL", "GN", "WL", "1")] == {"CNF": 1}
    assert summary.bands[("SL", "GN", "WL", "32-63")] == {"WL": 1}


def test_the_band_cells_add_up_to_the_cohort_cell_they_belong_to():
    summary = fit_cohorts(
        frame_of([(1, "CNF"), (3, "CNF"), (7, "WL/5"), (30, "CNF")]), with_bands=True
    )
    cohort = summary.cohorts[("SL", "GN", "WL")]
    band_total = sum(
        sum(counts.values())
        for key, counts in summary.bands.items()
        if key[:3] == ("SL", "GN", "WL")
    )
    assert band_total == sum(cohort.values()) == 4


def test_a_row_without_a_position_counts_in_the_cohort_and_in_no_band():
    summary = fit_cohorts(frame_of([(None, "CNF"), (4, "WL/5")]), with_bands=True)
    assert sum(summary.cohorts[("SL", "GN", "WL")].values()) == 2
    # Counted once against the exact cohort and once against the broad fallback, exactly
    # as a positioned row is: what must not happen is a band cell for an unknown position.
    assert (
        sum(
            sum(counts.values())
            for key, counts in summary.bands.items()
            if key[:3] == ("SL", "GN", "WL")
        )
        == 1
    )
    assert summary.rows_without_position == 1


def test_fitting_without_bands_changes_nothing_about_the_cohort_table():
    entries = [(1, "CNF"), (4, "WL/5")]
    plain = fit_cohorts(frame_of(entries))
    assert plain.bands == {}
    assert plain.rows_without_position == 0
    assert plain.cohorts == fit_cohorts(frame_of(entries), with_bands=True).cohorts


# ── Fitting through the gate ───────────────────────────────────────────────────


def fit_rows(tmp_path: Path, rows, **kwargs):
    """Fit through the real gate, so nothing here bypasses a rule."""
    defaults = {"version": "pos_v1", "min_sample_threshold": 1}
    defaults.update(kwargs)
    csv = write_position_dataset(tmp_path, rows)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="synthetic-positions")
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    return fit_baseline(dataset, **defaults), dataset


def spread(positions: list[int], dates: int = 6) -> list[tuple[str, str, str]]:
    """Positions round-robin over `dates` journey dates, confirming every other row."""
    days = [f"2026-04-{day:02d}" for day in range(1, dates + 1)]
    return [
        (days[index % dates], f"GNWL/{position}", "CNF" if index % 2 == 0 else "WL/5")
        for index, position in enumerate(positions)
    ]


def test_the_default_fit_stays_the_frequency_artifact_it_already_was(tmp_path):
    fitted_baseline, _ = fit_rows(tmp_path, spread(list(range(1, 25))))
    assert fitted_baseline.metadata.estimator == ESTIMATOR_HISTORICAL_FREQUENCY
    assert tuple(fitted_baseline.metadata.features_used) == COHORT_FEATURES
    assert fitted_baseline.bands == {}
    path = write_fitted_artifact(fitted_baseline, tmp_path / "pos_v1.json")
    assert '"bands"' not in path.read_text(encoding="utf-8")
    assert path.read_text(encoding="utf-8").count("frequency-baseline/2") == 1


def test_a_position_artifact_declares_the_estimator_the_features_and_the_band_floor(tmp_path):
    fitted_baseline, _ = fit_rows(
        tmp_path, spread(list(range(1, 25))), estimator=QUEUE_ESTIMATOR_ID, min_band_rows=3
    )
    metadata = fitted_baseline.metadata
    assert metadata.estimator == QUEUE_ESTIMATOR_ID
    assert tuple(metadata.features_used) == QUEUE_FEATURES
    assert metadata.min_band_rows == 3
    assert metadata.cohort_semantics == "asof_status_v1"
    assert any("fixed doubling bands" in item for item in metadata.limitations)
    assert not any("queue positions, queue ratio" in item for item in metadata.limitations)


def test_an_estimator_this_build_cannot_run_is_refused_rather_than_defaulted(tmp_path):
    with pytest.raises(DatasetValidationError, match="estimator"):
        fit_rows(tmp_path, spread([1, 2, 3]), estimator="catboost_baseline")


def test_the_position_cells_come_from_the_training_partition_only(tmp_path):
    """The locked period must not be inside the counts it is later judged by."""
    rows = [
        *[(f"2026-04-{day:02d}", "GNWL/1", "CNF") for day in (1, 2, 3, 4)],
        *[(f"2026-04-{day:02d}", "GNWL/40", "WL/5") for day in (1, 2, 3, 4)],
        *[(f"2026-04-{day:02d}", "GNWL/9", "CNF") for day in (5, 6, 7, 8)],
    ]
    fitted_baseline, dataset = fit_rows(
        tmp_path, rows, estimator=QUEUE_ESTIMATOR_ID, train_frac=0.5, val_frac=0.25
    )
    train_only = chronological_split(
        dataset.frame, train_frac=0.5, val_frac=0.25, gap_days=0
    )
    assert fitted_baseline.bands == fit_cohorts(train_only.train, with_bands=True).bands
    assert ("SL", "GN", "WL", "8-15") not in fitted_baseline.bands


# ── Scoring with the position the as-of status carries ─────────────────────────


def test_scoring_passes_the_same_asof_position_a_request_would_supply():
    """Different positions in one cohort must produce different scored rows."""
    frame = pd.DataFrame(
        [
            {
                "train_number": "12301",
                "journey_date": "2026-04-01",
                "class_code": "SL",
                "quota_code": "GN",
                "initial_status": f"GNWL/{position}",
                "current_status": "",
                "final_chart_status": "WL/5",
                "observation_date": "2026-03-01",
                "booking_group_id": f"B{index}",
                "passenger_record_id": f"P{index}",
            }
            for index, position in enumerate([1, 40])
        ]
    )
    estimator = _position_estimator()
    rows = score_rows(frame, estimator, target=PredictionTarget.FINAL_CHART_CNF.value)
    assert len(rows.rows) == 2
    assert rows.rows[0].event_predicted != rows.rows[1].event_predicted


def test_a_frequency_model_scores_the_same_cohort_identically_whatever_the_position():
    frame = pd.DataFrame(
        [
            {
                "train_number": "12301",
                "journey_date": "2026-04-01",
                "class_code": "SL",
                "quota_code": "GN",
                "initial_status": f"GNWL/{position}",
                "current_status": "",
                "final_chart_status": "WL/5",
                "observation_date": "2026-03-01",
                "booking_group_id": f"B{index}",
                "passenger_record_id": f"P{index}",
            }
            for index, position in enumerate([1, 40])
        ]
    )
    from railconfirm.inference.baseline import HistoricalFrequencyBaseline

    baseline = HistoricalFrequencyBaseline(min_sample_threshold=1, laplace_alpha=1.0)
    baseline.load_frequency_table(
        {("SL", "GN", "WL"): {"CNF": 10, "WL": 30}},
        evaluation_provenance(
            "position-parity",
            "b" * 64,
            "test",
            "approved",
            is_synthetic=False,
            mapping_version=MAPPING_VERSION,
        ),
    )
    rows = score_rows(frame, baseline, target=PredictionTarget.FINAL_CHART_CNF.value)
    assert rows.rows[0].event_predicted == rows.rows[1].event_predicted


def test_a_scored_partition_of_a_position_model_reports_both_cohorts_and_bands():
    frame = pd.DataFrame(
        [
            {
                "train_number": "12301",
                "journey_date": "2026-04-01",
                "class_code": "SL",
                "quota_code": "GN",
                "initial_status": f"GNWL/{position}",
                "current_status": "",
                "final_chart_status": "CNF" if index % 2 == 0 else "WL/5",
                "observation_date": "2026-03-01",
                "booking_group_id": f"B{index}",
                "passenger_record_id": f"P{index}",
            }
            for index, position in enumerate([1, 2, 3, 4, 5, 6, 7, 8])
        ]
    )
    card = score_partition(
        frame,
        _position_estimator(),
        prevalence={"CNF": 0.5, "RAC": 0.0, "WL": 0.5, "CANCELLED": 0.0, "OTHER": 0.0},
        partition="validation",
    )
    assert card.scored_rows == 8
    assert card.segment_calibration  # every scorecard keeps the subgroup measurement


def _position_estimator():
    from railconfirm.inference.queue import CohortPositionBaseline

    estimator = CohortPositionBaseline(
        min_sample_threshold=1, laplace_alpha=1.0, min_band_rows=1
    )
    estimator.load_tables(
        {("SL", "GN", "WL"): {"CNF": 10, "WL": 30}},
        {
            ("SL", "GN", "WL", "1"): {"CNF": 9, "WL": 1},
            ("SL", "GN", "WL", "32-63"): {"CNF": 1, "WL": 9},
        },
        evaluation_provenance(
            "position-parity",
            "b" * 64,
            "test",
            "approved",
            is_synthetic=False,
            mapping_version=MAPPING_VERSION,
        ),
    )
    return estimator


# ── Round trip through the artifact, then serve ────────────────────────────────


def observations(*raws):
    from datetime import UTC, datetime

    as_of = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
    outcomes = []
    for index, raw in enumerate(raws):
        observed_at = datetime(2026, 10, 21, 7, 30, tzinfo=UTC)
        obs = make_observation(
            raw, source="fixture", observed_at=observed_at, ingested_at=as_of
        )
        outcomes.append(
            {
                "passenger_id": f"p-{index}",
                "original_obs": obs,
                "current_obs": obs,
            }
        )
    return outcomes


def served(tmp_path: Path, *raws, version: str = "fixture_v1"):
    from datetime import UTC, datetime

    engine = InferenceEngine(
        registry=ModelRegistry(models_dir=tmp_path, active_version=version)
    )
    return engine.predict(
        JOURNEY,
        observations(*raws),
        prediction_at=datetime(2026, 10, 21, 8, 0, tzinfo=UTC),
    )


def test_a_promoted_position_artifact_answers_by_queue_position(tmp_path):
    """A cohort is not one number: depth in the queue has to change the answer served.

    The artifact is hand-written rather than fitted because a fitted fixture is synthetic
    and the registry will not serve synthetic provenance — that gate is asserted elsewhere.
    """
    write(tmp_path, bands=POSITION_BANDS)
    record = served(tmp_path, "GNWL/1", "GNWL/40")
    shallow, deep = record.passenger_outcomes
    assert shallow.is_supported() and deep.is_supported()
    assert shallow.p_cnf > deep.p_cnf
    assert "band=1" in shallow.basis
    assert "band=32-63" in deep.basis
    assert record.model_version == "fixture_v1"


def test_a_request_that_gives_no_position_is_answered_from_the_cohort_and_says_so(tmp_path):
    write(tmp_path, bands=POSITION_BANDS)
    outcome = served(tmp_path, "GNWL").passenger_outcomes[0]
    assert outcome.is_supported()
    assert "position unavailable" in outcome.basis


def test_a_fitted_position_artifact_round_trips_into_the_model_that_scored_it(tmp_path):
    """No serving gate involved: the cells that were fitted must be the cells that load."""
    fitted_baseline, _ = fit_rows(
        tmp_path, spread([1, 2, 3, 4, 5, 6, 7, 8]), estimator=QUEUE_ESTIMATOR_ID
    )
    path = write_fitted_artifact(fitted_baseline, tmp_path / "pos_v1.json")
    loaded = load_artifact(
        path,
        expected_version="pos_v1",
        expected_target=PredictionTarget.FINAL_CHART_CNF.value,
        max_bytes=1_000_000,
    )
    assert loaded.metadata.estimator == QUEUE_ESTIMATOR_ID
    assert loaded.bands == fitted_baseline.bands

    from_artifact = loaded.estimator_for(
        evaluation_provenance(
            "round-trip",
            "c" * 64,
            "test",
            "approved",
            is_synthetic=False,
            mapping_version=MAPPING_VERSION,
        )
    )
    from_fitted = fitted_baseline.estimator_for(
        evaluation_provenance(
            "round-trip",
            "c" * 64,
            "test",
            "approved",
            is_synthetic=False,
            mapping_version=MAPPING_VERSION,
        )
    )
    for raw, position in (("GNWL/1", 1), ("GNWL/40", 40)):
        answers = [
            estimator.estimate(
                passenger_id="p-1",
                asof_status=parse_status(raw),
                class_code="SL",
                quota_code="GN",
                asof_position=position,
            )
            for estimator in (from_artifact, from_fitted)
        ]
        assert answers[0].p_cnf == answers[1].p_cnf
        assert answers[0].basis == answers[1].basis

    # A fitted fixture is synthetic, and the serving construction of the same cells must
    # abstain: identical numbers, different gate. That is the difference between proving
    # arithmetic runs and answering a passenger.
    refusing = loaded.estimator().estimate(
        passenger_id="p-1",
        asof_status=parse_status("GNWL/1"),
        class_code="SL",
        quota_code="GN",
        asof_position=1,
    )
    assert refusing.p_cnf is None
    assert refusing.abstention_reason is AbstentionReason.NO_APPROVED_DATA


def test_the_position_artifact_still_flows_through_the_frozen_decay_path(tmp_path):
    """The cutoff contract is per-estimator: four features is correct for this model."""
    rows = [
        *cycle_rows("2026-04-01", [1, 2, 3, 4]),
        *cycle_rows("2026-04-02", [5, 6, 7, 8]),
        *cycle_rows("2026-04-03", [9, 10, 11, 12]),
        *cycle_rows("2026-04-04", [13, 14, 15, 16]),
    ]
    csv = write_position_dataset(tmp_path, rows)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="synthetic-positions")
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    fitted_baseline = fit_baseline(
        dataset,
        version="pos_v1",
        estimator=QUEUE_ESTIMATOR_ID,
        min_sample_threshold=1,
        train_frac=0.5,
        val_frac=0.25,
    )
    path = write_fitted_artifact(fitted_baseline, tmp_path / "pos_v1.json")
    loaded = load_artifact(
        path,
        expected_version="pos_v1",
        expected_target=PredictionTarget.FINAL_CHART_CNF.value,
        max_bytes=1_000_000,
    )
    result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
    assert result.horizon_count >= 2
    assert all(score.cohort_count == len(loaded.cohorts) for score in result.scores)


def test_decay_scores_the_model_the_artifact_declared_not_the_one_that_was_handiest(
    tmp_path,
):
    """Regression: decay once built every artifact with the frequency builder.

    Two artifacts fitted from the same rows on the same window differ only in whether the
    band cells are read, so identical decay numbers would mean the position model was never
    actually evaluated — the same class of mistake ADR-0013 records for cohort keys.
    """
    rows = [
        *cycle_rows("2026-04-01", [1, 2, 3, 4]),
        *cycle_rows("2026-04-02", [5, 6, 7, 8]),
        *cycle_rows("2026-04-03", [9, 10, 11, 12]),
        *cycle_rows("2026-04-04", [13, 14, 15, 16]),
        *cycle_rows("2026-04-05", [17, 18, 19, 20]),
        *cycle_rows("2026-04-06", [21, 22, 23, 24]),
    ]
    csv = write_position_dataset(tmp_path, rows)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="synthetic-positions")
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    numbers = {}
    for version, estimator_id in (
        ("flat_v1", None),
        ("pos_v1", QUEUE_ESTIMATOR_ID),
    ):
        kwargs = {"version": version, "estimator": estimator_id} if estimator_id else {"version": version}
        fitted_baseline = fit_baseline(
            dataset, min_sample_threshold=1, train_frac=0.5, val_frac=0.25, **kwargs
        )
        path = write_fitted_artifact(fitted_baseline, tmp_path / f"{version}.json")
        loaded = load_artifact(
            path,
            expected_version=version,
            expected_target=PredictionTarget.FINAL_CHART_CNF.value,
            max_bytes=1_000_000,
        )
        result = run_frozen_decay(dataset, loaded, horizon_dates=1, step_dates=1)
        numbers[version] = [score.scorecard.event_brier for score in result.scores]
    assert loaded.metadata.estimator == QUEUE_ESTIMATOR_ID
    assert numbers["flat_v1"] != numbers["pos_v1"]


def test_a_position_artifact_with_the_wrong_feature_declaration_is_refused_by_decay(tmp_path):
    from dataclasses import replace as dataclass_replace

    from railconfirm.inference.artifacts import LoadedArtifact

    rows = [
        *cycle_rows("2026-04-01", [1, 2, 3, 4]),
        *cycle_rows("2026-04-02", [5, 6, 7, 8]),
        *cycle_rows("2026-04-03", [9, 10, 11, 12]),
        *cycle_rows("2026-04-04", [13, 14, 15, 16]),
    ]
    csv = write_position_dataset(tmp_path, rows)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="synthetic-positions")
    dataset = load_approved_dataset(csv, manifest, allow_synthetic_for_testing=True)
    fitted_baseline = fit_baseline(
        dataset,
        version="pos_v1",
        estimator=QUEUE_ESTIMATOR_ID,
        min_sample_threshold=1,
        train_frac=0.5,
        val_frac=0.25,
    )
    path = write_fitted_artifact(fitted_baseline, tmp_path / "pos_v1.json")
    loaded = load_artifact(
        path,
        expected_version="pos_v1",
        expected_target=PredictionTarget.FINAL_CHART_CNF.value,
        max_bytes=1_000_000,
    )
    stale = LoadedArtifact(
        metadata=dataclass_replace(loaded.metadata, features_used=COHORT_FEATURES),
        cohorts=loaded.cohorts,
        bands=loaded.bands,
        path=loaded.path,
    )
    with pytest.raises(DatasetValidationError, match="features_used"):
        run_frozen_decay(dataset, stale, horizon_dates=1, step_dates=1)


def test_the_report_says_which_estimator_was_fitted_and_how_many_cells_it_has(tmp_path):
    fitted_baseline, dataset = fit_rows(
        tmp_path, spread([1, 2, 3, 4]), estimator=QUEUE_ESTIMATOR_ID
    )
    card = score_partition(
        dataset.frame,
        fitted_baseline.estimator_for(
            evaluation_provenance(
                dataset.dataset_id,
                dataset.sha256,
                "test",
                "approved",
                is_synthetic=True,
                mapping_version=MAPPING_VERSION,
            )
        ),
        prevalence=fitted_baseline.prevalence,
        partition="validation",
    )
    report = build_report(
        metadata=fitted_baseline.metadata,
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset.sha256,
        dataset_rows=dataset.report.total_rows,
        fit=fitted_baseline.summary,
        split=fitted_baseline.split,
        validation=card,
        test=None,
        generated_on="2026-10-24",
    )
    payload = report.to_dict()
    assert payload["fit"]["estimator"] == QUEUE_ESTIMATOR_ID
    assert payload["fit"]["band_count"] == len(fitted_baseline.bands)
    assert payload["features"]["used_by_estimator"] == list(QUEUE_FEATURES)
    assert "asof_position" not in payload["features"]["not_used_by_estimator"]


# ── The command line ───────────────────────────────────────────────────────────

from railconfirm.training.__main__ import main  # noqa: E402
from tests.support.datasets import write_balanced_dataset  # noqa: E402


def gate_files(tmp_path: Path):
    csv = write_balanced_dataset(tmp_path, count=240)
    manifest = write_approved_manifest(csv, tmp_path, dataset_id="synthetic-balanced-fixture")
    return csv, manifest


def test_the_fit_command_can_write_a_position_artifact(tmp_path, capsys):
    csv, manifest = gate_files(tmp_path)
    code = main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "pos_cli_v1",
            "--out",
            str(tmp_path / "pos_cli_v1.json"),
            "--estimator",
            QUEUE_ESTIMATOR_ID,
            "--min-sample-threshold",
            "5",
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert QUEUE_ESTIMATOR_ID in out
    assert "Bands:" in out
    loaded = load_artifact(
        tmp_path / "pos_cli_v1.json",
        expected_version="pos_cli_v1",
        expected_target=PredictionTarget.FINAL_CHART_CNF.value,
        max_bytes=1_000_000,
    )
    assert loaded.metadata.estimator == QUEUE_ESTIMATOR_ID
    assert loaded.bands


def test_the_fit_command_refuses_an_estimator_it_cannot_serve(tmp_path, capsys):
    csv, manifest = gate_files(tmp_path)
    code = main(
        [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            "pos_cli_v1",
            "--out",
            str(tmp_path / "pos_cli_v1.json"),
            "--estimator",
            "random_forest_baseline",
            "--allow-synthetic-for-testing",
        ]
    )
    assert code == 1
    assert "estimator" in capsys.readouterr().err.lower()
    assert not (tmp_path / "pos_cli_v1.json").exists()


def test_evaluate_scores_a_position_artifact_with_its_band_cells(tmp_path, capsys):
    """A position artifact scored by the frequency builder would ignore half the model.

    The two runs below read the same rows: if the band cells were dropped, the numbers
    would be identical, which is exactly the failure this asserts against.
    """
    csv, manifest = gate_files(tmp_path)
    for version, estimator_id in (
        ("flat_v1", None),
        ("pos_v1", QUEUE_ESTIMATOR_ID),
    ):
        argv = [
            "fit",
            str(csv),
            str(manifest),
            "--version",
            version,
            "--out",
            str(tmp_path / f"{version}.json"),
            "--min-sample-threshold",
            "5",
            "--allow-synthetic-for-testing",
        ]
        if estimator_id:
            argv += ["--estimator", estimator_id]
        assert main(argv) == 0
        capsys.readouterr()

    scores = {}
    for version in ("flat_v1", "pos_v1"):
        code = main(
            [
                "evaluate",
                str(csv),
                str(manifest),
                "--artifact",
                str(tmp_path / f"{version}.json"),
                "--allow-synthetic-for-testing",
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "calibration" in out or "uncalibrated" in out
        scores[version] = out
    assert scores["flat_v1"] != scores["pos_v1"]
