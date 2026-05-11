# AI_AGENT_RULES.md — Rules for Future AI Coding Agents

_Last updated: 2026-05-09_

Read this file before modifying code. It captures project-specific guardrails that future AI agents must follow.

## 1. Do Not Rebuild the App

The current project already contains a GUI scaffold, pipeline manager, render graph, batch renderer, overlay engines, and documentation. Future work should modify existing modules rather than replacing the architecture.

Do not:

- Delete and recreate the project.
- Split into multiple separate apps.
- Replace PySide6 with another GUI toolkit.
- Replace FFmpeg with MoviePy/OpenCV for final rendering.

## 2. Preserve Single Final Encode

All render stages before final output must be metadata/filtergraph/asset preparation stages.

Do not create intermediate MP4/H264/H265 files between stages.

Allowed temporary files:

- Minimal text PNG regions.
- Sticker/image inputs selected by user.
- Final `.rendering.mp4` before verification/rename.
- Developer-mode debug text files only when enabled.

## 3. Keep Audio Optional

Never assume a source video has audio.

When changing renderer command generation:

- Probe audio stream existence explicitly.
- Do not add audio input when no audio exists.
- Do not map audio when no audio exists.
- Do not add `-c:a` when no audio is mapped.
- Do not create fake silent tracks unless the user explicitly requests that feature later.

## 4. Do Not Shuffle Audio

Scene shuffle is video-only.

Correct model:

1. Extract original audio if present.
2. Shuffle visual segments only.
3. Compose image/fade/overlays visually.
4. Reattach original audio if present.

## 5. Respect Final-Canvas Overlay Space

Text/sticker overlays are final-canvas overlays.

Do not:

- Attach overlays to source video pixels.
- Apply overlays before image compositor/viewport shift.
- Store overlay positions as preview pixels.
- Store overlay positions as absolute output pixels.

Use normalized ratios and shared transform helpers.

## 6. Keep Minimal Overlay Assets

Text should be rendered as minimal Qt/QPainter RGBA regions.

Do not:

- Render full-frame 1080x1920 RGBA overlays per frame.
- Generate full-frame PNG sequences for normal text/sticker animation.
- Bake motion into regenerated PNG files frame-by-frame.

Motion should be applied in FFmpeg to the immutable overlay region.

## 7. Preserve Preview/Export Parity

When changing overlay motion, typography, coordinates, or safe area:

- Update preview and export logic together.
- Keep formulas/easing consistent.
- Add tests or at least command-string assertions for FFmpeg expressions.

## 8. Keep GUI Compact

Do not add large panels that push render controls out of view.

Current GUI rules:

- Left column: queue and logs.
- Center: preview and mini timeline.
- Right: workflow controls in scroll area plus fixed render/stop/open buttons.
- Safe area/snap settings remain internal; do not re-add a large Safe Area/Snap panel unless explicitly requested.

## 9. Use Existing Docs

Before implementing a major fix, read:

- `CURRENT_TASK.md`
- `KNOWN_ISSUES.md`
- `ARCHITECTURE.md`
- `RENDER_PIPELINE.md`
- `ANIMATION_SYSTEM.md`
- `FFmpeg_PIPELINE.md`
- `NEXT_SESSION_HANDOFF.md`

## 10. Keep Output Routing

Output must go to an `output/` folder beside the first queued input video.

Do not revert output to the project root unless the user explicitly changes the requirement.

## 11. Logging Rules

Normal user logs should be useful but not spammy.

Allowed normal logs:

- workflow start;
- output path;
- scene detection stage;
- image composite stage;
- overlay stage;
- final export;
- warnings/errors;
- success/failure.

Avoid normal UI spam:

- full frame-by-frame FFmpeg progress;
- giant debug graph dumps;
- painter/internal preview updates.

Developer-mode logs/files are allowed behind `ExportSettings.developer_mode`.

## 12. Testing Expectations

At minimum after code changes, run:

```bash
python -m compileall core gui models utils main.py
```

For renderer changes, also add or run focused tests/assertions for:

- FFmpeg command maps;
- audio/no-audio behavior;
- filtergraph labels;
- fade crop math;
- overlay motion expressions;
- output path selection.

## 13. Commit and PR Discipline

For this environment:

- Commit changes on the current branch.
- Create a PR record after committing.
- Do not create a PR if no code/docs changed.

## 14. Overlay Motion Patch Rules

After the 2026-05-09 motion patch, text and sticker motion must continue to use the shared `MotionEngine`.

Rules:

- Add new motion presets to `models.overlay.MotionPreset` first.
- Add matching FFmpeg and preview behavior in `core/overlays/motion_engine.py`.
- Apply motion after immutable RGBA overlay asset creation.
- Keep scale animation in FFmpeg `scale=...:eval=frame`.
- Keep fade as alpha animation on RGBA overlay streams.
- Keep preview transforms routed through the same motion helper formulas.
