"""Shared atomic file I/O utilities for the data layer.

Provides crash-safe write helpers used across the data package to ensure that
file-write interruptions never corrupt or truncate an existing file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


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

