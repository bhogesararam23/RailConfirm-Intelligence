# Contributing

Thanks for taking an interest in RailConfirm Intelligence. The project is still in its research and documentation phase, so data quality, reproducibility and honest reporting matter as much as application code.

## Before starting

1. Read the [README](README.md), [agent operating guide](AGENTS.md), and relevant documentation under `docs/`.
2. Check the existing ADRs before proposing a different architecture or policy.
3. Search issues and current work to avoid duplicating effort.
4. Confirm the licence and permitted use of any dataset, library, API or external material you plan to introduce.

## What is useful right now

- Dataset discovery with a clear source, schema, licence and access assessment.
- Status/quota normalization and data-contract tests.
- Leakage-resistant backtesting and probability calibration.
- Baseline models and reproducible evaluation.
- Privacy, provider-integration and data-retention design.
- Documentation that makes limitations explicit.

## Changes

- Keep each change focused and reviewable.
- Add or update tests for changed behavior.
- Update the affected specification, changelog and development log.
- Create an ADR for a material architectural, modelling, privacy, data, security, deployment or licensing decision.
- Do not bundle real personal data, PNRs, credentials or unlicensed datasets into examples.
- Clearly label synthetic fixtures and illustrative values.
- Do not add a dependency without a reason.
- Do not report evaluations without recording the dataset, split, configuration, metric and reproducible command.

## Commit messages

Use a short, specific message. Conventional Commit prefixes are welcome:

- `docs: define historical data requirements`
- `feat: add reservation status normalization`
- `fix: preserve original waitlist status`
- `test: cover mixed RAC and waitlist groups`
- `research: add chronological baseline evaluation`

Do not create extra commits solely to make the commit count larger. Each commit should represent a meaningful, reviewable step.

## Pull requests

A useful pull request explains:
- What changed and why.
- How the change was tested.
- The relevant ADR, issue or research question.
- Data provenance and licence implications, if applicable.
- Known limitations and follow-up work.

Do not claim a feature is complete when it is a stub, mock, unvalidated model or UI-only implementation.

## Research integrity

Predictions are probabilistic estimates. Report calibration and proper scoring rules as well as classification metrics. Keep final test data separate from model selection. Do not leak information from later status observations into earlier prediction snapshots. Failed experiments and limitations should remain visible in the research record.

## Code of conduct

Be respectful and constructive. Critique ideas and evidence, not people. Do not share private ticket information, credentials or personal data in issues or pull requests.
