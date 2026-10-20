# Definition of done

Use this checklist for meaningful feature work. Not every item applies to a docs-only change; mark non-applicable items explicitly rather than leaving ambiguity.

## Engineering
- [ ] Scope and acceptance criteria are clear.
- [ ] Implementation is reviewed against existing architecture and ADRs.
- [ ] Relevant tests are added or updated.
- [ ] Tests, formatters, linters and type checks were run where available.
- [ ] Failures and checks not run are documented.
- [ ] Dependencies have a documented reason.
- [ ] Errors, timeouts and unsupported cases are handled.

## Data and ML
- [ ] Source register and usage rights are clear.
- [ ] Schema and provenance are versioned.
- [ ] Target and prediction timestamp are explicit.
- [ ] No future information leaks into features.
- [ ] Booking/group snapshots are partitioned safely.
- [ ] Baseline comparison is included.
- [ ] Probability calibration and appropriate scoring rules are evaluated.
- [ ] Sample counts, uncertainty, coverage and subgroup limitations are reported.
- [ ] Synthetic records are excluded from claims about real-world performance.

## Privacy and security
- [ ] No credentials, real PNRs or passenger details are committed.
- [ ] New data collection has a stated purpose.
- [ ] Access, retention and deletion are defined.
- [ ] Logs and errors are redacted.
- [ ] External provider use conforms to verified permissions.

## Documentation and decisions
- [ ] Public-facing claims match implementation status.
- [ ] README/specifications are current.
- [ ] Changelog updated for meaningful changes.
- [ ] Development/session log updated at the session boundary.
- [ ] A material decision has a sequential ADR.
- [ ] Model card/evaluation report updated when model behavior changes.

## Release
- [ ] No unsupported accuracy claim.
- [ ] Prediction limitations are visible.
- [ ] Live tracking is enabled only with a verified provider.
- [ ] Rollback and failure behavior are understood.
