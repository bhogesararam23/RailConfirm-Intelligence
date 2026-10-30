# ADR-0034: An artifact fitted under another feature schema or status mapping is refused, not served

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0009 (artifact trust boundaries), ADR-0013 (as-of cohort rule and
  `FEATURE_SCHEMA_VERSION` 3.0.0), ADR-0022 (a contract definition lives in the domain so
  serving does not import the pandas stack), ADR-0023 (comparison requires one contract),
  `backend/railconfirm/inference/artifacts.py`, `backend/railconfirm/domain/prediction.py`

## Context

An artifact declares which feature schema and which status mapping it was fitted under. Both
were validated as *non-empty strings* and nothing more:

```python
for name in ("feature_schema_version", "status_mapping_version", ...):
    _require(isinstance(value, str) and bool(value.strip()), ...)
```

Everything else in the metadata block is checked against this build — the target, the
estimator, `outcome_classes`, `features_used`, `cohort_semantics`, the promotion state and the
dataset approval. The two versions that say *how the cohort keys were built* were the pair left
unchecked.

Three facts show that this is a missing rule rather than a deliberate latitude.

1. The module's own docstring says the registry "only serves artifacts whose declarations match
   the request". ADR-0013 says `FEATURE_SCHEMA_VERSION` was raised to 3.0.0 "so artifacts can be
   rejected rather than silently misread", and `docs/research/EVALUATION_PROTOCOL.md` repeats
   that purpose. No code performed the rejection.
2. The difference is load-bearing for this estimator. The cohort key is
   `(class_code, quota_code, asof_normalized)`: the third part is the normalized status, so a
   different `status_mapping_version` means the same raw value may have been counted under a
   different key; and `FEATURE_SCHEMA_VERSION` 3.0.0 changed *which* status is derived — a row
   with a blank `current_status` now falls back per row instead of becoming `UNKNOWN`. A table
   counted under another derivation would be read here with a rule it was never keyed by.
3. The shared artifact fixture declared `feature_schema_version: "1.0.0"` while this build
   derives 3.0.0, and the pipeline fixture declared `"2.0.0"`. Both loaded and served. A test,
   `test_ready_artifact_reports_its_own_feature_schema`, wrote an artifact declaring `"2.3.0"` —
   a version this build has never had — and asserted that it was served and echoed back into the
   prediction record. The gap was encoded as a feature.

What serving such an artifact produces is not a crash. The lookup for the derived status either
misses its exact cohort (and is answered from the broad `(class, quota, ALL)` row, silently
estimating a different population) or hits a cohort that was counted under a different rule.
Either way the request is answered with numbers from a table this build cannot vouch for, and
nothing in the response says so — the failure ADR-0013 describes one layer in, reached from one
layer out.

A second, smaller instance of the same drift: `PredictionRecord.feature_schema_version`
defaulted to the literal `"1.0.0"`, and `InferenceEngine.predict` set the same literal on the
path where no artifact serves. Every abstained record therefore claimed a feature schema two
majors behind the build that produced it, and the constant existed in three places.

## Decision

1. **Both versions are compared to this build at metadata validation.** `metadata_from_mapping`
   refuses an artifact whose `feature_schema_version` differs from `FEATURE_SCHEMA_VERSION` or
   whose `status_mapping_version` differs from `MAPPING_VERSION`. The message names the
   artifact's value, the build's value and why they cannot be reconciled — a refit or a written
   migration, not an interpretation. The registry reports this as `artifact_invalid`, so the
   request abstains with `model_artifact_invalid` and the reason in `limitations`.

2. **The version constant lives in the domain, beside the target definitions.**
   `FEATURE_SCHEMA_VERSION` moved from `railconfirm.data.preprocessing` to
   `railconfirm.domain.prediction` and is re-exported by the feature module, so every existing
   import keeps working. Serving needs the version to refuse an artifact, and importing
   `data.preprocessing` for one string would put pandas in the serving process and make the
   inference layer depend on the feature-construction package — the objection ADR-0022 already
   upheld for the target-to-event table. The column list stays where the columns are built.

3. **A record always states the schema this build applies.** `PredictionRecord`'s default and
   the engine's no-artifact branch now read the constant instead of repeating a literal, so an
   abstained response reports `3.0.0` — the derivation its inputs would have been given — rather
   than a version no longer in the build.

4. **Fixtures declare this build's contract.** The two shared artifact fixtures now derive the
   declaration from the constants instead of hardcoding older versions, so a fixture cannot drift
   into testing an unservable artifact by accident.

5. **No format or report version changes.** The artifact layout is unchanged and every key keeps
   its meaning; only which files are accepted changed. The report shapes do not publish these
   checks and gain nothing. A previously fitted artifact that declares this build's constants
   loads exactly as before, and the fitter writes them from the constants, so no model fitted by
   this project is affected.

## Alternatives considered

- **Migrate the artifact on load** — rewrite the declared versions to this build's, or recompute
  the cohort keys. Rejected: the cohorts would still be counts of a derivation this build cannot
  reproduce, and a rewritten version string turns an unverifiable table into an apparently
  current one. A migration has to know what changed; the build does not.
- **Accept any version and record the mismatch in `limitations`.** Rejected: the estimate would
  still be served, and a caveat beside a number is what ADR-0017 rejected for calibration and
  ADR-0022 for a target mismatch. `model_artifact_invalid` exists so a broken artifact cannot
  masquerade as a working one.
- **Compare only the major version.** Rejected: nothing in the schema contract promises that a
  minor bump leaves cohort keys alone, and the 3.0.0 change was a *derivation* change, not a
  layout change. Guessing compatibility is the interpretation this rule exists to avoid.
- **Import `data.preprocessing` in the inference layer to read the version.** Rejected: it puts
  pandas in the serving process for one string and inverts the stated separation between feature
  construction and serving (ADR-0022).
- **Leave `"1.0.0"` as the record default and only fix the engine.** Rejected: the default is
  what direct construction uses, and two copies of a versioned constant is how the third copy
  drifted; there is one constant and every consumer reads it.
- **Bump `ARTIFACT_FORMAT` to announce the stricter loader.** Rejected: the layout that a reader
  must parse did not change, and a format bump would make the new build reject files for the
  wrong reason. The loader's rule is stated in its refusal message and in the protocol.

## Consequences

- An artifact fitted by another feature derivation abstains with `model_artifact_invalid` and a
  reason that names both versions, instead of answering from cohorts keyed under a rule this
  build does not apply.
- `feature_schema_version` on a response now always names a schema this build has, including on
  abstentions; a consumer comparing records no longer sees a stale constant.
- The domain owns the feature-schema version and the feature module re-exports it. A future bump
  is one edit, and the loader cannot silently fall behind it.
- The two shared fixtures now publish this build's contract, so a test that wants to exercise a
  mismatch must ask for one explicitly — which is what the new refusal tests do.
- Nothing here is evidence about railway behaviour, and nothing promoted exists to be refused:
  the only artifacts in the repository are synthetic fixtures.

## Validation

`backend/tests/inference/test_engine_artifact.py`: `test_ready_artifact_yields_supported_estimates`
now asserts the served record reports `FEATURE_SCHEMA_VERSION`;
`test_an_artifact_fitted_under_another_feature_schema_is_refused` and
`test_an_artifact_fitted_under_another_status_mapping_is_refused` assert the abstention reason,
the `artifact_invalid` limitation and that both versions appear in the stated reason; and
`test_an_abstention_reports_the_feature_schema_the_build_applies` covers the no-artifact path.
`test_ready_artifact_reports_its_own_feature_schema` was deleted because it asserted the defect.
The backend suite (1078 tests), Ruff, mypy and the repository hygiene script were run before this
decision was committed.
