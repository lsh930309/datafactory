from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from datafactory.authoring import (
    authoring_review_prune_candidates,
    draft_authoring_bundle,
    load_authoring_bundle,
    migrate_authoring_schema_bboxes_to_review,
    prune_authoring_fields_by_review,
    render_authoring_batch,
    render_authoring_live_preview,
    render_authoring_preview,
    save_authoring_bundle,
    update_authoring_source_inpainted,
)
from datafactory.fonts import list_font_faces, load_font, resolve_font_path
from datafactory.models import BBox, FieldSpec, TemplateSpec
from datafactory.policy import load_review_policy
from datafactory.render import render_template


def _write_review(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source.png"
    Image.new("RGB", (360, 220), "white").save(source)
    detections = tmp_path / "detections.json"
    detections.write_text("{}\n", encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_engine": "test",
                "source_detections": str(detections),
                "source_image": str(source),
                "image": {"width": 360, "height": 220},
                "labels": [
                    {
                        "id": "det_name",
                        "text": "홍길동",
                        "confidence": 0.99,
                        "bbox": [50, 50, 120, 32],
                        "bbox_format": "xywh",
                        "polygon": [[50, 50], [170, 50], [170, 82], [50, 82]],
                        "status": "use",
                        "auto_type": "field_value",
                        "reason": "test",
                    },
                    {
                        "id": "det_label",
                        "text": "성명",
                        "confidence": 0.99,
                        "bbox": [10, 50, 35, 30],
                        "bbox_format": "xywh",
                        "polygon": [[10, 50], [45, 50], [45, 80], [10, 80]],
                        "status": "keep",
                        "auto_type": "static_label",
                        "reason": "test",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    base = tmp_path / "inpainted.png"
    Image.new("RGB", (360, 220), "white").save(base)
    return review, base


def test_draft_authoring_bundle_uses_review_use_labels_only(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)

    result = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring", doc_id="DOC-1", title="테스트문서")

    assert result.field_count == 1
    schema = json.loads(result.schema.read_text(encoding="utf-8"))
    stylesheet = json.loads(result.stylesheet.read_text(encoding="utf-8"))
    faker_profile = json.loads(result.faker_profile.read_text(encoding="utf-8"))
    assert schema["doc_id"] == "DOC-1"
    assert schema["source_inpainted"] == str(base.resolve())
    assert [field["source_detection_id"] for field in schema["fields"]] == ["det_name"]
    assert schema["fields"][0]["field_id"] == "field_001"
    assert schema["fields"][0]["bbox_label_id"] == "det_name"
    assert "bbox" not in schema["fields"][0]
    assert stylesheet["style_classes"][0]["style_class"] == "body_default"
    assert faker_profile["field_generators"] == {"field_001": schema["fields"][0]["value_type"]}


def test_render_authoring_preview_writes_preview_gt_and_validation(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")

    result = render_authoring_preview(draft.schema, draft.stylesheet, draft.faker_profile, out_dir=tmp_path / "authoring" / "render_preview", seed=42)

    assert result.field_count == 1
    assert result.image.exists()
    assert result.kv.exists()
    assert result.bbox.exists()
    assert result.overlay.exists()
    assert result.validation_report.exists()
    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    bbox = json.loads(result.bbox.read_text(encoding="utf-8"))
    validation = json.loads(result.validation_report.read_text(encoding="utf-8"))
    assert kv["values"]["field_001"]
    assert kv["export_values"]["field_001"]
    assert bbox["annotations"][0]["field"] == "field_001"
    assert "warnings" in validation


def test_render_authoring_live_preview_uses_unsaved_payload(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile).payload
    schema = loaded["schema"]
    stylesheet = loaded["stylesheet"]
    faker_profile = loaded["faker_profile"]
    stylesheet["style_classes"][0]["font_size"] = 18
    faker_profile["field_generators"]["field_001"] = "literal:라이브미리보기"

    result = render_authoring_live_preview(
        schema,
        stylesheet,
        faker_profile,
        out_dir=tmp_path / "authoring" / "live_preview",
        seed=42,
    )

    assert result.image.exists()
    assert result.kv.exists()
    assert result.bbox.exists()
    assert result.overlay.exists()
    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    assert kv["values"]["field_001"] == "라이브미리보기"
    assert not result.manifest.exists()


def test_render_authoring_live_preview_fills_blank_values_for_visual_review(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile).payload
    loaded["schema"]["fields"][0]["label"] = "검수용 빈 값"
    loaded["faker_profile"]["field_generators"]["field_001"] = "literal:"

    result = render_authoring_live_preview(
        loaded["schema"],
        loaded["stylesheet"],
        loaded["faker_profile"],
        out_dir=tmp_path / "authoring" / "live_preview_blank",
        seed=42,
    )

    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    assert kv["values"]["field_001"] == "검수용 빈 값"


def test_live_preview_does_not_infer_checkbox_from_selection_label(tmp_path: Path) -> None:
    source = tmp_path / "selection_label.png"
    Image.new("RGB", (240, 100), "white").save(source)
    schema = {
        "schema_version": 1,
        "doc_id": "APP-14",
        "source_inpainted": str(source),
        "fields": [
            {
                "field_id": "p1_optional_consent_year",
                "label": "선택동의년",
                "bbox": [20, 20, 80, 30],
                "bbox_format": "xywh",
                "value_type": "free_text.short",
                "generator": "literal:26",
                "style_class": "body_default",
                "render_policy": {"align": "center", "valign": "middle", "overflow": "shrink"},
                "export": {"json_path": "선택동의.년"},
            }
        ],
    }
    stylesheet = {
        "schema_version": 1,
        "doc_id": "APP-14",
        "style_classes": [{"style_class": "body_default", "font_size": 18, "fill": [0, 0, 0]}],
    }
    faker_profile = {
        "schema_version": 1,
        "doc_id": "APP-14",
        "field_generators": {"p1_optional_consent_year": "literal:26"},
        "constraints": [],
    }

    result = render_authoring_live_preview(
        schema,
        stylesheet,
        faker_profile,
        out_dir=tmp_path / "authoring" / "selection_label_live_preview",
    )

    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    bbox = json.loads(result.bbox.read_text(encoding="utf-8"))
    assert kv["values"]["p1_optional_consent_year"] == "26"
    assert bbox["annotations"][0]["text"] == "26"


def test_checkbox_text_is_not_inferred_from_label_without_explicit_type(tmp_path: Path) -> None:
    source = tmp_path / "checkbox_word_label.png"
    Image.new("RGB", (240, 100), "white").save(source)
    schema = {
        "schema_version": 1,
        "doc_id": "TEST",
        "source_inpainted": str(source),
        "fields": [
            {
                "field_id": "plain_check_word",
                "label": "체크 표시 안내",
                "bbox": [20, 20, 80, 30],
                "bbox_format": "xywh",
                "value_type": "free_text.short",
                "generator": "literal:✓",
                "style_class": "body_default",
                "render_policy": {"align": "center", "valign": "middle", "overflow": "shrink"},
                "export": {"json_path": "plain_check_word"},
            }
        ],
    }
    stylesheet = {
        "schema_version": 1,
        "doc_id": "TEST",
        "style_classes": [{"style_class": "body_default", "font_size": 18, "fill": [0, 0, 0]}],
    }
    faker_profile = {
        "schema_version": 1,
        "doc_id": "TEST",
        "field_generators": {"plain_check_word": "literal:✓"},
        "constraints": [],
    }

    schema_path = tmp_path / "schema.json"
    stylesheet_path = tmp_path / "stylesheet.json"
    faker_profile_path = tmp_path / "faker_profile.json"
    schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
    stylesheet_path.write_text(json.dumps(stylesheet, ensure_ascii=False), encoding="utf-8")
    faker_profile_path.write_text(json.dumps(faker_profile, ensure_ascii=False), encoding="utf-8")

    result = render_authoring_preview(
        schema_path,
        stylesheet_path,
        faker_profile_path,
        out_dir=tmp_path / "authoring" / "check_word_preview",
    )

    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    bbox = json.loads(result.bbox.read_text(encoding="utf-8"))
    assert kv["values"]["plain_check_word"] == "✓"
    assert bbox["annotations"][0]["text"] == "✓"


def test_render_template_applies_x_shift_without_changing_requested_bbox(tmp_path: Path) -> None:
    source = tmp_path / "x_shift_base.png"
    Image.new("RGB", (220, 90), "white").save(source)
    template_plain = TemplateSpec(
        template_id="plain",
        image_path=source,
        fields=[FieldSpec(name="value", bbox=BBox(20, 20, 150, 40), font_size=24, clear_background=False)],
    )
    template_shifted = TemplateSpec(
        template_id="shifted",
        image_path=source,
        fields=[FieldSpec(name="value", bbox=BBox(20, 20, 150, 40), font_size=24, x_shift=18, clear_background=False)],
    )

    _plain_image, plain_annotations = render_template(template_plain, {"value": "ABC"}, render_scale=1)
    _shifted_image, shifted_annotations = render_template(template_shifted, {"value": "ABC"}, render_scale=1)

    assert shifted_annotations[0].requested_bbox.to_list() == plain_annotations[0].requested_bbox.to_list()
    assert shifted_annotations[0].bbox.x >= plain_annotations[0].bbox.x + 16


def test_resolve_font_path_uses_requested_weight_with_same_family() -> None:
    faces = list_font_faces()
    by_family: dict[str, list[dict[str, object]]] = {}
    for face in faces:
        by_family.setdefault(str(face["family"]), []).append(face)
    chosen: tuple[dict[str, object], dict[str, object]] | None = None
    for family_faces in by_family.values():
        normal = next((face for face in family_faces if face.get("weight") == "normal"), None)
        bold = next((face for face in family_faces if face.get("weight") == "bold"), None)
        if normal and bold:
            chosen = (normal, bold)
            break
    if chosen is None:
        pytest.skip("no installed font family exposes both normal and bold faces")
    normal, bold = chosen

    resolved_path, resolved_index = resolve_font_path(
        font_path=str(normal["path"]),
        font_family=str(normal["family"]),
        font_weight="bold",
        font_style=str(normal.get("fontStyle") or "normal"),
        font_index=int(normal.get("index") or 0),
    )

    assert resolved_path == str(bold["absolutePath"])
    assert resolved_index == int(bold["index"])

    compact_family_alias = str(normal["family"]).replace(" ", "")
    alias_path, alias_index = resolve_font_path(
        font_path=str(normal["path"]),
        font_family=compact_family_alias,
        font_weight="bold",
        font_style=str(normal.get("fontStyle") or "normal"),
        font_index=int(normal.get("index") or 0),
    )
    assert alias_path == str(bold["absolutePath"])
    assert alias_index == int(bold["index"])


def test_render_template_forces_bold_weight_even_with_regular_font_face(tmp_path: Path) -> None:
    source = tmp_path / "bold_base.png"
    Image.new("RGB", (260, 90), "white").save(source)
    base_field = {
        "name": "value",
        "bbox": BBox(20, 12, 220, 60),
        "font_size": 34,
        "clear_background": False,
        "font_weight": "normal",
    }
    normal_template = TemplateSpec(template_id="normal", image_path=source, fields=[FieldSpec(**base_field)])
    bold_template = TemplateSpec(template_id="bold", image_path=source, fields=[FieldSpec(**{**base_field, "font_weight": "bold"})])

    normal_image, _normal_annotations = render_template(normal_template, {"value": "Bold Test"}, render_scale=1)
    bold_image, _bold_annotations = render_template(bold_template, {"value": "Bold Test"}, render_scale=1)

    normal_dark = sum(1 for pixel in normal_image.getdata() if pixel != (255, 255, 255))
    bold_dark = sum(1 for pixel in bold_image.getdata() if pixel != (255, 255, 255))
    assert bold_dark > normal_dark * 1.15


def test_checkbox_rules_render_v_for_true_and_blank_for_false(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile).payload
    schema = loaded["schema"]
    first = dict(schema["fields"][0])
    second = dict(first)
    first.update({"field_id": "check_true", "label": "법인 체크박스", "value_type": "bool.checkbox"})
    second.update({"field_id": "check_false", "label": "개인 체크박스", "value_type": "bool.checkbox"})
    schema["fields"] = [first, second]
    faker_profile = loaded["faker_profile"]
    faker_profile["field_generators"] = {"check_true": "literal:☑", "check_false": "literal:☐"}

    saved = save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=loaded["stylesheet"],
        faker_profile=faker_profile,
    )
    result = render_authoring_preview(saved.schema, saved.stylesheet, saved.faker_profile, out_dir=tmp_path / "authoring" / "checkbox", seed=1)

    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    assert kv["values"]["check_true"] == "V"
    assert kv["values"]["check_false"] == ""


def test_symbol_box_checkbox_is_drawn_without_unicode_font_dependency(tmp_path: Path) -> None:
    source = tmp_path / "checkbox_base.png"
    Image.new("RGB", (120, 70), "white").save(source)
    template = TemplateSpec(
        template_id="checkbox",
        image_path=source,
        fields=[
            FieldSpec(name="checked", bbox=BBox(12, 12, 28, 28), type="bool.checkbox", color=(0, 0, 0), checkbox_style="symbol_box", clear_background=False),
            FieldSpec(name="unchecked", bbox=BBox(62, 12, 28, 28), type="bool.checkbox", color=(0, 0, 0), checkbox_style="symbol_box", clear_background=False),
        ],
    )

    image, annotations = render_template(template, {"checked": "V", "unchecked": ""}, render_scale=1)

    assert len(annotations) == 2
    assert annotations[0].text == "V"
    assert annotations[1].text == ""
    # Both boxes should have vector-drawn dark pixels; the checked one should
    # contain more dark pixels due to the additional check stroke.
    checked_dark = sum(1 for pixel in image.crop((10, 10, 42, 42)).getdata() if pixel != (255, 255, 255))
    unchecked_dark = sum(1 for pixel in image.crop((60, 10, 92, 42)).getdata() if pixel != (255, 255, 255))
    assert unchecked_dark > 0
    assert checked_dark > unchecked_dark


def test_standalone_check_mark_styles_are_vector_drawn(tmp_path: Path) -> None:
    source = tmp_path / "check_marks_base.png"
    Image.new("RGB", (160, 70), "white").save(source)
    template = TemplateSpec(
        template_id="check_marks",
        image_path=source,
        fields=[
            FieldSpec(name="thin", bbox=BBox(12, 12, 32, 32), type="bool.checkbox", color=(0, 0, 0), checkbox_style="check_mark", clear_background=False),
            FieldSpec(name="heavy", bbox=BBox(62, 12, 32, 32), type="bool.checkbox", color=(0, 0, 0), checkbox_style="heavy_check_mark", clear_background=False),
            FieldSpec(name="blank", bbox=BBox(112, 12, 32, 32), type="bool.checkbox", color=(0, 0, 0), checkbox_style="check_mark", clear_background=False),
        ],
    )

    image, annotations = render_template(template, {"thin": "✓", "heavy": "✔️", "blank": ""}, render_scale=1)

    assert len(annotations) == 3
    thin_dark = sum(1 for pixel in image.crop((10, 10, 48, 48)).getdata() if pixel != (255, 255, 255))
    heavy_dark = sum(1 for pixel in image.crop((60, 10, 98, 48)).getdata() if pixel != (255, 255, 255))
    blank_dark = sum(1 for pixel in image.crop((110, 10, 148, 48)).getdata() if pixel != (255, 255, 255))
    assert thin_dark > 0
    assert heavy_dark > thin_dark
    assert blank_dark == 0


def test_update_authoring_source_inpainted_only_for_matching_page(tmp_path: Path) -> None:
    page_1 = tmp_path / "page_001.jpg"
    page_2 = tmp_path / "page_002.jpg"
    old_template = tmp_path / "old_template.png"
    new_template = tmp_path / "new_template.png"
    for path in (page_1, page_2, old_template, new_template):
        Image.new("RGB", (80, 80), "white").save(path)

    schema_1 = tmp_path / "authoring" / "schema.json"
    schema_2 = tmp_path / "authoring" / "page_002" / "schema.json"
    schema_1.parent.mkdir(parents=True)
    schema_2.parent.mkdir(parents=True)
    schema_1.write_text(
        json.dumps({"source_image": str(page_1), "source_inpainted": str(old_template), "fields": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    schema_2.write_text(
        json.dumps({"source_image": str(page_2), "source_inpainted": str(old_template), "fields": []}, ensure_ascii=False),
        encoding="utf-8",
    )

    updated = update_authoring_source_inpainted(schema_1, source_image=page_1, inpainted_path=new_template)
    skipped = update_authoring_source_inpainted(schema_2, source_image=page_1, inpainted_path=new_template)

    assert updated["updated"] is True
    assert json.loads(schema_1.read_text(encoding="utf-8"))["source_inpainted"] == str(new_template.resolve())
    assert skipped["updated"] is False
    assert skipped["reason"] == "source_image_mismatch"
    assert json.loads(schema_2.read_text(encoding="utf-8"))["source_inpainted"] == str(old_template)


def test_prune_authoring_fields_by_non_use_review_labels(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile).payload
    schema = loaded["schema"]
    first = dict(schema["fields"][0])
    second = dict(first)
    second.update({"field_id": "field_002", "label": "제거 대상", "bbox_label_id": "det_label", "style_class": "style_removed"})
    schema["fields"] = [first, second]
    stylesheet = loaded["stylesheet"]
    stylesheet["style_classes"].append({**stylesheet["style_classes"][0], "style_class": "style_removed"})
    faker_profile = loaded["faker_profile"]
    faker_profile["field_generators"] = {"field_001": "person.name_ko", "field_002": "free_text.short"}
    save_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile, schema=schema, stylesheet=stylesheet, faker_profile=faker_profile)
    policy = load_review_policy(review)

    candidates = authoring_review_prune_candidates(draft.schema, policy)
    result = prune_authoring_fields_by_review(draft.schema, draft.stylesheet, draft.faker_profile, policy=policy)

    pruned_schema = json.loads(draft.schema.read_text(encoding="utf-8"))
    pruned_stylesheet = json.loads(draft.stylesheet.read_text(encoding="utf-8"))
    pruned_faker = json.loads(draft.faker_profile.read_text(encoding="utf-8"))
    assert candidates["count"] == 1
    assert result["removed_count"] == 1
    assert [field["field_id"] for field in pruned_schema["fields"]] == ["field_001"]
    assert pruned_faker["field_generators"] == {"field_001": "person.name_ko"}
    assert "style_removed" not in {style["style_class"] for style in pruned_stylesheet["style_classes"]}



def test_prune_authoring_fields_by_deleted_review_labels(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile).payload
    schema = loaded["schema"]
    stylesheet = loaded["stylesheet"]
    faker_profile = loaded["faker_profile"]
    first = dict(schema["fields"][0])
    removed = dict(first)
    removed.update({"field_id": "field_deleted", "label": "삭제된 bbox", "bbox_label_id": "det_deleted", "source_detection_id": "det_deleted", "style_class": "style_deleted"})
    schema["fields"] = [first, removed]
    stylesheet["style_classes"].append({**stylesheet["style_classes"][0], "style_class": "style_deleted"})
    faker_profile["field_generators"] = {"field_001": "person.name_ko", "field_deleted": "free_text.short"}
    save_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile, schema=schema, stylesheet=stylesheet, faker_profile=faker_profile)
    policy = load_review_policy(review)

    candidates = authoring_review_prune_candidates(draft.schema, policy)
    result = prune_authoring_fields_by_review(draft.schema, draft.stylesheet, draft.faker_profile, policy=policy)

    pruned_schema = json.loads(draft.schema.read_text(encoding="utf-8"))
    pruned_stylesheet = json.loads(draft.stylesheet.read_text(encoding="utf-8"))
    pruned_faker = json.loads(draft.faker_profile.read_text(encoding="utf-8"))
    assert candidates["count"] == 1
    assert candidates["fields"][0]["bbox_status"] == "deleted"
    assert candidates["fields"][0]["reason"] == "missing_bbox_label"
    assert result["removed_count"] == 1
    assert [field["field_id"] for field in pruned_schema["fields"]] == ["field_001"]
    assert pruned_faker["field_generators"] == {"field_001": "person.name_ko"}
    assert "style_deleted" not in {style["style_class"] for style in pruned_stylesheet["style_classes"]}


def test_load_authoring_bundle_marks_missing_review_bbox_without_coordinates(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile).payload
    schema = loaded["schema"]
    missing = dict(schema["fields"][0])
    missing.update({"field_id": "field_missing", "bbox_label_id": "det_missing", "source_detection_id": "det_missing"})
    schema["fields"] = [missing]
    save_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile, schema=schema, stylesheet=loaded["stylesheet"], faker_profile=loaded["faker_profile"])

    payload = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile).payload

    field = payload["schema"]["fields"][0]
    assert field["bbox_missing"] is True
    assert field["bbox_status"] == "deleted"
    assert "bbox" not in field

def test_save_authoring_bundle_normalizes_field_and_faker_profile(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    stylesheet = loaded.payload["stylesheet"]
    faker_profile = loaded.payload["faker_profile"]
    schema["fields"][0]["label"] = "고객명"
    schema["fields"][0]["generator"] = "choice:홍길동|김민준"
    schema["fields"][0]["render_policy"] = {"align": "center", "valign": "middle", "overflow": "shrink"}
    faker_profile["field_generators"]["field_001"] = "choice:홍길동|김민준"
    stylesheet["style_classes"][0]["font_size"] = "24"
    stylesheet["style_classes"][0]["fill"] = ["12", "34", "56"]

    saved = save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=stylesheet,
        faker_profile=faker_profile,
    )

    saved_schema = json.loads(saved.schema.read_text(encoding="utf-8"))
    saved_stylesheet = json.loads(saved.stylesheet.read_text(encoding="utf-8"))
    saved_faker = json.loads(saved.faker_profile.read_text(encoding="utf-8"))
    assert saved.payload["summary"]["field_count"] == 1
    assert saved_schema["fields"][0]["field_id"] == "field_001"
    assert saved_schema["fields"][0]["generator"] == "choice:홍길동|김민준"
    assert "bbox" not in saved_schema["fields"][0]
    assert saved_schema["fields"][0]["bbox_label_id"] == "det_name"
    assert saved_schema["fields"][0]["export"] == {"json_path": "고객명", "csv_column": "고객명"}
    assert saved_stylesheet["style_classes"][0]["font_size"] == 24
    assert saved_stylesheet["style_classes"][0]["fill"] == [12, 34, 56]
    assert saved_faker["field_generators"] == {"field_001": "choice:홍길동|김민준"}


def test_save_authoring_bundle_preserves_explicit_export_keys(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    schema["fields"][0]["label"] = "고객명"
    schema["fields"][0]["export"] = {"json_path": "person.name", "csv_column": "person_name"}

    saved = save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=loaded.payload["stylesheet"],
        faker_profile=loaded.payload["faker_profile"],
    )

    saved_schema = json.loads(saved.schema.read_text(encoding="utf-8"))
    assert saved_schema["fields"][0]["export"] == {"json_path": "person.name", "csv_column": "person_name"}


def test_save_authoring_bundle_creates_duplicate_label_suffixes(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    first = dict(schema["fields"][0])
    second = dict(first)
    second["field_id"] = "field_002"
    schema["fields"] = [first | {"label": "성명"}, second | {"label": "성명"}]
    faker_profile = loaded.payload["faker_profile"]
    faker_profile["field_generators"] = {"field_001": "person.name_ko", "field_002": "person.name_ko"}

    saved = save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=loaded.payload["stylesheet"],
        faker_profile=faker_profile,
    )

    saved_schema = json.loads(saved.schema.read_text(encoding="utf-8"))
    assert [field["export"]["json_path"] for field in saved_schema["fields"]] == ["성명", "성명__2"]


def test_render_authoring_preview_supports_rule_strings_and_unknown_warning(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    schema["fields"][0]["label"] = "전화번호"
    faker_profile = loaded.payload["faker_profile"]
    faker_profile["field_generators"]["field_001"] = "pattern:010-####-####"
    save_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile, schema=schema, stylesheet=loaded.payload["stylesheet"], faker_profile=faker_profile)

    result = render_authoring_preview(draft.schema, draft.stylesheet, draft.faker_profile, out_dir=tmp_path / "authoring" / "render_preview", seed=7)
    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    assert kv["flat_values"]["전화번호"].startswith("010-")
    assert len(kv["flat_values"]["전화번호"]) == len("010-0000-0000")

    faker_profile["field_generators"]["field_001"] = "unknown.custom.rule"
    save_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile, schema=schema, stylesheet=loaded.payload["stylesheet"], faker_profile=faker_profile)
    result = render_authoring_preview(draft.schema, draft.stylesheet, draft.faker_profile, out_dir=tmp_path / "authoring" / "render_preview_unknown", seed=7)
    validation = json.loads(result.validation_report.read_text(encoding="utf-8"))
    assert validation["warning_count"] >= 1
    assert any(warning["type"] == "unknown_faker_rule" for warning in validation["warnings"])


def test_render_authoring_preview_supports_data_pools_and_pick_record_constraints(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    first = dict(schema["fields"][0])
    second = dict(first)
    second["field_id"] = "business_registration_number"
    second["label"] = "사업자등록번호"
    third = dict(first)
    third["field_id"] = "tax_office_chief"
    third["label"] = "세무서장"
    schema["fields"] = [first | {"field_id": "company_name", "label": "상호"}, second, third]
    faker_profile = loaded.payload["faker_profile"]
    faker_profile["field_generators"] = {
        "company_name": "free_text.short",
        "business_registration_number": "free_text.short",
        "tax_office_chief": "pool:tax_offices",
    }
    faker_profile["data_pools"] = {
        "company_profiles": [
            {"name": "한빛테크 주식회사", "biz_no": "101-81-12345"},
            {"name": "미래산업 주식회사", "biz_no": "220-86-54321"},
        ],
        "tax_offices": ["삼성세무서장", "서초세무서장"],
    }
    faker_profile["constraints"] = [
        {
            "type": "pick_record",
            "pool": "company_profiles",
            "targets": {"company_name": "name", "business_registration_number": "biz_no"},
        }
    ]
    save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=loaded.payload["stylesheet"],
        faker_profile=faker_profile,
    )

    result = render_authoring_preview(draft.schema, draft.stylesheet, draft.faker_profile, out_dir=tmp_path / "authoring" / "render_preview", seed=7)
    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    values = kv["values"]
    paired = {
        "한빛테크 주식회사": "101-81-12345",
        "미래산업 주식회사": "220-86-54321",
    }
    assert paired[values["company_name"]] == values["business_registration_number"]
    assert values["tax_office_chief"] in {"삼성세무서장", "서초세무서장"}
    validation = json.loads(result.validation_report.read_text(encoding="utf-8"))
    assert validation["warning_count"] == 0


def test_render_authoring_batch_writes_multiple_samples_and_summary(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring", doc_id="DOC-1", title="테스트문서")

    result = render_authoring_batch(draft.schema, draft.stylesheet, draft.faker_profile, out_dir=tmp_path / "batch", count=3, seed=900)

    assert result.sample_count == 3
    assert result.field_count == 1
    assert result.summary.exists()
    assert result.manifest.exists()
    assert len(result.manifest.read_text(encoding="utf-8").splitlines()) == 3
    summary = json.loads(result.summary.read_text(encoding="utf-8"))
    assert summary["doc_id"] == "DOC-1"
    assert summary["count"] == 3
    assert len(summary["samples"]) == 3
    for sample in summary["samples"]:
        assert Path(sample["image"]).exists()
        assert Path(sample["kv"]).exists()
        assert Path(sample["bbox"]).exists()
        assert Path(sample["overlay"]).exists()


def test_render_authoring_preview_uses_review_bbox_not_schema_bbox(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    review_payload = json.loads(review.read_text(encoding="utf-8"))
    review_payload["labels"][0]["bbox"] = [80, 90, 140, 40]
    review_payload["labels"][0]["polygon"] = [[80, 90], [220, 90], [220, 130], [80, 130]]
    review.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = render_authoring_preview(draft.schema, draft.stylesheet, draft.faker_profile, out_dir=tmp_path / "authoring" / "render_review_bbox", seed=42)

    bbox = json.loads(result.bbox.read_text(encoding="utf-8"))
    assert bbox["annotations"][0]["requested_bbox"] == [80, 90, 140, 40]


def test_migrate_authoring_schema_bboxes_to_review_strips_schema_and_updates_review(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    schema = json.loads(draft.schema.read_text(encoding="utf-8"))
    schema["fields"][0]["bbox"] = [101, 102, 103, 34]
    schema["fields"][0]["bbox_format"] = "xywh"
    schema["fields"][0]["bbox_label_id"] = "field_bbox_001"
    draft.schema.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = migrate_authoring_schema_bboxes_to_review(draft.schema)

    migrated_schema = json.loads(draft.schema.read_text(encoding="utf-8"))
    migrated_review = json.loads(review.read_text(encoding="utf-8"))
    use_labels = [label for label in migrated_review["labels"] if label["status"] == "use"]
    assert result["migrated"] == 1
    assert "bbox" not in migrated_schema["fields"][0]
    assert migrated_schema["fields"][0]["bbox_label_id"] == "field_bbox_001"
    assert use_labels[0]["id"] == "field_bbox_001"
    assert use_labels[0]["bbox"] == [101, 102, 103, 34]


def test_save_authoring_bundle_preserves_extended_render_policies(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    schema["fields"][0]["render_policy"] = {"align": "left", "valign": "top", "overflow": "wrap"}
    stylesheet = loaded.payload["stylesheet"]
    stylesheet["style_classes"][0]["overflow"] = "wrap"
    stylesheet["style_classes"][0]["line_spacing"] = "1.15"
    stylesheet["style_classes"][0]["baseline_shift"] = "-3"

    saved = save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=stylesheet,
        faker_profile=loaded.payload["faker_profile"],
    )

    saved_schema = json.loads(saved.schema.read_text(encoding="utf-8"))
    saved_stylesheet = json.loads(saved.stylesheet.read_text(encoding="utf-8"))
    assert saved_schema["fields"][0]["render_policy"]["overflow"] == "wrap"
    assert saved_schema["fields"][0]["render_policy"]["fit"] == "wrap"
    assert saved_stylesheet["style_classes"][0]["overflow"] == "wrap"
    assert saved_stylesheet["style_classes"][0]["line_spacing"] == 1.15
    assert saved_stylesheet["style_classes"][0]["baseline_shift"] == -3


def test_font_registry_exposes_workspace_fonts_and_loads_indexed_font() -> None:
    fonts = list_font_faces()
    workspace_fonts = [font for font in fonts if font["source"] == "workspace"]

    assert any(font["path"] == "fonts/malgun.ttf" for font in workspace_fonts)
    malgun = next(font for font in workspace_fonts if font["path"] == "fonts/malgun.ttf")
    font = load_font(14, malgun["path"], malgun["index"])
    path, index = resolve_font_path(font_family=malgun["family"], font_weight=malgun["weight"], font_style=malgun["fontStyle"])

    assert hasattr(font, "getbbox")
    assert path
    assert isinstance(index, int)


def test_authoring_stylesheet_preserves_font_selection_and_preview_uses_it(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    stylesheet = loaded.payload["stylesheet"]
    faker_profile = loaded.payload["faker_profile"]
    stylesheet["style_classes"][0].update(
        {
            "font_path": "fonts/malgun.ttf",
            "font_index": "0",
            "font_family": "Malgun Gothic",
            "font_weight": "bold",
            "font_style": "normal",
            "font_size": "20",
            "fill": [20, 30, 40],
        }
    )
    faker_profile["field_generators"]["field_001"] = "literal:홍길동"

    saved = save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=stylesheet,
        faker_profile=faker_profile,
    )
    saved_stylesheet = json.loads(saved.stylesheet.read_text(encoding="utf-8"))

    assert saved_stylesheet["style_classes"][0]["font_path"] == "fonts/malgun.ttf"
    assert saved_stylesheet["style_classes"][0]["font_index"] == 0
    assert saved_stylesheet["style_classes"][0]["font_weight"] == "bold"
    result = render_authoring_preview(draft.schema, draft.stylesheet, draft.faker_profile, out_dir=tmp_path / "authoring" / "font_preview", seed=1)
    assert result.image.exists()
    bbox = json.loads(result.bbox.read_text(encoding="utf-8"))
    assert bbox["annotations"][0]["text"] == "홍길동"


def test_authoring_library_approval_records_missing_and_copied_drafts(tmp_path: Path) -> None:
    import json

    from datafactory.authoring import approve_authoring_draft_to_library, authoring_library_payload

    request_dir = tmp_path / "request"
    request_dir.mkdir()
    request_path = request_dir / "request.json"
    request_path.write_text(json.dumps({"docId": "APP-14", "title": "카드발급신청서"}), encoding="utf-8")
    (request_dir / "faker_profile_draft.json").write_text("{}", encoding="utf-8")
    library_root = tmp_path / "library"

    result = approve_authoring_draft_to_library(request_path, library_root=library_root, note="approved")
    library = authoring_library_payload(library_root)

    assert result["summary"]["copied"] == 1
    assert "schema_draft.json" in result["approval"]["missing"]
    assert "anchor_map_draft.json" in result["approval"]["missing"]
    assert library["summary"]["approvalCount"] == 1
    assert library["summary"]["valuePoolCount"] >= 1
