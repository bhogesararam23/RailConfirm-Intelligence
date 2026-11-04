"""Unit tests for the shared atomic file I/O utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from railconfirm.data._io import atomic_write_json, atomic_write_text


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
    import os

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
