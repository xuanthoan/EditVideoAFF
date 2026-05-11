"""Sequential batch renderer that keeps the UI responsive via callbacks."""
from __future__ import annotations

import copy
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from core.pipeline.manager import PipelineManager
from core.overlays.template_manager import TemplateManager
from models.project_state import ProjectState, WorkflowMode
from utils.ffmpeg_helper import FFmpegNotFoundError, executable, validate_ffmpeg_pair
from utils.file_helper import output_directory_for_videos, safe_output_path, temporary_output_path
from utils.process_manager import ProcessManager, RenderStopped

ProgressCallback = Callable[[int, int, str], None]
LogCallback = Callable[[str], None]


class BatchRenderer:
    def __init__(self, manager: PipelineManager | None = None, debug: bool = False) -> None:
        self.manager = manager or PipelineManager()
        self.debug = debug
        self.process_manager = ProcessManager()
        self.template_manager = TemplateManager()
        self._last_random_template: str | None = None

    def stop(self) -> None:
        self.process_manager.stop_all()

    def render(
        self,
        state: ProjectState,
        progress: ProgressCallback | None = None,
        log: LogCallback | None = None,
    ) -> list[str]:
        self.process_manager.reset()
        outputs: list[str] = []
        total = len(state.videos)
        if total == 0:
            self._log(log, "WARNING", "Không có video trong queue.")
            return outputs

        try:
            validate_ffmpeg_pair()
        except FFmpegNotFoundError as exc:
            self._log(log, "ERROR", str(exc))
            raise

        batch_output_dir = output_directory_for_videos(state.videos, state.export.output_dir)
        self._log(log, "INFO", f"Workflow: {state.workflow_mode.value}")
        self._log(log, "INFO", "FFmpeg đã sẵn sàng.")
        self._log(log, "INFO", f"Output folder: {batch_output_dir}")
        for index, video in enumerate(state.videos, start=1):
            if self.process_manager.stop_requested:
                break
            output = safe_output_path(batch_output_dir, video)
            temp_output = temporary_output_path(output)
            temp_audio = temporary_output_path(output.with_suffix(".m4a"))
            temp_output.unlink(missing_ok=True)
            temp_audio.unlink(missing_ok=True)
            message = f"Rendering... {index}/{total}: {video.name}"
            if progress:
                progress(index, total, message)
            self._log(log, "INFO", message)
            self._log(log, "INFO", f"Output: {output}")

            original_audio_path: Path | None = None
            try:
                if state.workflow_mode in {WorkflowMode.PIPELINE_1, WorkflowMode.PIPELINE_2, WorkflowMode.PIPELINE_3}:
                    self._log(log, "INFO", "Extracting original audio before shuffle.")
                    original_audio_path = self._extract_original_audio(video, temp_audio, log)
                    self._log(log, "INFO", "Detecting scenes...")
                    self._log(log, "INFO", "Splitting video-only segments...")
                    self._log(log, "INFO", "Shuffling video segments only...")
                if state.workflow_mode in {WorkflowMode.PIPELINE_1, WorkflowMode.PIPELINE_2} and state.image_composite.enabled:
                    self._log(log, "INFO", "Applying image composite...")
                if state.workflow_mode in {WorkflowMode.PIPELINE_2, WorkflowMode.PIPELINE_3, WorkflowMode.PIPELINE_4} and state.overlays.enabled:
                    self._log(log, "INFO", "Rendering overlays...")
                self._log(log, "INFO", "Exporting final video...")
                render_state = self._state_for_video(state)
                cmd = self.manager.build_command(video, temp_output, render_state, original_audio_path=original_audio_path)
                self._log_debug_events(log)
                if render_state.export.developer_mode:
                    self._write_debug_filtergraph(cmd, output, log)
                    self._write_debug_fade_filter(cmd, output, log)
                self._log(log, "INFO", "FFmpeg command: " + self._format_command(cmd))
                self._run_command(cmd, log)
                self._verify_output(temp_output, log)
                temp_output.replace(output)
                self._verify_output(output, log, quiet=True)
                outputs.append(str(output))
                self._log(log, "SUCCESS", f"Video complete: {output}")
            except RenderStopped:
                temp_output.unlink(missing_ok=True)
                self._log(log, "WARNING", "Render stopped by user.")
                break
            except Exception as exc:
                temp_output.unlink(missing_ok=True)
                self._log(log, "ERROR", f"Video failed, skipping: {video.name}. {exc}")
                continue
            finally:
                temp_audio.unlink(missing_ok=True)
                self._cleanup_temp_files(self.manager.last_temp_files, log)
        if self.process_manager.stop_requested:
            self._log(log, "WARNING", "Queue stopped safely.")
        else:
            self._log(log, "SUCCESS", "Render batch hoàn tất.")
        return outputs


    def _state_for_video(self, state: ProjectState) -> ProjectState:
        random_texts = [
            overlay
            for overlay in state.overlays.text_overlays()
            if overlay.template == TemplateManager.RANDOM_TEMPLATE_NAME
        ]
        if not random_texts:
            return state
        render_state = copy.deepcopy(state)
        for overlay in render_state.overlays.text_overlays():
            if overlay.template == TemplateManager.RANDOM_TEMPLATE_NAME:
                selected = self.template_manager.random_name(self._last_random_template)
                self._last_random_template = selected
                overlay.template = selected
        return render_state

    def _extract_original_audio(self, video: Path, audio_output: Path, log: LogCallback | None) -> Path | None:
        copy_cmd = [executable("ffmpeg"), "-y", "-i", str(video), "-vn", "-acodec", "copy", str(audio_output)]
        result = self._run_capture(copy_cmd)
        if result.returncode == 0 and audio_output.exists() and audio_output.stat().st_size > 0:
            return audio_output

        self._log(log, "WARNING", "Không copy được audio gốc, thử fallback AAC.")
        fallback_cmd = [executable("ffmpeg"), "-y", "-i", str(video), "-vn", "-c:a", "aac", str(audio_output)]
        result = self._run_capture(fallback_cmd)
        if result.returncode == 0 and audio_output.exists() and audio_output.stat().st_size > 0:
            return audio_output

        detail = self._stderr_tail(result)
        if "does not contain any stream" in detail or "matches no streams" in detail or "Stream map" in detail:
            self._log(log, "WARNING", "Video không có audio, xuất video không kèm audio.")
            return None
        raise RuntimeError(f"Không tách được audio gốc. {detail}")

    def _log_debug_events(self, log: LogCallback | None) -> None:
        for event in self.manager.last_debug_events:
            self._log(log, "INFO", event)

    def _write_debug_filtergraph(self, cmd: list[str], output: Path, log: LogCallback | None) -> None:
        if "-filter_complex" not in cmd:
            return
        filtergraph = cmd[cmd.index("-filter_complex") + 1]
        debug_path = output.parent / "debug_filtergraph.txt"
        debug_path.write_text(filtergraph, encoding="utf-8")
        self._log(log, "INFO", f"Saved FFmpeg filtergraph debug file: {debug_path}")

    def _write_debug_fade_filter(self, cmd: list[str], output: Path, log: LogCallback | None) -> None:
        if "-filter_complex" not in cmd:
            return
        filtergraph = cmd[cmd.index("-filter_complex") + 1]
        fade_parts = [part for part in filtergraph.split(";") if "fade" in part or "[main_layer]" in part]
        if not fade_parts:
            return
        debug_path = output.parent / "debug_fade_filter.txt"
        debug_path.write_text(";\n".join(fade_parts), encoding="utf-8")
        self._log(log, "INFO", f"Saved FFmpeg fade debug file: {debug_path}")

    def _cleanup_temp_files(self, paths: list[Path], log: LogCallback | None) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                self._log(log, "WARNING", f"Không xoá được file overlay tạm: {path}. {exc}")
        paths.clear()

    def _run_command(self, cmd: list[str], log: LogCallback | None, retries: int = 1) -> None:
        last_result: subprocess.CompletedProcess[str] | None = None
        for attempt in range(retries + 1):
            result = self._run_capture(cmd)
            if result.returncode == 0:
                return
            last_result = result
            self._log(log, "WARNING", f"FFmpeg failed (attempt {attempt + 1}/{retries + 1}).")
        assert last_result is not None
        detail = self._stderr_tail(last_result)
        self._log(log, "ERROR", "FFmpeg stderr:\n" + detail)
        raise RuntimeError(f"FFmpeg render lỗi (exit code {last_result.returncode}).")

    def _run_capture(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return self.process_manager.run(cmd)

    def _verify_output(self, output: Path, log: LogCallback | None, quiet: bool = False) -> None:
        if not output.exists():
            raise FileNotFoundError(f"Không tìm thấy file output sau render: {output}")
        size = output.stat().st_size
        if size <= 0:
            raise RuntimeError(f"File output rỗng: {output}")
        cmd = [
            executable("ffprobe"),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(output),
        ]
        result = self._run_capture(cmd)
        if result.returncode != 0 or "video" not in result.stdout:
            detail = (result.stderr or result.stdout or "ffprobe không đọc được file").strip()
            raise RuntimeError(f"File output không hợp lệ hoặc không phát được: {output}. {detail}")
        if not quiet:
            self._log(log, "INFO", f"Đã xác minh output ({size / 1024 / 1024:.2f} MB).")

    @staticmethod
    def _stderr_tail(result: subprocess.CompletedProcess[str], lines: int = 20) -> str:
        output = result.stderr or result.stdout or "Không có log chi tiết từ FFmpeg."
        return "\n".join(output.strip().splitlines()[-lines:])

    @staticmethod
    def _format_command(cmd: list[str]) -> str:
        return " ".join(f'"{part}"' if " " in part else part for part in cmd)

    @staticmethod
    def _log(log: LogCallback | None, level: str, message: str) -> None:
        if log:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log(f"[{timestamp}] [{level}] {message}")
