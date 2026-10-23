"""Tests for probability scoring, checked against hand-computed values.

Synthetic rows only. These verify the arithmetic and the honesty rules of the
report — abstentions excluded, counts published, baselines computed from the
training period — not any claim about railways.
"""

import math

import pandas as pd
import pytest

from railconfirm.domain.prediction import PredictionTarget
from railconfirm.domain.status import MAPPING_VERSION
from railconfirm.inference.baseline import FrequencyTableProvenance
from railconfirm.training.metrics import (
    OUTCOME_CLASSES,
    TARGET_EVENTS,
    _binary_log_loss,
    _brier_one,
    _event_probability,
    _log_loss_one,
    build_estimator,
    score_partition,
)

COHORTS = {("SL", "GN", "WL"): {"CNF": 90, "RAC": 0, "WL": 10, "CANCELLED": 0, "OTHER": 0}}
PREVALENCE = {"CNF": 0.5, "RAC": 0.0, "WL": 0.5, "CANCELLED": 0.0, "OTHER": 0.0}


def estimator(threshold: int = 5):
    return build_estimator(
        COHORTS,
        FrequencyTableProvenance(
            dataset_id="scoring-fixture",
            sha256="c" * 64,
            source_reference="test",
            approval_status="approved",
            is_synthetic=False,
            mapping_version=MAPPING_VERSION,
        ),
        min_sample_threshold=threshold,
        laplace_alpha=1.0,
    )


def rows(specs: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "train_number": "12301",
                "journey_date": "2026-04-01",
                "class_code": "SL",
                "quota_code": "GN",
                "initial_status": initial,
                "current_status": initial,
                "final_chart_status": label,
                "observation_date": "2026-03-20",
                "passenger_record_id": f"P{index}",
            }
            for index, (initial, label) in enumerate(specs)
        ]
    )


def test_brier_of_a_perfect_forecast_is_zero():
    hypothesis = dict.fromkeys(OUTCOME_CLASSES, 0.0)
    hypothesis["CNF"] = 1.0
    truth = dict.fromkeys(OUTCOME_CLASSES, 0.0)
    truth["CNF"] = 1.0
    assert _brier_one(hypothesis, truth) == pytest.approx(0.0)


def test_brier_of_a_worst_forecast_is_two():
    hypothesis = dict.fromkeys(OUTCOME_CLASSES, 0.0)
    hypothesis["WL"] = 1.0
    truth = dict.fromkeys(OUTCOME_CLASSES, 0.0)
    truth["CNF"] = 1.0
    assert _brier_one(hypothesis, truth) == pytest.approx(2.0)


def test_log_loss_of_a_confident_correct_forecast_is_near_zero():
    hypothesis = dict.fromkeys(OUTCOME_CLASSES, 0.0)
    hypothesis["CNF"] = 1.0
    truth = dict.fromkeys(OUTCOME_CLASSES, 0.0)
    truth["CNF"] = 1.0
    assert _log_loss_one(hypothesis, truth) == pytest.approx(0.0, abs=1e-9)


def test_log_loss_penalises_a_confident_wrong_forecast():
    hypothesis = dict.fromkeys(OUTCOME_CLASSES, 0.0)
    hypothesis["WL"] = 1.0
    truth = dict.fromkeys(OUTCOME_CLASSES, 0.0)
    truth["CNF"] = 1.0
    # The floor is 1e-12, so -log(1e-12) is the penalty ceiling.
    assert _log_loss_one(hypothesis, truth) == pytest.approx(-math.log(1e-12))


def test_scores_match_the_smoothing_arithmetic():
    """Hand check: counts 90/0/10/0/0 total 100, alpha 1 over 5 classes → denom 105.

    p_cnf = 91/105, p_wl = 11/105, p_rac = p_cancelled = p_other = 1/105. Observed CNF.
    Brier = (91/105 - 1)^2 + (11/105)^2 + 3 * (1/105)^2
    """
    card = score_partition(
        rows([("GNWL/10", "CNF")]), estimator(), prevalence=PREVALENCE, partition="test"
    )
    p_cnf, p_rac, p_wl = 91 / 105, 1 / 105, 11 / 105
    expected = (p_cnf - 1) ** 2 + p_rac**2 + p_wl**2 + 2 * (1 / 105) ** 2
    assert card.brier == pytest.approx(expected, abs=1e-6)
    assert card.log_loss == pytest.approx(-math.log(p_cnf), abs=1e-6)
    assert card.scored_rows == 1
    assert card.abstained_rows == 0
    assert card.coverage == 1.0


def test_baseline_is_scored_on_the_same_rows():
    card = score_partition(
        rows([("GNWL/10", "CNF")]), estimator(), prevalence=PREVALENCE, partition="test"
    )
    # Prevalence 0.5/0/0.5: Brier = (0.5-1)^2 + 0 + 0.5^2 = 0.5
    assert card.baseline_brier == pytest.approx(0.5, abs=1e-6)
    assert card.brier_skill is not None
    assert card.beats_baseline is True


def test_abstained_rows_are_excluded_not_scored_as_wrong():
    """A row the estimator refuses must not become a free error."""
    frame = rows([("GNWL/10", "CNF"), ("RAC 4", "CNF")])
    # Only a WL cohort is fitted, so an RAC row has no cohort and abstains.
    card = score_partition(frame, estimator(), prevalence=PREVALENCE, partition="test")
    assert card.rows == 2
    assert card.scored_rows == 1
    assert card.abstained_rows == 1
    assert card.coverage == 0.5
    assert card.brier is not None


def test_a_partition_of_only_abstentions_reports_no_score():
    frame = rows([("RAC 4", "CNF"), ("CNF", "WL/2")])
    card = score_partition(frame, estimator(), prevalence=PREVALENCE, partition="test")
    assert card.brier is None
    assert card.beats_baseline is None
    assert card.scored_rows == 0


def test_censored_labels_are_not_scored_as_negative():
    frame = rows([("GNWL/10", "CNF"), ("GNWL/11", "CENSORED")])
    card = score_partition(frame, estimator(), prevalence=PREVALENCE, partition="test")
    assert card.abstained_rows == 1
    assert card.scored_rows == 1
    assert card.outcome_distribution == {"CNF": 1}


def test_segments_publish_their_counts_and_low_sample_flags():
    frame = rows([("GNWL/10", "CNF"), ("GNWL/11", "CNF"), ("GNWL/12", "WL/9")])
    card = score_partition(
        frame, estimator(), prevalence=PREVALENCE, partition="test", min_segment_rows=3
    )
    by_status = {s.value: s for s in card.segments if s.dimension == "initial_status"}
    assert set(by_status) == {"WL"}
    assert by_status["WL"].rows == 3
    assert by_status["WL"].low_sample is False

    # The same slice becomes low-sample once the threshold demands more rows: the
    # flag follows the count, so a thin segment cannot be quoted as a finding.
    strict = score_partition(
        frame, estimator(), prevalence=PREVALENCE, partition="test", min_segment_rows=4
    )
    by_class = {s.value: s for s in strict.segments if s.dimension == "class_code"}
    assert by_class["SL"].rows == 3
    assert by_class["SL"].low_sample is True


def test_reliability_bands_carry_counts():
    frame = rows([("GNWL/10", "CNF") for _ in range(3)] + [("GNWL/11", "WL/4")])
    card = score_partition(frame, estimator(), prevalence=PREVALENCE, partition="test")
    cnf_bands = card.reliability["CNF"]
    assert cnf_bands
    assert sum(band.count for band in cnf_bands) == card.scored_rows
    top = max(cnf_bands, key=lambda band: band.count)
    assert 0.0 <= top.mean_predicted <= 1.0
    assert 0.0 <= top.observed_frequency <= 1.0


def test_scoring_requires_a_label_column():
    frame = rows([("GNWL/10", "CNF")]).drop(columns=["final_chart_status"])
    with pytest.raises(Exception, match="final_chart_status"):
        score_partition(frame, estimator(), prevalence=PREVALENCE, partition="test")


def test_scoring_an_empty_partition_is_refused():
    with pytest.raises(Exception, match="empty"):
        score_partition(rows([]), estimator(), prevalence=PREVALENCE, partition="test")


def test_scorecard_serialises_for_the_report():
    card = score_partition(
        rows([("GNWL/10", "CNF")]), estimator(), prevalence=PREVALENCE, partition="test"
    )
    payload = card.to_dict()
    assert payload["partition"] == "test"
    assert "brier_skill" in payload
    assert isinstance(payload["reliability"], dict)
    assert isinstance(payload["segments"], list)


def test_estimator_is_the_same_object_inference_would_use():
    """Train/serve parity: scoring uses the inference estimator class, not a copy."""
    from railconfirm.domain.status import parse_status
    from railconfirm.inference.baseline import HistoricalFrequencyBaseline

    built = estimator()
    assert isinstance(built, HistoricalFrequencyBaseline)
    outcome = built.estimate("p", parse_status("GNWL/9"), "SL", "GN")
    assert outcome.is_supported()
    assert "SL/GN/WL" in outcome.basis


def test_every_declared_target_has_a_scorable_event():
    """A new PredictionTarget must be scored or the list edited deliberately."""
    assert set(TARGET_EVENTS) == {target.value for target in PredictionTarget}


def test_event_score_uses_the_mass_the_estimator_puts_on_the_event():
    """Hand check against the same smoothed row as the distribution test above."""
    card = score_partition(
        rows([("GNWL/10", "CNF")]), estimator(), prevalence=PREVALENCE, partition="test"
    )
    p_cnf = 91 / 105
    assert card.target == "final_chart_cnf"
    assert card.event_brier == pytest.approx((p_cnf - 1.0) ** 2, abs=1e-6)
    assert card.event_log_loss == pytest.approx(-math.log(p_cnf), abs=1e-6)
    # Prevalence puts 0.5 on CNF and 0.0 on RAC, so the event baseline is (0.5-1)^2.
    assert card.event_baseline_brier == pytest.approx(0.25, abs=1e-6)
    assert card.event_brier_skill == pytest.approx(1 - card.event_brier / 0.25, abs=1e-6)
    assert card.event_beats_baseline is True
    assert sum(band.count for band in card.event_reliability) == 1


def test_the_merged_target_counts_rac_as_the_event_and_the_single_target_does_not():
    frame = rows([("GNWL/10", "RAC 3")])
    cnf_only = score_partition(
        frame, estimator(), prevalence=PREVALENCE, partition="test"
    )
    cnf_or_rac = score_partition(
        frame,
        estimator(),
        prevalence=PREVALENCE,
        partition="test",
        target="final_chart_cnf_or_rac",
    )
    p_cnf, p_rac = 91 / 105, 1 / 105
    # RAC happened: the CNF event failed, so the error is the whole predicted mass.
    assert cnf_only.event_brier == pytest.approx(p_cnf**2, abs=1e-6)
    assert cnf_only.outcome_distribution == {"RAC": 1}
    # The same row satisfies the merged event, so the error shrinks to the gap.
    assert cnf_or_rac.event_brier == pytest.approx((p_cnf + p_rac - 1.0) ** 2, abs=1e-6)
    assert cnf_or_rac.brier == cnf_only.brier
    assert cnf_or_rac.target == "final_chart_cnf_or_rac"


def test_binary_log_loss_is_symmetric_about_the_event():
    assert _binary_log_loss(0.5, 1.0) == pytest.approx(_binary_log_loss(0.5, 0.0))
    assert _binary_log_loss(0.9, 1.0) < _binary_log_loss(0.1, 1.0)
    assert _binary_log_loss(0.0, 1.0) == pytest.approx(-math.log(1e-12), rel=1e-9)


def test_event_probability_sums_only_the_classes_in_the_event():
    distribution = dict.fromkeys(OUTCOME_CLASSES, 0.0)
    distribution["CNF"] = 0.4
    distribution["RAC"] = 0.3
    distribution["WL"] = 0.3
    assert _event_probability(distribution, ("CNF",)) == pytest.approx(0.4)
    assert _event_probability(distribution, ("CNF", "RAC")) == pytest.approx(0.7)


def test_an_undefined_target_is_refused_rather_than_scored_as_another_one():
    with pytest.raises(Exception, match="Cannot score target"):
        score_partition(
            rows([("GNWL/10", "CNF")]),
            estimator(),
            prevalence=PREVALENCE,
            partition="test",
            target="departure_status",
        )


def test_a_partition_of_only_abstentions_reports_no_event_score():
    frame = rows([("RAC 4", "CNF")])
    card = score_partition(frame, estimator(), prevalence=PREVALENCE, partition="test")
    assert card.event_brier is None
    assert card.event_beats_baseline is None
    assert card.event_reliability == []


def test_partition_without_booking_group_id_has_no_group_scorecard():
    frame = rows([("GNWL/10", "CNF"), ("GNWL/10", "WL/5")])
    card = score_partition(frame, estimator(), prevalence=PREVALENCE, partition="test")
    assert card.group is None
    assert card.to_dict()["group"] is None


def test_group_scoring_with_multi_passenger_bookings():
    # 2 rows with group B1 (multi-passenger), 1 row with group B2 (single-passenger)
    frame = pd.DataFrame(
        [
            {
                "train_number": "12301",
                "journey_date": "2026-04-01",
                "class_code": "SL",
                "quota_code": "GN",
                "initial_status": "GNWL/10",
                "current_status": "GNWL/10",
                "final_chart_status": "CNF",
                "observation_date": "2026-03-20",
                "passenger_record_id": "P1",
                "booking_group_id": "B1",
            },
            {
                "train_number": "12301",
                "journey_date": "2026-04-01",
                "class_code": "SL",
                "quota_code": "GN",
                "initial_status": "GNWL/10",
                "current_status": "GNWL/10",
                "final_chart_status": "CNF",
                "observation_date": "2026-03-20",
                "passenger_record_id": "P2",
                "booking_group_id": "B1",
            },
            {
                "train_number": "12301",
                "journey_date": "2026-04-01",
                "class_code": "SL",
                "quota_code": "GN",
                "initial_status": "GNWL/10",
                "current_status": "GNWL/10",
                "final_chart_status": "WL/5",
                "observation_date": "2026-03-20",
                "passenger_record_id": "P3",
                "booking_group_id": "B2",
            },
        ]
    )
    card = score_partition(frame, estimator(), prevalence=PREVALENCE, partition="test")
    assert card.group is not None
    assert card.group.total_groups == 2
    assert card.group.single_passenger_groups == 1
    assert card.group.multi_passenger_groups == 1
    assert card.group.scored_groups == 1
    assert card.group.abstained_groups == 0
    # Group B1: 2 passengers, both p_cnf = 91/105 ~ 0.866667
    # P(all CNF indep) = (91/105)^2 ~ 0.751134
    # P(all CNF queue) = 91/105 ~ 0.866667
    # Observed all CNF = 1.0
    p_indep = round((91 / 105) ** 2, 6)
    p_queue = round(91 / 105, 6)
    assert card.group.brier_all_cnf == pytest.approx((p_indep - 1.0) ** 2, abs=1e-5)
    assert card.group.queue_brier_all_cnf == pytest.approx((p_queue - 1.0) ** 2, abs=1e-5)
    # Queue-clearing Brier is lower (better) than independence Brier when both confirmed!
    assert card.group.queue_brier_all_cnf < card.group.brier_all_cnf
    payload = card.to_dict()
    assert "group" in payload
    assert payload["group"]["total_groups"] == 2


def test_group_scoring_abstained_when_passenger_abstains():
    # Group B1 has one valid passenger and one with unmappable status
    frame = pd.DataFrame(
        [
            {
                "train_number": "12301",
                "journey_date": "2026-04-01",
                "class_code": "SL",
                "quota_code": "GN",
                "initial_status": "GNWL/10",
                "current_status": "GNWL/10",
                "final_chart_status": "CNF",
                "observation_date": "2026-03-20",
                "passenger_record_id": "P1",
                "booking_group_id": "B1",
            },
            {
                "train_number": "12301",
                "journey_date": "2026-04-01",
                "class_code": "SL",
                "quota_code": "GN",
                "initial_status": "NOT_A_STATUS",
                "current_status": "NOT_A_STATUS",
                "final_chart_status": "CNF",
                "observation_date": "2026-03-20",
                "passenger_record_id": "P2",
                "booking_group_id": "B1",
            },
        ]
    )
    card = score_partition(frame, estimator(), prevalence=PREVALENCE, partition="test")
    assert card.group is not None
    assert card.group.total_groups == 1
    assert card.group.multi_passenger_groups == 1
    assert card.group.scored_groups == 0
    assert card.group.abstained_groups == 1
    assert card.group.brier_all_cnf is None
