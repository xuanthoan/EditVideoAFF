"""Export panel primitives for render/stop/output-folder controls."""
from __future__ import annotations

try:
    from PySide6.QtWidgets import QPushButton, QTextEdit, QVBoxLayout, QWidget
except ImportError:
    QPushButton = QTextEdit = QVBoxLayout = QWidget = None


if QWidget:
    class ExportPanel(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.render_button = QPushButton("Render Video")
            self.stop_button = QPushButton("Stop")
            self.open_output_button = QPushButton("Open Output Folder")
            self.log_box = QTextEdit()
            self.log_box.setReadOnly(True)
            layout = QVBoxLayout(self)
            for widget in (self.render_button, self.stop_button, self.open_output_button, self.log_box):
                layout.addWidget(widget)
else:
    class ExportPanel:  # type: ignore[no-redef]
        pass
