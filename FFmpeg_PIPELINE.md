# AutoVideoAFF FFmpeg Pipeline Reference

_Last updated: 2026-05-08_

This document records how FFmpeg commands are assembled, how inputs/maps/filter labels are expected to work, and what must be fixed or preserved in future development.

## 1. FFmpeg/FFprobe Discovery

`utils/ffmpeg_helper.py` resolves executables in this order:

1. bundled `bin/ffmpeg.exe` / `bin/ffprobe.exe` under app root;
2. executable in app root;
3. current working directory equivalents;
4. system `PATH`.

If required binaries are missing, `FFmpegNotFoundError` is raised with a Vietnamese user-actionable message.

## 2. Probing

Current helper functions:

- `probe_duration(path)`: uses FFprobe `format=duration`.
- `probe_video_size(path)`: uses FFprobe `stream=width,height` for `v:0`.

Known missing helper:

- `has_audio_stream(path)` should be added for no-audio-safe rendering.

Suggested FFprobe command for audio detection:

```bash
ffprobe -v error -select_streams a:0 -show_entries stream=codec_type -of json input.mp4
```

If no audio streams are returned, the final command must not add audio input, audio map, or audio codec args.

## 3. Command Builder Overview

`FFmpegBuilder.build(job, graph)` currently starts commands as:

```text
ffmpeg -y -i <input_video> <graph.inputs...>
```

Then, if `job.original_audio_path` exists, it appends:

```text
-i <original_audio_path>
```

Then it emits filter/map args:

- if graph has chains:
  - `-filter_complex <graph.filter_complex()>`
  - `-map [<graph.video_label>]`
  - optional audio map based on `graph.audio_label`
- if graph has no chains:
  - `-map 0:v -map 0:a?`

Finally it appends `graph.extra_args` and output path.

## 4. Input Indexing Contract

Base input:

```text
0 = source video
```

Additional inputs are appended by graph modules in order:

- Image compositor: looped image input.
- Text overlay: looped generated PNG region inputs.
- Sticker overlay: sticker image inputs.
- Original audio: appended by `FFmpegBuilder` after graph inputs if `job.original_audio_path` is present.

Important: hardcoded audio indexes are fragile. The builder calculates `original_audio_index` as:

```python
1 + sum(1 for token in graph.inputs if token == "-i")
```

Future changes should preserve dynamic index calculation or replace it with a more explicit input registry.

## 5. FilterGraph Output Mapping

When `graph.chains` exists:

```text
-filter_complex <chains joined by semicolon>
-map [graph.video_label]
```

Audio mapping rules currently:

- `graph.audio_label == "original_audio"` and audio input exists:
  - map `<original_audio_index>:a:0`
- other `graph.audio_label` value:
  - if it ends with `?`, map `0:a?`
  - otherwise map `[graph.audio_label]`

Known issue: output args still include `-c:a aac` unconditionally even when no audio is mapped.

## 6. Current Output Codec Args

`FFmpegBuilder.output_args(settings)` currently returns:

```text
-c:v libx264
-preset <preset>
-crf <crf>
-pix_fmt yuv420p
-c:a aac
-movflags +faststart
```

This is acceptable for audio outputs but should become conditional for no-audio videos.

Recommended future interface:

```python
build_ffmpeg_command(has_audio: bool)
# or
FFmpegBuilder.output_args(settings, has_audio: bool)
```

If `has_audio == False`, omit:

- audio input;
- audio map;
- `-c:a aac`;
- any fake/silent audio generation.

## 7. Timestamp and Duration Args

Current shuffle pipeline appends:

```text
-fps_mode passthrough
-fflags +genpts
-shortest
```

Rationale:

- `-fps_mode passthrough` replaced deprecated `-vsync 2`.
- `-fflags +genpts` helps regenerate stable timestamps.
- `-shortest` prevents looped static overlay PNG inputs from keeping the output alive forever.

Be careful with `-shortest`: it is necessary when `-loop 1` PNG inputs exist but can also interact with audio duration. Test both audio and no-audio inputs.

## 8. Shuffle Filter Shape

For video-only shuffle:

```text
[0:v]trim=start=0.000:end=4.000,setpts=PTS-STARTPTS[shv0];
[0:v]trim=start=8.000:end=12.000,setpts=PTS-STARTPTS[shv1];
[shv0][shv1]concat=n=2:v=1:a=0[shuffled_v]
```

No `atrim` should be generated for shuffled segments. Original audio timeline should remain external.

## 9. Image Compositor Filter Shape

For image compositor with overlap:

```text
[image]scale=w=W:h=-1,crop=w=W:h=image_h:x=(iw-W)/2:y=<focus>[bg];
color=c=black@0:s=WxH:d=1[canvas];
[canvas][bg]overlay=x=0:y=image_top[base];
[video]setpts=PTS-STARTPTS,split=2[main_src][fade_src];
[main_src]crop=w=W:h=main_video_h:x=0:y=-offset_y[mainv];
[fade_src]crop=w=W:h=overlap_h:x=0:y=source_y,format=yuva420p,geq=lum='p(X,Y)':a='255*(1-(Y/overlap_h))'[fade];
[base][mainv]overlay=x=0:y=0[main_layer];
[main_layer][fade]overlay=x=0:y=fade_start[composited_v]
```

Important rules:

- numeric `W` and `H` must be injected by Python;
- never emit literal `WxH` in `color=s=`;
- precompute `overlap_h` in Python;
- skip fade graph if `overlap_h <= 0`;
- fade is the viewport overlap region, not raw source video bottom.

## 10. Text Overlay Filter Shape

Text is not drawn by FFmpeg `drawtext`. It is a Qt-rendered minimal PNG region.

Current filter shape:

```text
[text_png]scale=w='<region_scale_expr>':h='<height_expr>':eval=frame,<alpha_filter>[text_src];
[current_video][text_src]overlay=x=W*x_ratio-w/2:y=H*y_ratio-h/2:enable='between(t,start,end)'[text_v]
```

Text PNG inputs are added with:

```text
-loop 1 -i text_region.png
```

Because looped static PNG inputs can be infinite, `-shortest` must be present.

## 11. Sticker Overlay Filter Shape

Current filter shape:

```text
[sticker]
  scale=w='<canvas_width * scale_ratio * motion_expr>':h='-1':eval=frame,
  rotate=<rotation>*PI/180:ow=rotw(iw):oh=roth(ih):c=none,
  <alpha_filter>
[sticker_src];
[current_video][sticker_src]overlay=x=W*x_ratio-w/2:y=H*y_ratio-h/2:enable='between(t,start,end)'[sticker_v]
```

Sticker scale must remain canvas-relative, not source-image-relative.

## 12. Developer Mode Debug Files

Current batch renderer only calls debug-file writers if `render_state.export.developer_mode` is true.

Debug files:

- `debug_filtergraph.txt`: full filtergraph.
- `debug_fade_filter.txt`: fade-relevant chains only.

Release/default mode must not create these files.

## 13. Logs

Renderer logs include timestamps and levels:

```text
[HH:MM:SS] [INFO] ...
[HH:MM:SS] [WARNING] ...
[HH:MM:SS] [ERROR] ...
[HH:MM:SS] [SUCCESS] ...
```

Current renderer logs FFmpeg command lines. It only logs FFmpeg stderr tails on failure, not frame-by-frame spam on success.

## 14. Critical No-Audio Fix Plan

The current code has a known no-audio risk. The correct behavior should be:

### Mode A — source has audio

```text
1. detect audio stream
2. extract original audio to temp m4a/aac
3. render video pipeline video-only
4. add original audio as final input
5. map final video + original audio
6. encode video + AAC audio
```

### Mode B — source has no audio

```text
1. detect no audio stream
2. skip audio extraction
3. render video pipeline video-only
4. do not add audio input
5. do not map audio
6. do not emit -c:a aac
```

Do not use:

- `anullsrc`;
- fake silent track;
- empty `.m4a`;
- hardcoded `-map 2:a:0`.

Recommended code changes:

1. Add `has_audio_stream(path)` in `utils/ffmpeg_helper.py`.
2. Have `BatchRenderer` call it before extraction.
3. If no audio, set `original_audio_path = None` and mark graph/builder as no-audio.
4. Make output args conditional on mapped audio.
5. Add tests for both audio and silent video command generation.

## 15. FFmpeg Change Checklist

Before committing FFmpeg changes:

- inspect generated command for each pipeline mode;
- ensure input indexes are correct after image/text/sticker/audio inputs;
- test no-image/no-overlay pipeline paths;
- test Pipeline 4 overlay-only path;
- test source with audio and source without audio;
- confirm no intermediate MP4 encodes;
- confirm `debug_*.txt` files only appear in developer mode;
- run `python -m compileall core gui models utils main.py`;
- add focused Python assertions for generated filtergraph strings.

## 2026-05-09 Overlay Motion Filter Notes

Overlay motion filters now follow this shape:

```text
[overlay_input]
scale=w='<dynamic_width>':h='<dynamic_height>':eval=frame,
format=rgba,
fade=t=in|out:st=<time>:d=<duration>:alpha=1
[prepared_overlay]

[base][prepared_overlay]
overlay=x=<dynamic_x>:y=<dynamic_y>:enable='between(t,start,end)'
[out]
```

Sticker overlays may also include dynamic `rotate='<expr>'` before alpha preparation.

Important:

- Keep `eval=frame` for dynamic scale expressions.
- Keep overlays as minimal regions, not full-frame sequences.
- Escape expression commas when embedding `if()`, `min()`, or `max()` expressions inside FFmpeg filter options.
