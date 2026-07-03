from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from datafactory.ocr_detectors import ProjectionTextDetector
from datafactory.ocr_export import write_ocr_eval
from datafactory.ocr_models import bbox_to_polygon, polygon_to_bbox


def test_polygon_bbox_roundtrip() -> None:
    bbox = polygon_to_bbox([[10, 20], [40, 18], [42, 50], [8, 49]])
    assert bbox.to_list() == [8, 18, 34, 32]
    assert bbox_to_polygon(bbox) == [[8, 18], [42, 18], [42, 50], [8, 50]]


def test_projection_detector_and_export(tmp_path: Path) -> None:
    image_path = tmp_path / "ocr_seed.png"
    image = Image.new("RGB", (320, 180), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([40, 50, 180, 80], fill=(0, 0, 0))
    image.save(image_path)

    result = ProjectionTextDetector().detect(image_path)
    assert result.engine == "projection"
    assert result.detections

    paths = write_ocr_eval(result, tmp_path / "eval")
    assert paths["detections"].exists()
    assert paths["raw"].exists()
    assert paths["overlay"].exists()
    assert paths["summary"].exists()

    detections = json.loads(paths["detections"].read_text(encoding="utf-8"))
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert detections["engine"] == "projection"
    assert summary["detection_count"] == len(result.detections)
