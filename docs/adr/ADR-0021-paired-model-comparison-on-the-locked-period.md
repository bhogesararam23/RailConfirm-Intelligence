# ADR-0021: Paired model comparison judged on the locked period

- **Status:** Accepted
- **Date:** 2026-10-24
- **Decision owner:** Project maintainer
- **Amended by:** ADR-0039 adds a pre-declared exact sign test to the locked-period
  conditions; every other part of this decision stands.
- **Related:** ADR-0011 (candidate-only artifacts, target-event scoring, promotion is human),
  ADR-0013 (one as-of rule across fit/score/serve), ADR-0017 (calibration is measured on the
  locked test; the same discipline applies to a model choice), ADR-0018 (decay over time),
  ADR-0019 (subgroup gaps each comparison publishes), ADR-0020 (the candidate this decides on),
  `backend/railconfirm/training/compare.py`, `backend/railconfirm/training/report.py`,
  `docs/research/EVALUATION_PROTOCOL.md`

## Context

Roadmap Phase 4's exit gate is "candidate evaluated on locked later journeys and compared with
baseline". Until now the repository could fit two models and score each on its own split, but
could not answer the question a promotion actually asks: on the same rows, with the same
yardstick, is the candidate better where it has not been chosen?

That qualifier is the whole problem. The validation window is where candidates are picked, so
it is the window they flatter themselves in — the same reason ADR-0017 refuses to embed a
calibration layer that only helps in-sample. The two fixtures used while building this show the
effect in both directions:

- On a fixture whose labels depend on queue position, the candidate was **worse** on validation
  (Brier `0.295680 → 0.366304`, delta `+0.070624`) and **better** on the locked period
  (`0.375680 → 0.337007`, delta `-0.038673`; event `0.184984 → 0.156482`; 62 paired wins against
  18 losses). A rule that read validation would have rejected a model that generalises.
- On a fixture whose labels ignore position, the candidate was better on validation's event
  score and much worse on the locked period (`+0.172314` distribution, 32 wins against 48
  losses). A rule that read the better of the two windows would have accepted noise.

Neither mistake is hypothetical, and neither is caught by looking at aggregate scores alone:
the second fixture's aggregate story and the first's differ only in which window they are read
from.

## Decision

**1. One split, or there is no comparison.**

`run_model_comparison()` takes two already-fitted models and refuses unless their split
partitions agree by name, boundaries and row count, and unless their training-window
prevalence distributions are identical. "Fit both on the same settings and hope" is not a
check; a different window can move these numbers further than a different model does.

**2. The candidate must be a different estimator, and both must target the same event.**

Two versions of one estimator differ by settings, which is a different question needing its
own rule. A baseline for `final_chart_cnf` cannot be differenced against a candidate for
`final_chart_cnf_or_rac`: the two headline numbers answer different questions.

**3. One prevalence baseline, shared.**

Both models are scored against the outcome shares of the shared training window, so every
skill and "beats the baseline" statement in the comparison refers to the same reference. A
comparison against two baselines is two unrelated evaluations printed side by side.

**4. Rows are paired by partition position, not by identity.**

Both models walk the same frame in the same order, so the row's position is a stable key even
when the models abstain on different rows — which is exactly when a naive key would silently
drop or duplicate rows. A row both answered is a win, a loss or an exact tie on the target
event's squared error. A row only one model answered is counted as `only_baseline_scored` or
`only_candidate_scored` and is **never** counted for either side.

**5. Coverage is a condition, not a footnote.**

A candidate that abstains more can improve every average it is measured on simply by dropping
the rows it answers badly. The verdict requires `candidate.coverage >= baseline.coverage`; a
coverage drop produces `baseline` with a reason naming both percentages, however good the
scores look.

**6. The verdict reads the locked period only, and needs all four things at once.**

`candidate` requires, on the `test` partition: distribution Brier improved, event Brier
improved, coverage not worse, and strictly more paired wins than losses. Anything else is
`baseline`. If the locked period produced no rows both models answered, or either model scored
nothing, the outcome is `undetermined` — which is not a pass, and the reason says so. There is
no flag to choose another deciding partition, for the same reason decay takes its cutoff from
the artifact (ADR-0018).

**7. The paired lens is the event the passenger is handed; the distribution is still required.**

Wins and ties are counted on the target event's squared error, because that is the number a
user reads. The distribution Brier must improve too, so a candidate cannot win the headline by
moving mass between the classes inside the event's complement — and the report states which
lens the counts use rather than leaving a reader to infer it.

**8. Reasons carry their numbers, and the method line names what this is.**

Every verdict is followed by lines like
`Locked period decided on: test: distribution Brier 0.37568 -> 0.337007 (delta -0.038673), …
paired 62 wins / 18 losses / 0 ties over 80 rows both answered`, and each failure is its own
named block. The report's method line is
`same split, one prevalence baseline, paired per-row comparison judged on the locked period`,
its own schema version, and its limitations say plainly that no calibration layer is applied
here and that one locked period settles these rows only.

**9. The card and the paired rows come from one scoring pass.**

`score_partition(..., pre_scored=…)` accepts rows a caller already walked. Before it, the
comparison had to score each partition twice — once for the aggregate, once for the pairing —
which is how an average and a row count could drift apart while both looked correct. The
parameter is named `pre_scored` rather than `scored` because `scored` already means "number of
scored rows" inside that function; the collision was caught by the type checker, not by a test.

## Alternatives considered

- **Decide on whichever window looks better.** Rejected: that is exactly how a candidate gets
  chosen and then sold, and it is the failure the first live fixture above demonstrates.
- **Average validation and the locked period into one score.** Rejected: averaging the window
  the candidate was selected on with the window that tests that selection hides it in both
  directions.
- **A McNemar-style significance test on paired wins and losses.** Deferred, not rejected: the
  counts are published so a reader can compute it, but a significance level has to be chosen
  before seeing the data, and a threshold invented now would be the same arbitrary margin
  rejected below.
- **Require a minimum margin (say 1 % relative).** Rejected: the margin would be a guess
  unrelated to any real dataset's variance, and a fixed bar invites tuning a candidate until it
  clears the bar. The rule requires direction and consistency across four conditions, and leaves
  magnitude to the human promoting.
- **Let the caller name the deciding partition.** Rejected for the reason ADR-0018 gives for its
  cutoff: a caller-supplied deciding window lets the comparison be arranged.
- **Count rows one model refused as losses for it.** Rejected: an abstention is a coverage fact,
  and ADR-0011 already refuses to score abstentions as errors. Coverage is handled as its own
  condition instead (Decision 5).

## Consequences

- A fourth question has a command: `fit` (produce a candidate), `evaluate` (score one
  artifact), `origins`/`decay` (how it behaves over time), and now `compare` (whether one model
  may replace another). Each prints its method line, and the reports have distinct schema
  versions, so a number cannot be quoted as answering a different question.
- On synthetic fixtures the harness can say `candidate` — and does, on the position-informative
  fixture — without that being evidence about railways. Both fixtures were built to have known
  answers, and the real question stays where it was: no approved dataset, so no promotion.
- Promotion stays a human act. The verdict is evidence with its numbers printed next to it; the
  artifact file still has to be edited to `approved_for_local_use` and named in configuration,
  and a synthetic artifact is still refused by the registry whatever any report says.
- Nothing in the serving path changed. `compare` fits models from a dataset in memory; it never
  writes an artifact, so it cannot activate a model.
- The comparison inherits ADR-0019's per-segment gaps for both models, so a candidate that wins
  overall while misaligning a cohort is visible in the same payload.

## Validation

- `backend/tests/training/test_compare.py` — 29 tests. Paired accounting on hand-built rows:
  wins, losses and exact ties; a hair of difference counted as a win, proving no epsilon band;
  rows one model refused kept out of both columns; positions pairing the same reservations
  across differing abstentions; order-independence; nothing-scored being incomparable rather
  than tied; and the distribution difference being ignored by the event lens. The verdict rule
  on constructed partitions: candidate only on all four conditions; event win with distribution
  loss refused; coverage drop refused with a named reason; ties not accumulating into a win; no
  locked partition or no comparable rows giving `undetermined` without a pass-flavoured word;
  and a validation win the locked period does not repeat reported as both things.
  Through the pipeline: method line, both partitions scored against one shared prevalence
  baseline, `rows_total` matching the partition, the run's verdict equal to
  `decide_verdict(result.partitions)`, refusals for different splits, the same estimator on both
  sides, and mismatched targets, plus row-level arithmetic consistency between the paired counts
  and the published scorecards. Report: schema and method lines, both estimators named, every
  published comparative field defined, the four limitations that bound the claim, byte-identical
  repeats, and no "recommend the candidate" wording when the verdict is not candidate. CLI: exit
  0 with a printed verdict and report, cp1252-encodable output, and an unknown candidate
  estimator refused with exit 1.
- Live runs on labelled synthetic fixtures built for the purpose (OS temp directory, deleted
  after; full transcript in `docs/DEVELOPMENT_LOG.md`): position-informative fixture →
  `Verdict: candidate`, validation delta `+0.070624` against locked deltas `-0.038673` and
  `-0.028502` with 62/18 paired wins; position-blind fixture → `Verdict: baseline` with three
  named blocks (distribution `+0.172314`, event `+0.077057`, 32 wins against 48 losses). Same
  harness, opposite answers, each traceable to printed numbers.
- Gates: `pytest tests/ --cov-fail-under=90` → 947 passed at 96.17% branch coverage; `ruff`,
  `mypy` (44 files), the repository hygiene script and the frontend suite — results recorded in
  `docs/DEVELOPMENT_LOG.md`.
