"""Sticker overlay model."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .overlay import OverlayBase


@dataclass(slots=True)
class StickerOverlay(OverlayBase):
    path: Path | None = None
    scale: float = 0.16
    rotation: float = 0.0

    @property
    def active(self) -> bool:
        return self.enabled and self.path is not None
