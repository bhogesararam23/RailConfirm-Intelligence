# RailConfirm Intelligence — Frontend

A local-first Next.js frontend for the RailConfirm Intelligence prediction tool. Estimates the final chart status (CNF / RAC / WL) for Indian Railways waitlisted and RAC tickets entered manually. No live railway API calls are made.

## Status

MVP shell — form and UI structure are complete. Numeric probability estimates are only shown when a validated model is available from the backend. Until then, the tool displays an honest abstention message.

## Requirements

- Node.js ≥ 18
- npm ≥ 9
- Backend running at `http://localhost:8000` (or set `NEXT_PUBLIC_API_URL`)

## Setup

```powershell
Set-Location d:\RailConfirm-Intelligence\frontend
npm install
npm run type-check
npm run build
```

## Development

```powershell
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |

Create a `.env.local` file to override:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure

```
src/
  app/                   Next.js App Router pages
    page.tsx             Home — manual prediction entry form
    about/
      methodology/       What the model predicts and its limitations
      data/              Data governance and source boundaries
  components/
    ui/                  Shared UI primitives (badges, bars, cards)
    prediction/          Prediction-specific form and result components
    layout/              Header, Footer, Navigation
  lib/
    types.ts             TypeScript types matching the API contract
    api.ts               Typed fetch client for the backend
    validation.ts        Client-side input validation
    statusUtils.ts       Status display helpers
  hooks/
    usePrediction.ts     Prediction submission state hook
    usePassengerList.ts  Passenger list management hook
```

## Key Principles

- **No fabricated probabilities.** The tool shows "Estimate not available" when no trained model exists.
- **No passenger names collected.** Inputs are ticket statuses only.
- **No PNRs in URLs.** Internal random IDs are used for saved results.
- **Accessibility first.** All status indicators use text labels in addition to colour.

## Related Docs

- Architecture: `../docs/architecture/`
- API Contract: `../docs/architecture/API_CONTRACT.md`
- Frontend Guide: `../docs/technical/FRONTEND_GUIDE.md`
- ADR index: `../docs/adr/README.md`
