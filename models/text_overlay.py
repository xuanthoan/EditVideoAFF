"""Text overlay model."""
from __future__ import annotations

from dataclasses import dataclass

from .overlay import OverlayBase


@dataclass(slots=True)
class TextOverlay(OverlayBase):
    text: str = ""
    template: str = "Orange White"
    font_size: int = 96

    @property
    def active(self) -> bool:
        return self.enabled and bool(self.text.strip())
