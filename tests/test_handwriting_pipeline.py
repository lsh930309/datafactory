from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from datafactory.handwriting import create_handwriting_print_pack, decode_barcode_image, intake_handwriting_scans, latest_accepted_handwriting_samples
from datafactory.policy import draft_review_policy, write_review_policy
from datafactory.registry import RegistryData, RegistryDocument
from datafactory.workbench import document_dir


def _detection(id_: str, text: str, bbox: list[int]) -> dict[str, object]:
    x, y, w, h = bbox
    return {
        "id": id_,
        "text": text,
        "confidence": 0.95,
        "bbox": bbox,
        "bbox_format": "xywh",
        "polygon": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
        "level": "word",
    }


def _registry() -> RegistryData:
    return RegistryData(
        documents={"HW-01": RegistryDocument(doc_id="HW-01", title="수기테스트", writing_method="수기")},
        workflows={},
        bindings=[],
        source_path=Path("registry.xlsx"),
        first_priority_scope_entries=(("금융", "HW-01"),),
    )


def _prepare_authoring(tmp_path: Path) -> tuple[RegistryData, Path]:
    registry = _registry()
    root = tmp_path / "workbench" / "documents"
    doc_root = document_dir(registry.documents["HW-01"], root)
    authoring_dir = doc_root / "authoring"
    authoring_dir.mkdir(parents=True)

    image_path = tmp_path / "blank_template.png"
    image = Image.new("RGB", (640, 420), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([30, 30, 610, 390], outline="black", width=2)
    draw.text((60, 80), "성명", fill="black")
    draw.text((60, 130), "코드", fill="black")
    image.save(image_path)

    detections_path = tmp_path / "detections.json"
    detections_path.write_text(
        json.dumps(
            {
                "engine": "test",
                "source_image": str(image_path),
                "image": {"width": 640, "height": 420},
                "detections": [
                    _detection("label_name", "성명", [60, 80, 50, 22]),
                    _detection("value_name", "홍길동", [160, 80, 90, 24]),
                    _detection("label_code", "코드", [60, 130, 50, 22]),
                    _detection("value_code", "P-000", [160, 130, 120, 24]),
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    policy = draft_review_policy(detections_path)
    review_path = write_review_policy(policy, doc_root / "review")['review']
    review_payload = json.loads(review_path.read_text(encoding="utf-8"))
    for label in review_payload.get("labels", []):
        if label.get("id") == "value_code":
            label["render_mode"] = "printed"
    review_path.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    schema = {
        "schema_version": 2,
        "doc_id": "HW-01",
        "title": "수기테스트",
        "source_image": str(image_path),
        "source_inpainted": str(image_path),
        "source_review": str(review_path),
        "image": {"width": 640, "height": 420},
        "semantic_schema": {"성명": "", "코드": ""},
        "fields": [
            {
                "field_id": "name",
                "label": "성명",
                "value_type": "literal:김수기",
                "bbox_label_id": "value_name",
                "semantic_path": ["성명"],
                "export": {"json_path": "성명"},
            },
            {
                "field_id": "code",
                "label": "코드",
                "value_type": "literal:P-123",
                "bbox_label_id": "value_code",
                "semantic_path": ["코드"],
                "style_class": "body_default",
                "export": {"json_path": "코드"},
            },
        ],
    }
    (authoring_dir / "schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    (authoring_dir / "stylesheet.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "style_classes": [
                    {
                        "style_class": "body_default",
                        "font_size": 22,
                        "fill": [0, 0, 0],
                        "opacity": 1.0,
                        "align": "left",
                        "valign": "middle",
                        "overflow": "shrink",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (authoring_dir / "faker_profile.json").write_text(
        json.dumps({"schema_version": 1, "field_generators": {"name": "literal:김수기", "code": "literal:P-123"}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return registry, root


def test_handwriting_print_pack_and_scan_intake_roundtrip(tmp_path: Path) -> None:
    registry, root = _prepare_authoring(tmp_path)

    pack = create_handwriting_print_pack("HW-01", count=1, registry=registry, root=root, qr_bbox=[420, 40, 160, 160])
    sample = pack["manifest"]["samples"][0]
    template_path = Path(sample["qr_template"])
    barcode_bbox = sample["qr_bbox"]
    with Image.open(template_path) as image:
        crop = image.crop((barcode_bbox[0], barcode_bbox[1], barcode_bbox[0] + barcode_bbox[2], barcode_bbox[1] + barcode_bbox[3]))
        decoded = decode_barcode_image(crop)
    assert decoded["doc_id"] == "HW-01"
    assert decoded["sample_id"] == "sample_000"
    assert sample["handwriting_field_count"] == 1
    assert sample["printed_field_count"] == 1
    with Image.open(template_path).convert("L") as rendered_template:
        printed_crop = rendered_template.crop((160, 130, 280, 154))
        assert sum(1 for pixel in printed_crop.getdata() if pixel < 200) > 10

    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    scan_path = scan_dir / "scan_001.png"
    Image.open(template_path).save(scan_path)
    intake = intake_handwriting_scans(doc_id="HW-01", scan_dir=scan_dir, registry=registry, root=root)

    assert intake["summary"]["acceptedCount"] == 1
    accepted = intake["manifest"]["accepted_samples"][0]
    assert Path(accepted["image"]).exists()
    assert json.loads(Path(accepted["gt"]).read_text(encoding="utf-8")) == {"성명": "김수기", "코드": "P-123"}

    item = {"latestHandwritingScanIntake": intake["paths"]["manifest"]}
    samples = latest_accepted_handwriting_samples(item)
    assert len(samples) == 1
    assert samples[0].gt.exists()
