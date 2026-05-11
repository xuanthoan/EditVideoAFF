"""Scene shuffle pipeline module.

Only video frames are shuffled. Audio is deliberately kept outside the shuffle
concat and reattached from the original timeline by the final FFmpeg command.
"""
from __future__ import annotations

from random import Random

from core.pipeline.base import FilterGraph, RenderJob, ShufflePlan, ShuffleSegment
from core.video.scene_detector import SceneDetector
from core.video.segmenter import Segmenter


class SceneShufflePipeline:
    name = "scene_shuffle"

    def __init__(self, detector: SceneDetector | None = None, random: Random | None = None) -> None:
        self.detector = detector or SceneDetector()
        self.random = random or Random()

    def enabled(self, state) -> bool:
        return state.scene_shuffle.enabled

    def apply(self, job: RenderJob, graph: FilterGraph) -> FilterGraph:
        settings = job.state.scene_shuffle
        scenes = self.detector.detect(job.input_path, settings.sensitivity)
        segments = Segmenter(settings.fallback_min_seconds, settings.fallback_max_seconds).ensure_segments(
            scenes, job.input_path
        )
        if settings.random_mode and len(segments) > 1:
            head, tail = segments[0], segments[1:]
            self.random.shuffle(tail)
            segments = [head, *tail] if settings.keep_first_segment else tail + [head]

        graph.shuffle_plan = ShufflePlan([ShuffleSegment(segment.start, segment.end) for segment in segments])
        graph.debug_events.append(f"[SHUFFLE] segment_count={len(segments)} order={graph.shuffle_plan.order_summary}")

        v_labels: list[str] = []
        for idx, segment in enumerate(segments):
            v = f"shv{idx}"
            graph.add_node(
                f"shuffle_trim_{idx}",
                f"[{graph.video_label}]trim=start={segment.start:.3f}:end={segment.end:.3f},setpts=PTS-STARTPTS[{v}]",
                None,
            )
            v_labels.append(f"[{v}]")
        out_v = "shuffled_v"
        graph.add_node("shuffle_concat", "".join(v_labels) + f"concat=n={len(segments)}:v=1:a=0[{out_v}]", out_v)
        graph.audio_label = "original_audio" if job.original_audio_path else "0:a?"
        graph.extra_args.extend(["-fps_mode", "passthrough", "-fflags", "+genpts", "-shortest"])
        return graph
