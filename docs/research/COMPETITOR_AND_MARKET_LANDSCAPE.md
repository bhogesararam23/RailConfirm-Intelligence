# Competitor and market landscape

**Last reviewed: 2026-10-31**
**Scope: Workstream E — competitor and market landscape**

This document is a **verification-focused** competitor review. Verified product
capability is separated from promotional claims. Where a competitor published a
prediction-accuracy figure we record it exactly as published and flag the experimental
context; we do not assume knowledge of a competitor's private model, dataset or
internal accuracy.

---

## 1. Competitors investigated

| Product | Actual company | Prediction feature | Probability reporting | Status update | Group support | Signals | Pricing/monetisation | Disclaimers |
|---|---|---|---|---|---|---|---|---|
| IRCTC | IRCTC Ltd (Indian Railways) | AI-based waitlist confirmation **prediction** (official, since 2018) | Probability % for General Quota, holiday scenario; shows last-year trend | Live PNR/status | Not a feature | Operational | Bookings via IRCTC | Official disclaimer; prediction is not guaranteed confirmation |
| CRIS RailOne | CRIS (Centre for Railway Information Systems) | **AI-based waitlist confirmation prediction** | Accuracy claim: improved **53% → 94%** (per Ministry of Railways, Min. of Railways) | Live status, chart | Via RailOne | Operational | ~9.65 lakh bookings/day | Official disclaimer; prediction vs confirmed |
| eRail | eRail (commercial) | PNR enquiry, **prediction** | Percentage on some surfaces | Live status | Not a feature | None public | Paid subscriptions/marketing | Not confirmed from source |
| RailYatri | RailYatri (commercial) | PNR, **prediction** | Prediction on site | Live status | Not a feature | Paid subscriptions | Not confirmed from source |
| ixigo | ixigo (commercial) | Train search, PNR, **prediction** | Prediction on region | Live status | Not a feature | Paid subscriptions | Not confirmed from source |
| ConfirmTkt | ConfirmTkt (commercial) | Book, PNR, **prediction** | Prediction on site | Live status | Not a feature | Paid subscriptions | Not confirmed from source |
| Railofy | Railofy (commercial) | Indian Railways challenge (dataset) | N/A | N/A | N/A | N/A | N/A | N/A |

**Important caveat:** product pages and marketing claims are promotional. We recorded
what sources state and labelled each figure with its context and source. We made no
claims about competitors' internal models, private data or undisclosed accuracy.

---

## 2. What the market is doing

- **Prediction as a feature (not the product):** IRCTC and CRIS operate
  confirmation-prediction as an *operational service* (IRCTC since 2018; CRIS RailOne
  AI-based waitlist prediction). Both are **government/state-linked**, with the
  prediction embedded in the booking and enquiry experience. They are not "competitors"
  to RailConfirm in the commercial sense; they are the providers of the underlying
  live data and the standard that RailConfirm's local-first product is independent of.
- **Consumer prediction tools (ixigo, eRail, RailYatri, ConfirmTkt):** offer prediction
  as one feature among booking, PNR and live status. They use paid subscription and
  API models; they do not publish their model, dataset or internal accuracy.
- **Commercial data aggregators (RailRadar):** supply delay/punctuality APIs built on
  NTES statistics. They are a **data supplier**, not a prediction product.
- **Dataset competitions (Railofy challenge):** published a dataset for the purpose of a
  competition; the dataset was quarantined and is not approvable.

**No competitor publishes a per-reservation training dataset with verified final-chart
labels under a train-permitting licence, and none publishes the raw PNR history or the
calibration/validation protocol behind their prediction.** This gap is exactly what
RailConfirm's legitimacy argument fills — but it also means no competitor's numbers are
approvable evidence.

---

## 3. User pain points (publicly reported)

Public reviews and discussions report recurring patterns (which we record as patterns,
not individual anecdotes):

1. **Unclear confirmation chances at booking:** passengers book into a WL and cannot
   know their real probability until the chart, which may be too late.
2. **RAC/between statuses confusion:** RAC is often misunderstood as "confirmed" or as
   "waitlisted"; users do not know whether they can board or whether a berth-sharing
   arrangement exists.
3. **Timing sensitivity:** charting timing varies with train and boarding station; a
   passenger checking late sees WL when a chart earlier would have confirmed.
4. **Curveball status after charting:** statuses move between observation and the chart;
   displays are not stable.

These are consistent with the operational rules in Workstream A (mapping,
chart-driving behaviour, quota priority). RailConfirm's value case is a local-first,
transparent, locally-runnable estimate that names its target, its assumptions and its
abstention, rather than a single opaque percentage.

---

## 4. Gap analysis and differentiation

| Gap | Market reality | RailConfirm response |
|---|---|---|
| No transparent, local, verifiable prediction | Competitors embed prediction in booking surfaces; no open protocol or local runnability | Local-first, no third-party runtime, open method |
| Opaque accuracy | Competitors do not publish protocol or data | Documented, leakage-safe evaluation; abstention on absence of evidence |
| Group dependence unaddressed | Usually single-passenger prediction | Dependent joint outcomes (ADRs 0003/0016) |
| Contextual live signals absent at prediction time | Competitors use live status (requires login) | Structured context pipeline, but no live dependency in local build |
| Dataset/provence not auditable | Competitors' data not open | Versioned manifests, intake checklist, SOURCE_REGISTER, ADRs |

**Differentiation is evidence quality and transparency, not accuracy claims.**

---

## 5. Summary

- Prediction is an **established operational capability** in Indian Railways (IRCTC 2018;
  CRIS RailOne AI-based prediction).
- Consumer prediction apps exist but do not publish data or protocol; their figures are
  promotional and not approvable as scientific evidence.
- No competitor or public dataset provides a **validated per-reservation final-chart
  outcome dataset**, which is RailConfirm's data blocker, not its mechanism.
- RailConfirm's differentiator is a **transparent, local-first, leakage-safe product**
  with documented abstention — not a prediction-accuracy arms race.
