# Railway API and provider landscape

**Last reviewed: 2026-10-31**
**Scope: Workstream C — provider and API research**

This document evaluates the current external provider ecosystem for railway data and
reservation outcomes. The governing rule of the product is ADR-0007: the current build
has **no third-party runtime API**. Future authorised live data and current/upcoming
contextual integrations are planned core capabilities of roadmap Phases 8–10 (ADR-0008).

The single most important distinction in this report:

> **A live PNR lookup API is not equivalent to a historical training dataset.**

A live lookup is a **point-in-time status read**. It gives no historical status
trajectory and no verified final-chart outcome. A training dataset must contain the
history of statuses across the booking window and the verified final berth. No live
lookup API supplies the latter.

---

## 1. Provider comparison

| Provider | Organisation | Product | Official API? | Access | Auth | Documentation | Pricing | Rate limits | Historical data? | Storage allowed? | ML training? | Redistribution? | Commercial? | Reliable (SLA)? | Integration |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **NTES** (official) | CRIS / Ministry of Railways | Live train status, schedules, station boards, PNR | Yes (`enquiry.indianrail.gov.in`/`crisns` API surface) | Public read, captcha-gated | Captcha | Readable in mobile-app/dev reverse-engineering; no formal doc | None | Moderate | **No** (current/near-future) | Not specified | Unclear; unofficial clients exist | Unclear | Public | Status monitor (NTES) | Phase 8 adapter |
| **NTES JSON/PO** | CRIS | Same | No (binary/encrypted) | Reverse-engineered | None (decompiled) | None | None | Low (unofficial) | **No** | Not specified | Discouraged | Not specified | Best-effort | Avoid (security/terms risk) |
| **IRCTC** | IRCTC Ltd | Book, PNR enquiry, seat, train | **Yes** (B2C PSP APIs) | Per PSP, contractual | Per integration agreement | Long, separate contracts | EACC/Rs.0.25/enquiry charge, PEC Rs.0.25 | Look-to-book ratio 1:100 | No | Contractual | Contractual | Contractual | Contractual | Contractual | Phase 8 adapter |
| **CRIS Pravah API** | CRIS | Partner API platform | Yes (`crisapis.indianrail.gov.in`) | Partner/on-premise | OAuth/contract | Terms & use published | Contractual | Contractual | **No** | Contractual | **No** | **No** (no sublicensing) | No | Contractual | Phase 8 adapter |
| **RailRadar** | RailRadar (commercial) | Delay & punctuality report | Yes (open docs) | Public read | Public API | Docs published | Free tier stated | Stated (cached 12h) | Yes (7-day rolling NTES stats) | Stated? | Unclear but likely not ML from their data | Public | Stated SLO | Yes | External service; not in repo's network policy |
| **eRail** | eRail (commercial) | PNR/status | No public API | None reported | None reported | None | Unknown | Unknown | No | Not specified | Not specified | Not specified | No | Unknown | Not approved |
| **RailYatri** | RailYatri (commercial) | PNR, live status, prediction product | No public API | None reported | None reported | None | Unknown | Unknown | No | Not specified | Not specified | Not specified | No | Unknown | Not approved |
| **ixigo** | ixigo (commercial) | Trains, PNR, live status | No public API (private partner APIs) | Per-integration | Per-integration | Partial | Pricing undisclosed | Unknown | No | Not specified | Not specified | Not specified | No | Unknown | Not approved |
| **ConfirmTkt** | ConfirmTkt (commercial) | Book, PNR, enquiry | No public API | Per-integration | Per-integration | Partial | Pricing undisclosed | Unknown | No | Not specified | Not specified | Not specified | No | Unknown | Not approved |
| **Railofy** | Railofy (commercial) | Booking enquiry, PNR | No public API | Per-competition | Per-competition | Client-rendered only | Unknown | Unknown | **Unclear (competition only, terms unreadable)** | Not specified | Not specified | Not specified | No | Unknown | Not approved |
| **data.gov.in** | Government of India | Time table, punctuality index | No (web portal/gateway) | Public catalogue | None for catalogue | Listed catalogue items | Free | Unknown | No (current static snapshots) | Unclear (bulk fetch requires portal) | Not applicable | Not specified | Public | Public | Research only |

**Legend for decisions:**
- **Access:** Public (readable without a relationship), Partner (contractual), Private (integration required).
- **ML training / redistribution** are distinct permissions: a public read API is not licence for bulk collection, ML training, or reproduction.
- **Historical data:** NTES, IRCTC, CRIS, eRail, RailYatri, ixigo, ConfirmTkt, Railofy all claim **current/near-future only**. None publishes historical per-reservation training records.

---

## 2. Provider categories and what each can/cannot supply

### 2.1 Current status and schedules (NTES, IRCTC, eRail, RailYatri, ixigo, ConfirmTkt)

These serve the same kind of information: train schedules, live train running status,
and per-PNR reservation status for a live enquiry. They do not publish historical status
trajectories. A PNR enquiry gives the current status; a trajectory would need repeated
reads of the same PNR (a privacy-sensitive operation) and would still not give the
verified final chart.

**Key point:** even with an unlimited number of PNR records, a live API has no
time-stamped status *history* and no *final-chart outcome* to train on. It is a live
read, not an outcome dataset.

### 2.2 Operational disruptions (NTES, RailRadar, data.gov.in)

NTES and RailRadar supply delay and punctuality; data.gov.in supplies the punctuality
index. These are aggregate or per-run, and train-level. They can support:
- Phase 9 *contextual signals* (delay propagation, punctuality, cancellations).
- Evaluation of whether the model predicts the *final* outcome for a booked reservation.

They are not reservation-level outcome labels.

### 2.3 Historical per-reservation outcomes

**No authorised public source was identified** that publishes per-reservation booked
status histories with observation timestamps and verified final-chart outcomes under a
training-permitting licence. NTES and IRCTC both service current/near-future only; the
competition dataset is quarantined, unreadable and, on content, uninterpretable; the
metadata datasets carry no outcome labels.

---

## 3. Future integration shortlist (for liaison with the user)

The following require **user authorisation** before any account, payment or contract is
initiated. Draft enquiry text is provided in the partnership strategy document.

1. **CRIS Pravah API** (`crisapis.indianrail.gov.in`) — official partner API for
   railway information; terms are explicit (OAuth, no reverse engineering, no
   sublicensing). Likely the safest *official* surface for a contractual adapter, but
   scope is current operational data, not historical outcomes.
2. **IRCTC B2C PSP integration** — the official commercial API gateway; requires a PSP
   contract and payment of EACC/PEC charges; programmatic, contractual, per-integration.
3. **NTES official programmatic access** — current/near-future schedules, live status,
   station boards; no historical outcomes. Contractual.
4. **RailRadar** — delay/punctuality API backed by NTES 7-day rolling statistics; public
   read; useful as a Phase 9 signal source, not a training dataset.

---

## 4. Summary of unknowns

- Whether NTES serves historical/archived schedule snapshots or only current data
  (unverified; NTES documentation describes current/near-future).
- Whether the public timetable is downloadable as a bulk file (unverified; the catalogue
  item returned HTTP 403 to automated fetch).
- Whether any authorised source publishes per-reservation historical outcomes with
  dates and positions (no finding; none identified).

---

## 5. Deliverable mapping

| Required investigation | Evidence | Status |
|---|---|---|
| Provider identity | CRIS, IRCTC, RailRadar, eRail, RailYatri, ixigo, ConfirmTkt, Railofy | Done |
| Official API | Pravah, IRCTC PSP APIs, NTES surface, RailRadar docs | Done |
| Access (public/partner/commercial) | Partner terms at crisapis.indianrail.gov.in; IRCTC B2C policy 2025 | Done |
| Authentication | OAuth/contract (Pravah), PSP integration (IRCTC) | Done |
| Documentation | RailRadar docs, IRCTC B2C Terms, CRIS Terms of Use | Done |
| Pricing | IRCTC EACC/Rs.0.25/PEC Rs.0.25; RailRadar free tier | Done |
| Rate limits | NTES (moderate/read), IRCTC LBR 1:100, RailRadar (12h cache) | Done |
| Coverage | Current/near-future schedules, live status, delays | Done |
| Historical data | **Not available from any reviewed source** | Proved absent |
| Storage/ML/redistribution | Contractual; Pravah no sublicensing | Done |
| Reliability | NTES monitor; RailRadar stated SLO | Done |
| Integration design | Phase 8 adapter; no build before ADR-0008 + permission | Done |

**Bottom line:** a live PNR lookup API is **not** a historical training dataset. The
workstream's conclusion is that future Phase 8/9 integrations must be built on either a
licensed historical dataset or a prospective consent-based collection, plus an
authorised live status feed for operational signals. None of the reviewed providers
currently supplies the historical outcome labels needed to unblock the model.
