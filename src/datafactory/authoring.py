from __future__ import annotations

import json
import random
import re
import string
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

from .fake_data import generate_value
from .fonts import default_font_id, default_font_path, list_font_faces, resolve_font_path
from .models import BBox, FieldSpec, RenderedAnnotation, TemplateSpec
from .policy import ReviewLabel, ReviewPolicy, load_review_policy, use_labels, write_review_policy
from .render import render_template
from .visualize import render_bbox_overlay
from .authoring_backup import backup_authoring_json_before_write

AUTHORING_SCHEMA_VERSION = 1
DEFAULT_STYLE_CLASS = "body_default"
CHECKBOX_VALUE_TYPE = "bool.checkbox"
SUPPORTED_VALUE_TYPES = {
    CHECKBOX_VALUE_TYPE,
    "person.name_ko",
    "person.phone_kr",
    "person.rrn",
    "date.kr",
    "money.krw",
    "company.name_ko",
    "address.ko",
    "free_text.short",
}
FAKER_RULE_EXAMPLES = [
    "person.name_ko",
    "person.phone_kr",
    "person.rrn",
    "date.kr",
    "money.krw",
    "company.name_ko",
    "address.ko",
    "free_text.short",
    "choice:남|여|기타",
    "literal:서울특별시",
    "template:{{company.name_ko}}는 {{date.kr}}에 설립됨",
    "pattern:###-####-####",
    "pool:tax_offices",
    "bool.checkbox",
]

DEFAULT_VALUE_POOLS = {
    "gender_ko": ["남", "여"],
    "yes_no_ko": ["예", "아니오"],
    "tax_offices": ["종로세무서", "중부세무서", "남대문세무서", "강남세무서"],
    "banks_ko": ["국민은행", "신한은행", "우리은행", "하나은행", "농협은행", "기업은행"],
}

DEFAULT_FAKER_PROFILE_TYPES = [
    {"id": "person", "label": "개인 정보", "rules": ["person.name_ko", "person.phone_kr", "person.rrn", "address.ko"]},
    {"id": "company", "label": "기업 정보", "rules": ["company.name_ko", "business_reg_no", "address.ko"]},
    {"id": "finance", "label": "금융/금액", "rules": ["money.krw", "bank", "account"]},
    {"id": "date", "label": "날짜", "rules": ["date.kr"]},
    {"id": "choice", "label": "선택/체크", "rules": ["choice:...", "bool.checkbox", "pool:..."]},
    {"id": "free_text", "label": "짧은 자유 텍스트", "rules": ["free_text.short", "literal:...", "template:..."]},
]


@dataclass(frozen=True)
class AuthoringDraftResult:
    schema: Path
    stylesheet: Path
    faker_profile: Path
    field_count: int


@dataclass(frozen=True)
class AuthoringRenderResult:
    image: Path
    kv: Path
    bbox: Path
    overlay: Path
    validation_report: Path
    manifest: Path
    sample_id: str
    field_count: int
    warning_count: int


@dataclass(frozen=True)
class AuthoringBundleResult:
    schema: Path
    stylesheet: Path
    faker_profile: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class AuthoringBatchResult:
    out_dir: Path
    manifest: Path
    summary: Path
    samples: list[AuthoringRenderResult]
    sample_count: int
    field_count: int
    warning_count: int


def draft_authoring_bundle(
    review_path: Path,
    *,
    base_image_path: Path,
    out_dir: Path,
    doc_id: str | None = None,
    title: str | None = None,
) -> AuthoringDraftResult:
    policy = load_review_policy(review_path)
    base_image_path = base_image_path.resolve()
    if not base_image_path.exists():
        raise FileNotFoundError(base_image_path)
    labels = use_labels(policy)
    if not labels:
        raise ValueError("review policy has no status=use labels")

    out_dir.mkdir(parents=True, exist_ok=True)
    schema_path = out_dir / "schema.json"
    stylesheet_path = out_dir / "stylesheet.json"
    faker_profile_path = out_dir / "faker_profile.json"

    schema = {
        "schema_version": AUTHORING_SCHEMA_VERSION,
        "created_at": _now(),
        "doc_id": doc_id,
        "title": title,
        "source_review": str(review_path.resolve()),
        "source_image": str(policy.source_image.resolve()),
        "source_inpainted": str(base_image_path),
        "image": {"width": policy.image_width, "height": policy.image_height},
        "fields": [_field_from_label(index, label) for index, label in enumerate(labels, start=1)],
        "groups": [],
    }
    stylesheet = {
        "schema_version": AUTHORING_SCHEMA_VERSION,
        "created_at": _now(),
        "doc_id": doc_id,
        "source_image": str(policy.source_image.resolve()),
        "style_classes": [
            {
                "style_class": DEFAULT_STYLE_CLASS,
                "font_family": "default_korean",
                "font_path": default_font_path(),
                "font_size": 28,
                "fill": [32, 32, 32],
                "opacity": 1.0,
                "align": "left",
                "valign": "middle",
                "line_spacing": 1.0,
                "letter_spacing": 0,
                "baseline_shift": 0,
                "x_shift": 0,
                "overflow": "shrink",
                "confidence": 0.2,
                "source_detection_ids": [label.id for label in labels],
            }
        ],
    }
    faker_profile = {
        "schema_version": AUTHORING_SCHEMA_VERSION,
        "created_at": _now(),
        "doc_id": doc_id,
        "locale": "ko_KR",
        "field_generators": {field["field_id"]: field["value_type"] for field in schema["fields"]},
        "constraints": [],
        "notes": "Phase A minimal faker profile. Context and constraints are intentionally not expanded yet.",
    }

    _write_json(schema_path, schema)
    _write_json(stylesheet_path, stylesheet)
    _write_json(faker_profile_path, faker_profile)
    return AuthoringDraftResult(schema_path, stylesheet_path, faker_profile_path, len(labels))


def render_authoring_preview(
    schema_path: Path,
    stylesheet_path: Path,
    faker_profile_path: Path,
    *,
    out_dir: Path,
    seed: int = 1234,
    sample_id: str = "preview_000001",
    render_scale: int = 2,
) -> AuthoringRenderResult:
    schema = _read_json(schema_path)
    stylesheet = _read_json(stylesheet_path)
    faker_profile = _read_json(faker_profile_path)
    base_image = Path(schema["source_inpainted"]).resolve()
    if not base_image.exists():
        raise FileNotFoundError(base_image)

    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    values, generation_warnings = _generate_values(schema, faker_profile, rng)
    template, template_warnings = _template_from_authoring(schema, stylesheet, base_image)
    image, annotations = render_template(template, values, render_scale=render_scale)
    validation = _validate_render(schema, annotations, [*(generation_warnings or []), *template_warnings])

    image_path = out_dir / f"{sample_id}.png"
    kv_path = out_dir / f"{sample_id}.kv.json"
    bbox_path = out_dir / f"{sample_id}.bbox.json"
    overlay_path = out_dir / f"{sample_id}.overlay.png"
    validation_path = out_dir / f"{sample_id}.validation_report.json"
    manifest_path = out_dir / "manifest.jsonl"

    image.save(image_path)
    render_bbox_overlay(image, annotations).save(overlay_path)
    _write_json(kv_path, _kv_payload(sample_id, schema, values))
    _write_json(bbox_path, _bbox_payload(sample_id, schema, image_path, overlay_path, annotations))
    _write_json(validation_path, validation)
    _append_manifest(
        manifest_path,
        {
            "sample_id": sample_id,
            "schema": str(schema_path),
            "stylesheet": str(stylesheet_path),
            "faker_profile": str(faker_profile_path),
            "image": str(image_path),
            "kv": str(kv_path),
            "bbox": str(bbox_path),
            "overlay": str(overlay_path),
            "validation_report": str(validation_path),
            "warning_count": len(validation["warnings"]),
        },
    )
    return AuthoringRenderResult(
        image=image_path,
        kv=kv_path,
        bbox=bbox_path,
        overlay=overlay_path,
        validation_report=validation_path,
        manifest=manifest_path,
        sample_id=sample_id,
        field_count=len(values),
        warning_count=len(validation["warnings"]),
    )


def render_authoring_live_preview(
    schema: dict[str, Any],
    stylesheet: dict[str, Any],
    faker_profile: dict[str, Any],
    *,
    out_dir: Path,
    seed: int = 1234,
    sample_id: str = "live_preview",
    render_scale: int = 2,
) -> AuthoringRenderResult:
    """Render an unsaved authoring payload through the final Pillow renderer.

    Unlike :func:`render_authoring_preview`, this function accepts the current
    UI payload directly and intentionally does not append to the persistent
    preview manifest.  It is used only for interactive visual feedback.
    """

    base_image = Path(schema["source_inpainted"]).resolve()
    if not base_image.exists():
        raise FileNotFoundError(base_image)

    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    values, generation_warnings = _generate_values(schema, faker_profile, rng, force_visible=True)
    template, template_warnings = _template_from_authoring(schema, stylesheet, base_image)
    image, annotations = render_template(template, values, render_scale=render_scale)
    validation = _validate_render(schema, annotations, [*(generation_warnings or []), *template_warnings])

    image_path = out_dir / f"{sample_id}.png"
    kv_path = out_dir / f"{sample_id}.kv.json"
    bbox_path = out_dir / f"{sample_id}.bbox.json"
    overlay_path = out_dir / f"{sample_id}.overlay.png"
    validation_path = out_dir / f"{sample_id}.validation_report.json"
    manifest_path = out_dir / "manifest.jsonl"

    image.save(image_path)
    render_bbox_overlay(image, annotations).save(overlay_path)
    _write_json(kv_path, _kv_payload(sample_id, schema, values))
    _write_json(bbox_path, _bbox_payload(sample_id, schema, image_path, overlay_path, annotations))
    _write_json(validation_path, validation)
    return AuthoringRenderResult(
        image=image_path,
        kv=kv_path,
        bbox=bbox_path,
        overlay=overlay_path,
        validation_report=validation_path,
        manifest=manifest_path,
        sample_id=sample_id,
        field_count=len(values),
        warning_count=len(validation["warnings"]),
    )


def render_authoring_batch(
    schema_path: Path,
    stylesheet_path: Path,
    faker_profile_path: Path,
    *,
    out_dir: Path,
    count: int = 5,
    seed: int = 1234,
    sample_prefix: str = "sample",
    clean: bool = True,
    render_scale: int = 2,
) -> AuthoringBatchResult:
    if count <= 0:
        raise ValueError("count must be positive")
    out_dir.mkdir(parents=True, exist_ok=True)
    if clean:
        for path in out_dir.glob(f"{sample_prefix}_*.*"):
            if path.is_file():
                path.unlink()
        (out_dir / "manifest.jsonl").unlink(missing_ok=True)
        (out_dir / "summary.json").unlink(missing_ok=True)

    samples: list[AuthoringRenderResult] = []
    for index in range(1, count + 1):
        sample_id = f"{sample_prefix}_{index:06d}"
        samples.append(
            render_authoring_preview(
                schema_path,
                stylesheet_path,
                faker_profile_path,
                out_dir=out_dir,
                seed=seed + index - 1,
                sample_id=sample_id,
                render_scale=render_scale,
            )
        )

    schema = _read_json(schema_path)
    warning_count = sum(sample.warning_count for sample in samples)
    summary_path = out_dir / "summary.json"
    manifest_path = out_dir / "manifest.jsonl"
    _write_json(
        summary_path,
        {
            "schema_version": AUTHORING_SCHEMA_VERSION,
            "created_at": _now(),
            "doc_id": schema.get("doc_id"),
            "title": schema.get("title"),
            "schema": str(schema_path),
            "stylesheet": str(stylesheet_path),
            "faker_profile": str(faker_profile_path),
            "out_dir": str(out_dir),
            "count": len(samples),
            "field_count": samples[0].field_count if samples else 0,
            "warning_count": warning_count,
            "samples": [
                {
                    "sample_id": sample.sample_id,
                    "image": str(sample.image),
                    "kv": str(sample.kv),
                    "bbox": str(sample.bbox),
                    "overlay": str(sample.overlay),
                    "validation_report": str(sample.validation_report),
                    "warning_count": sample.warning_count,
                }
                for sample in samples
            ],
        },
    )
    return AuthoringBatchResult(
        out_dir=out_dir,
        manifest=manifest_path,
        summary=summary_path,
        samples=samples,
        sample_count=len(samples),
        field_count=samples[0].field_count if samples else 0,
        warning_count=warning_count,
    )


def load_authoring_bundle(
    schema_path: Path,
    stylesheet_path: Path,
    faker_profile_path: Path,
) -> AuthoringBundleResult:
    schema = _read_json(schema_path)
    stylesheet = _read_json(stylesheet_path)
    faker_profile = _read_json(faker_profile_path)
    payload = _authoring_payload(schema, stylesheet, faker_profile, schema_path=schema_path)
    return AuthoringBundleResult(schema_path, stylesheet_path, faker_profile_path, payload)


def save_authoring_bundle(
    schema_path: Path,
    stylesheet_path: Path,
    faker_profile_path: Path,
    *,
    schema: dict[str, Any],
    stylesheet: dict[str, Any],
    faker_profile: dict[str, Any],
) -> AuthoringBundleResult:
    normalized_schema, normalized_stylesheet, normalized_faker = _normalize_authoring_bundle(schema, stylesheet, faker_profile)
    _write_json(schema_path, normalized_schema)
    _write_json(stylesheet_path, normalized_stylesheet)
    _write_json(faker_profile_path, normalized_faker)
    return AuthoringBundleResult(
        schema_path,
        stylesheet_path,
        faker_profile_path,
        _authoring_payload(normalized_schema, normalized_stylesheet, normalized_faker, schema_path=schema_path),
    )


def update_authoring_source_inpainted(
    schema_path: Path,
    *,
    source_image: Path,
    inpainted_path: Path,
) -> dict[str, Any]:
    """Point an authoring schema at a newly generated template image.

    The authoring renderer intentionally uses ``schema.source_inpainted`` as
    the single source of truth for its background image.  When an inpaint or
    cleanup result is regenerated after authoring already exists, the workbench
    manifest can know about the new image while the schema still points at the
    previous template.  This helper updates only schemas whose ``source_image``
    matches the regenerated page, so multi-page documents keep unrelated pages
    untouched.
    """

    schema_path = schema_path.resolve()
    source_image = source_image.resolve()
    inpainted_path = inpainted_path.resolve()
    if not schema_path.exists():
        return {"schema": str(schema_path), "updated": False, "reason": "missing_schema"}
    if not inpainted_path.exists():
        return {"schema": str(schema_path), "updated": False, "reason": "missing_inpainted", "inpainted": str(inpainted_path)}

    schema = _read_json(schema_path)
    schema_source = _resolve_schema_path(schema.get("source_image"), base=schema_path.parent)
    if schema_source is None:
        return {"schema": str(schema_path), "updated": False, "reason": "missing_source_image"}
    if not _same_resolved_path(schema_source, source_image):
        return {
            "schema": str(schema_path),
            "updated": False,
            "reason": "source_image_mismatch",
            "source_image": str(schema_source),
            "expected_source_image": str(source_image),
        }

    current = _resolve_schema_path(schema.get("source_inpainted"), base=schema_path.parent)
    if current is not None and _same_resolved_path(current, inpainted_path):
        return {"schema": str(schema_path), "updated": False, "reason": "already_current", "source_inpainted": str(inpainted_path)}

    schema["source_inpainted"] = str(inpainted_path)
    schema["updated_at"] = _now()
    _write_json(schema_path, schema)
    return {
        "schema": str(schema_path),
        "updated": True,
        "source_image": str(source_image),
        "previous_source_inpainted": str(current) if current is not None else None,
        "source_inpainted": str(inpainted_path),
    }


def authoring_review_prune_candidates(schema_path: Path, policy: ReviewPolicy) -> dict[str, Any]:
    """Return authoring fields whose reviewed bbox refs are no longer renderable.

    A field becomes non-renderable when its linked review label was changed to
    keep/ignore, or when the label was physically deleted from review.json.  The
    latter case is important for the GUI delete flow: without this check the
    saved authoring schema can keep a dangling ``bbox_label_id`` and later crash
    the canvas when it tries to draw a missing bbox.
    """

    schema_path = schema_path.resolve()
    if not schema_path.exists():
        return {"schema": str(schema_path), "count": 0, "fields": []}
    schema = _read_json(schema_path)
    label_by_id = {label.id: label for label in policy.labels}
    fields: list[dict[str, Any]] = []
    for raw in schema.get("fields", []) if isinstance(schema.get("fields"), list) else []:
        if not isinstance(raw, dict):
            continue
        label_id = str(raw.get("bbox_label_id") or raw.get("source_detection_id") or "")
        if not label_id:
            continue
        label = label_by_id.get(label_id)
        if label is not None and label.status == "use":
            continue
        fields.append(
            {
                "field_id": str(raw.get("field_id") or ""),
                "label": str(raw.get("label") or raw.get("field_id") or ""),
                "bbox_label_id": label_id,
                "bbox_status": label.status if label is not None else "deleted",
                "bbox_text": label.text if label is not None else "",
                "reason": "bbox_label_not_use" if label is not None else "missing_bbox_label",
                "style_class": str(raw.get("style_class") or ""),
            }
        )
    return {"schema": str(schema_path), "count": len(fields), "fields": fields}


def prune_authoring_fields_by_review(
    schema_path: Path,
    stylesheet_path: Path,
    faker_profile_path: Path,
    *,
    policy: ReviewPolicy,
) -> dict[str, Any]:
    """Remove authoring fields whose linked reviewed bbox labels are not use."""

    schema_path = schema_path.resolve()
    stylesheet_path = stylesheet_path.resolve()
    faker_profile_path = faker_profile_path.resolve()
    if not schema_path.exists() or not stylesheet_path.exists() or not faker_profile_path.exists():
        return {
            "schema": str(schema_path),
            "stylesheet": str(stylesheet_path),
            "faker_profile": str(faker_profile_path),
            "removed_count": 0,
            "removed_fields": [],
            "missing": True,
        }

    schema = _read_json(schema_path)
    stylesheet = _read_json(stylesheet_path)
    faker_profile = _read_json(faker_profile_path)
    label_by_id = {label.id: label for label in policy.labels}
    fields = [field for field in schema.get("fields", []) if isinstance(field, dict)]
    removed_fields = []
    for field in fields:
        label_id = str(field.get("bbox_label_id") or field.get("source_detection_id") or "")
        if not label_id:
            continue
        label = label_by_id.get(label_id)
        if label is None or label.status != "use":
            removed_fields.append(field)
    if not removed_fields:
        return {
            "schema": str(schema_path),
            "stylesheet": str(stylesheet_path),
            "faker_profile": str(faker_profile_path),
            "removed_count": 0,
            "removed_fields": [],
        }

    removed_ids = {str(field.get("field_id") or "") for field in removed_fields}
    kept_fields = [field for field in fields if str(field.get("field_id") or "") not in removed_ids]
    next_schema = dict(schema)
    next_schema["fields"] = kept_fields

    kept_style_classes = {str(field.get("style_class") or DEFAULT_STYLE_CLASS) for field in kept_fields}
    style_classes = stylesheet.get("style_classes") if isinstance(stylesheet.get("style_classes"), list) else []
    next_stylesheet = dict(stylesheet)
    if style_classes:
        next_stylesheet["style_classes"] = [
            style
            for style in style_classes
            if not isinstance(style, dict)
            or str(style.get("style_class") or "") == DEFAULT_STYLE_CLASS
            or str(style.get("style_class") or "") in kept_style_classes
        ]
        if not next_stylesheet["style_classes"]:
            next_stylesheet["style_classes"] = [_default_style_class()]

    generators = faker_profile.get("field_generators") if isinstance(faker_profile.get("field_generators"), dict) else {}
    next_faker = dict(faker_profile)
    next_faker["field_generators"] = {str(key): value for key, value in generators.items() if str(key) not in removed_ids}

    save_authoring_bundle(
        schema_path,
        stylesheet_path,
        faker_profile_path,
        schema=next_schema,
        stylesheet=next_stylesheet,
        faker_profile=next_faker,
    )
    return {
        "schema": str(schema_path),
        "stylesheet": str(stylesheet_path),
        "faker_profile": str(faker_profile_path),
        "removed_count": len(removed_fields),
        "removed_fields": [
            {
                "field_id": str(field.get("field_id") or ""),
                "label": str(field.get("label") or field.get("field_id") or ""),
                "bbox_label_id": str(field.get("bbox_label_id") or field.get("source_detection_id") or ""),
            }
            for field in removed_fields
        ],
    }


def _field_from_label(index: int, label: ReviewLabel) -> dict[str, Any]:
    field_id = f"field_{index:03d}"
    value_type = _guess_value_type(label)
    return {
        "field_id": field_id,
        "label": label.text or field_id,
        "bbox_label_id": label.id,
        "source_detection_id": label.id,
        "source_text": label.text,
        "value_type": value_type,
        "generator": value_type,
        "style_class": DEFAULT_STYLE_CLASS,
        "render_policy": {"align": "left", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        "export": {"json_path": field_id, "csv_column": field_id},
        "required": True,
        "notes": "",
    }


def _authoring_payload(schema: dict[str, Any], stylesheet: dict[str, Any], faker_profile: dict[str, Any], *, schema_path: Path | None = None) -> dict[str, Any]:
    schema = _schema_with_runtime_bboxes(schema, schema_path=schema_path)
    fields = schema.get("fields", []) if isinstance(schema.get("fields"), list) else []
    style_classes = stylesheet.get("style_classes", []) if isinstance(stylesheet.get("style_classes"), list) else []
    generators = faker_profile.get("field_generators", {}) if isinstance(faker_profile.get("field_generators"), dict) else {}
    return {
        "schema": schema,
        "stylesheet": stylesheet,
        "faker_profile": faker_profile,
        "summary": {
            "field_count": len(fields),
            "style_class_count": len(style_classes),
            "generator_count": len(generators),
        },
        "supported_value_types": sorted(SUPPORTED_VALUE_TYPES),
        "faker_rule_examples": FAKER_RULE_EXAMPLES,
        "supported_align": ["left", "center", "right"],
        "supported_valign": ["top", "middle", "bottom"],
        "supported_overflow": ["shrink", "clip", "allow", "wrap"],
        "supported_checkbox_styles": ["v_mark", "check_mark", "heavy_check_mark", "symbol_box", "filled_box", "dot"],
        "fonts": {"defaultFontId": default_font_id(), "items": list_font_faces()},
        "bbox_source": {"canonical": "review", "review_path": schema.get("source_review")},
    }


def _schema_with_runtime_bboxes(schema: dict[str, Any], *, schema_path: Path | None = None) -> dict[str, Any]:
    label_by_id = _review_labels_by_id(schema, schema_path=schema_path)
    next_schema = dict(schema)
    fields: list[dict[str, Any]] = []
    for raw in schema.get("fields", []) if isinstance(schema.get("fields"), list) else []:
        if not isinstance(raw, dict):
            continue
        field = dict(raw)
        label_id = str(field.get("bbox_label_id") or field.get("source_detection_id") or "")
        label = label_by_id.get(label_id)
        if label is not None:
            field["bbox"] = label.bbox.to_list()
            field["bbox_format"] = "xywh"
            field["bbox_status"] = label.status
            if not field.get("source_text"):
                field["source_text"] = label.text
        elif isinstance(raw.get("bbox"), (list, tuple)):
            # Legacy compatibility for not-yet-migrated schemas.  Save and
            # migration paths strip this value from persisted schema files.
            field["bbox"] = _normalize_bbox(raw.get("bbox"), str(raw.get("field_id") or "field"))
            field["bbox_format"] = "xywh"
            field["bbox_status"] = "legacy_schema"
        else:
            field["bbox_status"] = "deleted" if label_id else "missing"
            field["bbox_missing"] = True
        fields.append(field)
    next_schema["fields"] = fields
    return next_schema


def _review_labels_by_id(schema: dict[str, Any], *, schema_path: Path | None = None) -> dict[str, ReviewLabel]:
    review_path = _review_path_from_schema(schema, schema_path=schema_path)
    if review_path is None or not review_path.exists():
        return {}
    try:
        policy = load_review_policy(review_path)
    except Exception:
        return {}
    return {label.id: label for label in policy.labels}


def _review_path_from_schema(schema: dict[str, Any], *, schema_path: Path | None = None) -> Path | None:
    value = str(schema.get("source_review") or "").strip()
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    base = schema_path.parent if schema_path is not None else Path.cwd()
    candidate = (base / path).resolve()
    if candidate.exists():
        return candidate
    return (Path.cwd() / path).resolve()


def _normalize_authoring_bundle(
    schema: dict[str, Any],
    stylesheet: dict[str, Any],
    faker_profile: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(schema, dict) or not isinstance(stylesheet, dict) or not isinstance(faker_profile, dict):
        raise ValueError("schema, stylesheet and faker_profile must be objects")
    fields = schema.get("fields")
    if not isinstance(fields, list):
        raise ValueError("schema.fields must be a list")

    normalized_fields: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    used_export_keys: dict[str, int] = {}
    raw_generators = faker_profile.get("field_generators") if isinstance(faker_profile.get("field_generators"), dict) else {}
    for index, raw_field in enumerate(fields, start=1):
        if not isinstance(raw_field, dict):
            raise ValueError(f"schema.fields[{index - 1}] must be an object")
        field = dict(raw_field)
        field_id = str(field.get("field_id") or "").strip()
        if not field_id:
            raise ValueError(f"field #{index} has empty field_id")
        if field_id in seen_ids:
            raise ValueError(f"duplicated field_id: {field_id}")
        seen_ids.add(field_id)

        field["field_id"] = field_id
        field["label"] = str(field.get("label") or field_id)
        field["bbox_label_id"] = str(field.get("bbox_label_id") or field.get("source_detection_id") or field_id)
        field.pop("bbox", None)
        field.pop("bbox_format", None)
        rule = str(raw_generators.get(field_id) or field.get("generator") or field.get("value_type") or "free_text.short").strip() or "free_text.short"
        field["value_type"] = _base_value_type_from_rule(rule, str(field.get("value_type") or "free_text.short"))
        field["generator"] = rule
        field["style_class"] = str(field.get("style_class") or DEFAULT_STYLE_CLASS)
        field["render_policy"] = _normalize_render_policy(field.get("render_policy"))
        field["export"] = _normalize_export(field.get("export"), field_id, str(field["label"]), used_export_keys)
        field["required"] = bool(field.get("required", True))
        field["notes"] = str(field.get("notes") or "")
        normalized_fields.append(field)

    normalized_schema = dict(schema)
    normalized_schema["schema_version"] = int(normalized_schema.get("schema_version") or AUTHORING_SCHEMA_VERSION)
    normalized_schema["updated_at"] = _now()
    normalized_schema["fields"] = normalized_fields

    normalized_stylesheet = dict(stylesheet)
    style_classes = normalized_stylesheet.get("style_classes")
    if not isinstance(style_classes, list) or not style_classes:
        style_classes = [_default_style_class()]
    normalized_stylesheet["schema_version"] = int(normalized_stylesheet.get("schema_version") or AUTHORING_SCHEMA_VERSION)
    normalized_stylesheet["updated_at"] = _now()
    normalized_stylesheet["style_classes"] = [_normalize_style_class(style, index) for index, style in enumerate(style_classes, start=1)]

    normalized_faker = dict(faker_profile)
    normalized_generators: dict[str, str] = {}
    for field in normalized_fields:
        field_id = str(field["field_id"])
        normalized_generators[field_id] = str(field["generator"])
        field["generator"] = normalized_generators[field_id]
    normalized_faker["schema_version"] = int(normalized_faker.get("schema_version") or AUTHORING_SCHEMA_VERSION)
    normalized_faker["updated_at"] = _now()
    normalized_faker["field_generators"] = normalized_generators
    if not isinstance(normalized_faker.get("constraints"), list):
        normalized_faker["constraints"] = []
    return normalized_schema, normalized_stylesheet, normalized_faker


def _normalize_bbox(value: Any, field_id: str) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"{field_id}.bbox must be [x, y, width, height]")
    x, y, width, height = [int(round(float(item))) for item in value]
    if width <= 0 or height <= 0:
        raise ValueError(f"{field_id}.bbox width/height must be positive")
    return [x, y, width, height]


def migrate_authoring_schema_bboxes_to_review(
    schema_path: Path,
    *,
    review_path: Path | None = None,
) -> dict[str, Any]:
    """Move legacy authoring field bbox coordinates into the canonical review policy.

    Authoring schemas used to persist field-level ``bbox`` coordinates.  The
    canonical bbox source is now the reviewed bbox policy, so this migration
    rewrites use-target labels in the review file from those schema bboxes and
    strips coordinates from schema fields, leaving only ``bbox_label_id`` refs.
    """

    schema = _read_json(schema_path)
    fields = schema.get("fields") if isinstance(schema.get("fields"), list) else []
    migrated_fields = [field for field in fields if isinstance(field, dict) and isinstance(field.get("bbox"), (list, tuple))]
    if not migrated_fields:
        normalized_schema = _strip_schema_bboxes(schema)
        if normalized_schema != schema:
            _write_json(schema_path, normalized_schema)
        return {"schema": str(schema_path), "review": str(review_path or _review_path_from_schema(schema, schema_path=schema_path) or ""), "migrated": 0, "field_count": len(fields)}

    target_review_path = review_path or _review_path_from_schema(schema, schema_path=schema_path)
    if target_review_path is None:
        raise ValueError(f"schema has legacy bboxes but no source_review: {schema_path}")
    target_review_path = target_review_path.resolve()
    base_policy = load_review_policy(target_review_path) if target_review_path.exists() else _review_policy_from_schema(schema, schema_path)

    existing_non_use = [label for label in base_policy.labels if label.status != "use"]
    used_label_ids = {label.id for label in existing_non_use}
    migrated_labels: list[ReviewLabel] = []
    normalized_fields: list[dict[str, Any]] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        field_id = str(field.get("field_id") or f"field_{len(normalized_fields) + 1:03d}")
        label_id = _unique_label_id(str(field.get("bbox_label_id") or field.get("source_detection_id") or field_id), used_label_ids)
        used_label_ids.add(label_id)
        next_field = dict(field)
        bbox_value = next_field.pop("bbox", None)
        next_field.pop("bbox_format", None)
        next_field["bbox_label_id"] = label_id
        normalized_fields.append(next_field)
        if not isinstance(bbox_value, (list, tuple)):
            continue
        bbox = BBox.from_list(_normalize_bbox(bbox_value, field_id))
        migrated_labels.append(
            ReviewLabel(
                id=label_id,
                text=str(field.get("source_text") or field.get("label") or field_id),
                confidence=None,
                bbox=bbox,
                polygon=_polygon_from_bbox(bbox),
                status="use",
                auto_type="field_value",
                reason="migrated from authoring schema bbox",
                original_text=str(field.get("source_text") or field.get("label") or field_id),
                text_source="authoring_schema_migration",
            )
        )

    migrated_policy = ReviewPolicy(
        schema_version=base_policy.schema_version,
        source_detections=base_policy.source_detections,
        source_image=base_policy.source_image,
        image_width=base_policy.image_width,
        image_height=base_policy.image_height,
        labels=[*existing_non_use, *migrated_labels],
        source_engine=base_policy.source_engine,
        created_at=base_policy.created_at or _now(),
    )
    paths = write_review_policy(migrated_policy, target_review_path.parent)
    normalized_schema = dict(schema)
    normalized_schema["source_review"] = str(paths["review"].resolve())
    normalized_schema["bbox_source"] = {"canonical": "review", "review_path": str(paths["review"].resolve())}
    normalized_schema["fields"] = normalized_fields
    normalized_schema["updated_at"] = _now()
    _write_json(schema_path, normalized_schema)
    return {"schema": str(schema_path), "review": str(paths["review"]), "migrated": len(migrated_labels), "field_count": len(normalized_fields)}


def _strip_schema_bboxes(schema: dict[str, Any]) -> dict[str, Any]:
    changed = False
    fields: list[dict[str, Any]] = []
    for raw in schema.get("fields", []) if isinstance(schema.get("fields"), list) else []:
        if not isinstance(raw, dict):
            continue
        field = dict(raw)
        label_id = str(field.get("bbox_label_id") or field.get("source_detection_id") or field.get("field_id") or "").strip()
        if label_id and field.get("bbox_label_id") != label_id:
            field["bbox_label_id"] = label_id
            changed = True
        if "bbox" in field or "bbox_format" in field:
            field.pop("bbox", None)
            field.pop("bbox_format", None)
            changed = True
        fields.append(field)
    if not changed:
        return schema
    next_schema = dict(schema)
    next_schema["fields"] = fields
    next_schema["bbox_source"] = {"canonical": "review", "review_path": next_schema.get("source_review")}
    next_schema["updated_at"] = _now()
    return next_schema


def _review_policy_from_schema(schema: dict[str, Any], schema_path: Path) -> ReviewPolicy:
    source_image = Path(str(schema.get("source_image") or ""))
    if not source_image.is_absolute():
        source_image = (schema_path.parent / source_image).resolve()
    width = int(schema.get("image", {}).get("width", 0) or 0) if isinstance(schema.get("image"), dict) else 0
    height = int(schema.get("image", {}).get("height", 0) or 0) if isinstance(schema.get("image"), dict) else 0
    if (not width or not height) and source_image.exists():
        with Image.open(source_image) as image:
            width, height = image.size
    return ReviewPolicy(
        source_detections=schema_path.resolve(),
        source_image=source_image.resolve(),
        image_width=width,
        image_height=height,
        labels=[],
        source_engine="authoring_schema_migration",
        created_at=_now(),
    )


def _polygon_from_bbox(bbox: BBox) -> list[list[int]]:
    return [[bbox.x, bbox.y], [bbox.right, bbox.y], [bbox.right, bbox.bottom], [bbox.x, bbox.bottom]]


def _unique_label_id(raw: str, used: set[str]) -> str:
    base = re.sub(r"[^0-9A-Za-z_가-힣-]+", "_", raw.strip()) or "bbox_label"
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    return candidate


def _normalize_render_policy(value: Any) -> dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    align = str(raw.get("align") or "left")
    valign = str(raw.get("valign") or "middle")
    overflow = str(raw.get("overflow") or raw.get("fit") or "shrink")
    if align not in {"left", "center", "right"}:
        align = "left"
    if valign not in {"top", "middle", "bottom"}:
        valign = "middle"
    fit = str(raw.get("fit") or "").strip()
    if overflow in {"auto_size", "shrink_to_fit"} or fit in {"auto_size", "shrink_to_fit"}:
        overflow = "shrink"
    if overflow not in {"shrink", "clip", "allow", "wrap"}:
        overflow = "shrink"
    checkbox_style = str(raw.get("checkbox_style") or "v_mark").strip()
    if checkbox_style not in {"v_mark", "check_mark", "heavy_check_mark", "symbol_box", "filled_box", "dot"}:
        checkbox_style = "v_mark"
    fit_value = {"shrink": "shrink_to_fit", "clip": "clip", "allow": "allow_overflow", "wrap": "wrap"}[overflow]
    return {"align": align, "valign": valign, "fit": fit_value, "overflow": overflow, "checkbox_style": checkbox_style}


def _normalize_export(value: Any, field_id: str, label: str, used_keys: dict[str, int]) -> dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    raw_key = str(raw.get("json_path") or raw.get("csv_column") or "").strip()
    is_default_key = raw_key == field_id or bool(re.fullmatch(r"field_\d+", raw_key))
    explicit_key = "" if is_default_key else raw_key
    key_base = explicit_key or _export_key_from_label(label, field_id)
    count = used_keys.get(key_base, 0) + 1
    used_keys[key_base] = count
    key = key_base if count == 1 else f"{key_base}__{count}"
    raw_csv = str(raw.get("csv_column") or "").strip()
    csv_column = raw_csv if explicit_key and raw_csv and not re.fullmatch(r"field_\d+", raw_csv) else key
    if count > 1 and csv_column == key_base:
        csv_column = key
    return {"json_path": key, "csv_column": csv_column}


def _export_key_from_label(label: str, fallback: str) -> str:
    key = re.sub(r"\s+", "_", label.strip())
    return key or fallback


def _base_value_type_from_rule(rule: str, fallback: str) -> str:
    normalized = rule.strip()
    if normalized in SUPPORTED_VALUE_TYPES:
        return normalized
    if _is_checkbox_rule(normalized) or _is_checkbox_value(fallback):
        return CHECKBOX_VALUE_TYPE
    if normalized.startswith("template:"):
        return "free_text.short"
    if normalized.startswith("literal:"):
        return fallback if fallback in SUPPORTED_VALUE_TYPES else "free_text.short"
    if normalized.startswith("choice:"):
        return fallback if fallback in SUPPORTED_VALUE_TYPES else "free_text.short"
    if normalized.startswith("pattern:"):
        return fallback if fallback in SUPPORTED_VALUE_TYPES else "free_text.short"
    return fallback if fallback in SUPPORTED_VALUE_TYPES else "free_text.short"


def _default_style_class() -> dict[str, Any]:
    return {
        "style_class": DEFAULT_STYLE_CLASS,
        "font_family": "default_korean",
        "font_path": default_font_path(),
        "font_size": 28,
        "fill": [32, 32, 32],
        "opacity": 1.0,
        "align": "left",
        "valign": "middle",
        "line_spacing": 1.0,
        "letter_spacing": 0,
        "baseline_shift": 0,
        "x_shift": 0,
        "overflow": "shrink",
        "confidence": 0.2,
        "source_detection_ids": [],
    }


def _normalize_style_class(value: Any, index: int) -> dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    style = _default_style_class()
    style.update(raw)
    style["style_class"] = str(style.get("style_class") or (DEFAULT_STYLE_CLASS if index == 1 else f"style_{index:02d}"))
    style["font_size"] = max(1, int(float(style.get("font_size") or 28)))
    style["font_path"] = str(style.get("font_path") or "") or None
    style["font_index"] = max(0, int(float(style.get("font_index", 0) or 0)))
    style["font_family"] = str(style.get("font_family") or "default_korean")
    style["font_weight"] = _normalize_font_weight(style.get("font_weight"))
    style["font_style"] = _normalize_font_style(style.get("font_style"))
    style["fill"] = list(_rgb_tuple(style.get("fill") or [32, 32, 32]))
    style["opacity"] = max(0.0, min(1.0, float(style.get("opacity", 1.0))))
    style["align"] = style["align"] if style.get("align") in {"left", "center", "right"} else "left"
    style["valign"] = style["valign"] if style.get("valign") in {"top", "middle", "bottom"} else "middle"
    style["overflow"] = style["overflow"] if style.get("overflow") in {"shrink", "clip", "allow", "wrap"} else "shrink"
    style["line_spacing"] = max(0.1, float(style.get("line_spacing", 1.0) or 1.0))
    style["letter_spacing"] = float(style.get("letter_spacing", 0.0) or 0.0)
    style["baseline_shift"] = int(round(float(style.get("baseline_shift", 0) or 0)))
    style["x_shift"] = int(round(float(style.get("x_shift", 0) or 0)))
    return style


def _resolved_style_font_path(style: dict[str, Any]) -> str | None:
    path, _index = resolve_font_path(
        font_path=str(style.get("font_path") or "") or None,
        font_family=str(style.get("font_family") or "") or None,
        font_weight=str(style.get("font_weight") or "") or None,
        font_style=str(style.get("font_style") or "") or None,
        font_index=int(float(style.get("font_index", 0) or 0)),
    )
    return path


def _resolved_style_font_index(style: dict[str, Any]) -> int:
    _path, index = resolve_font_path(
        font_path=str(style.get("font_path") or "") or None,
        font_family=str(style.get("font_family") or "") or None,
        font_weight=str(style.get("font_weight") or "") or None,
        font_style=str(style.get("font_style") or "") or None,
        font_index=int(float(style.get("font_index", 0) or 0)),
    )
    return index


def _normalize_font_weight(value: Any) -> str:
    text = str(value or "normal").lower()
    if text in {"bold", "normal", "light", "black"}:
        return text
    if "bold" in text or "heavy" in text:
        return "bold"
    if "light" in text or "thin" in text:
        return "light"
    return "normal"


def _normalize_font_style(value: Any) -> str:
    text = str(value or "normal").lower()
    if text in {"italic", "normal"}:
        return text
    if "italic" in text or "oblique" in text:
        return "italic"
    return "normal"


def _guess_value_type(label: ReviewLabel) -> str:
    text = label.text.strip()
    auto_type = label.auto_type
    if auto_type == "long_paragraph" or len(text) >= 30:
        return "free_text.short"
    if any(token in text for token in ("원", ",")) and any(char.isdigit() for char in text):
        return "money.krw"
    if any(token in text for token in ("-", ".", "/")) and sum(char.isdigit() for char in text) >= 6:
        return "date.kr"
    if any(token in text for token in ("주식회사", "㈜", "회사", "법인")):
        return "company.name_ko"
    if any(token in text for token in ("시", "구", "로", "길")) and len(text) >= 8:
        return "address.ko"
    if auto_type == "field_value" and 2 <= len(text) <= 5 and not any(char.isdigit() for char in text):
        return "person.name_ko"
    return "free_text.short"


def _template_from_authoring(schema: dict[str, Any], stylesheet: dict[str, Any], base_image: Path) -> tuple[TemplateSpec, list[dict[str, Any]]]:
    style_by_id = {style["style_class"]: style for style in stylesheet.get("style_classes", []) if isinstance(style, dict)}
    label_by_id = _review_labels_by_id(schema)
    fields: list[FieldSpec] = []
    warnings: list[dict[str, Any]] = []
    for raw in schema.get("fields", []):
        field_id = str(raw["field_id"])
        label_id = str(raw.get("bbox_label_id") or raw.get("source_detection_id") or "")
        label = label_by_id.get(label_id)
        if label is not None:
            if label.status != "use":
                warnings.append(
                    {
                        "field_id": field_id,
                        "bbox_label_id": label_id,
                        "type": "bbox_label_not_use",
                        "message": "schema field references a reviewed bbox label that is not status=use",
                    }
                )
                continue
            bbox = label.bbox
        elif isinstance(raw.get("bbox"), (list, tuple)):
            # Legacy compatibility for schemas not migrated yet.
            bbox = BBox.from_list(raw["bbox"])
            warnings.append(
                {
                    "field_id": field_id,
                    "type": "legacy_schema_bbox",
                    "message": "field uses legacy schema-level bbox; migrate bbox into review.json",
                }
            )
        else:
            warnings.append(
                {
                    "field_id": field_id,
                    "bbox_label_id": label_id,
                    "type": "missing_bbox_label",
                    "message": "schema field has no matching reviewed bbox label",
                }
            )
            continue
        style = style_by_id.get(raw.get("style_class"), style_by_id.get(DEFAULT_STYLE_CLASS, {}))
        render_policy = raw.get("render_policy", {}) if isinstance(raw.get("render_policy"), dict) else {}
        fields.append(
            FieldSpec(
                name=field_id,
                bbox=bbox,
                type=str(raw.get("value_type") or "free_text.short"),
                font_size=int(style.get("font_size") or 28),
                color=_rgb_tuple(style.get("fill") or [32, 32, 32]),
                opacity=max(0.0, min(1.0, float(style.get("opacity", 1.0)))),
                letter_spacing=float(style.get("letter_spacing", 0.0) or 0.0),
                line_spacing=max(0.1, float(style.get("line_spacing", 1.0) or 1.0)),
                baseline_shift=int(round(float(style.get("baseline_shift", 0) or 0))),
                x_shift=int(round(float(style.get("x_shift", 0) or 0))),
                align=str(render_policy.get("align") or style.get("align") or "left"),  # type: ignore[arg-type]
                valign=str(render_policy.get("valign") or style.get("valign") or "middle"),  # type: ignore[arg-type]
                overflow=str(render_policy.get("overflow") or style.get("overflow") or "shrink"),  # type: ignore[arg-type]
                checkbox_style=str(render_policy.get("checkbox_style") or "v_mark"),  # type: ignore[arg-type]
                clear_background=False,
                include_gt=True,
                font_path=_resolved_style_font_path(style),
                font_index=_resolved_style_font_index(style),
                font_weight=str(style.get("font_weight") or "normal"),
            )
        )
    if not fields:
        raise ValueError("authoring schema has no renderable fields with reviewed bboxes")
    return (
        TemplateSpec(
            template_id=str(schema.get("doc_id") or schema_path_id(base_image)),
            image_path=base_image,
            fields=fields,
            font_path=None,
            description="DataFactory authoring preview template",
        ),
        warnings,
    )


def schema_path_id(path: Path) -> str:
    return path.stem


def _generate_values(
    schema: dict[str, Any],
    faker_profile: dict[str, Any],
    rng: random.Random,
    *,
    force_visible: bool = False,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    generators = faker_profile.get("field_generators", {}) if isinstance(faker_profile.get("field_generators"), dict) else {}
    values: dict[str, str] = {}
    warnings: list[dict[str, Any]] = []
    for field in schema.get("fields", []):
        field_id = str(field["field_id"])
        rule = str(generators.get(field_id) or field.get("generator") or field.get("value_type") or "free_text.short")
        value, warning = _generate_authoring_value(rule, rng, field_id=field_id, faker_profile=faker_profile, values=values)
        value = _normalize_generated_value_for_field(field, rule, value, force_visible=force_visible)
        values[field_id] = value
        if warning:
            warnings.append(warning)
    constraint_warnings = _apply_generation_constraints(values, faker_profile, rng)
    warnings.extend(constraint_warnings)
    for field in schema.get("fields", []):
        if not isinstance(field, dict):
            continue
        field_id = str(field.get("field_id") or "")
        if field_id not in values:
            continue
        rule = str(generators.get(field_id) or field.get("generator") or field.get("value_type") or "free_text.short")
        values[field_id] = _normalize_generated_value_for_field(field, rule, values[field_id], force_visible=force_visible)
    return values, warnings


def _generate_authoring_value(
    rule: str,
    rng: random.Random,
    *,
    field_id: str | None = None,
    faker_profile: dict[str, Any] | None = None,
    values: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any] | None]:
    normalized = rule.strip()
    normalized_lower = normalized.lower()
    if normalized_lower.startswith("choice:"):
        choices = [item.strip() for item in normalized.split(":", 1)[1].split("|") if item.strip()]
        if choices:
            return rng.choice(choices), None
        return _fallback_with_warning(field_id, rule, rng, "choice rule has no choices")
    if _is_checkbox_rule(normalized):
        return ("true" if rng.random() < 0.65 else "false"), None
    if normalized_lower.startswith("pool:"):
        pool_name = normalized.split(":", 1)[1].strip()
        pool = _pool_values(faker_profile, pool_name)
        string_values = [str(item) for item in pool if not isinstance(item, dict) and str(item).strip()]
        if string_values:
            return rng.choice(string_values), None
        return _fallback_with_warning(field_id, rule, rng, f"pool not found or has no scalar values: {pool_name}")
    if normalized_lower.startswith("same_as:"):
        source_field = normalized.split(":", 1)[1].strip()
        if values and source_field in values:
            return values[source_field], None
        return _fallback_with_warning(field_id, rule, rng, f"same_as source is not available yet: {source_field}")
    if normalized_lower.startswith("literal:"):
        return normalized.split(":", 1)[1], None
    if normalized_lower.startswith("template:"):
        template = normalized.split(":", 1)[1]
        return _render_rule_template(template, rng, faker_profile=faker_profile, values=values), None
    if normalized_lower.startswith("pattern:"):
        return _render_pattern(normalized.split(":", 1)[1], rng), None

    mapping = {
        "person.name_ko": "name",
        "person.phone_kr": "phone",
        "person.rrn": "rrn",
        "date.kr": "date",
        "money.krw": "amount",
        "company.name_ko": "company",
        "address.ko": "address",
        "free_text.short": "text",
    }
    if normalized_lower in mapping:
        return generate_value(mapping[normalized_lower], rng), None
    return _fallback_with_warning(field_id, rule, rng, "unknown faker rule")


def _normalize_generated_value_for_field(field: dict[str, Any], rule: str, value: str, *, force_visible: bool = False) -> str:
    if _field_is_checkbox(field, rule):
        if force_visible:
            return "V"
        if _truthy_checkbox_value(value):
            return "V"
        return ""
    text = str(value or "")
    if force_visible and not text.strip():
        label = str(field.get("label") or field.get("field_id") or "값").strip()
        return _preview_fallback_value(label)
    return _strip_guide_parenthetical(text).strip()


def _field_is_checkbox(field: dict[str, Any], rule: str) -> bool:
    return _is_checkbox_rule(rule) or _is_checkbox_value(str(field.get("value_type") or ""))


def _is_checkbox_rule(value: str) -> bool:
    normalized = str(value or "").strip().lower().replace("_", ".").replace("-", ".")
    if normalized in {CHECKBOX_VALUE_TYPE, "checkbox", "boolean", "bool", "bool.check", "checkbox.bool"}:
        return True
    if normalized.startswith(("bool.checkbox", "checkbox:", "boolean:", "bool:")):
        return True
    return False


def _is_checkbox_value(value: str) -> bool:
    return str(value or "").strip().lower().replace("_", ".").replace("-", ".") == CHECKBOX_VALUE_TYPE


def _truthy_checkbox_value(value: str) -> bool:
    normalized = str(value or "").replace("\ufe0f", "").strip().lower()
    return normalized in {"true", "1", "yes", "y", "v", "✓", "✔", "☑", "■", "●", "selected", "checked", "on"}


def _strip_guide_parenthetical(value: str) -> str:
    # 실제 입력값에 섞인 "(...기재)" 식 가이드 문구는 제거한다.
    return re.sub(r"\s*\([^)]*기재[^)]*\)\s*", " ", str(value or "")).strip()


def _preview_fallback_value(label: str) -> str:
    compact = re.sub(r"\s+", " ", label).strip()
    if not compact:
        return "샘플값"
    if len(compact) > 12:
        compact = compact[:12]
    return compact


def _pool_values(faker_profile: dict[str, Any] | None, pool_name: str) -> list[Any]:
    if not faker_profile or not pool_name:
        return []
    pools = faker_profile.get("data_pools")
    if isinstance(pools, dict):
        value = pools.get(pool_name)
        return value if isinstance(value, list) else []
    if isinstance(pools, list):
        for item in pools:
            if isinstance(item, dict) and item.get("name") == pool_name:
                values = item.get("values")
                return values if isinstance(values, list) else []
    return []


def _apply_generation_constraints(values: dict[str, str], faker_profile: dict[str, Any], rng: random.Random) -> list[dict[str, Any]]:
    constraints = faker_profile.get("constraints")
    if not isinstance(constraints, list):
        return []
    warnings: list[dict[str, Any]] = []
    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue
        ctype = str(constraint.get("type") or "").strip()
        if ctype == "pick_record":
            pool_name = str(constraint.get("pool") or "").strip()
            targets = constraint.get("targets")
            records = [item for item in _pool_values(faker_profile, pool_name) if isinstance(item, dict)]
            if not records or not isinstance(targets, dict):
                warnings.append(
                    {
                        "type": "invalid_generation_constraint",
                        "message": "pick_record constraint requires a data pool of object records and a targets mapping",
                        "constraint": constraint,
                    }
                )
                continue
            record = rng.choice(records)
            for field_id, record_key in targets.items():
                key = str(record_key)
                if key in record:
                    values[str(field_id)] = str(record[key])
        elif ctype == "copy":
            source = str(constraint.get("source") or "").strip()
            target = str(constraint.get("target") or "").strip()
            if source and target and source in values:
                values[target] = values[source]
            else:
                warnings.append(
                    {
                        "type": "invalid_generation_constraint",
                        "message": "copy constraint source/target is missing or source was not generated",
                        "constraint": constraint,
                    }
                )
    return warnings


def _fallback_with_warning(field_id: str | None, rule: str, rng: random.Random, message: str) -> tuple[str, dict[str, Any]]:
    return generate_value("text", rng), {
        "field_id": field_id,
        "type": "unknown_faker_rule",
        "message": message,
        "rule": rule,
        "fallback": "free_text.short",
    }


def _render_rule_template(
    template: str,
    rng: random.Random,
    *,
    faker_profile: dict[str, Any] | None = None,
    values: dict[str, str] | None = None,
) -> str:
    def replace(match: re.Match[str]) -> str:
        inner_rule = match.group(1).strip()
        value, _warning = _generate_authoring_value(inner_rule, rng, faker_profile=faker_profile, values=values)
        return value

    return re.sub(r"\{\{([^{}]+)\}\}", replace, template)


def _render_pattern(pattern: str, rng: random.Random) -> str:
    out: list[str] = []
    for char in pattern:
        if char == "#":
            out.append(str(rng.randint(0, 9)))
        elif char == "A":
            out.append(rng.choice(string.ascii_uppercase))
        elif char == "a":
            out.append(rng.choice(string.ascii_lowercase))
        elif char == "*":
            out.append(rng.choice(string.ascii_uppercase + string.digits))
        else:
            out.append(char)
    return "".join(out)


def _validate_render(schema: dict[str, Any], annotations: list[RenderedAnnotation], generation_warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    fields = {str(field["field_id"]): field for field in schema.get("fields", [])}
    annotated_fields = {annotation.field for annotation in annotations}
    warnings: list[dict[str, Any]] = list(generation_warnings or [])
    for annotation in annotations:
        requested = annotation.requested_bbox
        actual = annotation.bbox
        field_policy = fields.get(annotation.field, {}).get("render_policy", {}) if isinstance(fields.get(annotation.field, {}).get("render_policy"), dict) else {}
        allowed_overflow = str(field_policy.get("overflow") or "") == "allow"
        if not allowed_overflow and (actual.width > requested.width or actual.height > requested.height):
            warnings.append(
                {
                    "field_id": annotation.field,
                    "type": "overflow",
                    "message": "rendered text bbox exceeds requested bbox",
                    "requested_bbox": requested.to_list(),
                    "actual_bbox": actual.to_list(),
                }
            )
        if annotation.field not in fields:
            warnings.append({"field_id": annotation.field, "type": "unknown_field", "message": "annotation has no schema field"})
    for field_id in fields:
        if field_id not in annotated_fields:
            warnings.append({"field_id": field_id, "type": "not_rendered", "message": "schema field was not rendered, usually because its reviewed bbox label is missing or disabled"})
    return {"ok": not warnings, "warning_count": len(warnings), "warnings": warnings}


def _kv_payload(sample_id: str, schema: dict[str, Any], values: dict[str, str]) -> dict[str, Any]:
    export_values = _export_values(schema, values)
    return {
        "sample_id": sample_id,
        "doc_id": schema.get("doc_id"),
        "schema_version": schema.get("schema_version"),
        "values": values,
        "export_values": export_values,
        "flat_values": export_values,
    }


def _export_values(schema: dict[str, Any], values: dict[str, str]) -> dict[str, str]:
    exported: dict[str, str] = {}
    for field in schema.get("fields", []):
        field_id = str(field.get("field_id") or "")
        export = field.get("export") if isinstance(field.get("export"), dict) else {}
        key = str(export.get("json_path") or export.get("csv_column") or field_id)
        if field_id in values:
            exported[key] = values[field_id]
    return exported


def _bbox_payload(sample_id: str, schema: dict[str, Any], image_path: Path, overlay_path: Path, annotations: list[RenderedAnnotation]) -> dict[str, Any]:
    with Image.open(image_path) as image:
        width, height = image.size
    return {
        "sample_id": sample_id,
        "doc_id": schema.get("doc_id"),
        "source_inpainted": schema.get("source_inpainted"),
        "image": {"path": str(image_path), "bbox_overlay_path": str(overlay_path), "width": width, "height": height},
        "annotations": [annotation.to_dict() for annotation in annotations],
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_schema_path(value: Any, *, base: Path) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _same_resolved_path(left: Path, right: Path) -> bool:
    return left.resolve() == right.resolve()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=payload, reason="datafactory.authoring._write_json")
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _append_manifest(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def _rgb_tuple(value: Any) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return (32, 32, 32)
    rgb = tuple(max(0, min(255, int(v))) for v in value)
    return rgb  # type: ignore[return-value]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def review_anchor_map(review_path: Path, *, out_path: Path | None = None, doc_id: str | None = None, title: str | None = None) -> dict[str, Any]:
    policy = load_review_policy(review_path)
    anchors = []
    for label in policy.labels:
        if label.status != "use":
            continue
        anchors.append(
            {
                "anchor_id": label.id,
                "source": "bbox_review",
                "text": label.text,
                "bbox": label.bbox.to_list(),
                "bbox_format": "xywh",
                "status": label.status,
                "suggested_schema_key": label.text or label.id,
                "confidence": label.confidence,
            }
        )
    payload = {
        "schema_version": AUTHORING_SCHEMA_VERSION,
        "created_at": _now(),
        "doc_id": doc_id,
        "title": title,
        "source_review": str(review_path.resolve()),
        "source_image": str(policy.source_image.resolve()),
        "image": {"width": policy.image_width, "height": policy.image_height},
        "anchors": anchors,
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_path, payload)
    return payload


def draft_stylesheet_from_review(review_path: Path, *, out_path: Path, doc_id: str | None = None) -> dict[str, Any]:
    policy = load_review_policy(review_path)
    labels = use_labels(policy)
    payload = {
        "schema_version": AUTHORING_SCHEMA_VERSION,
        "created_at": _now(),
        "doc_id": doc_id,
        "source_review": str(review_path.resolve()),
        "source_image": str(policy.source_image.resolve()),
        "image": {"width": policy.image_width, "height": policy.image_height},
        "status": "draft_from_bbox_review",
        "safe_application": "draft_only_no_final_stylesheet_overwrite",
        "style_classes": [
            {
                **_default_style_class(),
                "confidence": 0.2,
                "source_detection_ids": [label.id for label in labels],
            }
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(out_path, payload)
    return payload


def semantic_schema_to_authoring_schema(
    semantic_schema: dict[str, Any],
    *,
    anchor_map: dict[str, Any] | None = None,
    source_review: str | None = None,
    source_image: str | None = None,
    source_inpainted: str | None = None,
    doc_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    fields = semantic_schema.get("fields") if isinstance(semantic_schema.get("fields"), list) else []
    anchors = {str(anchor.get("anchor_id") or ""): anchor for anchor in (anchor_map or {}).get("anchors", []) if isinstance(anchor, dict)}
    output_fields: list[dict[str, Any]] = []
    for index, raw in enumerate(fields, start=1):
        if not isinstance(raw, dict):
            continue
        field_id = str(raw.get("field_id") or raw.get("id") or f"field_{index:03d}").strip()
        label = str(raw.get("label") or raw.get("key") or raw.get("name") or field_id).strip()
        anchor_id = str(raw.get("anchor_id") or raw.get("bbox_label_id") or raw.get("source_detection_id") or "").strip()
        anchor = anchors.get(anchor_id, {})
        output_fields.append(
            {
                "field_id": field_id,
                "label": label,
                "bbox_label_id": anchor_id or field_id,
                "source_detection_id": anchor_id or field_id,
                "source_text": str(anchor.get("text") or raw.get("source_text") or label),
                "value_type": str(raw.get("value_type") or "free_text.short"),
                "generator": str(raw.get("generator") or raw.get("value_type") or "free_text.short"),
                "style_class": str(raw.get("style_class") or DEFAULT_STYLE_CLASS),
                "render_policy": _normalize_render_policy(raw.get("render_policy")),
                "export": {"json_path": str(raw.get("json_path") or field_id), "csv_column": str(raw.get("csv_column") or raw.get("json_path") or field_id)},
                "required": bool(raw.get("required", True)),
                "notes": str(raw.get("notes") or ""),
            }
        )
    return {
        "schema_version": AUTHORING_SCHEMA_VERSION,
        "created_at": _now(),
        "doc_id": doc_id or semantic_schema.get("doc_id"),
        "title": title or semantic_schema.get("title"),
        "source_review": source_review or semantic_schema.get("source_review"),
        "source_image": source_image or semantic_schema.get("source_image"),
        "source_inpainted": source_inpainted or semantic_schema.get("source_inpainted") or source_image or semantic_schema.get("source_image"),
        "image": (anchor_map or {}).get("image") or semantic_schema.get("image") or {},
        "bbox_source": {"canonical": "review", "review_path": source_review or semantic_schema.get("source_review")},
        "anchor_map_ref": (anchor_map or {}).get("source_review"),
        "fields": output_fields,
        "groups": semantic_schema.get("groups") if isinstance(semantic_schema.get("groups"), list) else [],
    }


def authoring_library_payload(library_root: Path) -> dict[str, Any]:
    library_root.mkdir(parents=True, exist_ok=True)
    index_path = library_root / "index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            index = {}
    else:
        index = {}
    approvals = index.get("approvals") if isinstance(index.get("approvals"), list) else []
    value_pools = index.get("value_pools") if isinstance(index.get("value_pools"), dict) else DEFAULT_VALUE_POOLS
    profile_types = index.get("profile_types") if isinstance(index.get("profile_types"), list) else DEFAULT_FAKER_PROFILE_TYPES
    payload = {
        "schema_version": AUTHORING_SCHEMA_VERSION,
        "library_root": str(library_root),
        "profile_types": profile_types,
        "value_pools": value_pools,
        "approvals": approvals,
        "summary": {"profileTypeCount": len(profile_types), "valuePoolCount": len(value_pools), "approvalCount": len(approvals)},
    }
    if not index_path.exists():
        _write_json(index_path, {k: payload[k] for k in ("schema_version", "profile_types", "value_pools", "approvals")})
    return payload


def approve_authoring_draft_to_library(request_path: Path, *, library_root: Path, note: str = "") -> dict[str, Any]:
    request_path = request_path.resolve()
    if not request_path.exists():
        raise FileNotFoundError(request_path)
    request_dir = request_path.parent
    request = _read_json(request_path)
    library_root.mkdir(parents=True, exist_ok=True)
    index_path = library_root / "index.json"
    current = authoring_library_payload(library_root)
    if index_path.exists():
        backup_dir = library_root / "backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_dir.mkdir(parents=True, exist_ok=True)
        (backup_dir / "index.json").write_text(index_path.read_text(encoding="utf-8"), encoding="utf-8")
    approval_id = f"approval_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    approval_dir = library_root / "approvals" / approval_id
    approval_dir.mkdir(parents=True, exist_ok=True)
    draft_names = [
        "schema_draft.json",
        "stylesheet_draft.json",
        "faker_profile_draft.json",
        "value_pool_draft.json",
        "research_report.json",
        "uncertainty_report.json",
        "anchor_map_draft.json",
        "application_notes.md",
    ]
    copied: list[dict[str, str]] = []
    missing: list[str] = []
    for name in draft_names:
        source = request_dir / name
        if not source.exists():
            missing.append(name)
            continue
        destination = approval_dir / name
        destination.write_bytes(source.read_bytes())
        copied.append({"name": name, "path": str(destination)})
    entry = {
        "id": approval_id,
        "docId": request.get("docId"),
        "title": request.get("title"),
        "request": str(request_path),
        "path": str(approval_dir),
        "copied": copied,
        "missing": missing,
        "note": note,
        "approved_at": _now(),
        "status": "approved_with_missing_drafts" if missing else "approved",
    }
    approvals = [entry, *current.get("approvals", [])]
    index = {
        "schema_version": AUTHORING_SCHEMA_VERSION,
        "profile_types": current.get("profile_types", DEFAULT_FAKER_PROFILE_TYPES),
        "value_pools": current.get("value_pools", DEFAULT_VALUE_POOLS),
        "approvals": approvals,
        "updated_at": _now(),
    }
    _write_json(index_path, index)
    return {"library": str(library_root), "index": str(index_path), "approval": entry, "summary": {"copied": len(copied), "missing": len(missing)}}
