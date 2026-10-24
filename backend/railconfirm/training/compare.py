"""Which estimator may replace the other — decided on the locked period, paired row by row.

A candidate that wins in the window it was chosen for has proved nothing. This module fits
nothing and promotes nothing: it scores two already-fitted models against the same rows with
the same prevalence baseline, pairs them reservation by reservation, and applies one rule to
the locked test period before it will say the word "candidate".

Three things make the comparison mean something:

* both models must have been fitted on **one split** of one dataset, checked rather than
  assumed, because two windows can differ more than two models do;
* the paired counts only ever compare rows **both** models answered. A model that abstains
  more can score better on the rows it chose, and that is a coverage change, not accuracy;
* the recommendation requires the candidate to win the distribution score, the target event
  score, the paired row count and the coverage floor at the same time — on the locked
  period, where a win cannot be arranged.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from railconfirm.domain.exceptions import DatasetValidationError
from railconfirm.training.dataset import ApprovedDataset
from railconfirm.training.fitter import FittedBaseline
from railconfirm.training.metrics import (
    TARGET_EVENTS,
    RowScores,
    Scorecard,
    ScoredRow,
    evaluation_provenance,
    score_partition,
    score_rows,
)

MODEL_SELECTION_METHOD = (
    "same split, one prevalence baseline, paired per-row comparison judged on the locked period"
)
"""The method line a reader judges these numbers by.

`fit`, `origins` and `decay` each answer a different question; this one answers which of two
fitted models may replace the other, and only that."""

LOCKED_PARTITION = "test"


@dataclass(frozen=True)
class PairedCount:
    """Row-by-row outcome of two models answering the same reservations."""

    rows_both_scored: int
    candidate_wins: int
    candidate_losses: int
    ties: int
    only_baseline_scored: int
    only_candidate_scored: int
    rows_total: int

    @property
    def comparable(self) -> bool:
        """No overlapping answers means no comparison, not a tie."""
        return self.rows_both_scored > 0

    @property
    def neither_scored(self) -> int:
        return (
            self.rows_total
            - self.rows_both_scored
            - self.only_baseline_scored
            - self.only_candidate_scored
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows_total": self.rows_total,
            "rows_both_scored": self.rows_both_scored,
            "candidate_wins": self.candidate_wins,
            "candidate_losses": self.candidate_losses,
            "ties": self.ties,
            "only_baseline_scored": self.only_baseline_scored,
            "only_candidate_scored": self.only_candidate_scored,
            "neither_scored": self.neither_scored,
        }


def pair_scores(
    baseline_rows: Sequence[ScoredRow],
    candidate_rows: Sequence[ScoredRow],
    *,
    rows_total: int | None = None,
) -> PairedCount:
    """Count wins, losses and ties on the rows both models answered.

    Pairing is by partition position, which is stable across two passes over the same frame
    even when the models abstain on different rows. The lens is the target event's own squared
    error — the number a passenger is actually handed — because a distribution difference
    inside the event's complement is not what the product claims.
    """
    baseline_by_position = {row.position: row for row in baseline_rows}
    candidate_by_position = {row.position: row for row in candidate_rows}
    shared = sorted(set(baseline_by_position) & set(candidate_by_position))

    wins = losses = ties = 0
    for position in shared:
        baseline_error = (
            baseline_by_position[position].event_predicted
            - baseline_by_position[position].event_observed
        ) ** 2
        candidate_error = (
            candidate_by_position[position].event_predicted
            - candidate_by_position[position].event_observed
        ) ** 2
        if candidate_error < baseline_error:
            wins += 1
        elif candidate_error > baseline_error:
            losses += 1
        else:
            ties += 1

    total = (
        rows_total
        if rows_total is not None
        else len(set(baseline_by_position) | set(candidate_by_position))
    )
    return PairedCount(
        rows_both_scored=len(shared),
        candidate_wins=wins,
        candidate_losses=losses,
        ties=ties,
        only_baseline_scored=len(baseline_by_position) - len(shared),
        only_candidate_scored=len(candidate_by_position) - len(shared),
        rows_total=total,
    )


@dataclass(frozen=True)
class PartitionComparison:
    """Both models on one partition, with the deltas and the paired counts between them."""

    partition: str
    baseline: Scorecard
    candidate: Scorecard
    paired: PairedCount

    @staticmethod
    def _delta(baseline_value: float | None, candidate_value: float | None) -> float | None:
        if baseline_value is None or candidate_value is None:
            return None
        return round(candidate_value - baseline_value, 6)

    @property
    def brier_delta(self) -> float | None:
        return self._delta(self.baseline.brier, self.candidate.brier)

    @property
    def event_brier_delta(self) -> float | None:
        return self._delta(self.baseline.event_brier, self.candidate.event_brier)

    @property
    def log_loss_delta(self) -> float | None:
        return self._delta(self.baseline.log_loss, self.candidate.log_loss)

    @property
    def coverage_delta(self) -> float | None:
        return self._delta(self.baseline.coverage, self.candidate.coverage)

    @property
    def comparison(self) -> dict[str, Any]:
        return {
            "brier_delta": self.brier_delta,
            "event_brier_delta": self.event_brier_delta,
            "log_loss_delta": self.log_loss_delta,
            "coverage_delta": self.coverage_delta,
            **self.paired.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "partition": self.partition,
            "baseline": self.baseline.to_dict(),
            "candidate": self.candidate.to_dict(),
            "comparison": self.comparison,
        }


@dataclass(frozen=True)
class Verdict:
    """What the rule decided, and the numbers it decided on."""

    outcome: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"outcome": self.outcome, "reasons": list(self.reasons)}


def _locked(partitions: Sequence[PartitionComparison]) -> PartitionComparison | None:
    return next(
        (item for item in partitions if item.partition == LOCKED_PARTITION), None
    )


def _wins_everywhere(item: PartitionComparison) -> bool:
    """All four conditions at once, or it is not a replacement."""
    return (
        item.paired.comparable
        and item.brier_delta is not None
        and item.event_brier_delta is not None
        and item.brier_delta < 0
        and item.event_brier_delta < 0
        and item.candidate.coverage >= item.baseline.coverage
        and item.paired.candidate_wins > item.paired.candidate_losses
    )


def _describe(item: PartitionComparison) -> str:
    return (
        f"{item.partition}: distribution Brier {item.baseline.brier} -> "
        f"{item.candidate.brier} (delta {item.brier_delta}), event Brier "
        f"{item.baseline.event_brier} -> {item.candidate.event_brier} (delta "
        f"{item.event_brier_delta}), coverage {item.baseline.coverage:.1%} -> "
        f"{item.candidate.coverage:.1%}, paired "
        f"{item.paired.candidate_wins} wins / {item.paired.candidate_losses} losses / "
        f"{item.paired.ties} ties over {item.paired.rows_both_scored} rows both answered"
    )


def decide_verdict(partitions: Sequence[PartitionComparison]) -> Verdict:
    """Recommend the candidate only on the locked period's numbers.

    Reasons are written from the measured values, so a reader can see the rule fire rather
    than trusting that it did.
    """
    locked = _locked(partitions)
    if locked is None:
        return Verdict(
            outcome="undetermined",
            reasons=[
                "No locked test period was scored, so there is nothing to decide the "
                "candidate on: a win in the fitting or validation window is the candidate "
                "grading its own homework."
            ],
        )
    if not locked.paired.comparable:
        return Verdict(
            outcome="undetermined",
            reasons=[
                f"The locked period produced no rows both models answered ({_describe(locked)}), "
                "so the two cannot be compared there — which is not the same as a tie."
            ],
        )
    if (
        locked.baseline.brier is None
        or locked.candidate.brier is None
        or locked.baseline.event_brier is None
        or locked.candidate.event_brier is None
    ):
        return Verdict(
            outcome="undetermined",
            reasons=[
                f"A model scored nothing on the locked period ({_describe(locked)}); an "
                "abstention is not a lost forecast and cannot be counted as one."
            ],
        )

    reasons = [f"Locked period decided on: {_describe(locked)}."]
    failures = _failures(locked)
    if not failures:
        reasons.append(
            "The candidate improved both scores, held its coverage, and won more rows "
            "than it lost on the locked period. Promotion remains a human act: this is "
            "evidence about these rows, and nothing here has been read from real data."
        )
        return Verdict(outcome="candidate", reasons=reasons)
    reasons.extend(failures)
    for earlier in partitions:
        if earlier.partition == LOCKED_PARTITION:
            continue
        if _wins_everywhere(earlier):
            reasons.append(
                f"The candidate won the {earlier.partition} window "
                f"({_describe(earlier)}) but not the locked period, which is the pattern a "
                "gain that belongs to the window it was chosen for makes."
            )
    reasons.append("Verdict: keep the baseline. It remains the artifact to promote from.")
    return Verdict(outcome="baseline", reasons=reasons)


def _failures(item: PartitionComparison) -> list[str]:
    """Every reason the candidate does not replace the baseline, with its numbers."""
    failures: list[str] = []
    if item.brier_delta is None or item.brier_delta >= 0:
        failures.append(
            f"Blocked on the locked period: the distribution Brier did not improve "
            f"({item.baseline.brier} -> {item.candidate.brier})."
        )
    if item.event_brier_delta is None or item.event_brier_delta >= 0:
        failures.append(
            f"Blocked on the locked period: the target event Brier did not improve "
            f"({item.baseline.event_brier} -> {item.candidate.event_brier})."
        )
    if item.candidate.coverage < item.baseline.coverage:
        failures.append(
            f"Blocked on the locked period: coverage fell from "
            f"{item.baseline.coverage:.1%} to {item.candidate.coverage:.1%}, so a better "
            "score could be the candidate refusing the harder rows."
        )
    if item.paired.candidate_wins <= item.paired.candidate_losses:
        failures.append(
            f"Blocked on the locked period: the candidate did not win more rows than it "
            f"lost ({item.paired.candidate_wins} wins, {item.paired.candidate_losses} "
            f"losses, {item.paired.ties} ties)."
        )
    return failures


@dataclass(frozen=True)
class ModelComparisonResult:
    """Both models, both partitions, the paired counts, and the verdict they support."""

    method: str
    target: str
    prevalence: dict[str, float]
    baseline_version: str
    candidate_version: str
    baseline_estimator: str
    candidate_estimator: str
    dataset_id: str
    dataset_sha256: str
    partitions: tuple[PartitionComparison, ...]
    verdict: Verdict

    @property
    def locked_test(self) -> PartitionComparison | None:
        return _locked(self.partitions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_method": self.method,
            "target": self.target,
            "target_event_classes": list(TARGET_EVENTS[self.target]),
            "baseline": {
                "version": self.baseline_version,
                "estimator": self.baseline_estimator,
            },
            "candidate": {
                "version": self.candidate_version,
                "estimator": self.candidate_estimator,
            },
            "dataset": {
                "dataset_id": self.dataset_id,
                "sha256": self.dataset_sha256,
            },
            "prevalence": dict(sorted(self.prevalence.items())),
            "partitions": [item.to_dict() for item in self.partitions],
            "verdict": self.verdict.to_dict(),
        }


def _require_comparable(baseline: FittedBaseline, candidate: FittedBaseline) -> None:
    """Refuse a comparison that would not be one.

    Each check names the difference rather than quietly aligning the two runs, because the
    tempting repair — scoring whatever each model happened to train on — is what makes two
    incomparable numbers look like a contest.
    """
    if baseline.metadata.estimator == candidate.metadata.estimator:
        raise DatasetValidationError(
            f"The two models are the same estimator ({baseline.metadata.estimator!r}): a "
            "candidate must be a different way of answering, not the same one under another "
            "version name. Comparing two settings of one model is a different question and "
            "needs its own rule."
        )
    if baseline.metadata.target != candidate.metadata.target:
        raise DatasetValidationError(
            f"Baseline targets {baseline.metadata.target!r} while the candidate targets "
            f"{candidate.metadata.target!r}; the two headline numbers answer different "
            "questions and cannot be differenced."
        )
    base_boundaries = [
        (item.name, item.start_date, item.end_date, item.row_count)
        for item in baseline.split.partitions
    ]
    cand_boundaries = [
        (item.name, item.start_date, item.end_date, item.row_count)
        for item in candidate.split.partitions
    ]
    if base_boundaries != cand_boundaries:
        raise DatasetValidationError(
            "The two models were not fitted on the same split, so their scores are not "
            f"comparable: baseline {base_boundaries} vs candidate {cand_boundaries}. Fit "
            "both from one dataset with the same split fractions and thresholds — a "
            "different window can move the numbers further than a different model does."
        )


def run_model_comparison(
    dataset: ApprovedDataset,
    *,
    baseline: FittedBaseline,
    candidate: FittedBaseline,
    target: str | None = None,
) -> ModelComparisonResult:
    """Score two already-fitted models on one split and judge them on the locked period.

    Nothing is fitted here: the caller brings the two models, and this walks the same
    partitions with both of them, one shared prevalence baseline, pairing the rows.
    """
    chosen = target or baseline.metadata.target
    if chosen not in TARGET_EVENTS:
        raise DatasetValidationError(
            f"Cannot compare target {chosen!r}: the event it names is not defined. "
            f"Known targets: {sorted(TARGET_EVENTS)}."
        )
    _require_comparable(baseline, candidate)

    def provenance(fitted: FittedBaseline):
        metadata = fitted.metadata
        return evaluation_provenance(
            dataset.dataset_id,
            dataset.sha256,
            metadata.source_reference,
            metadata.data_approval_status,
            is_synthetic=dataset.is_synthetic,
            mapping_version=metadata.status_mapping_version,
            fitted_from=metadata.trained_from,
            fitted_to=metadata.trained_to,
        )

    models = {
        "baseline": (baseline, baseline.estimator_for(provenance(baseline))),
        "candidate": (candidate, candidate.estimator_for(provenance(candidate))),
    }
    # One yardstick for both: the prevalence of the shared training window. Each model's
    # own fit produced the same distribution here, and asserting that is part of the
    # comparability check rather than a nicety.
    prevalence = dict(baseline.prevalence)
    if dict(candidate.prevalence) != prevalence:
        raise DatasetValidationError(
            "The two models report different training-population prevalences, so the same "
            "baseline cannot be quoted for both: "
            f"{prevalence} vs {dict(candidate.prevalence)}."
        )

    partitions: list[PartitionComparison] = []
    for name, frame in (
        ("validation", baseline.split.val),
        (LOCKED_PARTITION, baseline.split.test),
    ):
        if frame is None or len(frame) == 0:
            continue
        scored: dict[str, RowScores] = {}
        cards: dict[str, Scorecard] = {}
        for role, (fitted, estimator) in models.items():
            calibration = fitted.metadata.calibration
            scored[role] = score_rows(
                frame, estimator, target=chosen, calibration=calibration
            )
            cards[role] = score_partition(
                frame,
                estimator,
                prevalence=prevalence,
                partition=name,
                target=chosen,
                calibration=calibration,
                pre_scored=scored[role],
            )
        partitions.append(
            PartitionComparison(
                partition=name,
                baseline=cards["baseline"],
                candidate=cards["candidate"],
                paired=pair_scores(
                    scored["baseline"].rows,
                    scored["candidate"].rows,
                    rows_total=scored["baseline"].rows_total,
                ),
            )
        )

    if not partitions:
        raise DatasetValidationError(
            "Nothing to compare: the shared split held back no validation or test rows."
        )

    return ModelComparisonResult(
        method=MODEL_SELECTION_METHOD,
        target=chosen,
        prevalence=prevalence,
        baseline_version=baseline.metadata.version,
        candidate_version=candidate.metadata.version,
        baseline_estimator=baseline.metadata.estimator,
        candidate_estimator=candidate.metadata.estimator,
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset.sha256,
        partitions=tuple(partitions),
        verdict=decide_verdict(partitions),
    )


def describe_result(result: ModelComparisonResult) -> str:
    """The lines a terminal run prints: each partition, both models, then the verdict."""
    lines = [
        (
            f"Comparing {result.baseline_estimator} ({result.baseline_version}) against "
            f"{result.candidate_estimator} ({result.candidate_version}) on "
            f"{result.dataset_id}"
        ),
        f"Method: {result.method}",
    ]
    for item in result.partitions:
        lines.append(f"  {item.partition}:")
        lines.append(f"    baseline  {_line(item.baseline)}")
        lines.append(f"    candidate {_line(item.candidate)}")
        paired = item.paired
        lines.append(
            f"    paired: {paired.candidate_wins} wins, {paired.candidate_losses} losses, "
            f"{paired.ties} ties over {paired.rows_both_scored} rows both answered; "
            f"{paired.only_baseline_scored} answered only by the baseline, "
            f"{paired.only_candidate_scored} only by the candidate, "
            f"{paired.neither_scored} by neither"
        )
    lines.append(f"Verdict: {result.verdict.outcome}")
    lines.extend(f"  - {reason}" for reason in result.verdict.reasons)
    return "\n".join(lines)


def _line(card: Scorecard) -> str:
    return (
        f"Brier {card.brier} (baseline {card.baseline_brier}), event "
        f"{card.event_brier} (baseline {card.event_baseline_brier}), coverage "
        f"{card.coverage:.1%} ({card.scored_rows}/{card.rows})"
    )
