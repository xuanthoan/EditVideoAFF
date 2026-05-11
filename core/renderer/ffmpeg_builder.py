"""Build final single-encode FFmpeg commands."""
from __future__ import annotations

from core.pipeline.base import FilterGraph, RenderJob
from models.project_state import ExportSettings
from utils.ffmpeg_helper import executable


class FFmpegBuilder:
    def build(self, job: RenderJob, graph: FilterGraph) -> list[str]:
        cmd = [executable("ffmpeg"), "-y", "-i", str(job.input_path), *graph.inputs]
        original_audio_index: int | None = None
        if job.original_audio_path:
            original_audio_index = 1 + sum(1 for token in graph.inputs if token == "-i")
            cmd.extend(["-i", str(job.original_audio_path)])
        if graph.chains:
            cmd.extend(["-filter_complex", graph.filter_complex(), "-map", f"[{graph.video_label}]"])
            if graph.audio_label == "original_audio" and original_audio_index is not None:
                cmd.extend(["-map", f"{original_audio_index}:a:0"])
            elif graph.audio_label:
                cmd.extend(["-map", f"[{graph.audio_label}]" if not graph.audio_label.endswith("?") else "0:a?"])
        else:
            cmd.extend(["-map", "0:v", "-map", "0:a?"])
        cmd.extend(graph.extra_args)
        cmd.append(str(job.output_path))
        return cmd

    @staticmethod
    def output_args(settings: ExportSettings) -> list[str]:
        ratio_filters = {
            "9:16": "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            "1:1": "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2",
            "16:9": "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        }
        return [
            "-c:v",
            "libx264",
            "-preset",
            settings.preset,
            "-crf",
            str(settings.crf),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
        ]
