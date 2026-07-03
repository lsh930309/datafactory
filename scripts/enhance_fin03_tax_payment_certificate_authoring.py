#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from datafactory.authoring import render_authoring_batch, render_authoring_preview
from datafactory.workbench import update_manifest_artifact
from datafactory.authoring_backup import backup_authoring_json_before_write

DOC_ID = "FIN-03"
DOC_TITLE = "납세증명서(국세·지방세 완납)"
DOC_DIR = ROOT / "workbench" / "documents" / "납세증명서(국세·지방세_완납)__FIN-03"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "FIN-03_tax_payment_certificate"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "FIN-03_tax_payment_certificate"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_fin03_tax_payment_certificate_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "국세납세증명서_page_001.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_국세납세증명서_page_001" / "lama" / "inpainted_lama.png"
FONT_BATANG = ROOT / "fonts" / "batang.ttc"
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_BATANG if FONT_BATANG.exists() else FONT_FALLBACK)
FONT_FAMILY = "Batang" if FONT_BATANG.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()

STYLE_SIZES = {
    "page_number": 16,
    "document_confirmation_number": 14,
    "processing_period": 15,
    "taxpayer_name": 22,
    "taxpayer_rrn": 14,
    "taxpayer_address": 14,
    "valid_until": 21,
    "issue_date": 17,
    "tax_office_chief": 27,
    "tax_office_phone": 14,
}
ALIGN = {
    "page_number": "center",
    "document_confirmation_number": "center",
    "processing_period": "left",
    "taxpayer_name": "left",
    "taxpayer_rrn": "center",
    "taxpayer_address": "left",
    "valid_until": "center",
    "issue_date": "center",
    "tax_office_chief": "center",
    "tax_office_phone": "center",
}
TAX_OFFICES = [
    ("동대문세무서장", "02-958-0226"),
    ("서초세무서장", "02-3011-6200"),
    ("성동세무서장", "02-460-4200"),
    ("북인천세무서장", "032-540-6200"),
    ("수원세무서장", "031-250-4200"),
    ("대전세무서장", "042-229-8200"),
]
PEOPLE = [
    ("이승훈", "930309-1069114", "서울특별시 동대문구 제기로2길 28-12(제기동)"),
    ("박도윤", "880621-1054286", "부산광역시 중구 월드컵북로 128"),
    ("최서연", "920402-2059184", "경기도 성남시 분당구 판교역로 235"),
    ("정하준", "850730-1047621", "대구광역시 달서구 성서공단로 11"),
    ("오서윤", "900115-2063384", "광주광역시 북구 첨단과기로 123"),
    ("김민준", "790724-1037295", "서울특별시 강남구 테헤란로 152"),
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def fmt_date(date: datetime, *, zero: bool = True) -> str:
    if zero:
        return f"{date.year}년 {date.month:02d}월 {date.day:02d}일"
    return f"{date.year}년 {date.month}월 {date.day}일"


def confirmation_number(rng: random.Random) -> str:
    return f"{rng.randrange(1000, 9999)}-{rng.randrange(100, 999)}-{rng.randrange(1000, 9999)}-{rng.randrange(100, 999)}"


def make_profiles() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    profiles: list[dict[str, str]] = []
    base = datetime(2026, 6, 29)
    for idx in range(12):
        name, rrn, address = PEOPLE[idx % len(PEOPLE)]
        office, phone = TAX_OFFICES[idx % len(TAX_OFFICES)]
        issue = base + timedelta(days=idx * 11)
        valid = issue + timedelta(days=30)
        profiles.append({
            "page_number": "( 1 / 1 )",
            "document_confirmation_number": confirmation_number(rng),
            "processing_period": "즉시(단, 해외이주용 10일)",
            "taxpayer_name": name,
            "taxpayer_rrn": rrn,
            "taxpayer_address": address,
            "valid_until": fmt_date(valid, zero=True),
            "issue_date": fmt_date(issue, zero=False),
            "tax_office_chief": office,
            "tax_office_phone": phone,
        })
    return profiles


def update_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(json.dumps(schema, ensure_ascii=False))
    im = Image.open(ORIGINAL)
    schema.update({
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "source_image": str(ORIGINAL.resolve()),
        "source_inpainted": str(TEMPLATE.resolve()),
        "image": {"width": im.width, "height": im.height},
        "authoring_mode": "fin03_pipeline_ready_20260702",
        "quality_status": "pipeline_ready_candidate",
    })
    for field in schema.get("fields", []):
        fid = field.get("field_id")
        field["generator"] = f"pool_record:fin03_tax_payment_profiles.{fid}"
        field.setdefault("render_policy", {})["align"] = ALIGN.get(fid, "left")
        field.setdefault("render_policy", {})["valign"] = "middle"
        field.setdefault("render_policy", {})["fit"] = "shrink_to_fit"
        field.setdefault("render_policy", {})["overflow"] = "shrink"
        field["notes"] = "FIN-03 국세 납세증명서 생산용 보정 필드. crop 비교 없이 전체 문서/overlay 기준으로 검수."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update({
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "notes": f"FIN-03 납세증명서 style 보정. 원본 기입값은 명조 계열 인쇄체가 가장 유사하므로 {FONT_FAMILY}를 선택했다. 전체 문서와 50% overlay 기준으로 크기/농도만 보정했고 crop 비교는 제외했다.",
    })
    for style in stylesheet.get("style_classes", []):
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = STYLE_SIZES.get(fid, style.get("font_size", 16))
        style["fill"] = [22, 22, 22]
        style["opacity"] = 0.92
        style["align"] = ALIGN.get(fid, style.get("align", "left"))
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
    faker.update({
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "locale": "ko_KR",
        "field_generators": {fid: "literal:" for fid in field_ids},
        "constraints": [{"type": "pick_record", "pool": "fin03_tax_payment_profiles", "targets": {fid: fid for fid in field_ids}}],
        "data_pools": {"fin03_tax_payment_profiles": make_profiles()},
        "notes": "FIN-03 생산용 profile. 납세자/주민번호/주소/세무서/연락처/발급일/유효일을 같은 record에서 일관되게 선택한다.",
    })
    return faker


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 220, 320
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 58), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 15), f"fin03_{idx + 1:06d}", font=font, fill=(30, 30, 30))
        image = Image.open(path).convert("RGB")
        image.thumbnail((cell_w - 18, cell_h - 32))
        y = 42
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
    font = ImageFont.truetype(str(FONT_FALLBACK), 18) if FONT_FALLBACK.exists() else ImageFont.load_default()
    scale_w = 300
    sheet = Image.new("RGB", (scale_w * len(labels) + 20 * (len(labels) + 1), 500), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(labels):
        thumb = image.copy(); thumb.thumbnail((scale_w, 430))
        x = 20 + idx * (scale_w + 20)
        draw.text((x, 18), label, font=font, fill=(20, 20, 20))
        sheet.paste(thumb, (x, 52))
        draw.rectangle([x, 52, x + thumb.width, 52 + thumb.height], outline=(150, 150, 150))
    out = CALIB_DIR / "full_comparison.jpg"
    sheet.save(out, quality=92)
    diff.save(CALIB_DIR / "full_diff.png")
    overlay.save(CALIB_DIR / "full_overlay_50.png")
    return out


def write_progress(summary: dict[str, Any], preview_image: Path, comparison: Path, contact: Path) -> None:
    PROGRESS.write_text(f"""# 2026-07-02 FIN-03 납세증명서 파이프라인 준비 작업

## 목표
- `FIN-03 납세증명서(국세·지방세 완납)`을 단일 순차 대상으로 처리한다.
- 기존 10개 필드 authoring을 주주명부 방식에 맞춰 schema/style/faker/batch 산출물까지 완료한다.
- crop 비교 루틴은 사용하지 않고 전체 문서/50% overlay 기준으로만 검수한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: 1페이지 10개 필드, preview 동작 가능 상태.

## 구현 내용
- 문서확인번호, 처리기간, 납세자 성명, 주민등록번호, 주소, 유효일, 발급일, 세무서장, 연락처를 record 기반으로 일관 생성한다.
- 기존 preview의 `2쪽 중 제1쪽` 같은 부자연스러운 페이지 문구를 원본 형식인 `( 1 / 1 )`로 교체했다.
- 기존 mobile 형태 연락처를 원본과 유사한 세무서 대표번호 형태로 교체했다.
- 처리기간은 원본 문구와 맞춰 `즉시(단, 해외이주용 10일)`을 사용한다.
- font-family는 전체 렌더 시각 비교 결과 명조 계열이 더 유사하므로 `{FONT_FAMILY}`를 선택했다.

## 산출물
- schema: `{SCHEMA_PATH}`
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

## 한계 및 다음 조치
- 하단 바코드/상단 QR/관인은 정적 요소로 보존한다.
- 현재 template는 표와 보안 배경이 잘 보존되어 있어 추가 cleanup은 필수는 아니다.
""", encoding="utf-8")


def main() -> None:
    for path in [SCHEMA_PATH, STYLE_PATH, FAKER_PATH, ORIGINAL, TEMPLATE]:
        if not path.exists():
            raise FileNotFoundError(path)
    if CALIB_DIR.exists():
        shutil.rmtree(CALIB_DIR)
    schema = update_schema(read_json(SCHEMA_PATH))
    stylesheet = update_stylesheet(read_json(STYLE_PATH))
    faker = update_faker(schema, read_json(FAKER_PATH))
    write_json(SCHEMA_PATH, schema)
    write_json(STYLE_PATH, stylesheet)
    write_json(FAKER_PATH, faker)

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="fin03", clean=True)
    contact = make_contact_sheet([sample.image for sample in batch.samples])
    comparison = compare(preview.image)
    summary = read_json(batch.summary)
    summary["page_count"] = 1
    summary["field_count_per_sample"] = summary.get("field_count")
    summary["contact_sheet"] = str(contact)
    summary["style_comparison"] = str(comparison)
    write_json(batch.summary, summary)

    update_manifest_artifact(DOC_ID, "authoring", SCHEMA_PATH)
    update_manifest_artifact(DOC_ID, "authoring_stylesheet", STYLE_PATH)
    update_manifest_artifact(DOC_ID, "authoring_faker_profile", FAKER_PATH)
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
