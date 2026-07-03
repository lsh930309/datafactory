from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


@dataclass(frozen=True)
class ManualMaskPaths:
    directory: Path
    mask_json: Path
    manual_mask: Path

    def as_dict(self) -> dict[str, Path]:
        return {"mask_json": self.mask_json, "manual_mask": self.manual_mask}


def empty_manual_mask_payload(width: int, height: int) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "image": {"width": int(width), "height": int(height)},
        "strokes": [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def normalize_manual_mask_payload(payload: dict[str, Any] | None, *, width: int, height: int) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    strokes: list[dict[str, Any]] = []
    for index, stroke in enumerate(raw.get("strokes") or []):
        if not isinstance(stroke, dict):
            continue
        points = _normalize_points(stroke.get("points"), width=width, height=height)
        if len(points) < 3:
            continue
        stroke_id = str(stroke.get("id") or f"mask_{index + 1:04d}")
        strokes.append(
            {
                "id": stroke_id,
                "type": str(stroke.get("type") or "lasso"),
                "operation": "add",
                "points": points,
            }
        )
    return {
        "schema_version": 1,
        "image": {"width": int(width), "height": int(height)},
        "strokes": strokes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def rasterize_manual_mask(payload: dict[str, Any] | None, *, size: tuple[int, int]) -> Image.Image:
    width, height = int(size[0]), int(size[1])
    normalized = normalize_manual_mask_payload(payload, width=width, height=height)
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for stroke in normalized["strokes"]:
        points = [(int(round(point["x"])), int(round(point["y"]))) for point in stroke["points"]]
        if len(points) >= 3:
            draw.polygon(points, fill=255)
    return mask


def save_manual_mask(payload: dict[str, Any] | None, *, directory: Path, size: tuple[int, int]) -> tuple[dict[str, Any], ManualMaskPaths]:
    width, height = int(size[0]), int(size[1])
    directory.mkdir(parents=True, exist_ok=True)
    normalized = normalize_manual_mask_payload(payload, width=width, height=height)
    mask = rasterize_manual_mask(normalized, size=(width, height))
    paths = ManualMaskPaths(directory=directory, mask_json=directory / "mask.json", manual_mask=directory / "manual_mask.png")
    paths.mask_json.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mask.save(paths.manual_mask)
    return normalized, paths


def load_manual_mask(directory: Path, *, size: tuple[int, int]) -> dict[str, Any]:
    path = directory / "mask.json"
    if not path.exists():
        return empty_manual_mask_payload(size[0], size[1])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return empty_manual_mask_payload(size[0], size[1])
    return normalize_manual_mask_payload(payload if isinstance(payload, dict) else {}, width=size[0], height=size[1])


def combine_masks(*masks: Image.Image) -> Image.Image:
    if not masks:
        raise ValueError("at least one mask is required")
    base_size = masks[0].size
    arrays = []
    for mask in masks:
        if mask.size != base_size:
            raise ValueError(f"mask size mismatch: {mask.size} != {base_size}")
        arrays.append(np.asarray(mask.convert("L"), dtype=np.uint8))
    combined = np.maximum.reduce(arrays)
    combined = np.where(combined > 0, 255, 0).astype(np.uint8)
    return Image.fromarray(combined, mode="L")


def _normalize_points(raw_points: Any, *, width: int, height: int) -> list[dict[str, int]]:
    points: list[dict[str, int]] = []
    if not isinstance(raw_points, list):
        return points
    for raw in raw_points:
        if isinstance(raw, dict):
            x_value = raw.get("x")
            y_value = raw.get("y")
        elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
            x_value, y_value = raw[0], raw[1]
        else:
            continue
        try:
            x = int(round(float(x_value)))
            y = int(round(float(y_value)))
        except (TypeError, ValueError):
            continue
        points.append({"x": max(0, min(width - 1, x)), "y": max(0, min(height - 1, y))})
    return points
