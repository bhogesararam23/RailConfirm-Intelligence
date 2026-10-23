# ADR-0012: Opt-in local prediction history with a retention floor

- **Status:** Accepted
- **Date:** 2026-10-23
- **Decision owner:** Project maintainer
- **Related:** ADR-0005 (PNR privacy), ADR-0007 (local-first), ADR-0009 (artifact trust), `docs/SECURITY_AND_PRIVACY.md`, `backend/railconfirm/storage/`

## Context

Every prediction was ephemeral. A user who wanted to compare what the tool said
yesterday with what it says today had to keep their own screenshot, and the documented
route `/prediction/[id]` existed in `docs/technical/FRONTEND_GUIDE.md` with nothing
behind it. The directive's Milestone G asks for persistence and prediction history, and
the future label-feedback loop — "the chart said CNF, what did you predict?" — needs a
stored report to attach a label to.

Storing ticket data is also the one feature that can quietly break the product's privacy
claim. ADR-0005 says passenger names are never collected and PNR handling needs purpose,
short retention and redaction. A history table added as a convenience, always on, with no
deletion path, would contradict that while the on-page copy still said "nothing is stored".

## Decision

**Store reports, but only when two independent switches are on, and only for a bounded time.**

- **Two switches.** `RAILCONFIRM_PERSIST_PREDICTIONS` (default **false**) decides whether
  this server keeps history at all. The request field `persist` (default **false**) decides
  whether one report goes in. A caller asking to store against a server that keeps no
  history gets `stored: false` plus a limitation naming the reason — the response never
  implies a save that did not happen, and the storage failure never destroys the estimate.
- **What is stored:** the internal UUID prediction id, the full response the user was
  served (journey, target, observed and estimated statuses, model version, registry state,
  evidence coverage, limitations), and two bookkeeping columns, `recorded_at` and
  `expires_at`. **What is not stored:** passenger names (the domain model has no field for
  them, ADR-0005), PNRs, tokens, cookies, account identity, or any raw source response.
  `DENIED_KEYS` and a PNR-shaped value scan run before the write, so a future field that
  carries an identifier fails loudly here instead of silently accumulating.
- **Retention floor:** `prediction_retention_days` must be at least 1; a store configured
  with 0 is refused at construction. `purge_expired()` deletes past that window, and
  `get()` hides an expired row even before it is purged, because "delete when convenient"
  must not mean "still serve it meanwhile".
- **Reopening is by internal id only.** `GET /v1/predictions/{id}` answers a 10-digit
  PNR-shaped id with a refusal that says reports are reopened by the id the server
  returned. That endpoint must not become a ticket tracker by accident.
- **The stored report is the report.** Reopening returns the stored payload; nothing is
  recomputed, so the numbers carry the model version and registry state they were produced
  with. A reopened estimate is evidence about what was said then, not about what is known now.
- **SQLite, one file, no server.** `data/storage/predictions.sqlite3`, Git-ignored along
  with `*.sqlite3*`. One connection guarded by a lock and opened with
  `check_same_thread=False`: FastAPI serves routes on threads other than the one that
  opened the store, and the first version of this code raised in exactly that path.
- **Timestamps are stored as fixed-shape UTC text.** Retention is evaluated by comparing
  those strings in SQL, so mixed offsets would silently order them wrongly; writes are
  normalised to `…+00:00` at second precision, and a row whose text is naive, or whose
  expiry precedes its recording, is refused at read rather than guessed at.
- **The database is the record, not the process.** Verified by restarting the server and
  reopening a report written by the previous process.

## Alternatives considered

- **Keep predictions in the browser (localStorage or IndexedDB).** Rejected as the primary
  answer: it cannot serve `/prediction/[id]` on a fresh device or a different browser, and
  the API contract already issues a server-side id. It remains a reasonable extra later.
- **Store by default with an opt-out.** Rejected: the on-page claim would have to become
  "we store your ticket data unless you change a setting you will not find", which is the
  opposite of the project's privacy posture.
- **PostgreSQL now, as ADR-0002 sketched.** Rejected for this stage: nothing here needs a
  server, a local-first tool should not require one, and adding a database service would
  put credentials and a network dependency into a build that ADR-0007 keeps provider-free.
  The store is behind a narrow interface, so a later engine swap is a new ADR, not a rewrite.
- **Accept a PNR as the lookup key.** Rejected: it would turn a research tool's history
  endpoint into a live ticket lookup and put reservation identifiers in URLs and logs.
- **Let `recorded_at` have to be after `prediction_at`.** Tried, and removed after the
  running app rejected every ordinary save: the form defaults the as-of moment to 24 hours
  ahead, so a future `prediction_at` is a legitimate request. Retention runs from the save.
- **Encrypt the SQLite file (SQLCipher).** Deferred: it adds a native dependency and key
  management problem for a local file that already sits inside the user's own account
  boundary. Revisit if history is ever enabled by default or exposed beyond one machine.

## Consequences

- `/prediction/[id]` exists and shows the report as served, with its retention deadline.
- Health reports `prediction_history` — enabled, retention days, stored count — so an
  operator can see the state without opening the file, and a page can stop offering to
  save when saving is impossible.
- Unmatched routes and wrong methods now answer with the documented error envelope instead
  of Starlette's `{"detail": …}`, so "every error is an envelope" is actually true.
- New obligations: anyone enabling history owns that file. Deleting it deletes the history;
  there is no per-row delete endpoint yet, and no authentication, so this stays a
  single-operator local feature. Publishing a stored report means publishing ticket data.
- A stored report is not evidence of accuracy. The label-feedback loop that would make
  history scientifically useful still needs its own consent, retention and bias design —
  that is the roadmap's user-contributed-observations row, not this one.

## Validation

- 26 storage tests and 12 history-over-HTTP tests, including: nothing stored unless asked;
  a save refused by the store still delivers the estimate with the reason in `limitations`;
  a reopened report equals what was served; PNR-shaped and unknown ids are refused with
  distinct codes; an expired id stops resolving; a second process on the same file reopens
  the first process's report; concurrent writes from six threads lose nothing; and a
  tampered row (future schema version, corrupt JSON, naive or inverted timestamp) is
  refused rather than interpreted.
- Backend suite 502 tests at 95.91% branch coverage; frontend 93 tests; `ruff`, `mypy`,
  `tsc` and `next lint` clean.
- Run against the real servers: `uvicorn` on `127.0.0.1:8033` with
  `RAILCONFIRM_PERSIST_PREDICTIONS=true` and `next dev` on `localhost:3123`. Submitting with
  the box ticked produced `stored: true` and the banner "Kept on this machine. Reopen it
  later at this report — retrievable until 30 Oct 2026, 09:20 IST"; `/prediction/<id>`
  rendered the stored report; an invented id rendered "Report not available" with the
  never-stored-or-aged-out wording and the request id. The unrouted-path envelope fix came
  from observing `{"detail":"Not Found"}` in this flow.
- CI must be observed green on the pushed commit; the result is recorded in
  `docs/DEVELOPMENT_LOG.md`, not assumed here.
