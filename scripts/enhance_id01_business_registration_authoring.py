#!/usr/bin/env python3
from __future__ import annotations

import json
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

DOC_ID = "ID-01"
DOC_TITLE = "사업자등록증"
DOC_DIR = ROOT / "workbench" / "documents" / "사업자등록증__ID-01"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "ID-01_business_registration_certificate"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "ID-01_business_registration_certificate"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_id01_business_registration_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "15-4.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_15-4" / "lama" / "inpainted_lama.png"
FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()

# Existing draft came from OCR-sized boxes.  Normalize visually noisy outliers while
# keeping the full-line label+value strategy because the LaMa template removed many
# original labels together with values.
SIZE_BY_FIELD = {
    "business_registration_number": 82,
    "corporate_name": 72,
    "representative_name": 82,
    "opening_date": 76,
    "corporate_registration_number": 72,
    "workplace_address": 76,
    "head_office_address_line1": 76,
    "head_office_address_line2": 72,
    "issue_reason": 82,
    "issue_date": 78,
    "tax_office_chief": 112,
}
BUSINESS_FIELD_SIZE = 72


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def update_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(json.dumps(schema, ensure_ascii=False))
    schema.update({
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "source_image": str(ORIGINAL.resolve()),
        "source_inpainted": str(TEMPLATE.resolve()),
        "authoring_mode": "id01_pipeline_ready_20260702",
        "quality_status": "pipeline_ready_candidate",
    })
    for field in schema.get("fields", []):
        field["notes"] = "ID-01 생산용 보정 필드. 원본/템플릿/렌더 전체 비교 기준으로 검수하며 crop 비교는 사용하지 않음."
        field.setdefault("render_policy", {})["fit"] = "shrink_to_fit"
        field.setdefault("render_policy", {})["overflow"] = "shrink"
        field.setdefault("render_policy", {})["valign"] = "middle"
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update({
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "notes": f"ID-01 사업자등록증 보정. 원본은 국세청 전자증명서의 산세리프 계열이므로 {FONT_FAMILY}를 사용하고, OCR 기원 크기 편차가 큰 업태/종목 필드는 전체 문서 시각 균형 기준으로 72px 내외로 정규화했다. crop 비교는 제외했다.",
    })
    for style in stylesheet.get("style_classes", []):
        sid = style.get("style_class", "")
        fid = sid.removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["fill"] = [28, 28, 28]
        style["opacity"] = 0.92
        style["line_spacing"] = 1.0
        style["letter_spacing"] = 0.0
        style["baseline_shift"] = 0
        style["overflow"] = "shrink"
        style["confidence"] = 0.80
        if fid in SIZE_BY_FIELD:
            style["font_size"] = SIZE_BY_FIELD[fid]
        elif fid.startswith("business_type_") or fid.startswith("business_item_"):
            style["font_size"] = BUSINESS_FIELD_SIZE
        # Preserve the official's office name as a larger centered signature line.
        if fid == "tax_office_chief":
            style["align"] = "center"
        elif fid in {"business_registration_number", "corporate_registration_number", "issue_date"}:
            style["align"] = "center"
        else:
            style["align"] = "left"
    return stylesheet


def update_faker_profile(faker: dict[str, Any]) -> dict[str, Any]:
    faker = json.loads(json.dumps(faker, ensure_ascii=False))
    faker.update({
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "notes": "ID-01 사업자등록증 생산용 profile. 기존 label+value line strategy를 유지해 LaMa가 함께 제거한 라벨까지 자연스럽게 복원한다.",
    })
    return faker


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 230, 330
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 60), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 16), f"id01_{idx + 1:06d}", font=font, fill=(30, 30, 30))
        image = Image.open(path).convert("RGB")
        image.thumbnail((cell_w - 18, cell_h - 32))
        y = 44
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
    diff_amp = diff.point(lambda value: min(255, value * 4))
    overlay = Image.blend(template, render, 0.5)
    labels = [("original", original), ("template", template), ("render", render), ("amplified diff", diff_amp), ("50% overlay", overlay)]
    font = ImageFont.truetype(str(FONT_FALLBACK), 18) if FONT_FALLBACK.exists() else ImageFont.load_default()
    scale_w = 300
    sheet = Image.new("RGB", (scale_w * len(labels) + 20 * (len(labels) + 1), 500), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(labels):
        thumb = image.copy()
        thumb.thumbnail((scale_w, 430))
        x = 20 + idx * (scale_w + 20)
        draw.text((x, 18), label, font=font, fill=(20, 20, 20))
        sheet.paste(thumb, (x, 52))
        draw.rectangle([x, 52, x + thumb.width, 52 + thumb.height], outline=(150, 150, 150))
    out = CALIB_DIR / "full_comparison.jpg"
    sheet.save(out, quality=92)
    diff.save(CALIB_DIR / "full_diff.png")
    overlay.save(CALIB_DIR / "full_overlay_50.png")
    return out


def write_progress(batch_summary: dict[str, Any], preview_image: Path, comparison: Path, contact: Path) -> None:
    PROGRESS.write_text(f"""# 2026-07-02 ID-01 사업자등록증 파이프라인 준비 작업

## 목표
- `ID-01 사업자등록증`을 주주명부 방식에 따라 단일 순차 대상으로 처리한다.
- 기존 authoring bundle을 보존하되 전체 문서 시각 비교 기준으로 font/style 편차를 보정하고 5세트 batch 산출물을 만든다.
- crop 비교 루틴은 사용하지 않는다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 schema/style/faker: 24개 필드, 24개 style class, record pool 기반 profile.

## 구현 내용
- LaMa template가 일부 라벨까지 함께 지운 상태이므로 기존 `label + value` 렌더링 전략을 유지했다.
- OCR 기반 style 추출에서 과도하게 커졌던 업태/종목 필드 크기를 전체 문서 시각 균형 기준으로 72px 내외로 정규화했다.
- 사업자등록번호/법인명/대표자/주소/발급일/세무서장 등 주요 라인은 원본 국세청 전자증명서의 산세리프 인쇄 느낌에 맞춰 `{FONT_FAMILY}`로 통일했다.
- stylesheet opacity를 0.92로 낮춰 템플릿 잔존 노이즈와 과하게 뜨지 않도록 조정했다.
- schema quality_status를 `pipeline_ready_candidate`로 갱신하고 manifest artifact를 업데이트했다.

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
- 생성 수: {batch_summary['count']}세트
- field_count_per_sample: {batch_summary.get('field_count_per_sample', batch_summary.get('field_count'))}
- warning_count: {batch_summary['warning_count']}

## 한계 및 다음 조치
- 원본 template 자체에 일부 지워지지 않은 사업종목 조각과 중앙 국세청 워터마크가 남아 있다. 현재 단계에서는 그 위에 자연스럽게 합성하되, 최종 품질을 더 높이려면 cleanup mask로 잔존 텍스트를 추가 제거하는 것이 좋다.
- 하단 바코드/QR/관인/국세청 로고는 정적 요소로 보존한다.
""", encoding="utf-8")


def main() -> None:
    for path in [SCHEMA_PATH, STYLE_PATH, FAKER_PATH, ORIGINAL, TEMPLATE]:
        if not path.exists():
            raise FileNotFoundError(path)
    if CALIB_DIR.exists():
        shutil.rmtree(CALIB_DIR)
    schema = update_schema(read_json(SCHEMA_PATH))
    stylesheet = update_stylesheet(read_json(STYLE_PATH))
    faker = update_faker_profile(read_json(FAKER_PATH))
    write_json(SCHEMA_PATH, schema)
    write_json(STYLE_PATH, stylesheet)
    write_json(FAKER_PATH, faker)

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="id01", clean=True)
    sample_paths = [sample.image for sample in batch.samples]
    contact = make_contact_sheet(sample_paths)
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
