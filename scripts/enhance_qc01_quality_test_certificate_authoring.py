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

DOC_ID = "QC-01"
DOC_TITLE = "품질·시험성적서"
DOC_DIR = ROOT / "workbench" / "documents" / "품질·시험성적서__QC-01"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "QC-01_품질·시험성적서"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "QC-01_품질·시험성적서"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_qc01_quality_test_certificate_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "품질시험성적서.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_품질시험성적서" / "lama" / "inpainted_lama.png"

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
    if field_id in {
        "sample_name_country", "sampling_location", "intended_use", "project_name", "sampler_name", "ordering_client",
        "observer_name", "contractor_name", "manufacturer_name", "requester_name", "inventory_quantity",
        "national_critical_facility_status", "office_phone", "office_fax", "office_address",
    }:
        return "left"
    if field_id.endswith("_test_method") or field_id.endswith("_responsible_qualification") or field_id.endswith("_responsible_cert_number"):
        return "center"
    return "center"


def font_size_for(field_id: str, existing: int | None = None) -> int:
    if field_id in {"sample_name_country"}:
        return 30
    if field_id in {"receipt_number", "receipt_date_text", "sampling_date_text"}:
        return 32
    if field_id in {"sampling_location", "intended_use"}:
        return 34
    if field_id in {"project_name", "ordering_client", "observer_name", "contractor_name", "inventory_quantity", "national_critical_facility_status"}:
        return 25
    if field_id in {"sampler_name", "manufacturer_name", "requester_name"}:
        return 29
    if field_id.startswith("section_1_") or field_id.startswith("section_2_"):
        if field_id.endswith("_number"):
            return 30
        if "diameter" in field_id or field_id.endswith("_length"):
            return 30
        if field_id.endswith("_test_item_name") or field_id.endswith("_inner_label") or field_id.endswith("_outer_label") or field_id.endswith("_length_label"):
            return 28
        if field_id.endswith("_test_method"):
            return 25
        if field_id.endswith("_responsible_qualification") or field_id.endswith("_responsible_cert_number"):
            return 22
        if field_id.endswith("_engineer_name") or field_id.endswith("_examiner_name"):
            return 23
        if field_id.endswith("_signature"):
            return 25
    if field_id == "issue_date_text":
        return 31
    if field_id == "representative_title_name":
        return 33
    if field_id in {"office_phone", "office_fax", "office_address"}:
        return 22
    if field_id == "page_indicator":
        return 27
    return existing or 28


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
            "authoring_mode": "qc01_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:qc01_quality_test_profiles.{fid}"
        policy = field.setdefault("render_policy", {})
        policy["align"] = align_for(fid)
        policy["valign"] = "middle"
        policy["fit"] = "shrink_to_fit"
        policy["overflow"] = "shrink"
        field["notes"] = "QC-01 품질·시험성적서 생산용 보정 필드. 접수/채취/시료/치수시험 결과를 하나의 record에서 일관 생성한다."
    return schema


def update_stylesheet(stylesheet: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"QC-01 품질·시험성적서 style 보정. 스캔된 KICQ 성적서의 고딕 계열 인쇄체와 전체 렌더링 결과를 기준으로 {FONT_FAMILY}를 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다.",
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
        style["fill"] = [28, 28, 28]
        style["opacity"] = 0.90
        style["align"] = align_for(fid)
        style["valign"] = "middle"
        style["line_spacing"] = 1.0
        style["letter_spacing"] = 0.0
        style["baseline_shift"] = 0
        style["overflow"] = "shrink"
        style["confidence"] = 0.85
    return stylesheet


def update_faker(schema: dict[str, Any], faker: dict[str, Any]) -> dict[str, Any]:
    faker = json.loads(json.dumps(faker, ensure_ascii=False))
    field_ids = [field["field_id"] for field in schema.get("fields", [])]
    old_pools = faker.get("data_pools") or {}
    records = old_pools.get("qc01_quality_test_profiles")
    if not isinstance(records, list) or not records:
        raise ValueError("qc01_quality_test_profiles pool is missing")
    records = sanitize_records(records)
    faker.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "locale": "ko_KR",
            "field_generators": {fid: "literal:" for fid in field_ids},
            "constraints": [
                {"type": "pick_record", "pool": "qc01_quality_test_profiles", "targets": {fid: fid for fid in field_ids}}
            ],
            "data_pools": {"qc01_quality_test_profiles": records},
            "notes": "QC-01 생산용 profile. 기존 수동 authoring의 quality_test record pool을 보존하고, 시료/접수/채취/치수시험 결과/시험자/발행정보를 하나의 record에서 선택한다.",
        }
    )
    return faker


def sanitize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cutoff = date(2026, 7, 2)
    start = date(2023, 1, 3)
    sanitized: list[dict[str, Any]] = []
    for idx, record in enumerate(records):
        new_record = json.loads(json.dumps(record, ensure_ascii=False))
        receipt = _parse_date_text(str(new_record.get("receipt_date_text", "")))
        sampling = _parse_date_text(str(new_record.get("sampling_date_text", "")))
        issue = _parse_date_text(str(new_record.get("issue_date_text", "")))
        if receipt is None or receipt > cutoff:
            receipt = start + timedelta(days=(idx * 19) % 1180)
        if receipt > cutoff:
            receipt = cutoff - timedelta(days=idx % 11)
        if sampling is None or sampling > receipt:
            sampling = receipt - timedelta(days=1 + (idx % 3))
        if issue is None or issue < receipt or issue > cutoff:
            issue = receipt + timedelta(days=5 + (idx % 6))
        if issue > cutoff:
            issue = cutoff - timedelta(days=idx % 7)
        if sampling > receipt:
            sampling = receipt - timedelta(days=1)
        if receipt > issue:
            receipt = issue - timedelta(days=3)
            sampling = receipt - timedelta(days=1)
        new_record["receipt_date_text"] = f"{receipt:%Y. %m. %d.}"
        new_record["sampling_date_text"] = f"{sampling:%Y. %m. %d.}"
        new_record["issue_date_text"] = f"{issue.year}년 {issue.month:02d}월 {issue.day:02d}일"
        # The certificate template already prints the title "대표"; render only the person name.
        new_record["representative_title_name"] = re.sub(r"^\s*대표\s+", "", str(new_record.get("representative_title_name") or "")).strip()
        observer_names = ["김민준", "이서준", "박도윤", "최예준", "정시우", "강하준", "조주원", "윤지호", "장지후", "임준우", "한서연", "오서윤", "서지우", "신서현", "권민서", "김하은", "이하윤", "박윤서", "최지유", "정지민"]
        observer_prefixes = ["감리단", "품질관리팀", "현장대리인", "발주처", "검수담당", "시험입회자", "시공사 품질팀", "공장검사원"]
        if str(new_record.get("observer_name") or "").strip() in {"", "-", "_"}:
            new_record["observer_name"] = f"{observer_prefixes[idx % len(observer_prefixes)]} {observer_names[(idx * 3 + 5) % len(observer_names)]}"
        if str(new_record.get("inventory_quantity") or "").strip() in {"", "-", "_"}:
            units = ["EA", "PCS", "본", "개", "SET"]
            new_record["inventory_quantity"] = f"{18 + ((idx * 7) % 83)} {units[idx % len(units)]}"
        sanitized.append(new_record)
    return sanitized


def _parse_date_text(value: str) -> date | None:
    for pattern in [r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.", r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일"]:
        m = re.search(pattern, value)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                return None
    return None


def build_semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    field_mapping = {
        str(field["field_id"]): field.get("export", {}).get("json_path", field["field_id"])
        for field in schema.get("fields", [])
    }
    result_row = {
        "연번": "",
        "시험·검사종목": "",
        "시험·검사방법": "",
        "시험·검사결과": {},
        "책임기술인": {
            "자격종목 및 자격증번호": "",
            "성명": "",
            "서명": "",
        },
        "시험·검사자": {
            "성명": "",
            "서명": "",
        },
    }
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "purpose": "렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조",
        "semantic_schema": {
            "품질·시험성적서": {
                "시료 정보": {
                    "시료명": "",
                    "시료 채취 장소": "",
                    "성과 이용 목적": "",
                    "공사명": "",
                    "발주자": "",
                    "시공자": "",
                    "의뢰인": "",
                    "국가중요시설여부": "",
                },
                "접수 및 채취": {
                    "접수번호": "",
                    "접수일자": "",
                    "채취일": "",
                    "채취자": "",
                    "참관자": "",
                    "생산자": "",
                    "재고량": "",
                },
                "시험·검사 결과": [result_row],
                "발행 정보": {
                    "발행일": "",
                    "대표자": "",
                    "전화번호": "",
                    "팩스": "",
                    "주소": "",
                    "쪽번호": "",
                },
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "schema.json은 renderer 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 품질·시험성적서의 KIE label 구조만 계층형으로 표현한다.",
            "시험·검사 결과는 실제 렌더링에서 section 2개로 생성되지만 의미 schema에서는 반복 row 구조로 표현한다.",
        ],
    }


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT), 14) if Path(FONT).exists() else ImageFont.load_default()
    cell_w, cell_h = 150, 235
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 52), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 12), f"qc01_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
    PROGRESS.write_text(f"""# 2026-07-02 QC-01 품질·시험성적서 파이프라인 준비 작업

## 목표
- `QC-01 품질·시험성적서`를 단일 순차 대상으로 처리한다.
- 기존 수동 1-cycle 결과를 pipeline-ready 산출 체계로 승격한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: 1페이지 60개 필드. 시료/접수/채취/공사/의뢰/시험결과 2개 section/발행정보까지 bbox와 record pool이 준비되어 있었다.

## 구현 내용
- font-family는 스캔 성적서의 고딕 계열 인쇄체 시각 정보에 맞춰 `{FONT_FAMILY}`로 지정했다.
- 기존 `qc01_quality_test_profiles` record pool을 보존하고 모든 필드를 같은 record에서 선택하도록 `pick_record` constraint를 고정했다.
- D19/D22/D25 및 D29/D32 치수 결과는 record 내부에서 제품 규격별로 함께 이동하도록 유지했다.
- 원본 scan 대비 렌더 값이 과도하게 진해 보이지 않도록 opacity를 0.90으로 낮췄고, 대표/시험자/연락처 등 하단 필드도 같은 문서 질감에 맞췄다.

## 산출물
- script: `{ROOT / 'scripts' / 'enhance_qc01_quality_test_certificate_authoring.py'}`
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
- 원본의 손글씨 서명 질감은 현재 텍스트 렌더로 대체한다. 필요 시 서명 이미지/필기체 모듈을 별도로 붙일 수 있다.
- 현재는 성적서 1페이지 기준이다. 2페이지 시험 상세가 필요한 경우 별도 page template이 필요하다.
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
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="qc01", clean=True)
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
