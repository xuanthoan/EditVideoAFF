# CURRENT_TASK.md — Current Development Focus

_Last updated: 2026-05-09_

This file defines the immediate work for the next AI/developer session. It is intentionally practical and should be read before editing renderer, overlay, FFmpeg, GUI, or timeline code.

## 1. Current Priority

The project currently has a working architecture scaffold, but it is not production-ready. The next session should focus on runtime correctness, not broad refactoring.

Immediate priority order:

1. Fix no-audio input handling so videos without audio render without freeze/hang.
2. Validate and harden the newly patched overlay animation engine, especially Fade, Fade In, Pop, and Scale for both text and stickers.
3. Verify and harden Pipeline 4 (Overlay Only) on both with-audio and no-audio videos.
4. Verify image compositor overlap fade on real 9:16 media.
5. Add focused command-generation tests before adding new UI features.

## 2. Do Not Work On Yet

Avoid these until the critical runtime bugs are fixed:

- Full NLE-style timeline features.
- Audio waveform or multi-track audio editing.
- Major GUI redesign.
- AI generation features.
- GPU rendering.
- Full-frame RGBA overlay sequences.
- Intermediate MP4 render stages.

## 3. Required Fix 1 — Optional Audio

### Problem

The pipeline has historically assumed that source videos always contain audio and that extracted `.m4a` files always exist. This can make FFmpeg commands invalid or cause queue freezes when input videos are silent/no-audio.

### Expected Behavior

If source video has audio:

- Extract original audio.
- Build visual filtergraph independently.
- Add extracted audio as an input.
- Map final video and extracted audio.
- Encode audio as AAC.

If source video has no audio:

- Skip audio extraction.
- Do not add fake audio.
- Do not add empty `.m4a`.
- Do not map audio.
- Do not add `-c:a`.
- Export video-only MP4.

### Suggested Implementation

- Add `probe_has_audio(path: Path) -> bool` in `utils/ffmpeg_helper.py`.
- Add `has_audio` to `RenderJob` or pass it into `FFmpegBuilder.build()`.
- Refactor `FFmpegBuilder.output_args()` so audio codec args are conditional.
- Ensure `BatchRenderer._extract_original_audio()` is only called when `probe_has_audio()` returns true.
- Add tests for command output with audio and no audio.

## 4. Required Fix 2 — Overlay Motion

### Problem

A first implementation pass now translates motion presets into shared FFmpeg/preview expressions. Real render validation is still required because user-reported symptoms included:

- Text Fade does not work.
- Sticker Fade In can make sticker disappear.
- Pop has no visible effect.
- Text Scale does not work.

### Expected Behavior

- Motion is applied after immutable overlay asset creation.
- Text/sticker source assets remain static minimal regions.
- FFmpeg applies alpha/scale/position/rotation dynamically per frame.
- Preview uses the same formulas as export.
- Fade preserves original PNG/sticker alpha by multiplying motion alpha, not overwriting alpha.

### Suggested Implementation

- Expand `MotionEngine` into a single source of truth for export and preview formulas.
- Use per-frame evaluation for dynamic transforms.
- Verify scale expressions include `eval=frame`.
- Make Pop obvious: roughly `0.80 -> 1.20 -> 1.00` over a short duration.
- Add tests that inspect generated filtergraph strings for fade, pop, and scale behavior.

## 5. Required Fix 3 — Pipeline 4 Overlay Only

Pipeline 4 must be independent from shuffle/image/fade stages.

Correct Pipeline 4 behavior:

1. Input video is base video.
2. Text/sticker overlays are applied on top.
3. Output video is encoded.
4. No image compositor stage is called.
5. No fade stage is called.
6. No missing intermediate label is assumed.

Retest combinations:

- Text only.
- Sticker only.
- Text + sticker.
- Video with audio.
- Video without audio.
- Stop during render.

## 6. Required Fix 4 — Image/Fade Validation

The overlap fade has been patched but still needs real-media validation.

Test cases:

- 720x1280 and 1080x1920 videos.
- Image height 20%, 35%, 60%.
- Overlap 0%, 5%, 20%.
- Crop focus top, center, bottom.

Expected result:

- Fade is visible.
- Fade uses the shifted video region overlapping the image.
- Fade is not hidden behind the main video.
- No frame jump at the overlap boundary.

## 7. Acceptance Criteria for Next Session

A session can be considered successful if it completes at least one of these:

- Adds robust no-audio command handling with tests.
- Fixes text/sticker Fade/Pop/Scale filtergraph behavior with tests.
- Verifies Pipeline 4 with command-level tests for audio/no-audio.
- Adds sample-media render tests for fade and overlay-only output.

## 8. Files to Open First

For optional audio:

- `utils/ffmpeg_helper.py`
- `core/renderer/batch_renderer.py`
- `core/renderer/ffmpeg_builder.py`
- `core/pipeline/base.py`
- `core/pipeline/shuffle_pipeline.py`

For motion:

- `models/overlay.py`
- `core/overlays/motion_engine.py`
- `core/overlays/text_engine.py`
- `core/overlays/sticker_engine.py`
- `gui/preview_canvas.py`
- `gui/workflow_panel.py`

For fade:

- `core/compositor/image_compositor.py`
- `core/pipeline/compositor_pipeline.py`

## 9. Current Non-Negotiables

- Keep the single final encode architecture.
- Keep overlays in final-canvas normalized coordinate space.
- Keep text rendering as minimal Qt/QPainter RGBA regions.
- Keep sticker scale canvas-width-relative.
- Keep output folder beside the first queued input video.
- Keep safe area and snap enabled internally by default.

## 10. Update After Motion Patch — 2026-05-09

The first code pass for the overlay animation engine has been implemented.

What changed:

- `MotionPreset` includes more social motion presets.
- `MotionEngine` now owns shared FFmpeg/preview formulas.
- Text/sticker engines apply motion after overlay asset creation.
- Preview canvas applies matching alpha/scale/offset/rotate-float helpers.

Next task:

- Validate the new motion filters with real FFmpeg renders.
- Fix optional no-audio command handling next; it remains the highest unresolved runtime bug.
