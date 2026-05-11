"""Timestamp normalization constants used by FFmpeg commands."""
from __future__ import annotations

GENPTS_ARGS = ["-fps_mode", "passthrough", "-fflags", "+genpts"]
VIDEO_RESET = "setpts=PTS-STARTPTS"
AUDIO_RESET = "asetpts=PTS-STARTPTS"
