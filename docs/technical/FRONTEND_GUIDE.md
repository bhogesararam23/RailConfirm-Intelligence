# Frontend interaction guide

Status: behaviour and UX contract, with an implementation note on what `frontend/src/` does today.

## Page map

Implemented:

- `/` — manual prediction entry and the report for that request.
- `/prediction/[id]` — a report the user chose to keep, reopened by the internal id the
  API returned. It renders the stored response and must not recompute anything: a reopened
  report is evidence about what was said then, so it carries the model version, registry
  state and limitations it was served with, plus the moment it stops being retrievable.
  Three outcomes need distinct copy, because they call for different actions: never
  stored, aged out of retention, and this server keeps no history at all.
- `/about/methodology` — target, data and uncertainty explanation.
- `/about/data` — source and data-use boundaries.

Not implemented, deliberately:

- `/tracking/[trackingId]` — belongs to roadmap Phases 8–10; must stay unavailable
  until authorized tracking exists.

Saving is opt-in twice over (ADR-0012): the server must have history enabled and the
request must ask to be kept. The form therefore states that the response says whether the
report was actually kept, rather than implying the checkbox controls storage on its own.

Do not put PNRs or raw private source identifiers in browser paths or query strings.

## Input experience

- Group journey fields separately from passenger rows. **Implemented.**
- Explain original status versus latest observed status. **Implemented.**
- Ask for an observation time where known; let the user mark it unknown rather than inventing one. **Implemented** — the unknown checkbox is the default, because a fabricated timestamp is worse than a missing one.
- Keep raw status visible when normalization is uncertain. **Implemented** — the badge shows the normalized category and the raw string together, and server parse notes surface as warnings.
- Do not ask for a passenger name. **Implemented.**
- Allow adding/removing passengers and state the group count clearly. **Implemented** — at the limit the control stays visible and disabled with the reason, rather than vanishing.
- Use explicit examples tagged illustrative where examples are required. **Implemented** — the prefilled journey is labelled as an example.
- Client validation improves usability but the server must validate again. **Implemented** — `lib/validation.ts` mirrors the server rules and server 422 field paths are mapped back onto the inputs.
- A prediction moment and target are part of the request, so the form asks for both rather than assuming them. The observation and prediction timestamps are sent with the browser's UTC offset; the backend rejects naive timestamps.

## Result experience

The page distinguishes observed status, per-passenger estimate, group events, and
data/limitation context. Rendering rules that are enforced by tests:

- A null probability renders as an em dash, never as `0.0%`.
- All five outcome classes appear in the distribution, so the legend matches the
  server's declared outcome space.
- The evidence cohort and its sample size are shown, and a broad-cohort fallback is
  labelled as one.
- Group numbers stay next to their independence assumption, and the three group
  events are stated not to sum to 100%.
- An unrecognised abstention reason says the interface is out of date instead of
  borrowing another reason's text.
- Provenance — target, as-of time, model version, registry state, feature schema —
  is shown even when everything abstains, because that is when it matters most.

## Visual language

- Do not communicate outcome only through red/green.
- Ensure text contrast and keyboard-visible focus.
- Keep status/category labels textual.
- Use loading, empty, stale, unsupported and error states intentionally.
- Avoid animation that obscures the numbers or status.
- Do not use fake testimonials, accuracy counters or real-time badges without supporting evidence.

## Copy principles

Prefer:
- Estimated chance of a confirmed berth
- Estimated chance of RAC at final chart
- Latest observed status (as of 10:30 IST)
- Not enough validated data for this ticket category
- This estimate is not a guarantee

Avoid:
- Guaranteed confirmation
- 100% accurate AI
- Confirmed when the model predicts a probability
- Live when the source timestamp is unknown or stale
- AI says as a substitute for showing evidence context
- "No data leaves your environment" as an unqualified claim. The truthful statement
  depends on where the configured backend is: the page says requests go to this
  machine when the URL is loopback, and says they leave the device when it is not.

## Accessibility

- Use semantic headings and form controls.
- Associate labels with controls; link field errors with `aria-describedby` and mark
  the control `aria-invalid`.
- Keep keyboard navigation in logical order, with a skip link to the main region.
- Announce validation and state changes to assistive technology — one live region per
  message, not a nested stack that repeats the same text.
- Do not use `role="status"` on static content: it is a live announcement, and a
  status label that never changes should not interrupt a screen reader on re-render.
- Do not rely on hover as the only way to access information.
- Use textual labels in addition to colors and icons.

## Analytics

No analytics are configured, and none should be added without a privacy review. If they are added later, track only events needed to improve the experience, and never include PNRs, passenger names, exact route or ticket data, or raw input. Record the retention implications in the security and privacy review.
