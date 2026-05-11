"""Compact overlay-only timeline for social-video timing control."""
from __future__ import annotations

from dataclasses import dataclass

try:
    from PySide6.QtCore import QRectF, Qt, QTimer, Signal
    from PySide6.QtGui import QColor, QPainter, QPen
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget
except ImportError:  # keep non-GUI imports lightweight in CI
    QRectF = Qt = QTimer = Signal = QColor = QPainter = QPen = QHBoxLayout = QLabel = QListWidget = QListWidgetItem = QPushButton = QVBoxLayout = QWidget = None


@dataclass(slots=True)
class TimelineOverlayItem:
    key: str
    kind: str
    label: str
    start: float
    end: float
    visible: bool = True

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


if QWidget:
    class MiniTimelineTracks(QWidget):
        playheadChanged = Signal(float)
        overlayTimingChanged = Signal(str, float, float)
        overlaySelected = Signal(str)

        TRACK_HEIGHT = 26
        TRACK_GAP = 8
        LEFT_GUTTER = 74
        RIGHT_PAD = 8
        EDGE_HANDLE = 7
        SNAP_THRESHOLD = 5
        MIN_DURATION = 0.1

        def __init__(self) -> None:
            super().__init__()
            self.setMinimumHeight(104)
            self.setMaximumHeight(138)
            self.setMouseTracking(True)
            self.setStyleSheet("background:#151515;border:1px solid #303030;border-radius:6px;")
            self.items: list[TimelineOverlayItem] = []
            self.video_duration = 6.0
            self.playhead_time = 0.0
            self.selected_key: str | None = None
            self._mode: str | None = None
            self._drag_key: str | None = None
            self._drag_offset = 0.0

        def set_items(self, items: list[TimelineOverlayItem]) -> None:
            self.items = items[:20]
            if self.selected_key not in {item.key for item in self.items}:
                self.selected_key = self.items[0].key if self.items else None
            self.update()

        def set_duration(self, duration: float) -> None:
            self.video_duration = max(0.1, float(duration))
            self.playhead_time = min(self.playhead_time, self.video_duration)
            self.update()

        def set_playhead(self, time_seconds: float) -> None:
            self.playhead_time = min(max(float(time_seconds), 0.0), self.video_duration)
            self.update()

        def select_overlay(self, key: str) -> None:
            self.selected_key = key
            self.update()

        def paintEvent(self, event):
            super().paintEvent(event)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            area = self._track_area_width()
            painter.setPen(QColor("#737373"))
            painter.drawText(8, 17, "PLAYHEAD")
            for idx, item in enumerate(self.items):
                y = self._row_y(idx)
                painter.setPen(QColor("#a8a8a8" if item.visible else "#666"))
                painter.drawText(8, int(y + 18), item.label)
                painter.setPen(QPen(QColor("#2a2a2a"), 1))
                painter.drawRoundedRect(QRectF(self.LEFT_GUTTER, y, area, self.TRACK_HEIGHT), 4, 4)
                rect = self._item_rect(item, idx)
                color = QColor("#f28c28") if item.kind == "text" else QColor("#2f8cff")
                color.setAlpha(225 if item.visible else 90)
                painter.setBrush(color)
                painter.setPen(QPen(QColor("#ffe3b6") if item.key == self.selected_key else QColor("#111"), 2))
                painter.drawRoundedRect(rect, 5, 5)
                painter.setPen(QColor("#101010"))
                painter.drawText(rect.adjusted(8, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, f"{item.duration:.2f}s")
            x = self._time_to_x(self.playhead_time)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawLine(int(x), 0, int(x), self.height())

        def mousePressEvent(self, event):
            if event.button() != Qt.LeftButton:
                return super().mousePressEvent(event)
            pos = event.position()
            for idx, item in enumerate(self.items):
                rect = self._item_rect(item, idx)
                if rect.contains(pos):
                    self.selected_key = item.key
                    self._drag_key = item.key
                    self._drag_offset = self._x_to_time(pos.x()) - item.start
                    if abs(pos.x() - rect.left()) <= self.EDGE_HANDLE:
                        self._mode = "resize_left"
                    elif abs(pos.x() - rect.right()) <= self.EDGE_HANDLE:
                        self._mode = "resize_right"
                    else:
                        self._mode = "move"
                    self.overlaySelected.emit(item.key)
                    self.update()
                    return
            self.set_playhead(self._x_to_time(pos.x()))
            self.playheadChanged.emit(self.playhead_time)

        def mouseMoveEvent(self, event):
            pos = event.position()
            if not self._drag_key:
                if pos.x() >= self.LEFT_GUTTER:
                    self.setCursor(Qt.SplitHCursor)
                return super().mouseMoveEvent(event)
            item = next((candidate for candidate in self.items if candidate.key == self._drag_key), None)
            if item is None:
                return
            raw_time = self._x_to_time(pos.x())
            if self._mode == "move":
                duration = item.duration
                start = min(max(raw_time - self._drag_offset, 0.0), max(0.0, self.video_duration - duration))
                start = self._snapped_start(start, duration, item)
                item.start = start
                item.end = start + duration
            elif self._mode == "resize_left":
                time_value = self._snapped_time(raw_time, item)
                item.start = min(max(time_value, 0.0), item.end - self.MIN_DURATION)
            elif self._mode == "resize_right":
                time_value = self._snapped_time(raw_time, item)
                item.end = max(min(time_value, self.video_duration), item.start + self.MIN_DURATION)
            self.overlayTimingChanged.emit(item.key, item.start, item.end)
            self.update()

        def mouseReleaseEvent(self, event):
            self._mode = None
            self._drag_key = None
            self.unsetCursor()
            return super().mouseReleaseEvent(event)

        def _snapped_time(self, time_value: float, item: TimelineOverlayItem) -> float:
            snap_seconds = self._snap_seconds()
            for snap in self._snap_points(item):
                if abs(time_value - snap) <= snap_seconds:
                    return snap
            return time_value

        def _snapped_start(self, start: float, duration: float, item: TimelineOverlayItem) -> float:
            snap_seconds = self._snap_seconds()
            for snap in self._snap_points(item):
                if abs(start - snap) <= snap_seconds:
                    return min(max(snap, 0.0), max(0.0, self.video_duration - duration))
                if abs((start + duration) - snap) <= snap_seconds:
                    return min(max(snap - duration, 0.0), max(0.0, self.video_duration - duration))
            return start

        def _snap_points(self, item: TimelineOverlayItem) -> list[float]:
            points = [self.playhead_time]
            for other in self.items:
                if other.key != item.key:
                    points.extend([other.start, other.end])
            return points

        def _snap_seconds(self) -> float:
            pixels_per_second = self._track_area_width() / self.video_duration
            return self.SNAP_THRESHOLD / max(pixels_per_second, 1)

        def _row_y(self, index: int) -> float:
            return 25 + index * (self.TRACK_HEIGHT + self.TRACK_GAP)

        def _item_rect(self, item: TimelineOverlayItem, index: int) -> QRectF:
            start_x = self._time_to_x(item.start)
            end_x = self._time_to_x(item.end)
            return QRectF(start_x, self._row_y(index), max(8, end_x - start_x), self.TRACK_HEIGHT)

        def _track_area_width(self) -> float:
            return max(1.0, self.width() - self.LEFT_GUTTER - self.RIGHT_PAD)

        def _time_to_x(self, time_seconds: float) -> float:
            return self.LEFT_GUTTER + (min(max(time_seconds, 0.0), self.video_duration) / self.video_duration) * self._track_area_width()

        def _x_to_time(self, x: float) -> float:
            normalized = (x - self.LEFT_GUTTER) / self._track_area_width()
            return min(max(normalized, 0.0), 1.0) * self.video_duration


    class MiniTimeline(QWidget):
        playheadChanged = Signal(float)
        overlayTimingChanged = Signal(str, float, float)
        overlaySelected = Signal(str)
        overlayVisibilityChanged = Signal(str, bool)

        def __init__(self) -> None:
            super().__init__()
            self.setMinimumHeight(120)
            self.setMaximumHeight(180)
            self.setStyleSheet("QWidget{background:#101010;color:#dedede;} QPushButton{background:#252525;color:#eee;border:1px solid #3a3a3a;padding:3px 8px;border-radius:4px;} QListWidget{background:#171717;border:1px solid #303030;border-radius:5px;}")
            self.current_time = 0.0
            self.video_duration = 6.0
            self.play_button = QPushButton("Play")
            self.pause_button = QPushButton("Pause")
            self.stop_button = QPushButton("Stop")
            self.time_label = QLabel("00:00.00 / 00:06.00")
            self.overlay_list = QListWidget()
            self.overlay_list.setMaximumWidth(120)
            self.tracks = MiniTimelineTracks()
            self.timer = QTimer(self)
            self.timer.setInterval(33)
            controls = QHBoxLayout()
            controls.setContentsMargins(0, 0, 0, 0)
            controls.setSpacing(4)
            controls.addWidget(self.play_button)
            controls.addWidget(self.pause_button)
            controls.addWidget(self.stop_button)
            controls.addWidget(self.time_label)
            controls.addStretch()
            left = QVBoxLayout()
            left.setContentsMargins(0, 0, 0, 0)
            left.setSpacing(4)
            left.addLayout(controls)
            left.addWidget(self.tracks, 1)
            layout = QHBoxLayout(self)
            layout.setContentsMargins(6, 4, 6, 4)
            layout.setSpacing(6)
            layout.addLayout(left, 1)
            layout.addWidget(self.overlay_list, 0)
            self.play_button.clicked.connect(self.play)
            self.pause_button.clicked.connect(self.pause)
            self.stop_button.clicked.connect(self.stop)
            self.timer.timeout.connect(self._tick)
            self.tracks.playheadChanged.connect(self.set_playhead_time)
            self.tracks.playheadChanged.connect(self.playheadChanged.emit)
            self.tracks.overlayTimingChanged.connect(self.overlayTimingChanged.emit)
            self.tracks.overlaySelected.connect(self._select_from_tracks)
            self.overlay_list.currentRowChanged.connect(self._select_from_list)
            self.overlay_list.itemChanged.connect(self._visibility_from_list)

        def set_items(self, items: list[TimelineOverlayItem]) -> None:
            self.overlay_list.blockSignals(True)
            self.overlay_list.clear()
            for item in items[:20]:
                row_item = QListWidgetItem(item.label)
                row_item.setFlags(row_item.flags() | Qt.ItemIsUserCheckable)
                row_item.setCheckState(Qt.Checked if item.visible else Qt.Unchecked)
                self.overlay_list.addItem(row_item)
            self.overlay_list.blockSignals(False)
            self.tracks.set_items(items)
            if self.tracks.selected_key and self.overlay_list.currentRow() < 0:
                self.overlay_list.setCurrentRow(0)

        def set_duration(self, duration: float) -> None:
            self.video_duration = max(0.1, float(duration))
            self.tracks.set_duration(self.video_duration)
            self.set_playhead_time(min(self.current_time, self.video_duration))

        def set_playhead_time(self, time_seconds: float) -> None:
            self.current_time = min(max(float(time_seconds), 0.0), self.video_duration)
            self.tracks.set_playhead(self.current_time)
            self.time_label.setText(f"{self._format_time(self.current_time)} / {self._format_time(self.video_duration)}")

        def play(self) -> None:
            self.timer.start()

        def pause(self) -> None:
            self.timer.stop()

        def stop(self) -> None:
            self.timer.stop()
            self.set_playhead_time(0.0)
            self.playheadChanged.emit(0.0)

        def _tick(self) -> None:
            next_time = self.current_time + self.timer.interval() / 1000
            if next_time >= self.video_duration:
                self.stop()
                return
            self.set_playhead_time(next_time)
            self.playheadChanged.emit(self.current_time)

        def _select_from_tracks(self, key: str) -> None:
            for row, item in enumerate(self.tracks.items):
                if item.key == key:
                    self.overlay_list.blockSignals(True)
                    self.overlay_list.setCurrentRow(row)
                    self.overlay_list.blockSignals(False)
                    break
            self.overlaySelected.emit(key)

        def _select_from_list(self, row: int) -> None:
            if 0 <= row < len(self.tracks.items):
                key = self.tracks.items[row].key
                self.tracks.select_overlay(key)
                self.overlaySelected.emit(key)

        def _visibility_from_list(self, item: QListWidgetItem) -> None:
            row = self.overlay_list.row(item)
            if 0 <= row < len(self.tracks.items):
                timeline_item = self.tracks.items[row]
                timeline_item.visible = item.checkState() == Qt.Checked
                self.tracks.update()
                self.overlayVisibilityChanged.emit(timeline_item.key, timeline_item.visible)

        @staticmethod
        def _format_time(seconds: float) -> str:
            minutes = int(seconds // 60)
            remainder = seconds - minutes * 60
            return f"{minutes:02d}:{remainder:05.2f}"
else:
    class MiniTimeline:  # type: ignore[no-redef]
        pass

