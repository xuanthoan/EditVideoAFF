"""Final export pipeline assembly."""
from __future__ import annotations

from core.pipeline.base import FilterGraph, RenderJob
from core.renderer.ffmpeg_builder import FFmpegBuilder


class FinalExportPipeline:
    name = "final_export"

    def enabled(self, state) -> bool:
        return True

    def apply(self, job: RenderJob, graph: FilterGraph) -> FilterGraph:
        graph.extra_args.extend(FFmpegBuilder.output_args(job.state.export))
        return graph
