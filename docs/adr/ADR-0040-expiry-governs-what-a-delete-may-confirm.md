# ADR-0040: Expiry governs what a delete may confirm

- **Status:** Accepted
- **Date:** 2026-10-31
- **Decision owner:** Project maintainers
- **Related:** ADR-0012 (opt-in prediction history and retention), ADR-0015 (history listing and per-row deletion; amended by this decision), ADR-0005 (PNR privacy)

## Context

ADR-0015 says two things that meet at an expired row still on disk:

1. deletion is immediate and hard, and an explicit request clears an aged-out row;
2. `DELETE /v1/predictions/{id}` returns 204 when a row was removed and the same 404 in
   every other case — never stored, expired, already deleted, or a wrong id.

`purge_expired()` is not scheduled anywhere, so expired rows routinely stay in the table.
The route called `PredictionStore.delete(id)` and turned its rowcount into 204/404. For a
row that was still present but past retention, the delete removed it and the route answered
**204** — confirming that this machine had held that id, while `GET` on the same id answered
404 and the list omitted it. The route's own description, ADR-0015 decision 3 and
`docs/architecture/API_CONTRACT.md` all promise 404 for expired. The implementation
contradicted all three, and the contradiction was reachable without touching internals: let
retention pass, then delete.

The two ADR-0015 statements are not actually in conflict once "removed" is read as
"a kept report was removed". An expired row is not a kept report; clearing it is
housekeeping, not the deletion the caller asked for.

## Decision

1. **Availability decides the answer, not rowcount.** The route first deletes only if the
   report is still inside retention, using a single SQL statement
   (`DELETE … WHERE prediction_id = ? AND expires_at > ?`) so a row cannot expire between
   the decision and the removal. A live report answers 204; everything else answers the
   same 404 body.
2. **An expired row is still cleared, without confirmation.** When the live delete removes
   nothing, the route calls the unconditional `delete()` as housekeeping and returns 404.
   This preserves ADR-0015's intent that an explicit request should not wait for a purge
   that never runs, while removing the information leak.
3. **The store keeps both operations, with names that say what they mean.**
   `delete_live(id, now=…)` is availability-gated and atomic; `delete(id)` is the
   unconditional hard delete used for housekeeping and by callers that own the row's
   lifetime. `purge_expired(now=…)` is unchanged.
4. **A naive clock is refused before anything is deleted.** `delete_live` validates
   offset-awareness for the same reason the rest of the store does: an expiry comparison
   against a naive time is a guess about which clock wrote it.
5. **Deletion does not hydrate the payload.** A corrupt row inside retention is still a kept
   row, so the conditional delete removes its bytes like any other. `GET` keeps surfacing the
   `storage_unavailable` envelope for the same row; deletion is the one operation that should
   not fail because the contents cannot be read back.

## Alternatives considered

- **Return 204 because a row was removed, and update the docs to say so.** Rejected: the
  docs describe the privacy property, not an implementation detail. Changing them to match
  the leak would remove the check rather than fix it.
- **Leave expired rows alone until `purge_expired` runs.** Rejected: it makes the id
  undeletable through the only user-facing deletion route, and the purge is not scheduled.
- **Make `delete()` return False for expired rows.** Rejected: it conflates two facts — a
  row existed and a row was removed — and would break the storage-level guarantee that an
  explicit delete clears a hidden row. The route needs availability; the store already has
  two operations that can say both things.
- **Use `get()` followed by `delete()`.** Rejected: two lock acquisitions leave a window in
  which the row can expire or be replaced, and the route would hydrate a payload it does not
  need. It would also make a delete fail on a corrupt row the user asked to remove. The
  single conditional statement is smaller, atomic and does not read the payload.
- **Return 410 Gone for expired reports.** Rejected in ADR-0015 for the same reason it is
  rejected here: a distinct status confirms the id was once held.

## Consequences

- A DELETE of an expired id now answers 404 with the same body as a never-existed id, and
  the expired row is cleared. The list, GET and DELETE agree about what "kept" means.
- A live report still answers 204 with an empty body, and a second delete still answers 404
  identically to an unknown id.
- `PredictionStore.delete_live` is new. Only the history route uses it; the unconditional
  `delete` remains for housekeeping and for the tests that pin its semantics.
- No stored schema changed and no existing row migrates. The fix changes one route decision
  and adds one store method.
- The test that pins the old behaviour at the storage level (`delete()` clears an expired
  row) still passes, because that operation is intentionally unchanged.

## Validation

- `tests/api/test_prediction_history.py` — a report aged past retention is unreadable and
  unlisted, its DELETE answers 404 with details byte-identical to an unknown id's, and the
  expired row is gone afterwards. The existing live-delete, second-delete and unknown-id
  tests are unchanged and pass.
- `tests/storage/test_predictions.py` — `delete_live` removes a report 29 days into a 30-day
  retention, refuses one at expiry without removing it, leaves it for `delete()` to clear,
  and refuses a naive clock.
- Full suite after the change: 1121 passed, total coverage 96.47%. Ruff clean. `mypy` could
  not be run locally after the change because Windows Application Control blocked the
  installed mypy's compiled module; CI's backend job runs it, and no security policy was
  bypassed. Nothing here is evidence about railway behaviour; the fixtures remain synthetic.
