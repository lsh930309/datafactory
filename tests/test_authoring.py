from __future__ import annotations

import json
import random
from datetime import date, datetime
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

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
    _generate_values,
    _template_from_authoring,
)
from datafactory.fake_data import generate_value, is_valid_business_registration_number
from datafactory.fonts import list_font_faces, load_font, resolve_font_path
from datafactory.models import BBox, FieldSpec, TemplateSpec
from datafactory.policy import load_review_policy
from datafactory.render import _font_stroke_width, _synthetic_bold_offset, render_template


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
    assert schema["fields"][0]["render_mode"] == "printed"
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


def test_regular_font_synthetic_bold_avoids_stroke_contours(tmp_path: Path) -> None:
    source = tmp_path / "synthetic_bold_base.png"
    Image.new("RGB", (260, 90), "white").save(source)
    field = FieldSpec(
        name="value",
        bbox=BBox(20, 12, 220, 60),
        font_size=34,
        clear_background=False,
        font_weight="bold",
    )
    font = load_font(field.font_size, field.font_path, field.font_index)

    assert _font_stroke_width(field, font) == 0
    assert _synthetic_bold_offset(field, font) >= 1


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

    assert len(annotations) == 1
    assert annotations[0].text == "V"
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

    assert len(annotations) == 2
    assert [annotation.field for annotation in annotations] == ["thin", "heavy"]
    thin_dark = sum(1 for pixel in image.crop((10, 10, 48, 48)).getdata() if pixel != (255, 255, 255))
    heavy_dark = sum(1 for pixel in image.crop((60, 10, 98, 48)).getdata() if pixel != (255, 255, 255))
    blank_dark = sum(1 for pixel in image.crop((110, 10, 148, 48)).getdata() if pixel != (255, 255, 255))
    assert thin_dark > 0
    assert heavy_dark > thin_dark
    assert blank_dark == 0


def test_ellipse_mark_preserves_template_text_and_uses_existing_style_adjustments(tmp_path: Path) -> None:
    source = tmp_path / "ellipse_mark_base.png"
    base = Image.new("RGB", (180, 90), "white")
    base_draw = ImageDraw.Draw(base)
    base_draw.rectangle((70, 35, 89, 44), fill=(210, 30, 30))
    base.save(source)
    field = FieldSpec(
        name="selected",
        bbox=BBox(40, 30, 80, 20),
        type="bool.checkbox",
        font_size=20,
        color=(0, 0, 0),
        baseline_shift=-3,
        x_shift=5,
        checkbox_style="ellipse_mark",
        clear_background=True,
    )
    template = TemplateSpec(template_id="ellipse-mark", image_path=source, fields=[field])

    checked_image, annotations = render_template(template, {"selected": "V"}, render_scale=1)
    unchecked_image, unchecked_annotations = render_template(template, {"selected": ""}, render_scale=1)

    assert FieldSpec.from_dict(field.to_dict()).checkbox_style == "ellipse_mark"
    assert len(annotations) == 1
    assert annotations[0].text == "V"
    assert annotations[0].bbox == BBox(40, 24, 90, 26)
    assert annotations[0].requested_bbox == BBox(40, 30, 80, 20)
    assert checked_image.getpixel((85, 24)) == (0, 0, 0)
    assert checked_image.getpixel((70, 39)) == (210, 30, 30)
    assert unchecked_annotations == []
    assert unchecked_image.tobytes() == base.tobytes()


def test_authoring_preserves_ellipse_mark_as_supported_checkbox_style(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile).payload
    schema = loaded["schema"]
    schema["fields"][0]["value_type"] = "bool.checkbox"
    schema["fields"][0]["render_policy"]["checkbox_style"] = "ellipse_mark"

    saved = save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=loaded["stylesheet"],
        faker_profile=loaded["faker_profile"],
    )
    reloaded = load_authoring_bundle(saved.schema, saved.stylesheet, saved.faker_profile).payload

    assert reloaded["schema"]["fields"][0]["render_policy"]["checkbox_style"] == "ellipse_mark"
    assert "ellipse_mark" in reloaded["supported_checkbox_styles"]


def test_authoring_preserves_supported_display_format(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile).payload
    loaded["schema"]["fields"][0]["display_format"] = "date.yy/mm/dd"

    saved = save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=loaded["schema"],
        stylesheet=loaded["stylesheet"],
        faker_profile=loaded["faker_profile"],
    )
    reloaded = load_authoring_bundle(saved.schema, saved.stylesheet, saved.faker_profile).payload

    assert reloaded["schema"]["fields"][0]["display_format"] == "yy/mm/dd"
    assert reloaded["supported_display_formats"] == ["money.krw", "yy/mm/dd"]


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
    schema["fields"][0].pop("render_mode", None)
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
    assert saved_schema["fields"][0]["render_mode"] == "printed"
    assert saved_schema["fields"][0]["export"] == {"json_path": "고객명", "csv_column": "고객명"}
    assert saved_stylesheet["style_classes"][0]["font_size"] == 24
    assert saved_stylesheet["style_classes"][0]["fill"] == [12, 34, 56]
    assert saved_faker["field_generators"] == {"field_001": "choice:홍길동|김민준"}


def test_semantic_schema_to_authoring_schema_preserves_hierarchy_in_export(tmp_path: Path) -> None:
    from datafactory.authoring import semantic_schema_to_authoring_schema

    review, base = _write_review(tmp_path)
    schema = semantic_schema_to_authoring_schema(
        {
            "doc_id": "DOC-1",
            "title": "테스트",
            "semantic_schema": {"소유자 현황": {"성명": ""}},
            "fields": [
                {
                    "field_id": "det_name",
                    "label": "성명",
                    "key": "소유자 현황/성명",
                    "anchor_id": "det_name",
                    "value": "",
                    "value_type": "person.name_ko",
                }
            ],
        },
        anchor_map={"source_review": str(review), "anchors": [{"anchor_id": "det_name", "bbox": [50, 50, 120, 32], "text": "홍길동"}], "image": {"width": 360, "height": 220}},
        source_review=str(review),
        source_image=str(base),
        source_inpainted=str(base),
    )
    stylesheet = {"schema_version": 1, "style_classes": [{"style_class": "body_default", "font_size": 16}]}
    faker_profile = {"schema_version": 1, "field_generators": {"det_name": "literal:홍길동"}}
    saved = save_authoring_bundle(tmp_path / "schema.json", tmp_path / "stylesheet.json", tmp_path / "faker.json", schema=schema, stylesheet=stylesheet, faker_profile=faker_profile)

    result = render_authoring_preview(saved.schema, saved.stylesheet, saved.faker_profile, out_dir=tmp_path / "render", seed=1)
    kv = json.loads(result.kv.read_text(encoding="utf-8"))

    assert json.loads(saved.schema.read_text(encoding="utf-8"))["semantic_schema"] == {"소유자 현황": {"성명": ""}}
    assert json.loads((tmp_path / "semantic_schema.json").read_text(encoding="utf-8")) == {"소유자 현황": {"성명": ""}}
    assert kv["semantic_values"] == {"소유자 현황": {"성명": "홍길동"}}
    assert kv["flat_values"] == {"소유자 현황/성명": "홍길동"}


def test_semantic_schema_to_authoring_schema_parses_string_semantic_path() -> None:
    from datafactory.authoring import semantic_schema_to_authoring_schema

    schema = semantic_schema_to_authoring_schema(
        {
            "semantic_schema": {"발급정보": {"출력정보": {"출력일자": ""}}},
            "fields": [
                {
                    "field_id": "print_date",
                    "label": "출력일자",
                    "semantic_path": "발급정보/출력정보/출력일자",
                    "anchor_id": "det_date",
                }
            ],
        }
    )

    assert schema["fields"][0]["semantic_path"] == ["발급정보", "출력정보", "출력일자"]
    assert schema["fields"][0]["export"]["json_path"] == "발급정보/출력정보/출력일자"


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
    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    validation = json.loads(result.validation_report.read_text(encoding="utf-8"))
    assert kv["values"]["field_001"] == "전화번호"
    assert validation["warning_count"] >= 1
    assert any(warning["type"] == "unknown_faker_rule" for warning in validation["warnings"])


def test_render_authoring_preview_normalizes_date_component_pattern_rules(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    base_field = loaded.payload["schema"]["fields"][0]
    schema = loaded.payload["schema"]
    schema["fields"] = [
        dict(base_field, field_id="application_date_year", label="신청일자 연도"),
        dict(base_field, field_id="application_date_month", label="신청일자 월"),
        dict(base_field, field_id="application_date_day", label="신청일자 일"),
        dict(base_field, field_id="guarantor_age", label="보증인 연령"),
    ]
    faker_profile = loaded.payload["faker_profile"]
    faker_profile["field_generators"] = {
        "application_date_year": "pattern:####",
        "application_date_month": "pattern:##",
        "application_date_day": "pattern:##",
        "guarantor_age": "pattern:##",
    }
    save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=loaded.payload["stylesheet"],
        faker_profile=faker_profile,
    )

    result = render_authoring_preview(draft.schema, draft.stylesheet, draft.faker_profile, out_dir=tmp_path / "authoring" / "render_date_components", seed=7)
    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    values = kv["values"]

    assert 2020 <= int(values["application_date_year"]) <= 2027
    assert len(values["application_date_month"]) == 2
    assert 1 <= int(values["application_date_month"]) <= 12
    assert len(values["application_date_day"]) == 2
    assert 1 <= int(values["application_date_day"]) <= 28
    assert len(values["guarantor_age"]) == 2


def test_render_authoring_preview_uses_safe_placeholders_for_generic_or_missing_pool_rules(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    first = dict(schema["fields"][0])
    first["field_id"] = "generic_note"
    first["label"] = "비고"
    second = dict(first)
    second["field_id"] = "missing_pool"
    second["label"] = "구조"
    schema["fields"] = [first, second]
    faker_profile = loaded.payload["faker_profile"]
    faker_profile["field_generators"] = {"generic_note": "free_text.short", "missing_pool": "pool:undefined_pool"}
    save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=loaded.payload["stylesheet"],
        faker_profile=faker_profile,
    )

    result = render_authoring_preview(draft.schema, draft.stylesheet, draft.faker_profile, out_dir=tmp_path / "authoring" / "render_safe_fallback", seed=7)
    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    validation = json.loads(result.validation_report.read_text(encoding="utf-8"))

    assert kv["values"]["generic_note"] == "비고"
    assert kv["values"]["missing_pool"] == "구조"
    assert not {"확인함", "해당없음", "정상", "발급완료"} & set(kv["values"].values())
    assert any(warning["rule"] == "pool:undefined_pool" for warning in validation["warnings"])


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




def test_render_authoring_preview_applies_relational_constraints(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    base_field = dict(schema["fields"][0])
    field_ids = [
        "outpatient",
        "inpatient",
        "start_year",
        "start_month",
        "start_day",
        "end_year",
        "end_month",
        "end_day",
        "amount_a",
        "amount_b",
        "amount_total",
    ]
    schema["fields"] = [dict(base_field, field_id=field_id, label=field_id) for field_id in field_ids]
    faker_profile = loaded.payload["faker_profile"]
    faker_profile["field_generators"] = {
        "outpatient": "checkbox.bool",
        "inpatient": "checkbox.bool",
        "start_year": "date.year",
        "start_month": "date.month",
        "start_day": "date.day",
        "end_year": "date.year",
        "end_month": "date.month",
        "end_day": "date.day",
        "amount_a": "money.krw",
        "amount_b": "money.krw",
        "amount_total": "money.krw",
    }
    faker_profile["constraints"] = [
        {"type": "exclusive_choice", "targets": ["outpatient", "inpatient"]},
        {
            "type": "date_order",
            "start": {"year": "start_year", "month": "start_month", "day": "start_day"},
            "end": {"year": "end_year", "month": "end_month", "day": "end_day"},
            "min_year": 2024,
            "max_year": 2024,
            "min_days": 0,
            "max_days": 30,
        },
        {"type": "sum", "sources": ["amount_a", "amount_b"], "target": "amount_total", "format": "money.krw"},
    ]
    save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=loaded.payload["stylesheet"],
        faker_profile=faker_profile,
    )

    result = render_authoring_preview(draft.schema, draft.stylesheet, draft.faker_profile, out_dir=tmp_path / "authoring" / "relational", seed=11)
    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    values = kv["values"]

    assert [values["outpatient"], values["inpatient"]].count("V") == 1
    start = datetime(int(values["start_year"]), int(values["start_month"]), int(values["start_day"]))
    end = datetime(int(values["end_year"]), int(values["end_month"]), int(values["end_day"]))
    assert start <= end
    assert (end - start).days <= 30
    parse_amount = lambda value: int(str(value).replace(",", ""))
    assert parse_amount(values["amount_total"]) == parse_amount(values["amount_a"]) + parse_amount(values["amount_b"])
    validation = json.loads(result.validation_report.read_text(encoding="utf-8"))
    assert validation["warning_count"] == 0

    for seed in range(1, 80):
        values, warnings = _generate_values(schema, faker_profile, random.Random(seed))
        assert warnings == []
        start = datetime(int(values["start_year"]), int(values["start_month"]), int(values["start_day"]))
        end = datetime(int(values["end_year"]), int(values["end_month"]), int(values["end_day"]))
        assert start <= end
        assert (end - start).days <= 30


def test_generate_values_applies_display_formats_after_constraints() -> None:
    schema = {
        "fields": [
            {"field_id": "amount_current", "label": "현재 금액", "display_format": "money.krw"},
            {"field_id": "amount_prior", "label": "종전 금액", "display_format": "money.krw"},
            {"field_id": "amount_total", "label": "합계", "display_format": "money.krw"},
            {"field_id": "period_start", "label": "근무기간 시작", "display_format": "yy/mm/dd"},
            {"field_id": "blank_amount", "label": "미발생 금액", "display_format": "money.krw"},
        ]
    }
    faker_profile = {
        "field_generators": {
            "amount_current": "literal:",
            "amount_prior": "literal:",
            "amount_total": "literal:",
            "period_start": "literal:",
            "blank_amount": "literal:",
        },
        "data_pools": {
            "employment": [
                {
                    "current": 1_250_000,
                    "prior": 250_000,
                    "period_start": "2024.03.05",
                    "blank_amount": "",
                }
            ]
        },
        "constraints": [
            {
                "type": "pick_record",
                "pool": "employment",
                "targets": {
                    "amount_current": "current",
                    "amount_prior": "prior",
                    "period_start": "period_start",
                    "blank_amount": "blank_amount",
                },
            },
            {
                "type": "sum",
                "sources": ["amount_current", "amount_prior"],
                "target": "amount_total",
                "format": "plain",
            },
        ],
    }

    values, warnings = _generate_values(schema, faker_profile, random.Random(7))

    assert warnings == []
    assert values == {
        "amount_current": "1,250,000",
        "amount_prior": "250,000",
        "amount_total": "1,500,000",
        "period_start": "24/03/05",
        "blank_amount": "",
    }


def test_date_group_can_emit_two_digit_year_when_template_has_century_prefix(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    base_field = dict(schema["fields"][0])
    schema["fields"] = [
        dict(base_field, field_id="issue_year", label="일자 년"),
        dict(base_field, field_id="issue_month", label="일자 월"),
        dict(base_field, field_id="issue_day", label="일자 일"),
    ]
    faker_profile = loaded.payload["faker_profile"]
    faker_profile["field_generators"] = {
        "issue_year": "date.year",
        "issue_month": "date.month",
        "issue_day": "date.day",
    }
    faker_profile["constraints"] = [
        {"type": "date_group", "year": "issue_year", "month": "issue_month", "day": "issue_day", "min_year": 2024, "max_year": 2024, "year_format": "yy"}
    ]

    values, warnings = _generate_values(schema, faker_profile, random.Random(7))

    assert warnings == []
    assert values["issue_year"] == "24"
    assert values["issue_month"].isdigit()
    assert values["issue_day"].isdigit()


def test_primary_secondary_group_marks_one_primary_and_remaining_secondary(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    base_field = dict(schema["fields"][0])
    field_ids = [
        "op1_primary",
        "op1_secondary",
        "op2_primary",
        "op2_secondary",
        "op3_primary",
        "op3_secondary",
    ]
    schema["fields"] = [dict(base_field, field_id=field_id, label=field_id, generator="checkbox.bool") for field_id in field_ids]
    faker_profile = loaded.payload["faker_profile"]
    faker_profile["field_generators"] = {field_id: "checkbox.bool" for field_id in field_ids}
    faker_profile["constraints"] = [
        {
            "type": "primary_secondary_group",
            "rows": [
                {"primary": "op1_primary", "secondary": "op1_secondary"},
                {"primary": "op2_primary", "secondary": "op2_secondary"},
                {"primary": "op3_primary", "secondary": "op3_secondary"},
            ],
        }
    ]

    for seed in range(20):
        values, warnings = _generate_values(schema, faker_profile, random.Random(seed))
        assert warnings == []
        primary_values = [values["op1_primary"], values["op2_primary"], values["op3_primary"]]
        secondary_values = [values["op1_secondary"], values["op2_secondary"], values["op3_secondary"]]
        assert primary_values.count("V") == 1
        assert secondary_values.count("V") == 2
        for primary, secondary in zip(primary_values, secondary_values):
            assert {primary, secondary} == {"", "V"}


def test_sparse_row_generation_policy_blanks_trailing_authored_rows(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    schema = loaded.payload["schema"]
    base_field = dict(schema["fields"][0])
    fields = []
    for row in range(1, 6):
        for suffix, rule in (("수술명", "pool:surgery_names"), ("주수술", "checkbox.bool"), ("부수술", "checkbox.bool")):
            field_id = f"수술{row}_{suffix}"
            fields.append(dict(base_field, field_id=field_id, label=field_id, generator=rule))
    schema["fields"] = fields
    faker_profile = loaded.payload["faker_profile"]
    faker_profile["field_generators"] = {field["field_id"]: field["generator"] for field in fields}
    faker_profile["data_pools"] = {"surgery_names": ["충수절제술", "담낭절제술"]}
    faker_profile["constraints"] = [
        {
            "type": "primary_secondary_group",
            "rows": [{"primary": f"수술{row}_주수술", "secondary": f"수술{row}_부수술"} for row in range(1, 6)],
        }
    ]
    faker_profile["generation_policy"] = {
        "수술목록": {
            "type": "sparse_rows",
            "row_prefix": "수술",
            "min_filled_rows": 2,
            "max_filled_rows": 2,
            "total_authored_rows": 5,
        }
    }

    values, warnings = _generate_values(schema, faker_profile, random.Random(7))

    assert warnings == []
    assert values["수술1_수술명"]
    assert values["수술2_수술명"]
    assert values["수술3_수술명"] == ""
    assert values["수술4_주수술"] == ""
    assert values["수술5_부수술"] == ""
    assert [values["수술1_주수술"], values["수술2_주수술"]].count("V") == 1
    assert [values["수술1_부수술"], values["수술2_부수술"]].count("V") == 1


def test_render_authoring_preview_supports_semantic_hidden_and_render_only_fields(tmp_path: Path) -> None:
    review, base = _write_review(tmp_path)
    draft = draft_authoring_bundle(review, base_image_path=base, out_dir=tmp_path / "authoring")
    loaded = load_authoring_bundle(draft.schema, draft.stylesheet, draft.faker_profile)
    base_field = dict(loaded.payload["schema"]["fields"][0])
    fields = [
        dict(base_field, field_id="admission_date", label="입원일", semantic_path=["입퇴원", "입원일"], generator="literal:2024-03-12", render_policy={"render": "false"}),
        dict(base_field, field_id="discharge_date", label="퇴원일", semantic_path=["입퇴원", "퇴원일"], generator="literal:2024-03-18", render_policy={"render": "false"}),
        dict(
            base_field,
            field_id="admission_discharge_period",
            label="입원·퇴원연월일",
            semantic_path=["입퇴원", "표시문구"],
            generator="pool:period_labels",
            export={"json_path": "입퇴원/표시문구", "include": False},
        ),
    ]
    schema = loaded.payload["schema"]
    schema["semantic_schema"] = {"입퇴원": {"입원일": "", "퇴원일": ""}}
    schema["fields"] = fields
    faker_profile = loaded.payload["faker_profile"]
    faker_profile["field_generators"] = {
        "admission_date": "literal:2024-03-12",
        "discharge_date": "literal:2024-03-18",
        "admission_discharge_period": "pool:period_labels",
    }
    faker_profile["data_pools"] = {"periods": [{"admission": "2024-03-12", "discharge": "2024-03-18", "label": "입원: 2024-03-12, 퇴원: 2024-03-18"}], "period_labels": ["입원: 2024-03-12, 퇴원: 2024-03-18"]}
    faker_profile["constraints"] = [{"type": "pick_record", "pool": "periods", "targets": {"admission_date": "admission", "discharge_date": "discharge", "admission_discharge_period": "label"}}]
    save_authoring_bundle(
        draft.schema,
        draft.stylesheet,
        draft.faker_profile,
        schema=schema,
        stylesheet=loaded.payload["stylesheet"],
        faker_profile=faker_profile,
    )

    result = render_authoring_preview(draft.schema, draft.stylesheet, draft.faker_profile, out_dir=tmp_path / "authoring" / "semantic_hidden", seed=7)
    kv = json.loads(result.kv.read_text(encoding="utf-8"))
    bbox = json.loads(result.bbox.read_text(encoding="utf-8"))
    validation = json.loads(result.validation_report.read_text(encoding="utf-8"))

    assert kv["semantic_values"] == {"입퇴원": {"입원일": "2024-03-12", "퇴원일": "2024-03-18"}}
    assert "입퇴원/표시문구" not in kv["flat_values"]
    assert [annotation["field"] for annotation in bbox["annotations"]] == ["admission_discharge_period"]
    assert validation["warning_count"] == 0


def test_age_from_rrn_constraint_uses_issue_date() -> None:
    schema = {
        "fields": [
            {"field_id": "patient_rrn", "label": "주민등록번호", "generator": "literal:900715-1234567", "value_type": "person.rrn"},
            {"field_id": "patient_age", "label": "나이", "generator": "pattern:##", "value_type": "free_text.short"},
            {"field_id": "issue_year", "label": "발급일자 년", "generator": "literal:2024", "value_type": "date.year"},
            {"field_id": "issue_month", "label": "발급일자 월", "generator": "literal:07", "value_type": "date.month"},
            {"field_id": "issue_day", "label": "발급일자 일", "generator": "literal:14", "value_type": "date.day"},
        ]
    }
    faker_profile = {
        "field_generators": {field["field_id"]: field["generator"] for field in schema["fields"]},
        "constraints": [
            {
                "type": "age_from_rrn",
                "rrn": "patient_rrn",
                "age": "patient_age",
                "issue": {"year": "issue_year", "month": "issue_month", "day": "issue_day"},
            }
        ],
    }

    values, warnings = _generate_values(schema, faker_profile, random.Random(1))

    assert warnings == []
    assert values["patient_age"] == "33"


def test_date_not_before_constraint_updates_target_group_after_source_date() -> None:
    schema = {
        "fields": [
            {"field_id": "discharge_date", "label": "퇴원일", "generator": "literal:2024-03-18", "value_type": "date.kr"},
            {"field_id": "issue_year", "label": "발급일자 년", "generator": "literal:2024", "value_type": "date.year"},
            {"field_id": "issue_month", "label": "발급일자 월", "generator": "literal:01", "value_type": "date.month"},
            {"field_id": "issue_day", "label": "발급일자 일", "generator": "literal:01", "value_type": "date.day"},
        ]
    }
    faker_profile = {
        "field_generators": {field["field_id"]: field["generator"] for field in schema["fields"]},
        "constraints": [
            {
                "type": "date_not_before",
                "source": "discharge_date",
                "target": {"year": "issue_year", "month": "issue_month", "day": "issue_day"},
                "min_days": 0,
                "max_days": 0,
            }
        ],
    }

    values, warnings = _generate_values(schema, faker_profile, random.Random(1))

    assert warnings == []
    assert (values["issue_year"], values["issue_month"], values["issue_day"]) == ("2024", "03", "18")


def test_common_faker_address_and_medical_institution_are_realistic() -> None:
    address = generate_value("address", random.Random(3))
    hospital = generate_value("medical_institution", random.Random(3))
    rrn = generate_value("rrn", random.Random(3))

    assert "호" in address
    assert "(" not in address and ")" not in address
    assert any(hospital.endswith(suffix) for suffix in ("병원", "의원", "요양병원", "메디컬센터", "종합병원"))
    assert "-" in rrn
    assert rrn.split("-", 1)[1][0] in {"1", "2", "3", "4"}
    assert rrn.split("-", 1)[1][1:] == "******"


def test_common_faker_business_number_checksum_and_as_of_date() -> None:
    business_number = generate_value("business_reg_no", random.Random(11))
    generated_date = generate_value("date", random.Random(11), as_of_date=date(2024, 2, 29))

    assert is_valid_business_registration_number(business_number)
    assert generated_date <= "2024-02-29"


def test_numeric_and_date_ceiling_constraints_enforce_real_world_bounds() -> None:
    schema = {
        "fields": [
            {"field_id": "rate", "generator": "literal:86.55%"},
            {"field_id": "equity", "generator": "literal:41,700"},
            {"field_id": "assets", "generator": "literal:25,300"},
            {"field_id": "event_date", "generator": "literal:2026-08-20"},
        ]
    }
    faker_profile = {
        "field_generators": {field["field_id"]: field["generator"] for field in schema["fields"]},
        "constraints": [
            {"type": "numeric_range", "target": "rate", "min": 2.5, "max": 20, "decimals": 2, "suffix": "%"},
            {"type": "numeric_compare", "left": "equity", "operator": "<=", "right": "assets"},
            {"type": "date_not_after", "target": "event_date", "max": "as_of_date"},
        ],
    }

    values, warnings = _generate_values(schema, faker_profile, random.Random(2), as_of_date=date(2026, 7, 13))

    assert warnings == []
    assert float(values["rate"].rstrip("%")) <= 20
    assert int(values["equity"].replace(",", "")) <= int(values["assets"].replace(",", ""))
    assert values["event_date"] == "2026-07-13"


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


def test_authoring_email_faker_uses_realistic_domains() -> None:
    schema = {
        "fields": [
            {"field_id": "email_a", "label": "이메일", "value_type": "email"},
            {"field_id": "email_b", "label": "회사 이메일", "value_type": "company.email"},
            {"field_id": "email_c", "label": "개인 이메일", "value_type": "person.email"},
        ]
    }
    faker_profile = {
        "field_generators": {
            "email_a": "email",
            "email_b": "company.email",
            "email_c": "person.email",
        }
    }

    values, warnings = _generate_values(schema, faker_profile, random.Random(7))

    assert warnings == []
    assert all("@" in value for value in values.values())
    assert not any("example" in value for value in values.values())
    assert len({value.split("@", 1)[1] for value in values.values()}) >= 2


def test_authoring_template_scales_review_bbox_to_actual_template_dimensions(tmp_path: Path) -> None:
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_engine": "test",
                "source_detections": "",
                "source_image": "",
                "image": {"width": 1000, "height": 2000},
                "labels": [
                    {
                        "id": "det_value",
                        "text": "값",
                        "confidence": 1.0,
                        "bbox": [100, 400, 200, 100],
                        "bbox_format": "xywh",
                        "polygon": [[100, 400], [300, 400], [300, 500], [100, 500]],
                        "status": "use",
                        "auto_type": "field_value",
                        "reason": "test",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    base = tmp_path / "template.png"
    Image.new("RGB", (500, 1000), "white").save(base)
    schema = {
        "doc_id": "DOC-1",
        "source_review": str(review),
        "image": {"width": 1000, "height": 2000},
        "fields": [
            {
                "field_id": "value",
                "bbox_label_id": "det_value",
                "style_class": "default",
                "value_type": "free_text.short",
            }
        ],
    }
    stylesheet = {"style_classes": [{"style_class": "default", "font_size": 20}]}

    template, warnings = _template_from_authoring(schema, stylesheet, base)

    assert template.fields[0].bbox == BBox(50, 200, 100, 50)
    assert any(warning["type"] == "bbox_scaled_to_template" for warning in warnings)
