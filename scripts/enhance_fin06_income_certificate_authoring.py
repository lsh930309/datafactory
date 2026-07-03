#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from datafactory.authoring import render_authoring_batch, render_authoring_preview
from datafactory.workbench import update_manifest_artifact
from datafactory.authoring_backup import backup_authoring_json_before_write

DOC_ID = "FIN-06"
DOC_TITLE = "소득금액증명원"
DOC_DIR = ROOT / "workbench" / "documents" / "소득금액증명원__FIN-06"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "FIN-06_income_certificate"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "FIN-06_income_certificate"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_fin06_income_certificate_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "EgovPageLink.do_page_001.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_EgovPageLink.do_page_001" / "lama" / "inpainted_lama.png"

FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()

PEOPLE = [
    ("이승훈", "남", "1993-03-09", "서울특별시 동대문구 제기로22길 28-12(제기동)", "한국딥러닝 주식회사", "368-81-01409"),
    ("김서윤", "여", "1989-11-24", "경기도 성남시 분당구 정자일로 95", "주식회사 에이치비테크", "214-86-39217"),
    ("박도윤", "남", "1991-07-18", "인천광역시 연수구 송도과학로 32", "비전모빌리티 주식회사", "120-87-54109"),
    ("최하린", "여", "1995-02-03", "부산광역시 해운대구 센텀중앙로 48", "뉴웨이브솔루션 주식회사", "617-88-10452"),
    ("정민재", "남", "1986-12-15", "대전광역시 유성구 대학로 99", "케이엠바이오 주식회사", "305-86-77231"),
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def krw(value: int) -> str:
    return f"{value:,}"


def rrn(date_s: str, gender: str, rng: random.Random) -> str:
    yy, mm, dd = date_s[2:4], date_s[5:7], date_s[8:10]
    century_digit = "1" if gender == "남" else "2"
    if int(date_s[:4]) >= 2000:
        century_digit = "3" if gender == "남" else "4"
    return f"{yy}{mm}{dd}-{century_digit}{rng.randrange(100000, 999999)}"


def style_size(field_id: str) -> int:
    if field_id == "page_number":
        return 23
    if field_id == "document_confirmation_number":
        return 16
    if field_id == "income_year":
        return 24
    if field_id in {"taxpayer_name", "taxpayer_address"}:
        return 19
    if field_id == "taxpayer_rrn":
        return 17
    if field_id in {"business_registration_number"}:
        return 17
    if field_id.startswith(("revenue_amount", "income_amount")):
        return 18
    if field_id.startswith("tax_amount"):
        return 17
    if field_id.startswith("income_type"):
        return 16
    return 18


def align_for(field_id: str) -> str:
    if field_id.startswith(("revenue_amount", "income_amount", "tax_amount")):
        return "right"
    if field_id in {"page_number", "document_confirmation_number", "income_year", "taxpayer_rrn", "business_registration_number"}:
        return "center"
    return "left"


def make_records() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    records: list[dict[str, str]] = []
    for idx in range(12):
        name, gender, birth, address, company, brn = PEOPLE[idx % len(PEOPLE)]
        year = 2023 + (idx % 3)
        gross = [11000000, 18450000, 25780000, 39200000, 51600000, 72500000][idx % 6] + (idx // 6) * 1350000
        income = int(gross * [0.46, 0.52, 0.58, 0.63][idx % 4])
        # 원본 bbox의 총결정세액 칸은 한 자리 숫자 폭으로 잡혀 있어 원본과 동일하게 0 중심으로 생성한다.
        tax = 0
        second_gross = 0 if idx % 3 else int(gross * 0.12)
        second_income = 0 if idx % 3 else int(second_gross * 0.55)
        second_tax = 0
        records.append(
            {
                "page_number": "( 1 / 11 )",
                "document_confirmation_number": f"{rng.randrange(1000,9999)}-{rng.randrange(1000,9999)}-{rng.randrange(1000,9999)}-{rng.randrange(1000,9999)}",
                "income_year": f"({year}년 귀속)",
                "taxpayer_name": name,
                "taxpayer_rrn": rrn(birth, gender, rng),
                "taxpayer_address": address,
                "business_registration_number": brn,
                "revenue_amount_1": krw(gross),
                "income_amount_1": krw(income),
                "tax_amount_1": krw(tax),
                "income_type_1": " (연말정산)",
                "revenue_amount_2": krw(second_gross) if second_gross else "",
                "income_amount_2": krw(second_income) if second_income else "",
                "tax_amount_2": krw(second_tax) if second_tax else "",
            }
        )
    return records


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
            "authoring_mode": "fin06_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:fin06_income_records.{fid}"
        if fid == "income_type_1":
            # 기존 OCR bbox가 총결정세액 칸과 너무 붙어 있어 비고 열 내부로 시작점을 보정한다.
            field["bbox"] = [990, 729, 79, 27]
        field.setdefault("render_policy", {})["align"] = align_for(fid)
        field.setdefault("render_policy", {})["valign"] = "middle"
        field.setdefault("render_policy", {})["fit"] = "shrink_to_fit"
        field.setdefault("render_policy", {})["overflow"] = "shrink"
        field["notes"] = "FIN-06 소득금액증명원 생산용 보정 필드. 개인정보/소득금액/세액을 record 기반으로 일관 생성."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"FIN-06 소득금액증명원 style 보정. 정부24/Hometax 계열 산세리프 인쇄체와 전체 렌더링 결과를 기준으로 {FONT_FAMILY}를 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다.",
        }
    )
    for style in stylesheet.get("style_classes", []):
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = style_size(fid)
        style["fill"] = [18, 18, 18]
        style["opacity"] = 0.93
        style["align"] = align_for(fid)
        style["valign"] = "middle"
        style["line_spacing"] = 1.0
        style["letter_spacing"] = 0.0
        style["baseline_shift"] = 0
        style["overflow"] = "shrink"
        style["confidence"] = 0.84
    return stylesheet


def update_faker(schema: dict[str, Any], faker: dict[str, Any]) -> dict[str, Any]:
    field_ids = [field["field_id"] for field in schema.get("fields", [])]
    faker = json.loads(json.dumps(faker, ensure_ascii=False))
    faker.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "locale": "ko_KR",
            "field_generators": {fid: "literal:" for fid in field_ids},
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "fin06_income_records",
                    "targets": {fid: fid for fid in field_ids},
                }
            ],
            "data_pools": {"fin06_income_records": make_records()},
            "notes": "FIN-06 생산용 profile. 납세자 인적사항, 사업자등록번호, 수입금액, 소득금액, 총결정세액을 하나의 record로 일관 생성한다.",
        }
    )
    return faker


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 180, 250
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 58), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 15), f"fin06_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
    scale_w = 220
    sheet = Image.new("RGB", (scale_w * len(labels) + 18 * (len(labels) + 1), 390), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(labels):
        thumb = image.copy()
        thumb.thumbnail((scale_w, 330))
        x = 18 + idx * (scale_w + 18)
        draw.text((x, 16), label, font=font, fill=(20, 20, 20))
        sheet.paste(thumb, (x, 48))
        draw.rectangle([x, 48, x + thumb.width, 48 + thumb.height], outline=(150, 150, 150))
    out = CALIB_DIR / "full_comparison.jpg"
    sheet.save(out, quality=92)
    diff.save(CALIB_DIR / "full_diff.png")
    overlay.save(CALIB_DIR / "full_overlay_50.png")
    return out


def write_progress(summary: dict[str, Any], preview_image: Path, comparison: Path, contact: Path) -> None:
    PROGRESS.write_text(
        f"""# 2026-07-02 FIN-06 소득금액증명원 파이프라인 준비 작업

## 목표
- `FIN-06 소득금액증명원`을 단일 순차 대상으로 처리한다.
- 기존 14개 bbox authoring을 유지하되, 인적사항/귀속연도/수입금액/소득금액/총결정세액을 record 기반으로 일관 생성한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: 1페이지 14개 필드, preview 동작 가능 상태.

## 구현 내용
- font-family는 정부24/Hometax 양식의 산세리프 인쇄체 시각 정보에 가장 가까운 `{FONT_FAMILY}`로 통일했다.
- 기존 독립 faker 규칙을 `fin06_income_records` 단일 record pool로 치환했다.
- 납세자 이름/주민등록번호/주소, 사업자등록번호, 수입금액, 소득금액, 총결정세액이 같은 record에서 생성된다.
- 금액 및 세액은 right, 문서번호/귀속연도/주민번호/사업자번호는 center, 주소/성명/소득구분은 left 정렬로 고정했다.

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
- 현재 authoring은 첫 페이지 기준이다. 원본 PDF에는 다수 페이지가 있으므로, 필요 시 후속 단계에서 페이지별 템플릿 확장이 필요하다.
- QR/바코드/정부24 보안 배경은 template 원본을 그대로 사용한다.
""",
        encoding="utf-8",
    )


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
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="fin06", clean=True)
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
