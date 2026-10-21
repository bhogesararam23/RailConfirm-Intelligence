"""Status normalization for Indian Railways reservation codes.

This module provides a versioned mapping from raw source status strings
to a reviewed domain representation. Unknown codes are preserved and
surfaced for review — never silently mapped to WL or another category.

Reference: Indian Railways passenger enquiry terminology, verified 2026-10-21.
Mapping version: 1.0.0
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# ── Versioning ─────────────────────────────────────────────────────────────────
MAPPING_VERSION = "1.0.0"
"""Increment this whenever the mapping logic changes so historical data can be
reproduced and audited against the version that produced it."""


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


class WaitlistCategory(str, Enum):
    """Known waitlist quota/category codes.

    This list is not exhaustive. New categories should be added only after
    authoritative verification of their semantics.

    Source: Indian Railways booking/enquiry terminology (verified 2026-10-21).
    """

    GNWL = "GNWL"    # General Waitlist
    RLWL = "RLWL"    # Remote Location Waitlist
    PQWL = "PQWL"    # Pooled Quota Waitlist
    TQWL = "TQWL"    # Tatkal Quota Waitlist
    RQWL = "RQWL"    # Road-side Quota Waitlist
    DPWL = "DPWL"    # Duty Pass Waitlist
    CKWL = "CKWL"    # (possibly Concessional/Ticket Quota — needs verification)
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
    wl_category: Optional[WaitlistCategory]        # Only for WL statuses
    position: Optional[int]                        # Nullable; never fabricated
    mapping_version: str = MAPPING_VERSION
    parse_note: Optional[str] = None               # Warnings for review


# ── Internal helpers ───────────────────────────────────────────────────────────

# Known WL category prefixes mapped to their enum values.
_WL_CATEGORY_MAP: dict[str, WaitlistCategory] = {
    "GNWL": WaitlistCategory.GNWL,
    "RLWL": WaitlistCategory.RLWL,
    "PQWL": WaitlistCategory.PQWL,
    "TQWL": WaitlistCategory.TQWL,
    "RQWL": WaitlistCategory.RQWL,
    "DPWL": WaitlistCategory.DPWL,
    "CKWL": WaitlistCategory.CKWL,
    "WL": WaitlistCategory.GENERAL,
}

# Patterns for WL codes like "GNWL/15", "GNWL15", "WL/15", "WL15".
_WL_PATTERN = re.compile(
    r"^(?P<cat>GNWL|RLWL|PQWL|TQWL|RQWL|DPWL|CKWL|WL)"
    r"[/ ]?"
    r"(?P<pos>\d+)?$",
    re.IGNORECASE,
)

# Pattern for RAC: "RAC", "RAC 1", "RAC/1", "RAC1".
_RAC_PATTERN = re.compile(
    r"^RAC[/ ]?(?P<pos>\d+)?$",
    re.IGNORECASE,
)

# CK is sometimes seen (possibly same as CKWL) — treat as WL with a note.
_CK_PATTERN = re.compile(r"^CK$", re.IGNORECASE)


def _parse_position(pos_str: Optional[str]) -> Optional[int]:
    """Return validated integer position or None."""
    if pos_str is None:
        return None
    try:
        val = int(pos_str)
        if val <= 0:
            return None  # Negative/zero positions are invalid; do not store
        return val
    except (ValueError, TypeError):
        return None


# ── Public API ─────────────────────────────────────────────────────────────────


def parse_status(raw: Optional[str]) -> ParsedStatus:
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
        pos = _parse_position(rac_match.group("pos"))
        return ParsedStatus(
            raw=raw,
            normalized=NormalizedStatus.RAC,
            wl_category=None,
            position=pos,
        )

    # ── CK (possible short form — needs verification) ─────────────────────────
    if _CK_PATTERN.match(upper):
        return ParsedStatus(
            raw=raw,
            normalized=NormalizedStatus.WL,
            wl_category=WaitlistCategory.CKWL,
            position=None,
            parse_note=(
                "Code 'CK' tentatively mapped to WL/CKWL; "
                "semantics require authoritative verification."
            ),
        )

    # ── WL categories ─────────────────────────────────────────────────────────
    wl_match = _WL_PATTERN.match(upper)
    if wl_match:
        cat_str = wl_match.group("cat").upper()
        category = _WL_CATEGORY_MAP.get(cat_str, WaitlistCategory.GENERAL)
        pos = _parse_position(wl_match.group("pos"))
        note = None
        if cat_str == "CKWL":
            note = (
                "CKWL semantics require authoritative verification "
                "before use in model training."
            )
        return ParsedStatus(
            raw=raw,
            normalized=NormalizedStatus.WL,
            wl_category=category,
            position=pos,
            parse_note=note,
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
