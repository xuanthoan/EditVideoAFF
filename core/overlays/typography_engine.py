"""Shared Qt/QPainter typography renderer for preview and export parity."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from core.overlays.template_manager import TextTemplate
from utils.ffmpeg_helper import app_root

REFERENCE_HEIGHT = 1920

try:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QImage, QPainter
except ImportError:  # allows non-GUI CI imports when PySide6 is absent
    QRectF = Qt = QColor = QFont = QFontDatabase = QGuiApplication = QImage = QPainter = None


@dataclass(frozen=True, slots=True)
class TypographyStyle:
    line_spacing_ratio: float = 0.32
    horizontal_padding_ratio: float = 0.95
    vertical_padding_ratio: float = 0.58
    border_radius_ratio: float = 0.42
    shadow_opacity: float = 0.22
    max_width_ratio: float = 0.74


class TypographyEngine:
    def scale_factor(self, video_height: int) -> float:
        return video_height / REFERENCE_HEIGHT

    def scale(self, value: float, video_height: int) -> int:
        return round(value * self.scale_factor(video_height))


class SocialTypographyRenderer:
    """Render TikTok-style text into transparent RGBA assets using Qt."""

    FONT_FILES = ("Montserrat-ExtraBold.ttf", "Poppins-ExtraBold.ttf")
    FONT_FAMILIES = ("Montserrat ExtraBold", "Montserrat", "Poppins ExtraBold", "Poppins")
    _fonts_loaded = False
    _owned_app = None

    def __init__(self, style: TypographyStyle | None = None) -> None:
        self.style = style or TypographyStyle()

    def render_image(self, text: str, template: TextTemplate, font_size: int, canvas_width: int, canvas_height: int):
        """Return a minimal text bounding-box image, never a full-frame canvas."""
        if QImage is None:
            raise RuntimeError("PySide6 is required to render social typography assets.")
        self._ensure_qt_app()
        self._load_fonts()
        scaled_font = max(12, round(font_size * canvas_height / REFERENCE_HEIGHT))
        font = self._font(scaled_font)
        probe = QImage(8, 8, QImage.Format_ARGB32_Premultiplied)
        probe.fill(Qt.transparent)
        painter = QPainter(probe)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        lines = text.splitlines() or [text]
        max_text_width = max(metrics.horizontalAdvance(line) for line in lines) if lines else 1
        line_spacing = round(scaled_font * self.style.line_spacing_ratio)
        pad_x = round(scaled_font * self.style.horizontal_padding_ratio)
        pad_y = round(scaled_font * self.style.vertical_padding_ratio)
        text_height = len(lines) * metrics.height() + max(0, len(lines) - 1) * line_spacing
        max_box_width = round(canvas_width * self.style.max_width_ratio)
        box_width = min(max_text_width + pad_x * 2, max_box_width)
        box_height = text_height + pad_y * 2
        shadow_pad = max(6, round(scaled_font * 0.18))
        image = QImage(box_width + shadow_pad * 2, box_height + shadow_pad * 2, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter.end()

        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        box = QRectF(shadow_pad, shadow_pad, box_width, box_height)
        radius = scaled_font * self.style.border_radius_ratio
        painter.setBrush(QColor(template.box_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(box, radius, radius)
        painter.setFont(font)
        painter.setPen(QColor(template.font_color))
        y = box.top() + pad_y
        for line in lines:
            line_rect = QRectF(box.left() + pad_x, y, box.width() - pad_x * 2, metrics.height())
            painter.drawText(line_rect, Qt.AlignHCenter | Qt.AlignVCenter, line)
            y += metrics.height() + line_spacing
        painter.end()
        return image

    def render_png(self, path: Path, text: str, template: TextTemplate, font_size: int, canvas_width: int, canvas_height: int) -> Path:
        """Write only the typography region PNG; FFmpeg positions it on the final canvas."""
        image = self.render_image(text, template, font_size, canvas_width, canvas_height)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(path), "PNG"):
            raise RuntimeError(f"Unable to write typography PNG: {path}")
        return path

    @classmethod
    def _ensure_qt_app(cls) -> None:
        if QGuiApplication is None or QGuiApplication.instance() is not None:
            return
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._owned_app = QGuiApplication([sys.argv[0] or "AutoVideoAFF"])

    @classmethod
    def _load_fonts(cls) -> None:
        if cls._fonts_loaded or QFontDatabase is None:
            return
        font_dir = app_root() / "assets" / "fonts"
        for filename in cls.FONT_FILES:
            font_path = font_dir / filename
            if font_path.exists():
                QFontDatabase.addApplicationFont(str(font_path))
        cls._fonts_loaded = True

    @classmethod
    def _font(cls, size: int):
        available = set(QFontDatabase.families()) if QFontDatabase is not None else set()
        family = next((candidate for candidate in cls.FONT_FAMILIES if candidate in available), cls.FONT_FAMILIES[0])
        font = QFont(family, size)
        font.setWeight(QFont.ExtraBold)
        font.setStyleStrategy(QFont.PreferAntialias)
        return font
