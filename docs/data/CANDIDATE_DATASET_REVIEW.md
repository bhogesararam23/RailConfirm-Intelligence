# Candidate dataset review — 2026-10-23

Records what was actually looked for, what was found, and why training is still blocked.
This is a review of public *catalogue pages*; **no file was downloaded, opened or
ingested**, no manifest was generated, and no dataset was approved. Approval is a named
human decision (`docs/data/DATASET_INTAKE_CHECKLIST.md`), and nothing here makes one.

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
