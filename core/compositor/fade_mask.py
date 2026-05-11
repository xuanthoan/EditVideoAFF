"""Fade mask expression for the video overlap region."""
from __future__ import annotations


def vertical_alpha_mask(overlap_h: int) -> str:
    safe_overlap = max(1, int(overlap_h))
    return f"format=yuva420p,geq=lum='p(X,Y)':a='255*(1-(Y/{safe_overlap}))'"
