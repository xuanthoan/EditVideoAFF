"""Toolbar actions."""
from __future__ import annotations

try:
    from PySide6.QtWidgets import QToolBar
except ImportError:
    QToolBar = None


if QToolBar:
    class Toolbar(QToolBar):
        def __init__(self) -> None:
            super().__init__("AutoVideoAFF")
else:
    class Toolbar:  # type: ignore[no-redef]
        pass
