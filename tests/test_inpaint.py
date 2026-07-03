from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from datafactory.inpaint import InpaintConfig, inpaint_from_detections, lama_inpaint
from datafactory.inpaint_export import write_inpaint_result


def test_inpaint_fill_uses_all_detection_bboxes(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    image = Image.new("RGB", (120, 80), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([20, 20, 50, 36], fill=(0, 0, 0))
    draw.rectangle([70, 42, 94, 56], fill=(0, 0, 0))
    image.save(image_path)

    detections_path = tmp_path / "detections.json"
    detections_path.write_text(
        json.dumps(
            {
                "engine": "test",
                "source_image": str(image_path),
                "image": {"width": 120, "height": 80},
                "detections": [
                    {"id": "det_0001", "text": "A", "confidence": 1.0, "bbox": [20, 20, 30, 16], "bbox_format": "xywh", "polygon": [[20, 20], [50, 20], [50, 36], [20, 36]], "level": "word"},
                    {"id": "det_0002", "text": "B", "confidence": 1.0, "bbox": [70, 42, 24, 14], "bbox_format": "xywh", "polygon": [[70, 42], [94, 42], [94, 56], [70, 56]], "level": "word"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = inpaint_from_detections(detections_path, InpaintConfig(method="fill", padding=1, dilation=0))
    assert result.detection_count == 2
    assert result.mask_pixels > 0

    arr = np.asarray(result.image)
    assert arr[25, 25].mean() > 240
    assert arr[48, 78].mean() > 240

    paths = write_inpaint_result(result, tmp_path / "out")
    assert paths["mask"].exists()
    assert paths["mask_overlay"].exists()
    assert paths["inpainted"].exists()
    assert paths["comparison"].exists()
    assert paths["summary"].exists()


def test_lama_inpaint_uses_optional_runtime_and_preserves_source_size(tmp_path: Path, monkeypatch) -> None:
    import sys
    import types
    import datafactory.inpaint as inpaint_module

    image_path = tmp_path / "source.png"
    image = Image.new("RGB", (17, 13), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([3, 4, 9, 8], fill=(0, 0, 0))
    image.save(image_path)

    detections_path = tmp_path / "detections.json"
    detections_path.write_text(
        json.dumps(
            {
                "engine": "test",
                "source_image": str(image_path),
                "image": {"width": 17, "height": 13},
                "detections": [
                    {
                        "id": "det_0001",
                        "text": "A",
                        "confidence": 1.0,
                        "bbox": [3, 4, 6, 4],
                        "bbox_format": "xywh",
                        "polygon": [[3, 4], [9, 4], [9, 8], [3, 8]],
                        "level": "word",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class FakeSimpleLama:
        calls = 0

        def __init__(self, *args, **kwargs) -> None:
            type(self).calls += 1

        def __call__(self, source: Image.Image, mask: Image.Image) -> Image.Image:
            assert source.size == (17, 13)
            assert mask.mode == "L"
            # Simulate simple-lama padded output; production code must crop it.
            return Image.new("RGB", (24, 16), (240, 240, 240))

    monkeypatch.setitem(sys.modules, "simple_lama_inpainting", types.SimpleNamespace(SimpleLama=FakeSimpleLama))
    monkeypatch.setattr(inpaint_module, "_select_lama_device", lambda: None)
    monkeypatch.delattr(inpaint_module, "_LAMA_MODEL", raising=False)

    result = inpaint_from_detections(detections_path, InpaintConfig(method="lama", padding=0, dilation=0))

    assert result.method == "lama"
    assert result.image.size == (17, 13)
    assert FakeSimpleLama.calls == 1


def test_lama_inpaint_resizes_and_preserves_unmasked_pixels(monkeypatch) -> None:
    import sys
    import types
    import datafactory.inpaint as inpaint_module

    source = Image.new("RGB", (100, 80), (10, 20, 30))
    mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle([40, 30, 60, 45], fill=255)

    class FakeSimpleLama:
        seen_size = None

        def __init__(self, *args, **kwargs) -> None:
            pass

        def __call__(self, image: Image.Image, mask_image: Image.Image) -> Image.Image:
            type(self).seen_size = image.size
            assert max(image.size) == 50
            return Image.new("RGB", image.size, (200, 210, 220))

    monkeypatch.setitem(sys.modules, "simple_lama_inpainting", types.SimpleNamespace(SimpleLama=FakeSimpleLama))
    monkeypatch.setattr(inpaint_module, "_select_lama_device", lambda: None)
    monkeypatch.delattr(inpaint_module, "_LAMA_MODEL", raising=False)

    result = lama_inpaint(source, mask, max_side=50)
    arr = np.asarray(result)

    assert result.size == source.size
    assert FakeSimpleLama.seen_size == (50, 40)
    assert tuple(arr[0, 0]) == (10, 20, 30)
    assert tuple(arr[35, 50]) == (200, 210, 220)
