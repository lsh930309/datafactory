from __future__ import annotations

from PIL import Image, ImageDraw

from .fonts import load_font
from .policy import ReviewLabel, ReviewPolicy

STATUS_COLORS = {
    "use": (0, 200, 80),
    "keep": (70, 140, 255),
    "ignore": (235, 70, 70),
}
FILL_ALPHA = {
    "use": 72,
    "keep": 46,
    "ignore": 64,
}


def render_policy_overlay(image: Image.Image, policy: ReviewPolicy, *, show_labels: bool = True) -> Image.Image:
    return render_labels_overlay(image, policy.labels, show_labels=show_labels)


def render_labels_overlay(image: Image.Image, labels: list[ReviewLabel], *, show_labels: bool = True) -> Image.Image:
    base = image.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    line_width = max(2, round(max(base.size) / 1400))
    font = load_font(max(12, line_width * 7))
    for label in labels:
        color = STATUS_COLORS[label.status]
        fill = (*color, FILL_ALPHA[label.status])
        outline = (*color, 255)
        box = label.bbox
        draw.rectangle([box.x, box.y, box.right, box.bottom], fill=fill, outline=outline, width=line_width)
        if show_labels:
            _draw_label(draw, f"{label.id} {label.status}/{label.auto_type}", box.x, max(0, box.y - 22), font, color)
    return Image.alpha_composite(base, layer).convert("RGB")


def _draw_label(draw: ImageDraw.ImageDraw, label: str, x: int, y: int, font, color: tuple[int, int, int]) -> None:
    left, top, right, bottom = draw.textbbox((x, y), label, font=font)
    pad = 3
    draw.rectangle([left - pad, top - pad, right + pad, bottom + pad], fill=(0, 0, 0, 210))
    draw.text((x, y), label, font=font, fill=color)
