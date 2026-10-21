"""Feature construction and chronological splitting for RailConfirm Intelligence.

Ensures strict temporal integrity and prevents target leakage (ADR-0004, docs/technical/INGESTION_AND_TRACKING.md):
- Only features observable as of the prediction timestamp are constructed.
- Snaps of the same booking/journey are kept in the same partition.
- Chronological train/validation/test splits based on journey_date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple

import numpy as np
import pandas as pd

from railconfirm.domain.status import parse_status


@dataclass
class DatasetSplits:
    """Chronologically partitioned datasets."""

    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    train_dates: Tuple[str, str]
    val_dates: Tuple[str, str]
    test_dates: Tuple[str, str]


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Construct model feature matrix from validated observation records.

    Does NOT use final_chart_status or any outcome information.
    """
    out = df.copy()

    # Parse initial and observation statuses
    parsed_inits = [parse_status(str(s)) for s in out["initial_status"]]
    parsed_obs = [parse_status(str(s)) for s in out.get("current_status", out["initial_status"])]

    out["init_normalized"] = [p.normalized.value for p in parsed_inits]
    out["init_position"] = [p.position if p.position is not None else 0 for p in parsed_inits]

    out["obs_normalized"] = [p.normalized.value for p in parsed_obs]
    out["obs_position"] = [p.position if p.position is not None else 0 for p in parsed_obs]

    # Calculate lead time in days if both dates available
    if "observation_date" in out.columns and "journey_date" in out.columns:
        obs_dt = pd.to_datetime(out["observation_date"], errors="coerce")
        jrny_dt = pd.to_datetime(out["journey_date"], errors="coerce")
        out["lead_days"] = (jrny_dt - obs_dt).dt.days.fillna(0).clip(lower=0)
    else:
        out["lead_days"] = 0

    return out


def chronological_split(
    df: pd.DataFrame,
    train_frac: float = 0.70,
    val_frac: float = 0.15,
) -> DatasetSplits:
    """Split dataset chronologically by journey_date without leaking groups across boundaries.

    Parameters
    ----------
    df:
        DataFrame containing journey_date column.
    train_frac:
        Proportion of dates for training (earliest).
    val_frac:
        Proportion of dates for validation (intermediate).
        Remaining goes to test (latest, locked).

    Returns
    -------
    DatasetSplits
    """
    if "journey_date" not in df.columns:
        raise ValueError("Cannot perform chronological split without 'journey_date' column.")

    sorted_df = df.sort_values("journey_date").reset_index(drop=True)
    unique_dates = sorted_df["journey_date"].drop_duplicates().tolist()

    if len(unique_dates) < 3:
        # Too few distinct dates for a 3-way chronological split
        return DatasetSplits(
            train=sorted_df,
            val=sorted_df.iloc[0:0],
            test=sorted_df.iloc[0:0],
            train_dates=(str(unique_dates[0]), str(unique_dates[-1])) if unique_dates else ("", ""),
            val_dates=("", ""),
            test_dates=("", ""),
        )

    n_dates = len(unique_dates)
    train_cutoff_idx = max(1, int(n_dates * train_frac))
    val_cutoff_idx = max(train_cutoff_idx + 1, int(n_dates * (train_frac + val_frac)))

    train_dates_list = unique_dates[:train_cutoff_idx]
    val_dates_list = unique_dates[train_cutoff_idx:val_cutoff_idx]
    test_dates_list = unique_dates[val_cutoff_idx:]

    train_df = sorted_df[sorted_df["journey_date"].isin(train_dates_list)].copy()
    val_df = sorted_df[sorted_df["journey_date"].isin(val_dates_list)].copy()
    test_df = sorted_df[sorted_df["journey_date"].isin(test_dates_list)].copy()

    return DatasetSplits(
        train=train_df,
        val=val_df,
        test=test_df,
        train_dates=(str(train_dates_list[0]), str(train_dates_list[-1])),
        val_dates=(str(val_dates_list[0]), str(val_dates_list[-1])) if val_dates_list else ("", ""),
        test_dates=(str(test_dates_list[0]), str(test_dates_list[-1])) if test_dates_list else ("", ""),
    )
