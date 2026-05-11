"""Realtime preview canvas with safe-area, live overlays, and snap guides."""
from __future__ import annotations

from pathlib import Path

from core.overlays.template_manager import TemplateManager
from core.overlays.motion_engine import MotionEngine
from core.overlays.transform import OverlayTransform
from core.overlays.typography_engine import SocialTypographyRenderer
from core.safe_area_engine import NormalizedRect, SafeAreaEngine

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, Signal
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import QLabel
except ImportError:  # lets non-GUI CI import architecture modules without PySide6 installed
    QPointF = QRectF = Qt = Signal = QColor = QPainter = QPen = QPixmap = QLabel = None


if QLabel:
    class PreviewCanvas(QLabel):
        overlayMoved = Signal(str, float, float)
        SNAP_THRESHOLD = 10

        def __init__(self) -> None:
            super().__init__("Preview")
            self.setMinimumSize(520, 780)
            self.setAlignment(Qt.AlignCenter)
            self.setMouseTracking(True)
            self.setStyleSheet("background:#111;color:#aaa;border:1px solid #333;")
            self._snap_x: int | None = None
            self._snap_y: int | None = None
            self._source_pixmap: QPixmap | None = None
            self._safe_area_engine = SafeAreaEngine()
            self._safe_area_platform = "TikTok"
            self._safe_area_enabled = True
            self._snap_enabled = True
            self._template_manager = TemplateManager()
            self._typography_renderer = SocialTypographyRenderer()
            self._motion_engine = MotionEngine()
            self._current_time = 0.0
            self._text_pixmap_cache_key = None
            self._text_pixmap_cache = None
            self._overlays = {
                "text": {"active": False, "x": 0.5, "y": 0.35, "w": 260, "h": 90, "text": "", "template": "Orange White", "font_size": 96, "motion": "None", "start": 0.0, "end": 3.0},
                "sticker": {"active": False, "x": 0.5, "y": 0.55, "w": 120, "h": 120, "pixmap": None, "scale": 0.16, "rotation": 0.0, "motion": "None", "start": 0.0, "end": 3.0},
            }
            self._drag_kind: str | None = None

        def set_safe_area_options(self, platform: str = "TikTok", enabled: bool = True, snap_enabled: bool = True) -> None:
            self._safe_area_platform = platform
            self._safe_area_enabled = enabled
            self._snap_enabled = snap_enabled
            self.update()

        def set_preview_image(self, image_path: Path) -> None:
            pixmap = QPixmap(str(image_path))
            if pixmap.isNull():
                self.setText("Preview unavailable")
                self._source_pixmap = None
            else:
                self.setText("")
                self._source_pixmap = pixmap
                self._apply_scaled_pixmap()
            self.update()

        def set_text_overlay(self, text: str, template: str, font_size: int, active: bool, motion: str = "None") -> None:
            data = self._overlays["text"]
            data.update({"text": text, "template": template, "font_size": font_size, "active": active, "motion": motion})
            self.update()

        def set_sticker_overlay(self, path: Path | None, scale: float, rotation: float, active: bool, motion: str = "None") -> None:
            data = self._overlays["sticker"]
            pixmap = data.get("pixmap")
            if path is not None and (data.get("path") != path or pixmap is None):
                pixmap = QPixmap(str(path))
                data["path"] = path
            data.update({"pixmap": pixmap, "scale": scale, "rotation": rotation, "motion": motion, "active": active and pixmap is not None and not pixmap.isNull()})
            self.update()

        def set_playhead_time(self, time_seconds: float) -> None:
            self._current_time = max(0.0, float(time_seconds))
            self.update()

        def set_overlay_timing(self, kind: str, start: float, end: float) -> None:
            if kind in self._overlays:
                self._overlays[kind]["start"] = max(0.0, float(start))
                self._overlays[kind]["end"] = max(float(end), float(start) + 0.1)
                self.update()

        def set_overlay_active(self, kind: str, active: bool) -> None:
            if kind in self._overlays:
                self._overlays[kind]["active"] = active
                self.update()

        def set_overlay_position(self, kind: str, x: float, y: float) -> None:
            if kind in self._overlays:
                self._overlays[kind]["x"] = min(max(x, 0.0), 1.0)
                self._overlays[kind]["y"] = min(max(y, 0.0), 1.0)
                self.update()

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self._apply_scaled_pixmap()

        def mousePressEvent(self, event):
            if event.button() != Qt.LeftButton:
                return super().mousePressEvent(event)
            for kind in ("sticker", "text"):
                if self._overlay_rect(kind).contains(event.position()):
                    self._drag_kind = kind
                    return
            return super().mousePressEvent(event)

        def mouseMoveEvent(self, event):
            if not self._drag_kind:
                return super().mouseMoveEvent(event)
            x = event.position().x()
            y = event.position().y()
            canvas = self._canvas_rect()
            center_x = canvas.center().x()
            center_y = canvas.center().y()
            self._snap_x = None
            self._snap_y = None
            if self._snap_enabled and abs(x - center_x) <= self.SNAP_THRESHOLD:
                x = center_x
                self._snap_x = int(center_x)
            if self._snap_enabled and abs(y - center_y) <= self.SNAP_THRESHOLD:
                y = center_y
                self._snap_y = int(center_y)
            norm_x = min(max((x - canvas.left()) / max(canvas.width(), 1), 0.0), 1.0)
            norm_y = min(max((y - canvas.top()) / max(canvas.height(), 1), 0.0), 1.0)
            norm_x, norm_y = self._clamp_to_safe_area(self._drag_kind, norm_x, norm_y)
            self.set_overlay_position(self._drag_kind, norm_x, norm_y)
            self.overlayMoved.emit(self._drag_kind, norm_x, norm_y)

        def mouseReleaseEvent(self, event):
            self._drag_kind = None
            self._snap_x = None
            self._snap_y = None
            self.update()
            return super().mouseReleaseEvent(event)

        def _apply_scaled_pixmap(self) -> None:
            if self._source_pixmap is None or self._source_pixmap.isNull():
                return
            scaled = self._source_pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled)

        def paintEvent(self, event):
            super().paintEvent(event)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            if self._safe_area_enabled:
                self._draw_safe_area(painter)
            self._draw_text_overlay(painter)
            self._draw_sticker_overlay(painter)
            guide_pen = QPen(QColor(90, 190, 255, 170), 2)
            painter.setPen(guide_pen)
            if self._snap_x is not None:
                painter.drawLine(self._snap_x, 0, self._snap_x, self.height())
            if self._snap_y is not None:
                painter.drawLine(0, self._snap_y, self.width(), self._snap_y)

        def _draw_text_overlay(self, painter: QPainter) -> None:
            data = self._overlays["text"]
            if not self._overlay_visible(data) or not str(data["text"]).strip():
                return
            template = self._template_manager.get(str(data["template"]))
            canvas = self._canvas_rect()
            key = (str(data["text"]), str(data["template"]), int(data["font_size"]), round(canvas.width()), round(canvas.height()))
            if key != self._text_pixmap_cache_key or self._text_pixmap_cache is None:
                image = self._typography_renderer.render_image(
                    str(data["text"]),
                    template,
                    int(data["font_size"]),
                    round(canvas.width()),
                    round(canvas.height()),
                )
                self._text_pixmap_cache = QPixmap.fromImage(image)
                self._text_pixmap_cache_key = key
            pixmap = self._text_pixmap_cache
            data["w"] = pixmap.width()
            data["h"] = pixmap.height()
            transformed, alpha = self._preview_transform(data, pixmap)
            dx, dy = self._preview_offset(data, transformed, canvas)
            center = QPointF(
                canvas.left() + float(data["x"]) * canvas.width() + dx,
                canvas.top() + float(data["y"]) * canvas.height() + dy,
            )
            painter.save()
            painter.setOpacity(alpha)
            painter.drawPixmap(QPointF(center.x() - transformed.width() / 2, center.y() - transformed.height() / 2), transformed)
            painter.restore()

        def _draw_sticker_overlay(self, painter: QPainter) -> None:
            data = self._overlays["sticker"]
            pixmap = data.get("pixmap")
            if not self._overlay_visible(data) or pixmap is None or pixmap.isNull():
                return
            canvas = self._canvas_rect()
            target_width = OverlayTransform(
                x=float(data["x"]),
                y=float(data["y"]),
                scale_ratio=float(data["scale"]),
                rotation=float(data["rotation"]),
            ).sticker_width_pixels(round(canvas.width()))
            scaled = pixmap.scaled(target_width, target_width, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled, alpha = self._preview_transform(data, scaled)
            data["w"] = scaled.width()
            data["h"] = scaled.height()
            rect = self._overlay_rect("sticker")
            dx, dy = self._preview_offset(data, scaled, canvas)
            rotation_delta = self._preview_rotation_delta(data)
            painter.save()
            center = QPointF(rect.center().x() + dx, rect.center().y() + dy)
            painter.translate(center)
            painter.rotate(float(data["rotation"]) + rotation_delta)
            painter.setOpacity(alpha)
            painter.drawPixmap(QPointF(-scaled.width() / 2, -scaled.height() / 2), scaled)
            painter.restore()

        def _draw_safe_area(self, painter: QPainter) -> None:
            text_rect = self._safe_rect("text")
            sticker_rect = self._safe_rect("sticker")
            painter.fillRect(QRectF(0, 0, self.width(), text_rect.top()), QColor(0, 0, 0, 55))
            painter.fillRect(QRectF(0, text_rect.bottom(), self.width(), self.height() - text_rect.bottom()), QColor(0, 0, 0, 55))
            painter.fillRect(QRectF(0, text_rect.top(), text_rect.left(), text_rect.height()), QColor(0, 0, 0, 45))
            painter.fillRect(QRectF(text_rect.right(), text_rect.top(), self.width() - text_rect.right(), text_rect.height()), QColor(0, 0, 0, 45))
            painter.setPen(QPen(QColor(90, 220, 120, 180), 2, Qt.DashLine))
            painter.drawRoundedRect(text_rect, 8, 8)
            painter.setPen(QPen(QColor(120, 220, 255, 100), 1, Qt.DotLine))
            painter.drawRoundedRect(sticker_rect, 8, 8)
            painter.setPen(QPen(QColor(255, 90, 90, 70), 1, Qt.DotLine))
            for zone in self._safe_area_engine.calculate(self.width(), self.height(), platform=self._safe_area_platform).ui_exclusion_zones:
                painter.drawRect(self._rect_from_normalized(zone))

        def _preview_transform(self, data: dict, pixmap: QPixmap) -> tuple[QPixmap, float]:
            motion = str(data.get("motion", "None"))
            start = float(data.get("start", 0.0))
            end = float(data.get("end", start))
            local_t = max(0.0, self._current_time - start)
            duration = max(end - start, 0.0)
            alpha = self._motion_engine.preview_alpha(motion, local_t, duration)
            scale = self._motion_engine.preview_scale(motion, local_t, duration)
            if abs(scale - 1.0) < 0.001:
                return pixmap, alpha
            return pixmap.scaled(
                max(1, round(pixmap.width() * scale)),
                max(1, round(pixmap.height() * scale)),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            ), alpha

        def _preview_offset(self, data: dict, pixmap: QPixmap, canvas: QRectF) -> tuple[float, float]:
            motion = str(data.get("motion", "None"))
            start = float(data.get("start", 0.0))
            local_t = max(0.0, self._current_time - start)
            return self._motion_engine.preview_offset(
                motion,
                local_t,
                canvas.width(),
                canvas.height(),
                pixmap.width(),
                pixmap.height(),
                float(data.get("x", 0.5)),
                float(data.get("y", 0.5)),
            )

        def _preview_rotation_delta(self, data: dict) -> float:
            motion = str(data.get("motion", "None"))
            start = float(data.get("start", 0.0))
            local_t = max(0.0, self._current_time - start)
            return self._motion_engine.preview_rotation_delta(motion, local_t)

        def _overlay_visible(self, data: dict) -> bool:
            return bool(data["active"]) and float(data.get("start", 0.0)) <= self._current_time <= float(data.get("end", 0.0))

        def _overlay_rect(self, kind: str) -> QRectF:
            data = self._overlays[kind]
            canvas = self._canvas_rect()
            cx = canvas.left() + float(data["x"]) * canvas.width()
            cy = canvas.top() + float(data["y"]) * canvas.height()
            w = float(data["w"])
            h = float(data["h"])
            return QRectF(cx - w / 2, cy - h / 2, w, h)

        def _canvas_rect(self) -> QRectF:
            pixmap = self.pixmap()
            if pixmap is None or pixmap.isNull():
                return QRectF(0, 0, self.width(), self.height())
            x = (self.width() - pixmap.width()) / 2
            y = (self.height() - pixmap.height()) / 2
            return QRectF(x, y, pixmap.width(), pixmap.height())

        def _safe_rect(self, kind: str) -> QRectF:
            areas = self._safe_area_engine.calculate(self.width(), self.height(), platform=self._safe_area_platform)
            normalized = areas.text_safe_rect if kind == "text" else areas.sticker_safe_rect
            return self._rect_from_normalized(normalized)

        def _rect_from_normalized(self, rect: NormalizedRect) -> QRectF:
            canvas = self._canvas_rect()
            return QRectF(
                canvas.left() + rect.x * canvas.width(),
                canvas.top() + rect.y * canvas.height(),
                rect.width * canvas.width(),
                rect.height * canvas.height(),
            )

        def _clamp_to_safe_area(self, kind: str, x: float, y: float) -> tuple[float, float]:
            rect = self._safe_area_engine.calculate(self.width(), self.height(), platform=self._safe_area_platform)
            safe = rect.text_safe_rect if kind == "text" else rect.sticker_safe_rect
            return min(max(x, safe.x), safe.x + safe.width), min(max(y, safe.y), safe.y + safe.height)

        def safe_rect(self) -> tuple[int, int, int, int]:
            rect = self._safe_rect("text")
            return int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
else:
    class PreviewCanvas:  # type: ignore[no-redef]
        pass
