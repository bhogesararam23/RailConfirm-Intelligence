# Data contract

Status: initial specification; not yet an implemented schema.

## Design goals

- Preserve what was originally booked and what was observed later.
- Make each observation time and source explicit.
- Represent train, route segment, class, quota, booking/group and passenger outcomes separately.
- Keep source status vocabulary intact alongside normalized categories.
- Permit multiple passengers and mixed RAC/WL states under one booking.
- Support de-identification and data-retention controls.
- Avoid requiring passenger names.

## Core entities

### Journey
- `journey_id`: internal stable identifier.
- `train_number`: normalized train identifier.
- `journey_date`: local railway journey date.
- `boarding_station_id`, `destination_station_id`.
- `class_code`.
- `quota_code`.
- `scheduled_departure_at`: timezone-aware timestamp where available.
- `source_id`, `source_recorded_at`.

### Booking group
- `booking_group_id`: random internal identifier; do not use raw PNR as a public ID.
- `journey_id`.
- `booking_created_at`: only when legitimately available.
- `passenger_count`.
- `collection_basis`: licensed provider, consented input, research source, etc.
- `consent_or_authority_reference`: opaque reference if applicable, never a secret.
- `retention_expires_at`: required for identifiable or linkable tracking records.

### Passenger reservation
- `passenger_record_id`: internal pseudonymous ID.
- `booking_group_id`.
- `passenger_sequence`: sequence number when available.
- `original_status_raw`.
- `original_status_category`.
- `original_status_position`: nullable non-negative integer; keep RAC and WL semantics distinct.
- `original_observed_at`.
- `current/final labels` must not overwrite the original status.

### Status observation
- `observation_id`.
- `booking_group_id` and passenger reference where supported.
- `observed_at`: when the status was observed, with timezone semantics.
- `source_published_at`: when applicable.
- `status_raw`.
- `status_category`.
- `status_position`: nullable integer.
- `source_id`.
- `source_record_id`: opaque source linkage, with raw identifiers protected separately.
- `verification_state`.
- `ingested_at`.
- `schema_version`.

### Final outcome
- `outcome_id`.
- Booking/passenger reference.
- `outcome_target`: explicit target definition, e.g. final-chart outcome.
- `outcome_status_raw`.
- `outcome_category`.
- `outcome_observed_at`.
- `verified_by_source`.
- `label_confidence`.
- `censoring_reason`: nullable.
- `label_schema_version`.

## Normalization

Keep both raw and normalized status. Normalize only after a versioned mapping has been reviewed. Example broad categories include confirmed berth (CNF), reservation against cancellation (RAC), waitlisted (WL), cancelled, not available/invalid, and other/unknown. The exact raw values supported by the implementation must be documented in code and tests.

Do not assume all WL codes share the same queue behavior. Examples to account for in the taxonomy include GNWL, RLWL, PQWL, TQWL, RQWL and DPWL, plus any additional source-observed values confirmed by authoritative reference material. Status vocabularies can change; unknown values must be preserved and surfaced for review rather than silently coerced.

## Time and leakage rules

- Store timestamps in UTC internally when practical, preserving original timezone and local date semantics.
- Every feature set must have an explicit `prediction_at` timestamp.
- Features must be derived only from records available by `prediction_at`.
- A late-arriving historical record must not be used as if it were available earlier.
- Training snapshots for one booking/journey must stay in one dataset partition.
- Label data is stored separately from feature snapshots.

## Group outcomes

A group record must preserve all passenger-level outcomes and a stable group reference. Group probabilities must come from a model or joint distribution that accounts for dependency between passengers, not from undocumented multiplication of individual probabilities.

## Missing, censored and contradictory records

- Missing final outcomes are not automatically negative labels.
- User cancellations are not automatically confirmation failures.
- Contradictory snapshots must be flagged and resolved or excluded with a reason.
- Unknown statuses remain unknown until a reliable mapping exists.
- Synthetic fixture records must carry a clear marker and must never be included in real-world evaluation.

## Versioning and validation

Every dataset import should record:
- source register ID;
- source snapshot/download date;
- import code revision;
- schema version;
- validation report;
- record counts and exclusion reasons;
- licence/authority decision.

This contract is a starting point. Any material change to target semantics, status mapping or privacy-sensitive fields requires an ADR and a changelog entry.
