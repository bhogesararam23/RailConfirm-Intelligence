# ADR-0041: Real browser end-to-end verification gate using Playwright

- **Status:** Accepted
- **Date:** 2026-11-04
- **Decision owner:** Lead Software Engineer
- **Related:** ADR-0007, ADR-0012, ADR-0015, ADR-0027, ADR-0040, `docs/architecture/API_CONTRACT.md`

## Context

RailConfirm Intelligence had established two levels of system verification:
1. In-process unit, property and contract suites (Pytest in the backend with 1,195 tests, and Vitest in the frontend with 129 tests).
2. The cross-stack smoke script (`scripts/smoke_full_stack.py`, ADR-0027), which runs both the FastAPI backend and Next.js production server over loopback TCP sockets and tests raw HTTP endpoints.

However, as ADR-0027 explicitly acknowledged:
> "Does not prove: page interaction. No browser runs, so the rendered HTML is checked for content only. A JavaScript-only failure would still pass."

Specifically, several critical product surfaces remained completely unverified in an actual browser engine:
- DOM accessibility trees, client-side input validation barriers (`role="alert"`, `aria-invalid`), and polite screen-reader announcements.
- Dynamic multi-passenger workflows: adding rows, duplicating passenger rows with sequence incrementation, removing rows, and capping at 6 passengers.
- Preset journey scenario loading and state hydration.
- The real browser interaction of submitting a prediction request, rendering structured abstention cards and distributions under ADR-0007 constraints, and client-side JSON export.
- Full prediction history roundtrip: checking "Keep this report on this machine", navigating to `/history`, live client-side query and target filtering, navigating to `/prediction/[id]`, breadcrumb navigation, and report deletion via `DELETE /v1/predictions/[id]`.

During early implementation of this browser test, a genuine production defect was immediately uncovered: `backend/railconfirm/api/app.py` configured CORS with `allow_methods=["GET", "POST", "OPTIONS"]`, omitting `"DELETE"`. When a browser issued a `fetch(..., { method: 'DELETE' })` to delete a kept report, the browser's CORS preflight request was rejected by Starlette's CORS middleware. This defect was completely invisible to FastAPI's in-process `TestClient` and raw python socket checks because neither executes browser CORS preflight negotiations.

## Decision

1. **Establish Playwright as the official browser E2E test framework**:
   - Add `@playwright/test` to `frontend/package.json`.
   - Provide `frontend/playwright.config.ts` configuring automated startup of both the FastAPI backend (`uvicorn railconfirm.api.app:app` on port 8010) and the Next.js frontend (`npx next dev -p 3010`) with loopback TCP socket health polling before test execution.
   - Support cross-platform virtualenv discovery (Windows `.venv/Scripts/python.exe`, Linux/CI `backend/.venv/bin/python`, fallback to system Python).

2. **Add E2E suites covering critical user journeys**:
   - `frontend/e2e/journey.spec.ts`: Tests home page rendering, client-side validation barriers, preset journey application, passenger duplication with status sequence incrementing, and live prediction execution with structured abstention output.
   - `frontend/e2e/history.spec.ts`: Tests opt-in report persistence, `/history` listing, real-time query and target filtering, stored report reopening, and permanent deletion.

3. **Incorporate browser E2E into CI**:
   - Add a dedicated `browser-e2e` job in `.github/workflows/ci.yml` running Playwright Chromium in headless mode against live backend and frontend servers, uploading traces and screenshots as artifacts only on failure.

4. **Correct backend CORS configuration**:
   - Update `backend/railconfirm/api/app.py` `CORSMiddleware` to include `"DELETE"` in `allow_methods`.

## Alternatives considered

- **Puppeteer or Cypress**: Cypress introduces large proprietary dependencies and struggles with native multi-tab/window and modern cross-process orchestration; Puppeteer lacks first-class cross-browser test runner ergonomics and tracing features provided by Playwright.
- **Relying solely on `scripts/smoke_full_stack.py`**: As proven by the CORS `DELETE` defect, headless HTTP clients cannot verify browser-enforced security boundaries (such as CORS preflights), client-side JavaScript execution, focus management, or dynamic React re-renders.

## Consequences

### Positive
- Genuine end-to-end verification of the user journey from form interaction to server response to local storage and deletion.
- Immediate detection of CORS, routing, DOM, and JavaScript lifecycle regressions in CI and local development.
- Zero reliance on external network calls or third-party APIs: all tests run entirely on loopback localhost.
- Fast execution: the full 6-test Playwright suite completes in ~15 seconds locally.

### Negative / Costs
- Requires Playwright Chromium browser binaries installed in CI and dev environments (`npx playwright install --with-deps chromium`).
- Requires both backend and frontend servers to build and spin up during test runs.

## Validation

- `npx playwright test` executed locally against running FastAPI and Next.js instances: 6 passed in 15.1s.
- `DELETE /v1/predictions/[id]` confirmed working through real Chromium browser preflight with HTTP 204 response.
- Vitest unit/contract tests (129 tests), pytest backend suite (1,195 tests), and repository hygiene scanner all pass cleanly.
