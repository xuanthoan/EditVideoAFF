# AutoVideoAFF Render Pipeline Internals

_Last updated: 2026-05-08_

This document explains how the current multi-stage logic pipeline produces one final FFmpeg command and one final encode. Read this before changing scene shuffle, image compositing, overlay ordering, output paths, or batch behavior.

## 1. Pipeline Design Summary

The renderer is a metadata/filtergraph pipeline, not a sequence of encoded video files.

```text
ProjectState
  -> BatchRenderer
  -> PipelineManager
  -> RenderJob + FilterGraph
  -> SceneShufflePipeline       (optional)
  -> ImageCompositePipeline     (optional)
  -> OverlayPipeline            (optional)
  -> FinalExportPipeline
  -> FFmpegBuilder
  -> one FFmpeg process / one final encoded MP4
```

Pipeline stages may create non-video temporary assets such as typography PNG regions, but they must not create intermediate MP4/H264/H265 renders.

## 2. Batch Render Lifecycle

`BatchRenderer.render(state, progress, log)` owns queue processing.

For every video:

1. Resolve output folder using the first queued video.
2. Generate a safe non-overwriting final path.
3. Generate hidden temporary `.rendering.mp4` path.
4. Remove stale temp output/audio files.
5. Optionally extract original audio for shuffle workflows.
6. Deep-copy state if `Random Template` needs per-video template replacement.
7. Build a final FFmpeg command through `PipelineManager`.
8. Optionally write debug filter files if developer mode is enabled.
9. Run FFmpeg through `ProcessManager`.
10. Verify temp output with FFprobe.
11. Rename temp output to final output.
12. Verify final output.
13. Clean temporary overlay/audio files.

One video failure is logged and skipped; batch rendering continues unless the user presses Stop.

## 3. RenderJob

`RenderJob` contains:

- `input_path`: source video.
- `output_path`: temp render output path for the current run.
- `state`: render state for this video.
- `original_audio_path`: optional extracted original audio.
- `video_width`, `video_height`: probed from the source video.

The canvas currently follows the source video dimensions as probed by FFprobe. Most target workflows are 9:16 vertical videos.

## 4. FilterGraph Contract

`FilterGraph` is mutated by pipeline modules. Important fields:

- `inputs`: extra FFmpeg input tokens after `-i input.mp4`, such as `-loop 1 -i text.png`.
- `nodes`: ordered filter chains.
- `video_label`: current video output label after each module.
- `audio_label`: optional audio mapping label/convention.
- `extra_args`: final command args such as timestamp flags, `-shortest`, codecs.
- `temp_files`: temporary assets to clean.
- `shuffle_plan`: optional segment metadata.
- `layout_plan`: optional image/fade layout metadata.
- `debug_events`: human-readable pipeline events for logs.

A module must read `graph.video_label` as its input and set a new output label when it changes the video stream.

## 5. Stage 1 — Shuffle Plan and Video-Only Shuffle

### Responsibility

`SceneShufflePipeline`:

- runs PySceneDetect via `SceneDetector`;
- falls back to `Segmenter` if needed;
- keeps first segment and shuffles remaining segments;
- records a `ShufflePlan`;
- builds video-only trim/concat nodes.

### Filter shape

For segments `[A, B, C]`, output is conceptually:

```text
[0:v]trim=start=A.start:end=A.end,setpts=PTS-STARTPTS[shv0]
[0:v]trim=start=B.start:end=B.end,setpts=PTS-STARTPTS[shv1]
[0:v]trim=start=C.start:end=C.end,setpts=PTS-STARTPTS[shv2]
[shv0][shv1][shv2]concat=n=3:v=1:a=0[shuffled_v]
```

### Audio rule

Audio must never be shuffled. Shuffle output is video-only. Original audio should be remuxed separately if it exists.

### Known follow-up

Current no-audio behavior must be audited/fixed so final commands do not assume an extracted `.m4a` exists.

## 6. Stage 2 — Layout Plan

`ImageCompositor.build_plan()` computes dynamic layout values from `ImageCompositeSettings`, `video_width`, and `video_height`.

Definitions:

```text
W = canvas width
H = canvas height
IH = clamped image_height_percent, 20..60
OV = clamped overlap_percent, 0..min(20, IH)

image_h             = even_pixels(H * IH / 100)
overlap_h           = even_pixels(H * OV / 100)
visible_video_total = H - (image_h - overlap_h)
offset_y            = -(H - visible_video_total)
main_video_h        = visible_video_total - overlap_h
image_top           = H - image_h
fade_start          = image_top
source_y            = fade_start - offset_y, clamped for crop safety
```

The plan exists to keep layout math out of procedural string concatenation.

## 7. Stage 3 — Image Compositor and Viewport Fade

### Correct layer order

```text
1. base canvas
2. processed image layer at image_top
3. main visible video region
4. alpha fade strip from viewport overlap region
```

### Image processing

The image layer uses:

```text
scale=w=W:h=-1
crop=w=W:h=image_h:x=(iw-W)/2:y=<focus>
```

Focus values:

- `top`: `0`
- `center`: `(ih-oh)/2`
- `bottom`: `ih-oh`

### Fade logic

Fade must be the video region that overlaps the image after viewport offset.

Current graph structure when `overlap_h > 0`:

```text
[video]setpts=PTS-STARTPTS,split=2[main_src][fade_src]
[main_src]crop=w=W:h=main_video_h:x=0:y=-offset_y[mainv]
[fade_src]crop=w=W:h=overlap_h:x=0:y=source_y,format=yuva420p,geq=...[fade]
[base][mainv]overlay=x=0:y=0[main_layer]
[main_layer][fade]overlay=x=0:y=fade_start[composited_v]
```

The fade strip must sit above the image/base composition. If the opaque main video also covers the overlap region, the fade will be hidden. This is why `main_video_h` is cropped separately.

### Zero-overlap mode

If `overlap_h <= 0`, the fade stage is skipped entirely to avoid invalid crop height and unnecessary graph complexity.

## 8. Stage 4 — Overlay Plan

Overlay stage is final-canvas post-composition.

### Text overlays

1. `TextEngine.render_asset()` renders text into a minimal transparent PNG region.
2. The PNG is added as `-loop 1 -i text_region.png`.
3. `TextEngine.build_filter()` applies motion scale/alpha and overlays onto current final canvas label.

### Sticker overlays

1. Sticker image is added as an input.
2. `StickerEngine.build_filter()` scales by normalized canvas width, rotates, applies alpha/motion, and overlays onto current final canvas label.

### Overlay ordering

Current ordering is:

1. all active text overlays;
2. all active sticker overlays.

If visual z-order needs more control later, introduce explicit layer ordering in models rather than changing this implicitly.

## 9. Stage 5 — Final Export

`FinalExportPipeline` appends codec settings through `FFmpegBuilder.output_args()`.

Current default output args:

```text
-c:v libx264
-preset <state.export.preset>
-crf <state.export.crf>
-pix_fmt yuv420p
-c:a aac
-movflags +faststart
```

Important caveat: `-c:a aac` is currently unconditional in output args. For no-audio input, future code should omit audio codec args when no audio is mapped.

## 10. Pipeline Mode Behavior

| Mode | Base video entering overlay stage | Image/fade? | Overlay? |
| --- | --- | --- | --- |
| Pipeline 1 | shuffled video | yes | no |
| Pipeline 2 | image-composited shuffled video | yes | yes |
| Pipeline 3 | shuffled video | no | yes |
| Pipeline 4 | original input video | no | yes |

Pipeline 4 must never assume `composited_v`, image inputs, or fade labels exist.

## 11. Temporary Files

Allowed temporary files:

- `.rendering.mp4` final output staging file.
- extracted `.rendering.m4a` if source has audio and shuffle needs original audio restoration.
- minimal text-region PNG assets.

Disallowed temporary files:

- intermediate video-stage MP4s;
- full-frame RGBA overlay sequences;
- debug text files in release mode;
- fake/silent audio tracks for no-audio inputs.

## 12. Debug Events

Graph stages currently append events like:

```text
[SHUFFLE] segment_count=... order=...
[LAYOUT] image_h=... overlap_h=... offset_y=... fade_start=... source_y=...
[FADE] image_h=... overlap_h=... visible_video_total=... fade_overlay_y=...
[OVERLAY] text index=... asset=... region=minimal_bbox
[OVERLAY] sticker index=... target_width=... center=(x,y) rotation=...
[FINAL] node_count=... resolution=... output=...
```

These are log events, not required debug files.

## 13. Output Directory Rules

The batch output directory is:

```text
first_video.parent / "output"
```

`safe_output_path()` avoids overwrites:

```text
video.mp4
video_001.mp4
video_002.mp4
```

## 14. Renderer Change Checklist

Before modifying renderer logic, verify:

- active pipeline modes still select the correct modules;
- graph labels are valid after each module;
- no stage assumes an optional previous stage exists;
- text/sticker overlay happens after image/fade composition;
- no intermediate video encode is introduced;
- no full-frame overlay sequence is introduced;
- no-audio inputs are handled without audio inputs/maps/codecs;
- output folder remains first-input-folder/output;
- `python -m compileall core gui models utils main.py` passes;
- filter-string unit checks cover new graph behavior.

## 16. Overlay Motion Stage Update — 2026-05-09

Overlay motion is now explicitly part of the overlay stage, after text/sticker asset creation and before final overlay compositing.

Expected filter order for each overlay region:

1. Load or render immutable RGBA region.
2. Scale dynamically with `eval=frame` when motion requires it.
3. Rotate dynamically for sticker rotate-float when requested.
4. Apply RGBA alpha fade if requested.
5. Overlay onto the current final-canvas label with timing `enable='between(t,start,end)'`.

This keeps motion lightweight and avoids full-frame RGBA animation sequences.
