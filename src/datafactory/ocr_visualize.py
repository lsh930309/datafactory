from __future__ import annotations

from PIL import Image, ImageDraw

from .fonts import load_font
from .ocr_models import OcrDetection, OcrResult

DETECTION_COLOR = (0, 220, 80)
POLYGON_COLOR = (255, 120, 0)
LABEL_BG = (0, 0, 0)
LABEL_FG = (255, 255, 255)


def render_ocr_overlay(image: Image.Image, result: OcrResult, *, show_labels: bool = True) -> Image.Image:
    overlay = image.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)
    line_width = max(2, round(max(overlay.size) / 1400))
    font = load_font(max(12, line_width * 7))
    for detection in result.detections:
        _draw_polygon(draw, detection.polygon, POLYGON_COLOR, line_width)
        box = detection.bbox
        draw.rectangle([box.x, box.y, box.right, box.bottom], outline=DETECTION_COLOR, width=line_width)
        if show_labels:
            label = _label(detection)
            _draw_label(draw, label, box.x, max(0, box.y - 22), font)
    return overlay


def _draw_polygon(draw: ImageDraw.ImageDraw, polygon: list[list[int]], color: tuple[int, int, int], width: int) -> None:
    if len(polygon) < 2:
        return
    points = [(int(x), int(y)) for x, y in polygon]
    draw.line(points + [points[0]], fill=color, width=width)


def _label(detection: OcrDetection) -> str:
    score = "" if detection.confidence is None else f" {detection.confidence:.2f}"
    text = detection.text if detection.text else "<det>"
    return f"{detection.id}{score}: {text[:24]}"


def _draw_label(draw: ImageDraw.ImageDraw, label: str, x: int, y: int, font) -> None:
    left, top, right, bottom = draw.textbbox((x, y), label, font=font)
    pad = 3
    draw.rectangle([left - pad, top - pad, right + pad, bottom + pad], fill=LABEL_BG)
    draw.text((x, y), label, font=font, fill=LABEL_FG)
