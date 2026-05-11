"""Subprocess lifecycle management for FFmpeg jobs."""
from __future__ import annotations

import subprocess
import threading

from utils.ffmpeg_helper import subprocess_startupinfo


class RenderStopped(RuntimeError):
    """Raised when the user stops the current batch."""


class ProcessManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: subprocess.Popen[str] | None = None
        self._stop_requested = False

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested

    def reset(self) -> None:
        self._stop_requested = False

    def stop_all(self) -> None:
        self._stop_requested = True
        with self._lock:
            process = self._current
        if process and process.poll() is None:
            process.kill()

    def run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        if self._stop_requested:
            raise RenderStopped("Render stopped by user.")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=subprocess_startupinfo(),
        )
        with self._lock:
            self._current = process
        try:
            stdout, stderr = process.communicate()
        finally:
            with self._lock:
                if self._current is process:
                    self._current = None
        if self._stop_requested:
            raise RenderStopped("Render stopped by user.")
        return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
