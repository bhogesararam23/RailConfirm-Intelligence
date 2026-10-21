# Project canvas

Last reviewed: 2026-10-21

This is the short working view of the project. The canonical phase-by-phase plan is [the roadmap](ROADMAP.md).

## Problem

People holding WL and RAC tickets do not know the likely final reservation outcome, especially when a booking has multiple passengers whose final statuses can differ.

## Intended product

A research-backed manual-entry web application that can estimate passenger-level outcomes and, when validated, group-level outcomes using reviewed historical data and local model artifacts.

## Current build boundary

**Local-first. No third-party runtime APIs.**

- No live IRCTC/PNR lookups or polling.
- No external news, holiday, weather, crowd or event APIs.
- No hosted model-inference dependency.
- The app may use its own internal backend API.
- Data can be researched or prepared by agents and supplied as local files, but provenance, licence/terms, privacy, target labels and quality must be checked before training.
- Missing approved data or model coverage must be shown honestly; synthetic fixtures are only for development/tests.

See [ADR-0007](adr/ADR-0007-local-first-no-external-runtime-apis.md).

## Current priorities

**P0 — Scope and data intake**
1. Keep the local-only runtime boundary explicit.
2. Research candidate datasets through primary-source links and agent-assisted intake.
3. Complete the [dataset intake checklist](data/DATASET_INTAKE_CHECKLIST.md) for every candidate.
4. Identify if any dataset has reliable status trajectories and final outcomes permitted for ML training.

**P1 — Domain correctness**
1. Implement status/domain types and parsing.
2. Preserve raw statuses and unknown codes.
3. Add tests for positions, timestamps, missing inputs and mixed RAC/WL groups.

**P2 — Baseline and evaluation**
1. Build quality checks and as-of-time snapshots for approved local data.
2. Implement a historical/statistical baseline.
3. Use chronological, booking-group-aware evaluation.
4. Report calibration, proper scoring rules, coverage and uncertainty.

**P3 — Local web vertical slice**
1. Build manual form and passenger rows.
2. Add internal API and local inference interface.
3. Display model results only when backed by an evaluated model; otherwise return a clear no-model/unsupported state.
4. Add user-facing evidence and limitations.

**P4 — Group modelling and hardening**
1. Evaluate group-outcome estimation on real labelled groups.
2. Complete tests, model card, local setup and CI.
3. Verify the application runs without third-party API credentials.

## Explicitly deferred

Live PNR tracking, external provider integrations, news/calendar/weather/event APIs, hosted inference, push notifications and automatic refresh are not in the current roadmap. Reopen them only through a new ADR after a concrete need is established.

## Assumptions still to test

- A legally usable dataset with consistent final outcomes can be obtained.
- Status progression contains useful predictive signal.
- There are enough mixed-status groups to evaluate joint outcomes.
- The candidate model improves on a baseline and can be calibrated.

These are hypotheses, not findings.

## Next review

Update this canvas when the dataset inventory is complete and again after the first reproducible baseline. Do not mark a milestone complete without the documented exit criteria in ROADMAP.md.
