# ADR-0033: A split plan refuses a setting it cannot read, and names the reason it actually found

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0013 (one as-of status definition), ADR-0014 (rolling origin), ADR-0018
  (frozen-artifact decay), ADR-0024 (group arithmetic refuses invalid input),
  `backend/railconfirm/data/preprocessing.py`

## Context

Three planners cut a dataset into temporal blocks: `chronological_split`,
`rolling_origin_windows` and `frozen_horizon_windows`. Two defects were found by reading
their argument handling against their own rules.

**Most of the settings were type-checked, and the ones that decide the gap were not.**
`rolling_origin_windows` and `frozen_horizon_windows` already refuse a count that is not a
positive integer, and `chronological_split` refused `min_rows_per_partition` similarly.
`gap_days` — the setting that decides how much separation there must be between a training
block and the block scored after it — was checked only against zero:

```python
if gap_days < 0:
    raise DatasetValidationError("gap_days cannot be negative.")
```

Reproduced against the current build, for all three planners:

| `gap_days` | What happened |
| --- | --- |
| `"2"` | `TypeError: '<' not supported between instances of 'str' and 'int'` |
| `2.5` | accepted, then compared against a whole-day separation |
| `True` | accepted as a one-day gap |

Two more settings had the same shape in `chronological_split`: `train_frac="0.7"` and
`val_frac=None` raised `TypeError` out of a comparison, and `min_rows_per_partition=2.5`
was accepted as a threshold no row count can equal.

The consequence is not a differently-shaped split; it is a failure that names nothing. A
`TypeError` from a comparison reaches the caller without the argument, the function or the
rule that refused it — the same boundary problem ADR-0029 fixed for a calibration row
count. The two silent cases are worse in kind, because a gap of `2.5` days and a gap of
`2` days produce the same partition on many files and different ones on others, and
`gap_days=True` reads as "on" to a caller who wrote a flag while meaning "one day of
separation". The training CLI passes `type=int`, so this never surfaced through the
command line; it surfaces through the library API that `fitter`, `origins` and `decay`
call, which is the path tests and notebooks use.

**The group-crossing refusal described a case it had not found.** When
`booking_group_id` is present, `chronological_split` refuses a group id that appears on
more than one journey date. The test was `nunique() > 1`, and the reason it emitted was:

> 1 booking_group_id values appear on dates falling in more than one partition (for
> example ['B1']); the same outcome would then appear in training and evaluation.

On the repository's own fixture for this rule, both of B1's dates fall inside the training
partition under the default fractions. Nothing crossed a boundary, and the message told
the reader to look at the boundary for a problem in the data.

## Decision

1. **The settings that cut data are type-checked before they are used.** `_require_gap_days`
   refuses a `bool`, a non-`int`, and a negative value; `_require_positive_int` refuses a
   `bool`, a non-`int` and a value below one. Every planner calls them, and the duplicated
   inline loops in the two multi-window planners were replaced by calls to the same helper,
   so the rule has one definition. `chronological_split` additionally refuses a
   `train_frac`/`val_frac` that is not a number before comparing it to the range.

2. **A booking on more than one date is still refused, for the reason that applies.** The
   group check now separates the two cases it already refused. A group whose dates fall in
   more than one partition is reported as a leakage risk: that outcome would sit in the
   fit and in the evaluation. A group whose dates fall inside one partition is reported as
   an identity problem: one booking covers one journey, so its outcome cannot be attributed
   to a date or counted once. Each reason states its own count and sample.

3. **No behaviour changes for valid input.** Every refusal added here rejects an argument
   that previously crashed or was silently reinterpreted. No split that was eligible before
   is refused now, and no eligible split's boundaries move.

4. **No schema or artifact version changes.** These are argument checks and a message, and
   neither crosses a stored contract. A report written before this change remains readable
   and means what it says.

## Alternatives considered

- **Coerce: `int(gap_days)`, `float(train_frac)`.** Rejected. `int("2.5")` raises, `int(2.9)`
  silently becomes `2`, and `float(None)` raises — a coercion moves the failure rather than
  naming it, and the silent truncation is exactly the class of defect being fixed.
- **Keep the negative-only check and let Python's `TypeError` do the refusing.** Rejected:
  a `TypeError` from a comparison tells the caller nothing about which argument was wrong,
  and the training path catches `DatasetValidationError` to report a reason. A crash is not
  a refusal.
- **Accept a float gap and document it as "at least this many days".** Rejected: the
  separation is computed in whole days from date-only records, so a fractional gap has no
  meaning to compare against; it would be a threshold that rounds by accident of the data.
- **Stop refusing groups inside one partition, since no boundary is crossed.** Rejected: a
  group id on two dates cannot be attributed to one outcome, so whichever row is scored,
  the other is either dropped without a record or counted a second time. Two journey dates
  for one booking is a data question that must be answered before the split is trusted.
- **Emit one combined message for both cases.** Rejected: the two cases need different work
  — one is a boundary setting, the other is a record-identity defect — and a message that
  names both generically names neither.

## Consequences

- A caller who passes a wrong type gets a `DatasetValidationError` naming the setting and
  the value, on the path `fitter`, `origins`, `decay` and the CLI already handle.
- A refused group crossing now states which of the two problems it found, so a data owner
  can act on it without reading the planner's source.
- The helper duplication between the two multi-window planners is gone; a future setting
  added to any planner has one obvious check to call.
- Nothing here changes an eligible split, a metric, a report field or an artifact, so no
  published number moves. This is not evidence about railway data.

## Validation

`backend/tests/data/test_preprocessing.py` gained
`test_a_gap_that_is_not_a_whole_number_of_days_is_refused` (parametrised over `"2"`, `2.5`
and `True`, and run against all three planners),
`test_a_row_floor_that_is_not_a_whole_number_is_refused`,
`test_a_split_fraction_that_is_not_a_number_is_refused` and
`test_a_group_spanning_two_partitions_is_reported_as_leakage`. The existing
`test_booking_group_crossing_partitions_blocks_the_split` previously asserted the wrong
reason for its own fixture and now asserts the accurate one plus the absence of the other.
The backend suite (1076 tests), Ruff, mypy and the repository hygiene script were run before
this decision was committed.
