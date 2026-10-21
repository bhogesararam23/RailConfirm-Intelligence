"""Unit tests for dataset loading functions."""

from pathlib import Path
import pytest

from railconfirm.data.loader import load_dataset_file


def test_load_synthetic_csv(synthetic_dataset_path: Path):
    df = load_dataset_file(synthetic_dataset_path)
    assert not df.empty
    assert "train_number" in df.columns
    assert "journey_date" in df.columns
    assert "initial_status" in df.columns
    assert "final_chart_status" in df.columns
    assert len(df) == 6


def test_load_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        load_dataset_file("nonexistent_path_xyz.csv")


def test_load_unsupported_format(tmp_path: Path):
    bad_file = tmp_path / "test.txt"
    bad_file.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported dataset format"):
        load_dataset_file(bad_file)
