# ADR-0015: Listing kept reports and deleting one, with the list limited to metadata

- **Status:** Accepted
- **Date:** 2026-10-23
- **Decision owner:** Project maintainer
- **Amended by:** ADR-0040 — an expired row is still cleared, but DELETE answers 404 rather
  than confirming it; the store gains an availability-gated delete.
- **Related:** ADR-0005 (PNR privacy and retention), ADR-0012 (opt-in prediction history),
  `backend/railconfirm/storage/predictions.py`, `backend/railconfirm/api/v1/predictions.py`,
  `frontend/src/components/prediction/HistoryList.tsx`, `docs/SECURITY_AND_PRIVACY.md`,
  `docs/technical/STORAGE_MODEL.md`

## Context

ADR-0012 shipped history with two switches, a retention floor and a reopen route, and
named per-row deletion as follow-up work rather than permission to collect. The result was
a one-way door: a user who asked to keep a report could reopen it, but had no way to stop
keeping it before the window closed, other than deleting the database file — which also
destroys every other report, a fact no user should have to discover.

Listing was the other half of the same problem. A `report_url` is a UUID in a browser
history or a note; without a list, a user who kept several reports cannot find them, and a
page that says "you can delete what you kept" has to show what was kept first.

Both are privacy surfaces. A list of stored ticket predictions is exactly the kind of thing
that grows an unintended second use — a shared screen, a screenshot, a page someone left
open — and a delete route that answers differently for "yours" and "never existed" tells a
caller which ids this machine holds.

## Decision

**1. Deletion is immediate and hard; expiry stays a hide.**

`PredictionStore.delete(prediction_id)` removes the row. Expiry, as ADR-0012 defined it,
still hides rather than deletes — an aged-out row waits for a purge. The difference is who
asked: the retention window is the operator's rule, an explicit delete is the user's, and a
user request should not wait for a background process that this local-first build does not
run.

**2. The list carries ids, clocks and provenance, and nothing else.**

`GET /v1/predictions` returns `{reports: [{prediction_id, target, model_version,
recorded_at, retention_expires_at}], count, retention_days}`. No journey, no statuses, no
probabilities, no passenger rows. The reopen route exists precisely so that the report
itself is fetched deliberately, one at a time, by someone who chose to open it. Widening
this shape is a privacy change and needs its own decision, not a field added to a response
model.

**3. Absent, expired and already-deleted answer identically.**

`DELETE /v1/predictions/{id}` returns 204 when a row was removed and the same 404 body in
every other case — never stored, expired, deleted a minute ago, or a wrong id. A route that
distinguished them would confirm which ids this machine has held, which is exactly the
information a local endpoint should not hand out.

**4. A 204 has no body.**

Nothing is returned to read back: confirming a deletion by showing the deleted report would
contradict the thing that just happened. The frontend keeps the row out of the list and
says the copy is gone; the browser's own rendering of a page already open is stated as
browser memory, not stored data.

**5. `PRAGMA secure_delete = ON`, with its limit written down.**

SQLite then zeroes freed pages, so a deleted report is not left in the main database file
for a casual read. That is accident-proofing, not a cryptographic erase: the `-wal` side
file and any filesystem-level snapshot can still contain older bytes, and this build does
not claim otherwise. Retention and the existing denied-key/PNR-shaped-value refusal at the
write remain the primary controls.

**6. History-off answers 404 on the list route, not an empty list.**

"Nothing is kept" and "this server does not keep anything" are different facts for a page to
act on: the first invites the user to keep a report, the second tells them the switch is
off. The reopen route already made this distinction through `history_disabled`; the list
now makes the same one.

**7. Deletion needs a second click.**

Irreversible, and this product's users are not being asked to confirm a save. The list and
the reopened report both use Delete → Confirm delete (with a Keep it escape); the row stays
listed until the backend has answered, and a refused or failed delete says so and leaves the
report visible, because a delete that did not happen must never look like one that did.

**8. No new access boundary, stated plainly.**

These routes are unauthenticated, like every other route in the local-first build
(ADR-0007): whoever controls the machine or an allowed browser origin can list and delete
kept reports. The CORS allowlist limits which origins, and history stays off by default.
Enabling history for several users is what would force an authentication boundary, and that
is ADR-0012's recorded consequence, not a decision made here.

## Alternatives considered

- **Let expiry delete rows on read.** Rejected as ADR-0012 decided: hiding and removing are
  different promises, and deleting inside a read path makes the read's cost unpredictable.
- **Return report summaries with journey and probabilities so the list is more useful.**
  Rejected: that is the sensitive data, in a list, on screen, before anyone chose to open a
  report. A click on a link is a cheaper action than a leak.
- **Return 410 Gone for expired reports and 404 for unknown ones.** Rejected: a status code
  that says "this one existed here" is a disclosure.
- **Return a JSON body on success (`{deleted: true}`).** Rejected: 204 is the honest answer,
  and a body invites the client to render something about a report that no longer exists.
- **`VACUUM` after each delete.** Rejected for now: it rewrites the whole database on a
  request path, and `secure_delete` plus the retention floor already cover the realistic
  case. If a deployment needs file-level scrubbing, that belongs with an operator runbook
  and a measured cost.
- **Batch or "delete all" action.** Rejected: one tempting button that destroys every
  report is the failure mode this feature exists to avoid; the user can remove rows one at a
  time, and the file remains the operator's to manage.

## Consequences

- The history list is the only place a kept report is described without being opened, so its
  field set is now load-bearing: `StoredReportSummary` in the schemas, the matching
  `StoredReportSummary` / `StoredReportsResponse` types in `frontend/src/lib/types.ts`, and a
  contract test that pins both. Adding a field there is a privacy decision.
- `size` from `/v1/health` and the list count can differ for a moment: health counts rows,
  the list excludes those past retention. Both are correct about different things and the
  docs now say which is which.
- `purge_expired()` is still not scheduled anywhere. Rows past retention are hidden, listed
  nowhere and unreadable; they occupy disk until an operator purges them or a delete clears
  one. That is ADR-0012's position unchanged, restated here because deletion makes the
  difference visible.
- A deleted id can be kept again: there is no tombstone, so a later save for the same id
  writes a fresh row. Correct for a UUID, worth knowing if ids ever become derived.

## Validation

- `tests/storage/test_predictions.py` — `delete()` removes exactly the named row, returns
  False for absent/blank ids rather than raising, clears a hidden-but-expired row, and does
  not block a later save under the same id; `summaries()` is newest first with a stable
  tie-break, omits anything past retention, publishes the clocks and provenance, refuses a
  row whose expiry precedes its recording, and carries no payload — asserted by scanning the
  serialised list for probability and status keys; `PRAGMA secure_delete` is verified on the
  live connection.
- `tests/api/test_prediction_history.py` — empty list versus `history_disabled` 404; a listed
  report exposes only its five fields (a text scan of the response asserts no `p_cnf`,
  `current_status`, `train_number`, `passenger` or `limitations`); aged-out rows are listed no
  more than they are readable; delete answers 204 with an empty body, leaves nothing to
  reopen, and decrements the list; a second delete and an unknown id return byte-identical
  404 bodies; a PNR-shaped id gets the same answer on GET and DELETE; deleting one report
  leaves another readable; a contradictory row surfaces as `storage_unavailable` in the
  documented envelope.
- `frontend` — 11 `HistoryList` tests and 3 new `StoredPredictionReport` tests cover the
  loading, listed, empty, disabled, failed-and-retried states, the two-step confirmation
  (asserting the first click issues no DELETE), that a confirmed delete removes the row and a
  refused or network-failed delete does not, and that the empty state reports how many were
  removed this session. `npm test` → 113 passed; type-check, lint and build clean.
- Full backend run: commands and results are recorded in `docs/DEVELOPMENT_LOG.md`.
