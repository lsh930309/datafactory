from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from datafactory.handwriting import _resolve_qr_bbox, create_handwriting_print_pack, decode_marker_image, encode_marker_image, intake_handwriting_scans, latest_accepted_handwriting_samples, render_handwriting_authoring_preview
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
        if label.get("id") in {"value_name", "value_code"}:
            label["status"] = "use"
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
                "render_mode": "handwriting",
                "semantic_path": ["성명"],
                "export": {"json_path": "성명"},
            },
            {
                "field_id": "code",
                "label": "코드",
                "value_type": "literal:P-123",
                "bbox_label_id": "value_code",
                "render_mode": "printed",
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
    problem_path = Path(sample["problem_sheet"])
    pack_pdf = Path(sample["print_pack_pdf"])
    assert pack_pdf.exists()
    assert pack_pdf.parent.name == "수기테스트_HW-01"
    assert sample["qr_payload"] == {"doc_id": "HW-01", "sample_id": "sample_000", "run_id": sample["run_id"]}
    assert sample["handwriting_field_count"] == 1
    assert sample["printed_field_count"] == 1
    with Image.open(problem_path).convert("L") as rendered_template:
        printed_crop = rendered_template.crop((160, 130, 280, 154))
        assert sum(1 for pixel in printed_crop.getdata() if pixel < 200) > 10
    with Image.open(sample["answer_sheet"]).convert("RGB") as answer_sheet:
        handwriting_crop = answer_sheet.crop((160, 80, 250, 104))
        assert sum(1 for red, green, blue in handwriting_crop.getdata() if red > 150 and green < 80 and blue < 80) > 10

    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    scan_path = scan_dir / "scan_001.png"
    Image.open(problem_path).save(scan_path)
    intake = intake_handwriting_scans(doc_id="HW-01", scan_dir=scan_dir, registry=registry, root=root)

    assert intake["summary"]["acceptedCount"] == 1
    assert "debug" not in intake["manifest"]["records"][0]
    accepted = intake["manifest"]["accepted_samples"][0]
    assert Path(accepted["image"]).exists()
    assert "bbox_overlay" not in accepted
    assert json.loads(Path(accepted["gt"]).read_text(encoding="utf-8")) == {"성명": "김수기", "코드": "P-123"}

    item = {"latestHandwritingScanIntake": intake["paths"]["manifest"]}
    samples = latest_accepted_handwriting_samples(item)
    assert len(samples) == 1
    assert samples[0].gt.exists()


def test_handwriting_scan_intake_warps_to_template_and_writes_debug_overlay_only_when_requested(tmp_path: Path) -> None:
    import pytest

    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    registry, root = _prepare_authoring(tmp_path)
    pack = create_handwriting_print_pack("HW-01", count=1, registry=registry, root=root, qr_bbox=[420, 40, 160, 160])
    sample = pack["manifest"]["samples"][0]
    with Image.open(sample["problem_sheet"]).convert("RGB") as problem:
        source = np.asarray(problem)
    h, w = source.shape[:2]
    src = np.asarray([[0, 0], [w, 0], [w, h], [0, h]], dtype="float32")
    dst = np.asarray([[3, 2], [w - 5, 9], [w - 8, h - 4], [6, h - 9]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(src, dst)
    scanned = cv2.warpPerspective(source, matrix, (w, h), borderMode=cv2.BORDER_REPLICATE)
    scan_dir = tmp_path / "warped-scans"
    scan_dir.mkdir()
    scan_path = scan_dir / "scan_001.png"
    Image.fromarray(scanned).save(scan_path)

    intake = intake_handwriting_scans(doc_id="HW-01", scan_dir=scan_dir, registry=registry, root=root, debug_bbox_overlay=True)

    assert intake["summary"]["acceptedCount"] == 1
    record = intake["manifest"]["records"][0]
    assert record["warp_method"] == "qr_translate"
    overlay_path = Path(record["debug"]["bbox_overlay"])
    warped_path = Path(record["debug"]["warped_image"])
    template_path = Path(record["debug"]["warp_template"])
    diff_path = Path(record["debug"]["warp_diff"])
    assert overlay_path.exists()
    assert warped_path.exists()
    assert template_path.exists()
    assert diff_path.exists()
    with Image.open(record["qr_removed"]) as image:
        assert image.size == (640, 420)
    with Image.open(diff_path).convert("RGB") as diff:
        colors = set(diff.getdata())
        assert (0, 0, 0) in colors
        assert any(red > 150 and green < 80 and blue < 80 for red, green, blue in colors)
        assert any(red < 80 and green > 100 and blue < 80 for red, green, blue in colors)
    assert "bbox_overlay" not in intake["manifest"]["accepted_samples"][0]
    assert "warp_diff" not in intake["manifest"]["accepted_samples"][0]


def test_qr_decode_upscales_small_scanned_marker() -> None:
    import pytest

    pytest.importorskip("cv2")
    payload = {"doc_id": "APP-13", "sample_id": "sample_000", "run_id": "20260713T065822404584Z"}
    qr = encode_marker_image(payload, pixel_size=159)
    scanned_like = Image.new("RGB", (191, 191), "white")
    # Simulate the PDF/rendered scan crop that keeps a small quiet-zone margin
    # around the 159px QR.  The decoder must internally try a high-quality
    # upscaled candidate; otherwise this case is commonly missed by OpenCV.
    scanned_like.paste(qr, (16, 16))

    assert decode_marker_image(scanned_like) == payload


def test_handwriting_print_pack_prefers_render_only_composite_for_duplicate_bbox(tmp_path: Path) -> None:
    registry, root = _prepare_authoring(tmp_path)
    doc_root = document_dir(registry.documents["HW-01"], root)
    authoring_dir = doc_root / "authoring"
    schema_path = authoring_dir / "schema.json"
    faker_path = authoring_dir / "faker_profile.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    # Two primary leaves and one render-only composite share the same value bbox.
    # The primary leaves must stay in GT/schema, but only the composite should be
    # visibly printed on the answer sheet to avoid overprinted red text.
    schema["semantic_schema"] = {"성명": "", "계좌": {"종류": "", "통화": ""}}
    schema["fields"] = [schema["fields"][0]] + [
        {
            "field_id": "account_type",
            "label": "계좌종류",
            "value_type": "literal:외화보통예금",
            "bbox_label_id": "value_code",
            "render_mode": "handwriting",
            "semantic_path": ["계좌", "종류"],
            "export": {"json_path": "계좌/종류"},
        },
        {
            "field_id": "account_currency",
            "label": "통화",
            "value_type": "literal:SGD",
            "bbox_label_id": "value_code",
            "render_mode": "handwriting",
            "semantic_path": ["계좌", "통화"],
            "export": {"json_path": "계좌/통화"},
        },
        {
            "field_id": "account_type_currency",
            "label": "계좌 종류 및 통화",
            "value_type": "literal:외화보통예금 / SGD",
            "bbox_label_id": "value_code",
            "render_mode": "handwriting",
            "semantic_path": ["렌더전용", "계좌 종류 및 통화"],
            "export": {"json_path": "렌더전용/계좌 종류 및 통화", "include": "false"},
        },
    ]
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    faker_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "field_generators": {
                    "name": "literal:김수기",
                    "account_type": "literal:외화보통예금",
                    "account_currency": "literal:SGD",
                    "account_type_currency": "literal:외화보통예금 / SGD",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    pack = create_handwriting_print_pack("HW-01", count=1, registry=registry, root=root, qr_bbox=[420, 40, 160, 160])
    sample = pack["manifest"]["samples"][0]

    assert sample["handwriting_fields"] == ["name", "account_type_currency"]
    assert sample["handwriting_field_count"] == 2
    assert json.loads(Path(sample["public_gt"]).read_text(encoding="utf-8")) == {
        "성명": "김수기",
        "계좌": {"종류": "외화보통예금", "통화": "SGD"},
    }
    public_bbox = json.loads(Path(sample["public_bbox"]).read_text(encoding="utf-8"))
    assert "렌더전용" not in public_bbox
    with Image.open(sample["answer_sheet"]).convert("RGB") as answer_sheet:
        crop = answer_sheet.crop((160, 130, 280, 154))
        red_pixels = sum(1 for red, green, blue in crop.getdata() if red > 150 and green < 80 and blue < 80)
        assert red_pixels > 10


def test_handwriting_qr_bbox_is_forced_to_square() -> None:
    assert _resolve_qr_bbox([420, 40, 160, 90], width=640, height=420) == [420, 40, 160, 160]
    assert _resolve_qr_bbox([600, 390, 160, 90], width=640, height=420) == [480, 260, 160, 160]


def test_handwriting_authoring_preview_uses_schema_render_modes_and_qr_bbox(tmp_path: Path) -> None:
    registry, root = _prepare_authoring(tmp_path)
    doc_root = document_dir(registry.documents["HW-01"], root)
    authoring_dir = doc_root / "authoring"
    schema_path = authoring_dir / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for field in schema["fields"]:
        field["render_mode"] = "printed" if field["field_id"] == "code" else "handwriting"
    schema["handwriting"] = {"qr_bbox": [430, 30, 150, 150], "default_sample_count": 1}
    stylesheet = json.loads((authoring_dir / "stylesheet.json").read_text(encoding="utf-8"))
    faker = json.loads((authoring_dir / "faker_profile.json").read_text(encoding="utf-8"))

    preview = render_handwriting_authoring_preview("HW-01", schema, stylesheet, faker, out_dir=tmp_path / "preview", seed=7)

    assert preview["qr_bbox"] == [430, 30, 150, 150]
    assert preview["printed_field_count"] == 1
    assert preview["handwriting_field_count"] == 1
    with Image.open(preview["image"]).convert("RGB") as image:
        printed_crop = image.crop((160, 130, 280, 154)).convert("L")
        assert sum(1 for pixel in printed_crop.getdata() if pixel < 200) > 10
        handwriting_crop = image.crop((160, 80, 250, 104))
        red_pixels = sum(1 for red, green, blue in handwriting_crop.getdata() if red > 150 and green < 80 and blue < 80)
        assert red_pixels > 10
        qr_crop = image.crop((430, 30, 580, 180)).convert("L")
        assert sum(1 for pixel in qr_crop.getdata() if pixel < 64) > 100


def test_handwriting_render_mode_does_not_fallback_to_review_policy(tmp_path: Path) -> None:
    registry, root = _prepare_authoring(tmp_path)
    doc_root = document_dir(registry.documents["HW-01"], root)
    authoring_dir = doc_root / "authoring"
    schema = json.loads((authoring_dir / "schema.json").read_text(encoding="utf-8"))
    review_path = Path(schema["source_review"])
    review_payload = json.loads(review_path.read_text(encoding="utf-8"))
    for label in review_payload.get("labels", []):
        if label.get("id") == "value_name":
            label["render_mode"] = "printed"
    review_path.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for field in schema["fields"]:
        if field["field_id"] == "name":
            field["render_mode"] = "handwriting"
        if field["field_id"] == "code":
            field["render_mode"] = "printed"
    stylesheet = json.loads((authoring_dir / "stylesheet.json").read_text(encoding="utf-8"))
    faker = json.loads((authoring_dir / "faker_profile.json").read_text(encoding="utf-8"))

    preview = render_handwriting_authoring_preview("HW-01", schema, stylesheet, faker, out_dir=tmp_path / "preview-no-fallback", seed=9)

    assert preview["printed_field_count"] == 1
    assert preview["handwriting_field_count"] == 1
    with Image.open(preview["image"]).convert("RGB") as image:
        handwriting_crop = image.crop((160, 80, 250, 104))
        red_pixels = sum(1 for red, green, blue in handwriting_crop.getdata() if red > 150 and green < 80 and blue < 80)
        assert red_pixels > 10
