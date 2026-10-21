# Local data workspace

This directory contains documentation and safe manifests for project datasets. It must not become a place to publish raw ticket data by default.

## Current policy

The application and its tests must run without third-party runtime APIs. Data may be discovered and prepared by a research/coding agent, or supplied as a file by the project maintainer, but it is not approved for model training until its source, terms, privacy, labels and quality have been reviewed.

## Layout

- manifests/ — metadata and checksums that are safe to publish.
- sample/ — only tiny, licence-compatible public samples or clearly synthetic fixtures.
- raw/ — local-only source files; ignored by Git.
- interim/ — local-only intermediate transformations; ignored by Git.
- processed/ — approved local research datasets; do not commit unless explicitly reviewed.
- private/ — sensitive or restricted local data; never publish.

The ignored paths are an accident-prevention measure, not a permission to store data without a valid basis or to assume sensitive files are safe.

## Intake steps

1. Read docs/data/DATASET_INTAKE_CHECKLIST.md.
2. Record the source in docs/data/SOURCE_REGISTER.md.
3. Create a manifest using docs/data/DATASET_MANIFEST_TEMPLATE.yaml.
4. Validate the file schema, timestamps, labels, missingness, duplicates and coverage.
5. Mark the dataset approved, restricted, quarantined or rejected.
6. Keep a reproducible transformation script and quality report.
7. Confirm synthetic fixtures cannot flow into empirical training/evaluation.

Do not commit raw PNRs, passenger names, credentials or private provider responses. If a dataset's licence or permitted use is unclear, do not use it for training until the question is resolved.
