"""Normalized layout helpers for resolution-independent overlays."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NormalizedLayoutEngine:
    reference_width: int = 1080
    reference_height: int = 1920

    def normalize_font_size(self, font_px: int) -> float:
        return max(0.005, float(font_px) / float(self.reference_height))

    def denormalize_font_size(self, font_ratio: float, output_height: int) -> int:
        return max(8, round(float(font_ratio) * float(output_height)))
