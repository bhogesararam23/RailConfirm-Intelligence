# ADR-0009: Trust boundaries for model artifacts and unverified status codes

- **Status:** Accepted. The artifact format identifier in the Decision section is
  superseded by ADR-0013, which raises it to `railconfirm.frequency-baseline/2` to make
  the declared cohort-status rule and consumed-feature list load-time requirements.
  Everything else here stands.
- **Date:** 2026-10-23
- **Decision owner:** Project maintainer
- **Related:** ADR-0002, ADR-0004, ADR-0005, ADR-0007, docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md, docs/model/STATUS_GLOSSARY.md

## Context

Auditing the implemented foundation found three places where the system could present an unsupported claim as a trustworthy one.

1. `ModelRegistry.has_model()` returned true when a file named `<active_version>.pkl` existed. Existence was the only check: no metadata, no version agreement, no target agreement, no approval state. `InferenceEngine` then reported the configured model version on the response while every passenger abstained with `no_trained_model`, so a broken or foreign artifact was indistinguishable from "nothing trained yet". The chosen extension was also pickle, which executes arbitrary code on load — incompatible with ADR-0005 and the security requirement that data and model inputs must never reach a code path.
2. `HistoricalFrequencyBaseline` smoothed whatever dictionary it was handed. A cohort keyed `{"CONFIRMED": 100}` matched no outcome class, and because those foreign counts were summed into the denominator and the result renormalised, the estimator returned a flat 0.2 per class — a confident distribution built from zero usable evidence. Negative and NaN counts surfaced as unhandled errors mid-request; a table fitted with lowercase cohort keys silently never matched.
3. Status mapping 1.0.0 mapped `CK` to `WL/CKWL` on an inline comment admitting the semantics "need verification". No reference exists in the repository. A guessed family joins the waitlist population in both datasets and predictions.

## Decision

**Artifact format is JSON, validated before use, and activation needs two independent gates.**

- An artifact is a JSON document at `models/<version>.json` declaring `artifact_format` `railconfirm.frequency-baseline/1`. Deserialisation is limited to project-defined data; nothing is reconstructed as a Python object. Pickle is not an accepted artifact format at any version.
- Metadata must state the version, target, estimator name, feature-schema version, status-mapping version, exact outcome class order, dataset id and SHA-256, data approval status, synthetic flag, fitting window, smoothing and threshold settings, limitations, and promotion. Any mismatch against the request — a different version than the file it was read from, a different target than the one asked for, a different class order — rejects the artifact rather than repairing it.
- Serving requires both `RAILCONFIRM_ACTIVE_MODEL_VERSION` naming the version and the artifact's own metadata declaring `approved_for_local_use`. A file appearing in the models directory activates nothing.
- An artifact whose training data is not approved, or which is fitted on synthetic records, cannot serve estimates regardless of its promotion state.
- Artifact reads are bounded by `RAILCONFIRM_MAX_ARTIFACT_BYTES` before the file is read, and the version becomes a file name only after matching a character class that cannot traverse a path. Relative configured directories resolve against the repository root, not the working directory.

**Abstention reasons name the specific gate that is closed.** `no_trained_model` (nothing promoted), `model_artifact_invalid` (configured but rejected) and `no_approved_data` (no approved evidence base) are separate codes, because each calls for different unfinished work. A configured-but-broken artifact is never reported as absent.

**Frequency tables are validated when installed, and installation requires provenance.** Cohort keys are canonicalised (class, quota, status uppercased) and collisions are rejected; counts must be non-negative integers over the declared outcome classes with a positive total; unknown outcome keys are an error, not something to renormalise away. A table cannot be installed without `FrequencyTableProvenance`, and only a real dataset explicitly marked approved may yield an estimate. Each supported outcome records `basis`: the matched cohort, its sample size, and whether a broad-cohort fallback was used instead of an exact match.

**Unverified status families stay unknown.** Mapping 1.1.0 removes the `CK`/`CKWL` guess; both now resolve to `UNKNOWN` with a note naming what must be verified before re-admission. A discarded position token is reported in `parse_note`, so "source omitted the position" and "source gave an unusable position" are distinguishable.

## Alternatives considered

- **joblib or pickle artifacts with a signature check.** Rejected: signature verification still leaves a code-execution surface at load time, and the only estimator this build serves is a tabular frequency model whose natural serialisation is data, not objects.
- **Load-time coercion of malformed counts** (clamping negatives, ignoring unknown keys). Rejected: it manufactures a distribution from a table that cannot support one, which is the failure this ADR exists to remove.
- **A single `no_data` reason code.** Rejected: it hides whether the unfinished work is dataset approval, training, or artifact validation, and each of those has a different owner and cost.
- **Keeping `CK` mapped to waitlist behind a "unverified" flag.** Rejected: any flag that leaves the estimate flowing makes the guess load-bearing downstream; unknown must mean abstain at the boundary.
- **Serving the baseline table directly from a dataset file at request time.** Rejected for now: it duplicates registry policy and gives two code paths for promotion. The artifact is the single way trained state reaches inference.

## Consequences

- Everything abstains today, which is the correct state: no artifact is promoted and no dataset is approved. The observable difference from before is that the reason now identifies the open gate.
- A future training pipeline must emit this artifact format; a trained model that cannot declare its dataset SHA-256 and target cannot be promoted.
- The artifact surface is limited to the frequency baseline. A genuinely learned model needs its own format identifier and its own ADR before it can be served.
- `CK`/`CKWL` rows in any candidate dataset are now rejected as unknown labels, which will show up as an exclusion count in dataset reports. That is the intended review signal, and re-admitting them is a documented, sourced change.
- Two reason codes are added to a public contract, so the frontend and `docs/architecture/API_CONTRACT.md` must carry them.

## Validation

- `backend/tests/inference/test_registry.py`: 44 tests covering every resolution state, metadata rejection, the path-safe version check, the size limit, refusal to load a non-JSON/pickle file, and deterministic round-trip serialisation.
- `backend/tests/inference/test_engine_artifact.py`: engine behaviour across registry states, including that an artifact for one target cannot answer a request for another.
- `backend/tests/inference/test_baseline.py`: 47 tests covering malformed counts, colliding and lowercase cohort keys, unapproved and synthetic provenance, out-of-queue statuses, and hand-checked smoothing arithmetic.
- Revisit when a real trained model exists (it will need a new format and ADR), or if a source is found that verifies `CK`/`CKWL` semantics.
