#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from datafactory.authoring import render_authoring_batch, render_authoring_preview
from datafactory.workbench import update_manifest_artifact
from datafactory.authoring_backup import backup_authoring_json_before_write

DOC_ID = "TRD-05"
DOC_TITLE = "수출입신고필증"
DOC_DIR = ROOT / "workbench" / "documents" / "수출입신고필증__TRD-05"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "TRD-05_수출입신고필증"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "TRD-05_수출입신고필증"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_trd05_export_declaration_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "수출신고필증.jpg"
TEMPLATE_SOURCE = DOC_DIR / "inpaint" / "original_수출신고필증" / "lama" / "inpainted_lama.png"
TEMPLATE = AUTHORING / "template_trd05_pipeline_ready.png"

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
    right = {"unit_price_usd", "amount_usd", "reported_price_fob", "total_reported_price_fob", "freight_krw", "insurance_krw"}
    if field_id in right:
        return "right"
    center = {"exporter_category", "destination_code", "export_type", "container_flag", "item_quantity", "net_weight", "total_gross_weight", "total_package_count", "period_start_date", "period_end_date", "loading_due_date", "acceptance_date"}
    if field_id in center:
        return "center"
    return "left"


def font_size_for(field_id: str, existing: int | None = None) -> int:
    if field_id in {"settlement_exchange_rate", "usd_exchange_rate"}:
        return 15
    if field_id in {"issue_number", "declaration_number", "declaration_date", "declaration_type_name"}:
        return 15
    if field_id in {"customs_broker_office", "customs_broker_name"}:
        return 14
    if field_id in {"exporter_trade_code_top", "exporter_trade_code", "manufacturer_trade_code", "buyer_code", "exporter_business_registration_number"}:
        return 14
    if field_id in {"exporter_address", "goods_location_address"}:
        return 13
    if field_id in {"goods_name", "trade_goods_name", "model_specification"}:
        return 16
    if field_id in {"unit_price_usd", "amount_usd", "reported_price_fob", "total_reported_price_fob", "payment_amount_text"}:
        return 13
    if field_id in {"freight_krw", "insurance_krw"}:
        return 14
    if field_id in {"customs_chief_name", "customs_officer_name"}:
        return 14
    if field_id in {"period_start_date", "period_end_date", "loading_due_date", "acceptance_date"}:
        return 13
    return min(existing or 15, 16)


def prepare_template(schema: dict[str, Any]) -> None:
    """Remove LaMa ghost text in dynamic value bboxes while preserving the scanned form."""
    image = Image.open(TEMPLATE_SOURCE).convert("RGB")
    draw = ImageDraw.Draw(image)
    w, h = image.size
    for field in schema.get("fields", []):
        x, y, bw, bh = [int(v) for v in field.get("bbox", [0, 0, 0, 0])]
        pad = 2
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
        if x1 <= x0 or y1 <= y0:
            continue
        # Dynamic value cells are mostly light blue. Median fill removes residual text better than mean.
        crop = image.crop((x0, y0, x1, y1))
        stat = ImageStat.Stat(crop)
        color = tuple(int(c) for c in stat.median)
        # Avoid dark medians on tiny cells by falling back to nearby document blue.
        if sum(color) < 470:
            color = (210, 223, 243)
        draw.rectangle((x0, y0, x1, y1), fill=color)
    TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    image.save(TEMPLATE)


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
            "authoring_mode": "trd05_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:trd05_export_declaration_profiles.{fid}"
        policy = field.setdefault("render_policy", {})
        policy["align"] = align_for(fid)
        policy["valign"] = "middle"
        policy["fit"] = "shrink_to_fit"
        policy["overflow"] = "shrink"
        field["notes"] = "TRD-05 수출신고필증 생산용 보정 필드. 신고번호/수출자/제조자/구매자/품목/금액/중량/수리일자를 하나의 record에서 일관 생성한다."
    return schema


def update_stylesheet(stylesheet: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"TRD-05 수출신고필증 style 보정. 스캔된 관세 서식의 작은 고딕/전산 출력체와 전체 렌더링 결과를 기준으로 {FONT_FAMILY}를 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다.",
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
        existing = style.get("font_size") if isinstance(style.get("font_size"), int) else None
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = font_size_for(fid, existing)
        style["fill"] = [20, 20, 20]
        style["opacity"] = 0.88
        style["align"] = align_for(fid)
        style["valign"] = "middle"
        style["line_spacing"] = 1.0
        style["letter_spacing"] = 0.0
        style["baseline_shift"] = 0
        style["overflow"] = "shrink"
        style["confidence"] = 0.82
    return stylesheet


def update_faker(schema: dict[str, Any], faker: dict[str, Any]) -> dict[str, Any]:
    faker = json.loads(json.dumps(faker, ensure_ascii=False))
    field_ids = [field["field_id"] for field in schema.get("fields", [])]
    records = (faker.get("data_pools") or {}).get("trd05_export_declaration_profiles")
    if not isinstance(records, list) or not records:
        raise ValueError("trd05_export_declaration_profiles pool is missing")
    records = sanitize_records(records)
    faker.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "locale": "ko_KR",
            "field_generators": {fid: "literal:" for fid in field_ids},
            "constraints": [
                {"type": "pick_record", "pool": "trd05_export_declaration_profiles", "targets": {fid: fid for fid in field_ids}}
            ],
            "data_pools": {"trd05_export_declaration_profiles": records},
            "notes": "TRD-05 생산용 profile. 기존 수동 authoring의 export_declaration record pool을 보존하고 신고번호, 일자, 수출자/제조자/구매자, 품목, 금액, 중량, 운임/보험료, 수리일자를 하나의 record에서 선택한다.",
        }
    )
    return faker


def sanitize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cutoff = date(2026, 7, 2)
    start = date(2023, 1, 2)
    sanitized: list[dict[str, Any]] = []
    for idx, record in enumerate(records):
        new_record = json.loads(json.dumps(record, ensure_ascii=False))
        declaration = _parse_date(str(new_record.get("declaration_date", "")))
        if declaration is None or declaration > cutoff:
            declaration = start + timedelta(days=(idx * 23) % 1210)
        if declaration > cutoff:
            declaration = cutoff - timedelta(days=idx % 13)
        inspection = declaration
        acceptance = declaration
        loading_due = declaration + timedelta(days=30)
        if loading_due > cutoff:
            loading_due = cutoff - timedelta(days=idx % 7)
            acceptance = min(acceptance, loading_due)
            inspection = min(inspection, loading_due)
        new_record["declaration_date"] = f"{declaration:%Y-%m-%d}"
        new_record["inspection_due_date"] = f"{inspection:%Y/%m/%d}"
        new_record["acceptance_date"] = f"{acceptance:%Y/%m/%d}"
        new_record["loading_due_date"] = f"{loading_due:%Y/%m/%d}"
        # 제출번호는 원본 관세서식의 `11298-YY-XXXXXXX` 형태를 유지한다.
        new_record["issue_number"] = f"11298-{declaration:%y}-{201665 + idx:07d}"
        declaration_number = str(new_record.get("declaration_number", ""))
        new_record["declaration_number"] = re.sub(
            r"(\d{3}-)\d{2}(-)",
            rf"\g<1>{declaration:%y}\2",
            declaration_number,
        ) if declaration_number else f"150-{declaration:%y}-{idx:02d}-{500000 + idx:06d}"
        sanitized.append(new_record)
    return sanitized


def _parse_date(value: str) -> date | None:
    match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", value)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def build_semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    field_mapping = {
        str(field["field_id"]): field.get("export", {}).get("json_path", field["field_id"])
        for field in schema.get("fields", [])
    }
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "purpose": "렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조",
        "semantic_schema": {
            "수출입신고필증": {
                "신고 기본정보": {
                    "결재환율": "",
                    "USD환율": "",
                    "제출번호": "",
                    "신고번호": "",
                    "신고일자": "",
                    "신고구분": "",
                    "거래구분": "",
                    "종류": "",
                    "결제방법": "",
                },
                "신고인": {
                    "관세사무소": "",
                    "관세사명": "",
                },
                "수출자 및 제조자": {
                    "수출대행자": {"상호": "", "통관고유부호": "", "구분": ""},
                    "수출화주": {
                        "상호": "",
                        "통관고유부호": "",
                        "주소": "",
                        "대표자": "",
                        "소재지": "",
                        "사업자등록번호": "",
                    },
                    "제조자": {
                        "상호": "",
                        "통관고유부호": "",
                        "제조장소": "",
                        "산업단지부호": "",
                    },
                    "구매자": {"상호": "", "구매자부호": ""},
                },
                "운송 및 적재": {
                    "목적국": {"코드": "", "국가명": ""},
                    "적재항": "",
                    "선박회사": "",
                    "검사희망일": "",
                    "운송형태": "",
                    "물품소재지": {"코드": "", "주소": ""},
                    "컨테이너 여부": "",
                    "운송기간": {"시작": "", "종료": ""},
                    "적재의무기한": "",
                },
                "환급": {
                    "환급신청인": "",
                    "간이환급": "",
                },
                "품목": {
                    "품목 총란수": "",
                    "품명": "",
                    "거래품명": "",
                    "모델규격": "",
                    "수량": "",
                    "단가 USD": "",
                    "금액 USD": "",
                    "세번부호": "",
                    "순중량": "",
                    "수량 공란표기": "",
                    "신고가격 FOB": "",
                    "수출품장부호": "",
                    "포장갯수 종류": "",
                    "수출요건확인 번호": "",
                    "발급서류명": "",
                },
                "합계 및 비용": {
                    "총중량": "",
                    "총포장갯수": "",
                    "총신고가격 FOB": "",
                    "운임 원화": "",
                    "보험료 원화": "",
                    "결제금액": "",
                },
                "신고수리": {
                    "세관장": "",
                    "관세사": "",
                    "신고수리일자": "",
                },
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "schema.json은 renderer 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 수출입신고필증의 KIE label 구조만 계층형으로 표현한다.",
            "현재 sample은 수출신고필증 1페이지 양식 기준이다.",
        ],
    }


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT), 14) if Path(FONT).exists() else ImageFont.load_default()
    cell_w, cell_h = 150, 225
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 52), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 12), f"trd05_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
    scale_w = 160
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
    PROGRESS.write_text(f"""# 2026-07-02 TRD-05 수출입신고필증 파이프라인 준비 작업

## 목표
- `TRD-05 수출입신고필증`을 단일 순차 대상으로 처리한다.
- 기존 수동 1-cycle 결과를 pipeline-ready 산출 체계로 승격한다.
- LaMa template에 남아 있던 원문 잔흔을 동적 bbox 기반 파생 템플릿으로 줄인다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa source template: `{TEMPLATE_SOURCE}`
- derived template: `{TEMPLATE}`
- 기존 authoring: 1페이지 64개 필드. 신고/수출자/제조자/구매자/품목/금액/중량/운임/수리일자 record pool이 준비되어 있었다.

## 구현 내용
- font-family는 관세 신고필증의 작은 고딕/전산 출력체 시각 정보에 맞춰 `{FONT_FAMILY}`로 지정했다.
- 기존 `trd05_export_declaration_profiles` record pool을 보존하고 모든 필드를 같은 record에서 선택하도록 `pick_record` constraint를 고정했다.
- 동적 value bbox 영역을 median background로 메우는 파생 템플릿을 생성해 기존 LaMa 잔흔을 줄였다.
- 금액 계열은 우측 정렬, 코드/중량/날짜 계열은 중앙 정렬, 나머지 사업자/주소/품목명 계열은 좌측 정렬로 고정했다.

## 산출물
- script: `{ROOT / 'scripts' / 'enhance_trd05_export_declaration_authoring.py'}`
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
- 파생 템플릿은 median fill 기반이므로 일부 칸의 배경 질감이 원본 스캔 질감과 완전히 같지는 않다.
- 관세 코드/금액의 실제 법적 유효성 검증은 후속 validation layer에서 강화해야 한다.
""", encoding="utf-8")


def main() -> None:
    for path in [SCHEMA_PATH, STYLE_PATH, FAKER_PATH, ORIGINAL, TEMPLATE_SOURCE]:
        if not path.exists():
            raise FileNotFoundError(path)
    if CALIB_DIR.exists():
        shutil.rmtree(CALIB_DIR)
    schema = update_schema(read_json(SCHEMA_PATH))
    prepare_template(schema)
    stylesheet = update_stylesheet(read_json(STYLE_PATH), schema)
    faker = update_faker(schema, read_json(FAKER_PATH))
    write_json(SCHEMA_PATH, schema)
    write_json(STYLE_PATH, stylesheet)
    write_json(FAKER_PATH, faker)
    semantic_schema = build_semantic_schema(schema)
    write_json(SEMANTIC_SCHEMA, semantic_schema)

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="trd05", clean=True)
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
