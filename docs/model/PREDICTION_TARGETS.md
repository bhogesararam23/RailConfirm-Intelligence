# Prediction targets

Status: research specification; no trained model is implied.

## Primary estimand

At a defined `prediction_at` timestamp before final charting, estimate a passenger's final-chart reservation outcome using only information available by that timestamp. Separately estimate the joint distribution of outcomes for passengers belonging to the same booking group.

The target must be consistent within each evaluation. Do not mix final-chart status with status at departure or another post-chart outcome.

## Passenger outcomes

The primary multi-class target is intended to distinguish:
- `CNF`: confirmed berth at final chart under the chosen label definition.
- `RAC`: reservation against cancellation at final chart.
- `WL`: waitlisted at final chart.
- `OTHER`: another explicitly defined outcome that cannot safely be placed into the three groups above.
- `CENSORED`: the outcome is not reliably observed under the target definition.

Depending on availability and sample size, the first deployable model may handle only a subset. Never coerce `OTHER` or `CENSORED` into WL merely to make the class count convenient. Record exclusions and their counts.

For supported mutually exclusive classes, probabilities should sum to 1, subject to rounding. If an outcome is excluded from the target, the API must clearly say whether probabilities are conditional on an eligible outcome or include an explicit other/unknown category.

## Prediction horizons

Record the actual `prediction_at` and time remaining until the relevant charting event when it is known. Evaluate at predeclared horizons where coverage supports it. Candidate horizons:
- earliest valid observation / booking;
- a fixed intermediate window before charting;
- a fixed near-chart window before charting.

Do not assume one universal charting time for all trains or journeys. Time zones and local railway dates must be preserved.

## Group outcomes

Let a booking contain passengers (1,…,n), with final outcomes (Y_1,…,Y_n). The group model should estimate the joint distribution (P(Y_1,…,Y_n mid X)), or a structured representation that supports calibrated derived events.

Derive:
- all passengers CNF;
- all passengers CNF or RAC;
- exactly (k) passengers CNF;
- at least (k) passengers CNF;
- at least one passenger WL at final chart;
- passenger-level and group-level outcome combinations where useful and supported.

Group probabilities must be computed from the joint distribution. Do not multiply individual probabilities by default; passengers share booking context and outcomes can be dependent.

## Target definitions that must be settled before training

- Whether the label is final-chart status only or another explicitly named point in time.
- How passenger cancellations, booking cancellations and chart changes are handled.
- How partial group cancellation or split outcomes are represented.
- How unknown, corrected, duplicate and contradictory source records are handled.
- Whether RAC "confirmation" in the UI means a full berth or merely RAC accommodation. These must be separate concepts.
- Whether waitlist status after chart preparation is in scope.

## Input contract

Each prediction request must carry:
- journey context (train, date, route segment, class, quota where known);
- original status and current status for each passenger, if available;
- observation timestamps and source/provenance;
- booking passenger count;
- `prediction_at`;
- model/schema version where supplied internally.

Avoid names and unnecessary identifiers.

## Output contract

The API should return:
- target definition and prediction timestamp;
- outcome classes and their probabilities for each passenger;
- joint/group event probabilities when supported;
- model and feature-schema versions;
- data freshness and evidence coverage;
- uncertainty / abstention state;
- a short, non-causal explanation of major model inputs where supported;
- known limitations for unsupported categories.

Do not describe feature contribution as causality. Do not output high precision if the evidence supports only a broad estimate.
