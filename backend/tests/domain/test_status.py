"""Unit tests for status normalization and parsing in RailConfirm Intelligence."""


from railconfirm.domain.status import (
    MAPPING_VERSION,
    NormalizedStatus,
    WaitlistCategory,
    parse_status,
)


def test_parsed_status_records_mapping_version():
    """Every parse result must be traceable to the mapping that produced it."""
    for raw in ["CNF", "RAC 3", "GNWL/15", "CAN", "???"]:
        assert parse_status(raw).mapping_version == MAPPING_VERSION


def test_parse_cnf():
    res = parse_status("CNF")
    assert res.normalized == NormalizedStatus.CNF
    assert res.raw == "CNF"
    assert res.position is None
    assert res.wl_category is None
    assert res.parse_note is None


def test_parse_rac():
    res1 = parse_status("RAC")
    assert res1.normalized == NormalizedStatus.RAC
    assert res1.position is None

    res2 = parse_status("RAC 3")
    assert res2.normalized == NormalizedStatus.RAC
    assert res2.position == 3

    res3 = parse_status("RAC/12")
    assert res3.normalized == NormalizedStatus.RAC
    assert res3.position == 12


def test_parse_wl_categories():
    test_cases = [
        ("GNWL/15", WaitlistCategory.GNWL, 15),
        ("RLWL/2", WaitlistCategory.RLWL, 2),
        ("PQWL/100", WaitlistCategory.PQWL, 100),
        ("TQWL/1", WaitlistCategory.TQWL, 1),
        ("RQWL/5", WaitlistCategory.RQWL, 5),
        ("DPWL/3", WaitlistCategory.DPWL, 3),
        ("WL/25", WaitlistCategory.GENERAL, 25),
        ("WL 4", WaitlistCategory.GENERAL, 4),
        ("GNWL10", WaitlistCategory.GNWL, 10),
    ]
    for raw, expected_cat, expected_pos in test_cases:
        res = parse_status(raw)
        assert res.normalized == NormalizedStatus.WL, f"Failed for {raw}"
        assert res.wl_category == expected_cat, f"Failed category for {raw}"
        assert res.position == expected_pos, f"Failed position for {raw}"
        assert res.raw == raw


def test_parse_cancelled():
    for raw in ["CAN", "CANCELLED", "CANCEL", "can", "cancelled"]:
        res = parse_status(raw)
        assert res.normalized == NormalizedStatus.CANCELLED
        assert res.position is None


def test_parse_unknown_never_mapped_to_wl():
    unknown_codes = ["XYZ", "???", "INVALID_CODE", "UNKNOWN", "WAITLISTED", "CONFIRM"]
    for raw in unknown_codes:
        res = parse_status(raw)
        assert res.normalized == NormalizedStatus.UNKNOWN, (
            f"Code '{raw}' was wrongly normalized to {res.normalized}; "
            "must be UNKNOWN."
        )
        assert res.raw == raw
        assert res.parse_note is not None


def test_parse_none_and_empty():
    res_none = parse_status(None)
    assert res_none.normalized == NormalizedStatus.UNKNOWN

    res_empty = parse_status("")
    assert res_empty.normalized == NormalizedStatus.UNKNOWN

    res_spaces = parse_status("   ")
    assert res_spaces.normalized == NormalizedStatus.UNKNOWN


def test_parse_invalid_positions():
    # Negative and zero positions are rejected/None
    res_zero = parse_status("WL/0")
    assert res_zero.normalized == NormalizedStatus.WL
    assert res_zero.position is None

    res_rac_zero = parse_status("RAC 0")
    assert res_rac_zero.normalized == NormalizedStatus.RAC
    assert res_rac_zero.position is None


def test_discarded_position_is_reported_not_silent():
    """A position token that exists but is invalid must be visible to reviewers."""
    for raw in ["WL/0", "GNWL/0", "RAC 0", "RAC/0"]:
        res = parse_status(raw)
        assert res.position is None
        assert res.parse_note is not None, f"{raw} discarded a position without a note"
        assert "position" in res.parse_note.lower()

    # An absent token is not a warning: nothing was thrown away.
    assert parse_status("GNWL").parse_note is None


def test_verifiable_codes_have_no_parse_note():
    for raw in ["CNF", "RAC 3", "GNWL/15", "CAN", "CENSORED"]:
        assert parse_status(raw).parse_note is None


def test_ck_and_ckwl_are_not_mapped_to_waitlist():
    """Regression: 1.0.0 guessed CK -> WL/CKWL with no source.

    An unverified family must surface as UNKNOWN so it is reviewed rather than
    silently trained on as ordinary waitlist data.
    """
    for raw in ["CK", "ck", "CKWL", "CKWL/5", "CK 12"]:
        res = parse_status(raw)
        assert res.normalized == NormalizedStatus.UNKNOWN, (
            f"{raw!r} normalized to {res.normalized}; unverified families must "
            "stay UNKNOWN."
        )
        assert res.wl_category is None
        assert res.position is None
        assert "not verified" in res.parse_note


def test_wl_category_only_accompanies_waitlist():
    for raw in ["CNF", "RAC 2", "CAN", "CENSORED", "???"]:
        res = parse_status(raw)
        assert res.wl_category is None
    for raw in ["GNWL/3", "WL", "RLWL/7"]:
        assert parse_status(raw).wl_category is not None


def test_raw_string_is_preserved_verbatim_including_whitespace_and_case():
    for raw in [" gnwl/15 ", "Rac 2", "cnf"]:
        res = parse_status(raw)
        assert res.raw == raw
