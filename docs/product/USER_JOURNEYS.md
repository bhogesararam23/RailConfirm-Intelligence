# User journeys

These journeys define intended behavior. They are specifications, not evidence that the product UI has already been implemented or user-tested.

## Journey A — Manual prediction for one passenger

1. User opens the prediction page.
2. User enters the train, journey date, boarding/destination stations, class and quota if known.
3. User adds one passenger and enters the original and latest observed reservation statuses.
4. The UI validates required fields and shows which optional context is missing.
5. The API determines whether the request is within supported model coverage.
6. If eligible, the result shows outcome probabilities, prediction timestamp, model/version, evidence coverage and limitations.
7. If not eligible, the result explains what is unsupported and does not invent a number.

**Acceptance signal:** The user can tell the difference between observed status and predicted final status.

## Journey B — Four-person mixed RAC/WL booking

1. User enters the journey once.
2. User adds four passenger status rows. The example values should come from the user's actual ticket; documentation examples are illustrative only.
3. The API retains every passenger outcome as a separate record.
4. If the model supports all relevant categories and group prediction, the result displays passenger rows plus group events such as all CNF, all CNF/RAC and at least two CNF.
5. If one passenger status is unsupported, the response explains whether the group calculation is unavailable or uses a validated, documented handling rule.
6. Group probabilities derive from a supported joint/structured outcome distribution.

**Acceptance signal:** The product does not treat four marginal probabilities as independent by default.

## Journey C — Revisit an earlier prediction

1. User opens a saved prediction using a random internal ID, not a raw PNR in the URL.
2. The page shows the original prediction timestamp, inputs, model version and estimate.
3. If the product has stored a later observation, it displays that observation separately from the later prediction.
4. The system does not silently overwrite the earlier result.
5. The page shows when the last observation was obtained and whether it is now stale.

**Acceptance signal:** A user or researcher can compare forecasts over time without losing the provenance of past results.

## Journey D — Authorized PNR lookup

This journey is disabled until an approved provider and data-retention policy are in place.

1. User sees what information the lookup will access and what the application will retain.
2. User submits a PNR through a secure form.
3. Backend validates access, provider configuration and rate limits.
4. The adapter fetches only permitted fields and validates the response.
5. The server avoids logging the raw PNR and uses a random tracking identifier in user-facing URLs.
6. The UI shows the source timestamp and any provider limitations.
7. Retention expiry and deletion follow the documented policy.

**Acceptance signal:** The integration cannot silently fall back to unapproved scraping or treat a stale response as live.

## Journey E — Insufficient evidence

1. The user submits a valid input, but the model has no validated coverage for that status/quota/horizon.
2. The system explains which input combination is unsupported or which evidence is missing.
3. The UI avoids a probability dial or fake confidence badge.
4. The user can correct inputs or use the tool without a numeric estimate.

**Acceptance signal:** Missing data is an explicit outcome, not a fake low or high probability.

## Journey F — Researcher reproduces a result

1. Researcher identifies the result's experiment ID, model version, dataset version and code revision.
2. Research docs identify data provenance, split dates, target definition, features and exclusion rules.
3. The result can be regenerated without requiring access to private passenger data in Git.
4. Aggregate metrics include sample counts and uncertainty.
5. The report documents failed comparisons and known limitations.

**Acceptance signal:** Performance claims can be audited without exposing raw PNRs or passenger identity.
