"""Text overlay model."""
from __future__ import annotations

from dataclasses import dataclass

from core.normalized_layout_engine import NormalizedLayoutEngine
from .overlay import OverlayBase


@dataclass(slots=True)
class TextOverlay(OverlayBase):
    text: str = ""
    template: str = "Orange White"
    font_size: int = 96
    font_ratio: float = 96 / 1920

    @property
    def active(self) -> bool:
        return self.enabled and bool(self.text.strip())

    def effective_font_size(self, output_height: int) -> int:
        if self.font_ratio <= 0:
            self.font_ratio = NormalizedLayoutEngine().normalize_font_size(self.font_size)
        return NormalizedLayoutEngine().denormalize_font_size(self.font_ratio, output_height)
