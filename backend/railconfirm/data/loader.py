"""Local dataset loader for RailConfirm Intelligence.

Loads and cleans local dataset files (CSV, JSON) for offline evaluation
and data validation. Does not execute external network calls (ADR-0007).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

import pandas as pd


def load_dataset_file(file_path: Union[str, Path]) -> pd.DataFrame:
    """Load a candidate dataset file from disk.

    Supports CSV and JSON formats.

    Parameters
    ----------
    file_path:
        Path to local CSV or JSON dataset file.

    Returns
    -------
    pd.DataFrame
        Loaded raw DataFrame with stripped column names.

    Raises
    -------
    FileNotFoundError
        If file does not exist.
    ValueError
        If file format is unsupported or file is empty.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, dtype=str, comment="#")
    elif suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict) and "records" in data:
            df = pd.DataFrame(data["records"])
        else:
            raise ValueError("JSON dataset must be a list of records or have a 'records' key.")
    else:
        raise ValueError(f"Unsupported dataset format '{suffix}'. Expected .csv or .json.")

    if df.empty:
        raise ValueError(f"Dataset file {path} contains no data.")

    # Strip column names whitespace
    df.columns = [str(c).strip() for c in df.columns]
    return df
