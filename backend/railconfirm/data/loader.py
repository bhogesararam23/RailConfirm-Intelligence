"""Local dataset loader for RailConfirm Intelligence.

Reads a candidate dataset file from disk, off the working directory, as text
columns. No network access (ADR-0007) and no executable deserialisation: only
CSV and JSON are accepted, and the file is bounded in size before it is parsed.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from railconfirm.domain.exceptions import DatasetValidationError

SUPPORTED_SUFFIXES: frozenset[str] = frozenset({".csv", ".json"})

# A ceiling on what will be read into memory at all. Candidate railway datasets
# are research-scale; an unbounded read of an unexpected file is a way to hang a
# research machine, and "very large or suspicious file" is an intake concern.
DEFAULT_MAX_BYTES = 200 * 1024 * 1024

MAX_COLUMN_NAME_LENGTH = 120


def load_dataset_file(
    file_path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> pd.DataFrame:
    """Load a candidate dataset file from disk.

    Parameters
    ----------
    file_path:
        Path to a local ``.csv`` or ``.json`` dataset file.
    max_bytes:
        Refuse to read a file larger than this.

    Returns
    -------
    pd.DataFrame
        Every column typed as text, with whitespace stripped from column names.
        Values stay strings so the validator, not pandas' type inference, decides
        what a date or a count means.

    Raises
    ------
    FileNotFoundError
        If the path does not exist or is not a file.
    DatasetValidationError
        If the format is unsupported, the file is empty, unreadable, oversized, or
        has malformed structure.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise DatasetValidationError(
            f"Unsupported dataset format {suffix or '(no extension)'!r}. Expected one of "
            f"{sorted(SUPPORTED_SUFFIXES)}. Nothing here reads pickle, Excel or parquet, "
            "so a model or foreign workbook cannot be loaded as data."
        )

    if isinstance(max_bytes, bool) or max_bytes < 1:
        raise DatasetValidationError(f"max_bytes must be a positive integer, got {max_bytes!r}.")

    size = path.stat().st_size
    if size > max_bytes:
        raise DatasetValidationError(
            f"{path.name} is {size} bytes, above the {max_bytes} byte intake limit. "
            "Refusing to read it rather than exhausting memory on a suspicious file."
        )
    if size == 0:
        raise DatasetValidationError(f"Dataset file {path} is empty (0 bytes).")

    if suffix == ".csv":
        frame = _read_csv(path)
    else:
        frame = _read_json(path)

    if frame.empty:
        raise DatasetValidationError(f"Dataset file {path} contains no rows.")

    names = [str(column).strip() for column in frame.columns]
    _validate_header(names, path)
    frame.columns = names
    return frame


def _read_csv(path: Path) -> pd.DataFrame:
    """Parse CSV explicitly rather than through pandas' type inference.

    pandas accepts a row with too few fields (padded with NaN) and *drops* the
    surplus of a row with too many, renames a repeated column to ``a.1``, and
    renames a blank one to ``Unnamed: 1``. All four lose or disguise information
    without an error, so the header and every row width are checked here first.
    csv semantics are also identical across pandas versions, which matters while
    development runs on pandas 2 and CI on pandas 3.
    """
    try:
        handle = open(path, newline="", encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DatasetValidationError(
            f"Dataset file {path} is not valid UTF-8: {exc}"
        ) from exc
    except OSError as exc:
        raise DatasetValidationError(f"Dataset file {path} could not be read: {exc}") from exc

    with handle:
        rows: list[list[str]] = []
        try:
            for record in csv.reader(handle):
                # A provenance banner is a single field beginning with '#'.
                if len(record) == 1 and record[0].lstrip().startswith("#"):
                    continue
                if not record or (len(record) == 1 and not record[0].strip()):
                    continue
                rows.append(record)
        except UnicodeDecodeError as exc:
            raise DatasetValidationError(
                f"Dataset file {path} is not valid UTF-8: {exc}"
            ) from exc

    if not rows:
        raise DatasetValidationError(f"Dataset file {path} has no parsable CSV content.")

    header = [name.strip() for name in rows[0]]
    _validate_header(header, path)

    if len(rows) == 1:
        raise DatasetValidationError(f"Dataset file {path} contains no rows.")

    expected = len(header)
    mismatched = [
        (number, len(row)) for number, row in enumerate(rows[1:], start=2) if len(row) != expected
    ]
    if mismatched:
        examples = ", ".join(
            f"line {number} has {width} fields" for number, width in mismatched[:3]
        )
        raise DatasetValidationError(
            f"{len(mismatched)} row(s) of {path.name} do not match the {expected}-column "
            f"header ({examples}). pandas would pad or drop these silently."
        )

    return pd.DataFrame(rows[1:], columns=header)


def _validate_header(header: list[str], path: Path) -> None:
    if any(not name for name in header):
        raise DatasetValidationError(
            f"{path.name}: one or more column names are blank; every column needs a name."
        )
    if any(len(name) > MAX_COLUMN_NAME_LENGTH for name in header):
        raise DatasetValidationError(
            f"{path.name}: a column name exceeds {MAX_COLUMN_NAME_LENGTH} characters; "
            "this file is unlikely to be the dataset it claims to be."
        )
    duplicates = sorted({name for name in header if header.count(name) > 1})
    if duplicates:
        raise DatasetValidationError(
            f"{path.name}: duplicate column names {duplicates}. pandas would rename them "
            "to like 'a.1' and a row would then carry two values for one field."
        )


def _read_json(path: Path) -> pd.DataFrame:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise DatasetValidationError(
            f"Dataset file {path} is not readable UTF-8 JSON: {exc}"
        ) from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DatasetValidationError(
            f"Dataset file {path} is not valid JSON: {exc}"
        ) from exc

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict) and isinstance(data.get("records"), list):
        records = data["records"]
    else:
        raise DatasetValidationError(
            "A JSON dataset must be a list of records or an object with a 'records' list; "
            f"got {type(data).__name__}."
        )

    if not records:
        raise DatasetValidationError(f"Dataset file {path} contains no records.")
    if not all(isinstance(record, dict) for record in records):
        raise DatasetValidationError(
            f"Dataset file {path} mixes record objects with non-objects; every entry "
            "must be a JSON object."
        )
    return pd.DataFrame(records).astype(str)
