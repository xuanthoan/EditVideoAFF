"""Video queue panel."""
from __future__ import annotations

from pathlib import Path

try:
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QFileDialog, QListWidget, QPushButton, QVBoxLayout, QWidget
except ImportError:
    Signal = QFileDialog = QListWidget = QPushButton = QVBoxLayout = QWidget = None

from utils.file_helper import collect_videos


if QWidget:
    class QueuePanel(QWidget):
        changed = Signal(list)
        currentPathChanged = Signal(str)

        def __init__(self) -> None:
            super().__init__()
            self.list = QListWidget()
            self.list.setDragDropMode(QListWidget.InternalMove)
            self.list.currentRowChanged.connect(self.emit_current_path)
            add_video = QPushButton("Add video")
            add_folder = QPushButton("Add folder")
            remove = QPushButton("Remove selected")
            clear = QPushButton("Clear all")
            add_video.clicked.connect(self.add_video)
            add_folder.clicked.connect(self.add_folder)
            remove.clicked.connect(self.remove_selected)
            clear.clicked.connect(self.clear_all)
            layout = QVBoxLayout(self)
            for widget in (self.list, add_video, add_folder, remove, clear):
                layout.addWidget(widget)

        def paths(self) -> list[Path]:
            return [Path(self.list.item(i).text()) for i in range(self.list.count())]

        def emit_current_path(self) -> None:
            item = self.list.currentItem()
            if item is not None:
                self.currentPathChanged.emit(item.text())

        def add_video(self) -> None:
            files, _ = QFileDialog.getOpenFileNames(self, "Add videos", "", "Videos (*.mp4 *.mov *.mkv *.webm *.avi)")
            self.add_paths([Path(file) for file in files])

        def add_folder(self) -> None:
            folder = QFileDialog.getExistingDirectory(self, "Add folder")
            if folder:
                self.add_paths(collect_videos(Path(folder)))

        def add_paths(self, paths: list[Path]) -> None:
            was_empty = self.list.count() == 0
            for path in paths:
                self.list.addItem(str(path))
            if paths and was_empty:
                self.list.setCurrentRow(0)
            self.changed.emit(self.paths())
            self.emit_current_path()

        def remove_selected(self) -> None:
            for index in sorted((i.row() for i in self.list.selectedIndexes()), reverse=True):
                self.list.takeItem(index)
            self.changed.emit(self.paths())
            self.emit_current_path()

        def clear_all(self) -> None:
            self.list.clear()
            self.changed.emit([])
else:
    class QueuePanel:  # type: ignore[no-redef]
        pass
