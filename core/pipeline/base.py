"""Pipeline primitives for queue-based single-export rendering."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from models.project_state import ProjectState


@dataclass(frozen=True, slots=True)
class FilterNode:
    """One named FFmpeg filter node in the final single-encode graph."""

    name: str
    chain: str
    output_label: str | None = None


@dataclass(frozen=True, slots=True)
class ShuffleSegment:
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class ShufflePlan:
    segments: list[ShuffleSegment]

    @property
    def order_summary(self) -> str:
        return ", ".join(f"{segment.start:.2f}-{segment.end:.2f}" for segment in self.segments)


@dataclass(frozen=True, slots=True)
class LayoutPlan:
    canvas_width: int
    canvas_height: int
    image_h: int
    overlap_h: int
    visible_video_total: int
    offset_y: int
    main_video_h: int
    image_top: int
    fade_start: int
    source_y: int


@dataclass(slots=True)
class FilterGraph:
    inputs: list[str] = field(default_factory=list)
    nodes: list[FilterNode] = field(default_factory=list)
    video_label: str = "0:v"
    audio_label: str | None = "0:a?"
    extra_args: list[str] = field(default_factory=list)
    temp_files: list[Path] = field(default_factory=list)
    shuffle_plan: ShufflePlan | None = None
    layout_plan: LayoutPlan | None = None
    debug_events: list[str] = field(default_factory=list)

    @property
    def chains(self) -> list[str]:
        return [node.chain for node in self.nodes]

    def add_node(self, name: str, chain: str, output_label: str | None = None) -> None:
        self.nodes.append(FilterNode(name=name, chain=chain, output_label=output_label))
        if output_label:
            self.video_label = output_label

    def add_chain(self, chain: str, output_label: str) -> None:
        self.add_node(f"node_{len(self.nodes) + 1}", chain, output_label)

    def filter_complex(self) -> str:
        return ";".join(self.chains)


@dataclass(slots=True)
class RenderJob:
    input_path: Path
    output_path: Path
    state: ProjectState
    original_audio_path: Path | None = None
    video_width: int = 1080
    video_height: int = 1920

    @property
    def canvas_size(self) -> str:
        return f"{self.video_width}x{self.video_height}"


class PipelineModule(Protocol):
    name: str

    def enabled(self, state: ProjectState) -> bool: ...

    def apply(self, job: RenderJob, graph: FilterGraph) -> FilterGraph: ...
