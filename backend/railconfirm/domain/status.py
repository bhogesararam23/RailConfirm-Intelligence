"""Status normalization for Indian Railways reservation codes.

This module provides a versioned mapping from raw source status strings
to a reviewed domain representation. Unknown codes are preserved and
surfaced for review — never silently mapped to WL or another category.

Reference: Indian Railways passenger enquiry terminology, verified 2026-10-21.
Mapping version: 1.1.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

# ── Versioning ─────────────────────────────────────────────────────────────────
MAPPING_VERSION = "1.1.0"
"""Increment this whenever the mapping logic changes so historical data can be
reproduced and audited against the version that produced it.

1.1.0: `CK` is no longer mapped to WL/CKWL. The mapping was recorded here without
an authoritative source, and a code that has not been verified must produce
UNKNOWN rather than the nearest familiar category. Invalid numeric positions now
carry a parse note instead of being dropped silently.
"""


# ── Enumerations ───────────────────────────────────────────────────────────────


class NormalizedStatus(str, Enum):
    """Broad normalized status categories.

    These are domain concepts, not exhaustive raw-code enumerations.
    Unknown raw codes must produce UNKNOWN, not silently fall through to WL.
    """

    CNF = "CNF"            # Confirmed reservation / berth
    RAC = "RAC"            # Reservation Against Cancellation
    WL = "WL"              # Waitlisted (any category)
    CANCELLED = "CANCELLED"  # Explicitly cancelled
    OTHER = "OTHER"        # Recognized but out-of-target state
    UNKNOWN = "UNKNOWN"    # Mapping not established — must NOT map to WL
    CENSORED = "CENSORED"  # Outcome not reliably observed


# Categories that still sit inside the reservation queue and therefore have a
# final-chart outcome to estimate. A cancelled booking is no longer competing for
# berths; a censored record has no reliably observed outcome; OTHER is, by
# definition, outside the target. Estimators must refuse the latter rather than
# treat them as ordinary queue members.
TARGET_ELIGIBLE_STATUSES: frozenset[NormalizedStatus] = frozenset(
    {NormalizedStatus.CNF, NormalizedStatus.RAC, NormalizedStatus.WL}
)


class WaitlistCategory(str, Enum):
    """Known waitlist quota/category codes.

    Only the families listed in docs/model/STATUS_GLOSSARY.md as observed codes
    appear here. A family is admitted after its semantics are verified against a
    reference; this list is not exhaustive and new families must be added with a
    recorded source and date.

    Source: Indian Railways booking/enquiry terminology (verified 2026-10-21).
    """

    GNWL = "GNWL"    # General Waitlist
    RLWL = "RLWL"    # Remote Location Waitlist
    PQWL = "PQWL"    # Pooled Quota Waitlist
    TQWL = "TQWL"    # Tatkal Quota Waitlist
    RQWL = "RQWL"    # Road-side Quota Waitlist
    DPWL = "DPWL"    # Duty Pass Waitlist
    GENERAL = "WL"   # Generic / unspecified waitlist


# ── Parsed result ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ParsedStatus:
    """Immutable result of parsing one raw status string.

    Invariants
    ----------
    * ``raw`` is always preserved verbatim.
    * ``position`` is nullable; it is never guessed from context.
    * ``wl_category`` is only set when ``normalized == WL``.
    * ``mapping_version`` identifies the logic that produced this record.
    * ``parse_note`` carries warnings that warrant human review.
    """

    raw: str                                       # Always preserved
    normalized: NormalizedStatus
    wl_category: WaitlistCategory | None        # Only for WL statuses
    position: int | None                        # Nullable; never fabricated
    mapping_version: str = MAPPING_VERSION
    parse_note: str | None = None               # Warnings for review


# ── Internal helpers ───────────────────────────────────────────────────────────

# Known WL category prefixes mapped to their enum values.
_WL_CATEGORY_MAP: dict[str, WaitlistCategory] = {
    "GNWL": WaitlistCategory.GNWL,
    "RLWL": WaitlistCategory.RLWL,
    "PQWL": WaitlistCategory.PQWL,
    "TQWL": WaitlistCategory.TQWL,
    "RQWL": WaitlistCategory.RQWL,
    "DPWL": WaitlistCategory.DPWL,
    "WL": WaitlistCategory.GENERAL,
}

# Patterns for WL codes like "GNWL/15", "GNWL15", "WL/15", "WL15".
_WL_PATTERN = re.compile(
    r"^(?P<cat>GNWL|RLWL|PQWL|TQWL|RQWL|DPWL|WL)"
    r"[/ ]?"
    r"(?P<pos>\d+)?$",
    re.IGNORECASE,
)

# Pattern for RAC: "RAC", "RAC 1", "RAC/1", "RAC1".
_RAC_PATTERN = re.compile(
    r"^RAC[/ ]?(?P<pos>\d+)?$",
    re.IGNORECASE,
)

# Codes that appear in real enquiry output but whose semantics this project has
# not verified against a reference. They resolve to UNKNOWN with a review note;
# the note is deliberately distinct from the generic "unrecognized code" note so
# a reviewer can tell a known-but-unverified family apart from noise.
_UNVERIFIED_CODE_PATTERN = re.compile(
    r"^(?P<cat>CK|CKWL)[/ ]?(?P<pos>\d+)?$",
    re.IGNORECASE,
)


def _parse_position(pos_str: str | None) -> tuple[int | None, str | None]:
    """Return ``(position, note)`` for a captured position token.

    A missing token yields ``(None, None)`` — no queue position is invented. A
    token that is present but not a valid positive position yields ``(None,
    note)`` so the caller can see that information was discarded rather than
    simply absent.
    """
    if pos_str is None:
        return None, None
    try:
        val = int(pos_str)
    except (ValueError, TypeError):  # pragma: no cover - regex already restricts digits
        return None, f"Position token {pos_str!r} is not an integer and was discarded."
    if val <= 0:
        return None, (
            f"Position token {pos_str!r} is not a positive queue position "
            "and was discarded."
        )
    return val, None


# ── Public API ─────────────────────────────────────────────────────────────────


def parse_status(raw: str | None) -> ParsedStatus:
    """Parse a raw railway status string into a :class:`ParsedStatus`.

    Design rules
    ------------
    * Unknown codes → ``UNKNOWN`` with a ``parse_note``, **never** silently
      mapped to ``WL`` or any other category.
    * Positions are only set when explicitly present in the source string.
    * The original ``raw`` string is always preserved verbatim.
    * ``None`` or empty string → ``UNKNOWN``.

    Parameters
    ----------
    raw:
        The raw status string as received from the source (e.g. ``"GNWL/15"``,
        ``"RAC 3"``, ``"CNF"``, ``"CAN"``).

    Returns
    -------
    ParsedStatus
        An immutable parsed result with all fields populated.

    Examples
    --------
    >>> parse_status("CNF").normalized
    <NormalizedStatus.CNF: 'CNF'>
    >>> parse_status("GNWL/15").position
    15
    >>> parse_status("???").normalized
    <NormalizedStatus.UNKNOWN: 'UNKNOWN'>
    """
    # ── Handle None / empty ────────────────────────────────────────────────────
    if raw is None:
        return ParsedStatus(
            raw="",
            normalized=NormalizedStatus.UNKNOWN,
            wl_category=None,
            position=None,
            parse_note="Input was None; cannot determine status.",
        )

    stripped = str(raw).strip()

    if stripped == "":
        return ParsedStatus(
            raw=raw,
            normalized=NormalizedStatus.UNKNOWN,
            wl_category=None,
            position=None,
            parse_note="Empty string; cannot determine status.",
        )

    upper = stripped.upper()

    # ── CNF ───────────────────────────────────────────────────────────────────
    if upper == "CNF":
        return ParsedStatus(
            raw=raw,
            normalized=NormalizedStatus.CNF,
            wl_category=None,
            position=None,
        )

    # ── CENSORED ──────────────────────────────────────────────────────────────
    if upper == "CENSORED":
        return ParsedStatus(
            raw=raw,
            normalized=NormalizedStatus.CENSORED,
            wl_category=None,
            position=None,
        )

    # ── CANCELLED ─────────────────────────────────────────────────────────────
    if upper in ("CAN", "CANCELLED", "CANCEL"):
        return ParsedStatus(
            raw=raw,
            normalized=NormalizedStatus.CANCELLED,
            wl_category=None,
            position=None,
        )

    # ── RAC ───────────────────────────────────────────────────────────────────
    rac_match = _RAC_PATTERN.match(upper)
    if rac_match:
        pos, pos_note = _parse_position(rac_match.group("pos"))
        return ParsedStatus(
            raw=raw,
            normalized=NormalizedStatus.RAC,
            wl_category=None,
            position=pos,
            parse_note=pos_note,
        )

    # ── Known-in-the-wild but unmapped families → UNKNOWN ─────────────────────
    unverified_match = _UNVERIFIED_CODE_PATTERN.match(upper)
    if unverified_match:
        code = unverified_match.group("cat").upper()
        return ParsedStatus(
            raw=raw,
            normalized=NormalizedStatus.UNKNOWN,
            wl_category=None,
            position=None,
            parse_note=(
                f"Status family {code!r} is seen in enquiry output but its semantics "
                "are not verified against a reference. It is reported UNKNOWN rather "
                "than mapped to WL; verify and record a source before adding it to "
                "the mapping."
            ),
        )

    # ── WL categories ─────────────────────────────────────────────────────────
    wl_match = _WL_PATTERN.match(upper)
    if wl_match:
        cat_str = wl_match.group("cat").upper()
        category = _WL_CATEGORY_MAP[cat_str]
        pos, pos_note = _parse_position(wl_match.group("pos"))
        return ParsedStatus(
            raw=raw,
            normalized=NormalizedStatus.WL,
            wl_category=category,
            position=pos,
            parse_note=pos_note,
        )

    # ── UNKNOWN — all other codes ─────────────────────────────────────────────
    # IMPORTANT: Do NOT silently map unrecognized codes to WL.
    return ParsedStatus(
        raw=raw,
        normalized=NormalizedStatus.UNKNOWN,
        wl_category=None,
        position=None,
        parse_note=(
            f"Unrecognized status code '{stripped}'. "
            "Add to the versioned mapping after authoritative verification."
        ),
    )
