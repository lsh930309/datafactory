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

DOC_ID = "TRD-07"
DOC_TITLE = "발주서(PO)·거래명세서"
DOC_DIR = ROOT / "workbench" / "documents" / "발주서(PO)·거래명세서__TRD-07"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "TRD-07_발주서(PO)·거래명세서"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "TRD-07_발주서(PO)·거래명세서"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_trd07_purchase_order_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "발주서_page_001.jpg"
TEMPLATE_SOURCE = DOC_DIR / "inpaint" / "original_발주서_page_001" / "lama" / "inpainted_lama.png"
TEMPLATE = AUTHORING / "template_trd07_pipeline_ready.png"

FONT_MALGUN = ROOT / "fonts" / "malgun.ttf"
FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = FONT_APPLE if FONT_APPLE.exists() else ROOT / "fonts" / "gulim.ttc"
FONT = str(FONT_MALGUN if FONT_MALGUN.exists() else FONT_FALLBACK)
FONT_FAMILY = "Malgun Gothic" if FONT_MALGUN.exists() else ("AppleSDGothicNeo" if FONT_APPLE.exists() else "Gulim")
NOW = datetime.now(timezone.utc).isoformat()

BUYERS = [
    ("아남정밀", "정창식 사장님", "010-3873-7636", "055-246-2951", "경남 창원시 마산합포구 문화동 3길 14"),
    ("우림산업", "장현우 사장님", "010-3365-1455", "055-256-5192", "울산 북구 매곡산업로 35"),
    ("대성정밀", "박기현 부장", "010-7312-8841", "055-264-2078", "경남 김해시 진례면 테크노밸리로 91"),
    ("한울테크", "김민석 대표", "010-4920-1186", "053-742-6105", "대구 달서구 성서공단로 217"),
    ("세진금형", "이도윤 팀장", "010-5804-2269", "032-811-7044", "인천 남동구 남동대로 239"),
]

SENDERS = [
    ("㈜고려이노테크", "구매팀 정규현 대리", "055-242-6196(328)", "055-245-3123", "gyuhyun@kinno.co.kr", "경남 창원시 마산합포구 진북면 산단1길 5", "고려이노테크 진북공장"),
    ("(주)우림엔지니어링", "구매팀 장우진 대리", "055-245-3685(305)", "055-268-6836", "woojin@kinno.co.kr", "경북 구미시 1공단로 212", "우림엔지니어링 진북공장"),
    ("대영정공 주식회사", "자재팀 김소연 과장", "055-271-4308(210)", "055-271-4310", "soyoun@dytech.co.kr", "경남 창원시 성산구 공단로 88", "대영정공 제2공장"),
    ("주식회사 태림오토", "구매관리팀 최민재", "055-289-6120(114)", "055-289-6129", "minjae@taelimauto.co.kr", "경남 함안군 칠원읍 용산2길 41", "태림오토 칠원공장"),
]

ITEM_SETS = [
    [
        ("Side Retainer Core 직경 및 길이 검사용 Jig 폭 76.3mm*길이 100mm", 1, 60000, "ASAP"),
        ("Side Retainer Core 직경 및 길이 검사용 Jig 폭 77.7mm*길이 100mm", 1, 60000, "ASAP"),
        ("Side Retainer Core 직경 및 길이 검사용 Jig 폭 76.3mm*길이 120mm", 1, 60000, "ASAP"),
        ("Side Retainer Core 직경 및 길이 검사용 Jig 폭 77.7mm*길이 120mm", 1, 60000, "ASAP"),
    ],
    [
        ("Cooling Plate 알루미늄 가공품", 3, 150000, "1/10"),
        ("Cylinder Mount Block", 4, 30000, "1/17"),
        ("Linear Guide Base Plate", 1, 45000, "협의"),
        ("Robot Gripper Finger L형", 2, 60000, "납기준수"),
    ],
    [
        ("Guide Pin Holder SCM440 열처리품", 2, 85000, "2/05"),
        ("Inspection Jig Base 250*180*20T", 1, 180000, "2/12"),
        ("Bracket Assy 용접 후 가공", 6, 42000, "2/12"),
        ("Sensor Plate SUS304 2T", 10, 18000, "ASAP"),
    ],
    [
        ("금형 코어블록 SKD61 정삭가공", 1, 420000, "3/08"),
        ("Locator Pin Ø12 H7", 12, 9500, "3/08"),
        ("Support Block 흑착색", 4, 36000, "3/15"),
        ("검사용 마스터 샘플", 1, 75000, "협의"),
    ],
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def krw(value: int) -> str:
    return f"{value:,}"


def prepare_template() -> None:
    if not TEMPLATE_SOURCE.exists():
        raise FileNotFoundError(TEMPLATE_SOURCE)
    image = Image.open(TEMPLATE_SOURCE).convert("RGB")
    draw = ImageDraw.Draw(image)
    # PO 번호 inpaint 잔여 흔적만 제거. 테두리와 'PO NO. :' 정적 문구는 유지한다.
    draw.rectangle([828, 136, 964, 153], fill=(255, 255, 255))
    TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    image.save(TEMPLATE)


def make_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    rng = random.Random(20260702)
    for idx in range(12):
        buyer = BUYERS[idx % len(BUYERS)]
        sender = SENDERS[idx % len(SENDERS)]
        items = ITEM_SETS[idx % len(ITEM_SETS)]
        month = [11, 12, 1, 2, 3, 4][idx % 6]
        day = [16, 9, 24, 5, 8, 18][idx % 6]
        yy = 24 + (idx % 2)
        total = sum(qty * unit for _, qty, unit, _ in items)
        record: dict[str, str] = {
            "purchase_order_number": f"P{yy:02d}{month:02d}{day:02d}-{rng.randrange(10, 99)}",
            "receiver_company_name": buyer[0],
            "receiver_contact_title": buyer[1],
            "receiver_tel": buyer[2],
            "receiver_fax": buyer[3],
            "receiver_address": buyer[4],
            "sender_company_name": sender[0],
            "sender_department_contact": sender[1],
            "sender_tel": sender[2],
            "sender_fax": sender[3],
            "sender_email": sender[4],
            "sender_address": sender[5],
            "prepared_date": f"{month}/{day}",
            "reviewed_date": f"{month}/{day}",
            "approved_date": f"{month}/{day}",
            "shipping_address": f"발송지 : {sender[5]}",
            "delivery_site_name": sender[6],
            "supply_total_amount": krw(total),
            "form_code": f"KIT-QP-S09-{idx % 7 + 1:02d}_Rev.{idx % 3}",
            "issuer_company_footer": sender[0],
        }
        for line_no, (desc, qty, unit, due) in enumerate(items, start=1):
            record[f"line_{line_no}_number"] = str(line_no)
            record[f"line_{line_no}_item_description"] = desc
            record[f"line_{line_no}_quantity"] = str(qty)
            record[f"line_{line_no}_unit_price"] = krw(unit)
            record[f"line_{line_no}_amount"] = krw(qty * unit)
            record[f"line_{line_no}_due_date"] = due
        record["line_2_remark"] = ["Core 직경 및\n길이 검사용", "표면처리 포함", "검사성적서 첨부", "도면 최신 Rev 기준"][idx % 4]
        records.append(record)
    return records


def style_size(field_id: str) -> int:
    if field_id == "purchase_order_number":
        return 20
    if field_id in {"receiver_company_name", "sender_company_name", "receiver_contact_title", "sender_department_contact"}:
        return 22
    if field_id in {"receiver_tel", "sender_tel", "receiver_fax", "sender_fax", "sender_email", "receiver_address", "sender_address"}:
        return 20
    if field_id in {"prepared_date", "reviewed_date", "approved_date"}:
        return 22
    if field_id.endswith("_item_description"):
        return 20
    if field_id.endswith(("_quantity", "_unit_price", "_amount", "_due_date")):
        return 20
    if field_id.endswith("_number"):
        return 20
    if field_id == "line_2_remark":
        return 22
    if field_id in {"shipping_address", "delivery_site_name"}:
        return 22
    if field_id == "supply_total_amount":
        return 21
    if field_id in {"form_code", "issuer_company_footer"}:
        return 17
    return 20


def align_for(field_id: str) -> str:
    if field_id.endswith(("_number", "_quantity", "_due_date")) or field_id in {"purchase_order_number", "prepared_date", "reviewed_date", "approved_date", "line_2_remark", "delivery_site_name", "issuer_company_footer"}:
        return "center"
    if field_id.endswith(("_unit_price", "_amount")) or field_id == "supply_total_amount":
        return "right"
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
            "authoring_mode": "trd07_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    bbox_overrides = {
        "purchase_order_number": [824, 130, 146, 28],
        "shipping_address": [166, 815, 530, 31],
        "delivery_site_name": [304, 869, 250, 31],
    }
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:trd07_purchase_order_records.{fid}"
        if fid in bbox_overrides:
            field["bbox"] = bbox_overrides[fid]
        policy = field.setdefault("render_policy", {})
        policy["align"] = align_for(fid)
        policy["valign"] = "middle"
        policy["fit"] = "shrink_to_fit"
        policy["overflow"] = "shrink"
        field["notes"] = "TRD-07 발주서 생산용 보정 필드. 발주처/수신처/품목/수량/단가/금액/합계를 record 기반으로 일관 생성."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"TRD-07 발주서 style 보정. 원본은 Windows/Excel 기반 문서처럼 보이는 굵은 고딕 계열이므로 전체 렌더링 결과를 기준으로 {FONT_FAMILY}를 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다.",
        }
    )
    for style in stylesheet.get("style_classes", []):
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = style_size(fid)
        style["fill"] = [25, 25, 25]
        style["opacity"] = 0.94
        style["align"] = align_for(fid)
        style["valign"] = "middle"
        style["line_spacing"] = 1.05
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
                    "pool": "trd07_purchase_order_records",
                    "targets": {fid: fid for fid in field_ids},
                }
            ],
            "data_pools": {"trd07_purchase_order_records": make_records()},
            "notes": "TRD-07 생산용 profile. 발주번호, 수신처, 발신처, 품목 4행, 금액 합계, 배송지를 하나의 record로 생성하며 line amount = quantity * unit_price, supply_total = sum(line amount)를 만족한다.",
        }
    )
    return faker



def build_semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    field_mapping = {
        field["field_id"]: field.get("export", {}).get("json_path", field["field_id"])
        for field in schema.get("fields", [])
    }
    item_row = {
        "번호": "",
        "품명 및 규격": "",
        "수량": "",
        "단가": "",
        "금액": "",
        "납기": "",
        "비고": "",
    }
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "purpose": "렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조",
        "semantic_schema": {
            "발주서(PO)·거래명세서": {
                "문서 정보": {"발주번호": ""},
                "수신처": {"회사명": "", "참조": "", "전화번호": "", "팩스번호": "", "주소": ""},
                "발신처": {"회사명": "", "부서 및 담당자": "", "전화번호": "", "팩스번호": "", "이메일": "", "주소": ""},
                "결재": {"작성일": "", "검토일": "", "승인일": ""},
                "품목 내역": [item_row],
                "배송 정보": {"발송지": "", "납품처": ""},
                "합계": {"공급가": "", "VAT": "별도"},
                "푸터": {"서식코드": "", "발행회사": ""},
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "schema.json은 렌더러 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 KIE용 key-name 계층만 별도 관리한다.",
            "금액 관계는 faker profile의 record 생성 단계에서 line amount 및 supply total로 보장한다.",
        ],
    }

def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT), 16) if Path(FONT).exists() else ImageFont.load_default()
    cell_w, cell_h = 235, 170
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 58), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 15), f"trd07_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
    scale_w = 260
    sheet = Image.new("RGB", (scale_w * len(labels) + 18 * (len(labels) + 1), 260), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(labels):
        thumb = image.copy()
        thumb.thumbnail((scale_w, 200))
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
        f"""# 2026-07-02 TRD-07 발주서(PO)·거래명세서 파이프라인 준비 작업

## 목표
- `TRD-07 발주서(PO)·거래명세서`를 단일 순차 대상으로 처리한다.
- 1페이지 45개 필드 기반으로 발주번호, 수신/발신 정보, 품목 4행, 배송지, 공급가 합계가 일관 생성되도록 한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa source template: `{TEMPLATE_SOURCE}`
- authoring derived template: `{TEMPLATE}`
- 기존 authoring: 1페이지 45개 필드, preview 동작 가능 상태.

## 구현 내용
- font-family는 Windows/Excel류 발주서의 고딕 계열 시각 정보에 가장 가까운 `{FONT_FAMILY}`로 지정했다.
- 기존 독립 faker 규칙을 `trd07_purchase_order_records` 단일 record pool로 치환했다.
- 품목별 `amount = quantity * unit_price`, `supply_total = sum(amount)` 관계를 record 생성 단계에서 고정했다.
- KIE용 key-name 계층은 `semantic_schema.json`으로 분리했다.
- PO 번호 연도 토큰은 2024~2025 범위로 제한했다.
- 기존 inpaint 템플릿의 PO 번호 잔여 흔적은 파생 템플릿에서 제거하고, 발주번호 bbox를 약간 확장했다.
- 금액은 right, 날짜/수량/번호/납기/승인란은 center, 회사명/주소/품목명은 left 정렬로 고정했다.

## 산출물
- schema: `{SCHEMA_PATH}`
- stylesheet: `{STYLE_PATH}`
- faker_profile: `{FAKER_PATH}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
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
- 상단 로고와 발주조건 문구는 원본 template의 정적 요소를 유지한다.
- 비고란은 현재 OCR/review에서 잡힌 1개 병합 셀만 동적화했다. 필요 시 후속 bbox 편집으로 비고 행/열을 추가 확장할 수 있다.
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
    write_json(SEMANTIC_SCHEMA, build_semantic_schema(schema))

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="trd07", clean=True)
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
