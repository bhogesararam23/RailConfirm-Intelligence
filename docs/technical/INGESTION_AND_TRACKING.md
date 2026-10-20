# Ingestion and tracking lifecycle

Status: proposed. Live tracking must remain disabled until an authorized provider and data-retention design are approved.

## Source adapter interface

Every source adapter should expose a small, typed interface that conceptually supports:
- source metadata and capabilities;
- validated fetch operations;
- provider-specific response normalization;
- source timestamp and freshness semantics;
- known rate limits and retry behavior;
- structured errors that exclude secrets and personal data.

A provider adapter must not decide model probabilities. It returns observations and provenance to the domain/data layer.

## Ingestion stages

1. **Eligibility:** Confirm source is approved for the intended operation.
2. **Scheduling/request:** Respect terms, user consent, rate limits and bounded concurrency.
3. **Fetch:** Apply timeouts and bounded retries; do not retry permanent authorization failures.
4. **Validation:** Check payload shape, train/journey identity and timestamps.
5. **Normalization:** Preserve raw values and map recognized fields to the versioned domain schema.
6. **Deduplication:** Use a source-aware idempotency key; record corrections separately.
7. **Persistence:** Store only permitted fields with access and retention controls.
8. **Freshness update:** Record when the source was last successfully observed.
9. **Prediction trigger:** Recompute only when new evidence is relevant and the model can support the request.
10. **Audit:** Record redacted operational metadata and data-quality issues.

## Idempotency and ordering

- Repeated responses from a provider must not create unbounded duplicates.
- Use provider event IDs or a stable hash of permitted non-sensitive observation attributes where justified.
- Do not assume observations arrive in order.
- Preserve observed time and ingestion time separately.
- Late-arriving observations must not be applied to a prediction timestamp at which they were not available.
- Conflicting records must be flagged rather than silently resolved through an undocumented priority.

## Freshness semantics

Freshness is source-specific. The adapter must document whether its timestamp means current at lookup time, publication time, last update or an unknown time. The UI should show a timestamp and stale state rather than a universal "live" badge.

No universal TTL is defined yet. Establish source-specific thresholds from provider semantics and product requirements; record the thresholds in configuration and tests.

## Error classes

- Transient network/server failure: bounded retry with jitter if allowed.
- Authentication/authorization failure: fail closed and alert; do not bypass.
- Rate limit: respect provider guidance and schedule retry.
- Invalid/changed schema: quarantine the response and flag integration health.
- Unknown status: preserve raw value and mark unsupported for prediction.
- Source unavailable: keep last observation with stale metadata, if retention permits.
- Source permission uncertain/revoked: disable adapter until reviewed.

## Tracking lifecycle

1. User receives a clear notice of what will be accessed and stored.
2. Tracking gets a random internal identifier.
3. External identifier linkage is protected separately, if it is needed and permitted.
4. Scheduled refresh follows provider limits and user's tracking choice.
5. Each observation is appended with provenance.
6. A new prediction links to the new observation snapshot.
7. User can stop tracking; future fetches cease.
8. Data expires or is deleted according to the documented policy.
9. Aggregated research use happens only if source rights, consent and de-identification support it.

## Operational kill switch

Provider adapters need a configuration path to disable requests quickly. Disable the adapter if terms change, credentials are exposed, error rates spike, data semantics become unreliable or authorization is unclear. The manual-entry interface must continue to work independently.
