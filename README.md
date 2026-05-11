# AutoVideoAFF

Unified Python desktop app architecture for mass TikTok/Reels/Shorts video production.

## Goals

- One PySide6 desktop app, not separate tools.
- Modular queue-based pipeline system.
- Scene shuffle, image compositing, text overlay, sticker overlay, motion, preview, and batch export.
- Single final FFmpeg encode: enabled modules append to one `filter_complex` graph before final export.
- AI-ready structure for future subtitle, title, sticker randomization, caption timing, and auto-layout modules.

## Project layout

```text
main.py
core/pipeline/          module pipeline system
core/video/             scene detection, segmentation, timestamps
core/compositor/        image compositor and fade mask logic
core/overlays/          text, sticker, motion, typography, templates
core/renderer/          ffmpeg builder, preview, batch renderer
models/                 project and overlay state
gui/                    PySide6 main window and panels
utils/                  ffmpeg, file, logging, image cache helpers
assets/                 fonts, templates, stickers
bin/                    optional bundled ffmpeg.exe / ffprobe.exe
```

## Build

```bash
pyinstaller --noconfirm --onedir --windowed main.py
```

Or use the included `AutoVideoAFF.spec` to bundle `assets/` and `bin/`.

## FFmpeg setup

Rendering validates both `ffmpeg` and `ffprobe` before starting a batch. Put `ffmpeg.exe` and `ffprobe.exe` in `bin/`, or install FFmpeg globally and add it to `PATH`.

Output files are written with absolute paths under the app's `output/` directory by default. During render the app writes to a hidden `.rendering.mp4` file, verifies it with `ffprobe`, and only then renames it to the final `.mp4` to avoid exposing partial/corrupt files.

## Current workflow fixes

- Scene Shuffle now shuffles video frames only. The original audio is extracted before scene detection and reattached to the final export without shuffling audio chunks.
- The queue preview extracts a lightweight thumbnail at `-ss 0.05` and automatically updates when videos are imported or selected.
- Render logs are concise by default (`INFO`, `WARNING`, `ERROR`, `SUCCESS`) and hide FFmpeg frame-by-frame output unless developer debug logging is enabled in code.
- Text template previews show exactly two swatches: text color and background color.

## Additional UI fixes

- Preview overlays can be dragged and snap to the horizontal/vertical canvas center within 10px, showing light-blue guide lines only during snapping.
- Scene Shuffle exposes `Scene Sensitivity` (10-80, default 30) and passes the value to PySceneDetect threshold detection.
- Sticker Overlay includes scale (0.1x-5.0x), rotation (-360° to +360°), and motion presets: None, Fade In, Fade Out, Bounce, Pop, Slide Up, and Slide Down.
- Built-in text templates are locked to the requested seven exact text/background color pairs.

## Unified Social Video Factory workflow

- The app now exposes exactly four mutually exclusive workflow modes: Shuffle + Image, Shuffle + Image + Overlay, Shuffle + Overlay, and Overlay Only.
- The right workflow column includes dedicated controls for pipeline selection, shuffle sensitivity/fallback behavior, image multi-select compositing settings, text templates/motion, sticker properties/motion, and export actions.
- Batch rendering processes each video independently: failed videos are logged and skipped, FFmpeg commands are retried once, and the Stop action terminates active FFmpeg subprocesses safely.
- Render logs include timestamps, workflow status, FFmpeg commands, and stderr tails on failure without continuous frame-by-frame spam during successful renders.

## Layout and workflow UX refactor

- The main editor uses a 3-column layout with a 280-340px left queue/log splitter, a large center preview, and a 360-420px scrollable workflow column.
- The log box lives only at the bottom of the left panel so workflow controls are no longer clipped by render logs.
- Pipeline UI locking is centralized through `PIPELINE_CONFIG`; disabled panels are non-interactive, dimmed, and show a "Disabled in current pipeline" tooltip.
- Shuffle workflow is simplified for mass social production: random shuffle and keep-first-segment are fixed internal defaults.
- Safe areas are normalized via `SafeAreaEngine` with TikTok/Reels/Shorts/Custom presets; text safe width is intentionally narrower than sticker safe width and scales across 720x1280, 1080x1920, and other 9:16 resolutions.

## Live preview and compact UX update

- The visible Safe Area / Snap settings panel was removed; TikTok safe area and snapping now run as always-on internal editor defaults.
- Render, Stop, and Open Output Folder buttons are fixed below the scrollable workflow controls so they remain visible while editing.
- The template dropdown includes `Random Template`; batch rendering chooses a built-in template per video and avoids immediate repeats.
- Text and sticker edits update directly on the preview canvas from clean source assets without recursive framebuffer rendering.

## Mini Timeline Mode

- A compact 120-180px Mini Timeline sits below the preview canvas and controls only overlay timing: text, stickers, playhead scrubbing, visibility windows, and simple motion timing.
- Timeline blocks are deliberately lightweight: text blocks are orange, sticker blocks are blue, and selected blocks use a highlighted border. Blocks can be dragged horizontally, resized from either edge, and selected from either the timeline or compact overlay list.
- Each overlay stores `start_time`, `end_time`, and derived `duration`; new text and sticker overlays default to `0 → video_duration` when a source duration is available.
- Preview redraws are lightweight and synchronized with the playhead, so overlays are visible only while the current time is inside their timing window.
- Final export remains FFmpeg-based; overlay filters use `enable='between(t,start,end)'` timing expressions instead of realtime encoding or NLE-style timeline rendering.

## Final-canvas social typography export

- Text and sticker overlays are post-composition overlays: scene shuffle and image compositing build the final canvas first, then overlays are applied in final canvas coordinates.
- The preview is the visual master for social typography. Export text is rendered with the same Qt/QPainter typography renderer into transparent RGBA PNG assets and then composited by FFmpeg, instead of using raw `drawtext`.
- Typography uses the same padding, multiline line spacing, rounded background, optical centering, and soft shadow in preview and export. Place `Montserrat-ExtraBold.ttf` and `Poppins-ExtraBold.ttf` in `assets/fonts/` for bundled font consistency.
- Performance note: typography export renders only the minimal text bounding-box RGBA region and reuses cached static region PNGs during graph construction; it does not generate full-frame 1080x1920 overlay canvases or PNG sequences.
- Output folders follow the source-video workflow: batch exports are written to `output/` beside the first video added to the queue, even when later videos come from other folders.
- Stickers use normalized final-canvas scale (`target_width = canvas_width * sticker_scale_ratio`) in both preview and FFmpeg export, so preview and output share the same size and anchor model.
- Image compositing uses the dynamic viewport fade layout (`image_h`, `overlap_h`, `offset_y`, `fade_start`, and mapped `source_y`) so the fade is tied to the visible overlap region rather than an arbitrary source-video strip.
- Render internals are organized as multi-stage metadata/graph planning (`ShufflePlan`, `LayoutPlan`, named filter nodes, overlay region nodes, final render metadata) while still executing one final FFmpeg encode with no intermediate MP4 generation.
- Render logs include structured `[SHUFFLE]`, `[LAYOUT]`, `[OVERLAY]`, and `[FINAL]` events for segment order, dynamic layout/fade coordinates, overlay region details, graph node count, and final resolution.
- Critical fade patch: the opaque main video region now stops before the overlap and the alpha fade region is composited above the image at `fade_start`, so the fade cannot be hidden by a fully opaque shifted video layer; `debug_fade_filter.txt` is written beside render outputs when fade nodes exist.
- Text background boxes are flat rounded rectangles with no outer/drop shadow; overlay-only Pipeline 4 uses the original input video as its base and applies `-shortest` when looping static text-region PNGs.
