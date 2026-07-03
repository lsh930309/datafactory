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

DOC_ID = "ID-05"
DOC_TITLE = "가족관계증명서"
DOC_DIR = ROOT / "workbench" / "documents" / "가족관계증명서__ID-05"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "ID-05_family_relation_certificate"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "ID-05_family_relation_certificate"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_id05_family_relation_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "11-1.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_11-1" / "lama" / "inpainted_lama.png"

FONT_BATANG = ROOT / "fonts" / "batang.ttc"
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_BATANG if FONT_BATANG.exists() else FONT_FALLBACK)
FONT_FAMILY = "Batang" if FONT_BATANG.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()

FAMILIES = [
    {
        "bon": "安東",
        "father": ("권영기", "權寧基", datetime(1962, 1, 17)),
        "mother": ("임양빈", "任楊彬", datetime(1961, 3, 30)),
        "children": [("권민정", "權玟廷", datetime(1989, 1, 31), "여"), ("권지우", "權知佑", datetime(2004, 6, 21), "남")],
    },
    {
        "bon": "金海",
        "father": ("김도현", "金度賢", datetime(1971, 4, 13)),
        "mother": ("박서연", "朴瑞姸", datetime(1973, 8, 9)),
        "children": [("김하준", "金河俊", datetime(2006, 2, 18), "남"), ("김서윤", "金瑞潤", datetime(2008, 11, 7), "여")],
    },
    {
        "bon": "全州",
        "father": ("이준호", "李俊鎬", datetime(1968, 9, 25)),
        "mother": ("최지민", "崔智旼", datetime(1970, 12, 5)),
        "children": [("이서준", "李瑞俊", datetime(2003, 3, 16), "남"), ("이하은", "李河恩", datetime(2005, 5, 29), "여")],
    },
    {
        "bon": "密陽",
        "father": ("박재윤", "朴載允", datetime(1974, 6, 2)),
        "mother": ("한수빈", "韓秀彬", datetime(1975, 10, 22)),
        "children": [("박민재", "朴旼宰", datetime(2007, 7, 14), "남"), ("박예린", "朴叡潾", datetime(2010, 1, 4), "여")],
    },
    {
        "bon": "坡平",
        "father": ("윤성호", "尹成浩", datetime(1966, 11, 11)),
        "mother": ("오지현", "吳智賢", datetime(1969, 2, 27)),
        "children": [("윤도윤", "尹度允", datetime(2002, 9, 3), "남"), ("윤서아", "尹瑞娥", datetime(2006, 4, 19), "여")],
    },
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def fmt_date(date: datetime) -> str:
    return f"{date.year}년 {date.month:02d}월 {date.day:02d}일"


def rrn(date: datetime, gender: str, rng: random.Random) -> str:
    century_digit = "3" if gender == "남" else "4"
    if date.year < 2000:
        century_digit = "1" if gender == "남" else "2"
    return f"{date:%y%m%d}-{century_digit}{rng.randrange(100000, 999999)}"


def style_size(field_id: str) -> int:
    if field_id.endswith("_relation") or field_id.endswith("_gender"):
        return 66
    if field_id.endswith("_name"):
        return 66
    if field_id.endswith("_birth_date"):
        return 61
    if field_id.endswith("_rrn"):
        return 59
    if field_id.endswith("_registration_base"):
        return 63
    if field_id == "certificate_issue_date":
        return 66
    if field_id == "issuing_officer":
        return 62
    if field_id in {"issue_time", "applicant_name"}:
        return 54
    if field_id == "publication_number":
        return 38
    return 58


def align_for(field_id: str) -> str:
    if field_id in {"applicant_name"}:
        return "left"
    return "center"


def make_records() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    records: list[dict[str, str]] = []
    for idx in range(12):
        family = FAMILIES[idx % len(FAMILIES)]
        child_name, child_hanja, child_birth, child_gender = family["children"][idx % len(family["children"])]
        father_name, father_hanja, father_birth = family["father"]
        mother_name, mother_hanja, mother_birth = family["mother"]
        issue = datetime(2024 + (idx % 3), [3, 5, 6, 8, 10, 12][idx % 6], [8, 15, 21, 25, 27, 29][idx % 6])
        # 발급일이 대상자 생년월일보다 과거가 되지 않도록 보정한다.
        if issue <= child_birth:
            issue = child_birth + timedelta(days=365)
        applicant = child_name if child_birth.year <= 2006 else rng.choice([father_name, mother_name])
        officer = rng.choice(["유진호", "김민서", "이도윤", "박하린", "정서준"])
        records.append(
            {
                "subject_relation": "본인",
                "subject_name": f"{child_name} ({child_hanja})",
                "subject_birth_date": fmt_date(child_birth),
                "subject_rrn": rrn(child_birth, child_gender, rng),
                "subject_gender": child_gender,
                "subject_registration_base": family["bon"],
                "father_relation": "부",
                "father_name": f"{father_name} ({father_hanja})",
                "father_birth_date": fmt_date(father_birth),
                "father_rrn": rrn(father_birth, "남", rng),
                "father_gender": "남",
                "father_registration_base": family["bon"],
                "mother_relation": "모",
                "mother_name": f"{mother_name} ({mother_hanja})",
                "mother_birth_date": fmt_date(mother_birth),
                "mother_rrn": rrn(mother_birth, "여", rng),
                "mother_gender": "여",
                "mother_registration_base": family["bon"],
                "certificate_issue_date": fmt_date(issue),
                "issuing_officer": f"법원행정처 전산정보중앙관리소 전산운영책임관 {officer}",
                "issue_time": f"발급시각:{rng.randrange(9, 19):02d}시{rng.randrange(0, 60):02d}분",
                "applicant_name": f"신청인: {applicant}",
                "publication_number": f"발행번호:{rng.randrange(1000,9999)}-{rng.randrange(1000,9999)}-{rng.randrange(1000,9999)}-{rng.randrange(1000,9999)}",
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
            "authoring_mode": "id05_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:id05_family_records.{fid}"
        field.setdefault("render_policy", {})["align"] = align_for(fid)
        field.setdefault("render_policy", {})["valign"] = "middle"
        field.setdefault("render_policy", {})["fit"] = "shrink_to_fit"
        field.setdefault("render_policy", {})["overflow"] = "shrink"
        if fid.endswith("_registration_base"):
            field["label"] = field["label"].replace("등록기준지", "본관")
            field["notes"] = "기존 필드명은 registration_base지만 실제 bbox는 우측 '본' 칸이므로 본관 값을 렌더링한다."
        else:
            field["notes"] = "ID-05 가족관계증명서 생산용 보정 필드. 가족 구성원 record 기반으로 생년월일/성별/주민번호를 일관 생성."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"ID-05 가족관계증명서 style 보정. 원본 증명서의 명조/바탕 계열 인쇄체와 전체 렌더링 결과를 기준으로 {FONT_FAMILY}를 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다.",
        }
    )
    for style in stylesheet.get("style_classes", []):
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = style_size(fid)
        style["fill"] = [18, 18, 18]
        style["opacity"] = 0.94
        style["align"] = align_for(fid)
        style["valign"] = "middle"
        style["line_spacing"] = 1.0
        style["letter_spacing"] = 0.0
        style["baseline_shift"] = 0
        style["overflow"] = "shrink"
        style["confidence"] = 0.86
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
                    "pool": "id05_family_records",
                    "targets": {fid: fid for fid in field_ids},
                }
            ],
            "data_pools": {"id05_family_records": make_records()},
            "notes": "ID-05 생산용 profile. 본인/부/모의 이름, 한자명, 생년월일, 성별, 주민등록번호, 본관, 발급일/발급번호를 하나의 가족 record로 일관 생성한다.",
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
        draw.text((x, 15), f"id05_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
        f"""# 2026-07-02 ID-05 가족관계증명서 파이프라인 준비 작업

## 목표
- `ID-05 가족관계증명서`를 단일 순차 대상으로 처리한다.
- 기존 23개 bbox authoring을 유지하되, 가족 구성원 간 생년월일/성별/주민등록번호/본관을 record 기반으로 일관 생성한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: 1페이지 23개 필드, preview 동작 가능 상태.

## 구현 내용
- font-family는 원본 증명서의 명조/바탕 계열 시각 정보에 가장 가까운 `{FONT_FAMILY}`로 통일했다.
- 기존 `*_registration_base` 필드는 실제 bbox가 우측 `본` 칸이므로 주소가 아니라 `安東`, `金海` 등 본관 값으로 생성하도록 수정했다.
- 본인/부/모의 한자 병기 이름, 생년월일, 성별, 주민등록번호 앞자리 논리를 하나의 family record로 맞췄다.
- 발급일은 본인 생년월일 이후가 되도록 보정하고, 발급시각/신청인/발행번호를 함께 생성한다.

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
- 상단 등록기준지 주소는 현재 LaMa template에 잔존하는 고정 양식값을 사용한다.
- QR/직인/민국 워터마크 등 보안성 그래픽 요소는 template 원본을 그대로 사용한다.
- 필요 시 다음 라운드에서 상단 등록기준지 bbox를 새로 추가해 주소까지 동적화할 수 있다.
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
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="id05", clean=True)
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
