# Indian Railways domain and operational rules review

**Last reviewed: 2026-10-31**
**Scope: Workstream A — Indian Railways domain and operational research**

This document records the Indian Railways reservation and chart-preparation domain
knowledge consulted during the research campaign. It connects each operational rule to
the existing RailConfirm domain model and ADRs, and records what the authoritative
sources say, what remains ambiguous, and whether the implementation correctly represents
it.

This is a domain document, not a claim of model performance. No RailConfirm probability
number in this repository has been validated against real railway data.

---

## 1. Evidence base and reliability

The primary authority for the domain vocabulary is the official Indian Railways Passenger
Reservation Enquiry legend (`https://www.indianrail.gov.in/enquiry/PNR/PnrEnquiry.html`),
inspected 2026-10-31. IRCTC terms and conditions, refund rules, and the Ministry of
Railways / CRIS press and policy documents corroborate the secondary details.

**Confidence tier:** Tier 1 for the status vocabulary and charting/cancellation rules
(official railway/enquiry and official IRCTC policy sources). Tier 2 for restatement of
those rules on third-party travel-assistance sites. Tier 3 for commercial marketing
claims (e.g. RAC-to-confirmed uplift percentages published by booking sites).

**Status code provenance is authoritative; quantitative confirmation-chance numbers on
third-party sites are heuristic and are recorded as such.** No third-party published
percentage is used as a RailConfirm figure.

---

## 2. Status vocabulary and what each family means

The enquiry legend lists the following status families and the meaning of each:

| Code(s) | Full form | Meaning |
|---|---|---|
| CNF | Confirmed | Fully confirmed; coach/berth/seat number available after charting |
| RAC / RACWL | Reservation Against Cancellation | Confirmed seat, not a full berth; two RAC passengers share one side-lower berth |
| WL # | Waiting List number | Waiting list position; confirms only if passengers ahead cancel before charting |
| RLWL | Remote Location Wait List | For intermediate towns; clears only on cancellations at that boarding station |
| GNWL | General Wait List | Issued from the originating station; highest priority among waitlist types |
| PQWL | Pooled Quota Wait List | Shared across small intermediate stations; small seat pool |
| RQWL | Roadside Quota Wait List | For road-side stations |
| DPWL | Duty Pass Wait List | For railway duty duties |
| TQWL | Tatkal Quota Wait List | Tatkal quota; does not get RAC; clears only on cancellation of a confirmed Tatkal passenger |
| NT | Not Turned Up | Passenger did not show |
| CAN / MOD | Cancelled / Modified | Cancelled or ticket modified |
| RELEASED | Railway released | Ticket not cancelled but alternative accommodation provided |
| WEBCAN / WEBCANRF | Web cancelled / web cancelled refund | Counter ticket cancelled online; refund collected or not |
| REGRET/WL | Regret waiting list | No more booking permitted |
| R# | RAC coach/berth number | Shows the RAC coach and berth number |
| TDR | Ticket deposit receipt | Passenger files TDR to claim refund without cancellation |

The RailConfirm domain model (`backend/railconfirm/domain/status.py`) maps these to its
internal status categories. The official enquiry legend was used as the verification
source for the mapping. **The mapping must not silently collapse any of the status
families above** — each is a distinct observed state with different chart behaviour and
different terminal outcome.

### 2.1 RAC progression and confirmation behaviour

The most important operational subtlety for RailConfirm is the distinction between
**displayed status** (what the live enquiry shows at a point in time) and **final-chart
outcome** (the berth result after charting).

- RAC is an intermediate state. Two RAC passengers on the same PNR may share one
  side-lower berth; during daytime (06:00–22:00) they can sit out the berth.
- RAC clearances to CNF happen at chart preparation, driven by cancellations ahead of
  the waitlisted passengers on that ticket.
- A WL passenger confirms only when passengers ahead cancel; the WL number is the queue
  position.
- Once charting is complete, a ticket that is still WL is **automatically cancelled**
  (for e-tickets) and a refund is issued.
- For partially confirmed PNRs (some passengers confirmed, some waitlisted), the PNR is
  **not auto-cancelled**; the waitlisted passenger may travel in the shared/confirmed
  space or file a TDR up to 30 minutes before scheduled train departure.

The enquiry legend itself says: *"Please Note that in case the Final Charts have not been
prepared, the Current Status might upgrade/downgrade at a later stage."* This is the
single most important statement for RailConfirm's problem definition: the displayed
status at prediction time is not a stable final outcome.

### 2.2 Chart preparation and charting timeline

The chart-preparation timeline has two stages:

- **First chart:** about 8–10 hours before departure (migration from 4 hours to 8 hours
  in mid-2025 to 10 hours by late 2025). This is when the largest wave of confirmation
  happens, because unallocated berths from emergency quotas (Parliament House, Senior
  Citizen, Defence, Foreign Tourist) are released to the General Waiting List.
- **Second chart:** 30 minutes before departure, handling last-minute Tatkal
  cancellations and boarding-station changes.

For trains departing before about 11:00, the first chart is prepared the previous
evening (around 20:00–21:00). The RailConfirm row contract (`observation_date`) is the
only timestamp available; the same-day observation rule is retained because it cannot be
ordered against the chart.

**Implication for RailConfirm:** a prediction at the first chart has materially more
information than a prediction minutes before departure, and the observation time
determines which stage of the charting process the ticket is in.

### 2.3 Quotas and their operational implications

Quota determines who has priority when cancellations occur:

| Quota | Priority on confirmation |
|---|---|
| GNWL | Highest priority (general, from originating station) |
| RLWL | Only cancels at the specific boarding station |
| PQWL | Shared small intermediate-station pool; low priority |
| TQWL | Tatkal; rarely cancels; lowest priority |

This means a ticket with a *better* (lower) WL number under one quota is not
necessarily better than one under another quota. Two tickets with the same WL number
but different quota codes can have materially different confirmation probabilities.
RailConfirm's cohort model (class, quota, as-of status) explicitly separates quota —
which is correct.

### 2.4 Terminal outcomes

Beyond the route to CNF, the enquiry legend defines the terminal outcomes:

- **CNF:** full berth, coach and berth number shown.
- **RAC:** berth sharing; upgrade only if a berth opens before/during charting.
- **WL:** still waitlisted after charting = auto-cancelled (e-ticket) with refund.
- **NT:** passenger did not turn up.
- **TDR:** ticket deposit receipt to claim refund of a cancelled/missing train.
- **RELEASED:** alternative accommodation provided.

The RailConfirm schema must keep original status, current status, and final-chart
outcome distinct. The existing `initial_status` / `current_status` split (from the
data contract and preprocessing) correctly preserves the first two; the final-chart
outcome is the prediction target and needs an explicit observation because it is
normally only known after the journey is complete.

### 2.5 Displayed status vs historical observation vs final-chart outcome

| Concept | What it is | RailConfirm treatment |
|---|---|---|
| Original status | status at booking | Preserved in raw rows |
| Current (as-of) status | status at prediction time | The `as_of_status` cohort key |
| Observation timestamp | when the status was recorded | `observation_date` in the row contract |
| Final-chart outcome | berth result after charting | The target; only known after the fact |

**Correction to an earlier assumption:** the same-day observation refusal is a data-order
problem (a same-day row cannot be ordered against the chart), not a decision that
status changes are impossible on the same day. The row contract already carries an
explicit "unknown-time" state for observation time.

---

## 3. Comparison table: operational rules ↔ RailConfirm implementation

| Operational rule | Authoritative source | RailConfirm representation | Verdict |
|---|---|---|---|
| WL number = queue position; confirms only if ahead cancellations | IR enquiry legend | Cohort keyed by `as_of_status` and class/quota; position estimator (ADR-0020) | Correct, but position effect is only partial and must be measured |
| GNWL > RLWL > PQWL > TQWL priority on confirmation | IR enquiry legend, travel sites | `quota_code` carried as a cohort dimension | Correct |
| RAC = confirmed seat, not full berth; shares one side-lower berth; daytime sitting | IR enquiry legend; IRCTC terms | Rac status distinct from WL; RAC berth-share semantics in ADR-0016 group bounds | Correct |
| WL still WL after charting = auto-cancelled, refund | IR enquiry legend; IRCTC terms | Terminal outcome (CANCELLED) distinguishes web-cancel from chart-after-WL-cancel | Correct; final-chart outcome must be a distinct target |
| Charting has two stages (first ~8–10h, second 30min pre-departure) | IR enquiry; travel guides | Row contract carries `observation_date`; same-day refusal | Corroborated; a charting-stage feature is Phase 9 work |
| Partially confirmed PNR is not auto-cancelled; TDR up to 30min pre-departure | IRCTC terms | Partially confirmed handled in schema; TDR semantics in domain | Correct |
| TQWL does not get RAC; lowest confirmation probability | IR enquiry legend; travel guides | `TQWL` distinct from `GNWL`/`RLWL`/`PQWL` | Correct |
| First chart releases emergency-quota berths to GNWL | IR enquiry legends | Not yet a feature; contextual signal (Phase 9) | Correct |

---

## 4. Remaining ambiguities / what needs authoritative confirmation

1. **ETA first-chart vs second-chart timing** — the exact clock for "first chart
   preparation" varies with the departure hour and origin station. The row contract
   records `observation_date` only, not time-of-day. A future feature needs an
   authoritative IR timetable or NTES record for charting stage.

2. **WL number rollover between charting stages** — positions can shift between the
   first and second chart. The row contract conserves `observation_date` as the only
   timestamp; the dataset gate must preserve position.

3. **Whether "RAC to CNF" chance numbers published by travel sites are reproducible**
   — they are heuristic and ticket/route/season dependent; not accepted as RailConfirm
   evidence.

4. **CRIS/NTES historical reservation outcome data** — NTES, the official real-time
   source, serves only current and near-future data. Whether any authorised source
   publishes historical per-reservation final-chart outcomes under a training-permitting
   licence remains **open** (see data-workstream conclusions).

---

## 5. Verdict on the existing implementation

- **Status vocabulary:** accurately represented; no status family collapsed.
- **Status split (initial vs current):** correct; the final-chart outcome is explicitly
  kept distinct as the prediction target.
- **Quota:** carried as a cohort dimension; correct.
- **Group outcomes:** Poisson-binomial and comonotonic queue-clearing bounds are
  defined (ADR-0003, ADR-0016) but not validated against real group data.
- **Observation/timestamp ordering:** retained, with the same-day refusal under its own
  reason code.
- **Charting-stage awareness:** not yet a feature; Phase 9 contextual signal.
- **Dataset readiness:** blocked on an approved dataset with final-chart labels.

**No correction to the codebase is required by this review; the domain model is
consistent with the authoritative enquiry legend. The remaining gap is data rights and
labels, not representation.**
