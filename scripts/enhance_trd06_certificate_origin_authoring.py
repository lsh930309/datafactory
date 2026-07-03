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

DOC_ID = "TRD-06"
DOC_TITLE = "원산지증명서(C/O)"
DOC_DIR = ROOT / "workbench" / "documents" / "원산지증명서(C_O)__TRD-06"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "TRD-06_원산지증명서(C／O)"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "TRD-06_원산지증명서(C／O)"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_trd06_certificate_origin_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "원산지증명서_page_001.jpg"
TEMPLATE_SOURCE = DOC_DIR / "inpaint" / "original_원산지증명서_page_001" / "lama" / "inpainted_lama.png"
TEMPLATE = AUTHORING / "template_trd06_pipeline_ready.png"

FONT_TIMES = Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_TIMES if FONT_TIMES.exists() else FONT_FALLBACK)
FONT_FAMILY = "Times New Roman" if FONT_TIMES.exists() else "Malgun Gothic"
NOW = datetime.now(timezone.utc).isoformat()

EXPORTERS = [
    ("YesForm Co., Ltd.", "export@yesform.co.kr", "+82-2-123-4567", "+82-2-123-4568", "123 Yes Street, Yes-gu, Seoul, Republic of Korea"),
    ("SEORIN CHEMICAL CO., LTD.", "overseas@seorinchem.co.kr", "+82-42-935-8800", "+82-42-935-8801", "33 TECHNO 2-RO, YUSEONG-GU, DAEJEON, REPUBLIC OF KOREA"),
    ("DAEJIN INDUSTRIAL CO., LTD.", "trade@dae-jin.co.kr", "+82-55-281-7712", "+82-55-281-7713", "41 GONGDAN 2-RO, SEONGSAN-GU, CHANGWON, REPUBLIC OF KOREA"),
    ("KOREA MEDITECH INC.", "export@kmeditech.kr", "+82-31-493-4200", "+82-31-493-4201", "325 SANDAN-RO, DANWON-GU, ANSAN, REPUBLIC OF KOREA"),
]

PRODUCERS = [
    ("Yes Manufacturing Co.", "producer@yesmfg.co.kr", "+82-32-456-7890", "+82-32-456-7891", "456 Yes Industrial Park, Incheon, Republic of Korea"),
    ("SMART FACTORY SOLUTIONS INC.", "producer@sfs-korea.co.kr", "+82-70-4210-6300", "+82-70-4210-6301", "235 PANGYO-RO, SEONGNAM-SI, REPUBLIC OF KOREA"),
    ("HANBIT PRECISION WORKS", "mfg@hanbitprecision.kr", "+82-55-266-1400", "+82-55-266-1401", "19 TECHVALLEY 4-GIL, GIMHAE, REPUBLIC OF KOREA"),
]

IMPORTERS = [
    ("Nono Wholesale Inc.", "imports@nonowholesale.com", "+1-213-987-6543", "+1-213-987-6544", "789 Trade Ave, Nono City, CA, USA"),
    ("DUBAI SYSTEMS FZE", "trade@dubaisystems.ae", "+971-4-884-3200", "+971-4-884-3201", "JEBEL ALI FREE ZONE, DUBAI, U.A.E"),
    ("TORONTO AUTOMATION LTD", "imports@torontoauto.ca", "+1-416-555-4300", "+1-416-555-4301", "88 KING STREET WEST, TORONTO, CANADA"),
]

ITEM_SETS = [
    [("0123", "Plastic Office Supplies", "5,000 pcs", "3926.90", "CTC"), ("0234", "Power Transformers", "200 units", "8504.40", "RVC"), ("0345", "Leather Wallets", "3,000 pcs", "4202.22", "CTC")],
    [("0501", "Guide Pins", "1,000 pcs", "7318.29", "CTC"), ("0502", "Robot Gripper Fingers", "1,500 pcs", "8479.90", "RVC"), ("0503", "Bearing Housings", "2,000 pcs", "8483.30", "CTC")],
    [("1101", "Medical Sensor Modules", "390 pcs", "9027.90", "RVC"), ("1102", "Disposable Syringe Parts", "24,000 pcs", "9018.31", "CTC"), ("1103", "Diagnostic Kit Cases", "8,000 pcs", "3926.90", "CTC")],
    [("2201", "Aluminum Cooling Plates", "800 pcs", "7616.99", "RVC"), ("2202", "Control Switch Assemblies", "1,200 pcs", "8536.50", "CTC"), ("2203", "Cable Harness Sets", "2,400 pcs", "8544.42", "CTC")],
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def prepare_template() -> None:
    if not TEMPLATE_SOURCE.exists():
        raise FileNotFoundError(TEMPLATE_SOURCE)
    image = Image.open(TEMPLATE_SOURCE).convert("RGB")
    draw = ImageDraw.Draw(image)
    # Blanket Period From/To 주변 LaMa 잔흔만 제거한다. 정적 From/To 라벨은 유지.
    draw.rectangle([120, 380, 295, 405], fill=(255, 255, 255))
    draw.rectangle([380, 380, 514, 405], fill=(255, 255, 255))
    TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    image.save(TEMPLATE)


def make_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    rng = random.Random(20260702)
    for idx in range(12):
        exporter = EXPORTERS[idx % len(EXPORTERS)]
        producer = PRODUCERS[idx % len(PRODUCERS)]
        importer = IMPORTERS[idx % len(IMPORTERS)]
        items = ITEM_SETS[idx % len(ITEM_SETS)]
        start = datetime(2023 + (idx % 3), [1, 3, 5, 7, 9, 11][idx % 6], [2, 8, 14, 20, 23, 26][idx % 6])
        # 현재 기준일(2026-07-02) 이후의 blanket period가 생성되지 않도록 제한한다.
        end = min(start + timedelta(days=334 + (idx % 4) * 10), datetime(2026, 6, 30))
        cert = start + timedelta(days=18 + (idx % 5))
        record = {
            "exporter_name": exporter[0],
            "exporter_email": exporter[1],
            "exporter_telephone": exporter[2],
            "exporter_fax": exporter[3],
            "exporter_address": exporter[4],
            "blanket_period_from": f"{start:%Y/%m/%d}",
            "blanket_period_to": f"{end:%Y/%m/%d}",
            "producer_name": producer[0],
            "producer_email": producer[1],
            "producer_telephone": producer[2],
            "producer_fax": producer[3],
            "producer_address": producer[4],
            "importer_name": importer[0],
            "importer_email": importer[1],
            "importer_telephone": importer[2],
            "importer_fax": importer[3],
            "importer_address": importer[4],
            "certification_date": f"{cert:%Y/%m/%d}",
            "authorized_name": rng.choice(["K. D. HONG", "D. Y. PARK", "M. K. LEE", "J. S. CHOI"]),
        }
        for line_no, row in enumerate(items, start=1):
            serial, desc, qty, hs, criterion = row
            record[f"item_{line_no}_serial_no"] = serial
            record[f"item_{line_no}_description"] = desc
            record[f"item_{line_no}_quantity_unit"] = qty
            record[f"item_{line_no}_hs_no"] = hs
            record[f"item_{line_no}_preference_criterion"] = criterion
            record[f"item_{line_no}_country_of_origin"] = "Republic of Korea"
        records.append(record)
    return records


def style_size(field_id: str) -> int:
    if field_id.endswith("_address"):
        return 15
    if field_id in {"exporter_name", "producer_name", "importer_name"}:
        return 15
    if field_id.startswith("item_"):
        return 16
    if field_id in {"certification_date", "authorized_name"}:
        return 16
    if field_id.startswith("blanket_period"):
        return 16
    return 15


def align_for(field_id: str) -> str:
    if field_id.startswith("item_") and not field_id.endswith("description"):
        return "center"
    if field_id in {"blanket_period_from", "blanket_period_to", "certification_date", "authorized_name"}:
        return "center"
    return "left"


def update_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = json.loads(json.dumps(schema, ensure_ascii=False))
    im = Image.open(ORIGINAL)
    schema.update({"updated_at": NOW, "doc_id": DOC_ID, "title": DOC_TITLE, "source_image": str(ORIGINAL.resolve()), "source_inpainted": str(TEMPLATE.resolve()), "image": {"width": im.width, "height": im.height}, "authoring_mode": "trd06_pipeline_ready_20260702", "quality_status": "pipeline_ready_candidate"})
    bbox_overrides = {
        "blanket_period_from": [188, 379, 108, 26],
        "blanket_period_to": [380, 379, 145, 26],
        "certification_date": [625, 1516, 150, 28],
        "authorized_name": [888, 1585, 130, 30],
    }
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:trd06_certificate_origin_records.{fid}"
        if fid in bbox_overrides:
            field["bbox"] = bbox_overrides[fid]
        policy = field.setdefault("render_policy", {})
        policy["align"] = align_for(fid)
        policy["valign"] = "middle"
        policy["fit"] = "shrink_to_fit"
        policy["overflow"] = "shrink"
        field["notes"] = "TRD-06 원산지증명서 생산용 보정 필드. exporter/producer/importer/items/certification 정보를 record 기반으로 일관 생성."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update({"updated_at": NOW, "doc_id": DOC_ID, "notes": f"TRD-06 원산지증명서 style 보정. 영문 FTA certificate의 serif 출력체와 전체 렌더링 결과를 기준으로 {FONT_FAMILY}을 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다."})
    for style in stylesheet.get("style_classes", []):
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = style_size(fid)
        style["fill"] = [55, 55, 55]
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
    faker.update({"updated_at": NOW, "doc_id": DOC_ID, "locale": "en_US", "field_generators": {fid: "literal:" for fid in field_ids}, "constraints": [{"type": "pick_record", "pool": "trd06_certificate_origin_records", "targets": {fid: fid for fid in field_ids}}], "data_pools": {"trd06_certificate_origin_records": make_records()}, "notes": "TRD-06 생산용 profile. exporter, producer, importer, blanket period, item 3행, certification date, authorized name을 하나의 record로 생성한다."})
    return faker


def build_semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    field_mapping = {
        str(field["field_id"]): field.get("export", {}).get("json_path", field["field_id"])
        for field in schema.get("fields", [])
    }
    item_row = {
        "Serial No.": "",
        "Description of Good(s)": "",
        "Quantity & Unit": "",
        "HS No.": "",
        "Preference Criterion": "",
        "Country of Origin": "",
    }
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "purpose": "렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조",
        "semantic_schema": {
            "원산지증명서(C/O)": {
                "Exporter": {
                    "Name": "",
                    "E-mail": "",
                    "Telephone": "",
                    "Fax": "",
                    "Address": "",
                },
                "Blanket Period": {
                    "From": "",
                    "To": "",
                },
                "Producer": {
                    "Name": "",
                    "E-mail": "",
                    "Telephone": "",
                    "Fax": "",
                    "Address": "",
                },
                "Importer": {
                    "Name": "",
                    "E-mail": "",
                    "Telephone": "",
                    "Fax": "",
                    "Address": "",
                },
                "Items eligible for proof of origin": [item_row],
                "Certification": {
                    "Date": "",
                    "Authorized Name": "",
                },
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "schema.json은 renderer 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 원산지증명서(C/O)의 KIE label 구조만 계층형으로 표현한다.",
            "품목은 실제 렌더링에서 3행으로 생성되지만 의미 schema에서는 반복 row 구조로 표현한다.",
        ],
    }


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT), 14) if Path(FONT).exists() else ImageFont.load_default()
    cell_w, cell_h = 160, 230
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 52), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 12), f"trd06_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
    PROGRESS.write_text(f"""# 2026-07-02 TRD-06 원산지증명서(C/O) 파이프라인 준비 작업

## 목표
- `TRD-06 원산지증명서(C/O)`를 단일 순차 대상으로 처리한다.
- 1페이지 37개 필드 기반으로 exporter/producer/importer/items/certification 정보를 일관 생성한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa source template: `{TEMPLATE_SOURCE}`
- authoring derived template: `{TEMPLATE}`
- 기존 authoring: 1페이지 37개 필드. Blanket Period From 주변에 LaMa 잔여 흔적이 있었다.

## 구현 내용
- font-family는 영문 FTA certificate의 serif 출력체 시각 정보에 가장 가까운 `{FONT_FAMILY}`로 지정했다.
- 기존 독립 faker 규칙을 `trd06_certificate_origin_records` 단일 record pool로 치환했다.
- exporter, producer, importer, blanket period, item 3행, certification date, authorized name이 같은 record에서 생성된다.
- Blanket Period From/To 영역은 파생 템플릿에서 잔흔을 제거했다.

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
- 서명 이미지는 template의 정적 필기 서명을 유지하고, authorized name만 동적 렌더링한다.
- FTA 기준/HS code의 실제 법적 적합성 검증은 별도 validation layer에서 강화해야 한다.
""", encoding="utf-8")


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
    semantic_schema = build_semantic_schema(schema)
    write_json(SEMANTIC_SCHEMA, semantic_schema)
    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="trd06", clean=True)
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
