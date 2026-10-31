# Data source register

Last reviewed: 2026-10-31 (third pass on data.gov.in, NTES timetable, and live PNR API surfaces; web search 2026-10-31)

This register is intentionally conservative. A source is not approved merely because it is discoverable online. Verify source-specific terms before ingestion, persistent storage, redistribution, model training or commercial use.

## Current register

| Source / category | Intended use | Status | What remains to verify |
|---|---|---|---|
| DataMeet `datameet/railways` metadata (`stations.json`, `trains.json`, `schedules.json`; mirrored on Kaggle as `CC0: Public Domain`) | Station codes, train numbers, classes and routes for input validation and coverage reporting | **Under review — not ingested.** Directly downloadable, but the repository has no licence file; prose citing CC0 is not a grant | An explicit licence dedication or written confirmation of CC0 and its permitted uses. No outcome labels, so this cannot unblock training |
| Government open-data train timetable (`data.gov.in`, "Indian Railways Time Table for trains available for reservation as on 01.11.2017") | Initial route/train metadata research | **Candidate; not ingested.** `https://data.gov.in` returned HTTP 403 to an unauthenticated automated fetch on 2026-10-23, so the catalogue was not read; a 2026-10-31 web search surfaced the timetable dataset only as a metadata reference | A browser session or portal API key, then actual schema, licence and coverage. Metadata only — no outcome labels, so this cannot unblock training |
| National Train Enquiry System (NTES) timetable / schedule feeds (e.g. `shwetankg07/railpull`, an NTES timetable crawler/export) | Route and journey scheduling context for feature engineering | **Candidate; not ingested.** A crawler that walks NTES one train/station at a time produces schedules, stop lists and live delays; a 2026-10-31 search read its README only (`https://github.com/shwetankg07/railpull`). No per-reservation final-chart outcome | Whether NTES serves historical/archived schedule snapshots or only current data; whether the public timetable is also downloadable as a bulk file; and the service's acceptable use policy before any automated crawling. Schedules are a legitimate contextual feature; they are not a chart outcome |
| Official railway enquiry surfaces (`indianrail.gov.in` PNR enquiry, `pnr-status-indian-railway.p.rapidapi.com`, `railengine.vercel.app`, `eRail`) | Understand public status vocabulary and user-facing constraints | **Reference only.** Per-PNR interactive enquiry only; no bulk or historical export. Live APIs (`rapidapi`, `railengine`, `eRail`) return current status for a live PNR and require an API key; automated collection, retention and ML use are not assumed permitted | Whether any authorised source publishes per-reservation historical outcomes with dates and positions. None of these services publishes booked-status + final-chart outcome batches |
| Kaggle `aaryananil/indian-railway-ticket-confirmation` (`MIT`) | — | **Rejected** (2026-10-23) | The dataset page states it is synthetically generated. Labelled synthetic data may exercise code and prove nothing about railways |
| Kaggle `bhavyarajdev/indian-railways-schedule-prices-availability-data` (`Apache 2.0`, scraped from IRCTC Oct 2023) | — | **Rejected for training** (2026-10-23) | Schedules/fares/availability snapshots, not per-reservation final-chart labels; provenance rests on unverified third-party scraping terms |
| Kaggle `sripaadsrinivasan/indian-railways-dataset` (`CC0: Public Domain`) | — | **Under review, reference metadata only.** | Reference metadata only — no outcome labels — so at best it would sharpen station-code and train validation, not unlock training |
| Kaggle `railofy-challenge` — "Indian Railways Challenge", hosted by Railofy, listed status "Late Submission" | Potential historical reservation outcomes | **Quarantined — terms unreadable from this environment** (2026-10-30) | Its rules, data and About Dataset pages are client-rendered and return only a page title to an automated fetch, and `https://www.kaggle.com/api/v1/competitions/list` answers HTTP 401 without an account, which this environment has none. Needs a logged-in Kaggle session for the competition terms, and behind that a second answer: what Railofy was permitted to publish, since the records originate in its own PNR-tracking service. Public availability of the files is not treated here as a grant |
| `github.com/Yogalakshmi4784/PNR-Prediction` — competition work that re-publishes the Railofy CSVs | — | **Rejected for training on content** (2026-10-30); its code is not reusable here either | 36,775 labelled rows: 17 scaled floats (13 outside [0, 1]), one `QT` code (`GN`/`PQ`/`RL`), five integer flags, one 11-digit non-unique `pk`, and a **binary** `target` with base rate 0.3148. `python -m railconfirm.data validate` on it returns 0 valid rows and exits 1 — no train number, journey date, observation date, class code, booked status or final-chart status. Its `LICENSE` is verbatim GPL-3.0 and the word "dataset" appears in it 0 times, so it establishes nothing about the CSVs and its copyleft terms do not fit an Apache-2.0 project. `PNR_Confirmation.pkl` was not loaded; `sweetviz_report.html` was not opened |

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
