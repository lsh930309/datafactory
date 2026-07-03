from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .models import BBox

DetectionLevel = Literal["word", "line", "block", "unknown"]


@dataclass(frozen=True)
class OcrDetection:
    id: str
    text: str
    confidence: float | None
    bbox: BBox
    polygon: list[list[int]]
    level: DetectionLevel = "word"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "confidence": self.confidence,
            "bbox": self.bbox.to_list(),
            "bbox_format": "xywh",
            "polygon": self.polygon,
            "level": self.level,
        }


@dataclass(frozen=True)
class OcrResult:
    engine: str
    source_image: Path
    image_width: int
    image_height: int
    detections: list[OcrDetection]
    raw: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "source_image": str(self.source_image),
            "image": {"width": self.image_width, "height": self.image_height},
            "detections": [detection.to_dict() for detection in self.detections],
        }


def polygon_to_bbox(polygon: list[list[int | float]]) -> BBox:
    if not polygon:
        raise ValueError("polygon is empty")
    xs = [int(round(point[0])) for point in polygon]
    ys = [int(round(point[1])) for point in polygon]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    return BBox(x=x1, y=y1, width=max(1, x2 - x1), height=max(1, y2 - y1))


def bbox_to_polygon(bbox: BBox) -> list[list[int]]:
    return [[bbox.x, bbox.y], [bbox.right, bbox.y], [bbox.right, bbox.bottom], [bbox.x, bbox.bottom]]
