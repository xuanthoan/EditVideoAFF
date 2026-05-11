"""Shared overlay data models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal


class MotionPreset(str, Enum):
    NONE = "None"
    FADE_IN = "Fade In"
    FADE_OUT = "Fade Out"
    BOUNCE = "Bounce"
    POP = "Pop"
    SCALE = "Scale"
    SCALE_UP = "Scale Up"
    SCALE_DOWN = "Scale Down"
    FLOAT = "Float"
    SHAKE = "Shake"
    SLIDE_LEFT = "Slide Left"
    SLIDE_RIGHT = "Slide Right"
    SLIDE_UP = "Slide Up"
    SLIDE_DOWN = "Slide Down"
    PULSE = "Pulse"
    ROTATE_FLOAT = "Rotate Float"
    DRIFT = "Drift"
    # Backward-compatible aliases for older project states/UI values.
    FADE = "Fade"
    SLIDE = "Slide"
    ZOOM = "Zoom"
    ELASTIC = "Elastic"

    @classmethod
    def from_label(cls, label: str) -> "MotionPreset":
        for preset in cls:
            if preset.value == label:
                return preset
        return cls.NONE


@dataclass(slots=True)
class OverlayBase:
    enabled: bool = True
    x: float = 0.5
    y: float = 0.5
    start_time: float = 0.0
    end_time: float = 3.0
    duration: float = 3.0
    motion: MotionPreset = MotionPreset.NONE

    def set_timing(self, start_time: float, end_time: float) -> None:
        """Store a compact timeline timing range and derived duration."""
        self.start_time = max(0.0, float(start_time))
        self.end_time = max(self.start_time + 0.1, float(end_time))
        self.duration = self.end_time - self.start_time

    def set_full_duration(self, video_duration: float) -> None:
        """Default newly created overlays to the whole source duration."""
        self.set_timing(0.0, max(0.1, float(video_duration)))

    def active_at(self, current_time: float) -> bool:
        return self.enabled and self.start_time <= current_time <= self.end_time

    def clamp_to_safe_area(self, width: int, height: int) -> None:
        left = width * 0.05
        right = width - width * 0.05
        top = height * 0.08
        bottom = height - height * 0.16
        self.x = min(max(self.x * width, left), right) / width
        self.y = min(max(self.y * height, top), bottom) / height


CropFocus = Literal["top", "center", "bottom"]


@dataclass(slots=True)
class StickerAsset:
    path: Path
    scale: float = 0.16
    rotation: float = 0.0
