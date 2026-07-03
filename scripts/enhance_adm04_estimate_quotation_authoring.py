#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import re
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

DOC_ID = "ADM-04"
DOC_TITLE = "산출내역서·견적서"
DOC_DIR = ROOT / "workbench" / "documents" / "산출내역서·견적서__ADM-04"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "ADM-04_산출내역서·견적서"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "ADM-04_산출내역서·견적서"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_adm04_estimate_quotation_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "견적서_page_001.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_견적서_page_001" / "lama" / "inpainted_lama.png"

FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()

SUPPLIERS = [
    {
        "company": "정밀테크",
        "stamp": "정밀테크",
        "brn": "312-06-90731",
        "rep": "이민수",
        "addr": "경기 안산시 단원구 산단로 325",
        "biz": "제조/시험장비",
        "tel": "031-493-8801",
        "fax": "031-493-8802",
        "home": "www.jmtech.kr",
        "email": "quote@jmtech.kr",
        "bank_holder": "이민수(정밀테크)",
        "desc": "저희 정밀테크 회사는 각종 검교정 대행 및 법정장비(시험장비) 등록 업체입니다.",
    },
    {
        "company": "대성정밀",
        "stamp": "대성정밀",
        "brn": "128-21-67540",
        "rep": "박도윤",
        "addr": "인천 남동구 남동서로 184",
        "biz": "도소매/계측기,자동화부품",
        "tel": "032-812-4418",
        "fax": "032-812-4419",
        "home": "www.dsinst.co.kr",
        "email": "sales@dsinst.co.kr",
        "bank_holder": "박도윤(대성정밀)",
        "desc": "저희 대성정밀 회사는 각종 검교정 대행 및 법정장비(시험장비) 등록 업체입니다.",
    },
    {
        "company": "한빛계측",
        "stamp": "한빛계측",
        "brn": "214-18-59072",
        "rep": "최서연",
        "addr": "서울 금천구 가산디지털2로 98",
        "biz": "제조/계측기,전기자재",
        "tel": "02-6941-7200",
        "fax": "02-6941-7201",
        "home": "www.hbmeter.co.kr",
        "email": "order@hbmeter.co.kr",
        "bank_holder": "최서연(한빛계측)",
        "desc": "저희 한빛계측 회사는 각종 검교정 대행 및 법정장비(시험장비) 등록 업체입니다.",
    },
    {
        "company": "세진검교정",
        "stamp": "세진검교정",
        "brn": "105-12-88491",
        "rep": "정하준",
        "addr": "대전 유성구 테크노3로 65",
        "biz": "서비스/검교정,시험대행",
        "tel": "042-936-3104",
        "fax": "042-936-3105",
        "home": "www.sejincal.co.kr",
        "email": "cal@sejincal.co.kr",
        "bank_holder": "정하준(세진검교정)",
        "desc": "저희 세진검교정 회사는 각종 검교정 대행 및 법정장비(시험장비) 등록 업체입니다.",
    },
]

RECIPIENTS = [
    "법정장비 담당자 님",
    "구매관리 담당자 님",
    "설비보전 담당자 님",
    "품질관리 담당자 님",
    "총무구매 담당자 님",
]

RECIPIENT_COMPANIES = [
    "삼영전기제조",
    "한성전장",
    "동우산업",
    "세진전자",
    "유진정밀",
    "태성기전",
    "대명테크",
    "성진산업",
    "한빛시스템",
    "우림엔지니어링",
    "제일전기",
    "금강자동화",
]

ITEM_CATALOG = [
    ("전압계(V METER)-0.5급", "DW-6090", "SET", 1, 450000, 210000),
    ("전류계(A METER)-0.5급", "DW-6090", "SET", 1, 0, 0),
    ("전력계(W METER)-0.5급", "DW-6090", "SET", 1, 0, 0),
    ("절연저항계", "500V 1000M", "SET", 1, 70000, 90000),
    ("내전압시험기", "AC 5KV/HS", "SET", 1, 290000, 80000),
    ("자동전압조정기", "AVR 3KVA", "SET", 1, 340000, 70000),
    ("열전식온도계", "YF-160A", "SET", 1, 78000, 55000),
    ("버어니어켈리퍼스", "150mm 0.05mm", "SET", 1, 45000, 30000),
    ("마이크로메터 25mm", "0-25mm(0.01)", "SET", 1, 45000, 30000),
    ("토크게이지(법정검사용)", "2800kg/cm", "SET", 1, 620000, 80000),
    ("토크드라이버", "LTDK(일본)", "SET", 1, 250000, 47000),
    ("테스트 핀/핑거", "SS-100", "SET", 1, 160000, 0),
    ("디지털 멀티미터", "DMM-6500", "SET", 1, 280000, 65000),
    ("클램프메터", "CM-3289", "SET", 1, 95000, 45000),
    ("온습도계", "TH-200", "SET", 1, 120000, 55000),
]

DEFAULT_TOTAL_WORD = "삼백사만원"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def krw(value: int) -> str:
    return f"W{value:,}"


def style_size(field_id: str) -> int:
    if field_id == "top_contact_line":
        return 15
    if field_id in {"homepage_url", "email_address"}:
        return 16
    if field_id == "supplier_company_stamp_name":
        return 23
    if field_id == "recipient_company_name":
        return 25
    if field_id in {"estimate_subject"}:
        return 21
    if field_id in {"estimate_total_text"}:
        return 22
    if field_id in {"company_description"}:
        return 15
    if field_id.startswith("bank_account") or field_id in {"subtotal_amount", "vat_amount", "grand_total_amount"}:
        return 16
    if re.match(r"line_\\d+_", field_id):
        if field_id.endswith("_note"):
            return 15
        return 16
    if field_id in {"supplier_tel", "supplier_fax"}:
        return 16
    if field_id == "footer_recipient_company_name":
        return 18
    if field_id in {"recipient_tel", "recipient_fax", "recipient_mobile"}:
        return 17
    return 17


def align_for(field_id: str) -> str:
    if field_id == "supplier_company_stamp_name":
        return "center"
    if re.match(r"line_\\d+_(number|unit|quantity)$", field_id):
        return "center"
    if re.match(r"line_\\d+_(unit_price|calibration_fee|amount)$", field_id):
        return "right"
    if field_id in {"subtotal_amount", "vat_amount", "grand_total_amount"}:
        return "right"
    return "left"


def make_records() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    records: list[dict[str, str]] = []
    for idx in range(12):
        supplier = SUPPLIERS[idx % len(SUPPLIERS)]
        recipient = RECIPIENTS[idx % len(RECIPIENTS)]
        recipient_company = RECIPIENT_COMPANIES[idx % len(RECIPIENT_COMPANIES)]
        recipient_tel = f"02-{rng.randrange(2100, 8999)}-{rng.randrange(1000, 9999)}" if idx % 3 == 0 else f"031-{rng.randrange(300, 999)}-{rng.randrange(1000, 9999)}"
        recipient_fax = recipient_tel[:-1] + str((int(recipient_tel[-1]) + 1) % 10)
        recipient_mobile = f"010-{rng.randrange(1000, 9999)}-{rng.randrange(1000, 9999)}"
        # VAL-003(미래 발급/작성일 금지)에 맞춰 현재 기준일(2026-07-02) 이전 범위로 제한한다.
        base_date = datetime(2026, 1, 15) + timedelta(days=idx * 8)
        # 원본 구조를 유지한다. 1행은 대표 금액 행, 2·3행은 공동사용/검교정 설명 행, 4행 이후는 금액 행이다.
        rows = ITEM_CATALOG[:12]

        # 원본처럼 2·3행은 공동사용/검교정 설명 행으로 남기고, 1행과 4행 이후를 금액 행으로 계산한다.
        amount_rows: list[int] = []
        record: dict[str, str] = {}
        for row_no, (name, model, unit, qty, unit_price, cal_fee) in enumerate(rows, start=1):
            record[f"line_{row_no}_number"] = str(row_no)
            record[f"line_{row_no}_item_name"] = name
            record[f"line_{row_no}_model"] = model
            record[f"line_{row_no}_unit"] = unit
            record[f"line_{row_no}_quantity"] = str(qty)
            if row_no == 2:
                record[f"line_{row_no}_note"] = "*한장비로 전압,전류,전력 공통사용"
                continue
            if row_no == 3:
                record[f"line_{row_no}_note"] = "*검교정 전압,전류,전력 3개 모두"
                continue
            amount = qty * unit_price + cal_fee
            amount_rows.append(amount)
            record[f"line_{row_no}_unit_price"] = krw(unit_price) if unit_price else ""
            record[f"line_{row_no}_calibration_fee"] = krw(cal_fee) if cal_fee else "교정제외품목"
            record[f"line_{row_no}_amount"] = krw(amount)

        subtotal = sum(amount_rows)
        target_word = DEFAULT_TOTAL_WORD
        vat = int(round(subtotal * 0.1))
        grand = subtotal + vat

        banks = [
            f"국민:{rng.randrange(100000,999999)}-01-{rng.randrange(100000,999999)}",
            f"신한:110-{rng.randrange(100,999)}-{rng.randrange(100000,999999)}",
            f"우리:077-{rng.randrange(100000,999999)}-13-10{idx % 9}",
            f"기업:023-{rng.randrange(100000,999999)}-04-0{idx % 9} 농협:1271-01-{rng.randrange(100000,999999)}",
        ]

        record.update(
            {
                "top_contact_line": f"{supplier['company']} 법정장비 담당자: {supplier['rep']} 팀장(010-{rng.randrange(1000,9999)}-{rng.randrange(1000,9999)})",
                "homepage_url": supplier["home"],
                "email_address": supplier["email"],
                "recipient_company_name": recipient_company,
                "footer_recipient_company_name": recipient_company,
                "recipient_tel": recipient_tel,
                "recipient_fax": recipient_fax,
                "recipient_mobile": recipient_mobile,
                "recipient_title": recipient,
                "estimate_date_text": f"{base_date.year}년 {base_date.month}월 {base_date.day}일",
                "payment_terms": rng.choice(["현금결재", "납품 후 현금", "세금계산서 발행 후 현금"]),
                "delivery_period": rng.choice(["발주 후 9일이내(검교정기간포함)", "발주 후 10일이내", "계약 후 2주 이내"]),
                "quote_validity_period": rng.choice(["견적일로부터 2주", "견적일로부터 30일", "발행일로부터 15일"]),
                "calibration_period": rng.choice(["발주일로부터 8일 이내", "검교정 접수 후 5일 이내", "접수 후 7일 이내"]),
                "supplier_company_stamp_name": supplier["stamp"],
                "supplier_business_registration_number": supplier["brn"],
                "supplier_company_name": supplier["company"],
                "supplier_representative_name": supplier["rep"],
                "supplier_address": supplier["addr"],
                "supplier_business_type_item": supplier["biz"],
                "supplier_tel": supplier["tel"],
                "supplier_fax": supplier["fax"],
                "estimate_subject": "전기제조 형식승인 법정장비 보유품목",
                "estimate_total_text": f"{target_word}({krw(subtotal)}--) 부가세별도",
                "bank_account_kb": banks[0],
                "bank_account_holder": f"예금주:{supplier['bank_holder']}",
                "bank_account_shinhan": banks[1],
                "bank_account_woori": banks[2],
                "bank_account_enterprise_nonghyup": banks[3],
                "subtotal_amount": krw(subtotal),
                "vat_amount": krw(vat),
                "grand_total_amount": krw(grand),
                "company_description": supplier["desc"],
            }
        )
        records.append(record)
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
            "authoring_mode": "adm04_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:adm04_estimate_records.{fid}"
        field.setdefault("render_policy", {})["align"] = align_for(fid)
        field.setdefault("render_policy", {})["valign"] = "middle"
        field.setdefault("render_policy", {})["fit"] = "shrink_to_fit"
        field.setdefault("render_policy", {})["overflow"] = "shrink"
        field["notes"] = "ADM-04 생산용 보정 필드. bbox는 기존 수동 authoring을 유지하고, 품목/합계는 record 기반으로 일관 생성."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    """Preserve manually calibrated styles.

    This script is allowed to add missing style classes for new fields, but it
    must never rewrite existing font_size/baseline/x_shift/align/weight values.
    The GUI is the source of truth for visual calibration.
    """

    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"ADM-04 견적서 style 보정. 기존 수동 보정 style은 보존하고, 누락된 신규 field style만 기본값으로 추가한다.",
        }
    )
    style_classes = stylesheet.setdefault("style_classes", [])
    existing = {str(style.get("style_class") or "") for style in style_classes if isinstance(style, dict)}
    for field in read_json(SCHEMA_PATH).get("fields", []):
        fid = str(field.get("field_id") or "")
        style_class = str(field.get("style_class") or f"style_{fid}")
        if not fid or style_class in existing:
            continue
        style_classes.append(
            {
                "style_class": style_class,
                "font_family": FONT_FAMILY,
                "font_path": FONT,
                "font_weight": "normal",
                "font_size": style_size(fid),
                "fill": [22, 22, 22],
                "opacity": 0.92,
                "align": align_for(fid),
                "valign": "middle",
                "line_spacing": 1.0,
                "letter_spacing": 0.0,
                "baseline_shift": 0,
                "x_shift": 0,
                "overflow": "shrink",
                "confidence": 0.5,
                "source_detection_ids": [field.get("bbox_label_id") or field.get("source_detection_id") or ""],
            }
        )
        existing.add(style_class)
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
                    "pool": "adm04_estimate_records",
                    "targets": {fid: fid for fid in field_ids},
                }
            ],
            "data_pools": {"adm04_estimate_records": make_records()},
            "notes": "ADM-04 생산용 profile. 거래처/발행처/품목 12행/공급가액/부가세/합계를 하나의 record에서 생성하여 표 내부 산술 일관성을 유지한다.",
        }
    )
    return faker


def build_semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Renderer 전용 bbox/style 속성을 제외한 KIE 관점의 의미 schema."""

    field_mapping = {
        str(field["field_id"]): field.get("export", {}).get("json_path", field["field_id"])
        for field in schema.get("fields", [])
    }
    item_row = {
        "번호": "",
        "품목": "",
        "모델": "",
        "단위": "",
        "수량": "",
        "단가": "",
        "검교정": "",
        "견적금액": "",
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
            "산출내역서·견적서": {
                "문서 상단": {
                    "담당자 및 연락처": "",
                    "홈페이지": "",
                    "이메일": "",
                },
                "수신 및 견적 조건": {
                    "고객 업체명": "",
                    "하단 고객 업체명": "",
                    "고객 전화번호": "",
                    "고객 팩스번호": "",
                    "고객 휴대전화": "",
                    "받으실 분": "",
                    "견적일자": "",
                    "지불조건": "",
                    "납품기간": "",
                    "견적유효기간": "",
                    "검교정기간": "",
                },
                "발행처": {
                    "등록번호": "",
                    "상호": "",
                    "대표자명": "",
                    "주소": "",
                    "업태 및 종목": "",
                    "회사전화": "",
                    "회사팩스": "",
                    "인감명": "",
                },
                "견적 개요": {
                    "제목": "",
                    "견적 합계 문구": "",
                },
                "품목 내역": [item_row],
                "계좌 정보": {
                    "국민은행": "",
                    "예금주": "",
                    "신한은행": "",
                    "우리은행": "",
                    "기업 및 농협": "",
                },
                "금액 합계": {
                    "소계": "",
                    "부가세": "",
                    "합계": "",
                },
                "하단": {
                    "회사 설명": "",
                },
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "schema.json은 renderer 호환을 위해 field_id/bbox/style 연결 정보를 유지한다.",
            "semantic_schema.json은 산출내역서·견적서의 KIE label 구조만 계층형으로 표현한다.",
            "품목 내역은 실제 렌더링에서 12행으로 생성되지만 의미 schema에서는 반복 row 구조로 표현한다.",
        ],
    }


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 180, 250
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 58), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 15), f"adm04_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
        f"""# 2026-07-02 ADM-04 산출내역서·견적서 파이프라인 준비 작업

## 목표
- `ADM-04 산출내역서·견적서`를 단일 순차 대상으로 처리한다.
- 기존 120개 bbox authoring을 유지하되, 품목 행/합계/거래처 정보를 생산 가능한 record 기반 schema+faker_profile로 고정한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: 1페이지 120개 필드, preview 동작 가능 상태.

## 구현 내용
- font-family는 원본 견적서의 산세리프 인쇄체 시각 정보에 가장 가까운 `{FONT_FAMILY}`로 통일했다.
- 기존 필드별 독립 faker pool을 `adm04_estimate_records` 단일 record pool로 치환했다.
- 12개 품목 행, 공급가액, 부가세, 합계가 같은 record에서 함께 생성되므로 금액 일관성이 유지된다.
- 품목 번호/단위/수량은 center, 단가/검교정/견적금액/합계는 right, 나머지는 left 정렬로 보정했다.
- 원본처럼 2·3행은 공동사용/검교정 설명 행으로 남기고, 나머지 행은 금액 행으로 생성한다.

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
- 원본 로고/인감/기본 양식은 template에 남아 있는 요소를 사용한다.
- 일부 LaMa 잔흔은 template 자체에 남아 있으므로 필요 시 수동 cleanup mask를 추가하면 더 좋아진다.
- 회사명/품목명이 긴 경우 bbox 폭에 맞춰 자동 shrink가 적용된다.
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
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="adm04", clean=True)
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
