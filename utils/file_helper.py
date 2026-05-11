"""File-system helpers."""
from __future__ import annotations

from pathlib import Path

from utils.ffmpeg_helper import app_root

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def output_directory(output_dir: Path) -> Path:
    """Resolve output directories against the app root, not an arbitrary CWD."""
    return output_dir if output_dir.is_absolute() else app_root() / output_dir


def output_directory_for_videos(videos: list[Path], fallback: Path = Path("output")) -> Path:
    """Use the first imported video's folder as the batch output root."""
    if videos:
        return videos[0].resolve().parent / "output"
    return output_directory(fallback)


def safe_output_path(output_dir: Path, source: Path) -> Path:
    resolved_dir = output_dir.resolve() if output_dir.is_absolute() else output_directory(output_dir).resolve()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    candidate = resolved_dir / f"{source.stem}.mp4"
    index = 1
    while candidate.exists():
        candidate = resolved_dir / f"{source.stem}_{index:03d}.mp4"
        index += 1
    return candidate


def temporary_output_path(final_output: Path) -> Path:
    return final_output.with_name(f".{final_output.stem}.rendering{final_output.suffix}")


def collect_videos(folder: Path) -> list[Path]:
    return sorted(path for path in folder.iterdir() if path.suffix.lower() in VIDEO_EXTENSIONS)
