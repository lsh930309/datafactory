"""Project-local generated visual assets for cleanroom document renderers."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance

from .supersample import paste_logical

ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = ROOT / "assets" / "cleanroom_generated"

KIND_DIR = {
    "logo": "logos",
    "stamp": "stamps",
    "signature": "signatures",
}


@lru_cache(maxsize=64)
def load_cleanroom_asset(kind: str, index: int) -> Image.Image:
    folder = KIND_DIR[kind]
    path = ASSET_ROOT / folder / f"{kind}_{int(index):02d}.png"
    if not path.exists():
        raise FileNotFoundError(path)
    return Image.open(path).convert("RGBA")


def _fit_contain(im: Image.Image, w: int, h: int) -> Image.Image:
    if w <= 0 or h <= 0:
        return im
    out = im.copy()
    out.thumbnail((w, h), Image.Resampling.LANCZOS)
    return out


def _fit_cover(im: Image.Image, w: int, h: int) -> Image.Image:
    if w <= 0 or h <= 0:
        return im
    scale = max(w / im.width, h / im.height)
    resized = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - w) // 2)
    top = max(0, (resized.height - h) // 2)
    return resized.crop((left, top, left + w, top + h))


def paste_cleanroom_asset(
    draw: Any,
    kind: str,
    index: int,
    box: tuple[float, float, float, float] | list[float],
    *,
    opacity: float = 1.0,
    rotate: float = 0.0,
    fit: str = "contain",
) -> None:
    """Paste a generated RGBA cleanroom asset into a logical-coordinate box."""
    x1, y1, x2, y2 = [float(v) for v in box]
    w = max(1, int(round(x2 - x1)))
    h = max(1, int(round(y2 - y1)))
    im = load_cleanroom_asset(kind, index)
    im = _fit_cover(im, w, h) if fit == "cover" else _fit_contain(im, w, h)
    if rotate:
        im = im.rotate(rotate, expand=True, resample=Image.Resampling.BICUBIC)
        im = _fit_contain(im, w, h)
    if opacity < 1:
        alpha = im.getchannel("A")
        alpha = ImageEnhance.Brightness(alpha).enhance(max(0.0, min(1.0, opacity)))
        im.putalpha(alpha)
    px = x1 + (w - im.width) / 2
    py = y1 + (h - im.height) / 2
    paste_logical(draw, im, (px, py), im)


def paste_asset_center(
    draw: Any,
    kind: str,
    index: int,
    cx: float,
    cy: float,
    size: float,
    *,
    opacity: float = 1.0,
    rotate: float = 0.0,
    aspect: float = 1.0,
) -> None:
    half_w = size * aspect / 2
    half_h = size / 2
    paste_cleanroom_asset(draw, kind, index, (cx - half_w, cy - half_h, cx + half_w, cy + half_h), opacity=opacity, rotate=rotate)
