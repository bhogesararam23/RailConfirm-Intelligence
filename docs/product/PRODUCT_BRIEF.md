# Product brief — RailConfirm Intelligence

Status: product direction, not a launch claim. Last reviewed: 2026-10-21.

## What it is

RailConfirm Intelligence is intended to estimate final reservation outcomes for Indian Railways passengers with waitlisted (WL) or RAC tickets. It is both a web product and a probabilistic modelling research project.

The product should help a passenger understand three separate questions:
1. What is the estimated chance that this passenger receives a confirmed berth?
2. What is the estimated chance that this passenger ends at RAC or remains waitlisted?
3. Given the passengers on this booking, what are the likely outcomes for the group?

It should also explain how much evidence supports the forecast and how the estimate changes when new status information becomes available.

## Problem

A single current WL/RAC position is not enough to explain every reservation outcome. Similar-looking tickets can differ by route segment, class, quota, train, journey date, time remaining and status movement. Group bookings add another complication: individual outcomes are related, and the chance that everyone receives a confirmed berth is not the same as the average passenger-level chance.

Existing estimates can also be hard to interpret when they do not clearly explain prediction timing, evidence coverage, or whether "confirmation" means a full berth versus RAC accommodation.

## Product direction

Build a reliable, transparent prediction workflow in stages:
- Start with a manual-entry product that runs locally and uses reviewed local data/model artifacts.
- Keep third-party runtime APIs, live status polling, hosted inference and live news/event feeds out of the current build.
- Allow research agents to discover and prepare candidate datasets, but approve each source only after provenance, licence/terms, privacy, labels and quality have been reviewed.
- Make predictions only from an evaluated model or a documented baseline with demonstrated coverage.
- Evaluate predictions against verified outcomes and publish limitations alongside performance results.
- Treat authorized live ticket/status sources and verified current/upcoming contextual signals as planned core capabilities of the target product. They are not part of the first local-first build; they follow the local data/model/evaluation foundation in roadmap Phases 8–10. Each actual provider/source still requires a source-specific ADR, permission review and evidence of reliability/value.

## Intended users

- **Ticket holder:** Wants to understand the possible final outcome of one or more WL/RAC passengers.
- **Group traveller:** Needs an estimate of whether the whole group, or a minimum number of people, will receive confirmed berths.
- **Researcher/developer:** Needs inspectable inputs, reproducible evaluation, model versions and explicit uncertainty.

These are working user groups. Product analytics or user research may narrow them later; do not imply validation interviews have already happened.

## Main product outcomes

- Passenger-level CNF/RAC/WL probability estimates when supported.
- Group-event probabilities derived from a joint or validated structured outcome distribution.
- A status and prediction timeline that preserves observation timestamps, including future authorized live ticket/status updates.
- Incorporation of verified current and upcoming operational/news/event signals, once source permissions and incremental predictive value are established.
- A readable explanation of evidence coverage, model version and limitations.
- Clear rejection/abstention behavior for unsupported data or status categories.
- An auditable research trail from data source to model evaluation.

## What success means

Success is not defined by how many percentages the interface displays. It is defined by whether:
- outcomes are labelled consistently and legitimately;
- the model improves on a defensible baseline on future journeys;
- reported probabilities are reasonably calibrated;
- group-level estimates are evaluated separately from individual estimates;
- users can distinguish observed status from predicted outcome;
- uncertainty and gaps are visible;
- all locally used data has documented provenance and permitted-use status, and future live integrations are reliable, authorized and shown to improve the user experience.

Numeric success thresholds must be specified after data coverage is understood and before the locked test set is evaluated.

## Deferred from the first release, but part of the long-term product goal

- Authorized live ticket/PNR status integration and status refresh.
- Verified current/upcoming operational, event/news and calendar-context feeds, after source review and evaluation.
- Continuous forecast history and later alerting based on new observations.

These capabilities are planned for roadmap Phases 8–10. Their provider choices and exact implementation are not yet decided. If no suitable authorized source is available, the limitation must be stated; access restrictions must never be bypassed.

## Non-goals for the first release

- Guaranteeing confirmation or claiming official railway authority.
- Booking, changing, cancelling or modifying tickets.
- Bypassing railway/provider access restrictions.
- Using an LLM to fabricate probabilities or apply unvalidated news adjustments.
- Claiming reliable support for every train, quota and WL category before testing.
- Building subscriptions, ads, social features or complex notifications before the predictor is defensible.

## Product principle

**The product must be allowed to say “not enough evidence.”** An honest unavailable state is better than a precise-looking number produced outside tested model coverage.
