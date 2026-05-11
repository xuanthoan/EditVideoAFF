"""Shared normalized overlay transform helpers for preview and FFmpeg export."""
from __future__ import annotations

from dataclasses import dataclass

from models.overlay import MotionPreset, OverlayBase
from models.sticker_overlay import StickerOverlay


@dataclass(frozen=True, slots=True)
class OverlayTransform:
    x: float
    y: float
    scale_ratio: float = 0.0
    rotation: float = 0.0
    anchor_x: float = 0.5
    anchor_y: float = 0.5
    motion: MotionPreset = MotionPreset.NONE
    start_time: float = 0.0
    end_time: float = 0.0

    @classmethod
    def from_overlay(cls, overlay: OverlayBase) -> "OverlayTransform":
        return cls(
            x=min(max(float(overlay.x), 0.0), 1.0),
            y=min(max(float(overlay.y), 0.0), 1.0),
            scale_ratio=cls.scale_ratio_for(overlay),
            rotation=float(getattr(overlay, "rotation", 0.0)),
            motion=overlay.motion,
            start_time=overlay.start_time,
            end_time=overlay.end_time,
        )

    @staticmethod
    def scale_ratio_for(overlay: OverlayBase) -> float:
        if isinstance(overlay, StickerOverlay):
            return min(max(float(overlay.scale), 0.01), 1.0)
        return 0.0

    def center_pixels(self, canvas_width: int, canvas_height: int) -> tuple[float, float]:
        return self.x * canvas_width, self.y * canvas_height

    def sticker_width_pixels(self, canvas_width: int) -> int:
        return max(1, round(canvas_width * self.scale_ratio))
