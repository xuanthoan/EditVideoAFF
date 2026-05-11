# AutoVideoAFF — Known Bugs and Risk Register

This file records known bugs, suspected causes, and suggested fix direction for the current codebase.

## Critical Bugs

### 1. Pipeline can hang/fail with input videos that have no audio

**Status:** Known critical bug / not fully fixed.

**Symptom:**

- User reported render pipeline freezes/hangs when input video has no audio.
- Previous implementation assumed extracted audio always exists and audio mapping is always valid.

**Likely affected files:**

- `core/renderer/batch_renderer.py`
- `core/renderer/ffmpeg_builder.py`
- `core/pipeline/shuffle_pipeline.py`
- `utils/ffmpeg_helper.py`

**Current code risk:**

- `BatchRenderer` attempts audio extraction for shuffle workflows.
- `_extract_original_audio()` can return `None` if stderr indicates no audio.
- `SceneShufflePipeline` sets `graph.audio_label` to `0:a?` when no original audio path exists.
- `FFmpegBuilder` can still add optional audio mapping and `FFmpegBuilder.output_args()` always contains `-c:a aac`.
- There is no explicit `has_audio` field in `RenderJob` / `build_command()`.

**Required fix direction:**

1. Add `probe_has_audio(path: Path) -> bool` using ffprobe stream detection.
2. Add `has_audio: bool` to `RenderJob` or pass into `FFmpegBuilder.build()`.
3. Refactor command building to be truly dynamic:
   - If audio exists and extracted audio path exists: add audio input, map that audio, add `-c:a aac`.
   - If audio does not exist: do not add audio input, do not map audio, do not add audio codec args.
4. Avoid fake audio (`anullsrc`, silent track, empty m4a).
5. Ensure all visual filtergraph stages are independent of audio.
6. Add tests for with-audio and no-audio commands.

**Acceptance criteria:**

- No-audio video exports video-only MP4.
- With-audio video exports MP4 with restored original audio.
- No FFmpeg command contains missing `.m4a` input or invalid `-map N:a:0` when audio is absent.

---

### 2. Overlay animation engine is incomplete / broken for Fade, Pop, Scale

**Status:** First implementation patch added / requires real FFmpeg validation.

**User-reported symptoms:**

- Text Fade motion does not work.
- Sticker Fade In can make sticker disappear.
- Pop motion has little/no visible effect.
- Text Scale motion does not work.

**Likely affected files:**

- `core/overlays/motion_engine.py`
- `core/overlays/text_engine.py`
- `core/overlays/sticker_engine.py`
- `gui/preview_canvas.py`
- `models/overlay.py`
- `gui/workflow_panel.py`

**Current code status:**

- Motion enum now includes the requested common presets (Float, Shake, Slide Left/Right, Pulse, Rotate Float, Scale Up/Down).
- `MotionEngine.alpha_filter()` applies FFmpeg RGBA alpha fades after asset creation.
- Dynamic scale expressions use `scale=...:eval=frame` and are shared by text/sticker engines.
- Preview uses `MotionEngine` helper methods for alpha, scale, offset, and rotate-float behavior.
- Real FFmpeg render validation is still required for every preset.

**Required fix direction:**

1. Create/expand a unified overlay animation model with:
   - fade in/out
   - pop
   - bounce
   - scale up/down
   - float
   - shake
   - slide left/right/up/down
   - pulse
   - rotate float
   - speed/strength parameters if GUI is expanded.
2. Apply animation after immutable overlay asset creation, before final overlay composite.
3. For fade, multiply original alpha by motion alpha; do not overwrite alpha with zero.
4. Use `eval=frame` for dynamic scale/position/rotation filters.
5. Ensure preview uses the same formulas/easing as export.
6. Add tests asserting generated FFmpeg expressions contain dynamic `t`, `eval=frame`, and expected fade/scale filters.

**Acceptance criteria:**

- Sticker Fade In fades from transparent to visible without disappearing.
- Text Fade works.
- Pop visibly overshoots and returns to normal.
- Text Scale applies dynamic region transform, not source PNG regeneration.
- Preview and output motion visually match.

---

### 3. Viewport overlap fade needs real-media verification

**Status:** Recently patched / needs validation.

**Symptom history:**

- Fade overlap disappeared completely after graph refactor.
- Patch changed main video crop so opaque video does not hide fade strip.

**Likely affected files:**

- `core/compositor/image_compositor.py`
- `core/pipeline/compositor_pipeline.py`

**Current code behavior:**

- Calculates `LayoutPlan` dynamically.
- Uses separate `main_src` and `fade_src` from a split.
- Crops main region and fade region separately.
- Applies alpha with `format=yuva420p,geq=...`.
- Composites fade strip at `fade_start`.

**Remaining risk:**

- Main video crop/overlay may alter continuity around overlap region.
- `source_y` clamping may hide math mistakes for extreme layout settings.
- Fade curve setting exists but current geq expression appears linear.

**Required fix direction:**

1. Test with real 720x1280 and 1080x1920 videos.
2. Verify fade is exactly the video area over the image after offset.
3. Implement `fade_curve` variants if not already active.
4. Add command-level unit tests for multiple IH/OV values.

---

## High Priority Bugs / Gaps

### 4. Debug artifact output must remain disabled in release mode

**Status:** Partially handled.

**Files:**

- `models/project_state.py`
- `core/renderer/batch_renderer.py`

**Current behavior:**

- `ExportSettings.developer_mode` exists and defaults to `False`.
- Debug file writers are called only inside `if render_state.export.developer_mode`.

**Risk:**

- Need real render verification that no `debug_filtergraph.txt` or `debug_fade_filter.txt` appears in normal output.

---

### 5. Template color inconsistency

**Status:** Needs decision.

**Details:**

- Earlier requirement specified `Orange White` background `#F57C4D`.
- Later typography requirement requested visual tone approximately `#F58B57`.
- Current code likely uses the later visual tone.

**Files:**

- `core/overlays/template_manager.py`
- `core/overlays/typography_engine.py`

**Fix direction:**

- Decide whether exact template definitions or later visual typography tone wins.
- If exact templates are required, revert `Orange White` to `#F57C4D`.

---

### 6. Font parity depends on actual bundled fonts

**Status:** Incomplete until assets are added.

**Files:**

- `assets/fonts/README.md`
- `core/overlays/typography_engine.py`
- `AutoVideoAFF.spec`

**Risk:**

- If Montserrat/Poppins files are missing, Qt may use fallback fonts, reducing preview/export consistency across machines.

**Fix direction:**

- Add licensed font files to `assets/fonts/`.
- Ensure `SocialTypographyRenderer` explicitly loads the bundled font file.
- Test on a clean Windows machine.

---

### 7. FFmpeg output args are not cleanly separated for no-audio vs audio

**Status:** Related to Critical Bug #1.

**Files:**

- `core/renderer/ffmpeg_builder.py`

**Current risk:**

- `output_args()` always includes `-c:a aac`.
- `ratio_filters` variable is unused.
- Command builder should be refactored to `build_ffmpeg_command(has_audio: bool)` or equivalent.

---

### 8. Motion UI does not expose all requested presets/speed/strength

**Status:** Incomplete.

**Files:**

- `models/overlay.py`
- `gui/workflow_panel.py`
- `core/overlays/motion_engine.py`
- `gui/preview_canvas.py`

**Missing requested presets:**

- Float
- Shake
- Slide Left
- Slide Right
- Pulse
- Scale Up
- Scale Down
- Rotate Float

**Missing controls:**

- Animation Speed slider
- Animation Strength slider

---

## Medium Priority Bugs / Risks

### 9. Pipeline 4 overlay-only was previously freezing

**Status:** Recently patched but should be retested.

**Patch direction already applied:**

- Overlay-only graph uses original `0:v` base.
- `-shortest` is added when looped static text PNGs are introduced.

**Need validation:**

- Pipeline 4 with text only.
- Pipeline 4 with sticker only.
- Pipeline 4 with text + sticker.
- Pipeline 4 on videos with no audio.

---

### 10. Preview/export parity still needs visual QA

**Status:** Architectural path in place, not fully proven.

**Potential mismatch areas:**

- Qt preview canvas scaling vs final output canvas dimensions.
- Text antialiasing on Windows vs Linux.
- Sticker rotation bounding box vs FFmpeg rotate `rotw/roth`.
- Alpha fade / scale / pop motion.
- Timeline playhead active overlay visibility.

---

### 11. Image compositor input indexing is fragile

**Status:** Risk.

**File:** `core/pipeline/compositor_pipeline.py`

**Concern:**

- Image input index is derived from counting `graph.inputs` tokens after appending looped input args.
- This can become fragile as more input types are added.

**Fix direction:**

- Add a `FilterGraph.add_input(args: list[str]) -> int` helper that returns the new input index explicitly.

---

### 12. Text asset cache cleanup may conflict with reuse

**Status:** Risk.

**Files:**

- `core/overlays/text_engine.py`
- `core/renderer/batch_renderer.py`

**Concern:**

- `TextEngine` caches temp paths, while `BatchRenderer` cleans temp files after each video.
- If cache keeps deleted paths, it checks existence and regenerates, so it should work, but this should be tested.

---

## Suggested Immediate Test Matrix

1. Pipeline 1, with audio, image compositor enabled.
2. Pipeline 1, no audio, image compositor enabled.
3. Pipeline 2, with audio, image + text + sticker.
4. Pipeline 2, no audio, image + text + sticker.
5. Pipeline 3, with audio, text + sticker.
6. Pipeline 3, no audio, text + sticker.
7. Pipeline 4, with audio, text + sticker.
8. Pipeline 4, no audio, text + sticker.
9. Sticker Fade In / Fade Out / Pop / Bounce / Scale / Drift.
10. Text Fade In / Pop / Scale / multiline text.
11. Overlap fade at image height 20/35/60 and overlap 0/5/20.
12. Output path with videos from multiple source folders.

## Commands Useful for Debugging

```bash
python -m compileall core gui models utils main.py
```

```bash
rg "debug_filtergraph|debug_fade_filter|developer_mode" -n
```

```bash
rg "-map|original_audio|audio_label|c:a|probe" core/renderer core/pipeline utils -n
```

```bash
rg "MotionPreset|alpha_filter|region_scale_expr|eval=frame" core/overlays gui models -n
```

## Recently Addressed — Overlay Motion Patch 2026-05-09

The Fade/Pop/Scale motion bug has been partially addressed in code:

- `MotionPreset` now includes the requested common social motion presets.
- `MotionEngine` builds alpha fades and dynamic scale/position expressions for overlay regions.
- Text and sticker engines pass overlay start/end timing into dynamic region scaling.
- Preview canvas now applies matching alpha, scale, offset, and rotate-float helpers.

Remaining validation required:

- Run real FFmpeg renders for text/sticker Fade In, Fade Out, Pop, Scale, Pulse, Float, Shake, and slides.
- Confirm sticker Fade In preserves transparent PNG edges and does not disappear.
- Confirm preview/output parity visually on Windows.
