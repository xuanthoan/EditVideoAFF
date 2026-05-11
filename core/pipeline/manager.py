"""Module pipeline system orchestration."""
from __future__ import annotations

from pathlib import Path

from core.pipeline.base import FilterGraph, RenderJob
from core.pipeline.compositor_pipeline import ImageCompositePipeline
from core.pipeline.export_pipeline import FinalExportPipeline
from core.pipeline.overlay_pipeline import OverlayPipeline
from core.pipeline.shuffle_pipeline import SceneShufflePipeline
from core.renderer.ffmpeg_builder import FFmpegBuilder
from models.project_state import ProjectState, WorkflowMode
from utils.ffmpeg_helper import probe_video_size


class PipelineManager:
    """Builds one enabled workflow mode and merges modules into one FFmpeg command."""

    def __init__(self) -> None:
        self.shuffle = SceneShufflePipeline()
        self.image = ImageCompositePipeline()
        self.overlay = OverlayPipeline()
        self.export = FinalExportPipeline()
        self.last_temp_files: list[Path] = []
        self.last_debug_events: list[str] = []

    def active_modules(self, state: ProjectState):
        modules = []
        if state.workflow_mode in {WorkflowMode.PIPELINE_1, WorkflowMode.PIPELINE_2, WorkflowMode.PIPELINE_3}:
            if self.shuffle.enabled(state):
                modules.append(self.shuffle)
        if state.workflow_mode in {WorkflowMode.PIPELINE_1, WorkflowMode.PIPELINE_2}:
            if self.image.enabled(state):
                modules.append(self.image)
        if state.workflow_mode in {WorkflowMode.PIPELINE_2, WorkflowMode.PIPELINE_3, WorkflowMode.PIPELINE_4}:
            if self.overlay.enabled(state):
                modules.append(self.overlay)
        modules.append(self.export)
        return modules

    def build_command(
        self,
        input_path: Path,
        output_path: Path,
        state: ProjectState,
        original_audio_path: Path | None = None,
    ) -> list[str]:
        video_width, video_height = probe_video_size(input_path)
        job = RenderJob(
            input_path=input_path,
            output_path=output_path,
            state=state,
            original_audio_path=original_audio_path,
            video_width=video_width,
            video_height=video_height,
        )
        graph = FilterGraph()
        try:
            for module in self.active_modules(state):
                graph = module.apply(job, graph)
            graph.debug_events.append(
                f"[FINAL] node_count={len(graph.nodes)} resolution={job.canvas_size} output={output_path.name}"
            )
            return FFmpegBuilder().build(job, graph)
        finally:
            self.last_temp_files = list(graph.temp_files)
            self.last_debug_events = list(graph.debug_events)
