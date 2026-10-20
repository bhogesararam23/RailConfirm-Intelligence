# Security and privacy baseline

Status: policy draft for design and implementation.

## Data minimization

The predictor does not require passenger names. Collect only the journey, ticket status and other fields necessary for a documented purpose. Treat PNRs and combinations of travel dates/routes as sensitive linkable data even if names are absent.

## PNR handling

Before live tracking is enabled:
- Verify the source's authorization, contract and permitted purposes.
- Explain to users what is fetched and what is stored.
- Encrypt retained identifiers and restrict access.
- Keep raw PNRs out of URLs, browser analytics, logs, traces and error reports.
- Prefer an internal random tracking ID for application routes.
- Set a retention period and deletion behavior.
- Define who can access the data and how access is audited.
- Confirm whether provider output may be persisted or used for model training.

## Secrets

- Never commit API keys, access tokens, database URLs with credentials or private provider responses.
- Use environment variables locally and a secrets manager in deployment.
- Keep `.env.example` value-free.
- Rotate exposed credentials and invalidate them immediately.
- Use least-privilege credentials and separate development from production.

## External inputs

Validate train identifiers, dates, statuses, provider responses and event data. Bound payload sizes, retries and timeouts. Treat external news text and provider fields as untrusted data. Do not execute instructions contained in retrieved content.

## Logging and observability

Log operational identifiers and errors only when necessary. Redact PNRs, tokens, passenger data and provider payloads. Review telemetry before adding third-party analytics.

## Data retention and deletion

Define retention by data category: temporary request, user tracking record, de-identified observation, research feature table, verified outcome and operational log. An expired ticket should not remain identifiable indefinitely by default. A derived research record may only be retained if the source terms and applicable obligations permit it and re-identification risk has been considered.

## Research exports

Research datasets should be de-identified and access-controlled. Remove raw PNRs and passenger names. Preserve source IDs, sampling methodology and transformation version without exposing credentials or private data. Small subgroup metrics may also reveal information and should be aggregated appropriately.

## Incident response

If a credential, PNR or private provider output is accidentally committed:
1. Revoke/rotate the credential or disable access as appropriate.
2. Remove the sensitive content from active files and stop further distribution.
3. Assess repository history and downstream copies; deleting the latest file alone does not erase history.
4. Follow relevant provider and legal notification requirements.
5. Record the incident and corrective action without repeating the secret.

## Release checklist

- [ ] No secrets or real PNRs in repository.
- [ ] Input validation and rate limits are in place.
- [ ] Tracking uses an approved provider and documented purpose.
- [ ] Retention and deletion are implemented and tested.
- [ ] Logs and monitoring are redacted.
- [ ] Public copy identifies predictions as estimates.
- [ ] Unsupported or stale data can trigger an abstention response.
