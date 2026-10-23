# Dataset intake checklist

Use this checklist whenever an agent or maintainer proposes a data file for RailConfirm Intelligence. A downloaded file is not automatically an approved training dataset.

## 1. Identify the source

- [ ] Dataset name and publisher/owner are recorded.
- [ ] Canonical source URL or delivery reference is recorded.
- [ ] Retrieval/receipt date is recorded.
- [ ] Applicable licence, terms or written permission are reviewed.
- [ ] Permitted use has been checked separately for local inspection, storage, transformation, ML training, publication of aggregate metrics and commercial use.
- [ ] Attribution and redistribution conditions are recorded.
- [ ] The data is not obtained through a restricted endpoint or access-control bypass.

## 2. Check privacy and sensitivity

- [ ] File is checked for raw PNRs, passenger names, contact details and other identifiers.
- [ ] Any personal or linkable data has a valid use basis and documented purpose before processing.
- [ ] Unnecessary fields are removed or separated before use.
- [ ] Raw sensitive files are not copied into Git, issues, logs or public agent context.
- [ ] Retention and deletion requirements are documented.
- [ ] If unexpected identifiable data is present, stop and quarantine the file until reviewed.

## 3. Describe the contents

- [ ] File format and schema are documented.
- [ ] Row/record count and date range are calculated.
- [ ] Train, journey date, class, quota and route segment coverage are summarized where present.
- [ ] Raw status codes are counted without losing their original strings.
- [ ] Status-observation timestamps and their meaning are understood.
- [ ] Final outcome labels and their verification basis are understood.
- [ ] Missing, duplicate, contradictory and censored records are quantified.
- [ ] The dataset's known collection and selection biases are documented.

## 4. Integrity and reproducibility

- [ ] File checksum is generated.
- [ ] Transformation scripts and schema versions are recorded.
- [ ] Each dropped/excluded row has a reason category.
- [ ] Raw and transformed data are distinguishable.
- [ ] Synthetic fixtures have a persistent synthetic marker.
- [ ] No synthetic records enter an empirical test set or performance report.
- [ ] Import and quality reports can be reproduced.

## 5. Leakage review

- [ ] Features can be reconstructed using only information available at prediction time.
- [ ] Final outcomes are stored separately from input features.
- [ ] Source publication time, observation time and ingestion time are distinguished.
- [ ] Booking/journey snapshots can be kept in one data partition.
- [ ] Late-arriving information is not backdated into historical forecasts.
- [ ] Post-chart outcomes are not mixed with final-chart targets without a separate definition.

## 6. Approval decision

Record one of:
- **Approved for research/training:** rights, privacy, labels and quality allow the stated purpose.
- **Approved for metadata only:** the file can support schema/source analysis but not training.
- **Restricted:** use is limited to a stated purpose or environment.
- **Quarantined:** rights/privacy/label questions must be resolved.
- **Rejected:** the data cannot be used for the proposed purpose.

These map onto the manifest vocabulary in `docs/data/DATASET_MANIFEST_TEMPLATE.yaml`
(`status` and `decision.decision`: `candidate | approved | restricted | quarantined |
rejected`, plus `under_review`). "Approved for metadata only" is recorded as
`restricted` with the permitted purpose written into `decision.rationale` — there is
no separate `metadata_only` state, and inventing one would put the manifest out of
step with the template. `approved` requires `reviewed_by`, `reviewed_on` and a
rationale; the manifest model refuses to serialise the claim without them.

## What the tooling checks, and what it cannot

From `backend/`:

```bash
python -m railconfirm.data validate path/to/dataset.csv
python -m railconfirm.data manifest path/to/dataset.csv --dataset-id … --title … --retrieved-on YYYY-MM-DD
python -m railconfirm.data verify data/manifests/<id>.yaml path/to/dataset.csv
```

| Checklist item | Machine-checked? |
|---|---|
| Row/record count, date range, status and outcome distributions | Yes — `validate` reports counts and ranges |
| Raw status strings preserved while normalizing | Yes — parse keeps `raw`, and unknown codes are rejected rather than coerced |
| Missing, duplicate, contradictory and censored records quantified | Yes — `null_counts`, `duplicate_rows`, `contradictory_label_groups`, `censored_label_rows`, per-reason rejection counts |
| Timestamp semantics and ordering | Partly — ISO calendar dates and `observation_date <= journey_date` are enforced; sub-daily observation time is not in the row contract yet |
| Features reconstructed from as-of information | Yes for the implemented split — `asof_statuses()` is the single as-of rule (`current_status`, else `initial_status`), `extract_features` refuses label columns and `chronological_split` allocates whole dates |
| Rejected rows kept out of fitting and scoring | Yes — `assess_dataset()` returns only rows that passed, and the training gate refuses a file with any eligibility finding unless the rows are labelled synthetic and the caller opted in |
| Booking snapshots in one partition | Yes when `booking_group_id` is present; without it the validator warns that group integrity cannot be checked |
| File checksum, size, row-count consistency | Yes — `verify` rehashes and **recounts** instead of trusting the manifest |
| Intake reproducibility | Yes — manifest output is deterministic; the same inputs give the same digest |
| Licence, permitted use, attribution, commercial rights | **No.** Recorded in the manifest and source register, decided by a person |
| Whether unexpected identifiers exist beyond the PNR-shaped scan | **No.** The repository hygiene scan is accident prevention, not a privacy review |
| Collection and selection bias | **No.** Must be written up by the reviewer |

A passing `validate` means the file is technically eligible to be attempted; it does
not mean approved, and no exit code encodes approval.

Training enforces the same verdict: `load_approved_dataset()` refuses a file with any
eligibility finding and passes on only the rows the validator kept, so a rejected row
cannot reach a cohort count or a score. The single exception is the labelled synthetic
pipeline path, which needs `is_synthetic` rows *and* an explicit
`--allow-synthetic-for-testing`, and whose artifact records the relaxation (ADR-0013).

## Required intake report

Save a report containing:
- source and terms;
- date received;
- file checksum and schema version;
- row counts, date range and coverage;
- label and status semantics;
- cleaning/exclusion summary;
- privacy and rights decision;
- caveats and responsible reviewer;
- recommended experiments and the data limitations.

An agent's summary does not replace this record. Unverified claims must be marked as open questions.
