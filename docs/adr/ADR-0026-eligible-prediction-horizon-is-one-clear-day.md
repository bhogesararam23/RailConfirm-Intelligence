# ADR-0026: The eligible prediction horizon is one clear day, enforced at both ends

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainers
- **Related:** ADR-0003, ADR-0004, ADR-0013, docs/data/DATA_CONTRACT.md

## Context

The served request and the dataset row contract carry the same quantity in two
carriers. Serving takes an aware `prediction_at` timestamp and the journey date;
the dataset carries `observation_date` and `journey_date`, both calendar dates with
no clock attached.

The served path already refuses a prediction that is not genuinely ahead of the
journey: `validate_prediction_timing` rejects any `prediction_at` on or after
`journey_date`, because the final chart is prepared on the journey date and the
outcome is settled from that point.

The dataset gate did not enforce the same horizon. It rejected only
`observation_date > journey_date`, so a row observed *on* its own journey date
passed as a valid training record, with `lead_days = 0`. That row describes exactly
the situation the service refuses to answer:

* the two dates are equal, so the record cannot say whether the observation
  preceded the final chart or followed it;
* a model fitted on such rows is fitted on a population the service never serves;
* any metric computed on them would be a score on retrodictions reported as
  forecasts.

Nothing in the file distinguishes the two cases. A date-only record that could mean
either is not evidence, and the contract must not claim intraday precision it does
not have.

## Decision

1. `MIN_LEAD_DAYS = 1` in `railconfirm.domain.validation` is the single definition of
   the eligible prediction horizon. Serving compares `journey_date -
   prediction_at.date()` against it; `railconfirm.data.validator` imports the same
   constant for its row rule, so the two cannot drift.
2. The dataset gate rejects a row whose `observation_date` is closer than
   `MIN_LEAD_DAYS` to `journey_date`, under a new stable rejection reason
   `observation_on_journey_date`, counted in `same_day_observation_rows`.
   `observation_after_journey` and `date_order_violations` keep their existing
   meaning: the dates are in order, the gap is simply too small to be a forecast.
3. The row contract is versioned: `ROW_CONTRACT_VERSION = "1.1.0"` names the rules a
   report was produced under, and every `DatasetValidationReport` carries the version
   it applied. Existing artifacts are not reinterpreted — they record no row-contract
   version and are read exactly as before — but a report can no longer be mistaken
   for one produced under the older rule.
4. The floor is not lowered to admit data. A source that needs a shorter horizon must
   supply observation timestamps; a smaller constant would only relabel an ambiguous
   record as a valid one.

## Alternatives considered

* **Keep accepting same-day rows and let serving refuse the horizon.** Rejected: the
  fitting population and the served population would differ by exactly the rows whose
  label is not a forecast, and no report would say so.
* **Null `lead_days` for same-day rows instead of rejecting them.** Rejected: the row's
  label still comes from a chart that may already have been prepared when the record
  was written, so the leakage is in the label, not in one derived feature.
* **Require two clear days, or a fixed lookahead window.** Rejected for now: no dataset
  exists against which to measure a booking-window requirement, and the minimum that
  makes the record orderable is what the evidence supports. A wider window is a
  modelling choice that must be argued on real data.
* **Treat the same-day case as `observation_after_journey`.** Rejected: the dates are
  not out of order, and merging the reasons would hide which of the two mistakes a
  source made.

## Consequences

* A dataset whose observations are all recorded on the journey date now yields zero
  valid rows and is reported as structurally invalid rather than eligible. That is the
  intended outcome: such a file cannot answer a question about the future.
* Row counts fall for any candidate source that records a same-day look. The report
  states the exclusion count and names it, so the loss is visible instead of silent.
* The contract now depends on both dates being present and parseable before either
  date rule can be evaluated; that ordering is unchanged.
* The synthetic gate fixture carries one row of this shape, so the reason is exercised
  through the CLI, the training gate and the validator's own tests.

## Validation

* `tests/data/test_validator.py`:
  `test_observation_on_the_journey_date_is_not_a_forecast_input` (refused, counted, and
  not an ordering violation), `test_one_clear_day_before_the_journey_is_accepted`, and
  `test_the_gate_and_serving_refuse_the_same_horizon`, which parametrises over lead
  days `0, 1, 2, 5` and requires the gate's verdict and `validate_prediction_timing`'s
  verdict to agree for every one.
* `tests/domain/test_validation.py::test_the_eligible_horizon_is_one_clear_day` pins
  the constant and the boundary at the last minute of the previous day.
* `tests/training/test_dataset_gate.py` requires every shape in `gate_defects()` — now
  including `observation_on_journey_date` — to be counted in the report and absent from
  the frame handed to the fitter, and `tests/training/test_cli.py` checks the reason
  reaches the CLI's intake accounting.
* The tests above use synthetic fixtures. They establish that the rule is enforced, not
  that any real dataset satisfies it.
