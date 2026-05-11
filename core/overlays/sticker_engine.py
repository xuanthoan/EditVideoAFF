"""Sticker overlay filter builder."""
from __future__ import annotations

from core.overlays.motion_engine import MotionEngine
from core.overlays.transform import OverlayTransform
from models.sticker_overlay import StickerOverlay


class StickerEngine:
    def __init__(self) -> None:
        self.motion = MotionEngine()

    def build_filter(self, video_label: str, sticker_label: str, overlay: StickerOverlay, suffix: str = "", canvas_width: int = 1080) -> tuple[str, str]:
        out = f"sticker_v{suffix}"
        prepared = f"sticker_src{suffix}"
        transform = OverlayTransform.from_overlay(overlay)
        x, y, enable = self.motion.position_expr(transform.x, transform.y, transform.motion, transform.start_time, transform.end_time)
        width_expr, height_expr = self.motion.sticker_scale_expr(transform.scale_ratio, transform.motion, canvas_width, transform.start_time, transform.end_time)
        alpha_filter = self.motion.alpha_filter(transform.motion, transform.start_time, transform.end_time)
        rotation_expr = self.motion.rotation_expr(overlay.rotation, transform.motion, transform.start_time)
        chain = (
            f"[{sticker_label}]scale=w='{width_expr}':h='{height_expr}':eval=frame,"
            f"rotate='{rotation_expr}':ow=rotw(iw):oh=roth(ih):c=none"
            f"{alpha_filter}[{prepared}];"
            f"[{video_label}][{prepared}]overlay=x={x}:y={y}:enable='{enable}'[{out}]"
        )
        return chain, out

