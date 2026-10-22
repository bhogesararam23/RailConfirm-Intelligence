"""Dataset schema, quality and eligibility validation for RailConfirm Intelligence.

The validator answers three separate questions and never conflates them:

1. **Structurally valid** — the file parsed, required columns exist, and each row
   can be interpreted.
2. **Technically eligible** — enough clean, non-contradictory, leakage-safe rows
   exist to attempt an evaluation for a target.
3. **Approved for use** — a human decision recorded in the manifest and source
   register. A passing check here is *not* approval, and no code path in this
   module can grant it.

Rules follow docs/data/DATASET_INTAKE_CHECKLIST.md and docs/data/DATA_CONTRACT.md.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

from railconfirm.data.loader import load_dataset_file
from railconfirm.domain.status import NormalizedStatus, parse_status

# The implemented row contract. Each row is one passenger's reservation observed
# as of `observation_date`, with the final-chart outcome recorded in
# `final_chart_status`. Docs/data/DATA_CONTRACT.md describes the entity model this
# flat interchange schema is derived from.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "train_number",
    "journey_date",
    "class_code",
    "quota_code",
    "initial_status",
    "final_chart_status",
    "observation_date",
)

# Recognised but optional. Absence narrows what can be checked; it is reported,
# never silently assumed.
OPTIONAL_COLUMNS: tuple[str, ...] = (
    "booking_group_id",
    "passenger_record_id",
    "current_status",
    "source_id",
    "verification_method",
    "censoring_reason",
    "is_synthetic",
)

# Rows sharing these values describe the same reservation for label purposes. When
# booking_group_id is present it is used as well, because two passengers of one
# booking share a queue.
CONTEXT_COLUMNS: tuple[str, ...] = (
    "booking_group_id",
    "train_number",
    "journey_date",
    "class_code",
    "quota_code",
    "initial_status",
    "passenger_record_id",
)

DATE_COLUMNS: tuple[str, ...] = ("journey_date", "observation_date")

# Values a text dataset uses for "absent" that pandas does not treat as null.
MISSING_TOKENS: frozenset[str] = frozenset(
    {"", "na", "n/a", "nan", "none", "null", "nil", "-", "--", "<na>", "nat"}
)

# Outcome categories that may serve as a positive label for confirmation targets.
CONFIRMATION_LABELS: frozenset[str] = frozenset({NormalizedStatus.CNF.value})

RAC_LABELS: frozenset[str] = frozenset({NormalizedStatus.RAC.value})


@dataclass(frozen=True)
class EligibilityThresholds:
    """Provisional minimum intake requirements for *attempting* an evaluation.

    These are engineering guardrails, not scientific claims: clearing them means
    there is enough material to try, not that any estimate will be meaningful.
    They must be re-justified against the prediction target before training.
    """

    min_rows: int = 200
    min_valid_rows: int = 100
    min_valid_fraction: float = 0.5
    min_distinct_journey_dates: int = 4
    min_distinct_labeled_bookings: int = 40
    min_label_diversity: int = 2
    max_duplicate_fraction: float = 0.1
    min_confirmed_share: float = 0.01
    max_confirmed_share: float = 0.99

    def __post_init__(self) -> None:
        for name in (
            "min_rows",
            "min_valid_rows",
            "min_distinct_journey_dates",
            "min_distinct_labeled_bookings",
            "min_label_diversity",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer, got {value!r}.")
        if self.min_valid_rows > self.min_rows:
            raise ValueError("min_valid_rows cannot exceed min_rows.")
        for name in (
            "min_valid_fraction",
            "max_duplicate_fraction",
            "min_confirmed_share",
            "max_confirmed_share",
        ):
            value = getattr(self, name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must lie in [0, 1], got {value!r}.")
        if self.min_confirmed_share >= self.max_confirmed_share:
            raise ValueError("min_confirmed_share must be below max_confirmed_share.")


@dataclass
class DatasetValidationReport:
    """Schema compliance, data quality, and evaluation eligibility of one dataset."""

    source_name: str
    total_rows: int
    valid_rows: int
    rejected_rows: int
    missing_columns: list[str] = field(default_factory=list)
    unexpected_columns: list[str] = field(default_factory=list)
    absent_optional_columns: list[str] = field(default_factory=list)
    null_counts: dict[str, int] = field(default_factory=dict)
    blank_token_counts: dict[str, int] = field(default_factory=dict)
    duplicate_rows: int = 0
    contradictory_label_groups: int = 0
    contradictory_label_rows: int = 0
    censored_label_rows: int = 0
    date_order_violations: int = 0
    unparseable_dates: int = 0
    invalid_train_numbers: int = 0
    initial_status_distribution: dict[str, int] = field(default_factory=dict)
    final_status_distribution: dict[str, int] = field(default_factory=dict)
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    journey_date_range: tuple[str, str] | None = None
    observation_date_range: tuple[str, str] | None = None
    distinct_journey_dates: int = 0
    distinct_labeled_bookings: int = 0
    warnings: list[str] = field(default_factory=list)
    eligibility_findings: list[str] = field(default_factory=list)
    row_examples: list[dict[str, str]] = field(default_factory=list)

    # ── Three distinct verdicts ────────────────────────────────────────────────
    @property
    def structurally_valid(self) -> bool:
        """True when the schema is complete and at least one row is interpretable."""
        return not self.missing_columns and self.total_rows > 0 and self.valid_rows > 0

    @property
    def technically_eligible(self) -> bool:
        """True when enough clean, non-contradictory rows exist to attempt evaluation.

        This is not approval. A dataset can be technically eligible and still be
        unusable because its licence, provenance or privacy position was rejected.
        """
        return self.structurally_valid and not self.eligibility_findings

    @property
    def valid_fraction(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return self.valid_rows / self.total_rows

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["structurally_valid"] = self.structurally_valid
        payload["technically_eligible"] = self.technically_eligible
        payload["valid_fraction"] = round(self.valid_fraction, 6)
        return payload

    def summary(self) -> str:
        lines = [
            "=== Dataset Validation Report ===",
            f"Source: {self.source_name}",
            f"Total rows: {self.total_rows}",
            f"Valid rows: {self.valid_rows} ({self.valid_fraction:.1%})",
            f"Rejected rows: {self.rejected_rows}",
            f"Exact duplicate rows: {self.duplicate_rows}",
            (
                f"Contradictory label groups: {self.contradictory_label_groups} "
                f"({self.contradictory_label_rows} rows)"
            ),
            f"Censored label rows: {self.censored_label_rows}",
            f"Observation after journey date: {self.date_order_violations}",
            f"Unparseable dates: {self.unparseable_dates}",
            f"Distinct journey dates: {self.distinct_journey_dates}",
            f"Distinct labelled bookings: {self.distinct_labeled_bookings}",
            "",
            "Verdicts:",
            f"  structurally valid  : {'yes' if self.structurally_valid else 'no'}",
            f"  technically eligible: {'yes' if self.technically_eligible else 'no'}",
            "  approval            : NOT DETERMINED HERE - a quality report cannot grant "
            "usage rights; see the manifest decision block",
        ]
        if self.missing_columns:
            lines.append(f"  missing required columns: {', '.join(self.missing_columns)}")
        if self.absent_optional_columns:
            lines.append(f"  absent optional columns: {', '.join(self.absent_optional_columns)}")
        if self.eligibility_findings:
            lines.append("  why it is not eligible yet:")
            for finding in self.eligibility_findings:
                lines.append(f"    - {finding}")
        if self.rejection_reasons:
            lines.append("Rejections by reason:")
            for reason, count in sorted(self.rejection_reasons.items()):
                lines.append(f"  {reason}: {count}")
        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
        lines.append("Final outcome distribution:")
        for key, count in sorted(self.final_status_distribution.items()):
            lines.append(f"  {key}: {count}")
        if self.row_examples:
            lines.append("First rejected rows (row index / reason / detail):")
            for example in self.row_examples:
                lines.append(
                    f"  {example['row']} {example['reason']}: {example['detail']}"
                )
        return "\n".join(lines)


def _is_missing(value: object) -> bool:
    """Treat pandas nulls *and* textual placeholders as absent.

    ``str(pd.NA)`` renders ``"<NA>"``, so a string-only check let genuinely empty
    cells pass as populated.
    """
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip().lower() in MISSING_TOKENS


def _clean(value: object) -> str:
    return str(value).strip()


def _parse_iso_date(value: object) -> pd.Timestamp | None:
    """Parse a strict ISO-8601 calendar date.

    An explicit format is used because pandas otherwise guesses: ``01/02/2026``
    would silently become 1 February or 2 January depending on locale settings,
    which reorders the timeline a chronological split depends on.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in MISSING_TOKENS:
        return None
    try:
        return pd.Timestamp(pd.to_datetime(text, format="%Y-%m-%d"))
    except (ValueError, TypeError):
        return None


def _context_key(row: Mapping[str, object], columns: list[str]) -> tuple[str, ...]:
    return tuple(
        f"{column}={_normalise_cell(row.get(column))}" for column in columns
    )


def _normalise_cell(value: object) -> str:
    return "" if _is_missing(value) else _clean(value).upper()


def _record_rejection(
    report: DatasetValidationReport,
    reason: str,
    row_index: object,
    detail: str,
) -> None:
    report.rejection_reasons[reason] = report.rejection_reasons.get(reason, 0) + 1
    if len(report.row_examples) < 20:
        report.row_examples.append(
            {"row": str(row_index), "reason": reason, "detail": detail}
        )


def validate_dataset(
    df: pd.DataFrame,
    *,
    source_name: str = "in-memory-frame",
    thresholds: EligibilityThresholds | None = None,
) -> DatasetValidationReport:
    """Validate a candidate dataset frame against the row contract.

    Every rejected row is counted under a stable reason and the first twenty are
    kept as examples, so a report explains what happened instead of only that
    something failed.
    """
    rules = thresholds or EligibilityThresholds()
    columns = [str(name).strip() for name in df.columns]
    df = df.copy()
    df.columns = columns

    report = DatasetValidationReport(
        source_name=source_name,
        total_rows=len(df),
        valid_rows=0,
        rejected_rows=0,
        missing_columns=[c for c in REQUIRED_COLUMNS if c not in columns],
        unexpected_columns=[c for c in columns if c not in (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS)],
        absent_optional_columns=[c for c in OPTIONAL_COLUMNS if c not in columns],
    )

    report.null_counts = {column: int(df[column].isna().sum()) for column in columns}
    # Placeholder strings such as "NA" arrive as ordinary text, so isna() misses them.
    report.blank_token_counts = {
        column: int(sum(1 for value in df[column] if _is_textual_missing(value)))
        for column in columns
    }

    if report.missing_columns:
        report.rejection_reasons["missing_required_columns"] = report.total_rows
        report.eligibility_findings.append(
            f"Schema incomplete: missing {report.missing_columns}."
        )
        report.rejected_rows = report.total_rows
        return report

    if report.total_rows == 0:
        report.eligibility_findings.append("The dataset contains no rows.")
        return report

    context_columns = [column for column in CONTEXT_COLUMNS if column in columns]

    # ── Exact duplicate rows ───────────────────────────────────────────────────
    duplicate_mask = df.duplicated(subset=columns, keep="first")
    report.duplicate_rows = int(duplicate_mask.sum())

    # ── Contradictory labels within one reservation context ────────────────────
    labels_by_context: dict[tuple[str, ...], set[str]] = {}
    for _, row in df.iterrows():
        key = _context_key(row, context_columns)
        label = _clean(row["final_chart_status"]).upper()
        if label:
            labels_by_context.setdefault(key, set()).add(label)
    contradictory_keys = {key for key, labels in labels_by_context.items() if len(labels) > 1}
    report.contradictory_label_groups = len(contradictory_keys)

    # ── Row-level checks ───────────────────────────────────────────────────────
    journey_dates: list[pd.Timestamp] = []
    observation_dates: list[pd.Timestamp] = []
    labeled_bookings: set[tuple[str, ...]] = set()

    for row_index, row in df.iterrows():
        if bool(duplicate_mask.loc[row_index]):
            report.rejected_rows += 1
            _record_rejection(
                report, "exact_duplicate_row", row_index, "Identical to an earlier row."
            )
            continue

        missing_required = [
            column for column in REQUIRED_COLUMNS if _is_missing(row[column])
        ]
        if missing_required:
            report.rejected_rows += 1
            _record_rejection(
                report,
                "missing_required_value",
                row_index,
                f"Absent or placeholder in {missing_required}.",
            )
            continue

        train_number = _clean(row["train_number"])
        if not train_number.isdigit() or not 4 <= len(train_number) <= 6:
            report.invalid_train_numbers += 1
            report.rejected_rows += 1
            _record_rejection(
                report,
                "invalid_train_number",
                row_index,
                f"{train_number!r} is not 4-6 digits.",
            )
            continue

        journey_date = _parse_iso_date(row["journey_date"])
        observation_date = _parse_iso_date(row["observation_date"])
        if journey_date is None or observation_date is None:
            report.unparseable_dates += 1
            report.rejected_rows += 1
            _record_rejection(
                report,
                "unparseable_date",
                row_index,
                "journey_date and observation_date must be ISO YYYY-MM-DD.",
            )
            continue

        if observation_date > journey_date:
            report.date_order_violations += 1
            report.rejected_rows += 1
            _record_rejection(
                report,
                "observation_after_journey",
                row_index,
                f"observed {observation_date.date()} after journey {journey_date.date()}.",
            )
            continue

        initial = parse_status(_clean(row["initial_status"]))
        final = parse_status(_clean(row["final_chart_status"]))
        report.initial_status_distribution[initial.normalized.value] = (
            report.initial_status_distribution.get(initial.normalized.value, 0) + 1
        )
        report.final_status_distribution[final.normalized.value] = (
            report.final_status_distribution.get(final.normalized.value, 0) + 1
        )

        if initial.normalized == NormalizedStatus.UNKNOWN:
            report.rejected_rows += 1
            _record_rejection(
                report,
                "unknown_initial_status",
                row_index,
                f"{initial.raw!r} has no verified mapping.",
            )
            continue

        if final.normalized == NormalizedStatus.UNKNOWN:
            report.rejected_rows += 1
            _record_rejection(
                report,
                "unknown_final_status",
                row_index,
                f"Outcome label {final.raw!r} has no verified mapping.",
            )
            continue

        if final.normalized == NormalizedStatus.CENSORED:
            report.censored_label_rows += 1
            report.rejected_rows += 1
            _record_rejection(
                report,
                "censored_label",
                row_index,
                "Outcome not reliably observed; excluded rather than used as a negative.",
            )
            continue

        key = _context_key(row, context_columns)
        if key in contradictory_keys:
            report.contradictory_label_rows += 1
            report.rejected_rows += 1
            _record_rejection(
                report,
                "contradictory_labels",
                row_index,
                f"Same context carries labels {sorted(labels_by_context[key])}.",
            )
            continue

        journey_dates.append(journey_date)
        observation_dates.append(observation_date)
        labeled_bookings.add(key)
        report.valid_rows += 1

    if journey_dates:
        report.journey_date_range = (
            min(journey_dates).date().isoformat(),
            max(journey_dates).date().isoformat(),
        )
        report.observation_date_range = (
            min(observation_dates).date().isoformat(),
            max(observation_dates).date().isoformat(),
        )
    report.distinct_journey_dates = len({date.date() for date in journey_dates})
    report.distinct_labeled_bookings = len(labeled_bookings)

    if report.rejected_rows != report.total_rows - report.valid_rows:
        raise AssertionError(
            "Validation accounting error: rejected rows do not reconcile."
        )

    _apply_eligibility_rules(df, report, rules, labeled_bookings)
    _add_observations(df, report)
    return report


def _is_textual_missing(value: object) -> bool:
    """True for a placeholder string like "NA" that pandas reads as a real value."""
    return isinstance(value, str) and value.strip().lower() in MISSING_TOKENS


def _apply_eligibility_rules(
    df: pd.DataFrame,
    report: DatasetValidationReport,
    rules: EligibilityThresholds,
    labeled_bookings: set[tuple[str, ...]],
) -> None:
    if report.total_rows < rules.min_rows:
        report.eligibility_findings.append(
            f"Only {report.total_rows} rows, below the provisional minimum of "
            f"{rules.min_rows}."
        )
    if report.valid_rows < rules.min_valid_rows:
        report.eligibility_findings.append(
            f"Only {report.valid_rows} usable rows, below the provisional minimum of "
            f"{rules.min_valid_rows}."
        )
    if report.valid_fraction < rules.min_valid_fraction:
        report.eligibility_findings.append(
            f"{report.valid_fraction:.1%} of rows usable, below "
            f"{rules.min_valid_fraction:.0%}."
        )
    if report.distinct_journey_dates < rules.min_distinct_journey_dates:
        report.eligibility_findings.append(
            f"{report.distinct_journey_dates} distinct journey dates; at least "
            f"{rules.min_distinct_journey_dates} are needed before a chronological "
            "train/validation/test split can hold anything back."
        )
    if report.distinct_labeled_bookings < rules.min_distinct_labeled_bookings:
        report.eligibility_findings.append(
            f"{report.distinct_labeled_bookings} distinct labelled reservations; at "
            f"least {rules.min_distinct_labeled_bookings} are needed to evaluate a "
            "probability rather than count a table."
        )
    outcome_labels = {
        label
        for label in report.final_status_distribution
        if label not in {NormalizedStatus.CENSORED.value, NormalizedStatus.UNKNOWN.value}
    }
    if len(outcome_labels) < rules.min_label_diversity:
        report.eligibility_findings.append(
            f"Outcomes cover only {sorted(outcome_labels) or 'nothing'}; a single-class "
            "label teaches a model to always predict that class."
        )
    if report.duplicate_rows / max(report.total_rows, 1) > rules.max_duplicate_fraction:
        report.eligibility_findings.append(
            f"{report.duplicate_rows} exact duplicate rows exceed "
            f"{rules.max_duplicate_fraction:.0%} of the file."
        )
    confirmed = sum(
        count for label, count in report.final_status_distribution.items()
        if label in CONFIRMATION_LABELS
    )
    share = confirmed / max(len(labeled_bookings), 1) if labeled_bookings else 0.0
    if labeled_bookings and not (
        rules.min_confirmed_share <= share <= rules.max_confirmed_share
    ):
        report.eligibility_findings.append(
            f"Confirmed share {share:.1%} sits outside the plausible band "
            f"[{rules.min_confirmed_share:.0%}, {rules.max_confirmed_share:.0%}], "
            "which usually means the label column is not what it claims to be."
        )


def _add_observations(df: pd.DataFrame, report: DatasetValidationReport) -> None:
    """Add review signals that do not by themselves block eligibility."""
    if report.unexpected_columns:
        report.warnings.append(
            f"Columns outside the documented row contract: {report.unexpected_columns}. "
            "Any of them carrying personal data — passenger names, PNRs, booking "
            "identifiers — must be removed before the file is kept or imported."
        )
    if report.invalid_train_numbers:
        report.warnings.append(
            f"{report.invalid_train_numbers} rows carry a train number that is not 4-6 digits."
        )
    if report.date_order_violations:
        report.warnings.append(
            f"{report.date_order_violations} rows observed after their journey date; "
            "such a label cannot be a forecast input."
        )
    if report.censored_label_rows:
        report.warnings.append(
            f"{report.censored_label_rows} rows carry a CENSORED outcome and were excluded. "
            "Censored is not a negative label."
        )
    if report.contradictory_label_groups:
        report.warnings.append(
            f"{report.contradictory_label_groups} reservation contexts carry more than "
            "one outcome label. Resolving them needs source review, not a rule."
        )
    if NormalizedStatus.CANCELLED.value in report.final_status_distribution:
        report.warnings.append(
            "CANCELLED outcomes present: a user cancellation is not automatically a "
            "confirmation failure. Confirm the target definition before labelling them."
        )
    if "booking_group_id" in report.absent_optional_columns:
        report.warnings.append(
            "No booking_group_id column: group-level and dependence-aware evaluation is "
            "not possible from this file."
        )
    if "verification_method" in report.absent_optional_columns:
        report.warnings.append(
            "No verification_method column: how final outcomes were confirmed is unknown, "
            "so label quality cannot be assessed."
        )
    if "is_synthetic" in df.columns:
        flagged = sum(
            1
            for value in df["is_synthetic"]
            if str(value).strip().lower() in {"true", "1", "yes"}
        )
        if flagged:
            report.warnings.append(
                f"{flagged} rows declare is_synthetic: usable for software tests only, "
                "never as evidence of real-world accuracy."
            )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m railconfirm.data.validator <dataset_path>")
        sys.exit(2)

    path = sys.argv[1]
    try:
        frame = load_dataset_file(path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Cannot read dataset: {exc}")
        sys.exit(1)

    result = validate_dataset(frame, source_name=str(path))
    print(result.summary())
    sys.exit(0 if result.technically_eligible else 1)
