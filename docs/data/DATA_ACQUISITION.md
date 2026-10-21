# Data acquisition and source governance

Last reviewed: 2026-10-21

## Why data access is a critical dependency

A credible confirmation model requires observed reservation status over time and a trustworthy final outcome. Train schedules and station lists help define routes, but do not provide the historical booking trajectories and outcome labels needed to estimate confirmation probabilities.

Do not assume that historical PNR trajectories or an official live PNR API are freely available for unrestricted collection, storage or model training. Each source must be checked directly.

## Current operating mode: agent-assisted, local-only

The current product build must not depend on any third-party runtime API. Agents may help research sources, prepare permitted files, normalize documented schemas and write intake reports as a separate data-preparation activity. Data must be delivered as an inspectable local file or a user-supplied artifact, not fetched through a hidden network call when the application runs. Follow docs/data/DATASET_INTAKE_CHECKLIST.md for every candidate. An agent's research summary is not a licence, and a downloadable file is not automatically approved for model training. If no suitable dataset is available, report the blocker and continue with domain/test work; do not invent rows or labels.

## Source tiers

### Tier 1 — Official/open metadata
Potential contents: train identifiers, station identifiers, scheduled stops, distances and general railway metadata.

Required checks:
- Publisher and canonical URL.
- Publication/update date and update cadence.
- Schema and field definitions.
- Licence and attribution requirements.
- Whether redistribution, commercial use and derivative datasets are allowed.
- Whether the information is current enough for the intended purpose.

These sources support route and train metadata. They must not be mistaken for reservation-outcome labels.

### Tier 2 — Authorized outcome data
Preferred contents:
- De-identified booking/group identifier.
- Train, journey date, class, quota, route segment.
- Original booking statuses and booking time when permitted.
- Time-stamped subsequent status observations.
- Final chart outcome and outcome-verification method.
- Record provenance and source-specific restrictions.

Request data access and model-training rights explicitly. Confirm whether retention, feature extraction, derived-model training, publication of aggregate metrics and commercial use are all permitted.

### Tier 3 — Prospective, consent-based collection
Where historical records cannot be acquired, collect new observations from participating users or authorized providers. Explain the purpose, retention period and use before collection. Record selection bias: volunteers do not automatically represent the whole network.

Never represent this growing prospective dataset as a long historical record.

### Tier 4 — External context
Potential sources include structured public holiday calendars and published operational changes. Each event must have a source, publication timestamp, effective date range, geography/route relevance, event type and confidence/provenance fields.

News should not directly change a probability through an LLM-generated guess. First test whether structured context adds value to a status/historical baseline.

## Source register

Maintain one entry per source in `docs/data/SOURCE_REGISTER.md`. Do not ingest a source before its usage status has been recorded.

Minimum fields:
- Source name and owner.
- Canonical URL or contract reference.
- Data fields and coverage.
- Last checked date.
- Refresh frequency and timestamp semantics.
- Licence/terms URL and permitted uses.
- Attribution requirements.
- Rate limits, costs and operational limitations.
- Personal-data/security implications.
- Decision: approved, restricted, under review, or rejected.
- Reviewer and notes.

## Acquisition workflow

1. Identify a concrete research or product need.
2. Find the primary source or provider documentation.
3. Read the applicable access terms and licence.
4. Inspect the schema without retaining unnecessary personal fields.
5. Record coverage, freshness, missingness and label semantics.
6. Obtain required consent, contract or approval.
7. Test the ingestion path with minimal data.
8. Validate identity resolution and timestamp ordering.
9. Store provenance and data version with every import.
10. Publish a data-quality report before training.
11. Recheck terms when use, volume, retention or commercialization changes.

## Historical reconstruction

For each observation, distinguish:
- Booking-time/original status.
- Status displayed at observation time.
- Final chart status.
- Final status after any separately defined post-chart process.

A current status is not proof of a final outcome. A record without a verified outcome is not a positive or negative training label by default.

## Data quality checks

At minimum, check:
- Invalid train/date/class/quota identifiers.
- Unknown and misspelled status codes.
- Observation timestamps in the future or out of order.
- Duplicate snapshots and contradictory observations.
- Status positions that violate basic numeric constraints.
- Final outcome missingness or ambiguous definitions.
- Coverage by status type, route, train, class, quota and prediction horizon.
- Leakage from post-prediction information.
- Source licence and retention requirements.

Do not silently delete anomalous records; record the reason and effect of any cleaning rule.

## Explicitly prohibited approaches

- Bypassing authentication, CAPTCHA, technical restrictions or rate limits.
- Treating public accessibility as permission for bulk scraping.
- Reusing another application's private data or API credentials.
- Publishing PNRs or identifiable passenger data in the repository.
- Mixing synthetic fixtures with real data without a visible distinction.
- Inferring permissions from a third-party wrapper without reviewing the underlying terms.
