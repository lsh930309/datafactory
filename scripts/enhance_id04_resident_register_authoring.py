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

DOC_ID = "ID-04"
DOC_TITLE = "주민등록등본"
DOC_DIR = ROOT / "workbench" / "documents" / "주민등록등본__ID-04"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "ID-04_resident_register"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "ID-04_resident_register"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_id04_resident_register_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "009.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_009" / "lama" / "inpainted_lama.png"

FONT_BATANG = ROOT / "fonts" / "batang.ttc"
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_BATANG if FONT_BATANG.exists() else FONT_FALLBACK)
FONT_FAMILY = "Batang" if FONT_BATANG.exists() else "Malgun Gothic"
NOW = datetime.now(timezone.utc).isoformat()

HOUSEHOLDS = [
    {
        "head": ("정혜라", "鄭德羅", "여", datetime(1970, 6, 28)),
        "spouse": ("김관혁", "金寬赫", "남", datetime(1967, 6, 1)),
        "child": ("김지현", "金志泫", "여", datetime(1997, 8, 4)),
        "address1": "경기도 용인시 처인구 금어로 46,",
        "building": "112동",
        "detail": "2704호 (고림동, 힐스테이트 용인 둔전역)",
        "issuer": "경기도 용인시장",
        "phone_area": "031",
        "change_reason": "행정구역변경",
    },
    {
        "head": ("박서준", "朴瑞俊", "남", datetime(1975, 2, 13)),
        "spouse": ("최하윤", "崔河潤", "여", datetime(1977, 9, 3)),
        "child": ("박민서", "朴旼瑞", "여", datetime(2004, 11, 21)),
        "address1": "서울특별시 송파구 위례성대로 128,",
        "building": "305동",
        "detail": "1402호 (방이동, 올림픽파크하임)",
        "issuer": "서울특별시 송파구청장",
        "phone_area": "02",
        "change_reason": "전입",
    },
    {
        "head": ("이도윤", "李度潤", "남", datetime(1969, 12, 5)),
        "spouse": ("한서연", "韓瑞姸", "여", datetime(1972, 4, 17)),
        "child": ("이준서", "李俊瑞", "남", datetime(2001, 5, 9)),
        "address1": "부산광역시 해운대구 센텀중앙로 90,",
        "building": "101동",
        "detail": "2206호 (재송동, 센텀리버뷰)",
        "issuer": "부산광역시 해운대구청장",
        "phone_area": "051",
        "change_reason": "거주지변경",
    },
    {
        "head": ("윤지호", "尹智浩", "남", datetime(1980, 3, 30)),
        "spouse": ("오수빈", "吳秀彬", "여", datetime(1982, 7, 12)),
        "child": ("윤하람", "尹河覽", "여", datetime(2011, 1, 25)),
        "address1": "인천광역시 연수구 송도문화로 28,",
        "building": "207동",
        "detail": "803호 (송도동, 글로벌캠퍼스푸르지오)",
        "issuer": "인천광역시 연수구청장",
        "phone_area": "032",
        "change_reason": "전입",
    },
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def rrn(birth: datetime, gender: str, rng: random.Random) -> str:
    digit = "1" if gender == "남" else "2"
    if birth.year >= 2000:
        digit = "3" if gender == "남" else "4"
    return f"{birth:%y%m%d}-{digit}{rng.randrange(100000, 999999)}"


def fmt_dash(date: datetime) -> str:
    return f"{date:%Y-%m-%d}"


def fmt_kr(date: datetime) -> str:
    return f"{date.year}년 {date.month:02d}월 {date.day:02d}일"


def make_records() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    records: list[dict[str, str]] = []
    for idx in range(12):
        item = HOUSEHOLDS[idx % len(HOUSEHOLDS)]
        head_name, head_hanja, head_gender, head_birth = item["head"]
        spouse_name, spouse_hanja, spouse_gender, spouse_birth = item["spouse"]
        child_name, child_hanja, child_gender, child_birth = item["child"]
        issue = datetime(2024 + idx % 3, [2, 3, 5, 7, 8, 10][idx % 6], [4, 7, 12, 16, 21, 25][idx % 6])
        household_change = issue - timedelta(days=90 + idx * 17)
        address_change = issue - timedelta(days=24 + idx * 9)
        applicant_name, _, _, applicant_birth = [item["child"], item["head"], item["spouse"]][idx % 3]
        contact = f"전화:{item['phone_area']}-{rng.randrange(2000, 8999)}-{rng.randrange(1000, 9999)}"
        record: dict[str, str] = {
            "document_confirmation_number": f"문서확인번호 : {rng.randrange(1000,9999)}-{rng.randrange(1000,9999)}-{rng.randrange(1000,9999)}-{rng.randrange(1000,9999)}",
            "contact_phone": contact,
            "applicant_name": f"신청인: {applicant_name}",
            "applicant_birth_date": f"({applicant_birth:%Y-%m-%d} )",
            "certificate_issue_date": fmt_kr(issue),
            "issuer": item["issuer"],
            "household_change_reason_1": "세대주변경" if idx % 2 == 0 else "전입",
            "household_head_name": head_name,
            "household_head_name_hanja_open": "(",
            "household_head_hanja_value": head_hanja,
            "household_head_name_hanja_close": ")",
            "household_change_date_1": fmt_dash(household_change),
            "address_line_1": item["address1"],
            "address_change_date": fmt_dash(address_change),
            "address_line_2_building": item["building"],
            "address_line_2_detail": item["detail"],
            "address_change_reason": item["change_reason"],
            "member_1_no": "1",
            "member_1_relation": "본인",
            "member_1_name": head_name,
            "member_1_hanja_open": "(",
            "member_1_hanja_value": head_hanja,
            "member_1_hanja_close": ")",
            "member_1_change_date": fmt_dash(household_change),
            "member_1_change_reason": "세대주변경" if idx % 2 == 0 else "전입",
            "member_1_status": "거주자",
            "member_1_rrn": rrn(head_birth, head_gender, rng),
            "member_2_no": "2",
            "member_2_relation": "배우자",
            "member_2_name": spouse_name,
            "member_2_hanja_open": "(",
            "member_2_hanja_value": spouse_hanja,
            "member_2_hanja_close": ")",
            "member_2_change_date": fmt_dash(household_change),
            "member_2_change_reason": "세대주변경" if idx % 2 == 0 else "전입",
            "member_2_status": "거주자",
            "member_2_rrn": rrn(spouse_birth, spouse_gender, rng),
            "member_3_no": "3",
            "member_3_relation": "자녀",
            "member_3_name": child_name,
            "member_3_hanja_open": "(",
            "member_3_hanja_value": child_hanja,
            "member_3_hanja_close": ")",
            "member_3_change_date": fmt_dash(household_change),
            "member_3_change_reason": "세대주변경" if idx % 2 == 0 else "전입",
            "member_3_status": "거주자",
            "member_3_rrn": rrn(child_birth, child_gender, rng),
            "blank_line_marker": "== 이하 여백 ==",
        }
        records.append(record)
    return records


def clone_field(base: dict[str, Any], field_id: str, label: str, bbox: list[int], json_path: str) -> dict[str, Any]:
    return {
        "field_id": field_id,
        "label": label,
        "bbox": bbox,
        "bbox_format": "xywh",
        "source_detection_id": "manual_grid_addition_20260702",
        "source_text": "",
        "value_type": "person.name_hanja",
        "generator": f"pool_record:id04_resident_register_records.{field_id}",
        "style_class": f"style_{field_id}",
        "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        "export": {"json_path": json_path, "csv_column": field_id},
        "required": True,
        "notes": "원본 표에는 한자 이름 값이 있으나 초기 OCR bbox에는 괄호만 잡혀 수동 grid bbox로 추가했다.",
    }


def ensure_hanja_fields(schema: dict[str, Any]) -> None:
    fields = schema.setdefault("fields", [])
    existing = {f.get("field_id") for f in fields}
    anchor = fields[0] if fields else {}
    additions = [
        ("household_head_hanja_value", "세대주 한자", [1542, 905, 345, 89], "household.head.name_hanja"),
        ("member_1_hanja_value", "세대원 1 한자", [1512, 1736, 405, 89], "members.1.name_hanja"),
        ("member_2_hanja_value", "세대원 2 한자", [1512, 1911, 405, 89], "members.2.name_hanja"),
        ("member_3_hanja_value", "세대원 3 한자", [1512, 2085, 405, 89], "members.3.name_hanja"),
    ]
    for field_id, label, bbox, path in additions:
        if field_id not in existing:
            fields.append(clone_field(anchor, field_id, label, bbox, path))


def align_for(field_id: str) -> str:
    if field_id in {"document_confirmation_number", "contact_phone", "applicant_name", "applicant_birth_date", "address_line_1", "address_line_2_building", "address_line_2_detail"}:
        return "left"
    if field_id.endswith("_name") or field_id == "household_head_name":
        return "left"
    return "center"


def style_size(field_id: str) -> int:
    if field_id == "document_confirmation_number":
        return 54
    if field_id in {"contact_phone", "applicant_name", "applicant_birth_date"}:
        return 49
    if field_id == "certificate_issue_date":
        return 56
    if field_id == "issuer":
        return 72
    if field_id in {"household_head_name", "household_change_reason_1", "household_change_date_1"}:
        return 58
    if field_id.startswith("address_line_"):
        return 56
    if field_id in {"address_change_date", "address_change_reason"}:
        return 54
    if "hanja" in field_id:
        return 54
    if field_id.endswith("_name"):
        return 58
    if field_id.endswith("_rrn"):
        return 54
    if field_id.endswith("_change_date"):
        return 53
    if field_id.endswith("_status"):
        return 56
    if field_id.endswith("_relation") or field_id.endswith("_change_reason"):
        return 58
    if field_id.endswith("_no"):
        return 58
    if field_id == "blank_line_marker":
        return 54
    return 55


def bbox_overrides() -> dict[str, list[int]]:
    # 초기 OCR bbox를 표/grid 기준으로 조금 조정한다. 좌표계는 원본 3730x5272 기준 xywh.
    return {
        "document_confirmation_number": [675, 163, 1120, 82],
        "contact_phone": [2390, 410, 545, 82],
        "applicant_name": [1728, 486, 420, 86],
        "applicant_birth_date": [2388, 486, 390, 86],
        "certificate_issue_date": [2145, 640, 500, 82],
        "issuer": [2730, 735, 700, 120],
        "household_head_name": [930, 898, 185, 93],
        "household_change_reason_1": [2660, 870, 320, 68],
        "household_change_date_1": [2660, 940, 320, 68],
        "address_line_1": [506, 1210, 980, 72],
        "address_line_2_building": [506, 1284, 180, 72],
        "address_line_2_detail": [690, 1284, 1230, 72],
        "address_change_date": [3065, 1210, 335, 72],
        "address_change_reason": [3040, 1286, 360, 72],
        "member_1_no": [325, 1765, 72, 88],
        "member_1_relation": [548, 1748, 205, 108],
        "member_1_name": [825, 1725, 190, 80],
        "member_1_rrn": [825, 1810, 440, 72],
        "member_1_change_date": [2530, 1738, 330, 72],
        "member_1_status": [2330, 1813, 225, 72],
        "member_1_change_reason": [3010, 1760, 340, 88],
        "member_2_no": [325, 1938, 72, 88],
        "member_2_relation": [545, 1925, 210, 108],
        "member_2_name": [825, 1898, 190, 80],
        "member_2_rrn": [825, 1984, 440, 72],
        "member_2_change_date": [2530, 1912, 330, 72],
        "member_2_status": [2330, 1988, 225, 72],
        "member_2_change_reason": [3010, 1934, 340, 88],
        "member_3_no": [325, 2112, 72, 88],
        "member_3_relation": [548, 2098, 205, 108],
        "member_3_name": [825, 2072, 190, 80],
        "member_3_rrn": [825, 2158, 440, 72],
        "member_3_change_date": [2530, 2086, 330, 72],
        "member_3_status": [2330, 2162, 225, 72],
        "member_3_change_reason": [3010, 2108, 340, 88],
        "blank_line_marker": [1580, 2304, 560, 84],
    }


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
            "authoring_mode": "id04_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    ensure_hanja_fields(schema)
    overrides = bbox_overrides()
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:id04_resident_register_records.{fid}"
        if fid in overrides:
            field["bbox"] = overrides[fid]
        policy = field.setdefault("render_policy", {})
        policy["align"] = align_for(fid)
        policy["valign"] = "middle"
        policy["fit"] = "shrink_to_fit"
        policy["overflow"] = "shrink"
        field["notes"] = "ID-04 주민등록등본 생산용 보정 필드. 세대/주소/세대원 정보를 하나의 record로 일관 생성하고 표 grid에 맞춰 bbox를 보정했다."
    return schema


def update_stylesheet(stylesheet: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"ID-04 주민등록등본 style 보정. 원본 정부24 증명서의 명조 계열 출력체와 전체 렌더링/50% overlay/contact sheet 기준으로 {FONT_FAMILY}를 선택했다. crop 비교 루틴은 제외했다.",
        }
    )
    style_classes = stylesheet.setdefault("style_classes", [])
    by_class = {style.get("style_class"): style for style in style_classes}
    for field in schema.get("fields", []):
        style_class = field.get("style_class", f"style_{field['field_id']}")
        if style_class not in by_class:
            by_class[style_class] = {"style_class": style_class, "source_detection_ids": [field.get("source_detection_id", "manual_grid_addition_20260702")]}
            style_classes.append(by_class[style_class])
    for style in style_classes:
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = style_size(fid)
        style["fill"] = [22, 22, 22]
        style["opacity"] = 0.92
        style["align"] = align_for(fid)
        style["valign"] = "middle"
        style["line_spacing"] = 1.0
        style["letter_spacing"] = 0.0
        style["baseline_shift"] = 0
        style["overflow"] = "shrink"
        style["confidence"] = 0.85
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
                {"type": "pick_record", "pool": "id04_resident_register_records", "targets": {fid: fid for fid in field_ids}}
            ],
            "data_pools": {"id04_resident_register_records": make_records()},
            "notes": "ID-04 생산용 profile. 문서확인번호/신청정보/발급일/기관/세대주/주소/세대원 3인을 하나의 세대 record에서 일관 생성한다.",
        }
    )
    return faker


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT), 16) if Path(FONT).exists() else ImageFont.load_default()
    cell_w, cell_h = 170, 250
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 58), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 15), f"id04_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
    font = ImageFont.truetype(str(FONT), 16) if Path(FONT).exists() else ImageFont.load_default()
    scale_w = 170
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
    PROGRESS.write_text(
        f"""# 2026-07-02 ID-04 주민등록등본 파이프라인 준비 작업

## 목표
- `ID-04 주민등록등본`을 단일 순차 대상으로 처리한다.
- 1페이지 세대주/주소/세대원 3인 표 구조를 활용해 bbox를 보정하고 부족한 한자명 bbox를 추가한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: OCR 기반 44개 필드. 한자명 본문은 괄호만 잡혀 있었고 표 grid 대비 일부 bbox가 넓거나 어긋나 있었다.

## 구현 내용
- font-family는 원본 정부24 증명서의 명조/바탕 계열 출력체와 가장 가까운 `{FONT_FAMILY}`로 지정했다.
- `household_head_hanja_value`, `member_1_hanja_value`, `member_2_hanja_value`, `member_3_hanja_value` 4개 필드를 수동 grid bbox로 추가했다.
- 기존 독립 faker 규칙을 `id04_resident_register_records` 단일 record pool로 치환했다.
- 문서확인번호, 신청인/전화/생년월일, 발급일/기관, 주소, 세대 구성/변동일/사유, 세대원 주민등록번호가 같은 record에서 일관 생성된다.
- 표 행/열 기준으로 이름, 주민등록번호, 변동일, 등록상태, 변동사유 bbox를 보정했다.

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
- 정부24 확인용 QR/바코드, 워터마크, 직인은 template의 정적 요소를 유지한다.
- 한자명은 시각 완성도를 위해 bbox를 추가했지만 실제 한자 변환 사전 기반 검증은 후속 validation layer에서 강화할 수 있다.
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
    stylesheet = update_stylesheet(read_json(STYLE_PATH), schema)
    faker = update_faker(schema, read_json(FAKER_PATH))
    write_json(SCHEMA_PATH, schema)
    write_json(STYLE_PATH, stylesheet)
    write_json(FAKER_PATH, faker)

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="id04", clean=True)
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
