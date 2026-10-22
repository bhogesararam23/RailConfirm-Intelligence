# Local data workspace

This directory contains documentation and safe manifests for project datasets. It must not become a place to publish raw ticket data by default.

## Current policy

The application and its tests must run without third-party runtime APIs. Data may be discovered and prepared by a research/coding agent, or supplied as a file by the project maintainer, but it is not approved for model training until its source, terms, privacy, labels and quality have been reviewed.

## Layout

Only what exists is listed. Directories are created when first needed, not pre-made as placeholders.

- `manifests/` — tracked here: metadata and checksums that are safe to publish.
- `data/processed/` — approved local research datasets. Does not exist yet; Git-ignored.
- `data/raw/`, `data/interim/`, `data/private/` — local-only staging for a candidate under review. Git-ignored, created on demand, never committed.
- `models/` — Git-ignored location for model artifacts. Nothing is there yet.

`data/sample/` was listed previously and does not exist; the clearly-labelled synthetic fixtures live in `backend/tests/fixtures/`.

The ignored paths are an accident-prevention measure, not a permission to store data without a valid basis or to assume sensitive files are safe.

## Tooling

From `backend/`:

```bash
python -m railconfirm.data validate path/to/dataset.csv      # quality report; exit 1 if not eligible
python -m railconfirm.data manifest path/to/dataset.csv \
  --dataset-id my-set --title "My set" --retrieved-on 2026-10-18
python -m railconfirm.data verify ../data/manifests/my-set.yaml path/to/dataset.csv
```

`manifest` requires `--retrieved-on` because a manifest dated by the clock cannot
be regenerated identically, and "when did we receive this" is a fact about the
source record. Output is deterministic: the same inputs produce the same bytes and
the same digest. `verify` re-reads the dataset and recounts rows and duplicates
rather than trusting what the manifest says.

## Intake steps

1. Read docs/data/DATASET_INTAKE_CHECKLIST.md.
2. Record the source in docs/data/SOURCE_REGISTER.md.
3. Create a manifest using docs/data/DATASET_MANIFEST_TEMPLATE.yaml.
4. Validate the file schema, timestamps, labels, missingness, duplicates and coverage.
5. Mark the dataset approved, restricted, quarantined or rejected.
6. Keep a reproducible transformation script and quality report.
7. Confirm synthetic fixtures cannot flow into empirical training/evaluation.

Step 5 is a human decision. `validate` reports structural validity and technical
eligibility; it cannot and does not set approval, and the manifest model refuses to
serialise `status: approved` without a named reviewer, a date and a written
rationale.

Do not commit raw PNRs, passenger names, credentials or private provider responses. If a dataset's licence or permitted use is unclear, do not use it for training until the question is resolved.
