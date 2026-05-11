"""Resolution-independent safe-area calculations for social video layouts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NormalizedRect:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class SafeAreaResult:
    text_safe_rect: NormalizedRect
    sticker_safe_rect: NormalizedRect
    ui_exclusion_zones: tuple[NormalizedRect, ...]


class SafeAreaEngine:
    """Compute TikTok/Reels/Shorts-safe rectangles using normalized percentages."""

    PRESETS = {
        "TikTok": {"text_width": 0.74, "sticker_width": 0.88, "top": 0.10, "bottom": 0.18},
        "Instagram Reels": {"text_width": 0.78, "sticker_width": 0.90, "top": 0.10, "bottom": 0.16},
        "YouTube Shorts": {"text_width": 0.80, "sticker_width": 0.90, "top": 0.09, "bottom": 0.16},
        "Custom": {"text_width": 0.74, "sticker_width": 0.88, "top": 0.10, "bottom": 0.18},
    }

    def calculate(self, video_width: int, video_height: int, aspect_ratio: str = "9:16", platform: str = "TikTok") -> SafeAreaResult:
        preset = self.PRESETS.get(platform, self.PRESETS["TikTok"])
        text_width = preset["text_width"]
        sticker_width = preset["sticker_width"]
        top = preset["top"]
        bottom = preset["bottom"]
        text_rect = NormalizedRect((1 - text_width) / 2, top, text_width, 1 - top - bottom)
        sticker_rect = NormalizedRect((1 - sticker_width) / 2, top * 0.75, sticker_width, 1 - top * 0.75 - bottom * 0.8)
        exclusions = (
            NormalizedRect(0.86, 0.30, 0.12, 0.42),  # right-side social buttons
            NormalizedRect(0.00, 0.84, 1.00, 0.12),  # caption/music area
            NormalizedRect(0.00, 0.96, 1.00, 0.04),  # navigation area
        )
        return SafeAreaResult(text_rect, sticker_rect, exclusions)
