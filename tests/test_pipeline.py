from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from datafactory.models import BBox, FieldSpec, TemplateSpec
from datafactory.pipeline import render_samples
from datafactory.render import sample_background


def test_bbox_validation_and_serialization() -> None:
    bbox = BBox.from_list([1.2, 2.6, 30, 40])
    assert bbox.to_list() == [1, 3, 30, 40]
    assert bbox.right == 31
    assert bbox.bottom == 43


def test_sample_background_uses_nearby_pixels() -> None:
    image = Image.new("RGB", (20, 20), (240, 241, 242))
    bbox = BBox(5, 5, 5, 5)
    assert sample_background(image, bbox) == (240, 241, 242)


def test_render_samples_writes_image_kv_bbox_and_manifest(tmp_path: Path) -> None:
    image_path = tmp_path / "seed.png"
    Image.new("RGB", (640, 480), (255, 255, 255)).save(image_path)
    template = TemplateSpec(
        template_id="unit_template",
        image_path=image_path,
        fields=[
            FieldSpec(name="person_name", type="name", bbox=BBox(100, 80, 160, 40), font_size=24),
            FieldSpec(name="amount", type="amount", bbox=BBox(100, 140, 180, 40), font_size=24, align="right"),
        ],
    )

    samples = render_samples(template=template, output_dir=tmp_path / "out", count=2, seed=777)

    assert len(samples) == 2
    manifest = tmp_path / "out" / "manifest.jsonl"
    assert manifest.exists()
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert Path(first["image"]).exists()
    assert Path(first["kv"]).exists()
    assert Path(first["bbox"]).exists()
    assert Path(first["bbox_image"]).exists()

    kv = json.loads(Path(first["kv"]).read_text(encoding="utf-8"))
    bbox = json.loads(Path(first["bbox"]).read_text(encoding="utf-8"))
    assert kv["template_id"] == "unit_template"
    assert set(kv["fields"]) == {"person_name", "amount"}
    assert Path(bbox["image"]["bbox_overlay_path"]).exists()
    assert len(bbox["annotations"]) == 2
    assert bbox["annotations"][0]["bbox_format"] == "xywh"
