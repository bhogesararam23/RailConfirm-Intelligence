"""Tests for the local dataset loader: format bounds, safety and clear failures."""

import json
from pathlib import Path

import pytest

from railconfirm.data.loader import DEFAULT_MAX_BYTES, load_dataset_file

CSV = (
    "# SYNTHETIC DATA - TESTING ONLY\n"
    "train_number,journey_date,initial_status\n"
    "12301,2026-10-01,GNWL/10\n"
    "12302,2026-10-02,CNF\n"
)


def write_csv(tmp_path: Path, text: str = CSV, name: str = "data.csv") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_load_synthetic_csv(synthetic_dataset_path: Path):
    frame = load_dataset_file(synthetic_dataset_path)
    assert len(frame) == 6
    assert {"train_number", "journey_date", "initial_status", "final_chart_status"} <= set(frame.columns)


def test_provenance_comment_lines_are_not_columns(synthetic_dataset_path: Path):
    frame = load_dataset_file(synthetic_dataset_path)
    assert list(frame.columns)[0] == "train_number"
    assert not any("SYNTHETIC" in str(column) for column in frame.columns)


def test_every_column_arrives_as_text_so_interpretation_is_explicit(tmp_path: Path):
    frame = load_dataset_file(write_csv(tmp_path))
    assert frame["journey_date"].iloc[0] == "2026-10-01"
    assert not hasattr(frame["journey_date"].iloc[0], "year")


def test_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_dataset_file(tmp_path / "absent.csv")


@pytest.mark.parametrize("name", ["data.txt", "model.pkl", "sheet.xlsx", "table.parquet", "no_extension"])
def test_unsupported_formats_are_refused_before_reading(tmp_path: Path, name):
    path = tmp_path / name
    path.write_bytes(b"anything")
    with pytest.raises(ValueError, match="Unsupported dataset format"):
        load_dataset_file(path)


def test_empty_file_is_reported(tmp_path: Path):
    with pytest.raises(ValueError, match="empty"):
        load_dataset_file(write_csv(tmp_path, ""))


def test_header_only_file_is_reported(tmp_path: Path):
    with pytest.raises(ValueError, match="no rows"):
        load_dataset_file(write_csv(tmp_path, "train_number,journey_date\n"))


def test_ragged_rows_are_reported_not_silently_padded(tmp_path: Path):
    with pytest.raises(ValueError, match="do not match the"):
        load_dataset_file(write_csv(tmp_path, "a,b,c\n1,2\n"))


def test_undecodable_bytes_are_reported(tmp_path: Path):
    path = tmp_path / "data.csv"
    path.write_bytes(b"\xff\xfe\x00broken")
    with pytest.raises(ValueError, match="not valid UTF-8"):
        load_dataset_file(path)


def test_size_limit_is_enforced_without_reading_the_whole_file(tmp_path: Path):
    path = write_csv(tmp_path, CSV * 50)
    with pytest.raises(ValueError, match="above the"):
        load_dataset_file(path, max_bytes=100)


def test_nonsense_size_limit_is_rejected(tmp_path: Path):
    path = write_csv(tmp_path)
    with pytest.raises(ValueError, match="max_bytes"):
        load_dataset_file(path, max_bytes=0)


def test_default_limit_is_the_documented_ceiling():
    assert DEFAULT_MAX_BYTES == 200 * 1024 * 1024


def test_duplicate_column_names_are_refused(tmp_path: Path):
    """pandas would rename the second one silently."""
    path = write_csv(tmp_path, "a,b,a\n1,2,3\n")
    with pytest.raises(ValueError, match="duplicate column names"):
        load_dataset_file(path)


def test_blank_and_absurd_column_names_are_refused(tmp_path: Path):
    with pytest.raises(ValueError, match="column names are blank"):
        load_dataset_file(write_csv(tmp_path, "a,,b\n1,2,3\n"))
    with pytest.raises(ValueError, match="characters"):
        load_dataset_file(write_csv(tmp_path, f"{'x' * 300},b\n1,2\n"))


def test_column_names_are_trimmed(tmp_path: Path):
    frame = load_dataset_file(write_csv(tmp_path, " train_number , journey_date \n1,2026-10-01\n"))
    assert list(frame.columns) == ["train_number", "journey_date"]


def test_json_record_list(tmp_path: Path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps([{"train_number": "12301", "journey_date": "2026-10-01"}]), encoding="utf-8")
    assert len(load_dataset_file(path)) == 1


def test_json_records_key(tmp_path: Path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps({"records": [{"a": 1}, {"a": 2}]}), encoding="utf-8")
    assert load_dataset_file(path)["a"].tolist() == ["1", "2"]


@pytest.mark.parametrize(
    "payload,fragment",
    [
        ("{not json", "not valid JSON"),
        ('{"a": 1}', "list of records"),
        ("[]", "no records"),
        ('{"records": []}', "no records"),
        ('[{"a":1}, "b"]', "must be a JSON object"),
    ],
)
def test_malformed_json_is_reported_clearly(tmp_path: Path, payload, fragment):
    path = tmp_path / "data.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match=fragment):
        load_dataset_file(path)
