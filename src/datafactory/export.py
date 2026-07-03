from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from .models import RenderedAnnotation, SyntheticSample, TemplateSpec
from .visualize import render_bbox_overlay


def prepare_output_dirs(output_dir: Path) -> dict[str, Path]:
    dirs = {
        "root": output_dir,
        "images": output_dir / "images",
        "kv": output_dir / "kv",
        "bbox": output_dir / "bbox",
        "visualizations": output_dir / "visualizations",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def write_sample(
    *,
    output_dir: Path,
    sample_id: str,
    template: TemplateSpec,
    image: Image.Image,
    fields: dict[str, str],
    annotations: list[RenderedAnnotation],
    image_ext: str = "png",
) -> SyntheticSample:
    dirs = prepare_output_dirs(output_dir)
    image_path = dirs["images"] / f"{sample_id}.{image_ext}"
    kv_path = dirs["kv"] / f"{sample_id}.json"
    bbox_path = dirs["bbox"] / f"{sample_id}.json"
    bbox_image_path = dirs["visualizations"] / f"{sample_id}_bbox.png"

    image.save(image_path)
    render_bbox_overlay(image, annotations).save(bbox_image_path)
    kv_payload = {
        "sample_id": sample_id,
        "template_id": template.template_id,
        "fields": fields,
    }
    bbox_payload = {
        "sample_id": sample_id,
        "template_id": template.template_id,
        "source_image": str(template.image_path),
        "image": {
            "path": str(image_path),
            "bbox_overlay_path": str(bbox_image_path),
            "width": image.width,
            "height": image.height,
        },
        "annotations": [annotation.to_dict() for annotation in annotations],
    }
    _write_json(kv_path, kv_payload)
    _write_json(bbox_path, bbox_payload)
    _append_manifest(
        dirs["root"] / "manifest.jsonl",
        {
            "sample_id": sample_id,
            "template_id": template.template_id,
            "image": str(image_path),
            "kv": str(kv_path),
            "bbox": str(bbox_path),
            "bbox_image": str(bbox_image_path),
        },
    )
    return SyntheticSample(
        sample_id=sample_id,
        image_path=image_path,
        kv_path=kv_path,
        bbox_path=bbox_path,
        annotations=annotations,
        fields=fields,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _append_manifest(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")
