"""What the evaluation report says, and what it refuses to say.

The report is what a later reader judges the model by, so these tests check the
wording as well as the arithmetic: a configuration that beats the base rate on the
full distribution but not on the target's own event has to appear both ways.
"""

import json

import pytest

from railconfirm.data.preprocessing import chronological_split
from railconfirm.domain.status import MAPPING_VERSION
from railconfirm.inference.baseline import (
    COHORT_FEATURES,
    COHORT_STATUS_SEMANTICS,
    FrequencyTableProvenance,
)
from railconfirm.training.fitter import FitSummary
from railconfirm.training.metrics import (
    GROUP_METRIC_KEYS,
    GROUP_STRUCTURAL_FIELDS,
    METRIC_KEYS,
    STRUCTURAL_FIELDS,
    GroupScorecard,
    build_estimator,
    score_partition,
)
from railconfirm.training.report import build_report, write_report
from tests.support.artifacts import artifact_metadata
from tests.training.test_metrics import PREVALENCE, rows

# Mass leaks onto RAC and WL, so the smoothed CNF probability lands just under the
# 0.5 base rate: the distribution score improves while the headline event does not.
LEAKY = {("SL", "GN", "WL"): {"CNF": 50, "RAC": 20, "WL": 25, "CANCELLED": 5, "OTHER": 0}}
CONCLUSIVE = {("SL", "GN", "WL"): {"CNF": 90, "RAC": 0, "WL": 10, "CANCELLED": 0, "OTHER": 0}}


def estimator_for(cohorts: dict) -> object:
    return build_estimator(
        cohorts,
        FrequencyTableProvenance(
            dataset_id="report-fixture",
            sha256="d" * 64,
            source_reference="test",
            approval_status="approved",
            is_synthetic=False,
            mapping_version=MAPPING_VERSION,
        ),
        min_sample_threshold=5,
        laplace_alpha=1.0,
    )


def fit_summary(cohorts: dict) -> FitSummary:
    summary = FitSummary(rows_seen=100, rows_used=100)
    summary.cohorts = cohorts
    summary.window = ("2026-04-01", "2026-04-12")
    return summary


def make_report(
    *,
    cohorts: dict,
    frame: object,
    target: str = "final_chart_cnf",
    artifact_target: str | None = None,
):
    estimator = estimator_for(cohorts)
    scored = [
        score_partition(
            frame,
            estimator,
            prevalence=PREVALENCE,
            partition=partition,
            target=target,
        )
        for partition in ("validation", "test")
    ]
    return build_report(
        metadata=artifact_metadata(target=artifact_target or target),
        dataset_id="report-fixture",
        dataset_sha256="d" * 64,
        dataset_rows=len(frame),
        fit=fit_summary(cohorts),
        split=chronological_split(frame),
        validation=scored[0],
        test=scored[1],
        generated_on="2026-05-01",
    )


def test_the_report_states_which_features_the_estimator_actually_reads():
    """The baseline reads three values; the report must not credit it with eight."""
    report = make_report(cohorts=CONCLUSIVE, frame=rows([("GNWL/10", "CNF")] * 4))
    features = report.to_dict()["features"]
    assert features["used_by_estimator"] == list(COHORT_FEATURES)
    assert {"lead_days", "queue_ratio", "init_position"} <= set(features["not_used_by_estimator"])
    assert set(features["columns"]) >= set(features["used_by_estimator"])
    assert features["cohort_semantics"] == COHORT_STATUS_SEMANTICS

    summary = report.summary()
    assert "read by the estimator: class_code, quota_code, asof_normalized" in summary
    assert "derived but not read" in summary
    assert "no status column" in summary  # this fixture's FitSummary records none


def test_the_report_describes_the_asof_rule_behind_every_feature():
    report = make_report(cohorts=CONCLUSIVE, frame=rows([("GNWL/10", "CNF")] * 4))
    availability = report.to_dict()["features"]["availability"]
    assert "current_status" in availability
    assert "otherwise initial_status" in availability


def test_the_report_publishes_the_rule_the_fit_recorded():
    """A reader must be able to see which status the counts were keyed by."""
    report = make_report(cohorts=CONCLUSIVE, frame=rows([("GNWL/10", "CNF")] * 4))
    fit = report.to_dict()["fit"]
    assert fit["cohort_semantics"] == COHORT_STATUS_SEMANTICS
    assert fit["asof_status_columns"] == []


def test_the_report_names_the_event_it_scored():
    report = make_report(cohorts=CONCLUSIVE, frame=rows([("GNWL/10", "CNF")] * 4))
    assert report.target_event_classes == ["CNF"]
    assert "event: CNF" in report.summary()

    merged = make_report(
        cohorts=CONCLUSIVE,
        frame=rows([("GNWL/10", "CNF")] * 4),
        target="final_chart_cnf_or_rac",
        artifact_target="final_chart_cnf_or_rac",
    )
    assert merged.target_event_classes == ["CNF", "RAC"]
    assert "event: CNF/RAC" in merged.summary()


def test_the_event_line_lines_up_under_its_partition():
    summary = make_report(cohorts=CONCLUSIVE, frame=rows([("GNWL/10", "CNF")] * 4)).summary()
    widths = {len("Validation: "), len("Test: ")}
    aligned = [
        len(line) - len(line.lstrip())
        for line in summary.splitlines()
        if line.lstrip().startswith("event ")
    ]
    assert len(aligned) == 2
    assert set(aligned) <= widths


def test_a_better_distribution_does_not_hide_a_worse_event(tmp_path):
    """The disagreement case is stated, not averaged away."""
    report = make_report(cohorts=LEAKY, frame=rows([("GNWL/10", "CNF")] * 4))
    assert report.validation.beats_baseline is True
    assert report.validation.event_beats_baseline is False
    joined = " ".join(report.conclusions)
    assert "Brier" in joined
    assert "does not beat its prevalence baseline" in joined
    assert "target event final_chart_cnf (CNF)" in joined
    assert "the distribution and the target event disagree" in joined
    assert "no better than the base rate" in joined


def test_scoring_a_different_target_than_the_artifact_declares_is_a_limitation():
    report = make_report(
        cohorts=CONCLUSIVE,
        frame=rows([("GNWL/10", "CNF")] * 4),
        target="final_chart_cnf_or_rac",
        artifact_target="final_chart_cnf",
    )
    assert any(
        "scored for target 'final_chart_cnf_or_rac'" in item
        and "declares 'final_chart_cnf'" in item
        for item in report.limitations
    )


def test_an_unscored_partition_reports_no_event_verdict():
    # RAC rows have no fitted cohort, so every row abstains and nothing is measured.
    report = make_report(cohorts=CONCLUSIVE, frame=rows([("RAC 4", "CNF")] * 3))
    assert report.validation.brier is None
    assert report.validation.event_brier is None
    joined = " ".join(report.conclusions)
    assert "no score computed" in joined
    assert "target event" not in joined
    assert "n/a" in report.summary()


def test_every_published_metric_is_defined_and_nothing_extra_is():
    report = make_report(cohorts=CONCLUSIVE, frame=rows([("GNWL/10", "CNF")] * 4))
    published = set(report.to_dict()["validation"])
    assert published - STRUCTURAL_FIELDS == METRIC_KEYS
    assert set(report.to_dict()["metric_definitions"]) == set(METRIC_KEYS) | set(
        GROUP_METRIC_KEYS
    )


def test_a_group_figure_cannot_be_published_without_a_definition():
    """The group block is nested, so the top-level coverage check never saw it.

    Every number in it was published with no definition, including three Brier scores of
    a mathematical bound rather than of a probability — the one distinction the project
    insists must never be blurred.
    """
    report = make_report(cohorts=CONCLUSIVE, frame=rows([("GNWL/10", "CNF")] * 4))
    definitions = set(report.to_dict()["metric_definitions"])
    assert set(GroupScorecard.__dataclass_fields__) == GROUP_STRUCTURAL_FIELDS | GROUP_METRIC_KEYS
    assert GROUP_METRIC_KEYS <= definitions
    assert "mathematical bound" in report.to_dict()["metric_definitions"]["queue_brier_all_cnf"]


def test_the_report_serialises_event_metrics_byte_stably(tmp_path):
    first = write_report(
        make_report(cohorts=CONCLUSIVE, frame=rows([("GNWL/10", "CNF")] * 4)),
        tmp_path / "a" / "report.json",
    )
    second = write_report(
        make_report(cohorts=CONCLUSIVE, frame=rows([("GNWL/10", "CNF")] * 4)),
        tmp_path / "b" / "report.json",
    )
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["validation"]["event_brier"] == pytest.approx(0.017778, abs=1e-6)
    assert payload["validation"]["event_baseline_brier"] == pytest.approx(0.25)
    assert payload["test"]["event_log_loss"] == payload["validation"]["event_log_loss"]
    assert first.read_bytes() == second.read_bytes()
