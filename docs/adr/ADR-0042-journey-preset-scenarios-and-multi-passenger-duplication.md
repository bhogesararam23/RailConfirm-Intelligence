# ADR-0042: Journey preset scenarios and multi-passenger status duplication

- **Status:** Accepted
- **Date:** 2026-11-04
- **Decision owner:** Lead Software Engineer
- **Related:** ADR-0003, ADR-0007, ADR-0016, ADR-0041, `frontend/src/app/page.tsx`, `frontend/src/hooks/usePassengerList.ts`

## Context

Under ADR-0003 and ADR-0016, RailConfirm Intelligence supports group bookings with dependent Poisson-binomial distributions and queue comonotonic bounds for up to 6 passengers (`MAX_PASSENGERS = 6`).
However, manually typing 6 passenger statuses (e.g., as-booked status `GNWL/101` and current status `GNWL/25` through `GNWL/106` and `GNWL/30`) across multiple input fields was cumbersome, repetitive, and error-prone during manual usage and testing.

Furthermore, manual testing of complex multi-passenger states (such as mixed waitlist and RAC outcomes, Tatkal waitlist codes, or solo waitlists) required users to recall valid Indian Railways station code pairs (e.g. `NDLS` -> `HWH`, `MMCT` -> `NDLS`) and class/quota combinations (`3A`/`GN`, `SL`/`GN`, `3A`/`TQ`).

## Decision

1. **Automatic Passenger Duplication with Sequence Number Incrementing**:
   - Provide a "Duplicate" button on each passenger row.
   - Implement `incrementStatusString(status: string)` which matches the trailing numeric sequence in any status string and increments it by 1 (e.g. `GNWL/45` -> `GNWL/46`, `RAC 10` -> `RAC 11`, `CKWL/12` -> `CKWL/13`), while preserving status prefixes and punctuation.
   - Insert duplicated passengers immediately after the source row in the group sequence, preserving observation timing state while respecting the 6-passenger limit (`canDuplicate = rows.length < MAX_PASSENGERS`).

2. **Pre-configured Realistic Journey Preset Scenarios**:
   - Provide one-click preset test scenarios on the manual predictor page:
     - **Solo Waitlist**: Single passenger waitlist scenario (`12301`, `NDLS` -> `HWH`, `SL`/`GN`, `GNWL/45` -> `GNWL/12`).
     - **Family Mixed WL & RAC**: 3 passengers with mixed confirmation states (`12952`, `MMCT` -> `NDLS`, `3A`/`GN`, `RAC 5` -> `CNF`, `RAC 6` -> `RAC 1`, `GNWL/8` -> `RAC 2`).
     - **Full Group Booking**: Maximum 6-passenger high-density booking (`12840`, `HWH` -> `MAS`, `SL`/`GN`, `GNWL/101`..`106` -> `GNWL/25`..`30`).
     - **Tatkal Quota WL**: Tatkal waitlist quota booking (`12259`, `SDAH` -> `BKN`, `3A`/`TQ`, `CKWL/12`..`13` -> `CKWL/5`..`6`).
   - Automatically configure valid forward-looking journey departure dates (+7 days).
   - Announce preset selection via accessible `aria-live="polite"` status notifications so screen-reader users receive clear auditory feedback without losing input focus.

## Alternatives considered

- **Requiring manual row entry for every passenger**: Inefficient and slows down manual regression testing and product demonstrations.
- **Random mock data generation in the form**: Random strings risk generating invalid Indian Railways status combinations (e.g. invalid class/quota/status pairings) that violate domain validation rules. Curated presets guarantee validity while covering distinct operational topologies.

## Consequences

### Positive
- Substantially improved ergonomics for multi-passenger booking queries and demonstrations.
- Zero friction for testing mixed-status group probability computations.
- Accessible announcements inform assistive technologies of dynamic form state changes.
- Tested and verified through both Vitest contract suites and Playwright real browser E2E tests.

### Negative / Costs
- Adds preset definitions to frontend bundle (~1 KB).

## Validation

- Unit tests in `frontend/src/lib/__tests__/validation.test.ts` verifying `incrementStatusString` across diverse Indian Railways status strings (`GNWL/45`, `RAC 10`, `CKWL 1`, `WL 99`).
- Vitest component tests in `frontend/src/components/__tests__/contract.test.tsx` verifying preset application and duplicate button actions.
- Playwright E2E browser tests in `frontend/e2e/journey.spec.ts` asserting button clicks, DOM updates, and sequence incrementation in Chromium.
