#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from datafactory.authoring import render_authoring_batch, render_authoring_preview
from datafactory.workbench import update_manifest_artifact
from datafactory.authoring_backup import backup_authoring_json_before_write

DOC_ID = "QC-02"
DOC_TITLE = "입고·검수 보고서"
DOC_DIR = ROOT / "workbench" / "documents" / "입고·검수_보고서__QC-02"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "QC-02_입고·검수 보고서"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "QC-02_입고·검수 보고서"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_qc02_incoming_inspection_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "검수보고서_page_001.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_검수보고서_page_001" / "lama" / "inpainted_lama.png"

FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_MALGUN = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_MALGUN)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "Malgun Gothic"
NOW = datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def align_for(field_id: str) -> str:
    if field_id in {"supplier_company_name", "inspection_manager_name", "receiving_location", "inspection_method", "inspector_opinion"}:
        return "left"
    if field_id.endswith("_item_name") or field_id.endswith("_specification") or field_id.endswith("_remark"):
        return "left"
    return "center"


def font_size_for(field_id: str) -> int:
    if field_id.startswith("approval_"):
        return 22
    if field_id in {"supplier_company_name", "purchase_order_number", "inspection_manager_name", "receiving_location"}:
        return 27
    if field_id in {"inspection_method"}:
        return 18
    if field_id in {"purchase_order_year", "purchase_order_month", "purchase_order_day", "receiving_year", "receiving_month", "receiving_day"}:
        return 16
    if field_id.endswith("_number"):
        return 18
    if field_id.endswith("_item_name"):
        return 17
    if field_id.endswith("_specification"):
        return 17
    if field_id.endswith("_received_quantity"):
        return 17
    if field_id.endswith("_quality_result") or field_id.endswith("_other_result"):
        return 18
    if field_id.endswith("_remark"):
        return 14
    if field_id == "inspector_opinion":
        return 16
    if field_id == "department_head_confirmation":
        return 34
    return 18


def bbox_overrides() -> dict[str, list[int]]:
    # 기존 수동 bbox는 표 구조에 잘 맞는다. 일부 큰 텍스트의 시각 균형만 bbox 여백을 조절한다.
    return {
        "supplier_company_name": [324, 273, 270, 39],
        "purchase_order_number": [800, 273, 270, 39],
        "inspection_manager_name": [324, 362, 205, 39],
        "receiving_location": [800, 362, 270, 39],
        "inspection_method": [324, 409, 745, 38],
        "inspector_opinion": [200, 1423, 742, 96],
        "department_head_confirmation": [948, 1450, 124, 78],
    }


def update_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(json.dumps(schema, ensure_ascii=False))
    im = Image.open(ORIGINAL)
    schema.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "title": DOC_TITLE,
            "source_image": str(ORIGINAL.resolve()),
            "source_inpainted": str(TEMPLATE.resolve()),
            "image": {"width": im.width, "height": im.height},
            "authoring_mode": "qc02_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    overrides = bbox_overrides()
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:qc02_incoming_inspection_profiles.{fid}"
        if fid in overrides:
            field["bbox"] = overrides[fid]
        policy = field.setdefault("render_policy", {})
        policy["align"] = align_for(fid)
        policy["valign"] = "middle"
        policy["fit"] = "shrink_to_fit"
        policy["overflow"] = "shrink"
        field["notes"] = "QC-02 입고·검수 보고서 생산용 보정 필드. 거래처/발주/입고/검수 품목 8행을 하나의 inspection record에서 일관 생성한다."
    return schema


def update_stylesheet(stylesheet: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"QC-02 입고·검수 보고서 style 보정. 빈 양식의 고딕 라벨/표 양식과 전체 렌더링 결과를 기준으로 {FONT_FAMILY}를 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다.",
        }
    )
    style_classes = stylesheet.setdefault("style_classes", [])
    by_class = {style.get("style_class"): style for style in style_classes}
    for field in schema.get("fields", []):
        style_class = field.get("style_class", f"style_{field['field_id']}")
        if style_class not in by_class:
            by_class[style_class] = {"style_class": style_class, "source_detection_ids": [field.get("source_detection_id", "manual")]} 
            style_classes.append(by_class[style_class])
    for style in style_classes:
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = font_size_for(fid)
        style["fill"] = [24, 24, 24]
        style["opacity"] = 0.92
        style["align"] = align_for(fid)
        style["valign"] = "middle"
        style["line_spacing"] = 1.0
        style["letter_spacing"] = 0.0
        style["baseline_shift"] = 0
        style["overflow"] = "shrink"
        style["confidence"] = 0.84
    return stylesheet


def update_faker(schema: dict[str, Any], faker: dict[str, Any]) -> dict[str, Any]:
    faker = json.loads(json.dumps(faker, ensure_ascii=False))
    field_ids = [field["field_id"] for field in schema.get("fields", [])]
    old_pools = faker.get("data_pools") or {}
    records = old_pools.get("qc02_inspection_profiles") or old_pools.get("qc02_incoming_inspection_profiles")
    if not isinstance(records, list) or not records:
        raise ValueError("qc02_inspection_profiles pool is missing")
    records = sanitize_records(records)
    # 기존 1-cycle에서 이미 수량/불량/합격 여부가 record 단위로 정합화되어 있으므로 그대로 보존한다.
    faker.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "locale": "ko_KR",
            "field_generators": {fid: "literal:" for fid in field_ids},
            "constraints": [
                {"type": "pick_record", "pool": "qc02_incoming_inspection_profiles", "targets": {fid: fid for fid in field_ids}}
            ],
            "data_pools": {"qc02_incoming_inspection_profiles": records},
            "notes": "QC-02 생산용 profile. 기존 수동 authoring의 검수 record pool을 보존하되, 모든 렌더 필드를 하나의 record에서 선택하도록 고정했다. 품목 8행의 수량/품질/기타/비고 값은 record 내부에서 정합성을 유지한다.",
        }
    )
    return faker


def sanitize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """기존 record 의미값은 유지하되 날짜는 현재 기준일 이전으로 고정한다."""

    cutoff = date(2026, 7, 2)
    start = date(2024, 1, 3)
    sanitized: list[dict[str, Any]] = []
    for idx, record in enumerate(records):
        new_record = json.loads(json.dumps(record, ensure_ascii=False))
        order = _read_date(new_record, "purchase_order")
        receiving = _read_date(new_record, "receiving")
        if order is None or order > cutoff:
            order = start + timedelta(days=(idx * 17) % 820)
        if receiving is None or receiving > cutoff or receiving < order:
            receiving = order + timedelta(days=3 + (idx % 5))
        if receiving > cutoff:
            receiving = cutoff - timedelta(days=idx % 9)
        if order > receiving:
            order = receiving - timedelta(days=3)
        _write_date(new_record, "purchase_order", order)
        _write_date(new_record, "receiving", receiving)
        po_number = str(new_record.get("purchase_order_number", ""))
        new_record["purchase_order_number"] = re.sub(
            r"PO-\d{8}-",
            f"PO-{order:%Y%m%d}-",
            po_number,
        ) if po_number else f"PO-{order:%Y%m%d}-{100 + idx:03d}"
        sanitized.append(new_record)
    return sanitized


def _read_date(record: dict[str, Any], prefix: str) -> date | None:
    try:
        return date(int(record[f"{prefix}_year"]), int(record[f"{prefix}_month"]), int(record[f"{prefix}_day"]))
    except (KeyError, TypeError, ValueError):
        return None


def _write_date(record: dict[str, Any], prefix: str, value: date) -> None:
    record[f"{prefix}_year"] = str(value.year)
    record[f"{prefix}_month"] = str(value.month)
    record[f"{prefix}_day"] = str(value.day)


def build_semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    field_mapping = {
        str(field["field_id"]): field.get("export", {}).get("json_path", field["field_id"])
        for field in schema.get("fields", [])
    }
    inspection_row = {
        "No": "",
        "품명": "",
        "규격": "",
        "수량": "",
        "품질 결과": "",
        "기타 결과": "",
        "비고": "",
    }
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "purpose": "렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조",
        "semantic_schema": {
            "입고·검수 보고서": {
                "결재": {
                    "담당": "",
                    "검토": "",
                    "승인": "",
                },
                "기본 정보": {
                    "거래처": "",
                    "발주번호": "",
                    "발주일자": {"연": "", "월": "", "일": ""},
                    "입고일자": {"연": "", "월": "", "일": ""},
                    "검수담당자": "",
                    "입고장소": "",
                    "검수방법": "",
                },
                "검수내역": [inspection_row],
                "검수 의견": "",
                "부서장 확인": "",
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "schema.json은 renderer 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 입고·검수 보고서의 KIE label 구조만 계층형으로 표현한다.",
            "검수내역은 실제 렌더링에서 8행으로 생성되지만 의미 schema에서는 반복 row 구조로 표현한다.",
        ],
    }


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT), 14) if Path(FONT).exists() else ImageFont.load_default()
    cell_w, cell_h = 160, 230
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 52), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 12), f"qc02_{idx + 1:06d}", font=font, fill=(30, 30, 30))
        image = Image.open(path).convert("RGB")
        image.thumbnail((cell_w - 16, cell_h - 28))
        y = 36
        sheet.paste(image, (x, y))
        draw.rectangle([x, y, x + image.width, y + image.height], outline=(150, 150, 150))
    out = BATCH_DIR / "contact_sheet.jpg"
    sheet.save(out, quality=92)
    return out


def compare(rendered: Path) -> Path:
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    original = Image.open(ORIGINAL).convert("RGB")
    template = Image.open(TEMPLATE).convert("RGB").resize(original.size)
    render = Image.open(rendered).convert("RGB").resize(original.size)
    diff = ImageChops.difference(template, render)
    diff_amp = diff.point(lambda v: min(255, v * 4))
    overlay = Image.blend(template, render, 0.5)
    labels = [("original", original), ("template", template), ("render", render), ("amplified diff", diff_amp), ("50% overlay", overlay)]
    font = ImageFont.truetype(str(FONT), 16) if Path(FONT).exists() else ImageFont.load_default()
    scale_w = 170
    sheet = Image.new("RGB", (scale_w * len(labels) + 14 * (len(labels) + 1), 300), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(labels):
        thumb = image.copy()
        thumb.thumbnail((scale_w, 240))
        x = 14 + idx * (scale_w + 14)
        draw.text((x, 12), label, font=font, fill=(20, 20, 20))
        sheet.paste(thumb, (x, 40))
        draw.rectangle([x, 40, x + thumb.width, 40 + thumb.height], outline=(150, 150, 150))
    out = CALIB_DIR / "full_comparison.jpg"
    sheet.save(out, quality=92)
    diff.save(CALIB_DIR / "full_diff.png")
    overlay.save(CALIB_DIR / "full_overlay_50.png")
    return out


def write_progress(summary: dict[str, Any], preview_image: Path, comparison: Path, contact: Path) -> None:
    PROGRESS.write_text(f"""# 2026-07-02 QC-02 입고·검수 보고서 파이프라인 준비 작업

## 목표
- `QC-02 입고·검수 보고서`를 단일 순차 대상으로 처리한다.
- 기존 수동 1-cycle 결과를 pipeline-ready 산출 체계로 승격한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: 1페이지 72개 필드. 거래처/발주/입고/검수담당/검수내역 8행/검수의견/부서장 확인까지 bbox와 faker pool이 준비되어 있었다.

## 구현 내용
- font-family는 원본 빈 양식의 고딕 계열 라벨/표 시각 정보에 맞춰 `{FONT_FAMILY}`로 지정했다.
- 기존 `qc02_inspection_profiles` record pool을 `qc02_incoming_inspection_profiles`로 승격하고, 모든 필드를 같은 record에서 선택하도록 `pick_record` constraint를 고정했다.
- 상단 거래처/발주번호/검수담당자/입고장소와 하단 부서장 확인 값은 과도하게 커 보이지 않도록 font-size와 bbox 여백을 보정했다.
- 8개 품목 행은 기존 수동 grid bbox를 유지하고, 품목명/규격/수량/품질/기타/비고의 row-level 정합성을 보존했다.

## 산출물
- script: `{ROOT / 'scripts' / 'enhance_qc02_incoming_inspection_authoring.py'}`
- schema: `{SCHEMA_PATH}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
- stylesheet: `{STYLE_PATH}`
- faker_profile: `{FAKER_PATH}`
- preview: `{preview_image}`
- batch summary: `{BATCH_DIR / 'summary.json'}`
- contact sheet: `{contact}`
- style comparison: `{comparison}`
- overlay: `{CALIB_DIR / 'full_overlay_50.png'}`

## 검수 결과
- 생성 수: {summary['count']}세트
- page_count: {summary.get('page_count')}
- field_count_per_sample: {summary.get('field_count_per_sample', summary.get('field_count'))}
- warning_count: {summary['warning_count']}
- semantic field mapping: {summary.get('semantic_field_mapping_count')}

## 한계 및 다음 조치
- 원본은 빈 양식이므로 실제 필기/전자서명 샘플과의 직접 값 비교 근거는 없다.
- 현재는 8행 내역 기준이다. 더 많은 품목 행을 채워야 하는 경우 추가 행 bbox와 pagination 정책을 별도 설계해야 한다.
""", encoding="utf-8")


def main() -> None:
    for path in [SCHEMA_PATH, STYLE_PATH, FAKER_PATH, ORIGINAL, TEMPLATE]:
        if not path.exists():
            raise FileNotFoundError(path)
    if CALIB_DIR.exists():
        shutil.rmtree(CALIB_DIR)
    schema = update_schema(read_json(SCHEMA_PATH))
    stylesheet = update_stylesheet(read_json(STYLE_PATH), schema)
    faker = update_faker(schema, read_json(FAKER_PATH))
    write_json(SCHEMA_PATH, schema)
    write_json(STYLE_PATH, stylesheet)
    write_json(FAKER_PATH, faker)
    semantic_schema = build_semantic_schema(schema)
    write_json(SEMANTIC_SCHEMA, semantic_schema)

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="qc02", clean=True)
    contact = make_contact_sheet([sample.image for sample in batch.samples])
    comparison = compare(preview.image)
    summary = read_json(batch.summary)
    summary["page_count"] = 1
    summary["field_count_per_sample"] = summary.get("field_count")
    summary["contact_sheet"] = str(contact)
    summary["style_comparison"] = str(comparison)
    summary["semantic_schema"] = str(SEMANTIC_SCHEMA)
    summary["semantic_field_mapping_count"] = len(semantic_schema["field_mapping"])
    write_json(batch.summary, summary)

    update_manifest_artifact(DOC_ID, "authoring", SCHEMA_PATH)
    update_manifest_artifact(DOC_ID, "authoring_stylesheet", STYLE_PATH)
    update_manifest_artifact(DOC_ID, "authoring_faker_profile", FAKER_PATH)
    update_manifest_artifact(DOC_ID, "authoring_semantic_schema", SEMANTIC_SCHEMA)
    update_manifest_artifact(DOC_ID, "authoring_preview", preview.image)
    update_manifest_artifact(DOC_ID, "authoring_overlay", preview.overlay)
    update_manifest_artifact(DOC_ID, "authoring_batch", batch.summary)
    update_manifest_artifact(DOC_ID, "authoring_contact_sheet", contact)
    update_manifest_artifact(DOC_ID, "authoring_style_comparison", comparison)

    write_progress(summary, preview.image, comparison, contact)
    print("preview", preview.image, "warnings", preview.warning_count)
    print("batch", batch.summary, "samples", batch.sample_count, "warnings", batch.warning_count)
    print("contact", contact)
    print("comparison", comparison)


if __name__ == "__main__":
    main()
