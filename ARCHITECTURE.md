# AutoVideoAFF Internal Architecture

_Last updated: 2026-05-08_

This document is the primary handoff reference for future development sessions. It describes the current architecture as implemented in the repository, not an idealized rewrite. Use it before changing renderer, GUI, timeline, animation, or output behavior.

## 1. Product Goal

AutoVideoAFF is a unified PySide6 desktop application for high-volume social video production. It targets TikTok, Instagram Reels, and YouTube Shorts workflows where users import many vertical videos, optionally shuffle scenes, add an image compositor/fade area, add text/sticker overlays, and batch export final videos with minimal clicks.

The application intentionally remains one app with one render engine. It must not split into separate shuffle/compositor/overlay apps.

## 2. Core Architectural Rules

The current project is built around these rules:

1. **Python is orchestration/UI only.**
   - GUI, state management, planning, temporary overlay asset generation, and subprocess orchestration happen in Python.
   - Final video rendering/compositing/export is done by FFmpeg.

2. **Single final encode per output video.**
   - Pipeline stages build metadata and filtergraph nodes.
   - Stages must not export intermediate MP4/H264/H265 files.
   - Temporary PNG overlay regions are allowed for typography/stickers because they are assets, not video re-encodes.

3. **Modular pipeline system.**
   - Workflow modes enable/disable modules.
   - Modules append to a shared `FilterGraph`.
   - `FinalExportPipeline` appends final codec/output args.

4. **Final-canvas overlay space.**
   - Text and sticker overlays use normalized coordinates relative to final output canvas.
   - Overlays are post-composition elements, not attached to raw source pixels.

5. **Preview/export parity is a design goal.**
   - Preview should use the same coordinate, safe-area, motion, and typography concepts as FFmpeg export.
   - Differences that remain should be treated as bugs or known risks.

## 3. Repository Map

```text
main.py                         PySide6 app entry point.
models/                         Dataclass state models for project, overlays, stickers, text.
core/pipeline/                  Pipeline modules and render graph primitives.
core/compositor/                Image compositor and viewport fade layout/filter construction.
core/overlays/                  Template, typography, text, sticker, transform, motion engines.
core/renderer/                  Batch renderer, FFmpeg command builder, preview frame extraction.
core/video/                     Scene detection, fallback segmentation, timestamp constants.
core/safe_area_engine.py        Normalized platform safe-area calculations.
gui/                            Main window, queue, workflow panel, preview canvas, mini timeline.
utils/                          FFmpeg lookup/probing, file helpers, process lifecycle, logging.
assets/fonts/                   Expected bundled font location.
AutoVideoAFF.spec               PyInstaller packaging spec.
requirements.txt                PySide6 + PySceneDetect runtime dependencies.
```

## 4. Main Runtime Flow

High-level flow for one batch render:

1. User imports videos through the queue panel.
2. `MainWindow` stores paths in `ProjectState.videos`.
3. User selects one workflow mode in `WorkflowPanel`.
4. GUI controls sync into `ProjectState` before render.
5. `RenderWorker` runs `BatchRenderer.render()` in a background thread.
6. `BatchRenderer` validates FFmpeg/FFprobe, chooses output directory, and processes queue items sequentially.
7. For each input video:
   - output/temp paths are prepared;
   - optional original audio extraction is attempted for shuffle pipelines;
   - `PipelineManager.build_command()` probes video size and creates a `RenderJob`;
   - active pipeline modules mutate a shared `FilterGraph`;
   - `FFmpegBuilder` converts the graph into a final FFmpeg command;
   - `ProcessManager` runs FFmpeg and can be stopped by the UI;
   - output is verified with FFprobe and renamed from `.rendering.mp4` to final `.mp4`.

## 5. Central State Model

`models/project_state.py` is the source of truth passed from GUI to renderer.

### `ProjectState`

Important fields:

- `videos`: batch queue.
- `workflow_mode`: one of four mutually exclusive workflows.
- `scene_shuffle`: scene detection and fallback split settings.
- `image_composite`: image pool, image height %, overlap %, crop focus, fade curve.
- `overlays`: text/sticker settings plus multi-layer lists.
- `export`: output folder, CRF, preset, auto-open, developer-mode flag.
- `safe_area`: internal platform, safe area enabled, snap enabled.

### Overlay coordinate contract

`OverlayBase.x` and `OverlayBase.y` are normalized final-canvas center coordinates:

```text
x = 0.0 left edge, 0.5 center, 1.0 right edge
y = 0.0 top edge,  0.5 center, 1.0 bottom edge
```

Do not store or pass preview pixels into the export renderer. Convert preview positions back to ratios.

Sticker scale is also normalized: `StickerOverlay.scale = 0.16` means the target sticker width is roughly `canvas_width * 0.16`.

## 6. Workflow Modes

The app supports four mutually exclusive workflow modes:

| Mode | Name | Enabled modules |
| --- | --- | --- |
| `PIPELINE_1` | Shuffle + Image | scene shuffle, image compositor, final export |
| `PIPELINE_2` | Shuffle + Image + Overlay | scene shuffle, image compositor, overlay, final export |
| `PIPELINE_3` | Shuffle + Overlay | scene shuffle, overlay, final export |
| `PIPELINE_4` | Overlay Only | overlay, final export |

`gui/workflow_panel.py` contains `PIPELINE_CONFIG` for UI locking. `core/pipeline/manager.py` contains the renderer-side module selection.

## 7. Pipeline and Render Graph Primitives

Defined in `core/pipeline/base.py`:

- `FilterNode`: one named FFmpeg filter chain and optional output label.
- `ShuffleSegment`: one start/end segment.
- `ShufflePlan`: metadata for shuffled visual order.
- `LayoutPlan`: computed image/video/fade layout values.
- `FilterGraph`: shared mutable graph used by pipeline modules.
- `RenderJob`: input/output/state/audio/video-size bundle.
- `PipelineModule`: protocol for enabled/apply behavior.

`FilterGraph` is intentionally not a full DAG engine. It is a structured wrapper around ordered FFmpeg chains, inputs, extra args, temp files, and debug events.

## 8. Pipeline Modules

### 8.1 `SceneShufflePipeline`

Responsibilities:

- Detect scenes using `SceneDetector` / PySceneDetect.
- Fallback split using `Segmenter` if no useful scene list exists.
- Keep the first segment, shuffle remaining visual segments.
- Emit video-only `trim,setpts` nodes.
- Concat shuffled video with `concat=n=...:v=1:a=0`.
- Store `ShufflePlan` metadata.

Important: audio must not be shuffled. It is intended to be extracted/restored separately.

### 8.2 `ImageCompositePipeline`

Responsibilities:

- Pick an image from the image pool.
- Add image input to the graph.
- Ask `ImageCompositor` to compute a `LayoutPlan` and graph nodes.
- Append `[LAYOUT]` and `[FADE]` debug events.

### 8.3 `OverlayPipeline`

Responsibilities:

- Render text overlays into minimal transparent PNG regions via `TextEngine` / Qt typography.
- Add text PNG assets as looped inputs.
- Add sticker inputs.
- Apply text/sticker filters on top of the current `graph.video_label`.
- Preserve overlay ordering: text layers first, then sticker layers.

### 8.4 `FinalExportPipeline`

Responsibilities:

- Append codec/export args from `FFmpegBuilder.output_args()`.
- Does not write files itself.

## 9. GUI Architecture

The GUI is a three-column editor layout:

```text
Left column:    queue + queue buttons + log panel
Center column:  preview canvas + mini timeline
Right column:   scrollable workflow panel + fixed render/stop/open controls
```

Important GUI classes:

- `gui/main_window.py`: app shell, state synchronization, render worker wiring, preview/timeline sync.
- `gui/queue_panel.py`: video queue controls.
- `gui/workflow_panel.py`: compact workflow controls and pipeline UI locking.
- `gui/preview_canvas.py`: thumbnail preview, safe area, overlay preview, drag/snap.
- `gui/mini_timeline.py`: lightweight overlay timing UI.
- `gui/export_panel.py`: reusable export control primitives.

## 10. Safe Area System

`core/safe_area_engine.py` calculates normalized TikTok/Reels/Shorts safe areas. The visible safe-area/snap settings panel was removed from the GUI; safe area and snapping are core behaviors enabled internally by default.

Safe area applies to final canvas space. It should not be calculated from raw source video space after viewport/image offsets.

## 11. Output Routing

Output files are written beside the first imported video, not beside the project directory:

```text
Input first video:  D:/CampaignA/video1.mp4
Output folder:      D:/CampaignA/output/
Output file:        D:/CampaignA/output/video1.mp4
```

If the queue contains videos from multiple folders, the first queued video determines the batch output root.

`utils/file_helper.py` owns this behavior:

- `output_directory_for_videos()`
- `safe_output_path()`
- `temporary_output_path()`

## 12. Process and Stop Handling

`utils/process_manager.py` wraps subprocess execution. It tracks the active FFmpeg process and lets Stop kill it safely. `BatchRenderer.stop()` delegates to `ProcessManager.stop_all()`.

Batch render behavior:

- Sequential queue processing.
- One video failure is logged and skipped.
- Stop kills current process and stops the remaining queue.
- Output is first written to a hidden `.rendering.mp4`, verified, then renamed.

## 13. Developer Mode and Debug Artifacts

`ExportSettings.developer_mode` exists and defaults to `False`. Debug graph files are intended to be written only when developer mode is enabled.

Current code paths include helpers for:

- `debug_filtergraph.txt`
- `debug_fade_filter.txt`

Release behavior should produce only final videos unless developer mode is enabled.

## 14. Known High-Priority Risks

These are not solved by documentation and should be handled in future code sessions:

1. **No-audio input hang risk.**
   - Current audio handling still relies on optional extraction behavior and command-builder mapping should be audited.
   - Final FFmpeg command generation must dynamically omit audio input/map/codec when no audio exists.

2. **Overlay animation parity.**
   - Fade/Pop/Scale have helper expressions, but real FFmpeg behavior should be verified on text and sticker assets.
   - Sticker alpha fade must preserve existing PNG alpha.

3. **Fade overlap validation.**
   - The compositor now builds a visible fade layer, but real-media visual validation is still needed.

4. **Template color drift.**
   - Orange template was adjusted to `#F58B57` for preview/output tone, which differs from the earlier exact template spec `#F57C4D`.

5. **Font availability.**
   - Typography quality depends on bundling `Montserrat-ExtraBold.ttf` or `Poppins-ExtraBold.ttf` under `assets/fonts/`.

## 15. Guidelines for Future Changes

When modifying the app:

- Do not rebuild the app from scratch.
- Do not introduce MoviePy/OpenCV final rendering.
- Do not add intermediate MP4 render stages.
- Do not store overlay positions as preview pixels.
- Do not attach overlays to pre-composited/shifted source video.
- Keep timeline overlay-only and lightweight.
- Keep text assets minimal-region PNGs, not full-frame RGBA sequences.
- Add tests for generated filter strings whenever renderer logic changes.

## 17. Motion Engine Update — 2026-05-09

Overlay motion now follows a stricter two-stage model:

1. Render or load an immutable RGBA overlay region.
2. Apply alpha, scale, translation, and rotation motion to that region during final-canvas compositing.

The shared `MotionEngine` is the source of truth for FFmpeg expressions and preview helper calculations. Text and sticker overlays should not implement separate ad-hoc motion formulas.
