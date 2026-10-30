# ADR-0027: A cross-stack smoke gate — two real processes, one socket, and no suite that skips itself

- **Status:** Accepted
- **Date:** 2026-10-30
- **Decision owner:** Project maintainer
- **Related:** ADR-0007 (local-first, no external runtime APIs), ADR-0010 (declared check
  configurations), ADR-0012 (opt-in prediction history), `scripts/smoke_full_stack.py`,
  `frontend/vitest.live.config.ts`, `frontend/src/lib/__tests__/liveApi.test.ts`,
  `.github/workflows/ci.yml`, `docs/technical/TESTING_STRATEGY.md`

## Context

CI had three jobs and they could all be green while the two halves of the product
disagreed. The backend tests drive FastAPI through its in-process test client. The
frontend tests mock `fetch` and assert against fixtures written by hand. Nothing in
either job would notice:

- a response field renamed on one side and not the other; the backend's schema tests and
  the frontend's fixture agree with themselves, not with each other;
- an error envelope whose shape changed — `details[0].field`, the `X-Request-ID` header,
  the `not_found` code — which the UI's error states render;
- a production build whose `NEXT_PUBLIC_API_URL` was inlined as a different origin, so
  the browser calls a server that is not the one under test;
- CORS refusing the frontend origin, which the client reports as an unreachable backend;
- the history round trip (store, reopen, list, delete, delete again) across the HTTP
  boundary rather than against the storage module directly.

The project already had `backend/tests/api/` integration tests and a manual procedure in
`docs/technical/LOCAL_FIRST_DEVELOPMENT.md` to run the two together. The manual procedure
is the part that does not happen.

## Decision

1. **One script starts both processes and checks them over TCP.** `scripts/smoke_full_stack.py`
   starts the backend under uvicorn on `127.0.0.1:8010` with prediction history enabled and
   a throwaway storage directory, waits for `/v1/health`, drives the documented contract with
   `urllib` (health, abstention, a field-level refusal, the same-day horizon refusal, store /
   reopen / list / delete / delete-again, a PNR-shaped id, an unrouted path, the CORS
   preflight), then starts the production frontend build with `next start` on
   `127.0.0.1:3010` and fetches its pages. Nothing is mocked, nothing leaves loopback, and
   no third-party service or credential is involved.

2. **It asserts the built bundle names the running backend.** `NEXT_PUBLIC_API_URL` is
   inlined at build time, so the script reads the built JavaScript and fails if no chunk
   contains the origin it just started. Without this check the two halves could each be
   healthy and never meet, which is the failure this gate exists to catch.

3. **The client's own request-building code is what the server answers.** The live suite
   (`frontend/src/lib/__tests__/liveApi.test.ts`, `npm run test:live`) imports `src/lib/api.ts`
   and calls `submitPrediction`, `checkHealth`, `fetchStoredPrediction`, `fetchStoredReports`
   and `deleteStoredPrediction` against the running backend. It is not a second copy of the
   contract written in the test; it is the module the pages import.

4. **The live suite runs in Vitest's `node` environment, not jsdom.** This is a correction,
   not a preference. `src/lib/api.ts` wraps every request in an `AbortController` so a hung
   backend cannot leave the form spinning. Under the jsdom environment that controller is
   jsdom's, `fetch` is Node's, and Node's fetch rejects a foreign `AbortSignal` with
   `TypeError: RequestInit: Expected signal ("AbortSignal {}") to be an instance of
   AbortSignal`. `api.ts` reports that, correctly from its own point of view, as a network
   failure — so under jsdom every one of the five checks failed with "the backend may not be
   running" while the backend was running and answering. The suite would have been measuring
   the harness. In Node, `fetch`, `AbortController` and `URL` come from one realm. A browser
   is a single realm too, so this environment is closer to the real one than jsdom was.

5. **The suite refuses to run without a server; it does not skip.** `vitest.live.config.ts`
   throws when `RAILCONFIRM_LIVE_API_URL` is unset, and the test file repeats the refusal.
   `npm test` excludes the file entirely (`vitest.config.ts`). A skip reports success without
   evidence, and a suite that skips itself in every run nobody is watching is indistinguishable
   from a suite that passes.

6. **CI runs it as a fourth job, and `scripts/` is linted.** `full-stack-smoke` installs the
   backend's runtime dependencies, builds the frontend with
   `NEXT_PUBLIC_API_URL=http://127.0.0.1:8010`, runs the script, and on failure uploads the
   server logs (`RAILCONFIRM_SMOKE_LOG_DIR` keeps them; the default is a temporary directory
   that is gone by the time a run is read). `ruff check --config backend/pyproject.toml scripts/`
   joins the hygiene job, because the gate scripts were the one part of the Python code that
   no gate covered — run from the repository root, Ruff would otherwise fall back to its own
   defaults and judge them by rules the rest of the repository does not use.

7. **The gate states what it does not cover.** No browser runs: the pages are checked for
   the content they must render, so a JavaScript-only failure still passes. Interactions,
   focus order and the rendered abstention states are covered by the component tests and
   by nothing end-to-end. No artifact is promoted, so every prediction in this job must
   abstain and the script asserts that it does. It says nothing about railway accuracy.

## Alternatives considered

- **In-process `TestClient` end to end** (what `backend/tests/api/` already does). Rejected
  as a substitute: it never builds the frontend, never starts a second process, never sees a
  socket, and cannot observe a wrong inlined origin or a CORS refusal.
- **Playwright or another browser driver.** Deferred rather than rejected. It would add
  interaction coverage, but it also adds a browser download and a class of timing flakiness
  to every push, and the client contract is already exercised by the real module. The honest
  gap is recorded above; a browser belongs here once there is UI behaviour that only a browser
  can check, not before.
- **Mocking the backend for the frontend suite and calling it "integration".** Rejected:
  that is what the existing component tests do, and it is exactly the blindness this gate
  was added to remove.
- **Letting the live suite skip when no backend is running**, so `npm test` could include it.
  Rejected on principle and because CI now provides a server, making the skip pointless.
- **Ephemeral ports.** Rejected: the frontend's API origin is inlined at build time, so the
  build and the server must agree on a port before either starts. The script uses fixed
  loopback ports and fails with an explicit message if one is taken, naming the flag to change.

## Consequences

- CI gains a job whose failure is a real integration defect: a contract drift, a broken
  build origin, a CORS misconfiguration, or a history flow that only works in-process.
- The smoke's four refusals are now checked twice with different machinery: once in
  `backend/tests/api/` (fast, in-process) and once here (slow, over TCP). That duplication is
  deliberate — the second one is the only one that can be wrong about the deployment.
- A developer can run the same gate locally: `python scripts/smoke_full_stack.py`. It is
  documented in `README.md` and `docs/technical/TESTING_STRATEGY.md`, and it requires
  `npm ci` and `npm run build` first.
- jsdom remains the environment for the component tests, where a DOM is the point. The
  realm problem is specific to code that builds an `AbortController` and hands it to a
  runtime-provided `fetch`, and that is recorded here so the next person does not rediscover
  it as "the client is broken under test".
- Browser-level interaction testing, accessibility auditing and visual regression remain
  unverified by CI. They are real gaps, not covered by this decision.

## Validation

`scripts/smoke_full_stack.py` was run on 2026-10-30 against a production frontend build: 11
checks pass (eight backend, one client suite, two frontend). The first run failed at the
client suite with five network failures, which is how the jsdom realm problem was found;
that failure is quoted in the decision above. `npm test` passes with the live file excluded
(115 tests, 6 files). Ruff, the repository hygiene script and the backend suite were run
before the change was committed, and the new CI job's first run is the evidence for the job
itself.
