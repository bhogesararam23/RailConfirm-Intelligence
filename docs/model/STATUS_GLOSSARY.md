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
