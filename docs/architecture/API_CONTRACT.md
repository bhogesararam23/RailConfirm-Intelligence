# API contract

Status: initial interface proposal; no API implementation is implied.

## General requirements

- Version the public API under `/v1`.
- Validate all incoming fields.
- Do not accept passenger names as required prediction inputs.
- Preserve manual inputs separately from provider observations.
- Every returned estimate must include its target definition, prediction timestamp, model version, evidence status and limits.
- Return a structured unsupported/abstain result instead of a fabricated probability.
- Never return raw provider credentials or unnecessary provider payloads.

## Manual prediction request

Proposed route: `POST /v1/predictions/manual`

Conceptual request shape:

```json
{
  "journey": {
    "train_number": "string",
    "journey_date": "YYYY-MM-DD",
    "boarding_station": "string",
    "destination_station": "string",
    "class_code": "string",
    "quota_code": "string"
  },
  "prediction_at": "ISO-8601 timestamp",
  "passengers": [
    {
      "original_status": "source status string",
      "current_status": "source status string",
      "current_status_observed_at": "ISO-8601 timestamp"
    }
  ]
}
```

This is a design example, not a live API or a valid railway-status assertion. Exact enum values and constraints belong in the implemented schema.

## Response concepts

A supported prediction response should include:
- request/prediction ID that is not a raw PNR;
- `target_definition`;
- `prediction_at`;
- model and schema version;
- per-passenger mutually exclusive outcome probabilities;
- group event probabilities when supported;
- evidence freshness and coverage state;
- uncertainty/abstention status;
- limitations.

The API must state whether probabilities include an explicit OTHER/UNKNOWN outcome or are conditional on a restricted eligible outcome set.

## Errors

Use consistent error responses for invalid input, unknown status, unsupported category, no trained model, insufficient evidence, provider failure, rate limits and server errors. Do not turn upstream failure into a zero probability.

## Future tracking routes

Potential routes such as `POST /v1/tracking` and `GET /v1/tracking/{tracking_id}` must remain unavailable until an approved provider integration and retention controls are implemented. Raw PNRs should not appear in path parameters.

## Compatibility

Version changes that alter probability semantics, outcome classes, data retention or request fields require specification updates, tests and an ADR when the change is material.
