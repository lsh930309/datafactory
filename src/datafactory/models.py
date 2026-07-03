from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

BBoxFormat = Literal["xywh"]
Align = Literal["left", "center", "right"]
Valign = Literal["top", "middle", "bottom"]
Overflow = Literal["shrink", "clip", "allow", "wrap"]
CheckboxStyle = Literal["v_mark", "check_mark", "heavy_check_mark", "symbol_box", "filled_box", "dot"]


@dataclass(frozen=True)
class BBox:
    """Axis-aligned rectangle in pixel xywh coordinates."""

    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_list(cls, value: list[int | float]) -> "BBox":
        if len(value) != 4:
            raise ValueError(f"bbox must have 4 values, got {len(value)}")
        x, y, width, height = (int(round(v)) for v in value)
        if width <= 0 or height <= 0:
            raise ValueError(f"bbox width/height must be positive, got {value}")
        return cls(x=x, y=y, width=width, height=height)

    def to_list(self) -> list[int]:
        return [self.x, self.y, self.width, self.height]

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def padded(self, pixels: int) -> "BBox":
        return BBox(
            x=self.x - pixels,
            y=self.y - pixels,
            width=self.width + pixels * 2,
            height=self.height + pixels * 2,
        )

    def clipped(self, image_width: int, image_height: int) -> "BBox":
        x1 = max(0, min(self.x, image_width))
        y1 = max(0, min(self.y, image_height))
        x2 = max(x1, min(self.right, image_width))
        y2 = max(y1, min(self.bottom, image_height))
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        return BBox(x1, y1, width, height)


@dataclass
class FieldSpec:
    name: str
    bbox: BBox
    type: str = "text"
    font_size: int = 28
    color: tuple[int, int, int] = (30, 30, 30)
    opacity: float = 1.0
    letter_spacing: float = 0.0
    line_spacing: float = 1.0
    baseline_shift: int = 0
    x_shift: int = 0
    align: Align = "left"
    valign: Valign = "middle"
    overflow: Overflow = "shrink"
    checkbox_style: CheckboxStyle = "v_mark"
    clear_background: bool = True
    background_color: tuple[int, int, int] | None = None
    background_padding: int = 2
    include_gt: bool = True
    value: str | None = None
    choices: list[str] = field(default_factory=list)
    format: str | None = None
    font_path: str | None = None
    font_index: int = 0
    font_weight: str = "normal"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "FieldSpec":
        if "name" not in raw or "bbox" not in raw:
            raise ValueError("field spec requires name and bbox")
        color = raw.get("color", [30, 30, 30])
        background_color = raw.get("background_color")
        return cls(
            name=str(raw["name"]),
            bbox=BBox.from_list(raw["bbox"]),
            type=str(raw.get("type", "text")),
            font_size=int(raw.get("font_size", 28)),
            color=_rgb_tuple(color, "color"),
            opacity=max(0.0, min(1.0, float(raw.get("opacity", 1.0)))),
            letter_spacing=float(raw.get("letter_spacing", 0.0)),
            line_spacing=max(0.1, float(raw.get("line_spacing", 1.0))),
            baseline_shift=int(round(float(raw.get("baseline_shift", 0)))),
            x_shift=int(round(float(raw.get("x_shift", 0)))),
            align=raw.get("align", "left"),
            valign=raw.get("valign", "middle"),
            overflow=raw.get("overflow", "shrink"),
            checkbox_style=_checkbox_style(raw.get("checkbox_style")),
            clear_background=bool(raw.get("clear_background", True)),
            background_color=_rgb_tuple(background_color, "background_color") if background_color is not None else None,
            background_padding=int(raw.get("background_padding", 2)),
            include_gt=bool(raw.get("include_gt", True)),
            value=str(raw["value"]) if raw.get("value") is not None else None,
            choices=[str(v) for v in raw.get("choices", [])],
            format=str(raw["format"]) if raw.get("format") is not None else None,
            font_path=str(raw["font_path"]) if raw.get("font_path") is not None else None,
            font_index=max(0, int(raw.get("font_index", 0) or 0)),
            font_weight=str(raw.get("font_weight") or "normal"),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "bbox": self.bbox.to_list(),
            "type": self.type,
            "font_size": self.font_size,
            "color": list(self.color),
            "opacity": self.opacity,
            "letter_spacing": self.letter_spacing,
            "line_spacing": self.line_spacing,
            "baseline_shift": self.baseline_shift,
            "x_shift": self.x_shift,
            "align": self.align,
            "valign": self.valign,
            "overflow": self.overflow,
            "checkbox_style": self.checkbox_style,
            "clear_background": self.clear_background,
            "background_padding": self.background_padding,
            "include_gt": self.include_gt,
        }
        if self.background_color is not None:
            data["background_color"] = list(self.background_color)
        if self.value is not None:
            data["value"] = self.value
        if self.choices:
            data["choices"] = self.choices
        if self.format is not None:
            data["format"] = self.format
        if self.font_path is not None:
            data["font_path"] = self.font_path
        if self.font_index:
            data["font_index"] = self.font_index
        if self.font_weight != "normal":
            data["font_weight"] = self.font_weight
        return data


@dataclass
class TemplateSpec:
    template_id: str
    image_path: Path
    fields: list[FieldSpec]
    font_path: str | None = None
    description: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any], base_dir: Path | None = None) -> "TemplateSpec":
        if "template_id" not in raw or "image_path" not in raw:
            raise ValueError("template requires template_id and image_path")
        base = base_dir or Path.cwd()
        image_path = Path(raw["image_path"])
        if not image_path.is_absolute():
            image_path = (base / image_path).resolve()
        fields = [FieldSpec.from_dict(item) for item in raw.get("fields", [])]
        if not fields:
            raise ValueError("template must define at least one field")
        return cls(
            template_id=str(raw["template_id"]),
            image_path=image_path,
            fields=fields,
            font_path=str(raw["font_path"]) if raw.get("font_path") else None,
            description=str(raw["description"]) if raw.get("description") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "template_id": self.template_id,
            "image_path": str(self.image_path),
            "fields": [field.to_dict() for field in self.fields],
        }
        if self.font_path:
            data["font_path"] = self.font_path
        if self.description:
            data["description"] = self.description
        return data


@dataclass(frozen=True)
class RenderJob:
    template: TemplateSpec
    output_dir: Path
    count: int = 1
    seed: int = 1234
    image_ext: str = "png"


@dataclass(frozen=True)
class RenderedAnnotation:
    field: str
    text: str
    bbox: BBox
    requested_bbox: BBox
    bbox_format: BBoxFormat = "xywh"

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "text": self.text,
            "bbox": self.bbox.to_list(),
            "requested_bbox": self.requested_bbox.to_list(),
            "bbox_format": self.bbox_format,
        }


@dataclass(frozen=True)
class SyntheticSample:
    sample_id: str
    image_path: Path
    kv_path: Path
    bbox_path: Path
    annotations: list[RenderedAnnotation]
    fields: dict[str, str]


def _rgb_tuple(value: Any, name: str) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{name} must be an RGB triplet")
    rgb = tuple(int(v) for v in value)
    if any(v < 0 or v > 255 for v in rgb):
        raise ValueError(f"{name} values must be 0..255")
    return rgb  # type: ignore[return-value]


def _checkbox_style(value: Any) -> CheckboxStyle:
    text = str(value or "v_mark")
    if text in {"v_mark", "check_mark", "heavy_check_mark", "symbol_box", "filled_box", "dot"}:
        return text  # type: ignore[return-value]
    return "v_mark"
