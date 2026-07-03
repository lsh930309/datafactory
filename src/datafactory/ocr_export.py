from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from .ocr_models import OcrResult
from .ocr_visualize import render_ocr_overlay


def write_ocr_eval(result: OcrResult, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    detections_path = output_dir / "detections.json"
    raw_path = output_dir / "raw.json"
    overlay_path = output_dir / "overlay.png"
    summary_path = output_dir / "summary.json"

    with detections_path.open("w", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    with raw_path.open("w", encoding="utf-8") as handle:
        json.dump(_json_safe(result.raw), handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    image = Image.open(result.source_image).convert("RGB")
    render_ocr_overlay(image, result).save(overlay_path)

    summary = {
        "engine": result.engine,
        "source_image": str(result.source_image),
        "image": {"width": result.image_width, "height": result.image_height},
        "detection_count": len(result.detections),
        "avg_confidence": _avg([d.confidence for d in result.detections if d.confidence is not None]),
        "avg_bbox_area": _avg([d.bbox.width * d.bbox.height for d in result.detections]),
        "detections": str(detections_path),
        "raw": str(raw_path),
        "overlay": str(overlay_path),
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return {"detections": detections_path, "raw": raw_path, "overlay": overlay_path, "summary": summary_path}


def _avg(values: list[float | int]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    return repr(value)
