# ADR-0022: A calibration artifact's identity is its target's event, and only validation may carry a fit

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0004 (chronological evaluation and calibration policy), ADR-0009
  (artifact trust boundaries), ADR-0011 (target-event scoring), ADR-0017 (the calibration
  layer itself), ADR-0019 (subgroup calibration), ADR-0021 (paired comparison),
  `backend/railconfirm/inference/calibration.py`,
  `backend/railconfirm/training/metrics.py`, `docs/research/EVALUATION_PROTOCOL.md`

## Context

ADR-0017 added `platt_logistic_v1`: one slope and one intercept fitted on validation rows
and applied to the target event's mass. It fixed where the correction is fitted and where
it is measured, but it left the *identity* of the correction as free-text beside the target
it belongs to. `CalibrationSpec` accepted any `target` string, any `event_classes` tuple,
and any `fitted_partition` string, and `apply_calibration` was happy to apply a block to
whichever event the caller named.

That produced four reachable contradictions, reproduced against the code before the fix:

- A block declaring `target: final_chart_cnf` with `event_classes: ["CNF", "RAC"]` loaded
  successfully. The served CNF probability then carried a correction fitted on the merged
  CNF+RAC event.
- The same spec produced **0.103448** on the served path and **0.058824** on the scored
  path, because serving corrected CNF+RAC while scoring corrected CNF. Two numbers for one
  claim, from one artifact, with nothing in the artifact to say which was meant.
- `fitted_partition: "test"` loaded successfully: a correction tuned to the locked rows it
  would then be credited with, which is the one thing ADR-0004 exists to prevent.
- An unknown `target` such as `not_a_target` was accepted, so an artifact could declare a
  question this build cannot answer.

None of these are arithmetic errors. They are identity errors: the arithmetic is right for
the correction it was given, and the artifact lies about which correction that is.

## Decision

**1. The target determines the event, once.**

`EVENT_CLASSES_BY_TARGET` lives in `railconfirm.domain.prediction` — `final_chart_cnf` is
`("CNF",)`, `final_chart_cnf_or_rac` is `("CNF", "RAC")`. It is a property of the target,
not of the pipeline that consumes it, so scoring (`training.metrics`), calibration
(`inference.calibration`) and serving all read the same table. `training.metrics` keeps the
name `TARGET_EVENTS` for the reports that were already written against it, but it is no
longer a second definition.

**2. A calibration block must agree with its own target.**

`CalibrationSpec.__post_init__` refuses a block whose `event_classes` differ from the event
its `target` names, and refuses a `target` this build does not define. The check order is
deliberate: an empty `event_classes` is reported as an empty event, and a target mismatch is
reported as a target mismatch, so the message names the field the reader has to fix rather
than the subtlest consequence of it.

**3. A block may only claim a fit on validation.**

`FITTABLE_PARTITIONS = ("validation",)`, enforced at construction. Fitting on `test` is
refused rather than noted, because a spec that says so is already a correction selected on
the rows it is scored against, and a footnote cannot repair that.

**4. The served path and the scored path correct the same mass, or neither runs.**

`apply_calibration` takes the event as an argument and raises when it disagrees with the
spec's own event, so a caller cannot score one event while serving another. `score_rows`
additionally refuses a calibration whose target differs from the target being scored,
before any arithmetic, so the failure names the two questions rather than the two tuples.

**5. The artifact loader checks the block against the artifact, in the right order.**

`spec_from_mapping` compares the declared target with `artifact_target` *before*
constructing the spec. A block written for a different target is a different question; a
block whose event classes contradict its own target is a malformed block. Reporting the
second when the first is true would send a reader to fix the wrong field. The
`event_classes` container is validated before construction too, so a bare string cannot be
iterated into characters and reported as an event nobody wrote.

## Alternatives considered

- **Treat the event classes as the free variable and derive the target from them.** Rejected:
  several targets could then share an event, and the artifact's `target` field — the thing
  the API contract and history records quote — would stop meaning anything.
- **Coerce a mismatched block instead of refusing it**, e.g. rewrite CNF+RAC to CNF. Rejected:
  silently reinterpreting a fitted slope as belonging to a different mass is exactly the
  class of error ADR-0009's artifact trust boundary exists to prevent.
- **Accept `fitted_partition: "test"` and mark it in the artifact's limitations.** Rejected:
  the number would still be published, and ADR-0017's guarantee would become a caveat.
- **Keep the mapping in `training.metrics` and import it from inference.** Rejected: it
  would make the serving path depend on the pandas training package for one small table, and
  leave the definition owned by a consumer rather than by the domain.

## Consequences

- An existing artifact that declares a target/event mismatch or a `test`-fitted correction
  now fails to load. No such artifact exists in this repository, and none can have been
  produced by `training.calibration`, which only ever fits on validation.
- `final_chart_cnf_or_rac` artifacts can carry their own calibration; they simply must say
  so in both fields.
- The score card's `calibration_applied` flag and the served `basis` marker keep describing
  the same correction, because both now come from a spec that cannot be ambiguous.
- This does not validate any correction. It makes an invalid one impossible to publish.

## Validation

- `tests/inference/test_calibration.py` covers the target/event coupling, the empty-event
  message order, the partition refusal, the load-time refusal of a block written for another
  target, and the applied-event disagreement, in both directions (CNF spec on CNF+RAC, and
  CNF+RAC spec on CNF).
- `tests/inference/test_registry.py` covers the same refusals through the real artifact
  loader, including a target switch and an empty `event_classes` list in the JSON.
- The merged-event test that previously applied a CNF-fitted spec to the CNF+RAC event was
  rewritten to declare a CNF+RAC spec: the old test encoded the defect.
