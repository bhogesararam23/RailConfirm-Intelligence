# Reservation status glossary

This is a working domain glossary, not a complete or authoritative list of every railway reservation code. Verify each raw code and its meaning against an authoritative source before treating the mapping as production behavior.

## Normalized outcome concepts

| Normalized concept | Intended meaning | Important distinction |
|---|---|---|
| CNF | Confirmed reservation / berth under the chosen source definition | Distinct from RAC |
| RAC | Reservation Against Cancellation | Do not report as identical to a full confirmed berth |
| WL | Waitlisted reservation | Preserve the specific raw quota/status code |
| CANCELLED | Explicitly cancelled under the source's semantics | Not automatically a failed confirmation label |
| OTHER | A recognized but out-of-target state | Keep raw source value |
| UNKNOWN | Mapping not established | Must not be silently mapped to WL |
| CENSORED | Target outcome not reliably observed | Not a negative label |

## Observed codes to investigate

Examples include GNWL, RLWL, PQWL, TQWL, RQWL and DPWL. This list is not exhaustive and should not be interpreted as a complete supported-code list. Code semantics, availability by quota and final outcome mapping need authoritative verification.

## Codes deliberately not mapped

| Raw code | Behaviour | Reason |
|---|---|---|
| `CK`, `CKWL` | `UNKNOWN` with a review note, never `WL` | Recorded here historically as "possibly Concessional/Ticket Quota — needs verification" and, for `CK`, tentatively mapped to `WL/CKWL`. No reference was ever located, so the mapping was a guess about the nearest familiar category. Status mapping version 1.1.0 removed the guess; these codes now surface for review instead of being trained on as ordinary waitlist rows. |

Re-admitting a family requires an authoritative source, the date checked, valid and invalid examples, unit tests, and a mapping version bump.

## Mapping version history

| Version | Change | Date |
|---|---|---|
| 1.0.0 | Initial mapping: CNF, RAC, GNWL/RLWL/PQWL/TQWL/RQWL/DPWL, generic WL, CAN, CENSORED; `CK`/`CKWL` tentatively mapped to waitlist. | 2026-10-21 |
| 1.1.0 | `CK` and `CKWL` demoted to `UNKNOWN` pending verification (no source supported the waitlist mapping). A position token that is present but invalid now records a parse note rather than being dropped silently. | 2026-10-23 |

The version is stamped on every parsed status so historical rows can be reproduced against the mapping that produced them.

## Mapping requirements

For each raw status:
- Store the original source string.
- Define the normalized concept and any numeric position semantics.
- Record the authoritative reference and date checked.
- Add valid/invalid examples and unit tests.
- Preserve unknown status strings and emit a review signal.
- Version mapping changes so historical training data can be reproduced.

## Numeric position

Do not treat the number in WL and the number in RAC as the same queue measure. A parsed position is nullable and is meaningful only with its raw status category and quota context. Reject negative or malformed positions. Do not invent a queue position when the source omits it.

## Outcome semantics

The model target must name the outcome moment, e.g. final-chart status. A status from a later enquiry should not overwrite the final-chart label. A post-chart outcome is a separate target and must be evaluated separately.
