from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from datafactory.inpaint import InpaintConfig, inpaint_from_review_policy
from datafactory.policy import augment_blank_template_policy, draft_review_policy, load_review_policy, policy_from_edited_rows, review_rows, write_review_policy


def _detection(id_: str, text: str, bbox: list[int], confidence: float = 0.95) -> dict[str, object]:
    x, y, w, h = bbox
    return {
        "id": id_,
        "text": text,
        "confidence": confidence,
        "bbox": bbox,
        "bbox_format": "xywh",
        "polygon": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
        "level": "word",
    }


def test_draft_review_policy_prelabels_and_roundtrips(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    image = Image.new("RGB", (260, 180), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), "성명", fill=(0, 0, 0))
    draw.text((90, 20), "2026.06.26", fill=(0, 0, 0))
    draw.rectangle([180, 120, 230, 160], outline=(220, 0, 0), width=5)
    image.save(image_path)

    detections_path = tmp_path / "detections.json"
    detections_path.write_text(
        json.dumps(
            {
                "engine": "test",
                "source_image": str(image_path),
                "image": {"width": 260, "height": 180},
                "detections": [
                    _detection("det_label", "성명", [20, 20, 40, 18]),
                    _detection("det_value", "2026.06.26", [90, 20, 80, 18]),
                    _detection("det_stamp", "인", [180, 120, 50, 40]),
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    policy = draft_review_policy(detections_path)
    by_id = {label.id: label for label in policy.labels}
    assert by_id["det_label"].status == "keep"
    assert by_id["det_label"].auto_type == "static_label"
    assert by_id["det_value"].status == "use"
    assert by_id["det_value"].auto_type == "field_value"
    assert by_id["det_stamp"].status == "ignore"
    assert by_id["det_stamp"].auto_type == "stamp_or_seal"

    paths = write_review_policy(policy, tmp_path / "review")
    assert paths["review"].exists()
    assert paths["overlay"].exists()
    loaded = load_review_policy(paths["review"])
    assert len(loaded.labels) == 3


def test_blank_template_augmentation_adds_visual_value_region_candidates(tmp_path: Path) -> None:
    image_path = tmp_path / "blank_grid.png"
    image = Image.new("RGB", (220, 140), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for x in (20, 90, 160, 210):
        draw.line([(x, 20), (x, 120)], fill=(0, 0, 0), width=2)
    for y in (20, 55, 90, 120):
        draw.line([(20, y), (210, y)], fill=(0, 0, 0), width=2)
    draw.text((28, 30), "항목", fill=(0, 0, 0))
    image.save(image_path)
    detections_path = tmp_path / "detections.json"
    detections_path.write_text(
        json.dumps(
            {
                "engine": "test",
                "source_image": str(image_path),
                "image": {"width": 220, "height": 140},
                "detections": [_detection("det_label", "항목", [28, 30, 28, 14])],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    policy = draft_review_policy(detections_path)
    augmented, summary = augment_blank_template_policy(policy)

    visual = [label for label in augmented.labels if label.text_source == "visual_line_detect"]
    assert summary["candidateCount"] == len(visual)
    assert visual
    assert all(label.status == "keep" for label in visual)
    assert all(label.auto_type == "table_cell" for label in visual)


def test_review_policy_roundtrips_manual_edited_bbox(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    Image.new("RGB", (260, 180), (255, 255, 255)).save(image_path)
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": "2026-06-29T00:00:00+00:00",
                "source_engine": "manual",
                "source_detections": str(tmp_path / "detections.json"),
                "source_image": str(image_path),
                "image": {"width": 260, "height": 180},
                "labels": [
                    {
                        "id": "manual_1",
                        "text": "",
                        "confidence": None,
                        "bbox": [30, 40, 80, 20],
                        "bbox_format": "xywh",
                        "polygon": [[30, 40], [110, 40], [110, 60], [30, 60]],
                        "status": "use",
                        "auto_type": "field_value",
                        "reason": "manual bbox",
                        "original_text": "초기값",
                        "original_confidence": 0.91,
                        "text_source": "manual_bbox",
                        "ocr_text_stale": True,
                        "rec_text": "재인식값",
                        "rec_confidence": 0.88,
                        "rec_engine": "paddleocr",
                        "rec_updated_at": "2026-06-30T00:00:00+00:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = load_review_policy(review_path)
    assert loaded.labels[0].id == "manual_1"
    assert loaded.labels[0].bbox.to_list() == [30, 40, 80, 20]
    assert loaded.labels[0].status == "use"
    assert loaded.labels[0].ocr_text_stale is True
    assert loaded.labels[0].rec_text == "재인식값"

    paths = write_review_policy(loaded, tmp_path / "review")
    payload = json.loads(paths["review"].read_text(encoding="utf-8"))
    assert payload["labels"][0]["polygon"] == [[30, 40], [110, 40], [110, 60], [30, 60]]
    assert payload["labels"][0]["text_source"] == "manual_bbox"
    assert payload["labels"][0]["rec_confidence"] == 0.88


def test_policy_from_edited_rows_updates_bbox_coordinates(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    Image.new("RGB", (160, 90), (255, 255, 255)).save(image_path)
    detections_path = tmp_path / "detections.json"
    detections_path.write_text(
        json.dumps(
            {
                "engine": "test",
                "source_image": str(image_path),
                "image": {"width": 160, "height": 90},
                "detections": [_detection("det_use", "2026.06.26", [20, 25, 40, 15])],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    policy = draft_review_policy(detections_path)

    edited = policy_from_edited_rows(policy, [{**review_rows(policy)[0], "x": 90, "y": 30, "w": 50, "h": 20, "status": "use"}])

    assert edited.labels[0].bbox.to_list() == [90, 30, 50, 20]
    assert edited.labels[0].polygon == [[90, 30], [140, 30], [140, 50], [90, 50]]


def test_inpaint_review_uses_only_use_status(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    image = Image.new("RGB", (160, 90), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([20, 25, 58, 40], fill=(0, 0, 0))
    draw.rectangle([90, 25, 130, 40], fill=(0, 0, 0))
    image.save(image_path)

    detections_path = tmp_path / "detections.json"
    detections_path.write_text(
        json.dumps(
            {
                "engine": "test",
                "source_image": str(image_path),
                "image": {"width": 160, "height": 90},
                "detections": [
                    _detection("det_keep", "성명", [20, 25, 38, 15]),
                    _detection("det_use", "2026.06.26", [90, 25, 40, 15]),
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    policy = draft_review_policy(detections_path)
    rows = review_rows(policy)
    rows = [{**row, "status": "keep"} if row["id"] == "det_keep" else row for row in rows]
    rows = [{**row, "status": "use"} if row["id"] == "det_use" else row for row in rows]
    policy = policy_from_edited_rows(policy, rows)
    paths = write_review_policy(policy, tmp_path / "review")

    result = inpaint_from_review_policy(paths["review"], InpaintConfig(method="fill", padding=1, dilation=0))
    assert result.detection_count == 1
    arr = np.asarray(result.image)
    assert arr[30, 100].mean() > 240  # use bbox removed
    assert arr[30, 30].mean() < 20  # keep bbox preserved
