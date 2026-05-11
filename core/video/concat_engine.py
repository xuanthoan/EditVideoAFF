"""Concat demuxer helper for workflows that need stream-copy diagnostics."""
from __future__ import annotations

from pathlib import Path


def write_concat_file(paths: list[Path], destination: Path) -> Path:
    destination.write_text("".join(f"file '{path.as_posix()}'\n" for path in paths), encoding="utf-8")
    return destination
