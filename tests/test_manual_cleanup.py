from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from datafactory.inpaint import InpaintConfig, inpaint_from_detections
from datafactory.manual_cleanup import combine_masks, rasterize_manual_mask, save_manual_mask


def test_rasterize_manual_lasso_mask_clips_to_image_size() -> None:
    payload = {
        "strokes": [
            {
                "id": "cleanup_1",
                "type": "lasso",
                "points": [{"x": 2, "y": 2}, {"x": 12, "y": 2}, {"x": 12, "y": 8}, {"x": 2, "y": 8}],
            }
        ]
    }

    mask = rasterize_manual_mask(payload, size=(20, 12))
    arr = np.asarray(mask)

    assert mask.size == (20, 12)
    assert arr[4, 4] == 255
    assert arr[0, 0] == 0


def test_save_manual_mask_writes_vector_json_and_raster(tmp_path: Path) -> None:
    payload = {"strokes": [{"id": "a", "points": [[1, 1], [8, 1], [8, 8], [1, 8]]}]}

    normalized, paths = save_manual_mask(payload, directory=tmp_path / "manual_cleanup", size=(10, 10))

    assert normalized["image"] == {"width": 10, "height": 10}
    assert normalized["strokes"][0]["id"] == "a"
    assert paths.mask_json.exists()
    assert paths.manual_mask.exists()
    saved = json.loads(paths.mask_json.read_text(encoding="utf-8"))
    assert saved["strokes"][0]["points"][0] == {"x": 1, "y": 1}


def test_combine_masks_uses_binary_or() -> None:
    left = Image.new("L", (10, 10), 0)
    right = Image.new("L", (10, 10), 0)
    ImageDraw.Draw(left).rectangle([1, 1, 3, 3], fill=255)
    ImageDraw.Draw(right).rectangle([6, 6, 8, 8], fill=255)

    combined = np.asarray(combine_masks(left, right))

    assert combined[2, 2] == 255
    assert combined[7, 7] == 255
    assert combined[5, 5] == 0


def test_inpaint_extra_manual_mask_is_combined_with_detection_mask(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    image = Image.new("RGB", (80, 50), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([10, 10, 20, 20], fill=(0, 0, 0))
    draw.rectangle([50, 30, 58, 38], fill=(0, 0, 0))
    image.save(image_path)

    detections_path = tmp_path / "detections.json"
    detections_path.write_text(
        json.dumps(
            {
                "engine": "test",
                "source_image": str(image_path),
                "image": {"width": 80, "height": 50},
                "detections": [
                    {"id": "det_0001", "text": "A", "confidence": 1.0, "bbox": [10, 10, 10, 10], "bbox_format": "xywh", "polygon": [[10, 10], [20, 10], [20, 20], [10, 20]], "level": "word"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manual_mask = Image.new("L", (80, 50), 0)
    ImageDraw.Draw(manual_mask).rectangle([50, 30, 58, 38], fill=255)
    manual_mask_path = tmp_path / "manual_mask.png"
    manual_mask.save(manual_mask_path)

    result = inpaint_from_detections(detections_path, InpaintConfig(method="fill", padding=0, dilation=0, extra_mask_path=manual_mask_path))
    arr = np.asarray(result.mask)

    assert result.detection_count == 1
    assert arr[15, 15] == 255
    assert arr[34, 54] == 255


def test_cleanup_template_uses_base_inpainted_image_and_manual_mask_only(tmp_path: Path, monkeypatch) -> None:
    import datafactory.web_api as web_api

    base_path = tmp_path / "base_inpainted.png"
    base = Image.new("RGB", (40, 24), (245, 245, 245))
    ImageDraw.Draw(base).rectangle([4, 4, 10, 10], fill=(20, 20, 20))
    base.save(base_path)

    mask_path = tmp_path / "manual_mask.png"
    mask = Image.new("L", (40, 24), 0)
    ImageDraw.Draw(mask).rectangle([20, 8, 28, 16], fill=255)
    mask.save(mask_path)

    seen = {}

    def fake_lama(image: Image.Image, manual_mask: Image.Image, *, max_side: int) -> Image.Image:
        seen["image_pixel"] = tuple(image.getpixel((5, 5)))
        seen["mask_manual"] = manual_mask.getpixel((24, 12))
        seen["mask_old_bbox"] = manual_mask.getpixel((6, 6))
        seen["max_side"] = max_side
        return Image.new("RGB", image.size, (210, 220, 230))

    monkeypatch.setattr(web_api, "lama_inpaint", fake_lama)

    result = web_api._inpaint_cleanup_template(
        base_image_path=base_path,
        mask_path=mask_path,
        detections_path=tmp_path / "mask.json",
        lama_max_side=1024,
        detection_count=1,
    )

    assert result.source_image == base_path
    assert result.detection_count == 1
    assert result.mask_shape == "polygon"
    assert seen == {
        "image_pixel": (20, 20, 20),
        "mask_manual": 255,
        "mask_old_bbox": 0,
        "max_side": 1024,
    }
