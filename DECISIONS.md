# DECISIONS.md — Architecture and Product Decisions

_Last updated: 2026-05-09_

This document records important decisions already made so future sessions do not reopen or accidentally reverse them.

## 1. One Unified Application

Decision: AutoVideoAFF remains one desktop app, not separate apps for shuffle, compositor, overlays, or export.

Reason:

- User workflow is mass production with minimal clicks.
- Splitting tools would force intermediate exports/imports and slow batch production.

## 2. FFmpeg Is the Final Rendering Engine

Decision: Final video compositing/export uses FFmpeg through subprocess orchestration.

Allowed Python roles:

- GUI.
- Project state.
- Render planning.
- FFmpeg command building.
- Temporary minimal overlay asset generation.
- Process management.

Not allowed:

- MoviePy final render pipeline.
- OpenCV final compositor.
- Recursive QPainter/framebuffer capture as final video output.

## 3. Single Final Encode

Decision: The renderer must keep one final encode per output video.

Allowed:

- Metadata stages.
- FilterGraph stages.
- Temporary PNG text/sticker assets.
- Temporary `.rendering.mp4` final output file before verification/rename.

Not allowed:

- Stage 1 MP4 -> Stage 2 MP4 -> Stage 3 MP4.
- H264/H265 intermediate generation.
- Re-importing intermediate videos.

## 4. Multi-Stage Logic Pipeline

Decision: The pipeline is logically staged but physically merged into one final FFmpeg command.

Logical stages:

1. Shuffle plan.
2. Layout plan.
3. Image compositor/fade plan.
4. Overlay plan.
5. Final export.

Reason:

- Easier to debug than one giant procedural filter string.
- Keeps single final encode.
- Supports modular workflow modes.

## 5. Four Workflow Modes

Decision: The app supports exactly four production workflow modes for now:

1. Shuffle + Image.
2. Shuffle + Image + Overlay.
3. Shuffle + Overlay.
4. Overlay Only.

Only one mode is active at a time.

## 6. Audio Is Optional and Must Never Be Shuffled

Decision: Scene shuffle affects only video frames.

Rules:

- Audio must never be segmented/shuffled.
- If audio exists, extract/remux original audio into final output.
- If audio does not exist, export video-only MP4.
- Do not create fake silent audio tracks.

Status:

- This is a decided architecture rule, but implementation still needs a full no-audio fix.

## 7. Overlay Coordinate System

Decision: Text and sticker overlays use normalized final-canvas center coordinates.

Rules:

- `x=0.5, y=0.5` means final canvas center.
- Coordinates are not preview widget pixels.
- Coordinates are not raw source video pixels.
- Dragging in preview must convert display pixels back into normalized ratios.

## 8. Sticker Scale System

Decision: Sticker scale is canvas-width-relative.

Example:

- `scale=0.16` means sticker target width is about `canvas_width * 0.16`.

Not allowed:

- Scaling based on preview widget pixels.
- Scaling based only on source sticker dimensions.

## 9. Text Typography Rendering

Decision: Final social typography is rendered by Qt/QPainter into minimal transparent PNG regions, then composited by FFmpeg.

Reason:

- FFmpeg `drawtext` did not match preview typography quality.
- Qt/QPainter gives better antialiasing, rounded background, multiline layout, padding, and optical alignment.

Rules:

- Do not return to raw FFmpeg `drawtext` for final typography.
- Do not render full-frame text canvases.
- Render only minimal bounding-box RGBA text regions.

## 10. Text Box Shadow

Decision: Text background boxes should be flat rounded rectangles with no outer/drop shadow.

Allowed:

- Font antialiasing.
- Text styling from templates.

Not allowed:

- Dark halo behind text box.
- Outer glow behind box.
- Drop shadow behind box.

## 11. Overlay Layer Order

Decision: Overlays are final post-composition layers.

Order:

1. base canvas
2. image layer
3. shifted/cropped main video layer
4. fade layer
5. text overlays
6. sticker overlays

Text/sticker must not be applied before viewport/image compositing.

## 12. Image/Fade Layout

Decision: Image compositor uses dynamic percentage layout, not hardcoded `65/5/35` values.

Rules:

- `image_height_percent` default 35, range 20-60.
- `overlap_percent` default 5, range `0..min(20, image_height_percent)`.
- Fade region is the shifted video region overlapping the image.
- Fade source crop uses `source_y = fade_start - offset_y`.

## 13. Safe Area and Snap

Decision: Safe area and snap are core editor behaviors enabled internally by default.

Rules:

- Do not show a separate Safe Area/Snap panel in the current compact GUI.
- Default platform preset is TikTok.
- Safe area applies to final canvas, not raw source video.

## 14. Output Folder

Decision: Output goes beside the first queued video.

Example:

```text
Input:  D:/CampaignA/video1.mp4
Output: D:/CampaignA/output/video1.mp4
```

If the queue includes videos from multiple folders, the first video determines the output root.

## 15. Debug Artifacts

Decision: `debug_filtergraph.txt` and `debug_fade_filter.txt` are developer-mode artifacts only.

Default release behavior:

- Do not write debug text files.
- Export final video only, plus temporary files that are cleaned.

## 16. Mini Timeline Scope

Decision: Mini Timeline is only for overlay timing.

Allowed:

- Overlay start/end.
- Drag/resize overlay duration.
- Playhead preview.
- Text/sticker visibility.

Not allowed:

- Full NLE timeline.
- Video track editing.
- Audio waveform editing.
- Complex keyframe editor.

## 17. Documentation Strategy

Decision: Keep internal docs in Markdown files at repo root.

Current key docs:

- `ARCHITECTURE.md`
- `RENDER_PIPELINE.md`
- `ANIMATION_SYSTEM.md`
- `FFmpeg_PIPELINE.md`
- `PROJECT_STATUS.md`
- `BUGS.md`
- `NEXT_SESSION_HANDOFF.md`
- `CURRENT_TASK.md`
- `DECISIONS.md`
- `AI_AGENT_RULES.md`
- `TESTING.md`
- `KNOWN_ISSUES.md`
- `FILE_STRUCTURE.md`

## 18. Motion Engine Source of Truth

Decision: `core/overlays/motion_engine.py` is the shared source of truth for overlay motion in both preview and export.

Rules:

- Text and sticker engines should call `MotionEngine` instead of duplicating expressions.
- Preview canvas should call `MotionEngine` helper methods instead of hardcoding separate animation math.
- Animated scale must use region transforms, not regenerated PNG assets.
- Fade must animate RGBA overlay alpha after asset creation.
