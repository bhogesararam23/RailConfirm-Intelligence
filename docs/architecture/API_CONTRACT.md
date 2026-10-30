# API contract

Status: describes the implemented `/v1` surface of `backend/railconfirm/api/`. Fields listed here exist in `api/v1/schemas.py` and are covered by `backend/tests/api/`. A route or field is added to this document only together with its implementation and tests.

## General requirements

- Version the public API under `/v1`.
- Validate all incoming fields at the boundary; the domain re-validates independently.
- Do not accept passenger names as required prediction inputs.
- Preserve manual inputs separately from provider observations.
- Every returned estimate must include its target definition, prediction timestamp, model version, evidence status and limits.
- Return a structured unsupported/abstain result instead of a fabricated probability. A valid request the available evidence cannot support is an abstention inside a `200` response, not an invented number and not an HTTP error.
- Never return raw provider credentials or unnecessary provider payloads.

## Runtime boundaries

- CORS allows only the origins in `RAILCONFIRM_CORS_ALLOWED_ORIGINS`; `*` is refused at configuration time. Credentials are not permitted cross-origin.
- Request bodies are refused above `RAILCONFIRM_MAX_REQUEST_BYTES` with `413`.
- Every response carries `X-Request-ID`; a supplied printable id is echoed so a client and the access log can be correlated. Access logs record method, path, status and duration only — never a body, status string or passenger input.
- The unauthenticated local development server is not a production security boundary. Binding beyond loopback is a documented, deliberate act; see `docs/SECURITY_AND_PRIVACY.md`.

## Routes

| Route | Purpose |
|---|---|
| `GET /v1/health` | Liveness plus model availability, the limits in force and the history state |
| `POST /v1/predictions/manual` | Manual journey and passenger input, per-passenger and group outcomes |
| `GET /v1/predictions/{prediction_id}` | Reopen a stored report by the internal id that served it (ADR-0012) |
| `GET /v1/predictions` | List kept reports as ids, clocks and provenance only (ADR-0015) |
| `DELETE /v1/predictions/{prediction_id}` | Remove one kept report now instead of waiting for retention (ADR-0015, ADR-0040) |

## `POST /v1/predictions/manual`

Request:

```json
{
  "journey": {
    "train_number": "12301",
    "journey_date": "2026-11-15",
    "boarding_station": "NDLS",
    "destination_station": "HWH",
    "class_code": "SL",
    "quota_code": "GN"
  },
  "prediction_at": "2026-10-21T08:00:00Z",
  "target": "final_chart_cnf",
  "passengers": [
    {
      "original_status": "GNWL/45",
      "current_status": "GNWL/12",
      "current_status_observed_at": "2026-10-21T07:30:00Z"
    }
  ]
}
```

Constraints enforced:

- `train_number`: 4–6 digits.
- `boarding_station`, `destination_station`: 2–10 uppercase letters/digits, first character a letter, and the two must differ.
- `journey_date`: ISO-8601 calendar date. A datetime is rejected; the journey date carries no time by definition.
- `prediction_at`: required, ISO-8601 **with a UTC offset**, and earlier than `journey_date`. A naive timestamp is refused rather than assumed to be local or UTC.
- `target`: optional, `final_chart_cnf` (default) or `final_chart_cnf_or_rac`. The two are different questions and an artifact fitted for one cannot answer the other.
- `passengers`: 1–6 entries. More than six is rejected because the group baseline degrades and the answer stops being readable.
- `original_status`, `current_status`: non-empty after trimming, at most 120 characters.
- `current_status_observed_at`: optional, but when present it must carry an offset and must not be later than `prediction_at`. Evidence newer than the prediction timestamp would leak the outcome into the estimate.
- `persist`: optional, default `false`. Asks the server to keep this report so it can be reopened. Honoured only when the server also has history enabled (`RAILCONFIRM_PERSIST_PREDICTIONS`); `stored` in the response is the answer, not this field.

Response (`200`, shown in the current abstaining state):

```json
{
  "prediction_id": "6b1d1c2e-…",
  "target": "final_chart_cnf",
  "target_definition": "Probability that the passenger is confirmed (CNF) at final chart preparation. …",
  "prediction_at": "2026-10-21T08:00:00Z",
  "created_at": "2026-10-23T04:10:22.119289Z",
  "model_version": "no_model_v0",
  "registry_status": "no_active_version",
  "feature_schema_version": "3.0.0",
  "evidence_coverage": "insufficient",
  "is_supported": false,
  "passenger_count": 1,
  "passenger_outcomes": [
    {
      "passenger_id": "8f4a…",
      "original_status": "GNWL/45",
      "original_status_normalized": "WL",
      "current_status": "GNWL/12",
      "current_status_normalized": "WL",
      "p_cnf": null,
      "p_rac": null,
      "p_wl": null,
      "p_cancelled": null,
      "p_other": null,
      "p_target_event": null,
      "is_supported": false,
      "abstention_reason": "no_trained_model",
      "basis": null,
      "parse_warnings": []
    }
  ],
  "group_outcome": {
    "p_all_cnf": null,
    "p_all_cnf_or_rac": null,
    "p_at_least_one_wl": null,
    "method": "insufficient_data",
    "assumptions": "Group outcome is unavailable because at least one passenger outcome is an abstention.",
    "is_supported": false,
    "abstention_reason": "no_trained_model"
  },
  "limitations": ["…"],
  "warnings": ["…"],
  "outcome_classes": "CNF, RAC, WL, CANCELLED, OTHER — mutually exclusive and exhaustive over the eligible population. Probabilities sum to 1.0 per passenger.",
  "stored": false,
  "report_url": null,
  "retention_expires_at": null
}
```

Reading the response:

- `evidence_coverage` is `sufficient` when every passenger has an estimate, `partial` when some do, and `insufficient` when none do. Top-level `is_supported` means *at least one* passenger has an estimate; a mixed group is `partial`, not `sufficient`.
- Per-passenger probabilities are all `null` exactly when `is_supported` is `false`, and all non-`null` and summing to 1.0 when it is `true`. A client must not coerce a `null` probability into `0`.
- `target_definition` names the event the answer is about, and `p_target_event` is that event's probability for the passenger: the `CNF` class for `final_chart_cnf`, the `CNF` and `RAC` classes for `final_chart_cnf_or_rac`. The server sums the classes it published, so a client renders the figure the evaluation scores instead of re-deriving it; `p_target_event` is `null` exactly when the passenger abstains (ADR-0036). A report stored before the field existed reopens with the definition it was served with and no `p_target_event`, rather than being recomputed.
- `basis` names the evidence cohort and its sample size, says whether a broad-cohort fallback was used, and — when the served artifact carries one — records `calibrated=platt_logistic_v1`. A fallback is a weaker claim than a cohort match. The cohort is `(class_code, quota_code, as-of status)`, the same key the baseline was fitted under (ADR-0013, ADR-0017).
- When the active artifact declares the position estimator (ADR-0020), `basis` also names the queue-position band that answered — `band=8-15 n=41 position-aware cell used` — or records why the cohort answered instead: `band=8-15 n=1 below the 2-row band floor, cohort rate used`, or `as-of queue position unavailable; cohort rate used`. A request never receives a band label it cannot interpret, and a reader can tell a position answer from a cohort answer without seeing the artifact.
- `limitations` carries the calibration statement in full: method, fitted partition, row count, period, slope and intercept, and that the split between the classes inside the event keeps the model's own proportions. Uncalibrated artifacts keep the existing "Probabilities are not calibrated" limitation instead; the two are mutually exclusive.
- `group_outcome.method` is `single_passenger`, `independence_baseline`, or `insufficient_data`. The independence baseline assumes passenger outcomes are statistically independent, which is not true of passengers sharing a booking; the assumption is carried in `assumptions` and must stay visible in any UI that renders the numbers.
- `registry_status` reports the model registry resolution: `no_active_version`, `artifact_missing`, `artifact_invalid`, `not_promoted`, `data_not_approved`, `ready`.
- `stored` is `true` only when a copy was actually written. When `persist` was sent and nothing was kept, `limitations` carries the reason — history disabled, or a storage refusal — and the estimate is still delivered. A save failure never becomes a failed prediction, and a refused save never becomes a silent one.
- `report_url` is the server path for the stored report (`/v1/predictions/<id>`). A browser links to `/prediction/<id>`, which is the frontend's own route.

## `GET /v1/predictions/{prediction_id}`

Returns the stored response body for that id, byte-equivalent to what was served, with
`stored: true`, `report_url` and `retention_expires_at` set. Nothing is recomputed: a
reopened report is evidence about what was said then, including the `model_version` and
`registry_status` it came with.

| Outcome | When |
|---|---|
| `200` | A stored report exists for the id and is inside its retention window |
| `404` `not_found` | No report with this id, or its retention window has closed |
| `404` `history_disabled` | This server keeps no history, so no id can resolve |

A `prediction_id` shaped like a PNR (10 digits, not starting with 0) is answered with
`not_found` and a message saying reports are reopened by the id the server returned. That
endpoint is not a ticket tracker, and a PNR never becomes a lookup key by convenience.

## `GET /v1/predictions`

```json
{
  "reports": [
    {
      "prediction_id": "a1b2c3d4-0000-4000-8000-000000000009",
      "target": "final_chart_cnf",
      "model_version": "no_model_v0",
      "recorded_at": "2026-10-23T10:04:07Z",
      "retention_expires_at": "2026-10-30T10:04:07Z"
    }
  ],
  "count": 1,
  "retention_days": 7
}
```

Newest first, with `prediction_id` as a stable tie-break when two saves land in the same
second. The list is deliberately the narrowest thing that is still usable: no train number,
no stations, no statuses, no probabilities, no passenger rows. Everything about a report's
contents arrives by reopening that report deliberately
(ADR-0015 — widening this shape is a privacy decision, not a field addition).

| Outcome | When |
|---|---|
| `200` | History is enabled; `reports` may be empty because nothing has been kept |
| `404` `history_disabled` | This server keeps no history. Not the same answer as an empty list, because the actions differ |
| `500` `storage_unavailable` | A stored row contradicts itself (e.g. expiry before recording) and cannot be explained |

A report past its retention window is absent here and unreadable at
`GET /v1/predictions/{prediction_id}`: the list and the read route agree about what exists.

## `DELETE /v1/predictions/{prediction_id}`

Removes one stored row immediately. Expiry hides; this is the user asking, so the row goes.

| Outcome | When |
|---|---|
| `204` | A row was removed. No body: a deleted report must not be confirmable by reading it back |
| `404` `not_found` | Nothing was removed — never stored, already deleted, expired, wrong id, or a PNR-shaped number. One body in every case, so the route cannot be used to probe which ids this machine has held |
| `404` `history_disabled` | This server keeps no history |
| `500` `storage_unavailable` | The store refused the operation |

The interface asks twice (Delete → Confirm delete) and leaves the row listed until the
backend has answered, because a delete that did not happen must not look like one that did.

## `GET /v1/health`

```json
{
  "status": "ok",
  "model_version": "no_model_v0",
  "data_version": "none",
  "app_version": "0.1.0",
  "model_available": false,
  "registry_status": "no_active_version",
  "limits": {
    "max_passengers_per_request": 6,
    "min_sample_threshold": 30,
    "max_artifact_bytes": 4194304,
    "max_request_bytes": 65536
  },
  "prediction_history": {}
}
```

`model_available` is true only when a promoted artifact passed validation for the default target. `min_sample_threshold` is the threshold of the estimator that would actually serve the next prediction, which is the promoted artifact's own value when one is ready.

`prediction_history` is `{}` when this server keeps no reports — the default. When history is enabled it carries `enabled`, `retention_days` and `stored_reports`, because an interface that offers to save a report has to know whether saving is possible here before it offers.

## Errors

All handled errors use one envelope, including an unrouted path and a disallowed method:

```json
{
  "error": "Request validation failed.",
  "details": [
    { "code": "VALIDATION_ERROR", "message": "prediction_at=2026-10-21T08:00:00 has no timezone offset. Supply an offset-aware ISO-8601 timestamp.", "field": "prediction_at" }
  ],
  "request_id": "a829d293…"
}
```

| Status | `code` | Cause |
|---|---|---|
| `400` | `invalid_input` | Malformed `Content-Length` header |
| `413` | `REQUEST_TOO_LARGE` | Body above the configured byte limit |
| `422` | `VALIDATION_ERROR` | Request body failed schema validation; `field` is the dotted path relative to the body |
| `422` | `INVALID_PREDICTION_AT` | Timestamps cannot support a prediction: naive, on/after the journey date, or evidence newer than `prediction_at` |
| `422` | `invalid_input` | Journey constraint violation |
| `404` | `not_found` | No route matches this path, or no stored report matches this id |
| `404` | `history_disabled` | A report was requested by id from a server that keeps no history |
| `405` | `invalid_input` | The path exists but the method does not |
| `500` | `storage_unavailable` | A stored report exists but no longer matches the API contract, or disagrees with the id it is filed under |
| `500` | `INTERNAL_ERROR` | Unhandled failure. The exception text stays server-side; the response carries only the request id |

Unknown statuses, unsupported categories, an unavailable model and insufficient evidence are **not** HTTP errors: they are `200` responses carrying an abstention, so a client can present the limitation instead of guessing from a failure.

Abstention reason values: `unknown_status`, `unsupported_status`, `unsupported_class`, `unsupported_quota`, `no_trained_model`, `no_approved_data`, `model_artifact_invalid`, `insufficient_sample`, `invalid_input`. Their meanings and separations are documented in `docs/technical/INFERENCE_AND_GROUP_PROBABILITIES.md`.

## Future tracking and context routes

Potential routes such as `POST /v1/tracking` and `GET /v1/tracking/{tracking_id}` belong to the planned long-term product scope (roadmap Phases 8–10), but must remain unavailable in the current local-first build until an approved provider/source and retention controls are implemented. A later context-ingestion interface may accept normalized event records from an approved adapter or reviewed local import. Raw PNRs should not appear in path parameters. These are intended future capabilities, not proof of current functionality.

## Compatibility

Version changes that alter probability semantics, outcome classes, data retention or request fields require specification updates, tests and an ADR when the change is material.

Recent contract changes:

- `target`, `registry_status` and per-passenger `basis` added; `prediction_at` and `current_status_observed_at` now require a UTC offset; `passengers` capped at 6; `evidence_coverage` can be `partial`; errors moved to the single envelope above. ADR-0009.
- `persist` on the request and `stored` / `report_url` / `retention_expires_at` on the response added, with `GET /v1/predictions/{prediction_id}` and `prediction_history` in `/v1/health`; nothing is stored unless the server enables history *and* the request asks. ADR-0012.
- A served probability can now be the output of a calibration layer: when the active artifact declares one, `p_*` values are the corrected ones, `basis` records `calibrated=platt_logistic_v1`, and `limitations` names the fitted partition, rows, period and both parameters. ADR-0017.
- Two estimators can now serve. Which one is decided by the artifact's `estimator` and `artifact_format`, and the response shape does not change: `model_version`, `feature_schema_version`, `basis` and `p_*` mean the same thing for either. What differs is `basis`, which names the position band when one answered, and `limitations`, which for a position artifact states the band floor and how many fitted rows carried no position. An artifact whose declared estimator, format, band block and `features_used` do not agree is refused at load and the request abstains with `model_artifact_invalid` (ADR-0020).
- Per-passenger `p_target_event` added, and `target_definition` now names the requested target's event rather than describing the five-class distribution whatever the target was. The addition is backward compatible: the field defaults to `null`, so a report stored under the previous contract still validates and reopens unchanged. ADR-0036.
- `basis` now names the cohort keyed by the **as-of status**: for a served request that is `current_status`, the latest status the caller supplies at or before `prediction_at` (in dataset rows the same rule reads `current_status` and falls back to `initial_status` when the source recorded no later look). `feature_schema_version` reports the schema this build derives (`3.0.0` today) on every record, including one that abstains, and an artifact whose declared feature schema or status mapping differs from this build is refused at load rather than served: the cohort key's third part is that normalized status, so a table counted under another derivation would be read with a rule it was never keyed by (ADR-0034). A request whose as-of status has no exact cohort is answered from the broad class/quota cohort or abstains, and an artifact whose declared `cohort_semantics` differs from this build is refused at load rather than reinterpreted. ADR-0013.
