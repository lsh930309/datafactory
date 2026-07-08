from __future__ import annotations

from dataclasses import replace
from math import ceil, floor
from statistics import median
from typing import Iterable

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .fonts import load_font
from .models import BBox, FieldSpec, RenderedAnnotation, TemplateSpec


DEFAULT_RENDER_SCALE = 2


def render_template(template: TemplateSpec, values: dict[str, str], *, render_scale: int = DEFAULT_RENDER_SCALE) -> tuple[Image.Image, list[RenderedAnnotation]]:
    image = Image.open(template.image_path).convert("RGB")
    scale = max(1, int(render_scale or 1))
    if scale <= 1:
        return _render_template_on_image(image, template, values)

    original_size = image.size
    scaled_size = (image.width * scale, image.height * scale)
    scaled_image = image.resize(scaled_size, _resampling_lanczos())
    scaled_template = replace(template, fields=[_scale_field(field, scale) for field in template.fields])
    rendered, annotations = _render_template_on_image(scaled_image, scaled_template, values)
    final_image = rendered.resize(original_size, _resampling_lanczos())
    final_annotations = [_unscale_annotation(annotation, scale, original_size) for annotation in annotations]
    return final_image, final_annotations


def _render_template_on_image(image: Image.Image, template: TemplateSpec, values: dict[str, str]) -> tuple[Image.Image, list[RenderedAnnotation]]:
    draw = ImageDraw.Draw(image)
    annotations: list[RenderedAnnotation] = []

    for field in template.fields:
        text = values[field.name]
        requested = field.bbox.clipped(*image.size)
        if _is_checkbox_field(field):
            checked = _checkbox_checked(text)
            if field.checkbox_style == "symbol_box" or checked:
                if field.clear_background:
                    fill = field.background_color or sample_background(image, requested, padding=field.background_padding)
                    draw.rectangle([requested.x, requested.y, requested.right, requested.bottom], fill=fill)
                actual = _draw_checkbox(draw, requested, checked, field)
            else:
                actual = BBox(requested.x, requested.y, 1, 1)
            if field.include_gt:
                annotations.append(
                    RenderedAnnotation(
                        field=field.name,
                        text="V" if checked else "",
                        bbox=actual,
                        requested_bbox=requested,
                    )
                )
            continue
        if text is None or not str(text).strip():
            continue
        if field.clear_background:
            fill = field.background_color or sample_background(image, requested, padding=field.background_padding)
            draw.rectangle([requested.x, requested.y, requested.right, requested.bottom], fill=fill)

        font = _fit_font(draw, text, field, template.font_path, requested)
        lines = _wrap_lines(draw, text, font, field, requested) if field.overflow == "wrap" else [text]
        text_bbox = _multiline_text_bbox(draw, lines, font, field)
        x = _aligned_x(requested, text_bbox.width, field.align) + field.x_shift
        y = _aligned_y(requested, text_bbox.height, field.valign) + field.baseline_shift
        draw_target = draw
        target_image = image
        if field.opacity < 0.999 or field.overflow == "clip":
            layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw_target = ImageDraw.Draw(layer)
            target_image = layer
        fill = field.color if field.opacity >= 0.999 else (*field.color, max(0, min(255, int(round(255 * field.opacity)))))
        _draw_multiline_text(draw_target, x, y, lines, font, fill, field)
        if target_image is not image:
            if field.overflow == "clip":
                mask = Image.new("L", image.size, 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rectangle([requested.x, requested.y, requested.right, requested.bottom], fill=255)
                alpha = target_image.getchannel("A") if target_image.mode == "RGBA" else mask
                target_image.putalpha(ImageChops.multiply(alpha, mask))
            image = Image.alpha_composite(image.convert("RGBA"), target_image).convert("RGB")
            draw = ImageDraw.Draw(image)
        actual = _actual_multiline_bbox(draw, lines, font, x, y, field).clipped(*image.size)
        if field.include_gt:
            annotations.append(
                RenderedAnnotation(
                    field=field.name,
                    text=text,
                    bbox=actual,
                    requested_bbox=requested,
                )
            )
    return image, annotations


def _scale_field(field: FieldSpec, scale: int) -> FieldSpec:
    return replace(
        field,
        bbox=_scale_bbox(field.bbox, scale),
        font_size=max(1, int(round(field.font_size * scale))),
        letter_spacing=float(field.letter_spacing) * scale,
        baseline_shift=int(round(field.baseline_shift * scale)),
        x_shift=int(round(field.x_shift * scale)),
        background_padding=max(0, int(round(field.background_padding * scale))),
    )


def _is_checkbox_field(field: FieldSpec) -> bool:
    return str(field.type).lower().replace("_", ".").replace("-", ".") in {"bool.checkbox", "checkbox", "checkbox.bool", "boolean"}


def _checkbox_checked(value: str | None) -> bool:
    normalized = str(value or "").replace("\ufe0f", "").strip().lower()
    return normalized in {"v", "true", "1", "yes", "y", "✓", "✔", "☑", "■", "●", "selected", "checked", "on"}


def _draw_checkbox(draw: ImageDraw.ImageDraw, bbox: BBox, checked: bool, field: FieldSpec) -> BBox:
    style = field.checkbox_style or "v_mark"
    fill = field.color
    if style == "v_mark":
        if not checked:
            return BBox(bbox.x, bbox.y, 1, 1)
        font = load_font(max(6, int(field.font_size)), field.font_path, field.font_index)
        text = "V"
        text_bbox = _text_bbox(draw, text, font, field.letter_spacing)
        x = _aligned_x(bbox, text_bbox.width, field.align) + field.x_shift
        y = _aligned_y(bbox, text_bbox.height, field.valign) + field.baseline_shift
        _draw_text(draw, x, y, text, font, fill, field.letter_spacing)
        return _actual_bbox(draw, text, font, x, y, field.letter_spacing).clipped(bbox.right + 1, bbox.bottom + 1)

    square = _checkbox_square_bbox(BBox(bbox.x + field.x_shift, bbox.y, bbox.width, bbox.height))
    stroke = max(1, int(round(min(square.width, square.height) * 0.075)))
    if style in {"check_mark", "heavy_check_mark"}:
        if checked:
            return _draw_standalone_vector_check(draw, square, fill, stroke, weight=1.0 if style == "check_mark" else 1.55)
        return BBox(bbox.x, bbox.y, 1, 1)
    if style == "symbol_box":
        draw.rectangle([square.x, square.y, square.right, square.bottom], outline=fill, width=stroke)
        if checked:
            _draw_vector_check(draw, square, fill, stroke)
        return square
    if style == "filled_box":
        if checked:
            margin = max(1, int(round(min(square.width, square.height) * 0.22)))
            draw.rectangle([square.x + margin, square.y + margin, square.right - margin, square.bottom - margin], fill=fill)
            return BBox(square.x + margin, square.y + margin, max(1, square.width - margin * 2), max(1, square.height - margin * 2))
        return BBox(bbox.x, bbox.y, 1, 1)
    if style == "dot":
        if checked:
            margin = max(1, int(round(min(square.width, square.height) * 0.26)))
            draw.ellipse([square.x + margin, square.y + margin, square.right - margin, square.bottom - margin], fill=fill)
            return BBox(square.x + margin, square.y + margin, max(1, square.width - margin * 2), max(1, square.height - margin * 2))
        return BBox(bbox.x, bbox.y, 1, 1)
    return BBox(bbox.x, bbox.y, 1, 1)


def _checkbox_square_bbox(bbox: BBox) -> BBox:
    size = max(2, int(round(min(bbox.width, bbox.height) * 0.82)))
    x = bbox.x + max(0, (bbox.width - size) // 2)
    y = bbox.y + max(0, (bbox.height - size) // 2)
    return BBox(x, y, size, size)


def _draw_vector_check(draw: ImageDraw.ImageDraw, bbox: BBox, fill: tuple[int, int, int], stroke: int) -> None:
    s = min(bbox.width, bbox.height)
    points = [
        (bbox.x + int(round(s * 0.22)), bbox.y + int(round(s * 0.55))),
        (bbox.x + int(round(s * 0.42)), bbox.y + int(round(s * 0.74))),
        (bbox.x + int(round(s * 0.78)), bbox.y + int(round(s * 0.27))),
    ]
    draw.line(points, fill=fill, width=max(stroke, int(round(s * 0.11))), joint="curve")


def _draw_standalone_vector_check(
    draw: ImageDraw.ImageDraw,
    bbox: BBox,
    fill: tuple[int, int, int],
    stroke: int,
    *,
    weight: float,
) -> BBox:
    s = min(bbox.width, bbox.height)
    points = [
        (bbox.x + int(round(s * 0.12)), bbox.y + int(round(s * 0.57))),
        (bbox.x + int(round(s * 0.38)), bbox.y + int(round(s * 0.80))),
        (bbox.x + int(round(s * 0.88)), bbox.y + int(round(s * 0.20))),
    ]
    width = max(stroke, int(round(s * 0.13 * weight)))
    draw.line(points, fill=fill, width=width, joint="curve")
    min_x = min(point[0] for point in points) - width // 2
    min_y = min(point[1] for point in points) - width // 2
    max_x = max(point[0] for point in points) + width // 2
    max_y = max(point[1] for point in points) + width // 2
    return BBox(min_x, min_y, max(1, max_x - min_x), max(1, max_y - min_y))


def _scale_bbox(bbox: BBox, scale: int) -> BBox:
    return BBox(
        x=int(round(bbox.x * scale)),
        y=int(round(bbox.y * scale)),
        width=max(1, int(round(bbox.width * scale))),
        height=max(1, int(round(bbox.height * scale))),
    )


def _unscale_annotation(annotation: RenderedAnnotation, scale: int, image_size: tuple[int, int]) -> RenderedAnnotation:
    return RenderedAnnotation(
        field=annotation.field,
        text=annotation.text,
        bbox=_unscale_bbox(annotation.bbox, scale).clipped(*image_size),
        requested_bbox=_unscale_bbox(annotation.requested_bbox, scale).clipped(*image_size),
        bbox_format=annotation.bbox_format,
    )


def _unscale_bbox(bbox: BBox, scale: int) -> BBox:
    left = bbox.x / scale
    top = bbox.y / scale
    right = bbox.right / scale
    bottom = bbox.bottom / scale
    return BBox(
        x=int(round(left)),
        y=int(round(top)),
        width=max(1, int(round(right - left))),
        height=max(1, int(round(bottom - top))),
    )


def _resampling_lanczos() -> int:
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def sample_background(image: Image.Image, bbox: BBox, padding: int = 2) -> tuple[int, int, int]:
    """Estimate a fill color from pixels just outside a field bbox."""

    width, height = image.size
    outer = bbox.padded(max(1, padding + 2)).clipped(width, height)
    inner = bbox.clipped(width, height)
    pixels: list[tuple[int, int, int]] = []
    data = image.load()

    for x in range(outer.x, outer.right):
        for y in (outer.y, outer.bottom - 1):
            if 0 <= x < width and 0 <= y < height and not _inside(x, y, inner):
                pixels.append(data[x, y])
    for y in range(outer.y, outer.bottom):
        for x in (outer.x, outer.right - 1):
            if 0 <= x < width and 0 <= y < height and not _inside(x, y, inner):
                pixels.append(data[x, y])

    if not pixels:
        return (255, 255, 255)
    return tuple(int(median(channel)) for channel in zip(*pixels))  # type: ignore[return-value]


def _fit_font(draw: ImageDraw.ImageDraw, text: str, field: FieldSpec, template_font_path: str | None, bbox: BBox) -> ImageFont.ImageFont:
    font_path = field.font_path or template_font_path
    size = max(6, int(field.font_size))
    font = load_font(size, font_path, field.font_index)
    if field.overflow != "shrink":
        return font

    while size > 6:
        tb = _text_bbox(draw, text, font, field.letter_spacing, stroke_width=_font_stroke_width(field, font))
        if tb.width <= bbox.width and tb.height <= bbox.height:
            return font
        size -= 1
        font = load_font(size, font_path, field.font_index)
    return font


def _text_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, letter_spacing: float = 0.0, *, stroke_width: int = 0) -> BBox:
    if abs(letter_spacing) < 0.01:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font, stroke_width=max(0, int(stroke_width)))
        return BBox(left, top, max(1, right - left), max(1, bottom - top))

    cursor = 0.0
    min_left = 0.0
    min_top = 0.0
    max_right = 0.0
    max_bottom = 1.0
    seen = False
    for char in text:
        left, top, right, bottom = draw.textbbox((int(round(cursor)), 0), char, font=font, stroke_width=max(0, int(stroke_width)))
        if not seen:
            min_left, min_top, max_right, max_bottom = left, top, right, bottom
            seen = True
        else:
            min_left = min(min_left, left)
            min_top = min(min_top, top)
            max_right = max(max_right, right)
            max_bottom = max(max_bottom, bottom)
        cursor += float(draw.textlength(char, font=font)) + letter_spacing
    if not seen:
        return BBox(0, 0, 1, 1)
    return BBox(floor(min_left), floor(min_top), max(1, ceil(max_right - min_left)), max(1, ceil(max_bottom - min_top)))


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, field: FieldSpec, bbox: BBox) -> list[str]:
    tokens = _wrap_tokens(text)
    if not tokens:
        return [text]
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = token if not current else current + token
        if current and _text_bbox(draw, candidate, font, field.letter_spacing, stroke_width=_font_stroke_width(field, font)).width > bbox.width:
            lines.append(current.rstrip())
            current = token.lstrip()
        else:
            current = candidate
    if current.strip():
        lines.append(current.rstrip())
    if not lines:
        lines = [text]
    return lines


def _wrap_tokens(text: str) -> list[str]:
    # Keep Korean phrases readable: prefer existing spaces/newlines, but split very long
    # unspaced strings by character so form fields can still wrap inside a bbox.
    output: list[str] = []
    for para_index, paragraph in enumerate(str(text).splitlines()):
        if para_index:
            output.append("\n")
        if " " in paragraph:
            parts = paragraph.split(" ")
            for index, part in enumerate(parts):
                if index:
                    output.append(" ")
                output.append(part)
        else:
            output.extend(list(paragraph))
    return output


def _multiline_text_bbox(draw: ImageDraw.ImageDraw, lines: list[str], font: ImageFont.ImageFont, field: FieldSpec) -> BBox:
    stroke_width = _font_stroke_width(field, font)
    boxes = [_text_bbox(draw, line or " ", font, field.letter_spacing, stroke_width=stroke_width) for line in lines]
    width = max((box.width for box in boxes), default=1)
    line_height = max((box.height for box in boxes), default=1)
    height = _multiline_height(line_height, len(lines), field.line_spacing)
    return BBox(0, 0, max(1, width), max(1, height))


def _draw_multiline_text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    lines: list[str],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
    field: FieldSpec,
) -> None:
    stroke_width = _font_stroke_width(field, font)
    line_height = max(_text_bbox(draw, line or " ", font, field.letter_spacing, stroke_width=stroke_width).height for line in lines)
    step = max(1, int(round(line_height * field.line_spacing)))
    block = _multiline_text_bbox(draw, lines, font, field)
    for idx, line in enumerate(lines):
        line_box = _text_bbox(draw, line or " ", font, field.letter_spacing, stroke_width=stroke_width)
        line_x = x
        if field.align == "right":
            line_x = x + max(0, block.width - line_box.width)
        elif field.align == "center":
            line_x = x + max(0, (block.width - line_box.width) // 2)
        _draw_text(draw, line_x, y + idx * step, line, font, fill, field.letter_spacing, stroke_width=stroke_width)


def _actual_multiline_bbox(draw: ImageDraw.ImageDraw, lines: list[str], font: ImageFont.ImageFont, x: int, y: int, field: FieldSpec) -> BBox:
    if not lines:
        return BBox(x, y, 1, 1)
    stroke_width = _font_stroke_width(field, font)
    line_height = max(_text_bbox(draw, line or " ", font, field.letter_spacing, stroke_width=stroke_width).height for line in lines)
    step = max(1, int(round(line_height * field.line_spacing)))
    boxes=[]
    block = _multiline_text_bbox(draw, lines, font, field)
    for idx, line in enumerate(lines):
        line_box = _text_bbox(draw, line or " ", font, field.letter_spacing, stroke_width=stroke_width)
        line_x = x
        if field.align == "right":
            line_x = x + max(0, block.width - line_box.width)
        elif field.align == "center":
            line_x = x + max(0, (block.width - line_box.width) // 2)
        boxes.append(_actual_bbox(draw, line, font, line_x, y + idx * step, field.letter_spacing, stroke_width=stroke_width))
    left = min(box.x for box in boxes)
    top = min(box.y for box in boxes)
    right = max(box.right for box in boxes)
    bottom = max(box.bottom for box in boxes)
    return BBox(left, top, max(1, right - left), max(1, bottom - top))


def _multiline_height(line_height: int, line_count: int, line_spacing: float) -> int:
    if line_count <= 1:
        return line_height
    return int(round(line_height + (line_count - 1) * max(1, line_height * line_spacing)))


def _draw_text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
    letter_spacing: float = 0.0,
    stroke_width: int = 0,
) -> None:
    stroke_width = max(0, int(stroke_width))
    if abs(letter_spacing) < 0.01:
        draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=fill)
        return
    cursor = float(x)
    for char in text:
        draw.text((int(round(cursor)), y), char, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=fill)
        cursor += float(draw.textlength(char, font=font)) + letter_spacing


def _actual_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, x: int, y: int, letter_spacing: float = 0.0, *, stroke_width: int = 0) -> BBox:
    if abs(letter_spacing) >= 0.01:
        measured = _text_bbox(draw, text, font, letter_spacing, stroke_width=stroke_width)
        return BBox(x + measured.x, y + measured.y, measured.width, measured.height)
    left, top, right, bottom = draw.textbbox((x, y), text, font=font, stroke_width=max(0, int(stroke_width)))
    return BBox(left, top, max(1, right - left), max(1, bottom - top))


def _font_stroke_width(field: FieldSpec, font: ImageFont.ImageFont | None = None) -> int:
    weight = str(getattr(field, "font_weight", "normal") or "normal").lower()
    if font is not None and _font_already_has_requested_weight(font, weight):
        return 0
    if weight == "black":
        return max(1, int(round(field.font_size * 0.045)))
    if weight == "bold":
        return max(1, int(round(field.font_size * 0.028)))
    return 0


def _font_already_has_requested_weight(font: ImageFont.ImageFont, requested_weight: str) -> bool:
    if requested_weight not in {"bold", "black"}:
        return True
    try:
        _family, style = font.getname()  # type: ignore[attr-defined]
    except Exception:
        return False
    normalized = str(style or "").lower().replace(" ", "")
    if requested_weight == "black":
        return any(token in normalized for token in ("black", "heavy", "extrabold", "ultrabold"))
    return any(token in normalized for token in ("bold", "semibold", "demibold", "black", "heavy"))


def _aligned_x(bbox: BBox, text_width: int, align: str) -> int:
    if align == "right":
        return bbox.right - text_width
    if align == "center":
        return int(round((bbox.x + bbox.width / 2) - (text_width / 2)))
    return bbox.x


def _aligned_y(bbox: BBox, text_height: int, valign: str) -> int:
    if valign == "bottom":
        return bbox.bottom - text_height
    if valign == "top":
        return bbox.y
    return bbox.y + max(0, (bbox.height - text_height) // 2)


def _inside(x: int, y: int, bbox: BBox) -> bool:
    return bbox.x <= x < bbox.right and bbox.y <= y < bbox.bottom
