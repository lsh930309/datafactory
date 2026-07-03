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

DOC_ID = "FIN-05"
DOC_TITLE = "근로소득 원천징수영수증"
DOC_DIR = ROOT / "workbench" / "documents" / "근로소득_원천징수영수증__FIN-05"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "FIN-05_withholding_receipt"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "FIN-05_withholding_receipt"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_fin05_withholding_receipt_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "이승훈님_원천징수영수증(2023년)_page_001.jpg"
TEMPLATE_SOURCE = DOC_DIR / "inpaint" / "original_이승훈님_원천징수영수증(2023년)_page_001" / "lama" / "inpainted_lama.png"
TEMPLATE = AUTHORING / "template_fin05_pipeline_ready.png"

FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()

COMPANIES = [
    ("메가스터디교육(주)", "손성은", "780-87-00034", "서울특별시 서초구 효령로321 (서초동, 덕원빌딩)", "서초"),
    ("주식회사 세린테크", "김도현", "214-86-39217", "서울특별시 강남구 테헤란로 152", "삼성"),
    ("한빛솔루션 주식회사", "박재윤", "120-87-54109", "경기도 성남시 분당구 판교역로 235", "분당"),
    ("뉴웨이브모빌리티(주)", "정민재", "305-86-77231", "대전광역시 유성구 대학로 99", "대전"),
    ("대한정밀공업 주식회사", "이서준", "617-88-10452", "부산광역시 해운대구 센텀중앙로 48", "해운대"),
    ("비전바이오 주식회사", "최하린", "131-86-50741", "인천광역시 연수구 송도과학로 32", "인천"),
]

EMPLOYEES = [
    ("이승훈", "남", "1993-03-09"),
    ("김서윤", "여", "1989-11-24"),
    ("박도윤", "남", "1991-07-18"),
    ("최하린", "여", "1995-02-03"),
    ("정민재", "남", "1986-12-15"),
    ("윤하준", "남", "1997-05-27"),
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def krw(value: int) -> str:
    return f"{value:,}"


def rrn(birth: str, gender: str, rng: random.Random) -> str:
    yy, mm, dd = birth[2:4], birth[5:7], birth[8:10]
    century = "1" if gender == "남" else "2"
    if int(birth[:4]) >= 2000:
        century = "3" if gender == "남" else "4"
    return f"{yy}{mm}{dd}-{century}{rng.randrange(100000, 999999)}"


def style_size(field_id: str) -> int:
    # 원본은 산세리프 계열의 작고 옅은 인쇄체다. 전체 비교 결과 기준으로
    # 표 내부 값은 14~16px 중심, 하단 영수/세무서 영역은 17~19px로 맞춘다.
    if field_id in {"employer_name", "employer_representative_name", "employee_name", "employee_rrn"}:
        return 16
    if field_id in {"employer_address", "workplace_business_registration_number", "employment_period"}:
        return 12
    if field_id == "workplace_name":
        return 13
    if field_id.startswith(("gross_salary", "taxable_income")):
        return 15
    if field_id in {"income_tax_paid", "local_income_tax_paid", "income_tax_refund", "local_income_tax_refund"}:
        return 16
    if field_id.startswith("determined_") or field_id.startswith("tax_due_"):
        return 15
    if field_id == "receipt_date":
        return 15
    if field_id in {"withholding_agent_name", "tax_office_recipient"}:
        return 18
    if field_id == "employer_business_registration_number":
        return 15
    return 15


def align_for(field_id: str) -> str:
    if field_id.startswith(("gross_salary", "taxable_income", "income_tax", "local_income_tax", "determined_", "tax_due_")):
        return "right"
    if field_id in {"employer_business_registration_number", "employee_rrn", "workplace_name", "workplace_business_registration_number", "employment_period", "receipt_date", "withholding_agent_name", "tax_office_recipient"}:
        return "center"
    return "left"


def make_records() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    records: list[dict[str, str]] = []
    for idx in range(12):
        company, ceo, brn, address, office = COMPANIES[idx % len(COMPANIES)]
        emp_name, gender, birth = EMPLOYEES[idx % len(EMPLOYEES)]
        year = 2023 + (idx % 3)
        start_month = [1, 1, 3, 4, 1, 2][idx % 6]
        end_month = [7, 12, 12, 12, 10, 12][idx % 6]
        end_day = [7, 31, 31, 31, 30, 31][idx % 6]
        gross = [12_063_480, 18_720_000, 26_450_000, 34_800_000, 43_200_000, 51_600_000][idx % 6]
        gross += (idx // 6) * 1_850_000
        taxable = gross
        paid_income_tax = max(0, int(gross * [0.0098, 0.0135, 0.022, 0.031, 0.045, 0.058][idx % 6] // 10 * 10))
        paid_local_tax = int(paid_income_tax * 0.1 // 10 * 10)
        determined_income_tax = max(0, int(gross * [0.04, 0.055, 0.072, 0.088, 0.102, 0.118][idx % 6] // 10 * 10))
        determined_local_tax = int(determined_income_tax * 0.1 // 10 * 10)
        # 원천징수영수증에서는 75/77 라인이 기납부세액과 차감징수세액 사이에 회계적으로 대응한다.
        refund_income = paid_income_tax - determined_income_tax
        refund_local = paid_local_tax - determined_local_tax
        records.append(
            {
                "employer_name": company,
                "employer_representative_name": ceo,
                "employer_business_registration_number": brn,
                "employer_address": address,
                "employee_name": emp_name,
                "employee_rrn": rrn(birth, gender, rng),
                "workplace_name": company,
                "workplace_business_registration_number": brn,
                "employment_period": f"{year}.{start_month:02d}.01 ~ {year}.{end_month:02d}.{end_day:02d}",
                "gross_salary_current": krw(gross),
                "gross_salary_total": krw(gross),
                "taxable_income_current": krw(taxable),
                "taxable_income_total": krw(taxable),
                "income_tax_paid": krw(paid_income_tax),
                "local_income_tax_paid": krw(paid_local_tax),
                "income_tax_refund": krw(refund_income) if refund_income >= 0 else f"-{krw(abs(refund_income))}",
                "local_income_tax_refund": krw(refund_local) if refund_local >= 0 else f"-{krw(abs(refund_local))}",
                "determined_income_tax_current": krw(determined_income_tax),
                "determined_income_tax_total": krw(determined_income_tax),
                "determined_local_tax_current": krw(determined_local_tax),
                "determined_local_tax_total": krw(determined_local_tax),
                "receipt_date": f"{year} 년 {end_month:02d}월 {end_day:02d}일",
                "tax_due_income": krw(determined_income_tax),
                "tax_due_total": krw(determined_income_tax),
                "withholding_agent_name": company,
                "tax_office_recipient": f"{office}  세무서장  귀하",
            }
        )
    return records



def prepare_template() -> None:
    if not TEMPLATE_SOURCE.exists():
        raise FileNotFoundError(TEMPLATE_SOURCE)
    image = Image.open(TEMPLATE_SOURCE).convert("RGB")
    draw = ImageDraw.Draw(image)
    # 기존 inpaint 결과에 남아 있는 표 내부 정적 근무처명만 제거한다.
    # 선을 건드리지 않도록 텍스트 내부 영역만 옅은 셀 배경색으로 덮는다.
    draw.rectangle([334, 493, 480, 509], fill=(255, 255, 255))
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
            "authoring_mode": "fin05_pipeline_ready_20260702_page1",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    # 시각 검수 기준으로 긴 하단 문구는 원본과 동일한 위치 관계가 되도록 약간 넓힌다.
    bbox_overrides = {
        "withholding_agent_name": [788, 1468, 196, 26],
        "tax_office_recipient": [784, 1489, 212, 31],
        "employer_address": [384, 374, 346, 18],
    }

    existing_ids = {str(field["field_id"]) for field in schema.get("fields", [])}
    if "workplace_name" not in existing_ids:
        schema.setdefault("fields", []).append(
            {
                "field_id": "workplace_name",
                "label": "근무처명",
                "bbox": [334, 490, 146, 24],
                "bbox_format": "xywh",
                "source_detection_id": "manual_fin05_workplace_name",
                "source_text": "메가스터디교육(주)",
                "value_type": "company.name_ko",
                "generator": "pool_record:fin05_withholding_records.workplace_name",
                "style_class": "style_workplace_name",
                "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
                "export": {"json_path": "employment.workplace.name", "csv_column": "workplace_name"},
                "required": True,
                "notes": "기존 LaMa 템플릿에 정적으로 남아 있던 근무처명을 파생 템플릿에서 제거하고 동적 필드로 추가.",
            }
        )
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:fin05_withholding_records.{fid}"
        if fid in bbox_overrides:
            field["bbox"] = bbox_overrides[fid]
        policy = field.setdefault("render_policy", {})
        policy["align"] = align_for(fid)
        policy["valign"] = "middle"
        policy["fit"] = "shrink_to_fit"
        policy["overflow"] = "shrink"
        field["notes"] = "FIN-05 근로소득 원천징수영수증 1페이지 생산용 보정 필드. 회사/근로자/급여/세액 값을 record 기반으로 일관 생성."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"FIN-05 근로소득 원천징수영수증 style 보정. 원본의 국세청 서식 산세리프 인쇄체와 전체 렌더링 결과를 기준으로 {FONT_FAMILY}를 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다.",
        }
    )

    existing_style_ids = {str(style.get("style_class")) for style in stylesheet.get("style_classes", []) if isinstance(style, dict)}
    if "style_workplace_name" not in existing_style_ids:
        stylesheet.setdefault("style_classes", []).append({"style_class": "style_workplace_name"})
    for style in stylesheet.get("style_classes", []):
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = style_size(fid)
        style["fill"] = [20, 20, 20]
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
                    "pool": "fin05_withholding_records",
                    "targets": {fid: fid for fid in field_ids},
                }
            ],
            "data_pools": {"fin05_withholding_records": make_records()},
            "notes": "FIN-05 생산용 profile. 회사, 대표자, 근로자, 사업자번호, 근무기간, 총급여, 결정세액, 기납부세액, 차감징수세액을 하나의 record로 일관 생성한다.",
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
        draw.text((x, 15), f"fin05_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
        f"""# 2026-07-02 FIN-05 근로소득 원천징수영수증 파이프라인 준비 작업

## 목표
- `FIN-05 근로소득 원천징수영수증`을 단일 순차 대상으로 처리한다.
- 현재 workbench에 준비된 OCR/review/inpaint/authoring 범위는 1페이지이므로, 이번 산출물은 1페이지 서식 생산 준비로 명시한다.
- 주주명부 방식과 동일하게 schema + faker_profile + stylesheet를 record 기반으로 고정하고, crop 비교 없이 전체 문서 비교/50% overlay/contact sheet만으로 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa source template: `{TEMPLATE_SOURCE}`
- authoring derived template: `{TEMPLATE}`
- 기존 authoring: 1페이지 25개 필드.
- 원본 PDF는 3페이지이지만 2~3페이지에 대한 review/inpaint/authoring은 아직 준비되어 있지 않다.

## 구현 내용
- font-family는 원본 국세청 서식의 산세리프 인쇄체 시각 정보에 가장 가까운 `{FONT_FAMILY}`로 지정했다.
- 기존 독립 faker 규칙을 `fin05_withholding_records` 단일 record pool로 치환했다.
- 회사/대표자/사업자번호/주소, 근로자 성명/주민등록번호, 근무기간, 총급여, 과세소득, 기납부세액, 결정세액, 차감징수세액이 같은 record에서 생성된다.
- 금액/세액 계열은 right, 번호/일자/하단 기관명은 center, 회사명/주소/성명은 left 정렬로 고정했다.
- 기존 템플릿에 정적으로 남아 있던 표 내부 `근무처명`은 파생 템플릿에서 제거하고 `workplace_name` 동적 필드로 추가했다.
- 하단 `원천징수의무자`, `세무서장 귀하` 영역은 전체 비교 기준으로 bbox를 약간 확장하여 원본 위치 관계에 맞췄다.

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
- 현재 생산 준비 범위는 첫 페이지다. 원본 2~3페이지까지 합성 대상에 포함하려면 후속 단계에서 페이지별 bbox review/inpaint/authoring 확장이 필요하다.
- 원본 도장/상단 체크 표시/거주구분 필기는 template에 남겨 두는 방식이다.
""",
        encoding="utf-8",
    )


def main() -> None:
    for path in [SCHEMA_PATH, STYLE_PATH, FAKER_PATH, ORIGINAL, TEMPLATE_SOURCE]:
        if not path.exists():
            raise FileNotFoundError(path)
    prepare_template()
    if CALIB_DIR.exists():
        shutil.rmtree(CALIB_DIR)
    schema = update_schema(read_json(SCHEMA_PATH))
    stylesheet = update_stylesheet(read_json(STYLE_PATH))
    faker = update_faker(schema, read_json(FAKER_PATH))
    write_json(SCHEMA_PATH, schema)
    write_json(STYLE_PATH, stylesheet)
    write_json(FAKER_PATH, faker)

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="fin05", clean=True)
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
