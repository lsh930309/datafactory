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

DOC_ID = "FIN-04"
DOC_TITLE = "4대보험 가입증명원"
DOC_DIR = ROOT / "workbench" / "documents" / "4대보험_가입증명원__FIN-04"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "FIN-04_four_insurance_certificate"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "FIN-04_four_insurance_certificate"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_fin04_four_insurance_certificate_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "4대보험가입확인서_page_001.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_4대보험가입확인서_page_001" / "lama" / "inpainted_lama.png"
FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()

# Fine-tuned from the existing authoring sizes by whole-page comparison only.
SIZE = {
    "header_document_confirmation": 17,
    "print_date": 11,
    "print_time": 11,
    "application_number": 17,
    "application_datetime": 17,
    "applicant_rrn": 17,
    "applicant_name": 23,
    "page_number": 18,
    "subscriber_name": 22,
    "subscriber_type": 19,
    "workplace_number": 16,
    "workplace_name": 16,
    "date": 17,
}
PEOPLE = [
    ("이승훈", "930309-1069114"),
    ("김민준", "790724-1037295"),
    ("박도윤", "880621-1054286"),
    ("최서연", "920402-2059184"),
    ("정하준", "850730-1047621"),
    ("오서윤", "900115-2063384"),
    ("강도현", "850730-1038842"),
    ("윤지호", "870808-1042739"),
]
COMPANIES = [
    ("한국딥러닝 주식회사", "36881014090"),
    ("한빛정밀 주식회사", "11081172531"),
    ("대한산업 주식회사", "2148630951"),
    ("미래테크 주식회사", "1058722091"),
    ("주식회사 지엘어소시에이츠", "51824706402"),
    ("세종바이오 주식회사", "1208749021"),
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def doc_no(rng: random.Random) -> str:
    return f"{rng.randrange(1000, 9999)}-{rng.randrange(1000, 9999)}-{rng.randrange(1000, 9999)}-{rng.randrange(1000, 9999)}"


def app_no(issue: datetime, rng: random.Random) -> str:
    return issue.strftime("%Y%m%d") + f"{rng.randrange(100000, 999999)}"


def ymd_dot(date: datetime) -> str:
    return date.strftime("%Y.%m.%d")


def make_profiles() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    profiles: list[dict[str, str]] = []
    base_issue = datetime(2026, 6, 29, 11, 37)
    for idx in range(12):
        name, rrn = PEOPLE[idx % len(PEOPLE)]
        company, workplace = COMPANIES[idx % len(COMPANIES)]
        issue = base_issue + timedelta(days=idx * 17, minutes=idx * 7)
        acquire = datetime(2021 + (idx % 5), [1, 3, 5, 8, 10, 12][idx % 6], [1, 5, 8, 15, 21, 26][idx % 6])
        reported = acquire + timedelta(days=[0, 3, 5, 8][idx % 4])
        record: dict[str, str] = {
            "header_document_confirmation": f"문서확인번호: {doc_no(rng)} (신청인 : {name})",
            "print_date": issue.strftime("%Y/%m/%d"),
            "print_time": issue.strftime("%H:%M:%S"),
            "application_number": app_no(issue, rng),
            "application_datetime": issue.strftime("%Y-%m-%d %H:%M"),
            "applicant_rrn": rrn,
            "applicant_name": name,
            "page_number": "1 / 1",
        }
        rows = {
            "np": "사업장가입자",
            "hi": "직장가입자",
            "ei": "사업장가입자",
            "wc": "사업장가입자",
        }
        for prefix, subscriber_type in rows.items():
            record[f"{prefix}_acquisition_date"] = ymd_dot(acquire)
            record[f"{prefix}_subscriber_name"] = name
            record[f"{prefix}_subscriber_type"] = subscriber_type
            record[f"{prefix}_workplace_number"] = workplace
            record[f"{prefix}_workplace_name"] = company
            # Original document uses 신고접수일 in parentheses under the acquisition date.
            record[f"{prefix}_notice_date"] = f"({ymd_dot(reported)})"
        # 산재/고용은 일부 실제 양식에서 신고접수일이 같은 날로 찍히는 경우가 많아 약간 분기.
        if idx % 3 == 0:
            for prefix in ["ei", "wc"]:
                record[f"{prefix}_notice_date"] = f"({ymd_dot(acquire)})"
        profiles.append(record)
    return profiles


def style_size(field_id: str, current: int) -> int:
    if field_id in SIZE:
        return SIZE[field_id]
    if field_id.endswith("_subscriber_name"):
        return SIZE["subscriber_name"]
    if field_id.endswith("_subscriber_type"):
        return SIZE["subscriber_type"]
    if field_id.endswith("_workplace_number"):
        return SIZE["workplace_number"]
    if field_id.endswith("_workplace_name"):
        return SIZE["workplace_name"]
    if field_id.endswith("_acquisition_date") or field_id.endswith("_notice_date"):
        return SIZE["date"]
    return current


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
        "authoring_mode": "fin04_pipeline_ready_20260702",
        "quality_status": "pipeline_ready_candidate",
    })
    for field in schema.get("fields", []):
        fid = field["field_id"]
        field["generator"] = f"pool_record:fin04_profiles.{fid}"
        field.setdefault("render_policy", {})["valign"] = "middle"
        field.setdefault("render_policy", {})["fit"] = "shrink_to_fit"
        field.setdefault("render_policy", {})["overflow"] = "shrink"
        if fid.endswith("_workplace_name") or fid.endswith("_subscriber_type") or fid.endswith("_subscriber_name"):
            field["render_policy"]["align"] = "left"
        elif fid.endswith("_workplace_number") or fid.endswith("_acquisition_date") or fid.endswith("_notice_date"):
            field["render_policy"]["align"] = "center"
        field["notes"] = "FIN-04 생산용 보정 필드. crop 비교 없이 전체 문서/overlay 기준으로 검수."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update({
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "notes": f"FIN-04 4대보험 가입증명원 보정. 원본 표 기입값은 현대 산세리프 인쇄체가 가장 유사하여 {FONT_FAMILY}를 선택했다. 전체 문서/50% overlay 기준으로만 크기와 농도를 조정하고 crop 비교는 제외했다.",
    })
    for style in stylesheet.get("style_classes", []):
        sid = str(style.get("style_class", ""))
        fid = sid.removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = style_size(fid, int(style.get("font_size", 17)))
        style["fill"] = [28, 28, 28]
        style["opacity"] = 0.92
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
    faker.update({
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "locale": "ko_KR",
        "field_generators": {fid: "literal:" for fid in field_ids},
        "constraints": [{"type": "pick_record", "pool": "fin04_profiles", "targets": {fid: fid for fid in field_ids}}],
        "data_pools": {"fin04_profiles": make_profiles()},
        "notes": "FIN-04 생산용 profile. 신청인/주민번호/신청번호/4대보험 행의 이름·사업장·관리번호·취득일을 하나의 record로 일관 생성한다.",
    })
    return faker


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 220, 320
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 58), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 15), f"fin04_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
    PROGRESS.write_text(f"""# 2026-07-02 FIN-04 4대보험 가입증명원 파이프라인 준비 작업

## 목표
- `FIN-04 4대보험 가입증명원`을 단일 순차 대상으로 처리한다.
- 기존 32개 필드 authoring을 주주명부 방식에 맞춰 schema/style/faker/batch 산출물까지 완료한다.
- crop 비교 루틴은 사용하지 않고 전체 문서/50% overlay 기준으로만 검수한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: 1페이지 32개 필드, preview 동작 가능 상태.

## 구현 내용
- 기존 faker의 독립 생성 때문에 신청인/4대보험 행 성명/사업장명이 서로 달라지는 문제를 record 기반 profile로 수정했다.
- 문서확인번호, 출력일자/시각, 발급번호, 발급일시, 신청인 주민번호/성명, 4대보험 행의 취득일/신고접수일/사업장 정보를 하나의 record로 일관 생성한다.
- 페이지 표기는 원본과 같은 `1 / 1` 형식으로 고정했다.
- font-family는 전체 렌더 시각 기준으로 `{FONT_FAMILY}`를 선택했다.
- 표 내부 값의 크기를 원본 행 높이에 맞춰 조정하고, 회사명/가입자명/가입자종별은 좌측 정렬, 번호/일자는 중앙 정렬로 유지했다.

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
- 상단 진본확인 도장, 정부24 QR, 하단 기관 직인/로고/바코드는 정적 요소로 보존한다.
- 원본 template가 표와 기관 로고를 잘 보존하고 있어 추가 cleanup은 필수는 아니다.
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
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="fin04", clean=True)
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
