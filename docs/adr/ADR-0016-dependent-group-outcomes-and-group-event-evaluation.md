# ADR-0016: Dependent group outcomes, Poisson-binomial distribution, and queue-clearing comonotonic bounds

- **Status:** Accepted
- **Date:** 2026-10-23
- **Decision owner:** Project maintainer
- **Related:** ADR-0003 (prediction targets and dependent group outcomes),
  `backend/railconfirm/inference/group.py`, `backend/railconfirm/training/metrics.py`,
  `frontend/src/components/prediction/GroupOutcomeCard.tsx`,
  `docs/model/PREDICTION_TARGETS.md`, `docs/research/EVALUATION_PROTOCOL.md`

## Context

ADR-0003 established that passenger outcomes in a multi-passenger booking are dependent and
that joint group events must be supported. Up to now:

1. `group.py` only computed `p_all_cnf`, `p_all_cnf_or_rac`, and `p_at_least_one_wl` by
   casually multiplying per-passenger marginals under `independence_baseline`, with an
   assumption disclaimer in `assumptions`.
2. It lacked intermediate group events: the exact distribution of how many berths get
   confirmed ($P(K = k)$ and $P(K \ge k)$), which is what travellers need when deciding
   whether to travel if only part of a party gets confirmed.
3. It lacked a structured model reflecting railway queue reality: in Indian Railways,
   waitlisted passengers on the same booking share a queue context and clear sequentially
   in priority order (FIFO order), creating positive correlation where lower-priority
   passengers confirm only if higher-priority passengers have already confirmed.
4. During offline evaluation in `metrics.py`, `score_partition` scored individual passenger
   rows only. Group-level events were completely unscored, leaving the roadmap Phase 6
   requirement ("Group metrics and dependency assumptions are validated") unmeasured.

## Decision

**1. Exact Poisson-binomial distribution for independence baseline.**

For the independence baseline, compute the exact probability mass function $P(K = k)$ and
tail probabilities $P(K \ge k)$ for $k \in \{0, \dots, n\}$ using $O(n^2)$ dynamic programming
convolution of the passenger Bernoulli marginal probabilities (`compute_poisson_binomial_pmf`).

**2. Sequential queue-clearing comonotonic upper bound.**

Provide `compute_queue_dependent_bounds()` modeling the sequential queue-clearing process.
Under FIFO queue clearance:
- A lower-priority passenger confirms only if all higher-priority passengers in the booking
  confirm.
- $P_{\text{queue}}(\text{all CNF}) = \min_i P_i(\text{CNF})$.
- $P_{\text{queue}}(\text{all CNF or RAC}) = \min_i P_i(\text{CNF or RAC})$.
- $P_{\text{queue}}(\text{at least one WL}) = \max_i P_i(\text{WL})$.
- For sorted marginals $p_{(1)} \ge \dots \ge p_{(n)}$, $P_{\text{queue}}(K \ge k) = p_{(k)}$,
  and $P_{\text{queue}}(K = k) = p_{(k)} - p_{(k+1)}$.

This represents the Fréchet-Hoeffding comonotonic upper bound on joint confirmation. In the
presence of positive queue correlation, the true joint confirmation probability lies between
the independence lower bound $\prod p_i$ and the comonotonic upper bound $\min_i p_i$.

**3. Group-event evaluation in `score_partition`.**

When `booking_group_id` is present in the evaluated partition:
- Group records by `booking_group_id`.
- Track total groups, single-passenger groups, multi-passenger groups, scored groups, and
  abstained groups.
- Score both the independence baseline and the queue-clearing comonotonic bound against
  observed group outcomes using proper scoring rules (Brier score for all-CNF, all-CNF-or-RAC,
  at-least-one-WL).
- Compare against group prevalence base rates.
- Record `GroupScorecard` in `Scorecard`.
- When `booking_group_id` is absent, group metrics are cleanly `None`.

**4. Coherence and transparent assumption labelling.**

- Both methods enforce mathematical coherence: $P(K=k) \ge 0$, $\sum_{k=0}^n P(K=k) = 1.0$,
  $P(\text{all CNF}) = P(K = n) = P(K \ge n)$.
- Every method labels its assumptions in `GroupOutcome.assumptions`.

## Alternatives considered

- **Multiply marginals without Poisson-binomial convolution.** Rejected: calculating only
  all-or-nothing ignores partial confirmation, which is a major passenger question.
- **Simulate joint distributions with random Monte Carlo draws.** Rejected: exact dynamic
  programming convolution is deterministic, fast ($O(n^2)$ with $n \le 6$), and requires zero
  random seed or sampling variance.
- **Assume empirical group correlation can be estimated without group data.** Rejected:
  AGENTS.md forbids fabricating correlation parameters without approved training data.
  The Fréchet-Hoeffding comonotonic bound provides the exact theoretical upper bound
  without requiring unvalidated correlation hyperparameters.

## Consequences

- `GroupOutcome` carries `p_at_least_k_cnf` and `p_exactly_k_cnf`.
- `GroupScorecard` records joint multi-passenger performance in evaluation reports.
- The UI displays the confirmed berths distribution for multi-passenger bookings.
- When an approved dataset with booking groups is ingested, the group evaluation pipeline is
  already tested and ready to score both models against real group outcomes.
