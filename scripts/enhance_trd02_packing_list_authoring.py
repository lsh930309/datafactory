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

DOC_ID = "TRD-02"
DOC_TITLE = "포장명세서(Packing List)"
DOC_DIR = ROOT / "workbench" / "documents" / "포장명세서(Packing_List)__TRD-02"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "TRD-02_포장명세서(Packing List)"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "TRD-02_포장명세서(Packing List)"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_trd02_packing_list_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "포장명세서.jpg"
TEMPLATE_SOURCE = DOC_DIR / "inpaint" / "original_포장명세서" / "lama" / "inpainted_lama.png"
TEMPLATE = AUTHORING / "template_trd02_pipeline_ready.png"

FONT_TIMES = Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_TIMES if FONT_TIMES.exists() else FONT_FALLBACK)
FONT_FAMILY = "Times New Roman" if FONT_TIMES.exists() else "Malgun Gothic"
NOW = datetime.now(timezone.utc).isoformat()

SHIPPER_POOL = [
    ("ABC CORPORATION", "120, SAMSUNG-DONG, GANGNAM-GU,", "SEOUL, SOUTH KOREA", "+82-2-000-0000", "+82-2-000-0000", "K. D. HONG / MANAGING DIRECTOR"),
    ("A-ONE MOLDING CO., LTD.", "325 SANDAN-RO, DANWON-GU, ANSAN-SI,", "GYEONGGI-DO, SOUTH KOREA", "+82-31-493-4200", "+82-31-493-4201", "H. S. CHOI / GENERAL MANAGER"),
    ("KOREA TECH PARTS INC.", "77 DIGITAL-RO 9-GIL, GEUMCHEON-GU,", "SEOUL, SOUTH KOREA", "+82-2-867-2190", "+82-2-867-2191", "J. Y. PARK / SALES DIRECTOR"),
    ("DAEJIN INDUSTRIAL CO., LTD.", "41 GONGDAN 2-RO, SEONGSAN-GU,", "CHANGWON, SOUTH KOREA", "+82-55-281-7712", "+82-55-281-7713", "M. K. LEE / EXPORT MANAGER"),
]

BUYERS = [
    ("DEF CORPORATION", "110, FLOWER ROAD,", "NEW YORK, U.S.A", "+1-123-456789", "NEW YORK", "U.S.A"),
    ("TORONTO AUTOMATION LTD", "88 KING STREET WEST,", "TORONTO, CANADA", "+1-416-555-4300", "TORONTO", "CANADA"),
    ("TAIPEI MOTION CO.", "12F, NO. 168, MINSHENG E. ROAD,", "TAIPEI, TAIWAN", "+886-2-2710-5521", "TAIPEI", "TAIWAN"),
    ("HAMBURG TRADING GMBH", "24 HAFENSTRASSE,", "HAMBURG, GERMANY", "+49-40-555-1980", "HAMBURG", "GERMANY"),
]

ITEM_SETS = [
    ("MOTORCYCLE GLOVES", "MG", "PRS", [(1000, 420.0, 500.0, 0.212, "1,200 X 420 X 420 MM", 5), (1000, 420.0, 500.0, 0.212, "1,200 X 420 X 420 MM", 5)]),
    ("MEDICAL SENSOR MODULES", "MSM", "PCS", [(390, 62.4, 78.0, 0.156, "460 X 330 X 340 MM", 3), (600, 108.0, 132.0, 0.290, "500 X 360 X 320 MM", 5)]),
    ("PRECISION MOLD PARTS", "PMP", "PCS", [(240, 135.0, 164.0, 0.188, "580 X 410 X 310 MM", 4), (360, 202.0, 238.0, 0.260, "620 X 420 X 360 MM", 6)]),
    ("AUTO CONTROL SWITCH", "ACS", "PCS", [(800, 76.0, 94.0, 0.144, "520 X 300 X 300 MM", 4), (800, 76.0, 94.0, 0.144, "520 X 300 X 300 MM", 4)]),
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def fmt_float(value: float) -> str:
    return f"{value:,.3f}"


def prepare_template(schema: dict[str, Any]) -> None:
    if not TEMPLATE_SOURCE.exists():
        raise FileNotFoundError(TEMPLATE_SOURCE)
    image = Image.open(TEMPLATE_SOURCE).convert("RGB")
    draw = ImageDraw.Draw(image)
    # LaMa 잔여 흔적이 꽤 많으므로, 동적 bbox 내부만 흰 배경으로 정리한다.
    # 표/테두리/정적 라벨을 보존하기 위해 bbox 안쪽 1px만 사용하고, bbox가 아주 작으면 원래 크기를 유지한다.
    for field in schema.get("fields", []):
        x, y, w, h = [int(v) for v in field["bbox"]]
        inset = 1 if w > 4 and h > 4 else 0
        draw.rectangle([x + inset, y + inset, x + w - inset, y + h - inset], fill=(255, 255, 255))
    draw.rectangle([160, 128, 302, 143], fill=(255, 255, 255))
    draw.rectangle([190, 512, 208, 526], fill=(255, 255, 255))
    TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    image.save(TEMPLATE)


def make_records() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    records: list[dict[str, str]] = []
    for idx in range(12):
        shipper = SHIPPER_POOL[idx % len(SHIPPER_POOL)]
        buyer = BUYERS[idx % len(BUYERS)]
        goods, prefix, unit, items = ITEM_SETS[idx % len(ITEM_SETS)]
        year = 2024 + (idx % 3)
        month_name = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "SEP", "NOV"][idx % 8]
        day = [12, 20, 25, 9, 19, 27][idx % 6]
        no = f"{shipper[0].split()[0][:3].upper()}PI {year}-{idx + 1:03d}"
        bl = f"{prefix}{rng.randrange(10000000,99999999)}"
        seal = f"{prefix}P{rng.randrange(100000,999999)}/EFB{rng.randrange(100000,999999)}"
        total_qty = sum(row[0] for row in items)
        total_net = sum(row[1] for row in items)
        total_gross = sum(row[2] for row in items)
        total_vol = sum(row[3] for row in items)
        total_boxes = sum(row[5] for row in items)
        box_word = "TWO" if total_boxes == 2 else ("EIGHT" if total_boxes == 8 else str(total_boxes))
        record: dict[str, str] = {
            "shipper_exporter_name": shipper[0],
            "shipper_address_line1": shipper[1],
            "shipper_address_line2": shipper[2],
            "shipper_tel": shipper[3],
            "shipper_fax": f"/ FAX : {shipper[4]}",
            "buyer_importer_name": buyer[0],
            "buyer_address_line1": buyer[1],
            "buyer_address_line2": buyer[2],
            "buyer_tel": buyer[3],
            "consignee_name": "SAME AS ABOVE",
            "packing_list_number_date": f"{no}  {month_name} {day}, {year}",
            "notify_party": "SAME AS CONSIGNEE",
            "payment_delivery_1": "1) FREIGHT COLLECT BY OCEAN",
            "payment_delivery_2": f"2) H.S. CODE NO. : {rng.randrange(1000,9999)}-00-{rng.randrange(1000,9999)}",
            "payment_delivery_3": f"3) NO. OF BILL OF LADING : {bl}",
            "port_loading_city": "BUSAN,",
            "port_loading_country": "SOUTH KOREA",
            "final_destination_city": f"{buyer[4]},",
            "final_destination_country": buyer[5],
            "carrier_vessel": f"{rng.choice(['HAPPY VESSEL', 'WAN HAI', 'KMTC BUSAN', 'HMM PROMISE'])} V.{rng.randrange(10,99)}E",
            "sailing_date": f"{month_name} {day + 5 if day < 24 else day}, {year}",
            "shipping_mark_buyer": buyer[0].split()[0],
            "shipping_mark_destination": buyer[4],
            "shipping_mark_carton_range": f"C/NO.1~{total_boxes}",
            "shipping_mark_item_no": "ITEM NO.",
            "description_goods_header": goods,
            "box_1_title": goods,
            "box_2_title": goods,
            "box_1_item_code": f"(1) {prefix}-001",
            "box_2_item_code": f"(1) {prefix}-002",
            "box_1_quantity": f"X {items[0][0]:,} {unit}",
            "box_2_quantity": f"X {items[1][0]:,} {unit}",
            "box_1_carton_breakdown": f"({items[0][0] // items[0][5]:,} {unit} X {items[0][5]} CARTONS)",
            "box_2_carton_breakdown": f"({items[1][0] // items[1][5]:,} {unit} X {items[1][5]} CARTONS)",
            "box_1_net_weight": fmt_float(items[0][1]),
            "box_1_gross_weight": fmt_float(items[0][2]),
            "box_1_volume": fmt_float(items[0][3]),
            "box_1_dimensions": f"({items[0][4]})",
            "box_2_net_weight": fmt_float(items[1][1]),
            "box_2_gross_weight": fmt_float(items[1][2]),
            "box_2_volume": fmt_float(items[1][3]),
            "box_2_dimensions": f"({items[1][4]})",
            "total_trade_terms": ": FOB BUSAN, SOUTH KOREA",
            "total_net_weight": fmt_float(total_net),
            "total_gross_weight": fmt_float(total_gross),
            "total_volume": fmt_float(total_vol),
            "net_weight_unit": "KGS",
            "gross_weight_unit": "KGS",
            "volume_unit": "CBM",
            "package_summary": f"{box_word} ({total_boxes}) BOXES OF {goods}",
            "say_package_only": f"*SAY: {box_word} ({total_boxes}) BOXES ONLY.",
            "container_seal_no": f"* CONTAINER & SEAL NO. : {seal}",
            "origin_country_statement": "* ORIGIN OF COUNTRY : REPUBLIC OF KOREA (R.O.K)",
            "footer_company_name": shipper[0],
            "footer_tel": shipper[3],
            "footer_fax": shipper[4],
            "signed_by_name": shipper[5],
        }
        records.append(record)
    return records


def style_size(field_id: str) -> int:
    if field_id in {"footer_company_name"}:
        return 20
    if field_id in {"signed_by_name"}:
        return 12
    if field_id.startswith(("shipper_", "buyer_")) or field_id in {"notify_party", "consignee_name"}:
        return 11
    if field_id.startswith("payment_delivery"):
        return 11
    if field_id in {"port_loading_city", "port_loading_country", "final_destination_city", "final_destination_country", "carrier_vessel", "sailing_date"}:
        return 11
    if field_id.startswith("shipping_mark") or field_id == "description_goods_header":
        return 11
    if field_id.startswith("box_"):
        return 10
    if field_id.startswith("total_") or field_id.endswith("_unit"):
        return 10
    if field_id in {"package_summary"}:
        return 10
    if field_id in {"say_package_only", "container_seal_no", "origin_country_statement"}:
        return 10
    if field_id in {"packing_list_number_date"}:
        return 11
    return 10


def align_for(field_id: str) -> str:
    if field_id in {"port_loading_city", "port_loading_country", "final_destination_city", "final_destination_country", "carrier_vessel", "sailing_date", "package_summary", "footer_company_name", "signed_by_name"}:
        return "center"
    if field_id.endswith(("weight", "volume")) or field_id in {"total_net_weight", "total_gross_weight", "total_volume"}:
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
            "authoring_mode": "trd02_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    bbox_overrides = {
        "shipper_fax": [165, 128, 135, 15],
        "box_1_title": [178, 426, 122, 14],
        "box_2_title": [178, 469, 122, 14],
        "total_trade_terms": [190, 513, 160, 12],
        "footer_company_name": [466, 738, 190, 25],
        "signed_by_name": [470, 831, 214, 20],
    }
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:trd02_packing_list_records.{fid}"
        if fid in bbox_overrides:
            field["bbox"] = bbox_overrides[fid]
        policy = field.setdefault("render_policy", {})
        policy["align"] = align_for(fid)
        policy["valign"] = "middle"
        policy["fit"] = "shrink_to_fit"
        policy["overflow"] = "shrink"
        field["notes"] = "TRD-02 포장명세서 생산용 보정 필드. 수출자/수입자/선적/박스별 중량·부피·포장 수량을 record 기반으로 일관 생성."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"TRD-02 포장명세서 style 보정. 원본은 스캔된 영문 무역 서식의 Times 계열 serif이므로 전체 렌더링 결과를 기준으로 {FONT_FAMILY}을 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다.",
        }
    )
    for style in stylesheet.get("style_classes", []):
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = style_size(fid)
        style["fill"] = [18, 18, 18]
        style["opacity"] = 0.92
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
            "locale": "en_US",
            "field_generators": {fid: "literal:" for fid in field_ids},
            "constraints": [
                {
                    "type": "pick_record",
                    "pool": "trd02_packing_list_records",
                    "targets": {fid: fid for fid in field_ids},
                }
            ],
            "data_pools": {"trd02_packing_list_records": make_records()},
            "notes": "TRD-02 생산용 profile. 포장명세서의 shipper/buyer/shipping/box/weight/volume/package summary를 하나의 record로 생성하며 box totals와 package count가 일치한다.",
        }
    )
    return faker


def build_semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    field_mapping = {
        str(field["field_id"]): field.get("export", {}).get("json_path", field["field_id"])
        for field in schema.get("fields", [])
    }
    box_row = {
        "box_title": "",
        "item_code": "",
        "quantity": "",
        "carton_breakdown": "",
        "net_weight": "",
        "gross_weight": "",
        "volume": "",
        "dimensions": "",
    }
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "purpose": "렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조",
        "semantic_schema": {
            "포장명세서(Packing List)": {
                "Shipper/Exporter": {
                    "name": "",
                    "address_line1": "",
                    "address_line2": "",
                    "tel": "",
                    "fax": "",
                },
                "Buyer/Importer/Applicant": {
                    "name": "",
                    "address_line1": "",
                    "address_line2": "",
                    "tel": "",
                },
                "Consignee": "",
                "Packing List": {
                    "number_and_date": "",
                    "notify_party": "",
                    "terms_of_payment_and_delivery": [],
                },
                "Shipment": {
                    "port_of_loading": {"city": "", "country": ""},
                    "final_destination": {"city": "", "country": ""},
                    "carrier_vessel": "",
                    "sailing_date": "",
                },
                "Shipping Mark": {
                    "buyer": "",
                    "destination": "",
                    "carton_range": "",
                    "item_no": "",
                },
                "Description of Goods or Services": {
                    "header": "",
                    "boxes": [box_row],
                    "total_trade_terms": "",
                },
                "Totals": {
                    "net_weight": "",
                    "gross_weight": "",
                    "volume": "",
                    "net_weight_unit": "",
                    "gross_weight_unit": "",
                    "volume_unit": "",
                    "package_summary": "",
                    "say_package_only": "",
                    "container_seal_no": "",
                    "origin_country_statement": "",
                },
                "Footer": {
                    "company_name": "",
                    "tel": "",
                    "fax": "",
                    "signed_by": "",
                },
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "schema.json은 renderer 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 포장명세서의 KIE label 구조만 계층형으로 표현한다.",
            "박스 상세는 실제 렌더링에서 2개 box로 생성되지만 의미 schema에서는 반복 row 구조로 표현한다.",
        ],
    }


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT), 14) if Path(FONT).exists() else ImageFont.load_default()
    cell_w, cell_h = 150, 190
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 52), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 12), f"trd02_{idx + 1:06d}", font=font, fill=(30, 30, 30))
        image = Image.open(path).convert("RGB")
        image.thumbnail((cell_w - 16, cell_h - 28))
        y = 36
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
    scale_w = 155
    sheet = Image.new("RGB", (scale_w * len(labels) + 14 * (len(labels) + 1), 245), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(labels):
        thumb = image.copy()
        thumb.thumbnail((scale_w, 190))
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
        f"""# 2026-07-02 TRD-02 포장명세서(Packing List) 파이프라인 준비 작업

## 목표
- `TRD-02 포장명세서(Packing List)`를 단일 순차 대상으로 처리한다.
- 1페이지 57개 필드 기반으로 수출자/수입자/선적/박스별 중량·부피·포장 수량을 일관 생성한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa source template: `{TEMPLATE_SOURCE}`
- authoring derived template: `{TEMPLATE}`
- 기존 authoring: 1페이지 57개 필드. 기존 LaMa 템플릿에는 값 잔여 흔적이 다수 남아 있었다.

## 구현 내용
- font-family는 원본 스캔 영문 무역서식의 serif 계열 시각 정보에 가장 가까운 `{FONT_FAMILY}`로 지정했다.
- 기존 독립 faker 규칙을 `trd02_packing_list_records` 단일 record pool로 치환했다.
- 파생 템플릿 생성 시 모든 동적 bbox 내부를 흰 배경으로 정리하여 기존 OCR/LaMa 잔여 텍스트가 새 렌더와 겹치지 않도록 했다.
- 박스별 net/gross/volume, 총합, package summary, carton range가 같은 record에서 일관되게 생성된다.
- 중량/부피 수치는 right, 목적지/선박/하단 회사명은 center, 주소/조건/설명은 left 정렬로 고정했다.

## 산출물
- schema: `{SCHEMA_PATH}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
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
- semantic field mapping: {summary.get('semantic_field_mapping_count')}

## 한계 및 다음 조치
- 서명 필기 이미지는 원본 template의 정적 요소를 유지한다.
- 원본 스캔 노이즈/희미한 선은 template 고유 품질이므로, 필요 시 cleanup mask 후처리로 추가 개선할 수 있다.
""",
        encoding="utf-8",
    )


def main() -> None:
    for path in [SCHEMA_PATH, STYLE_PATH, FAKER_PATH, ORIGINAL, TEMPLATE_SOURCE]:
        if not path.exists():
            raise FileNotFoundError(path)
    base_schema = read_json(SCHEMA_PATH)
    prepare_template(base_schema)
    if CALIB_DIR.exists():
        shutil.rmtree(CALIB_DIR)
    schema = update_schema(base_schema)
    stylesheet = update_stylesheet(read_json(STYLE_PATH))
    faker = update_faker(schema, read_json(FAKER_PATH))
    write_json(SCHEMA_PATH, schema)
    write_json(STYLE_PATH, stylesheet)
    write_json(FAKER_PATH, faker)
    semantic_schema = build_semantic_schema(schema)
    write_json(SEMANTIC_SCHEMA, semantic_schema)

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="trd02", clean=True)
    contact = make_contact_sheet([sample.image for sample in batch.samples])
    comparison = compare(preview.image)
    summary = read_json(batch.summary)
    summary["page_count"] = 1
    summary["field_count_per_sample"] = summary.get("field_count")
    summary["contact_sheet"] = str(contact)
    summary["style_comparison"] = str(comparison)
    summary["semantic_schema"] = str(SEMANTIC_SCHEMA)
    summary["semantic_field_mapping_count"] = len(semantic_schema["field_mapping"])
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
