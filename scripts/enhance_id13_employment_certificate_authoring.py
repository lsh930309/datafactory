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

DOC_ID = "ID-13"
DOC_TITLE = "재직증명서"
DOC_DIR = ROOT / "workbench" / "documents" / "재직증명서__ID-13"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "ID-13_employment_certificate"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "ID-13_employment_certificate"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_id13_employment_certificate_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "재직증명서.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_재직증명서" / "lama" / "inpainted_lama.png"
FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()

STYLE_SIZE = {
    "certificate_number": 18,
    "department": 18,
    "job_title": 18,
    "employee_name": 19,
    "employment_period": 16,
    "submission_to": 16,
    "purpose": 17,
    "issue_date": 17,
    "organization_name": 24,
    "chairperson_name": 27,
    "confirmation_department": 15,
    "confirmation_phone": 14,
}
ALIGN = {
    "certificate_number": "center",
    "department": "left",
    "job_title": "left",
    "employee_name": "left",
    "employment_period": "left",
    "submission_to": "left",
    "purpose": "left",
    "issue_date": "center",
    "organization_name": "center",
    "chairperson_name": "center",
    "confirmation_department": "left",
    "confirmation_phone": "left",
}
PEOPLE = ["김명신", "이서윤", "박도윤", "최서연", "정하준", "오서윤", "강도현", "윤지호", "임준우", "한지민"]
ORG_RECORDS = [
    ("(사)한국게임산업협회", "회장", "김명신", "기획이사", "경영지원실"),
    ("한국소프트웨어산업협회", "회장", "한지민", "팀장", "정책기획팀"),
    ("한국제조산업협회", "회장", "박재윤", "책임연구원", "산업조사본부"),
    ("한국디지털산업진흥회", "회장", "이도현", "국장", "대외협력국"),
    ("한국바이오산업협회", "회장", "오서윤", "선임연구원", "회원지원팀"),
]
PURPOSES = ["구비 서류", "금융기관 제출", "공공기관 제출", "학교 제출", "경력 확인", "비자 신청"]
SUBMISSIONS = ["학교 제출", "금융기관 제출", "공공기관 제출", "관공서 제출", "제출처 지정 없음"]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def fmt_date(date: datetime) -> str:
    return f"{date.year}년 {date.month:02d}월 {date.day:02d}일"


def employment_period(start: datetime, end: datetime) -> str:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    years, rem = divmod(max(months, 0), 12)
    return f"{fmt_date(start)}부터 {end.year}년 {end.month}월 {end.day}일 현재까지 ( {years}년 {rem}개월 )"


def make_profiles() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    profiles: list[dict[str, str]] = []
    for idx in range(12):
        org, chair_title, chair, job_title, dept = ORG_RECORDS[idx % len(ORG_RECORDS)]
        employee = PEOPLE[(idx + 1) % len(PEOPLE)]
        issue = datetime(2024 + (idx % 3), [3, 5, 6, 8, 10, 12][idx % 6], [8, 15, 21, 25, 27, 29][idx % 6])
        start = datetime(issue.year - rng.choice([2, 3, 4, 5, 6]), rng.choice([1, 3, 4, 7, 9]), rng.choice([1, 5, 10, 15]))
        cert = f"제 KAO{chr(65 + idx % 26)}{rng.randrange(10,99)}-{rng.randrange(1,999):03d}호"
        profiles.append({
            "certificate_number": cert,
            "department": dept,
            "job_title": job_title,
            "employee_name": employee,
            "employment_period": employment_period(start, issue),
            "submission_to": SUBMISSIONS[idx % len(SUBMISSIONS)],
            "purpose": PURPOSES[idx % len(PURPOSES)],
            "issue_date": fmt_date(issue),
            "organization_name": org,
            "chairperson_name": f"{chair_title} {chair}",
            "confirmation_department": f"확인부서 : {dept}, 성명 : {chair}",
            "confirmation_phone": f"(확인부서 연락처 : 02-{rng.randrange(1000,9999)}-{rng.randrange(1000,9999)})",
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
        "authoring_mode": "id13_pipeline_ready_20260702",
        "quality_status": "pipeline_ready_candidate",
    })
    for field in schema.get("fields", []):
        fid = field["field_id"]
        field["generator"] = f"pool_record:id13_employment_profiles.{fid}"
        field.setdefault("render_policy", {})["align"] = ALIGN.get(fid, "left")
        field.setdefault("render_policy", {})["valign"] = "middle"
        field.setdefault("render_policy", {})["fit"] = "shrink_to_fit"
        field.setdefault("render_policy", {})["overflow"] = "shrink"
        field["notes"] = "ID-13 재직증명서 생산용 보정 필드. 원본 라벨과 중복되지 않도록 값만 주입하며 crop 비교 없이 전체 문서 기준으로 검수."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update({
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "notes": f"ID-13 재직증명서 style 보정. 초기 보정 결과에 더 가까운 산세리프 인상으로 회귀하기 위해 {FONT_FAMILY}를 선택했다. 전체 문서/50% overlay 기준으로만 크기·농도를 조정하고 crop 비교는 제외했다.",
    })
    for style in stylesheet.get("style_classes", []):
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = STYLE_SIZE.get(fid, style.get("font_size", 18))
        style["fill"] = [26, 26, 26]
        style["opacity"] = 0.84
        style["align"] = ALIGN.get(fid, style.get("align", "left"))
        style["valign"] = "middle"
        style["line_spacing"] = 1.0
        style["letter_spacing"] = 0.0
        style["baseline_shift"] = 0
        style["overflow"] = "shrink"
        style["confidence"] = 0.82
    return stylesheet


def update_faker(schema: dict[str, Any], faker: dict[str, Any]) -> dict[str, Any]:
    field_ids = [field["field_id"] for field in schema.get("fields", [])]
    faker = json.loads(json.dumps(faker, ensure_ascii=False))
    faker.update({
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "locale": "ko_KR",
        "field_generators": {fid: "literal:" for fid in field_ids},
        "constraints": [{"type": "pick_record", "pool": "id13_employment_profiles", "targets": {fid: fid for fid in field_ids}}],
        "data_pools": {"id13_employment_profiles": make_profiles()},
        "notes": "ID-13 생산용 profile. 기존 라벨 포함 값을 제거하고 증명서번호/소속/직책/성명/근무기간/제출처/용도/발급일/기관장 정보를 하나의 record로 일관 생성한다.",
    })
    return faker


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 190, 280
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 58), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 15), f"id13_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
        thumb = image.copy(); thumb.thumbnail((scale_w, 330))
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
    PROGRESS.write_text(f"""# 2026-07-02 ID-13 재직증명서 파이프라인 준비 작업

## 목표
- `ID-13 재직증명서`를 단일 순차 대상으로 처리한다.
- 기존 12개 필드 authoring을 주주명부 방식에 맞춰 schema/style/faker/batch 산출물까지 완료한다.
- crop 비교 루틴은 사용하지 않고 전체 문서/50% overlay 기준으로만 검수한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: 1페이지 12개 필드, preview 동작 가능 상태.

## 구현 내용
- 기존 faker가 입력 bbox에 `소속:`, `성명:`, `근무기간:` 등 라벨까지 포함해 원본 라벨과 중복되던 문제를 제거했다.
- 증명서번호, 소속, 직책, 성명, 근무기간, 제출처, 용도, 발급일, 기관명/대표자명, 확인부서/연락처를 하나의 record에서 일관 생성한다.
- font-family는 초기 작업 결과에 더 가까운 `{FONT_FAMILY}`로 회귀했다.
- crop 비교가 보정 방향을 흐린다고 판단하여 제외하고, 전체 문서/50% overlay/contact sheet만 보고 font-size·농도만 재보정했다.
- template 잔흔이 일부 남아 있으므로 opacity를 0.84로 낮춰 스캔 농도와 맞췄다.

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
- LaMa template에 소속/성명/제출처 주변 잔흔이 일부 남아 있다. 필요 시 수동 cleanup mask로 잔흔 제거를 추가하면 품질이 더 좋아진다.
- 주민등록번호/현주소는 원본도 사실상 공란이어서 이번 생산 필드에서는 유지하지 않았다.
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
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="id13", clean=True)
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
