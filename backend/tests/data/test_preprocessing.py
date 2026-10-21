"""Unit tests for feature construction and chronological partitioning."""

from pathlib import Path

import pandas as pd
import pytest

from railconfirm.data.loader import load_dataset_file
from railconfirm.data.preprocessing import chronological_split, extract_features


def test_extract_features(synthetic_dataset_path: Path):
    df = load_dataset_file(synthetic_dataset_path)
    features_df = extract_features(df)
    assert "init_normalized" in features_df.columns
    assert "init_position" in features_df.columns
    assert "obs_normalized" in features_df.columns
    assert "obs_position" in features_df.columns
    assert "lead_days" in features_df.columns
    assert len(features_df) == len(df)


def test_chronological_split(synthetic_dataset_path: Path):
    df = load_dataset_file(synthetic_dataset_path)
    splits = chronological_split(df, train_frac=0.5, val_frac=0.25)
    assert not splits.train.empty
    # Earliest date in synthetic dataset is 2026-10-01
    assert splits.train_dates[0] <= splits.train_dates[1]


def test_chronological_split_missing_column():
    df = pd.DataFrame({"some_col": [1, 2]})
    with pytest.raises(ValueError, match="journey_date"):
        chronological_split(df)
