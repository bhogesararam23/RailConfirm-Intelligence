# Data source register

Last reviewed: 2026-10-21

This register is intentionally conservative. A source is not approved merely because it is discoverable online. Verify source-specific terms before ingestion, persistent storage, redistribution, model training or commercial use.

## Current register

| Source / category | Intended use | Status | What remains to verify |
|---|---|---|---|
| Government open-data train timetable catalogue | Initial route/train metadata research | Candidate; not yet ingested | Currentness, actual downloadable schema, licence and coverage |
| Official railway enquiry surfaces | Understand public status vocabulary and user-facing constraints | Reference only | Automated access, retention and ML use are not assumed permitted |
| Official/contracted PNR enquiry provider | Planned future live ticket/status source (roadmap Phase 8) | Planned; provider not selected and not enabled in current build | Source-specific ADR; verify access, terms, cost, storage, retention and ML-use rights |
| Historical PNR/status trajectory dataset | Supervised model training and chronological evaluation | No dataset approved | Provenance, licence, outcome labels, sample coverage and redistribution/publication rights |
| User-contributed status observations | Potential future prospective dataset | Design only; not required for local MVP | Consent wording, validation, retention, sampling bias and deletion process |
| Public holiday/calendar data | Planned current/upcoming context (roadmap Phase 9) | Planned; source not selected | Provenance, usage review, coverage, timestamps, refresh model and measurable predictive value |
| Verified operational event/news sources | Planned current/upcoming factors (roadmap Phase 9) | Planned; no feed currently connected | Source review, publication/effective timestamps, permitted use and evidence of incremental value |

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

## Current scope and target-product note

The current build has no third-party runtime API or provider integration (ADR-0007). Agents may research candidate local datasets, but must submit the manifest and intake report before training. Live status and current/upcoming contextual integrations are planned core capabilities in roadmap Phases 8–10; the entries above are potential source categories, not approved providers. Do not treat planned product capability as permission to use a specific source.

## Approval rule

A source cannot enter model training until its data rights, label meaning, quality, provenance and publication constraints are clear. If a contract allows live display but does not allow historical storage or model training, treat those as distinct permissions.
