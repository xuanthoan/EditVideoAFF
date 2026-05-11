# FILE_STRUCTURE.md — Project File and Module Guide

_Last updated: 2026-05-09_

This file explains what each major file or directory is responsible for. Use it to navigate the codebase quickly.

## Root Files

### `main.py`

PySide6 application entry point. Creates `QApplication`, instantiates `MainWindow`, and starts the GUI event loop.

### `README.md`

User-facing overview and basic project instructions.

### `ARCHITECTURE.md`

Primary architecture reference describing the current implementation, project goals, state model, workflow modes, render graph, GUI, output routing, and known risks.

### `RENDER_PIPELINE.md`

Detailed documentation for the multi-stage logic pipeline and single-final-encode render flow.

### `ANIMATION_SYSTEM.md`

Documentation for overlay coordinates, typography, sticker, motion, preview/export parity, and current animation risks.

### `FFmpeg_PIPELINE.md`

Documentation for FFmpeg/FFprobe discovery, probing, command building, input mapping, filtergraph patterns, and audio/no-audio requirements.

### `PROJECT_STATUS.md`

Current project status, completed features, important recent changes, and next work order.

### `BUGS.md`

Detailed known bug and risk register.

### `NEXT_SESSION_HANDOFF.md`

Compact handoff summary designed to paste into a future chat/session.

### `CURRENT_TASK.md`

Immediate next development priorities and acceptance criteria.

### `DECISIONS.md`

Architecture/product decisions that should not be reversed accidentally.

### `AI_AGENT_RULES.md`

Rules and guardrails for future AI coding agents.

### `TESTING.md`

Test plan, validation matrix, and suggested automated/manual checks.

### `KNOWN_ISSUES.md`

Quick active bug list.

### `AutoVideoAFF.spec`

PyInstaller packaging specification.

### `requirements.txt`

Runtime Python dependencies.

## `models/`

State and data models. These objects are shared by GUI, pipeline, preview, and renderer.

### `models/project_state.py`

Main state model:

- `ProjectState`
- `WorkflowMode`
- `SceneShuffleSettings`
- `ImageCompositeSettings`
- `OverlaySettings`
- `ExportSettings`
- `SafeAreaSettings`

### `models/overlay.py`

Base overlay model and enums/common types such as motion preset and crop focus.

### `models/text_overlay.py`

Text overlay dataclass: text content, template, font size, normalized position, timing, motion.

### `models/sticker_overlay.py`

Sticker overlay dataclass: path, normalized position, normalized canvas-width scale, rotation, timing, motion.

## `core/pipeline/`

Pipeline orchestration and filtergraph primitives.

### `core/pipeline/base.py`

Core render graph primitives:

- `FilterNode`
- `ShuffleSegment`
- `ShufflePlan`
- `LayoutPlan`
- `FilterGraph`
- `RenderJob`
- `PipelineModule`

### `core/pipeline/manager.py`

Selects active modules for the chosen workflow mode and builds the final FFmpeg command.

### `core/pipeline/shuffle_pipeline.py`

Creates video-only scene shuffle graph nodes and stores shuffle metadata.

### `core/pipeline/compositor_pipeline.py`

Adds selected image input and image compositor/fade graph nodes.

### `core/pipeline/overlay_pipeline.py`

Adds text/sticker overlay inputs and graph nodes on top of the current final canvas label.

### `core/pipeline/export_pipeline.py`

Adds final export/codec arguments.

## `core/compositor/`

Image layout and viewport fade implementation.

### `core/compositor/image_compositor.py`

Computes `LayoutPlan` and builds image/video/fade filter nodes. Key file for overlap fade issues.

### `core/compositor/fade_mask.py`

Small fade-mask helper placeholder/module.

## `core/overlays/`

Text, sticker, typography, transform, and motion logic.

### `core/overlays/template_manager.py`

Built-in social text templates and random template selection.

### `core/overlays/typography_engine.py`

Qt/QPainter typography renderer for minimal transparent text PNG regions.

### `core/overlays/text_engine.py`

Renders text assets and builds FFmpeg overlay filters for text regions.

### `core/overlays/sticker_engine.py`

Builds FFmpeg scale/rotate/alpha/overlay filters for sticker assets.

### `core/overlays/motion_engine.py`

Shared motion expression and preview helper logic. Key file for Fade/Pop/Scale bugs.

### `core/overlays/transform.py`

Shared normalized overlay transform helper, including canvas-relative sticker width calculation.

## `core/renderer/`

Batch rendering, command building, and preview frame extraction.

### `core/renderer/batch_renderer.py`

Sequential batch render loop, output paths, audio extraction, process execution, temp cleanup, verification, and logs.

### `core/renderer/ffmpeg_builder.py`

Builds final FFmpeg command from `RenderJob` and `FilterGraph`. Key file for no-audio command bugs.

### `core/renderer/preview_renderer.py`

Extracts first valid preview frame from video using FFmpeg.

## `core/video/`

Scene detection and segmentation utilities.

### `core/video/scene_detector.py`

PySceneDetect wrapper that returns scene segments.

### `core/video/segmenter.py`

Fallback segment generation when scene detection returns too few segments.

### `core/video/concat_engine.py`

Concat-related helper placeholder/module.

### `core/video/timestamp_manager.py`

Timestamp/PTS related constants for FFmpeg command generation.

## `core/safe_area_engine.py`

Computes normalized platform-safe areas and UI exclusion zones for TikTok/Reels/Shorts.

## `core/render_engine.py` and `core/workflow_manager.py`

These files may be introduced later if the project moves toward a higher-level service layer. Current implementation primarily uses `PipelineManager` and `BatchRenderer`.

## `gui/`

PySide6 user interface.

### `gui/main_window.py`

Main app shell, 3-column layout, render thread, state sync, preview/timeline wiring.

### `gui/queue_panel.py`

Video queue UI: add files/folder, remove, clear, select.

### `gui/workflow_panel.py`

Right workflow controls and pipeline-dependent UI locking.

### `gui/preview_canvas.py`

Preview display, safe area drawing, overlay drawing, drag/snap, live text/sticker preview.

### `gui/mini_timeline.py`

Compact overlay-only timeline with playhead, timing blocks, visibility, selection.

### `gui/export_panel.py`

Reusable export panel/control primitives.

### `gui/timeline_panel.py`

Placeholder/light wrapper for timeline panel concepts.

### `gui/toolbar.py`

Toolbar placeholder/basic toolbar component.

## `utils/`

Utility modules.

### `utils/ffmpeg_helper.py`

Finds FFmpeg/FFprobe, validates availability, runs ffprobe helpers. Add `probe_has_audio()` here.

### `utils/file_helper.py`

Output path logic, safe output naming, temporary output naming.

### `utils/process_manager.py`

Subprocess lifecycle wrapper with stop support.

### `utils/image_cache.py`

Image cache helper.

### `utils/logger.py`

Small logging helper.

## `assets/`

Static application assets.

### `assets/fonts/README.md`

Documents expected bundled font files. Actual licensed font files still need to be added.

## `bin/`

Expected location for bundled FFmpeg binaries in local/dev/distribution builds:

- `ffmpeg.exe`
- `ffprobe.exe`

This directory may not be committed depending on binary distribution policy.

## Motion Patch File Responsibilities

The 2026-05-09 motion patch makes these files especially important:

- `models/overlay.py`: canonical list of motion presets.
- `core/overlays/motion_engine.py`: shared FFmpeg and preview motion formulas.
- `core/overlays/text_engine.py`: applies dynamic motion to Qt-rendered text regions.
- `core/overlays/sticker_engine.py`: applies dynamic motion to sticker regions, including rotate-float.
- `gui/preview_canvas.py`: live preview alpha/scale/offset/rotation using `MotionEngine`.
- `gui/workflow_panel.py`: exposes the available motion presets in text/sticker dropdowns.
