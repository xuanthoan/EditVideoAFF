"""Serializable project state for the all-in-one production workflow."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

from .overlay import CropFocus
from .sticker_overlay import StickerOverlay
from .text_overlay import TextOverlay

AspectRatio = Literal["9:16", "1:1", "16:9"]
FadeCurve = Literal["linear", "smooth", "strong"]


PlatformPreset = Literal["TikTok", "Instagram Reels", "YouTube Shorts", "Custom"]


class WorkflowMode(str, Enum):
    PIPELINE_1 = "Pipeline 1 — Shuffle + Image"
    PIPELINE_2 = "Pipeline 2 — Shuffle + Image + Overlay"
    PIPELINE_3 = "Pipeline 3 — Shuffle + Overlay"
    PIPELINE_4 = "Pipeline 4 — Overlay Only"


@dataclass(slots=True)
class SceneShuffleSettings:
    enabled: bool = True
    sensitivity: float = 30.0
    random_mode: bool = True
    keep_first_segment: bool = True
    fallback_min_seconds: float = 3.0
    fallback_max_seconds: float = 5.0


@dataclass(slots=True)
class ImageCompositeSettings:
    enabled: bool = False
    image_pool: list[Path] = field(default_factory=list)
    image_height_percent: float = 35.0
    overlap_percent: float = 5.0
    crop_focus: CropFocus = "center"
    fade_curve: FadeCurve = "linear"
    auto_random_image: bool = True


@dataclass(slots=True)
class OverlaySettings:
    text_enabled: bool = False
    sticker_enabled: bool = False
    text: TextOverlay = field(default_factory=TextOverlay)
    sticker: StickerOverlay = field(default_factory=StickerOverlay)
    text_layers: list[TextOverlay] = field(default_factory=list)
    sticker_layers: list[StickerOverlay] = field(default_factory=list)

    def text_overlays(self) -> list[TextOverlay]:
        layers = [overlay for overlay in self.text_layers if overlay.active]
        if self.text_enabled and self.text.active and self.text not in layers:
            layers.insert(0, self.text)
        return layers[:20]

    def sticker_overlays(self) -> list[StickerOverlay]:
        layers = [overlay for overlay in self.sticker_layers if overlay.active]
        if self.sticker_enabled and self.sticker.active and self.sticker not in layers:
            layers.insert(0, self.sticker)
        return layers[:20]

    @property
    def enabled(self) -> bool:
        return bool(self.text_overlays() or self.sticker_overlays())


@dataclass(slots=True)
class ExportSettings:
    output_dir: Path = Path("output")
    aspect_ratio: AspectRatio = "9:16"
    crf: int = 18
    preset: str = "veryfast"
    auto_open_output: bool = False
    developer_mode: bool = False


@dataclass(slots=True)
class SafeAreaSettings:
    platform: PlatformPreset = "TikTok"
    enabled: bool = True
    snap_enabled: bool = True


@dataclass(slots=True)
class ProjectState:
    videos: list[Path] = field(default_factory=list)
    workflow_mode: WorkflowMode = WorkflowMode.PIPELINE_1
    scene_shuffle: SceneShuffleSettings = field(default_factory=SceneShuffleSettings)
    image_composite: ImageCompositeSettings = field(default_factory=ImageCompositeSettings)
    overlays: OverlaySettings = field(default_factory=OverlaySettings)
    export: ExportSettings = field(default_factory=ExportSettings)
    safe_area: SafeAreaSettings = field(default_factory=SafeAreaSettings)

    def render_count_label(self) -> str:
        return f"Render Video ({len(self.videos)})" if self.videos else "Render Video"
