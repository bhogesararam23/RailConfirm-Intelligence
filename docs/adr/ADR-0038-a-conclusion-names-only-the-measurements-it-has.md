# ADR-0038: A conclusion names only the measurements it has

- **Status:** Accepted
- **Date:** 2026-10-31
- **Decision owner:** Project maintainers
- **Related:** ADR-0021 (paired comparison), ADR-0028 (rolling origin publishes both aggregations), ADR-0030 (a decay readout dates its own ends), ADR-0035 (a figure is scored against the event its name gives), ADR-0036 (a report's definition and its figure name the same event), ADR-0037 (a scorecard refuses rows it was not handed)

## Context

ADR-0037 closed three ways a scorecard could publish arithmetic under labels it was not
handed. The layer above it — the sentences a report derives from those cards — had the same
class of defect, in three forms.

1. **The wrong event's classes.** `build_report` correctly names the artifact's target in
   the payload and adds a limitation when a partition was scored for a different one. The
   per-partition conclusion then printed `scorecard.target` beside event classes taken from
   `metadata.target`. Scoring `final_chart_cnf_or_rac` against a `final_chart_cnf` artifact
   produced `validation: target event final_chart_cnf_or_rac (CNF) Brier 0.015329 …`: the
   merged event's score captioned with the confirmed event's classes. The limitation and the
   conclusion contradicted each other in the same report.

2. **A missing verdict read as a disagreement.** The paragraph that reports whether the
   distribution and the target event disagree compared `beats_baseline !=
   event_beats_baseline` without checking either side for `None`. A card with a distribution
   verdict and no event verdict — `True != None` — printed "the distribution and the target
   event disagree about beating the base rate", turning an unmeasured result into the
   opposite result. Two further branches claimed from no measurement: a rolling-origin run
   with no event scores printed `All 0 origins beat the baseline …`, and the decay report
   printed the same sentence and then raised `TypeError: unsupported format string passed to
   NoneType.__format__`, so a report that had scored six horizons could not be written at all.

3. **A partial event table read as a full one.** The decay drift line counted horizons with a
   *distribution* score and applied the count to *event* readings. A run with six
   distribution scores and one event reading printed `Across 6 scored horizons … a drift of
   +0.000000`, dating both ends to the same horizon; `describe_result` printed `hNone n/a ->
   hNone n/a` with `0/0 scored horizons`; and the written summary published `0/0 (event)`.
   A single reading was presented as a curve with zero slope. The rolling-origin description
   and summary printed the same zero denominator (`0/0 beat it`, `0/0 (event)`), and its
   "All N origins beat the target event" sentence did not distinguish origins that produced
   an event reading from origins that produced none.

Every card `score_partition` builds carries both scores, so forms 2 and 3 were not reachable
from the pipeline. They were reachable from a `Scorecard` assembled by any other caller, and
the reports are exported functions whose purpose is to describe cards they are given. Form 1
was reachable from the pipeline whenever a caller scored one target against another
artifact — a comparison the report itself supports and discloses.

## Decision

1. **A conclusion reads the card it describes.** The per-partition event sentence takes its
   classes from `scorecard.target`, the target the partition was actually scored for. The
   payload continues to declare the artifact's own target and classes. The limitation naming
   a mismatch is unchanged, so the report states both facts instead of publishing one of them
   as a false pairing.
2. **A disagreement requires two verdicts.** The distribution-versus-event paragraph runs
   only when both verdicts exist. A missing side makes no claim.
3. **No event measurement produces no event claim.** The rolling-origin and decay
   conclusions state that no target-event score exists and that the event baseline was never
   compared. The origin report continues with its distribution conclusions; the decay report
   returns there, because its drift cannot be dated against a horizon that produced no
   reading.
4. **Counts name the measurement they count.** The decay drift sentence counts horizons that
   produced a target-event score, not horizons that produced any score. One such reading is
   named as a single measurement, not a decay curve, and a horizon without an event reading
   is named rather than silently excluded.
5. **Terminal and written summaries follow the same rule.** The rolling-origin and decay
   `describe_result` functions and both written summaries print the event count beside the
   event claim, say when there was no event measurement instead of formatting `None`, and do
   not print a zero denominator as if it were a result. A single measured origin or horizon
   is named as the only one, not as "all" of a set it did not measure.

## Alternatives considered

- **Remove the mismatch path and refuse to build a report for another target.** Rejected:
  scoring one target against another artifact is a legitimate diagnostic the report already
  supports and explains; refusing it would remove the limitation that makes it honest.
- **Keep the artifact's classes in the conclusion and rely on the limitation.** Rejected:
  the limitation says the numbers are not comparable while the conclusion states an event
  pairing. A reader who reads only the conclusion would be misled, and the report exists to
  be read.
- **Treat a missing event verdict as "not beaten".** Rejected: that is the defect, not the
  fix. An abstention is not a failed forecast (ADR-0029), and an unmeasured score is not a
  lost comparison.
- **Print the event figures only when every scored card carries one.** Rejected: a partial
  table is still evidence about the horizons that were measured, and the report already
  knows how to date a subset of readings (ADR-0030). The fix is to count and name the subset,
  not to discard it.

## Consequences

- Reporting text changed in `training/report.py`, `training/decay.py` and
  `training/origins.py`; no score, cohort, calibration, artifact or API field changed. JSON payloads are unchanged except that the
  conclusions and summary strings now say what was measured.
- Four existing decay assertions were updated to the new wording ("produced no target-event
  score", "horizons that produced a target-event score"). The behaviour they pin — dating
  the ends, naming a silent horizon, refusing a one-reading curve — is unchanged.
- The decay summary uses an em dash in `one reading, not a drift`; it is written to a UTF-8
  file, and every terminal line remains cp1252-encodable, which the existing encoding test
  continues to check.

## Validation

- Sixteen tests were added across `tests/training/test_report.py`,
  `tests/training/test_origins.py` and `tests/training/test_decay.py`. Twelve were watched
  failing against the pre-fix modules: both per-partition tests, the missing-verdict and
  zero-event conclusions, the two partial-table tests, the three terminal/summary tests, the
  two origin-table tests and the single-winning-reading test. Four pin sentences that already
  existed and must not change.
- The reproduction is in the tests themselves: scoring `final_chart_cnf_or_rac` against a
  `final_chart_cnf` artifact, replacing a card's event fields with `None`, and blanking the
  event fields of one or all but one horizon.
- Full backend suite after the change: 1105 passed, total coverage 96.51%. Ruff clean.
  mypy clean in 44 source files.
- No synthetic or real-data claim is introduced: every fixture remains a labelled synthetic
  pipeline fixture, and no probability, calibration or artifact was promoted.
