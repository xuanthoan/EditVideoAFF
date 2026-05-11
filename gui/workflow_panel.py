"""Right-side compact workflow controls with pipeline-dependent UI locking."""
from __future__ import annotations

from pathlib import Path

try:
    from PySide6.QtCore import Signal
    from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import (
        QButtonGroup,
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QGraphicsOpacityEffect,
        QGroupBox,
        QListWidget,
        QPushButton,
        QRadioButton,
        QSpinBox,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    Signal = QColor = QIcon = QPainter = QPen = QPixmap = None
    QButtonGroup = QComboBox = QDoubleSpinBox = QFileDialog = QFormLayout = QGraphicsOpacityEffect = None
    QGroupBox = QListWidget = QPushButton = QRadioButton = QSpinBox = QTextEdit = QVBoxLayout = QWidget = None

from core.overlays.template_manager import TemplateManager, TextTemplate
from models.project_state import WorkflowMode


PIPELINE_CONFIG = {
    WorkflowMode.PIPELINE_1: {"shuffle": True, "image": True, "text": False, "sticker": False},
    WorkflowMode.PIPELINE_2: {"shuffle": True, "image": True, "text": True, "sticker": True},
    WorkflowMode.PIPELINE_3: {"shuffle": True, "image": False, "text": True, "sticker": True},
    WorkflowMode.PIPELINE_4: {"shuffle": False, "image": False, "text": True, "sticker": True},
}


if QWidget:
    class WorkflowPanel(QWidget):
        changed = Signal()
        imagePoolSelected = Signal(list)
        stickerSelected = Signal(str)
        stickerControlsChanged = Signal(float, float, str)
        textChanged = Signal(str)

        def __init__(self) -> None:
            super().__init__()
            self.template_manager = TemplateManager()
            self.pipeline_group = QButtonGroup(self)
            self.pipeline_buttons: dict[WorkflowMode, QRadioButton] = {}
            for mode in WorkflowMode:
                button = QRadioButton(mode.value)
                self.pipeline_buttons[mode] = button
                self.pipeline_group.addButton(button)
                button.toggled.connect(lambda _checked: self.apply_pipeline_ui_state())
            self.pipeline_buttons[WorkflowMode.PIPELINE_1].setChecked(True)

            self.scene_sensitivity = QSpinBox(); self.scene_sensitivity.setRange(10, 80); self.scene_sensitivity.setValue(30)
            self.fallback_min = QDoubleSpinBox(); self.fallback_min.setRange(1.0, 10.0); self.fallback_min.setValue(3.0); self.fallback_min.setSuffix("s")
            self.fallback_max = QDoubleSpinBox(); self.fallback_max.setRange(1.0, 12.0); self.fallback_max.setValue(5.0); self.fallback_max.setSuffix("s")

            self.image_list = QListWidget(); self.image_list.setMaximumHeight(58)
            self.image_height = QSpinBox(); self.image_height.setRange(20, 60); self.image_height.setValue(35); self.image_height.setSuffix("%")
            self.overlap = QSpinBox(); self.overlap.setRange(0, 20); self.overlap.setValue(5); self.overlap.setSuffix("%")
            self.crop_focus = QComboBox(); self.crop_focus.addItems(["top", "center", "bottom"]); self.crop_focus.setCurrentText("center")
            self.fade_curve = QComboBox(); self.fade_curve.addItems(["linear", "smooth", "strong"])

            self.text = QTextEdit(); self.text.setMaximumHeight(70)
            self.text.setPlaceholderText("TEXT - nhập text để tự tạo layer")
            self.template = QComboBox()
            self._populate_template_combo()
            self.font_size = QSpinBox(); self.font_size.setRange(18, 260); self.font_size.setValue(96)
            self.motion = QComboBox(); self.motion.addItems(["None", "Fade In", "Fade Out", "Pop", "Bounce", "Scale", "Scale Up", "Scale Down", "Float", "Slide Left", "Slide Right", "Slide Up", "Slide Down", "Pulse", "Shake"])

            self.sticker_scale = QDoubleSpinBox(); self.sticker_scale.setRange(0.05, 0.45); self.sticker_scale.setSingleStep(0.01); self.sticker_scale.setDecimals(2); self.sticker_scale.setValue(0.16); self.sticker_scale.setSuffix(" canvas")
            self.sticker_rotation = QSpinBox(); self.sticker_rotation.setRange(-360, 360); self.sticker_rotation.setValue(0); self.sticker_rotation.setSuffix("°")
            self.sticker_motion = QComboBox(); self.sticker_motion.addItems(["None", "Fade In", "Fade Out", "Pop", "Bounce", "Scale", "Scale Up", "Scale Down", "Float", "Slide Left", "Slide Right", "Slide Up", "Slide Down", "Pulse", "Shake", "Rotate Float"])

            sticker_button = QPushButton("Chọn sticker")
            image_button = QPushButton("Chọn ảnh (multi-select)")
            image_button.clicked.connect(self.pick_images)
            sticker_button.clicked.connect(self.pick_sticker)

            self.text.textChanged.connect(lambda: self.textChanged.emit(self.text.toPlainText()))
            self.sticker_scale.valueChanged.connect(lambda _value: self.emit_sticker_controls())
            self.sticker_rotation.valueChanged.connect(lambda _value: self.emit_sticker_controls())
            self.sticker_motion.currentTextChanged.connect(lambda _text: self.emit_sticker_controls())
            self.image_height.valueChanged.connect(lambda _value: self._clamp_overlap())

            layout = QVBoxLayout(self)
            layout.setContentsMargins(6, 6, 6, 6)
            layout.setSpacing(6)
            self.pipeline_panel = self._pipeline_group()
            self.shuffle_panel = self._scene_group()
            self.image_panel = self._image_group(image_button)
            self.text_panel = self._text_group()
            self.sticker_panel = self._sticker_group(sticker_button)
            for group in (self.pipeline_panel, self.shuffle_panel, self.image_panel, self.text_panel, self.sticker_panel):
                layout.addWidget(group)
            layout.addStretch()
            self.apply_pipeline_ui_state()

        def selected_workflow_mode(self) -> WorkflowMode:
            for mode, button in self.pipeline_buttons.items():
                if button.isChecked():
                    return mode
            return WorkflowMode.PIPELINE_1

        def apply_pipeline_ui_state(self) -> None:
            config = PIPELINE_CONFIG[self.selected_workflow_mode()]
            self._set_panel_state(self.shuffle_panel, config["shuffle"])
            self._set_panel_state(self.image_panel, config["image"])
            self._set_panel_state(self.text_panel, config["text"])
            self._set_panel_state(self.sticker_panel, config["sticker"])
            self.changed.emit()

        def _set_panel_state(self, panel: QGroupBox, enabled: bool) -> None:
            panel.setEnabled(enabled)
            effect = panel.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(panel)
                panel.setGraphicsEffect(effect)
            effect.setOpacity(1.0 if enabled else 0.38)
            panel.setToolTip("" if enabled else "Disabled in current pipeline")
            title_color = "#e8e8e8" if enabled else "#777"
            panel.setStyleSheet(f"QGroupBox {{ color: {title_color}; font-weight: 600; margin-top: 6px; }} QGroupBox::title {{ subcontrol-origin: margin; left: 6px; }}")

        def set_image_pool(self, paths: list[Path]) -> None:
            self.image_list.clear()
            for path in paths:
                self.image_list.addItem(path.name)

        def _populate_template_combo(self) -> None:
            self.template.setIconSize(self._template_icon_size())
            self.template.addItem(TemplateManager.RANDOM_TEMPLATE_NAME)
            for template in self.template_manager.BUILT_INS:
                self.template.addItem(self._template_icon(template), template.name)

        def _template_icon_size(self):
            from PySide6.QtCore import QSize
            return QSize(48, 20)

        def _template_icon(self, template: TextTemplate):
            pixmap = QPixmap(48, 20)
            pixmap.fill(QColor("transparent"))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            width = 24
            for index, color in enumerate(template.preview_colors):
                painter.fillRect(index * width, 0, width, 20, QColor(color))
            painter.setPen(QPen(QColor("#222222"), 1))
            painter.drawRoundedRect(0, 0, 47, 19, 4, 4)
            painter.end()
            return QIcon(pixmap)

        def _compact_form(self, group: QGroupBox) -> QFormLayout:
            form = QFormLayout(group)
            form.setContentsMargins(8, 8, 8, 8)
            form.setVerticalSpacing(4)
            form.setHorizontalSpacing(8)
            return form

        def _pipeline_group(self):
            group = QGroupBox("1. PIPELINE")
            form = self._compact_form(group)
            for mode in WorkflowMode:
                form.addRow(self.pipeline_buttons[mode])
            return group

        def _scene_group(self):
            group = QGroupBox("2. SHUFFLE")
            form = self._compact_form(group)
            form.addRow("Sensitivity", self.scene_sensitivity)
            form.addRow("Fallback min", self.fallback_min)
            form.addRow("Fallback max", self.fallback_max)
            return group

        def _image_group(self, button):
            group = QGroupBox("3. IMAGE")
            form = self._compact_form(group)
            form.addRow(button)
            form.addRow("Images", self.image_list)
            form.addRow("Crop", self.crop_focus)
            form.addRow("Height", self.image_height)
            form.addRow("Overlap", self.overlap)
            form.addRow("Fade", self.fade_curve)
            return group

        def _text_group(self):
            group = QGroupBox("4. TEXT")
            form = self._compact_form(group)
            form.addRow("TEXT", self.text)
            form.addRow("Template", self.template)
            form.addRow("Font", self.font_size)
            form.addRow("Motion", self.motion)
            return group

        def _sticker_group(self, button):
            group = QGroupBox("5. STICKER")
            form = self._compact_form(group)
            form.addRow(button)
            form.addRow("Scale", self.sticker_scale)
            form.addRow("Rotation", self.sticker_rotation)
            form.addRow("Motion", self.sticker_motion)
            return group

        def emit_sticker_controls(self) -> None:
            self.stickerControlsChanged.emit(float(self.sticker_scale.value()), float(self.sticker_rotation.value()), self.sticker_motion.currentText())

        def pick_images(self) -> None:
            files, _ = QFileDialog.getOpenFileNames(self, "Image pool", "", "Images (*.png *.jpg *.jpeg *.webp)")
            paths = [Path(file) for file in files]
            self.set_image_pool(paths)
            self.imagePoolSelected.emit(paths)

        def pick_sticker(self) -> None:
            file, _ = QFileDialog.getOpenFileName(self, "Sticker", "", "Images (*.png *.webp *.jpg)")
            if file:
                self.stickerSelected.emit(file)

        def _clamp_overlap(self) -> None:
            self.overlap.setMaximum(min(20, self.image_height.value()))
else:
    class WorkflowPanel:  # type: ignore[no-redef]
        pass
