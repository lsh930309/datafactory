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


def test_cleanup_paint_payload_draws_template_and_updates_manifest(tmp_path: Path, monkeypatch) -> None:
    import datafactory.web_api as web_api
    from datafactory.registry import load_registry
    from datafactory.workbench import document_dir

    monkeypatch.setattr(web_api, "ROOT", tmp_path)
    import datafactory.workbench as workbench_module
    monkeypatch.setattr(workbench_module, "ROOT", tmp_path)
    monkeypatch.setattr(workbench_module, "WORKBENCH_ROOT", tmp_path / "workbench" / "documents")

    registry = load_registry()
    workbench_root = tmp_path / "workbench" / "documents"
    doc = registry.documents["ID-05"]
    doc_root = document_dir(doc, workbench_root)
    doc_root.mkdir(parents=True)
    monkeypatch.setattr(web_api, "workbench_subdir", lambda doc_id, subdir: document_dir(registry.documents[doc_id], workbench_root) / subdir)
    monkeypatch.setattr(
        web_api,
        "update_manifest_artifact",
        lambda doc_id, artifact, path: workbench_module.update_manifest_artifact(doc_id, artifact, path, registry=registry, root=workbench_root),
    )
    base = tmp_path / "base.png"
    Image.new("RGB", (20, 20), "white").save(base)
    review_dir = doc_root / "review" / "base"
    review_dir.mkdir(parents=True)
    review = review_dir / "review.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_detections": str(tmp_path / "detections.json"),
                "source_image": str(base),
                "image": {"width": 20, "height": 20},
                "labels": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = web_api.save_cleanup_paint_payload(
        {
            "docId": "ID-05",
            "reviewPath": str(review),
            "baseImagePath": str(base),
            "paint": {
                "selected_color": [255, 0, 0],
                "brush_radius": 2,
                "strokes": [{"id": "s1", "color": [255, 0, 0], "radius": 2, "points": [{"x": 10, "y": 10}]}],
            },
        }
    )

    painted = tmp_path / result["paths"]["inpainted"]
    assert painted.exists()
    assert Image.open(painted).convert("RGB").getpixel((10, 10)) == (255, 0, 0)
    manifest = json.loads((doc_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifacts"]["inpaint_cleanup_inpainted"].endswith("painted_template.png")
    assert manifest["artifacts"]["inpaint_cleanup_mask"].endswith("paint.json")
