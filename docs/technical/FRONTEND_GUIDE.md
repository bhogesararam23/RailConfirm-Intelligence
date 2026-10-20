# Frontend interaction guide

Status: behavior and UX contract for implementation.

## Page map

Initial routes can remain simple:
- / — explanation and manual prediction entry.
- /prediction/[id] — saved/versioned prediction report using a random internal ID.
- /tracking/[trackingId] — future route; keep unavailable until authorized tracking is enabled.
- /about/methodology — target, data and uncertainty explanation.
- /about/data — source and data-use boundaries.

Do not put PNRs or raw private source identifiers in browser paths or query strings.

## Input experience

- Group journey fields separately from passenger rows.
- Explain original status versus latest observed status.
- Ask for an observation time where known; let the user mark it unknown rather than inventing one.
- Keep raw status visible when normalization is uncertain.
- Do not ask for a passenger name.
- Allow adding/removing passengers and state group count clearly.
- Use explicit examples tagged illustrative where examples are required.
- Client validation improves usability but the server must validate again.

## Result experience

The page should distinguish:
1. observed ticket status;
2. model-estimated final outcome;
3. group-level derived events;
4. data freshness and limitations.

Each number requires a clear label, probability interpretation, prediction timestamp and model/evidence status. Do not show a generic confidence score as if it were a calibrated outcome probability.

Recommended report order:
- supported / abstained state;
- target moment and latest input timestamp;
- passenger outcomes;
- group outcomes, if supported;
- main relevant inputs and explanation caveat;
- model version, evidence coverage and limitations.

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

## Accessibility

- Use semantic headings and form controls.
- Associate labels with controls.
- Keep keyboard navigation in logical order.
- Announce validation and state changes to assistive technology.
- Do not rely on hover as the only way to access information.
- Use textual labels in addition to colors and icons.

## Analytics

If product analytics are added, track only events needed to improve the user experience. Do not include PNRs, passenger names, exact route/ticket data or raw user input in analytics payloads by default. Record analytics and retention implications in the security/privacy review.
