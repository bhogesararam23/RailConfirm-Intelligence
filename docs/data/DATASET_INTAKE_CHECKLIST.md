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
