"""Built-in text templates; color pickers are intentionally not exposed."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextTemplate:
    name: str
    font_color: str
    box_color: str
    border_color: str
    shadow_color: str
    preview_colors: tuple[str, str]
    stroke_width: int = 0
    padding: int = 24


class TemplateManager:
    RANDOM_TEMPLATE_NAME = "Random Template"
    BUILT_INS = [
        TextTemplate("Orange White", "#FFFFFF", "#F58B57", "#FFFFFF", "black@0.22", ("#FFFFFF", "#F58B57")),
        TextTemplate("White Black", "#000000", "#FFFFFF", "#000000", "black@0.20", ("#000000", "#FFFFFF")),
        TextTemplate("Pink White", "#FFFFFF", "#FF3FA4", "#FFFFFF", "black@0.35", ("#FFFFFF", "#FF3FA4")),
        TextTemplate("Red White", "#FFFFFF", "#FF4B4B", "#FFFFFF", "black@0.35", ("#FFFFFF", "#FF4B4B")),
        TextTemplate("Yellow White", "#FFFFFF", "#EFCB39", "#FFFFFF", "black@0.35", ("#FFFFFF", "#EFCB39")),
        TextTemplate("Pastel Pink", "#F0537A", "#FFD7DF", "#F0537A", "black@0.20", ("#F0537A", "#FFD7DF")),
        TextTemplate("Green White", "#FFFFFF", "#8BC34A", "#FFFFFF", "black@0.35", ("#FFFFFF", "#8BC34A")),
    ]

    def names(self) -> list[str]:
        return [template.name for template in self.BUILT_INS]

    def get(self, name: str) -> TextTemplate:
        if name == self.RANDOM_TEMPLATE_NAME:
            return self.BUILT_INS[0]
        return next((template for template in self.BUILT_INS if template.name == name), self.BUILT_INS[0])

    def random_name(self, last_name: str | None = None) -> str:
        import random

        names = self.names()
        choices = [name for name in names if name != last_name] or names
        return random.choice(choices)
