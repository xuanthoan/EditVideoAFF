"""Unified text/sticker overlay pipeline module."""
from __future__ import annotations

from core.overlays.sticker_engine import StickerEngine
from core.overlays.text_engine import TextEngine
from core.overlays.transform import OverlayTransform
from core.pipeline.base import FilterGraph, RenderJob


class OverlayPipeline:
    name = "overlay"

    def __init__(self) -> None:
        self.text_engine = TextEngine()
        self.sticker_engine = StickerEngine()

    def enabled(self, state) -> bool:
        return state.overlays.enabled

    def apply(self, job: RenderJob, graph: FilterGraph) -> FilterGraph:
        overlays = job.state.overlays
        for index, text_overlay in enumerate(overlays.text_overlays(), start=1):
            asset_path = self.text_engine.render_asset(
                text_overlay,
                job.video_width,
                job.video_height,
                temp_files=graph.temp_files,
            )
            graph.debug_events.append(f"[OVERLAY] text index={index} asset={asset_path.name} region=minimal_bbox")
            graph.inputs.extend(["-loop", "1", "-i", str(asset_path)])
            if "-shortest" not in graph.extra_args:
                graph.extra_args.append("-shortest")
            text_index = sum(1 for token in graph.inputs if token == "-i")
            chain, output = self.text_engine.build_filter(
                graph.video_label,
                f"{text_index}:v",
                text_overlay,
                suffix=f"_{index}",
            )
            graph.add_chain(chain, output)
        for index, sticker_overlay in enumerate(overlays.sticker_overlays(), start=1):
            transform = OverlayTransform.from_overlay(sticker_overlay)
            graph.debug_events.append(
                f"[OVERLAY] sticker index={index} target_width={transform.sticker_width_pixels(job.video_width)} "
                f"center=({transform.x:.3f},{transform.y:.3f}) rotation={transform.rotation:.1f}"
            )
            graph.inputs.extend(["-i", str(sticker_overlay.path)])
            sticker_index = sum(1 for token in graph.inputs if token == "-i")
            chain, output = self.sticker_engine.build_filter(
                graph.video_label,
                f"{sticker_index}:v",
                sticker_overlay,
                suffix=f"_{index}",
                canvas_width=job.video_width,
            )
            graph.add_chain(chain, output)
        return graph
