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

DOC_ID = "ID-06"
DOC_TITLE = "신분증 사본(주민등록증)"
DOC_DIR = ROOT / "workbench" / "documents" / "신분증_사본(주민·면허·여권)__ID-06"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "ID-06_resident_id_copy"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "ID-06_resident_id_copy"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_id06_resident_id_copy_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "source.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_source" / "lama" / "inpainted_lama.png"

FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "Malgun Gothic"
NOW = datetime.now(timezone.utc).isoformat()

PEOPLE = [
    ("김민준(金敏俊)", "남", "1995-01-01"),
    ("서민서(徐旼瑞)", "여", "1997-03-14"),
    ("박도윤(朴度允)", "남", "1992-11-08"),
    ("이하린(李河潾)", "여", "1996-07-22"),
    ("정유찬(鄭裕燦)", "남", "1994-05-30"),
    ("최서연(崔瑞娟)", "여", "1998-12-19"),
]

ADDRESSES = [
    ("서울특별시 강남구 테헤란로 123", "456", "아파트 101동 505호", "서울특별시 시장"),
    ("부산광역시 영등포구 중앙로 43", "153", "아파트 101동 505호", "부산광역시 시장"),
    ("경기도 성남시 분당구 정자일로 95", "", "한솔마을 312동 1102호", "경기도 성남시장"),
    ("인천광역시 연수구 송도과학로 32", "", "더샵센트럴파크 204동 802호", "인천광역시 연수구청장"),
    ("대전광역시 유성구 대학로 99", "", "청솔아파트 703동 402호", "대전광역시 유성구청장"),
    ("광주광역시 서구 상무중앙로 71", "", "상무자이 108동 903호", "광주광역시 서구청장"),
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def rrn(birth: str, gender: str, rng: random.Random) -> str:
    yy, mm, dd = birth[2:4], birth[5:7], birth[8:10]
    century = "1" if gender == "남" else "2"
    return f"{yy}{mm}{dd}-{century}{rng.randrange(100000, 999999)}"


def make_records() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    records: list[dict[str, str]] = []
    for idx in range(12):
        name, gender, birth = PEOPLE[idx % len(PEOPLE)]
        addr1, addr2, addr3, issuer = ADDRESSES[idx % len(ADDRESSES)]
        issue_year = 2023 + (idx % 4)
        issue_month = [2, 4, 6, 8, 10, 12][idx % 6]
        issue_day = [3, 9, 15, 21, 24, 27][idx % 6]
        records.append(
            {
                "resident_name": name,
                "resident_registration_number": rrn(birth, gender, rng),
                "resident_address_line1": addr1,
                "resident_address_line2": addr2,
                "resident_address_line3": addr3,
                "id_issue_date": f"{issue_year}.{issue_month:02d}.{issue_day:02d}.",
                "id_issuer": issuer,
            }
        )
    return records


def style_size(field_id: str) -> int:
    if field_id == "resident_name":
        return 43
    if field_id == "resident_registration_number":
        return 35
    if field_id == "resident_address_line1":
        return 34
    if field_id == "resident_address_line2":
        return 32
    if field_id == "resident_address_line3":
        return 34
    if field_id == "id_issue_date":
        return 34
    if field_id == "id_issuer":
        return 42
    return 34


def align_for(field_id: str) -> str:
    if field_id in {"resident_registration_number", "id_issue_date", "id_issuer"}:
        return "center"
    return "left"


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
            "authoring_mode": "id06_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    bbox_overrides = {
        "resident_name": [190, 235, 430, 68],
        "resident_registration_number": [150, 338, 466, 52],
        "resident_address_line1": [130, 430, 650, 52],
        "resident_address_line2": [130, 480, 200, 45],
        "resident_address_line3": [130, 520, 440, 54],
        "id_issue_date": [560, 608, 290, 50],
        "id_issuer": [468, 660, 390, 70],
    }
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:id06_resident_id_records.{fid}"
        if fid in bbox_overrides:
            field["bbox"] = bbox_overrides[fid]
        policy = field.setdefault("render_policy", {})
        policy["align"] = align_for(fid)
        policy["valign"] = "middle"
        policy["fit"] = "shrink_to_fit"
        policy["overflow"] = "shrink"
        field["notes"] = "ID-06 주민등록증 사본 생산용 보정 필드. 이름/주민번호/주소/발급일/발급기관을 record 기반으로 일관 생성."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"ID-06 주민등록증 사본 style 보정. 실물 촬영 주민등록증의 산세리프 인쇄체와 전체 렌더링 결과를 기준으로 {FONT_FAMILY}를 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다.",
        }
    )
    for style in stylesheet.get("style_classes", []):
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = style_size(fid)
        style["fill"] = [22, 22, 22]
        style["opacity"] = 0.88
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
                    "pool": "id06_resident_id_records",
                    "targets": {fid: fid for fid in field_ids},
                }
            ],
            "data_pools": {"id06_resident_id_records": make_records()},
            "notes": "ID-06 생산용 profile. 주민등록증 표면 값 7개를 하나의 record로 생성한다.",
        }
    )
    return faker


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT), 16) if Path(FONT).exists() else ImageFont.load_default()
    cell_w, cell_h = 230, 170
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 58), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 15), f"id06_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
    font = ImageFont.truetype(str(FONT), 18) if Path(FONT).exists() else ImageFont.load_default()
    scale_w = 235
    sheet = Image.new("RGB", (scale_w * len(labels) + 18 * (len(labels) + 1), 260), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(labels):
        thumb = image.copy()
        thumb.thumbnail((scale_w, 190))
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
        f"""# 2026-07-02 ID-06 신분증 사본(주민등록증) 파이프라인 준비 작업

## 목표
- `ID-06 신분증 사본(주민등록증)`을 단일 순차 대상으로 처리한다.
- 7개 필드 기반으로 이름, 주민등록번호, 주소 3행, 발급일, 발급기관이 일관 생성되도록 한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: 1페이지 7개 필드, preview 동작 가능 상태.

## 구현 내용
- font-family는 실물 촬영 주민등록증의 산세리프 인쇄체 시각 정보에 가장 가까운 `{FONT_FAMILY}`로 지정했다.
- 기존 독립 faker 규칙을 `id06_resident_id_records` 단일 record pool로 치환했다.
- 성명/주민번호/주소/발급일/발급기관을 같은 record에서 생성한다.
- 이전 preview 대비 font-size와 opacity를 낮춰 원본 촬영본의 흐릿한 인쇄 질감에 맞췄다.

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
- 사진/직인/보안패턴은 template 원본을 유지한다.
- 현재는 주민등록증 앞면 1종 샘플 기준이다. 운전면허증/여권 사본은 별도 샘플 확보 후 별도 authoring 템플릿으로 확장해야 한다.
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
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="id06", clean=True)
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
