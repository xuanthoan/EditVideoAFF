"""Image compositor pipeline module."""
from __future__ import annotations

from core.compositor.image_compositor import ImageCompositor
from core.pipeline.base import FilterGraph, RenderJob


class ImageCompositePipeline:
    name = "image_composite"

    def enabled(self, state) -> bool:
        return state.image_composite.enabled and bool(state.image_composite.image_pool)

    def apply(self, job: RenderJob, graph: FilterGraph) -> FilterGraph:
        image = ImageCompositor.pick_image(job.state.image_composite.image_pool, job.input_path.name)
        graph.inputs.extend(["-loop", "1", "-i", str(image)])
        image_input_index = 1 + (len(graph.inputs) // 4) - 1
        nodes, output, plan = ImageCompositor().build_nodes(
            video_label=graph.video_label,
            image_label=f"{image_input_index}:v",
            settings=job.state.image_composite,
            video_width=job.video_width,
            video_height=job.video_height,
        )
        graph.layout_plan = plan
        graph.debug_events.append(
            "[LAYOUT] "
            f"image_h={plan.image_h} overlap_h={plan.overlap_h} offset_y={plan.offset_y} "
            f"main_video_h={plan.main_video_h} fade_start={plan.fade_start} source_y={plan.source_y}"
        )
        graph.debug_events.append(
            "[FADE] "
            f"image_h={plan.image_h} overlap_h={plan.overlap_h} "
            f"visible_video_total={plan.visible_video_total} offset_y={plan.offset_y} "
            f"fade_start={plan.fade_start} source_y={plan.source_y} fade_overlay_y={plan.fade_start}"
        )
        for name, chain, output_label in nodes:
            graph.add_node(name, chain, output_label)
        graph.video_label = output
        return graph
