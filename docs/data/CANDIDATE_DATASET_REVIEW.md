# Candidate dataset review — 2026-10-23, second pass 2026-10-30

Records what was actually looked for, what was found, and why training is still blocked.
The 2026-10-23 pass reviewed public *catalogue pages* only: no file was downloaded, opened
or ingested, no manifest was generated, and no dataset was approved. The 2026-10-30 pass
below opened one candidate file outside the product runtime and says so, with what that
did and did not establish. Approval is a named human decision
(`docs/data/DATASET_INTAKE_CHECKLIST.md`), and nothing in this document makes one.

## What the product needs from a dataset

The model target is the final chart status of a reservation. A usable row therefore needs
all of:

1. the **status at the prediction moment** (initial booked status, e.g. `GNWL/27`);
2. the **final chart outcome label** for that same reservation (`CNF`, `RAC`, `WL` …);
3. a **journey date** and an **observation/as-of time**, so the split is chronological and
   leakage-free;
4. **class and quota**, since the baseline conditions on `(CLASS, QUOTA, STATUS)`;
5. a licence that permits storage **and** model training.

Conditions 1 and 2 together are the hard part. A dataset that only says "confirmed:
yes/no" cannot support the CNF / RAC / WL distinction ADR-0003 requires, and a dataset of
timetables or prices has no reservation outcome at all.

## Candidates inspected

| Candidate | Publisher / uploader | Checked | Licence as stated on the page | Contents | Outcome labels? | Verdict |
|---|---|---|---|---|---|---|
| [`aaryananil/indian-railway-ticket-confirmation`](https://www.kaggle.com/datasets/aaryananil/indian-railway-ticket-confirmation) | Aaryan Anil (Kaggle) | 2026-10-23 | `MIT` | ~903,874 bytes; pitched as predicting whether waitlisted tickets get confirmed | Unusable | **Rejected.** The page states: *"This dataset is synthetically generated and does not represent real data."* An MIT licence lets us use it; the generator's absence makes it worthless as evidence. We already maintain labelled synthetic fixtures for tests, so it adds nothing |
| [`bhavyarajdev/indian-railways-schedule-prices-availability-data`](https://www.kaggle.com/datasets/bhavyarajdev/indian-railways-schedule-prices-availability-data) | Bhavya Rajdev (Kaggle) | 2026-10-23 | `Apache 2.0` | ~7,026,565 bytes (zip); schedules, fares, availability; page says it was collected by *"web scraping techniques"* from the IRCTC website in October 2023 | No — availability snapshots, not chart results | **Rejected for training.** Wrong content (no per-reservation final-chart label), and provenance rests on whether the uploader's bulk collection was permitted by IRCTC terms, which this repository cannot verify. AGENTS.md treats unclear rights as disqualifying until they are clear |
| [`sripaadsrinivasan/indian-railways-dataset`](https://www.kaggle.com/datasets/sripaadsrinivasan/indian-railways-dataset) | Sripaad Srinivasan (Kaggle) | 2026-10-23 | `CC0: Public Domain` | ~17,170,333 bytes (zip); three JSON files — Stations, Trains, Schedules — credited to the `datameet` repository | No — reference metadata only | **Under review, reference metadata only.** Licence-relevant use would be station codes, train numbers and classes for validation and route coverage, never outcome modelling. The grant needs confirming at the origin (see next row) |
| [`datameet/railways`](https://github.com/datameet/railways) | DataMeet (GitHub) | 2026-10-23 | No licence file in the repository; its documentation cites a Creative Commons CC0 page | `stations.json`, `trains.json`, `schedules.json`, directly fetchable | No | **Under review.** This is the origin of the Kaggle mirror. Files are downloadable without credentials, so ingestion is technically trivial — but a citation of CC0 in prose is not a licence grant, and the intake checklist requires the licence and its permitted uses to be established. Settling it needs a maintainer action (an explicit dedication on the repository, or written confirmation from DataMeet) |
| [`Yogalakshmi4784/PNR-Prediction`](https://github.com/Yogalakshmi4784/PNR-Prediction) → Kaggle `railofy-challenge` | Yogalakshmi4784 (GitHub), data from Railofy's closed Kaggle competition | 2026-10-30 | Repo is **GPL-3.0** (code only; the file never mentions a dataset). No data licence published | 36,775 labelled rows + 3,847 unlabelled rows, 25 columns (1 id, 1 quota code, 17 scaled floats, 5 integer flags, 1 binary target); plus a `.pkl` model that was not loaded | Binary confirmed/not-confirmed only — no booked status, no chart label, no dates | **Rejected on content, quarantined on rights.** See the second-pass section below: the intake gate returns 0 valid rows out of 36,775, and the competition terms could not be read without a Kaggle session |

`https://www.data.gov.in/resource?…q=railway+reservation` returned **HTTP 403** to an
automated fetch from this environment, which has no portal API key. That says nothing about
the portal's holdings, only that the catalogue could not be read here. A browser session or
a `data.gov.in` API key is the next step for that source specifically; government railway
datasets generally publish aggregates (bookings per train, quota utilisation) rather than
per-reservation outcomes, so expectations should be modest and evidence-based.

## What this search establishes

- No dataset was found that carries **both** a reservation's booked status and its verified
  final-chart label with a licence permitting training. That is the reason the product
  abstains, and it is now documented with named sources rather than asserted.
- The visible "train ticket prediction" datasets split into two failure modes: synthetic
  data published as if it were railway history (the first row — exactly the trap
  AGENTS.md's synthetic-labelling rule exists for), and real-but-wrong-content data
  (scraped schedules and fares).
- Licence-clean **reference** data plausibly exists (rows 3 and 4). Ingesting it would
  improve station-code and train validation and route coverage reporting, and would not
  change the abstention behaviour at all. It is a separate, smaller milestone from
  training.
- A **third** failure mode showed up in the 2026-10-30 pass below: data whose reservation
  semantics were destroyed before publication. A competition matrix of scaled floats can
  carry a real label and still be unusable — it has no date, no status and no position to
  validate against a contract, so it fails on content regardless of its terms.

## Second pass, 2026-10-30 — `Yogalakshmi4784/PNR-Prediction` and the Railofy competition

This candidate was named for review because its README points at a competition dataset
rather than inventing one: `https://github.com/Yogalakshmi4784/PNR-Prediction`, "PNR
Prediction - Indian Railways", whose README states *"Dataset was collected from Kaggle: …
https://www.kaggle.com/competitions/railofy-challenge/data"*. Everything below was read
from the repository itself through the GitHub API on 2026-10-30, plus one local inspection
of the CSV named in it. Nothing was added to this repository.

### What the repository is

| Observed | Value |
|---|---|
| Created / last pushed | 2024-08-09 / 2024-08-09 (same day), default branch `main`, 1 star, issues enabled, not archived |
| Licence file | `LICENSE`, 35,149 bytes, verbatim **GPL-3.0**. The word "dataset" appears **0 times** in it |
| Contents (10 blobs, 18.8 MB) | `Railofy_training_data_for_model.csv` 7,981,954 B; `Railofy_testing_data_for_model.csv` 830,193 B; `PNR_Confirmation.pkl` 5,403,663 B; `Indian_Railway_PNR_Confirmation_Prediction.ipynb` 616,951 B; `sweetviz_report.html` 2,096,105 B; `Final Presentation.pptx`; `app (2).py`; `index.html`; `README.md`; `LICENSE` |
| Metrics the README reports | "Best Model: K-Nearest Neighbors Classifier. F1 score .872, Matthews Correlation Coefficient .815", plus a list of 12 "key indicators" and a Flask `/predict` deployment note |
| What the README does **not** state | the train/validation/test split, whether it was chronological, a baseline, class balance, calibration, or any licence for the CSVs |

A single-day repository of competition work is not a maintained source, and it publishes no
data licence of its own. **A code licence is not a data licence**: GPL-3.0 governs the
notebook and `app (2).py`, says nothing about the CSVs, and is copyleft, so nothing in that
code may be copied into this Apache-2.0 project without consequences for the whole.
Separately, the fact that competition CSVs are sitting in a public third-party repository is
itself a redistribution by someone who is not the rights holder. It cannot be read as
permission here.

### What the file actually holds

The title promises PNR prediction; the file carries no status, no journey and no PNR — its
identifier column is 11 digits, not a ten-digit PNR, and is not even unique. Header of the
training file:

```text
pk,QT,GRCA,CCA,JD,ODD,JS,ODS,SL,NDTD,CURP,GROP,CANP,SBRA,SCRA,GRA,CURA,RPW,CUCA,CAR,BKT_2,CL_1,CL_2,CL_3,target
```

Measured on the copy, read-only, outside the product runtime (36,775 data rows; the "testing"
file is the same 25 columns **without** `target`, 3,847 rows):

- **Every feature is already a number in someone else's space.** Of the 25 columns, one is
  `pk`, one is `QT`, five are integer flags (`SL`, `BKT_2`, `CL_1`–`CL_3`), one is `target`,
  and the remaining **17 are `float64`, 13 of which fall outside `[0, 1]`** (observed range
  includes `1.9994` and `-0.0076`). `JD`,
  which the README's own glossary calls *Journey Date*, is a float. There is **no date,
  no station, no train number, no class code and no status string anywhere in the file**.
- **`QT` is the only textual column**, with exactly three values: `GN`, `PQ`, `RL`. The
  status families this product distinguishes (`GNWL`, `RLWL`, `PQWL`, `TQWL`, `RQWL`, `DPWL`,
  plus `RAC` and `CNF`) are not present and cannot be recovered from a scaled number.
- **`SL` is one bit** (`0`/`1`), `BKT_2` and `CL_1`–`CL_3` are dummies, so travel class is not
  a code either.
- **`target` is binary.** 11,578 positives in 36,775 rows, base rate **0.3148**. A binary
  "confirmed / not confirmed" label cannot support the CNF-vs-RAC-vs-WL distinction ADR-0003
  requires, cannot feed the five-class distribution the response schema carries, and cannot
  be compared with the prevalence baseline the evaluator draws from a training window.
- **`pk` is not a booking key.** 11 digits, not monotonic, and three values occur twice —
  each pair with *different* `QT` values (`RL` and `GN` on the same `pk`). Labels did not
  conflict, so this repository's contradictory-label rule would not fire, but a group key
  that is shared across quotas cannot establish a booking's dependent passengers.
- **No missing values at all** (0 rows with any NaN). Real reservation extracts are not
  complete in that way; this is a processed matrix.
- **Univariate association with the label is weak**: the largest absolute correlation is
  `GROP` 0.293, then `CURP` 0.250, `RPW` 0.220, `NDTD` −0.206, `CANP` 0.187, `CUCA` 0.164,
  `GRCA` −0.128. `CCA` is not in the top eight. The README's reported MCC of 0.815 is not
  explained by these signals, and with no split described it cannot be checked — which is
  the reason not to treat those figures as reproducible.
- The README's glossary describes `CCA` as *"the number of seats available after the chart has
  been prepared"* and `RPW` as *"a calculated weight indicating the likelihood of reservation
  confirmation"*. Taken at face value, an input set that contains a post-chart quantity and a
  pre-computed confirmation weight is not a booking-time feature set. The measured
  correlations do not show `CCA` dominating, so this is recorded as a question about the
  glossary's accuracy — the transformation is undocumented — not as a proven leak.

### The product's own gate was run against it

`python -m railconfirm.data validate <copy of the training CSV>` (executed on the file
outside the repository, then deleted): **36,775 rows, 0 valid, exit code 1**,

```text
missing required columns: train_number, journey_date, class_code, quota_code,
                          initial_status, final_chart_status, observation_date
absent optional columns : booking_group_id, passenger_record_id, current_status,
                          source_id, verification_method, censoring_reason, is_synthetic
```

That is a *contract* verdict, not a rights verdict, and it is the decisive one: even under
ideal terms the file cannot produce one valid row. Without `journey_date` and
`observation_date` there is no chronological split (ADR-0014), no frozen-artifact decay
horizon (ADR-0018), no one-clear-day eligible horizon (ADR-0026) and no as-of cohort key
(ADR-0013). Without a status string there is nothing for `asof_statuses()` to read, so
neither estimator can be fitted or scored. No manifest was generated; a manifest would
imply a candidate worth deciding on.

### Rights: unresolved, and the precise blocker

The question the directive asked — may this data be stored, transformed, used for research
and model training, and used for this project's intended distribution or commercial purposes
— **cannot be answered from primary evidence in this environment**, and no approval is being
invented in its place:

- `https://www.kaggle.com/competitions/railofy-challenge/rules`, `/data` and
  `/overview/citation` are client-rendered: an automated fetch returns only the page title
  ("Indian Railways Challenge | Kaggle") and no rules text, in this environment and in the
  Wayback attempt.
- `https://www.kaggle.com/api/v1/competitions/list?search=railofy` returns **HTTP 401** —
  the Kaggle API requires an account. This environment has no Kaggle credentials.
- What the search snippets do establish: the competition is titled "Indian Railways
  Challenge", hosted by Railofy ("a travel tech start-up"), described as "a Classification
  problem to predict confirmation of your train journey in India", and its listed status is
  **"Late Submission"**, i.e. closed. Whether its terms permitted any use beyond the
  competition, and what Railofy's own terms said about the PNR records it supplied, are
  unknown here.
- The dataset's origin is a private company's PNR-tracking service, so the upstream chain —
  IRCTC terms, passenger data, whatever Railofy committed to its own users — is a second
  question behind Kaggle's competition terms, and neither is answerable from a README.

**Status: quarantined.** Not rejected on rights, because the rights text was not readable;
rejected on content, which needed no rights to establish. Reading the competition rules
requires a logged-in Kaggle session, which is a maintainer action.

### What would change this verdict

Nothing about this file. Its useful information content is a *column glossary* and a
reminder of what the transformation destroyed. The source worth pursuing is Railofy's own
record set — or any provider of it — published with dates, statuses, positions and explicit
training and publication terms. If that ever appears, this repository's intake gate is
already the instrument that decides.

## Unblocking training: what would have to be true

1. A source with per-reservation records: booked status and position, class, quota,
   journey date, and the final chart result for the same berth — with an as-of timestamp.
2. Terms that permit local storage, transformation, model training, and publication of
   aggregate metrics.
3. No raw PNRs or passenger details, or a documented redaction step before storage.
4. Enough rows and enough distinct journey dates for `chronological_split` to hold a real
   future period back; the splitter reports ineligibility rather than faking one.

The realistic paths to (1) are a licensed data agreement with a railway/CRIS source, or a
prospective user-contributed observation collection with explicit consent — the second row
of `SOURCE_REGISTER.md`. Neither is available to an automated agent, and pretending
otherwise would be the fabrication this repository is built to avoid.

## Method, so the next session does not repeat it

Web search on 2026-10-23 for waitlist/RAC confirmation datasets, then page fetches of each
hit to read the description, metadata panel and licence field directly. Sizes, dates and
quoted licence names above are copied from those panels. Kaggle downloads require an
account; this environment has no Kaggle credentials, so no file was retrieved even for the
rejected candidates. `github.com` raw files need no credentials, and deliberately were not
fetched while the rights question is open.

### Method, 2026-10-30 pass

That last sentence held until this pass, and the reason for revisiting it was specific: the
review asked whether a *code* licence establishes *data* rights, and that question is only
answerable by looking at what the repository actually distributes. So:

- repository metadata, the file listing with byte sizes, and the `LICENSE` text were read
  through the GitHub API (no clone, no archive);
- the two CSVs named in the README were read **once, outside the product runtime**, into a
  tool cache that is not part of this repository, to establish the header, the column types
  and the summary figures quoted above. `python -m railconfirm.data validate` was then run
  against a temporary copy of that cache file under `%TEMP%`. **No pickle was loaded** —
  `PNR_Confirmation.pkl` is a fitted model of unknown provenance in a format that executes
  code on load, and `railconfirm/data/loader.py` refuses `.pkl` by design. `sweetviz_report.html`
  (2 MB, an auto-generated EDA report that would embed data excerpts) and the notebook were
  **not opened**;
- nothing entered `data/`, `local/`, `backend/tests/fixtures/`, a manifest or a training
  run; the repository contains no byte of this dataset;
- the copies were deleted at the end of the review, on the same short-retention reasoning
  the storage layer uses. Re-deriving the figures above means fetching again — which is why
  every number quoted here is stated with its source and its date.

A successful download is not permission, and this pass changes no approval state. Kaggle's
competition pages remained unreadable without a session, so the rights question is recorded
as open rather than answered.
