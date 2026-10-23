# Storage model

Status: logical schema proposal, plus one implemented table. The tables below are still a
design; what exists in code today is described first.

## What exists today

`backend/railconfirm/storage/predictions.py` implements one SQLite table, created on
demand and off by default (ADR-0012):

```
predictions(
  prediction_id  TEXT PRIMARY KEY,   -- the internal UUID the API returned
  recorded_at    TEXT NOT NULL,      -- fixed-shape UTC, second precision
  expires_at     TEXT NOT NULL,      -- recorded_at + retention_days (floor: 1)
  target         TEXT NOT NULL,
  model_version  TEXT NOT NULL,
  schema_version INTEGER NOT NULL,   -- read refuses a version it does not understand
  payload_json   TEXT NOT NULL       -- the response the user was served
)
```

This is the document's "validated JSON for an initial implementation" option for
`predictions`, not a normalisation of it: journey, passenger and observation rows do not
exist, nothing joins to them, and the store answers one question — reopen this report.
The write path refuses denied key names and PNR-shaped values, so the payload cannot grow
an identifier by accident.

Retention for this table is decided (default 30 days, minimum 1, purge to delete) because
the data is the user's own submission on their own machine, not provider-sourced records
whose terms are still under review. The paragraph below still governs every other table.

## Design rules

- Store structured, queryable data in PostgreSQL or another database selected through implementation.
- Keep licensed source data, public metadata, tracking records, training tables and model artifacts in separately controlled locations.
- Use stable random internal IDs, not raw PNRs, for routes and API resources.
- Keep observations and predictions append-only where practical.
- Add retention and deletion metadata to identifiable tracking records.
- Never commit raw datasets or model weights to the repository by default.

## Logical tables

### `journeys`
- `id` UUID primary key.
- `train_number` text.
- `journey_date` date.
- `boarding_station_id`, `destination_station_id`.
- `class_code`, `quota_code` nullable where unknown.
- `source_id`, `source_updated_at`, `created_at`.

Use a unique key only after the railway source identity and route-segment semantics are verified. Train number plus journey date alone may not uniquely describe all service/route contexts.

### `booking_groups`
- `id` UUID primary key.
- `journey_id` foreign key.
- `passenger_count` positive integer.
- `collection_basis` controlled value.
- `created_at`.
- `retention_expires_at` nullable only for records that are demonstrably non-identifiable and allowed to persist.

Raw PNR-to-internal-ID linkage, if required by an approved provider, belongs in a separately protected mapping table or secret-bearing vault with more restrictive access.

### `passenger_reservations`
- `id` UUID primary key.
- `booking_group_id` foreign key.
- `passenger_sequence` nullable integer.
- `original_status_raw`, `original_status_normalized`.
- `original_position` nullable integer.
- `original_observed_at`.
- `created_at`.

Do not add passenger name or demographic fields for the core predictor.

### `status_observations`
- `id` UUID primary key.
- `booking_group_id` foreign key.
- `passenger_reservation_id` foreign key nullable if source only provides group status.
- `source_id`, `source_record_ref`.
- `observed_at`, `source_published_at`, `ingested_at`.
- `status_raw`, `status_normalized`, `position`.
- `verification_state`, `schema_version`.

Index by group/passenger and observation time. Avoid duplicate inserts with a source-aware idempotency key.

### `final_outcomes`
- `id` UUID primary key.
- `booking_group_id`, `passenger_reservation_id`.
- `target_definition_version`.
- `outcome_raw`, `outcome_normalized`.
- `observed_at`, `verification_source_id`.
- `label_state`, `censoring_reason`.

Keep outcome labels separate from features to reduce leakage risk.

### `predictions`
- `id` UUID primary key.
- `created_at`, `prediction_at`.
- `target_definition_version`, `model_version`, `feature_schema_version`.
- `request_snapshot_ref` and/or a minimized feature snapshot, subject to retention.
- `status` supported / abstained / unavailable.
- `evidence_freshness`, `coverage_state`, `reason_code`.

Detailed probability outputs may be stored in child tables keyed by prediction and passenger/outcome, or as validated JSON for an initial implementation. Choose only after defining query and audit needs.

### `prediction_events`
Optional append-only record that links earlier and later predictions to their corresponding observation snapshots. It must not overwrite a previous estimate.

## Model artifact registry

Store metadata for model version, artifact URI, checksum, target/feature schema, calibration layer, training dataset version, evaluation report, code revision and deployment state. Artifact storage permissions should be stricter than general source documentation.

## Migrations and constraints

- Use versioned migrations.
- Add database-level constraints for positive passenger counts and valid timestamp relationships where safe.
- Do not overconstrain railway status progression: source data can be corrected or show different perspectives.
- Use transactions for a group request when passenger records must be internally consistent.
- Use database roles with least privilege.

## Retention and deletion

The implementation must define separate rules for raw provider linkage, trackable observations, de-identified research records, inference logs and model artifacts. Expiry of a ticket should trigger the applicable deletion or de-identification policy. The exact retention interval is pending a source/consent/legal review; do not invent a fixed duration in code before that review.

## Migration gate

This logical design becomes a production schema only after an ADR or implementation review resolves identity semantics, required query patterns, access boundaries and deletion behavior. Keep actual SQL migrations and generated schema documentation in sync.
