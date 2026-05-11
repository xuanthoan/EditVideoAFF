# TESTING.md — Test Plan and Validation Matrix

_Last updated: 2026-05-09_

This project currently has limited automated coverage. Use this file to guide manual and automated validation for future fixes.

## 1. Baseline Static Check

Run after every code/documentation change that could affect imports:

```bash
python -m compileall core gui models utils main.py
```

Expected result:

- Command exits with code 0.
- No syntax/import errors.

## 2. Command-Generation Unit Tests to Add

The most urgent automated tests should validate FFmpeg command construction without requiring full media renders.

### 2.1 No-Audio Command Test

Given:

- input video has no audio;
- overlay/image/shuffle mode is selected.

Assert command does not contain:

- extracted `.m4a` input;
- `-map N:a:0`;
- `-map 0:a?` if no audio should be included;
- `-c:a`.

Assert command does contain:

- final video map;
- video codec args;
- output path.

### 2.2 With-Audio Command Test

Given:

- input video has audio;
- extracted original audio path exists.

Assert command contains:

- audio input path;
- correct audio input index mapping;
- `-c:a aac`;
- final video map.

### 2.3 Pipeline 4 Command Test

For Overlay Only:

- no image input should be added unless sticker/image overlay requires it;
- no compositor/fade labels should be required;
- base video should be `0:v` or a valid chain from original input;
- looped static text inputs should terminate via `-shortest` or equivalent.

### 2.4 Debug Artifact Gate Test

When `developer_mode=False`:

- no debug files are written.

When `developer_mode=True`:

- debug files may be written.

## 3. Filtergraph Tests to Add

### 3.1 Image/Fade Math

For several canvas sizes and settings, assert generated filtergraph contains expected values.

Suggested cases:

| Canvas | Image % | Overlap % |
| --- | --- | --- |
| 720x1280 | 35 | 5 |
| 1080x1920 | 35 | 5 |
| 1080x1920 | 20 | 0 |
| 1080x1920 | 60 | 20 |

Check:

- numeric `color=s=WxH` size;
- no literal `WxH` placeholder;
- `overlap_h` not zero when overlap is enabled;
- fade crop uses expected `source_y`;
- zero-overlap does not generate invalid crop height.

### 3.2 Overlay Position Expressions

Assert text/sticker overlay expressions use final canvas:

```text
W*x_ratio-w/2
H*y_ratio-h/2
```

Do not accept raw preview pixel coordinates.

### 3.3 Sticker Scale Expressions

Assert sticker width is computed from canvas width and normalized scale ratio.

Example:

- `canvas_width=1080`
- `scale=0.16`
- expected target width about `173` pixels.

### 3.4 Motion Expressions

For Fade/Pop/Scale/Bounce:

- assert generated filter contains time-dependent expression using `t` or local time;
- assert dynamic scale uses `eval=frame`;
- assert fade preserves alpha instead of hiding overlay permanently.

## 4. Manual Render Validation Matrix

Use short 5-15 second vertical clips to keep tests fast.

### 4.1 Audio Matrix

| Pipeline | With audio | No audio |
| --- | --- | --- |
| Pipeline 1 Shuffle + Image | Required | Required |
| Pipeline 2 Shuffle + Image + Overlay | Required | Required |
| Pipeline 3 Shuffle + Overlay | Required | Required |
| Pipeline 4 Overlay Only | Required | Required |

Expected:

- With-audio outputs contain audio.
- No-audio outputs are valid silent/video-only MP4 files.
- No queue freeze.
- No invalid `.m4a` references.

### 4.2 Overlay Motion Matrix

Test for both text and sticker where applicable:

- None
- Fade / Fade In
- Fade Out
- Pop
- Bounce
- Scale
- Drift
- Slide Up
- Slide Down

Expected:

- Preview and output look similar.
- Fade transitions opacity, not visibility only.
- Sticker fade does not disappear permanently.
- Pop visibly overshoots then returns.
- Scale changes region transform, not source PNG generation.

### 4.3 Image Compositor Matrix

Test:

- image height 20%, 35%, 60%;
- overlap 0%, 5%, 20%;
- crop focus top/center/bottom.

Expected:

- Image is not distorted.
- Video is shifted/cropped correctly.
- Fade appears only in overlap region.
- No jump frame at fade boundary.

### 4.4 GUI Smoke Test

Manual checks:

- Add multiple videos.
- Select queue item and confirm preview updates.
- Text edits update preview immediately.
- Sticker selection/scale/rotation updates preview immediately.
- Drag overlay and verify normalized position persists into render.
- Mini timeline playhead hides/shows overlays by timing.
- Render/Stop/Open Output Folder buttons remain visible.

## 5. Suggested Test Assets

Maintain a small local test asset folder outside git or in a future `tests/assets/` if licensing permits:

- `vertical_with_audio_720x1280.mp4`
- `vertical_no_audio_720x1280.mp4`
- `vertical_with_audio_1080x1920.mp4`
- `background_image_1080x600.jpg`
- `sticker_transparent.png`

Do not commit copyrighted sample videos.

## 6. Useful Search Commands

```bash
rg "-map|original_audio|audio_label|c:a|probe" core/renderer core/pipeline utils -n
```

```bash
rg "MotionPreset|alpha_filter|region_scale_expr|eval=frame" core/overlays gui models -n
```

```bash
rg "debug_filtergraph|debug_fade_filter|developer_mode" -n
```

```bash
rg "color=c=black|geq=|crop=w=.*h=.*source" core/compositor core/pipeline -n
```

## 7. Release Readiness Gate

Before calling the app production-ready, all must pass:

- compileall static check;
- command-level tests for audio/no-audio;
- real media render for all four pipelines;
- overlay motion visual QA;
- image/fade visual QA;
- no debug artifacts in default mode;
- output folder correctness with multi-folder input queue;
- stop button kills active FFmpeg process;
- clean Windows machine font/FFmpeg bundle test.

## 8. Motion Patch Tests Added/Required

A command-level smoke test should assert:

- Pop scale expressions contain `0.80`, `1.20`, local time, and escaped FFmpeg expression commas.
- Fade In filter contains `format=rgba` and `fade=t=in:st=<start>:d=0.350:alpha=1`.
- Fade Out starts at `end - 0.350`.
- Text filters use `scale=...:eval=frame` and do not use `drawtext`.
- Sticker Rotate Float uses a dynamic `rotate='<expr>'` expression.

Manual render validation is still required for visual quality and preview/output parity.
