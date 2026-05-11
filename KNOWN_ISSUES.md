# KNOWN_ISSUES.md — Active Bugs, Risks, and Follow-Up Items

_Last updated: 2026-05-09_

This file is the quick bug list for future development. For broader context, see `BUGS.md` and `NEXT_SESSION_HANDOFF.md`.

## Critical Issues

### 1. No-Audio Input Can Hang or Fail

Status: open.

Impact:

- Rendering videos without audio can freeze/fail because the pipeline may still assume extracted audio exists or may include audio codec/map args.

Likely files:

- `utils/ffmpeg_helper.py`
- `core/renderer/batch_renderer.py`
- `core/renderer/ffmpeg_builder.py`
- `core/pipeline/base.py`
- `core/pipeline/shuffle_pipeline.py`

Fix summary:

- Probe audio stream before extraction.
- Add explicit `has_audio` handling.
- Build FFmpeg command dynamically.
- Omit audio input/map/codec args for no-audio videos.

Acceptance:

- No-audio videos export video-only MP4 without freeze.
- With-audio videos export with restored original audio.

### 2. Overlay Motion Fade/Pop/Scale Needs Validation

Status: first implementation patch added; real render validation required.

Impact history:

- Text Fade previously did not work.
- Sticker Fade In could disappear.
- Pop previously had little/no visible effect.
- Text Scale previously did not animate.

Current code path:

- Shared `MotionEngine` now generates fade, scale, position, and rotate-float expressions.
- Preview canvas now uses matching motion helpers.
- Needs real FFmpeg output validation.

Likely files:

- `models/overlay.py`
- `core/overlays/motion_engine.py`
- `core/overlays/text_engine.py`
- `core/overlays/sticker_engine.py`
- `gui/preview_canvas.py`
- `gui/workflow_panel.py`

Fix summary:

- Apply animation to immutable overlay regions after asset creation.
- Preserve/multiply original alpha for fade.
- Use per-frame scale/position expressions.
- Keep preview formulas identical to export formulas.

Acceptance:

- Text/sticker Fade works.
- Sticker Fade In does not disappear.
- Pop visibly overshoots.
- Text Scale works in output and preview.

### 3. Pipeline 4 Overlay Only Needs Retest

Status: patched but not fully proven.

Impact:

- Pipeline 4 previously froze when overlay-only graph depended on missing compositor labels or looped PNG inputs did not terminate.

Retest:

- Text only.
- Sticker only.
- Text + sticker.
- With audio.
- Without audio.

## High Priority Risks

### 4. Viewport Fade Needs Real-Media Verification

Status: patched but needs QA.

Risk:

- Fade may be hidden, misaligned, or discontinuous for certain image/overlap values.
- `fade_curve` field may not be fully implemented beyond linear.

Test:

- 720x1280 and 1080x1920.
- Image height 20/35/60.
- Overlap 0/5/20.

### 5. Debug Files Must Stay Developer-Only

Status: partially handled.

Risk:

- `debug_filtergraph.txt` or `debug_fade_filter.txt` could accidentally appear in normal release output.

Acceptance:

- Default `developer_mode=False` render creates only final output and cleaned temp files.

### 6. Font Bundle Missing

Status: open.

Risk:

- Preview/export typography can vary by machine if Montserrat/Poppins are not bundled and explicitly loaded.

Fix:

- Add licensed font files to `assets/fonts/`.
- Ensure renderer loads bundled fonts.

### 7. Template Color Conflict

Status: needs product decision.

Conflict:

- Earlier exact template: `Orange White` background `#F57C4D`.
- Later typography visual tone: approximately `#F58B57`.

Need:

- Decide source of truth.

### 8. Input Indexing Is Fragile

Status: open risk.

Problem:

- Several modules derive FFmpeg input indexes by counting `-i` tokens.

Fix:

- Add explicit `FilterGraph.add_input(args) -> int` helper.

### 9. Text Asset Cache Cleanup Needs Stress Test

Status: risk.

Problem:

- TextEngine caches temp paths while BatchRenderer cleans temp files after each video.

Need:

- Verify cache regenerates correctly after cleanup.

## Medium Priority Items

### 10. Motion UI Is Incomplete

Missing requested presets:

- Float
- Shake
- Slide Left
- Slide Right
- Pulse
- Scale Up
- Scale Down
- Rotate Float

Missing controls:

- Animation Speed slider.
- Animation Strength slider.

### 11. Preview/Export Parity Needs Visual QA

Potential mismatch areas:

- Sticker rotation bounding box.
- Qt preview scaling vs final canvas dimensions.
- Fade alpha behavior.
- Pop/scale motion.
- Timeline visibility and final FFmpeg enable expressions.

### 12. Scene Detection Robustness Needs Media QA

Need to test:

- Videos with very few cuts.
- Very short videos.
- Corrupted/variable frame rate videos.
- Videos with unusual timebases.

### 13. Packaging Is Not Fully Validated

Need to test PyInstaller one-dir build with:

- bundled ffmpeg.exe;
- bundled ffprobe.exe;
- bundled fonts;
- fresh Windows machine.

## Suggested Immediate Bugfix Branch Scope

Best next branch scope:

1. Add no-audio detection/command fix.
2. Add command-level tests for audio/no-audio.
3. Fix motion fade/pop/scale string generation.
4. Add command-level tests for motion filters.

Avoid mixing broad GUI redesign into the same branch.

## Recently Changed — Motion Engine

The Fade/Pop/Scale issue has a first implementation patch, but it still needs media validation.

Validation still required:

- Render text Fade In/Fade Out/Pop/Scale/Pulse.
- Render sticker Fade In/Fade Out/Pop/Rotate Float/Shake/Slide.
- Compare preview and output at the same playhead time.
- Verify transparent sticker edges remain clean during fade.

If failures remain, start with `core/overlays/motion_engine.py` and inspect generated FFmpeg expressions.
