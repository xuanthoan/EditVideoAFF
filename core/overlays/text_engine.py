"""FFmpeg overlay engine for Qt-rendered social typography assets."""
from __future__ import annotations

import tempfile
from pathlib import Path

from core.overlays.motion_engine import MotionEngine
from core.overlays.template_manager import TemplateManager
from core.overlays.typography_engine import SocialTypographyRenderer
from models.text_overlay import TextOverlay


class TextEngine:
    def __init__(self) -> None:
        self.templates = TemplateManager()
        self.motion = MotionEngine()
        self.typography = SocialTypographyRenderer()
        self._asset_cache: dict[tuple[str, str, int, int, int], Path] = {}

    def build_filter(
        self,
        video_label: str,
        text_label: str,
        overlay: TextOverlay,
        suffix: str = "",
    ) -> tuple[str, str]:
        out = f"text_v{suffix}"
        prepared = f"text_src{suffix}"
        x, y, enable = self.motion.position_expr(overlay.x, overlay.y, overlay.motion, overlay.start_time, overlay.end_time)
        width_expr, height_expr = self.motion.region_scale_expr("iw", overlay.motion, overlay.start_time, overlay.end_time)
        alpha_filter = self.motion.alpha_filter(overlay.motion, overlay.start_time, overlay.end_time)
        chain = (
            f"[{text_label}]scale=w='{width_expr}':h='{height_expr}':eval=frame{alpha_filter}[{prepared}];"
            f"[{video_label}][{prepared}]overlay=x={x}:y={y}:enable='{enable}'[{out}]"
        )
        return chain, out

    def render_asset(
        self,
        overlay: TextOverlay,
        canvas_width: int,
        canvas_height: int,
        temp_files: list[Path] | None = None,
    ) -> Path:
        template = self.templates.get(overlay.template)
        key = (overlay.text, overlay.template, overlay.font_size, canvas_width, canvas_height)
        path = self._asset_cache.get(key)
        if path is None or not path.exists():
            path = self._new_asset_path()
            self.typography.render_png(path, overlay.text, template, overlay.font_size, canvas_width, canvas_height)
            self._asset_cache[key] = path
        if temp_files is not None and path not in temp_files:
            temp_files.append(path)
        return path

    @staticmethod
    def _new_asset_path() -> Path:
        handle = tempfile.NamedTemporaryFile(prefix="autovideoaff_text_region_", suffix=".png", delete=False)
        path = Path(handle.name)
        handle.close()
        return path
