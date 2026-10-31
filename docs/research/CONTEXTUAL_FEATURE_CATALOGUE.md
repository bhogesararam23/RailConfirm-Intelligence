# Contextual feature catalogue

**Last reviewed: 2026-10-31**
**Scope: Workstream F — contextual and external feature discovery**

This catalogue lists the contextual features that could plausibly affect reservation
outcomes, assessed against the criteria defined in the research plan (why it might
matter; published support; availability before prediction time; resolution; source
reliability; access; rights; leakage/confounding; ablation protocol). It is a
**catalogue and phased plan for roadmap Phases 8–10**, not a claim that any feature
improves a model. Each feature is ranked by expected usefulness, verifiability,
cost, reliability and implementation complexity.

---

## 1. Ranking rubric

| Criterion | Weight |
|---|---|
| Expected usefulness (mechanistic, evidence-backed) | High |
| Verifiability (measured by temporal ablation, not assumed) | High |
| Availability before prediction time | High |
| Historical availability | Medium |
| Spatial/temporal resolution | Medium |
| Source reliability | High |
| Access cost / difficulty | Medium |
| Licence and ML-use rights | High |
| Leakage / confounding risk | High |
| Implementation complexity | Medium |

A feature is **adopted only if**: (a) it is available before the prediction timestamp,
(b) a temporal ablation on the locked period shows measurable improvement to the
declared primary metrics, and (c) the rights for storage, training and publication are
clear.

---

## 2. Contextual feature catalogue

| Rank | Feature | Why it might matter | Published support | Availability before prediction | Resolution | Source reliability | Access | Licence/ML rights | Leakage & confounding | Ablation protocol | Complexity | Rank verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 | Train punctuality profile (station-by-station historical average delay) | Trains that run late relative to schedule have different operational pressure, which correlates with higher cancellation/chart churn | NTES rolling stats; data.gov.in punctuality index | Yes, historical | Station × train × day/week | NTES official rolling stats | RailRadar API / NTES | Contractual (RailRadar); NTES partner terms | Low-moderate | Temporal ablation of punctuality vs baseline | Medium | **Adoptable (Phase 9)** |
| F2 | Delay and disruption alerts (train cancelled/delayed/diversion) | Cancellations and diversions move a booking to an unplanned outcome | NTES exception streams; IRCTC notices | Yes, operational alerts | Route/segment | Official NTES notices | NTES surface; IRCTC | Partner terms | Low | Ablation of disruption flag | Low | **Adoptable (Phase 9)** |
| F3 | Calendar / holiday markers (festival holidays, school/uni breaks) | Travel demand and cancellation pressure vary by calendar | Published holiday calendars (NTA, state governments, schools) | Yes | National + regional | High (official calendars) | Public calendars | Open | Moderate (need to align local holiday definitions to ticket booking station and travel class) | Ablation of holiday feature | Low | **Adoptable (Phase 9)** |
| F4 | Seasonal / demand signals (monthly and day-of-week effect on cancellation) | Demand surges raise cancellation pressure and WL churn | Historical booking and NTES data | Yes, historical aggregates | Monthly / weekly | High (NTES official) | data.gov.in | OGD | Low (aggregate) | Ablation of seasonality | Low | **Adoptable (Phase 9)** |
| F5 | Train-class capacity and coach composition | Smaller capacity classes (1A, 2A) have less headroom; confirmation probability is structurally bounded | NTES schedule type codes; Timetable | Yes | Train × class | High | Official schedules | Public facts | Low (structural, not a target leak) | Ablation of capacity | Low | **Adoptable (Phase 9)** |
| F6 | Booking window / advance-purchase position (days before departure) | WL position is measured against a chart at a booking-age-dependent scheduling point | IRCTC booking window; ARP changes | Yes | Journey date | Official | Official/NTES | Public facts | Low | Ablation of booking age | Low | **Adoptable (Phase 9)** |
| F7 | Emergency-quota release schedule (booking time of unallotted quota) | 4PM charting reallocation of unused quotas changes GNWL confirmation | IR enquiry guidance (4PM chart release) | Yes | Charting day | Official guidance | IR enquiry | Public facts | Low | Ablation of quota-release timing | Low | **Adoptable (Phase 9)** |
| F8 | Weather / severe-weather disruptions | Weather affects operation of trains and boarding stations | Meteorological agencies (IMD); railway incident logs | Yes, forecast and historic | Route/city | High | Public feeds | Public facts | Moderate | Ablation of weather | Medium | **Adoptable (Phase 9)** |
| F9 | Station-level characteristics (size, throughput, seasonality) | Large origination stations have different reservation dynamics | Station metadata (OM) | Yes | Station | High | Official/NTES | Public facts | Low | Ablation of station features | Low | **Adoptable (Phase 9)** |
| F10 | Major public events and crowd indicators | Surge demand changes capacity pressure | Event calendars; crowd datasets | Yes | Route/region | Variable | Public | Variable | Moderate | Ablation of event feature | Medium | **Conditional (Phase 9)** |

---

## 3. The decisive validation test for every feature

A feature is retained only if it survives a **temporal holdout ablation** on the locked
period: fit on training dates, score on locked later journeys, and compare
(pre-declared) Brier and coverage against the status/history baseline without the
feature. The comparison must be:

- One dataset file, one contract, one row set (ADR-0023).
- Same partition, one target (ADR-0022).
- Paired by position with a pre-declared exact two-sided sign test (ADR-0039).
- Coverage as a condition (ADR-0021).

No feature is promoted on correlation or mechanism alone.

---

## 4. Phased plan for roadmap Phases 8–10

| Phase | Features carried | Rationale |
|---|---|---|
| 8 | F4 (seasonality), F6 (booking window), F7 (quota release) | Historical availability, low complexity, verifiable now; low leakage risk |
| 9 | F1, F2, F3, F5, F8, F9, F10 | Requires operational data source; measured by temporal ablation |
| 10 | F1, F2, F8 (live, if source agreed) | Live operational signals; freshness and staleness controls |

Features F1–F10 are **candidates**, not commitments. None is a model input until a
temporal ablation demonstrates incremental value and its rights are clear.
