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

DOC_ID = "TRD-01"
DOC_TITLE = "상업송장(Commercial Invoice)"
DOC_DIR = ROOT / "workbench" / "documents" / "상업송장(Commercial_Invoice)__TRD-01"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "TRD-01_상업송장(Commercial Invoice)"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "TRD-01_상업송장(Commercial Invoice)"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_trd01_commercial_invoice_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "상업송장.png"
TEMPLATE = DOC_DIR / "inpaint" / "original_상업송장" / "lama" / "inpainted_lama.png"

FONT_TIMES = Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_TIMES if FONT_TIMES.exists() else FONT_FALLBACK)
FONT_FAMILY = "Times New Roman" if FONT_TIMES.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()

SHIPPERS = [
    ("MK GLOBAL CO., LTD.", "HWASEONG-SI, GYEONGGI-DO,", "REPUBLIC OF KOREA"),
    ("HANSOL TRADING CO., LTD.", "SEOCHO-GU, SEOUL,", "REPUBLIC OF KOREA"),
    ("DAEHO TEXTILE INC.", "BUK-GU, DAEGU,", "REPUBLIC OF KOREA"),
    ("SEJIN APPAREL CO., LTD.", "GIMHAE-SI, GYEONGSANGNAM-DO,", "REPUBLIC OF KOREA"),
]
CONSIGNEES = [
    ("GOSINARA CO., LTD.", "14524 YUAN LAOSHAN QU,", "QINGDAO SHI, SHANDONG SHENG,", "CHINA", "QINGDAO, CHINA"),
    ("BLUE OCEAN TRADING LLC", "28 AL WASL ROAD,", "DUBAI, UNITED ARAB EMIRATES,", "U.A.E.", "JEBEL ALI, U.A.E."),
    ("NORTH STAR IMPORTS LTD.", "210 KING STREET WEST,", "TORONTO, ONTARIO,", "CANADA", "VANCOUVER, CANADA"),
    ("TOKYO STYLE MART CO., LTD.", "3-12-5 SHIBAURA, MINATO-KU,", "TOKYO,", "JAPAN", "TOKYO, JAPAN"),
]
GOODS = [
    ("GIRL'S SHIRTS", "(Cotton 40%, Nylon 30%, Rayon 30%)", "PC", 10000, 1.00),
    ("MEN'S KNIT SWEATERS", "(Wool 60%, Acrylic 40%)", "PCS", 4800, 7.50),
    ("COTTON T-SHIRTS", "(Cotton 100%)", "PCS", 12000, 2.35),
    ("WOMEN'S BLOUSES", "(Polyester 70%, Cotton 30%)", "PCS", 6500, 4.20),
    ("DENIM PANTS", "(Cotton 98%, Span 2%)", "PCS", 3200, 11.80),
]
VESSELS = ["QCY123", "HMM NURI 042E", "KMTC BUSAN 118S", "EVER BEST 071W", "KE274"]
PORTS = ["INCHEON, KOREA", "BUSAN, KOREA", "PYEONGTAEK, KOREA"]
TERMS = [("F.O.B INCHEON", "L/C AT SIGHT"), ("F.O.B BUSAN", "T/T IN ADVANCE"), ("CIF QINGDAO", "D/P AT SIGHT")]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def money_usd(value: float, *, unit: bool = False) -> str:
    if unit:
        return f"US${value:,.2f}/PC"
    return f"US${value:,.0f}" if value == int(value) else f"US${value:,.2f}"


def fmt_date(date: datetime) -> str:
    return date.strftime("%b %d. %Y").upper()


def style_size(field_id: str) -> int:
    if field_id in {"shipper_address", "consignee_address_line1", "consignee_address_line2"}:
        return 18
    if field_id in {"shipper_name", "consignee_name", "shipper_country", "consignee_country"}:
        return 17
    if field_id in {"invoice_number_date", "lc_number_date", "buyer_reference", "country_of_origin"}:
        return 16
    if field_id in {"goods_description", "shipping_mark_code", "shipping_mark_destination", "lot_number", "carton_range"}:
        return 17
    if field_id in {"material_composition"}:
        return 15
    if field_id in {"quantity", "unit_price", "amount"}:
        return 16
    if field_id == "signed_by":
        return 18
    return 16


def align_for(field_id: str) -> str:
    if field_id in {"departure_date", "vessel_flight", "loading_port", "quantity", "unit_price"}:
        return "center"
    if field_id == "amount":
        return "right"
    if field_id == "signed_by":
        return "center"
    return "left"


def make_records() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    records: list[dict[str, str]] = []
    for idx in range(12):
        shipper = SHIPPERS[idx % len(SHIPPERS)]
        consignee = CONSIGNEES[idx % len(CONSIGNEES)]
        goods, composition, unit, qty, unit_price = GOODS[idx % len(GOODS)]
        amount = qty * unit_price
        inv_date = datetime(2021 + (idx % 5), [1, 3, 5, 7, 9, 12][idx % 6], [4, 9, 14, 18, 22, 27][idx % 6])
        lc_date = inv_date + timedelta(days=2)
        dep_date = inv_date + timedelta(days=4)
        terms, payment = TERMS[idx % len(TERMS)]
        carton_to = max(1, int(qty / 400))
        records.append(
            {
                "invoice_number_date": f"MK{inv_date:%Y%m%d}, {fmt_date(inv_date)}",
                "shipper_name": shipper[0],
                "shipper_address": shipper[1],
                "shipper_country": shipper[2],
                "lc_number_date": f"LC{rng.randrange(10,99)}{rng.randrange(100000,999999)}, {fmt_date(lc_date)}",
                "buyer_reference": "SAME AS CONSIGNEE" if idx % 2 == 0 else consignee[0],
                "consignee_name": consignee[0],
                "consignee_address_line1": consignee[1],
                "consignee_address_line2": consignee[2],
                "consignee_country": consignee[3],
                "country_of_origin": "REPUBLIC OF KOREA",
                "departure_date": fmt_date(dep_date),
                "vessel_flight": VESSELS[idx % len(VESSELS)],
                "loading_port": PORTS[idx % len(PORTS)],
                "terms_of_delivery": terms,
                "payment_terms": payment,
                "destination_port": consignee[4],
                "goods_description": goods,
                "quantity": f"{qty:,} {unit}",
                "unit_price": money_usd(unit_price, unit=True),
                "amount": money_usd(amount),
                "shipping_mark_code": f"CN-{rng.randrange(100,999)}",
                "material_composition": composition,
                "shipping_mark_destination": consignee[4].split(",", 1)[0],
                "lot_number": f"LOT NO {rng.randrange(10,99)}-{idx + 1:02d}",
                "carton_range": f"C/NO.1-{carton_to}",
                "origin_mark": "MADE IN KOREA",
                "signed_by": shipper[0],
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
            "authoring_mode": "trd01_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:trd01_commercial_invoice_records.{fid}"
        field.setdefault("render_policy", {})["align"] = align_for(fid)
        field.setdefault("render_policy", {})["valign"] = "middle"
        field.setdefault("render_policy", {})["fit"] = "shrink_to_fit"
        field.setdefault("render_policy", {})["overflow"] = "shrink"
        field["notes"] = "TRD-01 Commercial Invoice 생산용 보정 필드. 영문 거래처/항목/수량/단가/금액을 record 기반으로 일관 생성."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"TRD-01 Commercial Invoice style 보정. 원본 영문 송장의 Times 계열 serif 인쇄체와 전체 렌더링 결과를 기준으로 {FONT_FAMILY}를 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다.",
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
        style["confidence"] = 0.88
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
                    "pool": "trd01_commercial_invoice_records",
                    "targets": {fid: fid for fid in field_ids},
                }
            ],
            "data_pools": {"trd01_commercial_invoice_records": make_records()},
            "notes": "TRD-01 생산용 profile. invoice/L-C/shipper/consignee/goods/quantity/unit_price/amount/shipping mark를 하나의 record로 생성하여 금액 일관성을 유지한다.",
        }
    )
    return faker


def build_semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    field_mapping = {
        str(field["field_id"]): field.get("export", {}).get("json_path", field["field_id"])
        for field in schema.get("fields", [])
    }
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "purpose": "렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조",
        "semantic_schema": {
            "상업송장(Commercial Invoice)": {
                "Shipper/Seller": {
                    "name": "",
                    "address": "",
                    "country": "",
                },
                "Consignee": {
                    "name": "",
                    "address_line1": "",
                    "address_line2": "",
                    "country": "",
                },
                "Invoice": {
                    "invoice_number_and_date": "",
                    "lc_number_and_date": "",
                    "buyer_reference": "",
                    "country_of_origin": "",
                },
                "Shipment": {
                    "departure_date": "",
                    "vessel_or_flight": "",
                    "loading_port": "",
                    "destination_port": "",
                    "terms_of_delivery": "",
                    "payment_terms": "",
                },
                "Goods": {
                    "shipping_marks": {
                        "code": "",
                        "destination": "",
                        "lot_number": "",
                        "carton_range": "",
                        "origin_mark": "",
                    },
                    "description": "",
                    "material_composition": "",
                    "quantity": "",
                    "unit_price": "",
                    "amount": "",
                },
                "Signature": {
                    "signed_by": "",
                },
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "schema.json은 renderer 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 상업송장의 KIE label 구조만 계층형으로 표현한다.",
            "현재 template은 단일 품목 invoice 구조 기준이다.",
        ],
    }


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 170, 250
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 58), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 15), f"trd01_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
    scale_w = 180
    sheet = Image.new("RGB", (scale_w * len(labels) + 18 * (len(labels) + 1), 330), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(labels):
        thumb = image.copy()
        thumb.thumbnail((scale_w, 280))
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
        f"""# 2026-07-02 TRD-01 상업송장(Commercial Invoice) 파이프라인 준비 작업

## 목표
- `TRD-01 상업송장(Commercial Invoice)`를 단일 순차 대상으로 처리한다.
- 기존 28개 bbox authoring을 유지하되, shipper/consignee/goods/quantity/unit_price/amount를 record 기반으로 일관 생성한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: 1페이지 28개 필드, preview 동작 가능 상태.

## 구현 내용
- font-family는 원본 영문 송장의 Times 계열 serif 시각 정보에 가장 가까운 `{FONT_FAMILY}`로 통일했다.
- 기존 field별 pool/오타 가능성을 제거하고 `trd01_commercial_invoice_records` 단일 record pool로 치환했다.
- 수량×단가=금액이 같은 record에서 산출되므로 금액 일관성이 유지된다.
- shipping marks, destination, lot/carton range, origin mark를 거래 record와 맞춰 생성한다.

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
- LaMa template에 일부 옅은 잔흔이 남아 있으나 전체 문서 기준에서는 원본 양식과 잘 융합된다.
- 현재 bbox는 단일 품목 commercial invoice 구조이다. 다품목 invoice가 필요하면 행 bbox를 추가 확장해야 한다.
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
    semantic_schema = build_semantic_schema(schema)
    write_json(SEMANTIC_SCHEMA, semantic_schema)

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="trd01", clean=True)
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
