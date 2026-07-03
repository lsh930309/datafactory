"""Punched/perforated text rendering helpers for cleanroom document images.

The goal is not physical press simulation. It is a reusable Pillow primitive that
renders serial numbers or short Latin labels as small embossed holes, similar to
7-segment or dot-matrix punch markings seen on scanned business documents.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from PIL import Image, ImageDraw

# Seven-segment identifiers:
#   a: top, b: upper-right, c: lower-right, d: bottom,
#   e: lower-left, f: upper-left, g: middle
SEGMENTS: Mapping[str, str] = {
    '0': 'abcdef',
    '1': 'bc',
    '2': 'abged',
    '3': 'abgcd',
    '4': 'fgbc',
    '5': 'afgcd',
    '6': 'afgecd',
    '7': 'abc',
    '8': 'abcdefg',
    '9': 'abfgcd',
    'A': 'abcefg',
    'B': 'fcdeg',
    'C': 'afed',
    'D': 'bcdeg',
    'E': 'afged',
    'F': 'afge',
    'G': 'afedc',
    'H': 'fbceg',
    'I': 'bc',
    'J': 'bcde',
    'K': 'feg',
    'L': 'fed',
    'M': 'abcef',
    'N': 'abcef',
    'O': 'abcdef',
    'P': 'abfeg',
    'Q': 'abcdfg',
    'R': 'abfegc',
    'S': 'afgcd',
    'T': 'fedg',
    'U': 'bcdef',
    'V': 'bcdef',
    'W': 'bcdef',
    'X': 'fbceg',
    'Y': 'fbgcd',
    'Z': 'abged',
}


@dataclass(frozen=True)
class PunchedStyle:
    scale: float = 7.0
    hole_radius: float = 3.0
    spacing: float = 9.0
    jitter: float = 0.55
    alpha: int = 170
    shadow_alpha: int = 90
    seed: int = 19


def _segment_lines(x: float, y: float, s: float) -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    w, h = 8.0 * s, 14.0 * s
    pad = 1.2 * s
    mid = y + h / 2.0
    return {
        'a': ((x + pad, y), (x + w - pad, y)),
        'b': ((x + w, y + pad), (x + w, mid - pad * 0.45)),
        'c': ((x + w, mid + pad * 0.45), (x + w, y + h - pad)),
        'd': ((x + pad, y + h), (x + w - pad, y + h)),
        'e': ((x, mid + pad * 0.45), (x, y + h - pad)),
        'f': ((x, y + pad), (x, mid - pad * 0.45)),
        'g': ((x + pad, mid), (x + w - pad, mid)),
    }


def _points_on_line(a: tuple[float, float], b: tuple[float, float], spacing: float) -> Iterable[tuple[float, float]]:
    ax, ay = a
    bx, by = b
    length = max(1.0, math.hypot(bx - ax, by - ay))
    n = max(2, int(length / max(1.0, spacing)) + 1)
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        yield ax + (bx - ax) * t, ay + (by - ay) * t


def _draw_hole(layer: ImageDraw.ImageDraw, cx: float, cy: float, r: float, style: PunchedStyle, rng: random.Random) -> None:
    jx = rng.uniform(-style.jitter, style.jitter)
    jy = rng.uniform(-style.jitter, style.jitter)
    rr = r * rng.uniform(0.83, 1.18)
    cx += jx
    cy += jy
    # Lower-right pressure shadow, inner paper depression, upper-left catchlight.
    layer.ellipse([cx - rr + 1.4, cy - rr + 1.6, cx + rr + 1.4, cy + rr + 1.6], fill=(85, 76, 60, style.shadow_alpha))
    layer.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(231, 226, 211, style.alpha), outline=(151, 143, 124, min(220, style.alpha + 35)))
    layer.ellipse([cx - rr * 0.55, cy - rr * 0.62, cx - rr * 0.02, cy - rr * 0.08], fill=(255, 255, 248, min(150, style.alpha)))


def punched_text_size(text: str, style: PunchedStyle | None = None) -> tuple[int, int]:
    style = style or PunchedStyle()
    s = style.scale
    width = 0.0
    for ch in text:
        if ch == ' ':
            width += 5 * s
        elif ch in '.·':
            width += 3.2 * s
        elif ch == '-':
            width += 5.5 * s
        else:
            width += 10.2 * s
    return int(math.ceil(max(1.0, width))), int(math.ceil(14 * s + 2 * style.hole_radius))


def draw_punched_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, style: PunchedStyle | None = None) -> tuple[int, int, int, int]:
    """Draw perforated 7-segment-like text onto a Pillow ImageDraw canvas.

    Returns the approximate bounding box `(x1, y1, x2, y2)`.
    """
    style = style or PunchedStyle()
    base: Image.Image = draw._image  # Pillow keeps the target image here; scripts already use this convention.
    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer, 'RGBA')
    rng = random.Random(style.seed + sum(ord(c) for c in text))
    x, y = xy
    start_x = float(x)
    cursor = float(x)
    r = style.hole_radius
    s = style.scale
    for raw in text.upper():
        if raw == ' ':
            cursor += 5 * s
            continue
        if raw in '.·':
            _draw_hole(ld, cursor + 1.5 * s, y + 13.2 * s, r, style, rng)
            cursor += 3.2 * s
            continue
        if raw == '-':
            line = _segment_lines(cursor, y, s)['g']
            for pt in _points_on_line(*line, style.spacing):
                _draw_hole(ld, *pt, r, style, rng)
            cursor += 5.5 * s
            continue
        segs = SEGMENTS.get(raw)
        if not segs:
            cursor += 6.5 * s
            continue
        lines = _segment_lines(cursor, y, s)
        for seg in segs:
            for pt in _points_on_line(*lines[seg], style.spacing):
                _draw_hole(ld, *pt, r, style, rng)
        cursor += 10.2 * s
    base.paste(Image.alpha_composite(base.convert('RGBA'), layer).convert(base.mode), (0, 0))
    return (int(start_x - r - 2), int(y - r - 2), int(cursor + r + 2), int(y + 14 * s + r + 4))
