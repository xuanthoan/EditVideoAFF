"""Segment fallback logic for shuffle mode."""
from __future__ import annotations

from pathlib import Path

from core.video.scene_detector import Segment
from utils.ffmpeg_helper import probe_duration


class Segmenter:
    def __init__(self, fallback_min_seconds: float = 3.0, fallback_max_seconds: float = 5.0) -> None:
        self.fallback_min_seconds = fallback_min_seconds
        self.fallback_max_seconds = fallback_max_seconds

    def ensure_segments(self, detected: list[Segment], path: Path) -> list[Segment]:
        if len(detected) > 1:
            return detected
        duration = max(probe_duration(path), self.fallback_min_seconds)
        step = (self.fallback_min_seconds + self.fallback_max_seconds) / 2
        segments: list[Segment] = []
        cursor = 0.0
        while cursor < duration:
            end = min(cursor + step, duration)
            if end - cursor > 0.25:
                segments.append(Segment(cursor, end))
            cursor = end
        return segments or [Segment(0, duration)]
