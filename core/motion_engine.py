"""Shared motion system for preview + FFmpeg overlay animation.

This module keeps one source of truth for RGBA-region overlay motion without
switching to full-frame overlay rendering.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, exp, sin

from models.overlay import MotionPreset


@dataclass(frozen=True, slots=True)
class MotionSpec:
    preset: MotionPreset = MotionPreset.NONE
    start: float = 0.0
    end: float = 3.0
    speed: float = 1.0
    strength: float = 1.0

    @property
    def duration(self) -> float:
        return max(0.1, self.end - self.start)

    def local_time(self, t: float) -> float:
        return max(0.0, (t - self.start) * max(0.1, self.speed))


@dataclass(frozen=True, slots=True)
class MotionState:
    x_offset: float = 0.0
    y_offset: float = 0.0
    scale: float = 1.0
    opacity: float = 1.0
    rotation_delta_deg: float = 0.0


class MotionEvaluator:
    @staticmethod
    def resolve(preset: MotionPreset | str, start: float, end: float, speed: float = 1.0, strength: float = 1.0) -> MotionSpec:
        motion = preset if isinstance(preset, MotionPreset) else MotionPreset.from_label(str(preset))
        s = max(0.0, float(start))
        e = max(s + 0.1, float(end))
        return MotionSpec(motion, s, e, max(0.1, float(speed)), max(0.1, float(strength)))

    @staticmethod
    def evaluate(spec: MotionSpec, t: float) -> MotionState:
        lt = spec.local_time(t)
        strength = spec.strength
        duration = spec.duration
        p = min(max(lt / duration, 0.0), 1.0)

        opacity = 1.0
        if spec.preset in {MotionPreset.FADE, MotionPreset.FADE_IN}:
            opacity = min(max(lt / 0.35, 0.0), 1.0)
        elif spec.preset == MotionPreset.FADE_OUT:
            fade_t = lt - max(duration - 0.35, 0.0)
            opacity = 1.0 - min(max(fade_t / 0.35, 0.0), 1.0)

        scale = 1.0
        if spec.preset in {MotionPreset.POP, MotionPreset.ZOOM}:
            if lt < 0.15:
                scale = 0.80 + 0.40 * min(max(lt / 0.15, 0.0), 1.0)
            elif lt < 0.30:
                scale = 1.20 - 0.20 * min(max((lt - 0.15) / 0.15, 0.0), 1.0)
        elif spec.preset == MotionPreset.BOUNCE:
            if lt < 0.25:
                scale = 0.85 + 0.23 * min(max(lt / 0.25, 0.0), 1.0)
            elif lt < 0.55:
                scale = 1.08 - 0.08 * min(max((lt - 0.25) / 0.30, 0.0), 1.0)
        elif spec.preset in {MotionPreset.SCALE, MotionPreset.SCALE_UP}:
            scale = 1.0 + 0.15 * p
        elif spec.preset == MotionPreset.SCALE_DOWN:
            scale = 1.15 - 0.15 * p
        elif spec.preset == MotionPreset.PULSE:
            scale = 1.0 + 0.05 * sin(lt * 8)

        x_offset = y_offset = 0.0
        if spec.preset in {MotionPreset.FLOAT, MotionPreset.DRIFT}:
            x_offset, y_offset = 18 * sin(lt * 1.4), 12 * cos(lt * 1.1)
        elif spec.preset == MotionPreset.SHAKE:
            x_offset, y_offset = 8 * sin(lt * 42), 6 * cos(lt * 55)
        elif spec.preset == MotionPreset.ELASTIC:
            y_offset = 28 * sin(22 * lt) * exp(-3 * lt)

        rotation_delta = 8 * sin(lt * 3) if spec.preset == MotionPreset.ROTATE_FLOAT else 0.0
        return MotionState(x_offset * strength, y_offset * strength, scale, opacity, rotation_delta * strength)


class PreviewTransformEvaluator:
    @staticmethod
    def state_for_time(spec: MotionSpec, current_time: float) -> MotionState:
        return MotionEvaluator.evaluate(spec, current_time)


class FFmpegExpressionBuilder:
    @staticmethod
    def _e(value: str) -> str:
        return value.replace(",", r"\,")

    @staticmethod
    def _clip01(value: str) -> str:
        return FFmpegExpressionBuilder._e(f"min(max({value},0),1)")

    @staticmethod
    def local_time(start: float = 0.0, speed: float = 1.0) -> str:
        return f"((t-{max(0.0, float(start)):.3f})*{max(0.1, float(speed)):.3f})"
