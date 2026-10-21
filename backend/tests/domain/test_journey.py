"""Unit tests for Journey domain model in RailConfirm Intelligence."""

from datetime import date
import pytest

from railconfirm.domain.journey import Journey, make_journey


def test_valid_journey():
    j = make_journey(
        train_number="12301",
        journey_date=date(2026, 11, 15),
        boarding_station="ndls",
        destination_station="hwh",
        class_code="sl",
        quota_code="gn",
    )
    assert j.train_number == "12301"
    assert j.journey_date == date(2026, 11, 15)
    assert j.boarding_station == "NDLS"
    assert j.destination_station == "HWH"
    assert j.class_code == "SL"
    assert j.quota_code == "GN"
    assert j.is_class_supported() is True
    assert j.is_quota_supported() is True


def test_invalid_train_numbers():
    invalid = ["123", "ABCDE", "1234567", "", "12A34"]
    for tn in invalid:
        with pytest.raises(ValueError, match="train_number"):
            Journey(
                train_number=tn,
                journey_date=date(2026, 11, 15),
                boarding_station="NDLS",
                destination_station="HWH",
                class_code="SL",
                quota_code="GN",
            )


def test_identical_stations_rejected():
    with pytest.raises(ValueError, match="must differ"):
        make_journey(
            train_number="12301",
            journey_date=date(2026, 11, 15),
            boarding_station="NDLS",
            destination_station="NDLS",
            class_code="SL",
            quota_code="GN",
        )


def test_unknown_class_and_quota_warns():
    with pytest.warns(UserWarning, match="class_code"):
        j = make_journey(
            train_number="12301",
            journey_date=date(2026, 11, 15),
            boarding_station="NDLS",
            destination_station="HWH",
            class_code="UNKNOWN_CLASS",
            quota_code="GN",
        )
        assert j.is_class_supported() is False
