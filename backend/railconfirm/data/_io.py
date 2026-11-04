"""Shared atomic file I/O utilities for the data layer.

Provides crash-safe write helpers used across the data package to ensure that
file-write interruptions never corrupt or truncate an existing file.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


def atomic_write_text(path: Path | str, text: str, *, encoding: str = "utf-8") -> Path:
    """Atomically write text to *path* using a temp file + os.replace.

    If the write or fsync fails the original file at *path* (if any) is not
    modified. The temp file is cleaned up on failure.

    Returns the resolved destination path.
    """
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        dir=target.parent,
        delete=False,
        prefix=f".tmp_{target.name}_",
    )
    temp_path = Path(temp_file.name)
    try:
        temp_file.write(text)
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file.close()
        os.replace(temp_path, target)
        return target
    except Exception:
        temp_file.close()
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def atomic_write_json(
    path: Path | str,
    data: Any,
    *,
    indent: int = 2,
    sort_keys: bool = False,
    encoding: str = "utf-8",
) -> Path:
    """Atomically write JSON data to *path* using a temp file + os.replace.

    Equivalent to ``atomic_write_text`` but accepts an arbitrary serialisable
    object and formats it with :func:`json.dumps`.
    """
    text = json.dumps(data, indent=indent, sort_keys=sort_keys) + "\n"
    return atomic_write_text(path, text, encoding=encoding)


def atomic_write_csv(
    path: Path | str,
    df: pd.DataFrame,
    *,
    index: bool = False,
    encoding: str = "utf-8",
    **kwargs: Any,
) -> Path:
    """Atomically write a pandas DataFrame to CSV at *path* using a temporary file.

    Guarantees that write failures or interruptions never leave a partial or
    truncated CSV file. Uses ``df.to_csv(index=index, ...)`` to format the CSV
    string and writes atomically via ``atomic_write_text``.
    """
    csv_text = df.to_csv(index=index, **kwargs)
    return atomic_write_text(path, str(csv_text), encoding=encoding)


def atomic_copy_file(source: Path | str, destination: Path | str) -> Path:
    """Atomically copy *source* file to *destination* using a temporary file + os.replace.

    Guarantees that an interrupted copy never leaves a partial, zero-byte, or
    corrupted file at *destination*. Uses a temporary file in the destination's
    parent directory (ensuring same-filesystem placement), flushes and fsyncs the
    copied bytes, and atomically renames via ``os.replace``.

    Platform note:
    On POSIX systems, ``os.replace`` is an atomic rename within the same mount.
    On Windows (NTFS), ``os.replace`` uses ``MoveFileExW`` with
    ``MOVEFILE_REPLACE_EXISTING``, which is atomic at the directory entry level
    provided no conflicting non-shared handle is held open.
    """
    src = Path(source).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Source file does not exist: {src}")

    dst = Path(destination).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    temp_file = tempfile.NamedTemporaryFile(
        dir=dst.parent,
        delete=False,
        prefix=f".tmp_{dst.name}_",
    )
    temp_path = Path(temp_file.name)
    try:
        temp_file.close()
        shutil.copy2(src, temp_path)
        with open(temp_path, "r+b") as f:
            os.fsync(f.fileno())
        os.replace(temp_path, dst)
        return dst
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
