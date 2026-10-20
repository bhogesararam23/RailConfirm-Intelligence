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
- Start with manual entry so the product and domain contracts can be implemented without depending on an unverified live integration.
- Make predictions only from an evaluated model or a documented baseline with demonstrated coverage.
- Add live tracking through an authorized data provider when permissions, usage terms and retention behavior are confirmed.
- Evaluate predictions against verified outcomes and publish limitations alongside performance results.

## Intended users

- **Ticket holder:** Wants to understand the possible final outcome of one or more WL/RAC passengers.
- **Group traveller:** Needs an estimate of whether the whole group, or a minimum number of people, will receive confirmed berths.
- **Researcher/developer:** Needs inspectable inputs, reproducible evaluation, model versions and explicit uncertainty.

These are working user groups. Product analytics or user research may narrow them later; do not imply validation interviews have already happened.

## Main product outcomes

- Passenger-level CNF/RAC/WL probability estimates when supported.
- Group-event probabilities derived from a joint or validated structured outcome distribution.
- A status and prediction timeline that preserves observation timestamps.
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
- and live data access complies with the relevant provider terms.

Numeric success thresholds must be specified after data coverage is understood and before the locked test set is evaluated.

## Non-goals for the first release

- Guaranteeing confirmation or claiming official railway authority.
- Booking, changing, cancelling or modifying tickets.
- Bypassing railway/provider access restrictions.
- Using an LLM to fabricate probabilities or apply unvalidated news adjustments.
- Claiming reliable support for every train, quota and WL category before testing.
- Building subscriptions, ads, social features or complex notifications before the predictor is defensible.

## Product principle

**The product must be allowed to say “not enough evidence.”** An honest unavailable state is better than a precise-looking number produced outside tested model coverage.
