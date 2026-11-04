# ADR-0043: Versioned Longitudinal Observation Contract and Point-in-Time Snapshot Conversion

## Status

Accepted

## Context

Phase 2 of the RailConfirm Intelligence roadmap focuses on dataset intake and quality readiness for legitimate railway reservation data. Prior to this decision, the dataset contract was based solely on flat, date-only rows (`ROW_CONTRACT_VERSION = "1.1.0"`, ADR-0026), where each row recorded an `initial_status`, an `observation_date`, and a `final_chart_status`.

While sufficient as a simplified training interchange format, date-only flat rows have fundamental limitations when modelling real Indian Railways waitlist progression:
1. **Multi-observation histories:** A reservation's waitlist position changes repeatedly over days and hours as cancellations and quota releases occur. A flat table either captures only one arbitrary snapshot per passenger or introduces complex booking-level duplicate records without explicit sequence order.
2. **Clock and charting precision:** Date-only observation records cannot resolve whether an observation occurred before or after charting on the journey date (a same-day observation was historically refused by ADR-0026 to avoid retrodiction). Offset-aware clocks (UTC/IST) are necessary to distinguish pre-chart updates from chart snapshots.
3. **Outcome verification and censoring:** Real reservation outcomes include not only confirmed berths and remaining waitlists, but passenger-initiated cancellations, train cancellations, and unobserved charts. Treating cancelled tickets as non-confirmations introduces right-censoring bias.
4. **Group dependencies:** Passengers travelling on the same PNR share identical journey attributes and experience dependent outcome distributions.

At the same time, existing downstream pipeline code (validation, feature construction, chronological split, training baselines) depends on the flat row interchange format. Silently changing this format would break existing estimators and verification gates.

## Decision

1. **Introduce a Versioned Longitudinal Observation Contract (`LONGITUDINAL_SCHEMA_VERSION = "2.0.0"`)**:
   - Organized hierarchically into `LongitudinalJourney`, `BookingGroup`, `PassengerReservation`, `StatusObservation`, and `FinalOutcome`.
   - All observation timestamps (`observed_at`, `source_published_at`, `outcome_observed_at`, `scheduled_departure_at`) require timezone-aware datetime objects (`UTC` or explicit timezone offsets). Naive timestamps are refused.
   - Enforce strict sequential order per passenger ($t_{booking} \le t_1 < t_2 < \dots < t_n \le t_{departure}$).
   - Explicitly represent final-chart outcomes with verification source, `VerificationMethod` (`chart_snapshot`, `sms_confirmation`, `status_enquiry`, etc.), `LabelConfidence` (`verified`, `provisional`, `unverified`), and `CensoringReason` (`user_cancelled`, `train_cancelled`, `chart_not_recorded`, `outcome_missing`, `contradictory_source`).

2. **Longitudinal Quality Auditing and Transition Anomaly Detection**:
   - Provide `validate_longitudinal_dataset` in `railconfirm.data.longitudinal_validator` returning a structured `LongitudinalAuditReport`.
   - Check structural consistency, chronological bounds, and impossible railway status regressions (e.g., CNF to WL, or RAC to WL).
   - Compute coverage metrics: lead-time spans, observation interval statistics, group size distribution, and censoring rates.

3. **Point-in-Time Snapshot Conversion with Flat Interchange Compatibility**:
   - Provide `create_point_in_time_snapshot` converting longitudinal datasets into flat row interchange frames (`ROW_CONTRACT_VERSION = "1.1.0"`).
   - Allows sampling at either a fixed lead-day horizon (`as_of_lead_days=N`) or an exact timestamp (`as_of_datetime=T`).
   - Evaluates the latest status observed *at or before* the cutoff instant, preventing future leakage by construction.
   - Filters censored outcomes by default while recording exclusions in `SnapshotResult`.
   - Preserves synthetic provenance markers (`is_synthetic`).

4. **Manifest and CLI Integration**:
   - Manifest generation and verification (`railconfirm.data.manifest`) seamlessly support longitudinal datasets (`format="longitudinal_json"`, `schema_version="2.0.0"`).
   - Add `detect`, `snapshot`, and `validate` support in `python -m railconfirm.data`.

## Consequences

- Real longitudinal reservation data can be ingested without loss of observation precision, sequential order, or censoring reasons.
- Existing estimators and training infrastructure continue to operate unchanged by consuming point-in-time snapshots.
- Future leakage is prevented through explicit cutoff filtering.
- Same-day observations with aware timestamps can now be evaluated as long as they precede chart preparation or scheduled departure.
