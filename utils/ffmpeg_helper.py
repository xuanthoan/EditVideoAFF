"""FFmpeg/FFprobe helpers.

The renderer must fail early with a clear message when FFmpeg is not bundled or
available on PATH. Returning a bare executable name caused Windows to raise
``WinError 2`` inside ``subprocess`` with no useful GUI feedback.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


class FFmpegNotFoundError(FileNotFoundError):
    """Raised when ffmpeg/ffprobe cannot be located."""


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def candidate_paths(name: str) -> list[Path]:
    exe_name = name if name.endswith(".exe") else f"{name}.exe"
    plain_name = name.removesuffix(".exe")
    roots = [app_root(), Path.cwd()]
    candidates: list[Path] = []
    for root in roots:
        candidates.extend([root / "bin" / exe_name, root / "bin" / plain_name, root / exe_name, root / plain_name])
    return candidates


def executable(name: str, *, required: bool = True) -> str:
    """Return an absolute executable path or raise a user-actionable error."""
    for candidate in candidate_paths(name):
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    path_match = shutil.which(name) or shutil.which(name.removesuffix(".exe"))
    if path_match:
        return path_match

    if required:
        searched = ", ".join(str(path) for path in candidate_paths(name)[:4])
        raise FFmpegNotFoundError(
            f"Không tìm thấy {name}. Hãy copy {name}.exe vào thư mục bin/ của phần mềm "
            f"hoặc cài FFmpeg và thêm vào PATH. Đã kiểm tra: {searched}"
        )
    return name


def validate_ffmpeg_pair() -> tuple[str, str]:
    """Validate both ffmpeg and ffprobe before rendering starts."""
    return executable("ffmpeg"), executable("ffprobe")


def subprocess_startupinfo():
    """Hide console windows for bundled Windows GUI builds."""
    if os.name != "nt":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo


def probe_duration(path: Path) -> float:
    cmd = [
        executable("ffprobe"),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, startupinfo=subprocess_startupinfo())
    return float(json.loads(result.stdout)["format"]["duration"])


def probe_video_size(path: Path) -> tuple[int, int]:
    cmd = [
        executable("ffprobe"),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, startupinfo=subprocess_startupinfo())
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise ValueError(f"No video stream found in {path}")
    width = int(streams[0]["width"])
    height = int(streams[0]["height"])
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid video size for {path}: {width}x{height}")
    return width, height
