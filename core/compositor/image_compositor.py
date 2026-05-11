"""FFmpeg image compositor graph builder."""
from __future__ import annotations

from pathlib import Path
from random import Random

from core.pipeline.base import LayoutPlan
from models.project_state import ImageCompositeSettings


class ImageCompositor:
    def __init__(self) -> None:
        self.random = Random()

    @staticmethod
    def pick_image(pool: list[Path], salt: str) -> Path:
        if not pool:
            raise ValueError("image pool is empty")
        return sorted(pool, key=lambda p: p.as_posix())[hash(salt) % len(pool)]

    def build_plan(self, settings: ImageCompositeSettings, video_width: int, video_height: int) -> LayoutPlan:
        image_percent = self._clamp_percent(settings.image_height_percent, 20, 60)
        image_h = self._even_pixels(video_height * image_percent / 100)
        overlap_percent = min(max(settings.overlap_percent, 0), min(20, image_percent))
        overlap_h = 0 if overlap_percent <= 0 else min(self._even_pixels(video_height * overlap_percent / 100), image_h)
        visible_video_total = video_height - (image_h - overlap_h)
        offset_y = -(video_height - visible_video_total)
        main_video_h = visible_video_total - overlap_h
        image_top = video_height - image_h
        fade_start = image_top
        source_y = max(0, min(video_height - overlap_h, fade_start - offset_y))
        return LayoutPlan(
            canvas_width=video_width,
            canvas_height=video_height,
            image_h=image_h,
            overlap_h=overlap_h,
            visible_video_total=visible_video_total,
            offset_y=offset_y,
            main_video_h=main_video_h,
            image_top=image_top,
            fade_start=fade_start,
            source_y=source_y,
        )

    def build_nodes(
        self,
        video_label: str,
        image_label: str,
        settings: ImageCompositeSettings,
        video_width: int,
        video_height: int,
    ) -> tuple[list[tuple[str, str, str | None]], str, LayoutPlan]:
        out = "composited_v"
        plan = self.build_plan(settings, video_width, video_height)
        focus = {"top": "0", "center": "(ih-oh)/2", "bottom": "ih-oh"}[settings.crop_focus]
        nodes: list[tuple[str, str, str | None]] = [
            (
                "layout_image_prepare",
                f"[{image_label}]scale=w={video_width}:h=-1,crop=w={video_width}:h={plan.image_h}:x=(iw-{video_width})/2:y={focus}[bg]",
                None,
            ),
            ("layout_canvas", f"color=c=black@0:s={video_width}x{video_height}:d=1[canvas]", None),
            ("layout_base_image", f"[canvas][bg]overlay=x=0:y={plan.image_top}[base]", None),
        ]
        if plan.overlap_h <= 0:
            nodes.extend(
                [
                    ("layout_main_video", f"[{video_label}]setpts=PTS-STARTPTS[mainv]", None),
                    ("layout_main_overlay", f"[base][mainv]overlay=x=0:y={plan.offset_y}[{out}]", out),
                ]
            )
            return nodes, out, plan

        main_source_y = max(0, -plan.offset_y)
        nodes.extend(
            [
                ("layout_video_split", f"[{video_label}]setpts=PTS-STARTPTS,split=2[main_src][fade_src]", None),
                (
                    "layout_main_region",
                    f"[main_src]crop=w={video_width}:h={plan.main_video_h}:x=0:y={main_source_y}[mainv]",
                    None,
                ),
                (
                    "layout_fade_region",
                    f"[fade_src]crop=w={video_width}:h={plan.overlap_h}:x=0:y={plan.source_y},"
                    f"format=yuva420p,geq=lum='p(X,Y)':a='255*(1-(Y/{plan.overlap_h}))'[fade]",
                    None,
                ),
                ("layout_main_overlay", f"[base][mainv]overlay=x=0:y=0[main_layer]", None),
                ("layout_fade_overlay", f"[main_layer][fade]overlay=x=0:y={plan.fade_start}[{out}]", out),
            ]
        )
        return nodes, out, plan

    def build_filter(
        self,
        video_label: str,
        image_label: str,
        settings: ImageCompositeSettings,
        video_width: int,
        video_height: int,
    ) -> tuple[str, str]:
        nodes, out, _plan = self.build_nodes(video_label, image_label, settings, video_width, video_height)
        return ";".join(chain for _name, chain, _output in nodes), out

    @staticmethod
    def _even_pixels(value: float) -> int:
        return max(2, int(value) // 2 * 2)

    @staticmethod
    def _clamp_percent(value: float, minimum: float, maximum: float) -> float:
        return min(max(float(value), minimum), maximum)
