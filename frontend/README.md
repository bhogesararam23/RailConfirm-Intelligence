# RailConfirm Intelligence — Frontend

A local-first Next.js frontend for the RailConfirm prediction tool. It collects a
journey and per-passenger ticket statuses by hand and shows what the backend
returns: observed statuses, and either an outcome distribution or a structured
abstention. No live railway API is called.

## Status

The form, result rendering and abstention states are implemented, and the
TypeScript types mirror `backend/railconfirm/api/v1/schemas.py` field for field,
with contract tests that fail if the two drift.

Nothing here has been validated against real predictions, because the backend
produces none yet: no dataset has been approved and no model artifact is promoted,
so a real request returns an abstention. The supported-number path was exercised
locally against a temporary synthetic artifact to confirm the rendering, and that
artifact was deleted afterwards.

## Requirements

- Node.js ≥ 18, npm ≥ 9
- Backend on `http://127.0.0.1:8000`, or set `NEXT_PUBLIC_API_URL`

The backend only answers cross-origin requests from origins listed in
`RAILCONFIRM_CORS_ALLOWED_ORIGINS` (default: `http://localhost:3000` and
`http://127.0.0.1:3000`). If you run the dev server on another port, add that
origin to the backend, or the browser blocks the preflight and the page reports an
unreachable backend. On the maintainer's machine port 3000 is Grafana, so:

```bash
# backend
RAILCONFIRM_CORS_ALLOWED_ORIGINS='["http://localhost:3123"]' \
  uvicorn --app-dir backend railconfirm.api.app:app --port 8000
# frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev -- -p 3123
```

## Commands

```bash
npm ci
npm run dev         # development server
npm run type-check  # tsc --noEmit
npm run lint        # next lint
npm test            # vitest run — unit and contract tests
npm run build       # production build
```

CI runs all of the above.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Backend the browser calls. Inlined into the bundle at build time. |

Set it in `.env.local`. Because the value is baked into client JavaScript at build
time, changing it needs a rebuild, not just a restart.

The page states where requests go, and only claims "this machine only" when the
configured URL is actually a loopback address. Point it at a remote host and the
copy changes to say your input leaves the device.

## Structure

```
src/
  app/                   App Router pages
    page.tsx             Prediction entry form and result
    about/methodology/   What is estimated, and what is not
    about/data/          Provenance, privacy and intake boundaries
  components/
    ui/                  StatusBadge, ProbabilityBar, AbstentionCard, ErrorBanner, LoadingSpinner
    prediction/          JourneyForm, PassengerList, PassengerRow, PredictionResult, outcome cards
    layout/              Header, Footer
  lib/
    types.ts             Mirrors the backend response schemas
    api.ts               Fetch client: timeout, error envelope, origin checks
    validation.ts        Client rules that mirror the server's
    statusUtils.ts       Display formatting, null-safe probability rendering
  hooks/
    usePrediction.ts     One in-flight request, typed failure states
    usePassengerList.ts  Rows with stable ids, capped at the server's limit
  test/                  Vitest setup
  **/__tests__/          Unit and contract tests
```

## Principles enforced in code

- **No fabricated probabilities.** A null probability renders as an em dash. The
  `(x || 0) * 100` idiom that turned a missing estimate into a confident "0.0%" is
  covered by a test.
- **Observed and estimated stay separate.** Both the as-booked and the current
  status are shown from the server's fields, distinct from any probability.
- **Abstentions name their own reason.** Every reason code the backend can send has
  distinct text; an unrecognised code says the interface is out of date rather than
  borrowing the "no model" message.
- **Group numbers carry their assumption.** The independence baseline is labelled as
  an approximation, and the three group events are stated not to sum to 100%.
- **Colour never carries meaning alone.** Every status badge pairs a hue with text
  and an aria description.
- **Nothing is claimed to be saved.** There is no persistence in the product, so no
  copy says results are stored or retrievable.

## Related docs

- `../docs/architecture/API_CONTRACT.md` — the response this client is written against
- `../docs/technical/FRONTEND_GUIDE.md` — conventions and the accessibility rules
- `../docs/data/DATASET_INTAKE_CHECKLIST.md` — why there are no numbers yet
