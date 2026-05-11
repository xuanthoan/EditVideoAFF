"""Lightweight timeline placeholder for future AI timing expansion."""
from __future__ import annotations

try:
    from PySide6.QtWidgets import QLabel
except ImportError:
    QLabel = None


if QLabel:
    class TimelinePanel(QLabel):
        def __init__(self) -> None:
            super().__init__("Timeline / motion preview")
else:
    class TimelinePanel:  # type: ignore[no-redef]
        pass
