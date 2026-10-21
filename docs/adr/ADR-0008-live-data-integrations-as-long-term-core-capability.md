# ADR-0008: Treat authorized live data integrations as a core long-term product capability

- **Status:** Accepted
- **Date:** 2026-10-21
- **Decision owner:** Project maintainer
- **Related:** ADR-0007, docs/ROADMAP.md, docs/product/PRODUCT_BRIEF.md

## Context

ADR-0007 sets the boundary for the current build: the first version must work locally without third-party runtime APIs. That is an implementation sequencing decision, not a reduction of RailConfirm's overall product goal.

The intended long-term product is a data-aware reservation intelligence platform. In addition to manual entry and locally evaluated models, the target product is expected to use authorized current ticket/status data and relevant upcoming operational/context signals to keep estimates useful as journey conditions change. These integrations must follow the local model and data pipeline foundation because permissions, source reliability, costs, retention and predictive value must be verified first.

## Decision

Keep ADR-0007 in force for the current implementation, while explicitly treating external integrations as planned core capabilities of the long-term product roadmap rather than permanently excluded or merely decorative optional features.

The staged direction is:

1. **Current phases 0–7:** Build and validate the local data/domain/model/application workflow without third-party runtime APIs.
2. **Future Phase 8 — Authorized current ticket data:** Integrate an approved source for live PNR/status observations, when an eligible provider/source and permitted use are verified.
3. **Future Phase 9 — Current operational and contextual signals:** Ingest relevant verified event/news/calendar/operational data through approved sources, and keep each signal only if temporal evaluation demonstrates incremental predictive value.
4. **Future Phase 10 — Continuous tracking and forecast updates:** Use permitted new observations and validated context to refresh estimates, preserve prediction history, expose freshness, and add user notifications where justified.

The product must remain useful in a local/manual mode when external services are unavailable. Each concrete provider requires its own source/terms review and an ADR before implementation; a new ADR is an integration gate, not a reason to remove the capability from the product goal.

## Alternatives considered

- **Treat all external integrations as permanently out of scope:** Rejected because live status and relevant current/upcoming context are part of the intended long-term product.
- **Implement integrations before the local predictor is validated:** Rejected because live integrations do not substitute for correct targets, reliable labels, calibrated probabilities or group-outcome evaluation.
- **Treat any available API as automatically acceptable:** Rejected because access, storage, model training, publication, privacy and commercial rights can differ.
- **Allow arbitrary news headlines to alter probabilities directly:** Rejected; source items must be structured, time-stamped and evaluated for incremental value.

## Consequences

- The current build remains offline/local-first and requires no third-party credentials for core development, testing or manual input.
- Roadmap documents must distinguish current build scope from the future target product.
- Adapter boundaries and source provenance should be kept clean so a later approved provider can be added without rewriting domain/model logic.
- Provider selection, permissions, retention, failure behavior, cost and feature value must be assessed before integration.
- If no suitable authorized provider exists, the limitation must be documented; restricted access must never be bypassed.

## Validation

The roadmap and product documentation must consistently show live status integration and verified current/upcoming contextual signals as planned later phases. The current app must still run without them. When a provider is considered, record the exact permitted use and show through testing that removing or disabling the integration does not break the local/manual workflow.
