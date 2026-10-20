# Domain model

Status: conceptual model for implementation.

## Core entities

### Journey
Represents a dated train movement relevant to the passenger's route segment. It has a train identifier, journey date, boarding and destination stations, class and quota context where known.

### Booking group
Represents passengers whose reservation outcomes are analyzed together. It has a random internal ID and passenger membership. Raw PNRs, where lawfully required for tracking, are sensitive external identifiers and must not be used as a public resource ID.

### Passenger reservation
Represents one passenger's reservation state within a booking group. The model does not need the passenger's name. It retains original booking status independently from later observations.

### Status observation
An immutable observation of a status from a defined source at a given time. It includes raw status, normalized status, parsed position if valid, source, observed time, ingestion time and validation state.

### Prediction
An immutable model output for a specific request/feature snapshot. It includes target definition, prediction timestamp, created time, model version, feature schema version, evidence metadata and a supported or abstained state.

### Prediction outcome distribution
Passenger-level probabilities for supported classes plus a booking/group-level representation sufficient to compute named events. This is not interchangeable with a summary badge.

### Data source
A registered source with owner, terms, approved purposes, schema, freshness semantics, coverage and status. Provider configuration references a source register entry.

### Model version
A specific trained artifact, feature schema, target definition, calibration layer and evaluation record. "Latest" is not sufficient provenance for a stored prediction.

## State distinctions

Keep these pairs separate:
- original booking status vs latest observed status;
- observed status vs predicted final outcome;
- source publication time vs system observation time vs ingestion time;
- final-chart status vs any separately defined post-chart status;
- group probability vs passenger marginal probability;
- live/current status vs stale last-known status;
- unknown category vs invalid input vs censored outcome.

## Invariants

1. Each status observation has exactly one source reference and an explicit observation timestamp or documented unknown-time state.
2. Raw status strings are not destroyed by normalization.
3. Parsed positions are nullable and validated; they are never guessed.
4. A passenger belongs to one booking group for the defined journey snapshot.
5. Predictions are immutable records and do not replace observation records.
6. Each prediction has a target definition and model/inference version or an explicit baseline/unsupported reason.
7. Probabilities for a mutually exclusive, exhaustive outcome set sum to one within tolerance.
8. Group-event probabilities are internally coherent with the supported joint outcome representation.
9. A censored or unverified record does not silently become a negative training label.
10. The prediction feature snapshot uses only information available at its prediction time.
11. Unknown status codes are preserved and surfaced for mapping review.
12. Raw PNRs and passenger names do not appear in public resource IDs or ordinary logs.

## Status normalization

Normalization is a versioned mapping from source-observed codes into a reviewed domain representation. Do not hard-code assumptions that all waitlist categories have identical mechanics. The mapping should capture:
- raw code;
- broad state (CNF, RAC, WL, cancelled, other/unknown);
- quota/category where supported;
- parsed position and parsing result;
- source/reference and date checked;
- mapping version.

Unknown values should not prevent the rest of the product from validating non-status fields, but the request must not enter a model path that does not support them.

## Group-level dependency

Passengers in one booking share train, date, class, route, quota and potentially reservation allocation constraints. Compute group events from a joint/structured outcome model or a simulation strategy whose assumptions have been evaluated. Do not claim that passenger outcomes are independent by default.

## Terminology

Use "confirmed berth" for CNF and "at least RAC accommodation" for a different group criterion. Avoid an ambiguous label such as "ticket confirmed" when the UI might treat RAC as equivalent to CNF.
