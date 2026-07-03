from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .fonts import load_font
from .models import RenderedAnnotation

REQUESTED_COLOR = (255, 170, 0)
ACTUAL_COLOR = (0, 170, 255)
LABEL_BG = (0, 0, 0)
LABEL_FG = (255, 255, 255)


def render_bbox_overlay(
    image: Image.Image,
    annotations: list[RenderedAnnotation],
    *,
    show_requested: bool = True,
    show_actual: bool = True,
    show_labels: bool = True,
    line_width: int | None = None,
) -> Image.Image:
    """Return a copy of image with requested/actual bbox annotations drawn on top."""

    overlay = image.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)
    width = line_width or max(2, round(max(overlay.size) / 1200))
    font = load_font(max(12, width * 7))

    for annotation in annotations:
        if show_requested:
            _draw_box(draw, annotation.requested_bbox.to_list(), REQUESTED_COLOR, width)
        if show_actual:
            _draw_box(draw, annotation.bbox.to_list(), ACTUAL_COLOR, width)
        if show_labels:
            label = f"{annotation.field}: {annotation.text}"
            target = annotation.bbox if show_actual else annotation.requested_bbox
            _draw_label(draw, label, target.x, max(0, target.y - 22), font)
    return overlay


def _draw_box(draw: ImageDraw.ImageDraw, xywh: list[int], color: tuple[int, int, int], width: int) -> None:
    x, y, w, h = xywh
    draw.rectangle([x, y, x + w, y + h], outline=color, width=width)


def _draw_label(draw: ImageDraw.ImageDraw, label: str, x: int, y: int, font: ImageFont.ImageFont) -> None:
    left, top, right, bottom = draw.textbbox((x, y), label, font=font)
    pad = 3
    draw.rectangle([left - pad, top - pad, right + pad, bottom + pad], fill=LABEL_BG)
    draw.text((x, y), label, font=font, fill=LABEL_FG)
