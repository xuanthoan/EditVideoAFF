"""Shared overlay motion expression builder.

Text and sticker overlays are immutable RGBA regions. Motion is applied after
asset creation by FFmpeg filters/expressions and by matching lightweight preview
helpers. This avoids regenerating full-frame overlay sequences and prevents
recursive framebuffer/sticker rendering bugs.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin

from models.overlay import MotionPreset


@dataclass(frozen=True, slots=True)
class OverlayAnimation:
    """Resolved animation parameters shared by preview and FFmpeg export."""

    preset: MotionPreset = MotionPreset.NONE
    start: float = 0.0
    end: float = 3.0
    fade_duration: float = 0.35
    pop_duration: float = 0.30
    bounce_duration: float = 0.55
    slide_duration: float = 0.35
    speed: float = 1.0
    strength: float = 1.0

    @property
    def duration(self) -> float:
        return max(0.1, self.end - self.start)

    @property
    def local_t(self) -> str:
        return MotionEngine.local_time(self.start)


class MotionEngine:
    """Build matching FFmpeg and preview transforms for overlay regions."""

    @staticmethod
    def _preset(motion: MotionPreset | str) -> MotionPreset:
        return motion if isinstance(motion, MotionPreset) else MotionPreset.from_label(str(motion))

    @staticmethod
    def _e(value: str) -> str:
        """Escape expression commas for FFmpeg filtergraph option values."""
        return value.replace(",", r"\,")

    @staticmethod
    def _clip01_raw(value: str) -> str:
        return f"min(max({value},0),1)"

    @staticmethod
    def _clip01_expr(value: str) -> str:
        return MotionEngine._e(MotionEngine._clip01_raw(value))

    @staticmethod
    def local_time(start: float = 0.0) -> str:
        return f"(t-{max(0.0, float(start)):.3f})"

    def animation(self, motion: MotionPreset | str, start: float = 0.0, end: float | None = None) -> OverlayAnimation:
        start = max(0.0, float(start))
        resolved_end = max(start + 0.1, float(end)) if end is not None else start + 3.0
        return OverlayAnimation(preset=self._preset(motion), start=start, end=resolved_end)

    def position_expr(self, x: float, y: float, motion: MotionPreset, start: float, end: float) -> tuple[str, str, str]:
        """Return top-left overlay expressions in final-canvas space.

        Expressions are evaluated by FFmpeg's overlay filter per frame. The base
        position is always the normalized final-canvas center minus half of the
        animated region size.
        """
        animation = self.animation(motion, start, end)
        base_x = f"W*{x:.4f}-w/2"
        base_y = f"H*{y:.4f}-h/2"
        enable = f"between(t,{animation.start:.3f},{animation.end:.3f})"
        local_t = animation.local_t
        slide_p = self._clip01_expr(f"{local_t}/{animation.slide_duration:.3f}")

        if animation.preset in {MotionPreset.SLIDE, MotionPreset.SLIDE_LEFT}:
            return f"W-(W-({base_x}))*{slide_p}", base_y, enable
        if animation.preset == MotionPreset.SLIDE_RIGHT:
            return f"-w+(({base_x})+w)*{slide_p}", base_y, enable
        if animation.preset == MotionPreset.SLIDE_UP:
            return base_x, f"H-(H-({base_y}))*{slide_p}", enable
        if animation.preset == MotionPreset.SLIDE_DOWN:
            return base_x, f"-h+(({base_y})+h)*{slide_p}", enable
        if animation.preset in {MotionPreset.FLOAT, MotionPreset.DRIFT}:
            return f"{base_x}+18*sin({local_t}*1.4)", f"{base_y}+12*cos({local_t}*1.1)", enable
        if animation.preset == MotionPreset.SHAKE:
            return f"{base_x}+8*sin({local_t}*42)", f"{base_y}+6*cos({local_t}*55)", enable
        if animation.preset == MotionPreset.ELASTIC:
            return base_x, f"{base_y}+28*sin(22*{local_t})*exp(-3*{local_t})", enable
        return base_x, base_y, enable

    def alpha_filter(self, motion: MotionPreset, start: float = 0.0, end: float | None = None, duration: float = 0.35) -> str:
        """Return alpha-preserving FFmpeg filters for fade motion.

        FFmpeg's `fade=...:alpha=1` modifies the alpha plane of the RGBA overlay
        stream, preserving the original PNG/sticker transparency while applying
        the temporal fade factor. Non-fade motions still force RGBA format so the
        overlay keeps transparency through scale/rotate filters.
        """
        animation = self.animation(motion, start, end)
        duration = max(float(duration), 0.05)
        if animation.preset in {MotionPreset.FADE, MotionPreset.FADE_IN}:
            return f",format=rgba,fade=t=in:st={animation.start:.3f}:d={duration:.3f}:alpha=1"
        if animation.preset == MotionPreset.FADE_OUT:
            fade_start = max(animation.start, animation.end - duration)
            return f",format=rgba,fade=t=out:st={fade_start:.3f}:d={duration:.3f}:alpha=1"
        return ",format=rgba"

    def _scale_factor_expr(self, motion: MotionPreset, start: float = 0.0, end: float | None = None) -> str:
        animation = self.animation(motion, start, end)
        local_t = animation.local_t
        duration = animation.duration
        progress = self._clip01_expr(f"{local_t}/{duration:.3f}")
        pop_up = self._clip01_raw(f"{local_t}/0.150")
        pop_down = self._clip01_raw(f"({local_t}-0.150)/0.150")
        bounce_up = self._clip01_raw(f"{local_t}/0.250")
        bounce_down = self._clip01_raw(f"({local_t}-0.250)/0.300")

        if animation.preset in {MotionPreset.POP, MotionPreset.ZOOM}:
            # Social pop: 80% -> 120% -> 100% in 0.30s.
            return self._e(
                f"if(lt({local_t},0),0.80,"
                f"if(lt({local_t},0.150),0.80+0.40*{pop_up},"
                f"if(lt({local_t},0.300),1.20-0.20*{pop_down},1.00)))"
            )
        if animation.preset == MotionPreset.BOUNCE:
            # Slightly longer bounce: 85% -> 108% -> 100%.
            return self._e(
                f"if(lt({local_t},0),0.85,"
                f"if(lt({local_t},0.250),0.85+0.23*{bounce_up},"
                f"if(lt({local_t},0.550),1.08-0.08*{bounce_down},1.00)))"
            )
        if animation.preset in {MotionPreset.SCALE, MotionPreset.SCALE_UP}:
            return f"1.00+0.15*{progress}"
        if animation.preset == MotionPreset.SCALE_DOWN:
            return f"1.15-0.15*{progress}"
        if animation.preset == MotionPreset.PULSE:
            return f"1.00+0.05*sin({local_t}*8)"
        return "1.00"

    def region_scale_expr(
        self,
        base_width: str,
        motion: MotionPreset,
        start: float = 0.0,
        end: float | None = None,
        base_height: str = "-1",
    ) -> tuple[str, str]:
        """Return dynamic region scale expressions for `scale=eval=frame`."""
        factor = self._scale_factor_expr(motion, start, end)
        if factor == "1.00":
            return base_width, base_height
        width = f"({base_width})*({factor})"
        if base_height == "-1":
            return width, "-1"
        return width, f"({base_height})*({factor})"

    def rotation_expr(self, base_degrees: float, motion: MotionPreset | str, start: float = 0.0) -> str:
        preset = self._preset(motion)
        local_t = self.local_time(start)
        if preset == MotionPreset.ROTATE_FLOAT:
            return f"({float(base_degrees):.4f}+8*sin({local_t}*3))*PI/180"
        return f"{float(base_degrees):.4f}*PI/180"

    def preview_alpha(
        self,
        motion: MotionPreset | str,
        local_t: float,
        overlay_duration: float | None = None,
        fade_duration: float = 0.35,
    ) -> float:
        preset = self._preset(motion)
        fade_duration = max(fade_duration, 0.05)
        if preset in {MotionPreset.FADE, MotionPreset.FADE_IN}:
            return min(max(local_t / fade_duration, 0.0), 1.0)
        if preset == MotionPreset.FADE_OUT:
            duration = max(float(overlay_duration), fade_duration) if overlay_duration is not None else fade_duration
            fade_t = local_t - max(duration - fade_duration, 0.0)
            return 1.0 - min(max(fade_t / fade_duration, 0.0), 1.0)
        return 1.0

    def preview_scale(self, motion: MotionPreset | str, local_t: float, overlay_duration: float | None = None) -> float:
        preset = self._preset(motion)
        duration = max(float(overlay_duration or 3.0), 0.1)
        if preset in {MotionPreset.POP, MotionPreset.ZOOM}:
            if local_t < 0:
                return 0.80
            if local_t < 0.15:
                return 0.80 + 0.40 * min(max(local_t / 0.15, 0.0), 1.0)
            if local_t < 0.30:
                return 1.20 - 0.20 * min(max((local_t - 0.15) / 0.15, 0.0), 1.0)
            return 1.0
        if preset == MotionPreset.BOUNCE:
            if local_t < 0:
                return 0.85
            if local_t < 0.25:
                return 0.85 + 0.23 * min(max(local_t / 0.25, 0.0), 1.0)
            if local_t < 0.55:
                return 1.08 - 0.08 * min(max((local_t - 0.25) / 0.30, 0.0), 1.0)
            return 1.0
        if preset in {MotionPreset.SCALE, MotionPreset.SCALE_UP}:
            return 1.0 + 0.15 * min(max(local_t / duration, 0.0), 1.0)
        if preset == MotionPreset.SCALE_DOWN:
            return 1.15 - 0.15 * min(max(local_t / duration, 0.0), 1.0)
        if preset == MotionPreset.PULSE:
            return 1.0 + 0.05 * sin(local_t * 8)
        return 1.0

    def preview_offset(
        self,
        motion: MotionPreset | str,
        local_t: float,
        canvas_width: float,
        canvas_height: float,
        overlay_width: float,
        overlay_height: float,
        x_ratio: float = 0.5,
        y_ratio: float = 0.5,
    ) -> tuple[float, float]:
        preset = self._preset(motion)
        slide_p = min(max(local_t / 0.35, 0.0), 1.0)
        base_left = canvas_width * x_ratio - overlay_width / 2
        base_top = canvas_height * y_ratio - overlay_height / 2
        if preset in {MotionPreset.SLIDE, MotionPreset.SLIDE_LEFT}:
            return (canvas_width - base_left) * (1 - slide_p), 0.0
        if preset == MotionPreset.SLIDE_RIGHT:
            return (-overlay_width - base_left) * (1 - slide_p), 0.0
        if preset == MotionPreset.SLIDE_UP:
            return 0.0, (canvas_height - base_top) * (1 - slide_p)
        if preset == MotionPreset.SLIDE_DOWN:
            return 0.0, (-overlay_height - base_top) * (1 - slide_p)
        if preset in {MotionPreset.FLOAT, MotionPreset.DRIFT}:
            return 18 * sin(local_t * 1.4), 12 * cos(local_t * 1.1)
        if preset == MotionPreset.SHAKE:
            return 8 * sin(local_t * 42), 6 * cos(local_t * 55)
        if preset == MotionPreset.ELASTIC:
            return 0.0, 28 * sin(22 * local_t) * pow(2.718281828, -3 * local_t)
        return 0.0, 0.0

    def preview_rotation_delta(self, motion: MotionPreset | str, local_t: float) -> float:
        if self._preset(motion) == MotionPreset.ROTATE_FLOAT:
            return 8 * sin(local_t * 3)
        return 0.0

    def alpha_expr(self, motion: MotionPreset, duration: float) -> str:
        # Kept for compatibility with older tests/callers; prefer alpha_filter().
        if motion in {MotionPreset.FADE, MotionPreset.FADE_IN}:
            return "if(lt(t,0.35),t/0.35,1)"
        if motion == MotionPreset.FADE_OUT:
            return f"if(gt(t,{max(duration - 0.35, 0):.3f}),max(0,({duration:.3f}-t)/0.35),1)"
        return "1"

    def sticker_scale_expr(self, scale_ratio: float, motion: MotionPreset, canvas_width: int, start: float = 0.0, end: float | None = None) -> tuple[str, str]:
        target_w = max(1, round(canvas_width * min(max(scale_ratio, 0.01), 1.0)))
        return self.region_scale_expr(str(target_w), motion, start, end)
