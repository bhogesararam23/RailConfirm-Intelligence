"""Unit tests for the shared atomic file I/O utilities."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from railconfirm.data._io import (
    atomic_copy_file,
    atomic_write_csv,
    atomic_write_json,
    atomic_write_text,
)
from railconfirm.data.inspection import quarantine_dataset


def test_atomic_write_text_success(tmp_path: Path):
    target = tmp_path / "deep" / "nested" / "file.txt"
    text = "hello world\nline 2"

    written = atomic_write_text(target, text)
    assert written == target.resolve()
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == text


def test_atomic_write_text_preserves_on_write_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "protected.txt"
    original_text = "original contents"
    target.write_text(original_text, encoding="utf-8")

    # Monkeypatch os.fsync to raise an error during write
    def failing_fsync(fd: int):
        raise OSError("Simulated disk error during fsync")

    monkeypatch.setattr(os, "fsync", failing_fsync)

    with pytest.raises(OSError, match="Simulated disk error"):
        atomic_write_text(target, "new corrupted content")

    # Target must remain unmodified
    assert target.read_text(encoding="utf-8") == original_text
    # No temporary files should linger
    temp_files = list(target.parent.glob(".tmp_*"))
    assert len(temp_files) == 0


def test_atomic_write_json_roundtrip(tmp_path: Path):
    target = tmp_path / "data.json"
    data = {"key": "value", "list": [1, 2, 3], "flag": True}

    written = atomic_write_json(target, data, indent=2, sort_keys=True)
    assert written == target.resolve()
    assert target.is_file()

    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded == data


def test_atomic_write_csv_roundtrip_and_safety(tmp_path: Path):
    target = tmp_path / "subdir" / "data.csv"
    df = pd.DataFrame({
        "train_number": ["12301", "12302"],
        "class_code": ["SL", "3A"],
        "passengers": [2, 4],
    })

    written = atomic_write_csv(target, df, index=False)
    assert written == target.resolve()
    assert target.is_file()

    loaded = pd.read_csv(target, dtype=str)
    assert list(loaded["train_number"]) == ["12301", "12302"]
    assert list(loaded["class_code"]) == ["SL", "3A"]


def test_atomic_write_csv_preserves_existing_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "table.csv"
    original_content = "col1,col2\nval1,val2\n"
    target.write_text(original_content, encoding="utf-8")

    def failing_fsync(fd: int):
        raise OSError("Simulated flush failure")

    monkeypatch.setattr(os, "fsync", failing_fsync)

    df = pd.DataFrame({"col1": ["new_val1"], "col2": ["new_val2"]})
    with pytest.raises(OSError, match="Simulated flush failure"):
        atomic_write_csv(target, df, index=False)

    # Destination unchanged
    assert target.read_text(encoding="utf-8") == original_content
    # Temporary files purged
    assert len(list(target.parent.glob(".tmp_*"))) == 0


def test_atomic_copy_file_success_and_preservation(tmp_path: Path):
    src = tmp_path / "source.dat"
    src.write_bytes(b"DATA_BINARY_PAYLOAD_12345")

    dst = tmp_path / "nested" / "quarantined.dat"
    written = atomic_copy_file(src, dst)

    assert written == dst.resolve()
    assert dst.is_file()
    assert dst.read_bytes() == b"DATA_BINARY_PAYLOAD_12345"


def test_atomic_copy_file_missing_source(tmp_path: Path):
    src = tmp_path / "non_existent.dat"
    dst = tmp_path / "out.dat"
    with pytest.raises(FileNotFoundError, match="Source file does not exist"):
        atomic_copy_file(src, dst)


def test_atomic_copy_file_preserves_dst_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    src = tmp_path / "source.dat"
    src.write_text("fresh source content", encoding="utf-8")

    dst = tmp_path / "target.dat"
    dst.write_text("precious existing content", encoding="utf-8")

    import shutil

    def failing_copy2(s, d):
        # Write partial bytes then fail
        Path(d).write_text("partial corrupt bytes", encoding="utf-8")
        raise IOError("Disk write interrupted midway")

    monkeypatch.setattr(shutil, "copy2", failing_copy2)

    with pytest.raises(IOError, match="Disk write interrupted"):
        atomic_copy_file(src, dst)

    # Target must be untouched with its original content
    assert dst.read_text(encoding="utf-8") == "precious existing content"
    # No temporary file leftovers
    assert len(list(dst.parent.glob(".tmp_*"))) == 0


def test_quarantine_pair_atomicity_on_sidecar_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source_file = tmp_path / "bad_dataset.csv"
    source_file.write_text("corrupted content", encoding="utf-8")
    quarantine_dir = tmp_path / "quarantine"

    import railconfirm.data.inspection as insp

    def failing_sidecar_write(path, report, indent=2):
        raise RuntimeError("Simulated sidecar write failure")

    monkeypatch.setattr(insp, "atomic_write_json", failing_sidecar_write)

    with pytest.raises(RuntimeError, match="Simulated sidecar write failure"):
        quarantine_dataset(
            source_file,
            quarantine_dir=quarantine_dir,
            reason="Corrupted headers",
            operator="test_operator",
        )

    # No orphaned quarantined file or temporary file should linger
    files_in_quarantine = list(quarantine_dir.iterdir())
    assert len(files_in_quarantine) == 0


def test_atomic_write_text_preserves_permissions(tmp_path: Path):
    target = tmp_path / "permissions_test.txt"
    target.write_text("initial", encoding="utf-8")
    initial_mode = target.stat().st_mode

    # Perform atomic update
    atomic_write_text(target, "updated content")
    assert target.read_text(encoding="utf-8") == "updated content"
    assert target.stat().st_mode == initial_mode


def test_atomic_write_csv_streaming_and_newlines(tmp_path: Path):
    target = tmp_path / "streamed.csv"
    df = pd.DataFrame({"col_a": [10, 20], "col_b": ["x", "y"]})

    atomic_write_csv(target, df, index=False)
    assert target.is_file()

    # Verify no double carriage returns (\r\r\n) exist in binary representation
    raw_bytes = target.read_bytes()
    assert b"\r\r\n" not in raw_bytes
    loaded = pd.read_csv(target)
    assert len(loaded) == 2
    assert list(loaded["col_a"]) == [10, 20]

