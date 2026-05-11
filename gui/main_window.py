"""Main desktop window for the unified app."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

try:
    from PySide6.QtCore import Qt, QThread, QUrl, Signal
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QPushButton, QScrollArea, QSplitter, QStatusBar, QTextEdit, QVBoxLayout, QWidget
except ImportError:
    Qt = QThread = QUrl = Signal = QDesktopServices = QHBoxLayout = QMainWindow = QPushButton = QScrollArea = QSplitter = QStatusBar = QTextEdit = QVBoxLayout = QWidget = None

from core.renderer.batch_renderer import BatchRenderer
from core.renderer.preview_renderer import PreviewRenderer
from gui.mini_timeline import MiniTimeline, TimelineOverlayItem
from gui.preview_canvas import PreviewCanvas
from gui.queue_panel import QueuePanel
from gui.workflow_panel import WorkflowPanel
from models.overlay import MotionPreset
from models.project_state import ProjectState, WorkflowMode
from models.sticker_overlay import StickerOverlay
from utils.ffmpeg_helper import FFmpegNotFoundError, probe_duration
from utils.file_helper import output_directory_for_videos


if QMainWindow:
    class RenderThread(QThread):
        progress = Signal(int, int, str)
        log = Signal(str)
        failed = Signal(str)
        finishedPaths = Signal(list)

        def __init__(self, state: ProjectState) -> None:
            super().__init__()
            self.state = state
            self.renderer = BatchRenderer()

        def stop(self) -> None:
            self.renderer.stop()

        def run(self) -> None:
            try:
                outputs = self.renderer.render(
                    self.state,
                    lambda i, t, m: self.progress.emit(i, t, m),
                    lambda message: self.log.emit(message),
                )
            except Exception as exc:
                self.failed.emit(str(exc))
                return
            self.finishedPaths.emit(outputs)


    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("AutoVideoAFF — Unified Mass Video Production")
            self.state = ProjectState()
            self.queue = QueuePanel()
            self.preview = PreviewCanvas()
            self.timeline = MiniTimeline()
            self.video_duration = 6.0
            self.workflow = WorkflowPanel()
            self.export_button = QPushButton(self.state.render_count_label())
            self.stop_button = QPushButton("Stop")
            self.stop_button.setEnabled(False)
            self.open_output_button = QPushButton("Open Output Folder")
            self.preview_renderer = PreviewRenderer()
            self.preview_cache_dir = Path(tempfile.gettempdir()) / "autovideoaff_preview"
            self.preview_cache_dir.mkdir(parents=True, exist_ok=True)
            self.log_box = QTextEdit()
            self.log_box.setReadOnly(True)
            self.log_box.setMinimumHeight(140)
            self.log_box.setMaximumHeight(220)
            self.log_box.setPlaceholderText("Log tiến trình render sẽ hiển thị tại đây...")
            self.status = QStatusBar()
            self.setStatusBar(self.status)
            self._wire()
            root = QWidget(); layout = QHBoxLayout(root)
            left_splitter = QSplitter(Qt.Vertical)
            left_splitter.setMinimumWidth(280)
            left_splitter.setMaximumWidth(340)
            left_splitter.addWidget(self.queue)
            left_splitter.addWidget(self.log_box)
            left_splitter.setSizes([700, 240])

            workflow_container = QWidget()
            workflow_layout = QVBoxLayout(workflow_container)
            workflow_layout.setContentsMargins(4, 4, 4, 4)
            workflow_layout.setSpacing(4)
            workflow_layout.addWidget(self.workflow)
            workflow_layout.addStretch()
            right_scroll = QScrollArea()
            right_scroll.setWidgetResizable(True)
            right_scroll.setWidget(workflow_container)

            right_column = QWidget()
            right_column.setMinimumWidth(360)
            right_column.setMaximumWidth(420)
            right_column_layout = QVBoxLayout(right_column)
            right_column_layout.setContentsMargins(0, 0, 0, 0)
            right_column_layout.setSpacing(6)
            right_column_layout.addWidget(right_scroll, 1)
            right_column_layout.addWidget(self.export_button)
            right_column_layout.addWidget(self.stop_button)
            right_column_layout.addWidget(self.open_output_button)

            center_column = QWidget()
            center_layout = QVBoxLayout(center_column)
            center_layout.setContentsMargins(0, 0, 0, 0)
            center_layout.setSpacing(6)
            center_layout.addWidget(self.preview, 1)
            center_layout.addWidget(self.timeline, 0)

            layout.addWidget(left_splitter, 0)
            layout.addWidget(center_column, 1)
            layout.addWidget(right_column, 0)
            self.setCentralWidget(root)

        def _wire(self) -> None:
            self.queue.changed.connect(self.set_videos)
            self.queue.currentPathChanged.connect(lambda path: (self.set_video_duration(Path(path)), self.update_preview(Path(path))))
            self.workflow.imagePoolSelected.connect(self.set_image_pool)
            self.workflow.stickerSelected.connect(self.set_sticker)
            self.workflow.stickerControlsChanged.connect(self.set_sticker_controls)
            self.workflow.textChanged.connect(self.set_text)
            self.workflow.template.currentTextChanged.connect(lambda _text: self.update_text_preview())
            self.workflow.font_size.valueChanged.connect(lambda _value: self.update_text_preview())
            self.workflow.motion.currentTextChanged.connect(lambda _text: self.update_text_preview())
            self.workflow.changed.connect(self.sync_preview_panel_state)
            self.preview.overlayMoved.connect(self.set_overlay_position)
            self.timeline.playheadChanged.connect(self.set_playhead_time)
            self.timeline.overlayTimingChanged.connect(self.set_overlay_timing)
            self.timeline.overlaySelected.connect(self.select_overlay)
            self.timeline.overlayVisibilityChanged.connect(self.set_overlay_visibility)
            self.export_button.clicked.connect(self.render)
            self.stop_button.clicked.connect(self.stop_render)
            self.open_output_button.clicked.connect(self.open_output_folder)


        def set_safe_area_options(self, platform: str = "TikTok", enabled: bool = True, snap_enabled: bool = True) -> None:
            self.state.safe_area.platform = platform
            self.state.safe_area.enabled = enabled
            self.state.safe_area.snap_enabled = snap_enabled
            self.preview.set_safe_area_options(platform, enabled, snap_enabled)

        def sync_preview_panel_state(self) -> None:
            mode = self.workflow.selected_workflow_mode()
            overlay_pipeline = mode in {WorkflowMode.PIPELINE_2, WorkflowMode.PIPELINE_3, WorkflowMode.PIPELINE_4}
            self.update_text_preview()
            self.update_sticker_preview()

        def open_output_folder(self) -> None:
            output_path = output_directory_for_videos(self.state.videos, self.state.export.output_dir).resolve()
            output_path.mkdir(parents=True, exist_ok=True)
            self.append_log(f"[INFO] Mở thư mục output: {output_path}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_path)))

        def set_videos(self, paths: list[Path]) -> None:
            self.state.videos = paths
            self.export_button.setText(self.state.render_count_label())
            self.append_log(f"[INFO] Loading videos: {len(paths)} video")
            if paths:
                self.set_video_duration(paths[0])
                self.update_preview(paths[0])
            else:
                self.video_duration = 6.0
                self.timeline.set_duration(self.video_duration)

        def set_image_pool(self, paths: list[Path]) -> None:
            self.state.image_composite.image_pool = paths
            self.state.image_composite.enabled = bool(paths)
            self.workflow.set_image_pool(paths)
            self.append_log(f"[INFO] Đã chọn image pool: {len(paths)} ảnh")

        def set_sticker(self, path: str) -> None:
            self.state.overlays.sticker = StickerOverlay(path=Path(path))
            self.state.overlays.sticker.set_full_duration(self.video_duration)
            self.set_sticker_controls(
                float(self.workflow.sticker_scale.value()),
                float(self.workflow.sticker_rotation.value()),
                self.workflow.sticker_motion.currentText(),
            )
            self.state.overlays.sticker_enabled = True
            self.update_sticker_preview()
            self.refresh_timeline()
            self.append_log(f"[INFO] Đã chọn sticker: {Path(path).name}")

        def set_sticker_controls(self, scale: float, rotation: float, motion: str) -> None:
            self.state.overlays.sticker.scale = scale
            self.state.overlays.sticker.rotation = rotation
            self.state.overlays.sticker.motion = MotionPreset.from_label(motion)
            self.update_sticker_preview()

        def set_overlay_position(self, kind: str, x: float, y: float) -> None:
            if kind == "text":
                self.state.overlays.text.x = x
                self.state.overlays.text.y = y
            elif kind == "sticker":
                self.state.overlays.sticker.x = x
                self.state.overlays.sticker.y = y


        def update_text_preview(self) -> None:
            self.state.overlays.text.template = self.workflow.template.currentText()
            self.state.overlays.text.font_size = self.workflow.font_size.value()
            self.state.overlays.text.motion = MotionPreset.from_label(self.workflow.motion.currentText())
            mode = self.workflow.selected_workflow_mode()
            active = mode in {WorkflowMode.PIPELINE_2, WorkflowMode.PIPELINE_3, WorkflowMode.PIPELINE_4} and self.state.overlays.text.active
            self.preview.set_text_overlay(
                self.state.overlays.text.text,
                self.state.overlays.text.template,
                self.state.overlays.text.font_size,
                active,
                self.state.overlays.text.motion.value,
            )
            self.preview.set_overlay_timing("text", self.state.overlays.text.start_time, self.state.overlays.text.end_time)
            self.preview.set_overlay_position("text", self.state.overlays.text.x, self.state.overlays.text.y)

        def update_sticker_preview(self) -> None:
            mode = self.workflow.selected_workflow_mode()
            active = mode in {WorkflowMode.PIPELINE_2, WorkflowMode.PIPELINE_3, WorkflowMode.PIPELINE_4} and self.state.overlays.sticker.active
            self.preview.set_sticker_overlay(
                self.state.overlays.sticker.path,
                self.state.overlays.sticker.scale,
                self.state.overlays.sticker.rotation,
                active,
                self.state.overlays.sticker.motion.value,
            )
            self.preview.set_overlay_timing("sticker", self.state.overlays.sticker.start_time, self.state.overlays.sticker.end_time)
            self.preview.set_overlay_position("sticker", self.state.overlays.sticker.x, self.state.overlays.sticker.y)

        def set_playhead_time(self, time_seconds: float) -> None:
            self.timeline.set_playhead_time(time_seconds)
            self.preview.set_playhead_time(time_seconds)
            self.update_text_preview()
            self.update_sticker_preview()

        def set_overlay_timing(self, key: str, start: float, end: float) -> None:
            overlay = self._overlay_by_key(key)
            if overlay is None:
                return
            overlay.set_timing(start, end)
            self.preview.set_overlay_timing(key, start, end)
            self.refresh_timeline()
            self.update_text_preview()
            self.update_sticker_preview()

        def select_overlay(self, key: str) -> None:
            if key == "text":
                self.workflow.text.setFocus()
            elif key == "sticker":
                self.workflow.sticker_scale.setFocus()
            self.status.showMessage(f"Selected overlay: {key}")

        def set_overlay_visibility(self, key: str, visible: bool) -> None:
            overlay = self._overlay_by_key(key)
            if overlay is None:
                return
            overlay.enabled = visible
            if key == "text":
                self.state.overlays.text_enabled = visible and self.state.overlays.text.active
            elif key == "sticker":
                self.state.overlays.sticker_enabled = visible and self.state.overlays.sticker.active
            self.update_text_preview()
            self.update_sticker_preview()
            self.refresh_timeline()

        def _overlay_by_key(self, key: str):
            if key == "text":
                return self.state.overlays.text
            if key == "sticker":
                return self.state.overlays.sticker
            return None

        def refresh_timeline(self) -> None:
            items: list[TimelineOverlayItem] = []
            if self.state.overlays.text.text.strip():
                items.append(
                    TimelineOverlayItem(
                        "text",
                        "text",
                        "Text 1",
                        self.state.overlays.text.start_time,
                        self.state.overlays.text.end_time,
                        self.state.overlays.text.enabled,
                    )
                )
            if self.state.overlays.sticker.path is not None:
                items.append(
                    TimelineOverlayItem(
                        "sticker",
                        "sticker",
                        "Sticker 1",
                        self.state.overlays.sticker.start_time,
                        self.state.overlays.sticker.end_time,
                        self.state.overlays.sticker.enabled,
                    )
                )
            self.timeline.set_duration(self.video_duration)
            self.timeline.set_items(items)

        def set_text(self, text: str) -> None:
            was_inactive = not self.state.overlays.text.active
            self.state.overlays.text.text = text
            if was_inactive and text.strip():
                self.state.overlays.text.set_full_duration(self.video_duration)
            active = bool(text.strip())
            self.state.overlays.text_enabled = active
            self.update_text_preview()
            self.refresh_timeline()
            # Keep typing workflow quiet; render logs will show overlay processing when enabled.

        def set_video_duration(self, video_path: Path) -> None:
            try:
                self.video_duration = max(0.1, probe_duration(video_path))
            except (FFmpegNotFoundError, KeyError, ValueError, OSError) as exc:
                self.video_duration = 6.0
                self.append_log(f"[WARNING] Không đọc được duration, dùng timeline 6s: {exc}")
            self.timeline.set_duration(self.video_duration)
            if not self.state.overlays.text.text.strip():
                self.state.overlays.text.set_full_duration(self.video_duration)
            if self.state.overlays.sticker.path is None:
                self.state.overlays.sticker.set_full_duration(self.video_duration)
            self.refresh_timeline()

        def update_preview(self, video_path: Path) -> None:
            if not video_path.exists():
                self.append_log(f"[WARNING] Không tìm thấy video preview: {video_path}")
                return
            cache_name = hashlib.sha1(str(video_path).encode("utf-8")).hexdigest() + ".jpg"
            preview_path = self.preview_cache_dir / cache_name
            try:
                if not preview_path.exists():
                    self.preview_renderer.extract_first_valid_frame(video_path, preview_path)
                self.preview.set_preview_image(preview_path)
            except Exception as exc:
                self.append_log(f"[WARNING] Không tạo được preview: {exc}")

        def sync_state_from_controls(self) -> None:
            mode = self.workflow.selected_workflow_mode()
            self.state.workflow_mode = mode
            self.state.scene_shuffle.enabled = mode in {WorkflowMode.PIPELINE_1, WorkflowMode.PIPELINE_2, WorkflowMode.PIPELINE_3}
            self.state.scene_shuffle.sensitivity = float(self.workflow.scene_sensitivity.value())
            self.state.scene_shuffle.random_mode = True
            self.state.scene_shuffle.keep_first_segment = True
            self.state.scene_shuffle.fallback_min_seconds = float(self.workflow.fallback_min.value())
            self.state.scene_shuffle.fallback_max_seconds = max(float(self.workflow.fallback_max.value()), float(self.workflow.fallback_min.value()))
            self.state.image_composite.enabled = mode in {WorkflowMode.PIPELINE_1, WorkflowMode.PIPELINE_2} and bool(self.state.image_composite.image_pool)
            self.state.image_composite.image_height_percent = float(self.workflow.image_height.value())
            self.state.image_composite.overlap_percent = min(float(self.workflow.overlap.value()), self.state.image_composite.image_height_percent)
            self.state.image_composite.crop_focus = self.workflow.crop_focus.currentText()
            self.state.image_composite.fade_curve = self.workflow.fade_curve.currentText()
            self.set_safe_area_options("TikTok", True, True)
            overlay_pipeline = mode in {WorkflowMode.PIPELINE_2, WorkflowMode.PIPELINE_3, WorkflowMode.PIPELINE_4}
            self.state.overlays.text_enabled = overlay_pipeline and bool(self.state.overlays.text.text.strip())
            self.state.overlays.sticker_enabled = overlay_pipeline and self.state.overlays.sticker.path is not None
            self.state.overlays.text.template = self.workflow.template.currentText()
            self.state.overlays.text.font_size = self.workflow.font_size.value()
            self.state.overlays.text.motion = MotionPreset.from_label(self.workflow.motion.currentText())
            self.set_sticker_controls(
                float(self.workflow.sticker_scale.value()),
                float(self.workflow.sticker_rotation.value()),
                self.workflow.sticker_motion.currentText(),
            )

        def append_log(self, message: str) -> None:
            self.log_box.append(message)

        def render(self) -> None:
            self.sync_state_from_controls()
            self.export_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.export_button.setText("Rendering...")
            self.append_log(f"[INFO] Bắt đầu render batch vào: {output_directory_for_videos(self.state.videos, self.state.export.output_dir).resolve()}")
            self.thread = RenderThread(self.state)
            self.thread.progress.connect(self.render_progress)
            self.thread.log.connect(self.append_log)
            self.thread.failed.connect(self.render_failed)
            self.thread.finishedPaths.connect(self.render_finished)
            self.thread.start()

        def render_progress(self, index: int, total: int, message: str) -> None:
            self.status.showMessage(message)
            self.export_button.setText(f"Rendering... {index}/{total}")

        def stop_render(self) -> None:
            if hasattr(self, "thread"):
                self.thread.stop()
                self.append_log("[WARNING] Stop requested — terminating FFmpeg tasks...")

        def render_finished(self, paths: list[str]) -> None:
            self.export_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.export_button.setText("Render Complete")
            self.status.showMessage(f"Hoàn tất {len(paths)} video")
            self.append_log(f"[SUCCESS] Hoàn tất {len(paths)} video.")
            if self.state.export.auto_open_output:
                self.open_output_folder()

        def render_failed(self, message: str) -> None:
            self.export_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.export_button.setText(self.state.render_count_label())
            self.status.showMessage("Render lỗi")
            self.append_log("[ERROR] " + message)
else:
    class MainWindow:  # type: ignore[no-redef]
        pass
