"""Small in-memory image path cache for previews."""
from __future__ import annotations

from pathlib import Path


class ImageCache:
    def __init__(self) -> None:
        self._cache: dict[Path, object] = {}

    def get(self, path: Path):
        return self._cache.get(path)

    def set(self, path: Path, image: object) -> None:
        self._cache[path] = image
