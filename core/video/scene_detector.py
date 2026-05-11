"""Scene detection wrapper around PySceneDetect with safe fallback behavior."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Segment:
    start: float
    end: float


class SceneDetector:
    def detect(self, path: Path, sensitivity: float = 27.0) -> list[Segment]:
        try:
            from scenedetect import ContentDetector, SceneManager, open_video
        except ImportError:
            return []

        video = open_video(str(path))
        manager = SceneManager()
        manager.add_detector(ContentDetector(threshold=sensitivity))
        manager.detect_scenes(video)
        segments: list[Segment] = []
        for start, end in manager.get_scene_list():
            segments.append(Segment(start.get_seconds(), end.get_seconds()))
        return segments
