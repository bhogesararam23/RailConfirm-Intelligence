# Data source register

Last reviewed: 2026-10-21

This register is intentionally conservative. A source is not approved merely because it is discoverable online. Verify source-specific terms before ingestion, persistent storage, redistribution, model training or commercial use.

## Current register

| Source / category | Intended use | Status | What remains to verify |
|---|---|---|---|
| Government open-data train timetable catalogue | Initial route/train metadata research | Candidate; not yet ingested | Currentness, actual downloadable schema, licence and coverage |
| Official railway enquiry surfaces | Understand public status vocabulary and user-facing constraints | Reference only | Automated access, retention and ML use are not assumed permitted |
| Official/contracted PNR enquiry provider | Potential future live status integration | Deferred; not in current roadmap | Any future proposal needs an ADR plus verified access, terms, cost, storage and ML-use rights |
| Historical PNR/status trajectory dataset | Supervised model training and chronological evaluation | No dataset approved | Provenance, licence, outcome labels, sample coverage and redistribution/publication rights |
| User-contributed status observations | Potential future prospective dataset | Design only; not required for local MVP | Consent wording, validation, retention, sampling bias and deletion process |
| Public holiday/calendar data | Contextual feature research | Deferred; not in current roadmap | A future offline dataset must have provenance, usage review, coverage and update process |
| Verified operational event/news sources | Structured event features | Deferred; no runtime feeds in current roadmap | Any future offline or runtime use needs source review and evidence of incremental value |

## Template for adding a source

Copy this block for each source.

- **Name:**
- **Publisher / owner:**
- **Canonical URL / contract reference:**
- **Date checked:**
- **Data fields:**
- **Geographic and temporal coverage:**
- **Schema documentation:**
- **Refresh interval and timestamp semantics:**
- **Licence / terms URL:**
- **Permitted storage:**
- **Permitted derived features / model training:**
- **Permitted redistribution / publication:**
- **Commercial use:**
- **Attribution requirements:**
- **Rate limits and cost:**
- **Personal or sensitive data involved:**
- **Security and retention controls:**
- **Known biases and limitations:**
- **Decision:** Approved / Restricted / Under review / Rejected
- **Decision owner and rationale:**

## Current scope note

The current build has no third-party runtime API or provider integration (ADR-0007). Agents may research candidate local datasets, but must submit the manifest and intake report before training. Runtime providers listed above are deferred research possibilities, not approved integrations.

## Approval rule

A source cannot enter model training until its data rights, label meaning, quality, provenance and publication constraints are clear. If a contract allows live display but does not allow historical storage or model training, treat those as distinct permissions.
