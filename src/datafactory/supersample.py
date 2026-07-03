"""Supersampled Pillow drawing helpers.

Cleanroom renderers draw in logical document coordinates.  These helpers create a
high-resolution backing image, scale all drawing operations/font rasterization,
and finally downsample with LANCZOS, matching the web authoring renderer's
external-font supersampling strategy.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont

DEFAULT_RENDER_SCALE = 2


def _resampling_lanczos() -> int:
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def _s(v: Any, scale: int) -> Any:
    if isinstance(v, (int, float)):
        return int(round(v * scale))
    return v


def scale_value(v: Any, scale: int = DEFAULT_RENDER_SCALE) -> Any:
    return _s(v, scale)


def scale_coords(value: Any, scale: int = DEFAULT_RENDER_SCALE) -> Any:
    """Scale PIL coordinate containers while preserving their shape."""
    if isinstance(value, (int, float)):
        return _s(value, scale)
    if isinstance(value, tuple):
        return tuple(scale_coords(v, scale) for v in value)
    if isinstance(value, list):
        return [scale_coords(v, scale) for v in value]
    return value


@lru_cache(maxsize=512)
def _truetype(path: str, size: int, index: int = 0, encoding: str = "") -> ImageFont.FreeTypeFont:
    kwargs = {"size": max(1, int(round(size)))}
    if index:
        kwargs["index"] = index
    if encoding:
        kwargs["encoding"] = encoding
    return ImageFont.truetype(path, **kwargs)


def scaled_font(font: Any, scale: int = DEFAULT_RENDER_SCALE) -> Any:
    if scale == 1 or font is None:
        return font
    path = getattr(font, "path", None)
    size = getattr(font, "size", None)
    if path and size:
        index = getattr(font, "index", 0) or 0
        encoding = getattr(font, "encoding", "") or ""
        try:
            return _truetype(str(path), int(size) * scale, int(index), str(encoding))
        except Exception:
            return font
    return font


class ScaledDraw:
    """ImageDraw-compatible wrapper using logical coordinates."""

    def __init__(self, image: Image.Image, scale: int = DEFAULT_RENDER_SCALE):
        self._image = image
        self._d = ImageDraw.Draw(image)
        self.scale = max(1, int(scale))

    def _width(self, width: int | float | None) -> int:
        return max(1, int(round((width or 1) * self.scale)))

    def _kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        out = dict(kwargs)
        if "font" in out:
            out["font"] = scaled_font(out.get("font"), self.scale)
        if "width" in out and out["width"] is not None:
            out["width"] = self._width(out["width"])
        if "radius" in out and out["radius"] is not None:
            out["radius"] = _s(out["radius"], self.scale)
        return out

    def text(self, xy: Any, text: Any, *args: Any, **kwargs: Any) -> Any:
        return self._d.text(scale_coords(xy, self.scale), text, *args, **self._kwargs(kwargs))

    def multiline_text(self, xy: Any, text: Any, *args: Any, **kwargs: Any) -> Any:
        return self._d.multiline_text(scale_coords(xy, self.scale), text, *args, **self._kwargs(kwargs))

    def textlength(self, text: Any, *args: Any, **kwargs: Any) -> float:
        return self._d.textlength(text, *args, **self._kwargs(kwargs)) / self.scale

    def textbbox(self, xy: Any, text: Any, *args: Any, **kwargs: Any) -> tuple[float, float, float, float]:
        box = self._d.textbbox(scale_coords(xy, self.scale), text, *args, **self._kwargs(kwargs))
        return tuple(v / self.scale for v in box)  # type: ignore[return-value]

    def line(self, xy: Any, *args: Any, **kwargs: Any) -> Any:
        return self._d.line(scale_coords(xy, self.scale), *args, **self._kwargs(kwargs))

    def rectangle(self, xy: Any, *args: Any, **kwargs: Any) -> Any:
        return self._d.rectangle(scale_coords(xy, self.scale), *args, **self._kwargs(kwargs))

    def rounded_rectangle(self, xy: Any, *args: Any, **kwargs: Any) -> Any:
        return self._d.rounded_rectangle(scale_coords(xy, self.scale), *args, **self._kwargs(kwargs))

    def ellipse(self, xy: Any, *args: Any, **kwargs: Any) -> Any:
        return self._d.ellipse(scale_coords(xy, self.scale), *args, **self._kwargs(kwargs))

    def polygon(self, xy: Any, *args: Any, **kwargs: Any) -> Any:
        return self._d.polygon(scale_coords(xy, self.scale), *args, **self._kwargs(kwargs))

    def arc(self, xy: Any, *args: Any, **kwargs: Any) -> Any:
        return self._d.arc(scale_coords(xy, self.scale), *args, **self._kwargs(kwargs))

    def pieslice(self, xy: Any, *args: Any, **kwargs: Any) -> Any:
        return self._d.pieslice(scale_coords(xy, self.scale), *args, **self._kwargs(kwargs))

    def point(self, xy: Any, *args: Any, **kwargs: Any) -> Any:
        return self._d.point(scale_coords(xy, self.scale), *args, **kwargs)

    def regular_polygon(self, bounding_circle: Any, n_sides: int, *args: Any, **kwargs: Any) -> Any:
        return self._d.regular_polygon(scale_coords(bounding_circle, self.scale), n_sides, *args, **self._kwargs(kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._d, name)


def new_supersampled_page(width: int, height: int, bg: Any, scale: int = DEFAULT_RENDER_SCALE) -> tuple[Image.Image, ScaledDraw]:
    image = Image.new("RGB", (int(width * scale), int(height * scale)), bg)
    return image, ScaledDraw(image, scale)


def finish_supersampled_page(image: Image.Image, size: tuple[int, int], scale: int = DEFAULT_RENDER_SCALE) -> Image.Image:
    if scale <= 1:
        return image
    if image.size == size:
        return image
    return image.resize(size, _resampling_lanczos())


def resize_logical(image: Image.Image, scale: int = DEFAULT_RENDER_SCALE) -> Image.Image:
    if scale <= 1:
        return image
    return image.resize((max(1, int(round(image.width * scale))), max(1, int(round(image.height * scale)))), _resampling_lanczos())


def paste_logical(draw: Any, image: Image.Image, xy: tuple[int | float, int | float], mask: Image.Image | None = None) -> None:
    scale = getattr(draw, "scale", 1)
    target = resize_logical(image, scale)
    if mask is image and image.mode in ("RGBA", "LA"):
        target_mask = target
    elif mask is not None:
        target_mask = resize_logical(mask, scale)
    elif target.mode in ("RGBA", "LA"):
        target_mask = target
    else:
        target_mask = None
    draw._image.paste(target, (int(round(xy[0] * scale)), int(round(xy[1] * scale))), target_mask)


def alpha_composite_logical(draw: Any, overlay: Image.Image) -> None:
    """Composite a logical-size RGBA overlay onto a supersampled page."""
    scale = getattr(draw, "scale", 1)
    high = resize_logical(overlay.convert("RGBA"), scale)
    draw._image.paste(Image.alpha_composite(draw._image.convert("RGBA"), high).convert("RGB"))
