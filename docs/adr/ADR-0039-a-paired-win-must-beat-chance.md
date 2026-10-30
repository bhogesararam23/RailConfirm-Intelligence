# ADR-0039: A paired win must beat chance

- **Status:** Accepted
- **Date:** 2026-10-31
- **Decision owner:** Project maintainers
- **Related:** ADR-0016 (dependent group outcomes), ADR-0017 (calibration measured on the locked test), ADR-0021 (paired comparison judged on the locked period), ADR-0023 (one file, one contract, one row set), ADR-0038 (a conclusion names only its measurements)

## Context

ADR-0021's promotion rule requires the candidate, on the locked period, to improve the
distribution Brier, improve the target-event Brier, keep or improve coverage, and win more
paired rows than it loses. Those conditions are all direction tests. None of them asks whether
the row-level advantage is larger than the coin it is measured against.

On a 100-row locked period a candidate that wins 12 rows and loses 10 clears every condition
and is reported as a `candidate`. Under the null that the two models are equally good, that
split is unremarkable: the exact two-sided probability of a split at least that lopsided is
0.83. A rule that promotes on it is selecting on noise — the same failure ADR-0021 exists to
avoid, one layer below the partition choice. The repository states that promotion evidence is
a scientific claim and that a synthetic fixture does not establish railway accuracy; a
promotion rule that cannot distinguish an advantage from a coin is inconsistent with that
position.

A significance rule has to be declared before it is applied. Choosing an alpha after reading a
real result is the arbitrary margin the project refuses elsewhere — and the repository holds
no approved real dataset, so no real comparison has been read. Declaring it now, against
synthetic fixtures only, is the only point at which the level is genuinely prior.

## Decision

1. **An exact two-sided sign test is an additional condition for `candidate`.** Discordant
   rows — wins plus losses — are the only rows that carry information about which model is
   better; ties are excluded. Under the null each discordant row is a fair coin, so the win
   count is `Binomial(n, 1/2)`. The p-value is the exact two-sided probability of a split at
   least as lopsided as the observed one, computed in log space so a large held-back period
   does not overflow. It is not a normal approximation.
2. **The level is two-sided 0.05, declared now.** The level does not vary by run, target or
   dataset, and changing it requires a new ADR. A one-sided rule would encode the expectation
   that the candidate wins and would not detect a significantly worse candidate; the two-sided
   rule is the conservative choice for a promotion decision.
3. **At least six discordant rows are required.** The smallest attainable two-sided p at
   `n = 5` is `2/2^5 = 0.0625`, so a run below six can never be significant however one-sided
   it looks. The reason names the floor rather than raising the alpha.
4. **Significance does not replace any existing condition.** A significant row advantage with
   worse distribution Brier, worse event Brier, or worse coverage is still `baseline`. The
   failure list names the p-value, the wins, the losses, the ties and the discordant count, so
   the reader can see which condition fired.
5. **The test is published with the counts it reads.** Every partition's comparison block
   gains `sign_test_discordant`, `sign_test_p_value` and `sign_test_significant`; the report
   defines each and the method line names the test. The comparison report schema rises to
   `1.1.0` because keys were added and no existing key changed meaning.
6. **The test's independence assumption is stated as a limitation.** Passengers in one booking
   move together (ADR-0016), so rows are not independent when a locked period contains group
   bookings. The sign test is still applied — it is the pre-declared rule — but the report says
   the p-value is approximate for correlated rows and is not a group-outcome test.

## Alternatives considered

- **A normal approximation or a t-test on per-row error differences.** Rejected: the
  discriminant counts are small integers, the exact binomial is computable without an
  approximation, and an approximation invites a different p-value at the boundary without a
  reason.
- **A confidence interval on the Brier difference.** Rejected for this decision: it would need
  its own coverage level, variance estimator and dependence treatment. The sign test is the
  pre-declared rule; a bootstrap interval can be added later with its own ADR, but it is not a
  substitute for a rule chosen now.
- **McNemar's test on per-row correctness.** Rejected: the target is a probability, not a
  binary prediction, so "correct" would discard the calibration and magnitude the product is
  trying to improve. The paired lens remains the target event's squared error (ADR-0021).
- **A minimum win margin (for example, ten more wins than losses).** Rejected: a margin's
  meaning depends on the number of rows, while the exact test accounts for that directly.
- **A one-sided test at 0.05.** Rejected: a candidate that is significantly worse would pass a
  one-sided test in the wrong direction only if the rule were read upside down; the
  conservative two-sided level is the right default for a decision to replace a model.
- **Keep the direction-only rule and document the risk.** Rejected: a documented risk that the
  verdict can still say `candidate` is not a check. The rule must refuse the verdict, and the
  reason must say why.

## Consequences

- Promotion is harder. A candidate now needs at least six discordant rows and a sufficiently
  one-sided split: six wins and no losses clears the level (p = 0.03125), while a balanced
  12–10 does not (p = 0.83). A once-plausible `candidate` on a small synthetic locked period
  can become `baseline`; that is the intended effect, not a regression.
- No approved dataset exists, so no published real result changes. The live synthetic
  comparisons recorded in the development log were run under the previous rule and remain
  historical evidence about the rule at that time; their verdicts are not re-labelled.
- `PairedCount` gains three derived properties and three published keys. Construction is
  unchanged and no caller passes them in.
- The comparison report's method line and schema version change. Stored comparison reports
  carry no schema migration: they are files, not a database, and a report written before this
  decision remains a true record of the rule it was written under.
- The independence approximation is now explicit. A future group-aware paired test can replace
  it under its own ADR.

## Validation

- `tests/training/test_compare.py`:
  - exact p-values for 9–1 (`0.021484375`), 6–0 (`0.03125`), 5–0 (`0.0625`), 6–4
    (`0.75390625`) and no discordant rows (`1.0`);
  - the published counts and the significance flag, including that a thousand ties do not
    change the discordant count;
  - a 12–10 advantage with every other condition favourable is `baseline`, with the reason
    naming the wins, losses and the sign test;
  - six wins and no losses is `candidate` despite the small sample, because the exact test can
    reach the declared level at six;
  - the report defines every published comparison key, publishes a non-null p-value and a
    discordant count no larger than the rows both answered, and states the independence
    limitation.
- The command-line test checks that the terminal output prints the exact sign test and its
  discordant count, and still encodes to cp1252.
- A live comparison on the labelled synthetic fixture (`write_balanced_dataset`, 240 rows)
  printed validation p = 0.366294 over 34 wins / 26 losses and locked p = 0.897422 over
  29 wins / 31 losses, with verdict `baseline`; the rule reports the p-value it used rather
  than only its verdict.
- Full suite after the change: 1117 passed, total coverage 96.50%. Ruff clean. mypy clean in
  44 source files. No real data, calibration or artifact was touched.
