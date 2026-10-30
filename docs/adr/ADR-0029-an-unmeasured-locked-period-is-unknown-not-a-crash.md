# ADR-0029: An unmeasured locked period is `unknown`, and it is never a crash

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0017 (calibration fitted on validation, measured on the locked test),
  ADR-0022 (calibration identity bound to its target event), `backend/railconfirm/training/calibration.py`,
  `backend/railconfirm/training/report.py`, `backend/railconfirm/training/__main__.py`

## Context

A calibration is fitted on the validation partition and its effect is then measured on the
locked test partition (ADR-0017). Both readings are published because a correction that
gains on the rows it was chosen for and loses on the rows it was not is exactly the finding
a report must not smooth over.

`CalibrationEvidence` published that reading through `test_effect` and
`helps_on_locked_test`, and both opened with bare `assert` statements:

```python
@property
def test_effect(self) -> float:
    assert self.test_before.event_brier is not None
    assert self.test_after.event_brier is not None
    return round(self.test_after.event_brier - self.test_before.event_brier, 6)
```

The locked partition is scored by the same estimator that produces predictions, and that
estimator abstains when it cannot reach a cohort. A locked period whose rows all abstain
therefore produces a scorecard with `scored_rows == 0` and `event_brier is None` — a
legitimate outcome on a small fixture, on a narrow class/quota slice, or on a held-out
period that introduces a category the table never saw.

Three things were wrong with raising there.

1. **It is not an error condition.** Nothing contradicted anything. The locked period simply
   carried no evidence about the correction. The two numbers being absent is the finding.
2. **It happened after the artifact was written.** `_fit` writes the candidate artifact,
   prints the summary, and builds the report afterwards. The `AssertionError` surfaced in
   `to_dict()` and in the printed line — so a fit that had completed and written its artifact
   reported itself as a crash, and `--report` was never written. A caller reading the exit
   code saw a failure where the work had succeeded.
3. **It was invisible under `python -O`.** Stripped assertions change the return value of a
   public property into a `TypeError` on `None - None`, which is worse than either a raise or
   a `None`.

The validation side of the same object had the mirror-image problem. `validation_effect`
also asserted, but there the assertion was *right*: `fit_platt` refuses to fit without rows
carrying a probability strictly inside `(0, 1)`, so a calibration that exists at all was
fitted on a partition that scored. A validation scorecard with no event Brier cannot come
from the same run. It was the bare `assert` — not the refusal — that was wrong.

## Decision

1. **A missing locked reading is `None`, and it is named.** `CalibrationEvidence.test_effect`
   returns `float | None`; `locked_test_measured` states whether the locked period produced
   an event score at all; `helps_on_locked_test` returns `bool | None`. `None` is not `False`:
   a correction that measured nothing has not been shown to fail.

2. **The report says "unmeasured", not "did not help".** When `helps_on_locked_test` is
   `None`, the conclusion reads that the locked period produced no score at all, that the
   effect there is unknown, and that the artifact's calibration rests on the validation
   window alone. The failing branch keeps its existing wording, because that branch is about
   a measurement that was made and pointed the wrong way.

3. **The validation side refuses with a typed error.** `validation_effect` raises
   `DatasetValidationError` naming the contradiction — a scorecard with no event Brier cannot
   be produced by a fit that required scored rows — rather than an `AssertionError` that
   survives nothing and explains nothing.

4. **The terminal says the same thing as the report.** The `fit` command prints
   `unknown (the locked period produced no score)` in place of the helped/not-helped word.
   One wording rule, two rendering paths, so a reader cannot see one claim on the console and
   another in the JSON.

5. **The calibration block gains a key and the report moves to `1.1.0`.**
   `REPORT_SCHEMA_VERSION` becomes `1.1.0`: `locked_test_measured` is added and
   `helps_on_locked_test` may now be `null`. No key changed meaning, so a `1.0.0` reader is
   under-informed rather than misled — except for the one null it would have read as `false`,
   which is precisely the ambiguity the new key removes.

6. **The artifact is still written.** The fit decision is a validation decision (ADR-0017);
   a locked period that could not be scored does not retroactively invalidate it. The report
   carries the missing measurement as a stated limitation instead, and promotion stays
   `candidate` — nothing is served without an explicit approval step regardless.

## Alternatives considered

- **Keep the assertion and let it raise.** Rejected: it turns a measured-but-empty evaluation
  into a run failure, and it fires after the artifact exists, so the caller cannot tell a
  broken pipeline from a small locked period.
- **Return `False` when the locked period scored nothing.** Rejected: it publishes "the
  correction did not help on the locked period" for a period that was never evaluated. That
  is a fabricated finding, and it is the same class of error as printing an unvalidated
  probability.
- **Refuse to calibrate when the locked period cannot be scored.** Rejected: the fit decision
  belongs to the validation window. Making an unrelated partition's coverage a fitting gate
  would let a downstream evaluation failure silently remove a correction on evidence that has
  nothing to do with it.
- **Skip scoring the locked period when coverage is low, and report nothing.** Rejected: the
  abstention count is itself a result. The scorecard already carries `rows`, `scored_rows`,
  `abstained_rows` and `coverage`; the calibration block should point at them, not erase them.
- **Bump the report schema to `2.0.0`.** Rejected: no key was renamed or reinterpreted. The
  additive key plus the tri-state is a minor version by the same rule ADR-0028 applied.
- **Widen the fixture until the locked period always scores, and leave the code alone.**
  Rejected: it makes the tests pass by removing the case, and the reachable path stays broken
  for anyone whose held-out period is thinner than the fixture's.

## Consequences

- A run whose locked period abstains now completes, writes both the artifact and the report,
  exits `0`, and states in three places that the locked effect is unknown.
- `helps_on_locked_test` is tri-state, so every consumer must handle `None`. The report and
  the CLI do; a future consumer that treats it as a boolean will get a type error rather than
  a silent wrong branch.
- The regression is covered at two levels: a unit test that builds the evidence with a silent
  locked scorecard, and a CLI test that rewrites the fixture so the locked period is genuinely
  unreachable. The second one is the one that would have caught the original ordering bug,
  because it asserts on what `main()` printed and wrote, not on the object in isolation.
- Reaching that state in a test required an unseen `(class, quota)` pair, not merely an unseen
  status: the estimator falls back to a broad `(class, quota, ALL)` cohort, so every status
  inside a known class/quota pair is answerable. That fallback is a real property of the
  lookup and is now recorded where the test needs it.
- Nothing here is evidence about railway behaviour. The measurements being discussed are
  measurements of a pipeline on synthetic fixtures, and the report keeps saying so.

## Validation

`backend/tests/training/test_calibration.py` gained four tests: an unmeasured locked period is
`unknown` rather than a failure (properties and `to_dict`), the report wording names the gap
and never claims the correction failed, a validation scorecard without a score is refused with
`DatasetValidationError`, and the `fit` command reports the unmeasured locked period instead
of crashing after writing its artifact. The same file's `plain_scores` helper gained
`min_sample_threshold` so a partition can be made fully abstaining on purpose. The backend
suite (1054 tests), Ruff, mypy and the repository hygiene script were run before the change
was committed.
