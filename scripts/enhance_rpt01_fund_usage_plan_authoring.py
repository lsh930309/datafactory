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

from datafactory.authoring import render_authoring_preview
from datafactory.workbench import update_manifest_artifact
from datafactory.authoring_backup import backup_authoring_json_before_write

DOC_ID = "RPT-01"
DOC_TITLE = "사업계획서·자금사용계획서"
DOC_DIR = ROOT / "workbench" / "documents" / "사업계획서·자금사용계획서__RPT-01"
AUTHORING = DOC_DIR / "authoring"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "RPT-01_사업계획서·자금사용계획서"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "RPT-01_사업계획서·자금사용계획서"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_rpt01_fund_usage_plan_pipeline_readiness.md"
ORIGINAL_BLANK = DOC_DIR / "samples" / "original" / "자금사용계획서_page_001.jpg"
FILLED_REFERENCE = DOC_DIR / "samples" / "original" / "자금사용계획서_page_002.jpg"
REVIEW_PAGE1 = DOC_DIR / "review" / "original_자금사용계획서_page_001" / "review.json"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
FONT_MYUNGJO = Path("/System/Library/Fonts/Supplemental/AppleMyungjo.ttf")
FONT_SD = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_MYUNGJO if FONT_MYUNGJO.exists() else (FONT_SD if FONT_SD.exists() else FONT_FALLBACK))
FONT_FAMILY = "AppleMyungjo" if FONT_MYUNGJO.exists() else ("AppleSDGothicNeo" if FONT_SD.exists() else "default_korean")
NOW = datetime.now(timezone.utc).isoformat()
RED = [184, 45, 52]
CHECK = "■"

FIELDS: list[dict[str, Any]] = [
    # account selection and join month
    {"id": "account_hope_check", "label": "희망저축계좌II 선택", "bbox": [246, 441, 24, 24], "style": "style_check", "align": "center"},
    {"id": "account_youth_check", "label": "청년내일저축계좌 선택", "bbox": [246, 489, 24, 24], "style": "style_check", "align": "center"},
    {"id": "hope_join_month", "label": "희망저축계좌 가입기수", "bbox": [790, 438, 140, 30], "style": "style_small_center", "align": "center"},
    {"id": "youth_join_month", "label": "청년내일저축계좌 가입기수", "bbox": [790, 481, 140, 30], "style": "style_small_center", "align": "center"},
    {"id": "youth_join_note", "label": "가입연월 안내", "bbox": [790, 506, 140, 24], "style": "style_note", "align": "center"},
    # applicant info
    {"id": "applicant_name", "label": "성명", "bbox": [339, 526, 175, 32], "style": "style_text", "align": "left"},
    {"id": "birth_date", "label": "생년월일", "bbox": [702, 528, 165, 32], "style": "style_text", "align": "left"},
    {"id": "total_grant_amount_text", "label": "지급액 총액", "bbox": [338, 559, 560, 30], "style": "style_text_small", "align": "left", "overflow": "allow"},
    {"id": "personal_saving_text", "label": "본인적립금", "bbox": [340, 592, 260, 30], "style": "style_text_small", "align": "left"},
    {"id": "support_amount_text", "label": "지원금", "bbox": [682, 592, 420, 30], "style": "style_text_small", "align": "left", "overflow": "allow"},
    {"id": "usage_plan_note", "label": "사용용도 계획 안내", "bbox": [350, 628, 520, 30], "style": "style_text_small", "align": "left", "overflow": "allow"},
    # housing row
    {"id": "housing_self_purchase_check", "label": "주택 자가구입", "bbox": [372, 713, 22, 22], "style": "style_check", "align": "center"},
    {"id": "housing_deposit_check", "label": "주택 보증금", "bbox": [480, 713, 22, 22], "style": "style_check", "align": "center"},
    {"id": "housing_rent_check", "label": "월세", "bbox": [578, 713, 22, 22], "style": "style_check", "align": "center"},
    {"id": "housing_loan_check", "label": "대출상환", "bbox": [372, 735, 22, 22], "style": "style_check", "align": "center"},
    {"id": "housing_repair_check", "label": "주택 유지 및 보수", "bbox": [562, 735, 22, 22], "style": "style_check", "align": "center"},
    {"id": "housing_dorm_check", "label": "기숙사비", "bbox": [372, 757, 22, 22], "style": "style_check", "align": "center"},
    {"id": "housing_other_check", "label": "주택 기타", "bbox": [480, 757, 22, 22], "style": "style_check", "align": "center"},
    {"id": "housing_other_text", "label": "주택 기타 내용", "bbox": [544, 755, 245, 26], "style": "style_small", "align": "left"},
    {"id": "housing_amount", "label": "주택 금액", "bbox": [823, 734, 126, 35], "style": "style_amount", "align": "center"},
    # education row
    {"id": "education_tuition_check", "label": "자녀 학비", "bbox": [372, 799, 22, 22], "style": "style_check", "align": "center"},
    {"id": "education_books_check", "label": "교재교복", "bbox": [501, 799, 22, 22], "style": "style_check", "align": "center"},
    {"id": "education_loan_check", "label": "학자금 대출상환", "bbox": [372, 821, 22, 22], "style": "style_check", "align": "center"},
    {"id": "education_exam_check", "label": "시험 응시료", "bbox": [562, 821, 22, 22], "style": "style_check", "align": "center"},
    {"id": "education_academy_check", "label": "학원비", "bbox": [372, 843, 22, 22], "style": "style_check", "align": "center"},
    {"id": "education_certificate_check", "label": "자격증 취득", "bbox": [372, 866, 22, 22], "style": "style_check", "align": "center"},
    {"id": "education_other_check", "label": "교육 기타", "bbox": [511, 866, 22, 22], "style": "style_check", "align": "center"},
    {"id": "education_other_text", "label": "교육 기타 내용", "bbox": [575, 862, 215, 26], "style": "style_small", "align": "left"},
    {"id": "education_amount", "label": "교육 금액", "bbox": [823, 828, 126, 35], "style": "style_amount", "align": "center"},
    # startup row
    {"id": "startup_working_capital_check", "label": "운용자금", "bbox": [372, 903, 22, 22], "style": "style_check", "align": "center"},
    {"id": "startup_other_check", "label": "창업 기타", "bbox": [490, 903, 22, 22], "style": "style_check", "align": "center"},
    {"id": "startup_other_text", "label": "창업 기타 내용", "bbox": [550, 899, 240, 26], "style": "style_small", "align": "left"},
    {"id": "startup_amount", "label": "창업 금액", "bbox": [823, 900, 126, 35], "style": "style_amount", "align": "center"},
    # medical row
    {"id": "medical_self_check", "label": "본인 의료비", "bbox": [372, 944, 22, 22], "style": "style_check", "align": "center"},
    {"id": "medical_family_check", "label": "가구원 의료비", "bbox": [512, 944, 22, 22], "style": "style_check", "align": "center"},
    {"id": "medical_equipment_check", "label": "의료보장구", "bbox": [372, 966, 22, 22], "style": "style_check", "align": "center"},
    {"id": "medical_care_check", "label": "돌봄 비용", "bbox": [372, 988, 22, 22], "style": "style_check", "align": "center"},
    {"id": "medical_other_check", "label": "의료 기타", "bbox": [372, 1010, 22, 22], "style": "style_check", "align": "center"},
    {"id": "medical_other_text", "label": "의료 기타 내용", "bbox": [440, 1006, 350, 26], "style": "style_small", "align": "left"},
    {"id": "medical_amount", "label": "의료 금액", "bbox": [823, 970, 126, 35], "style": "style_amount", "align": "center"},
    # finance/child/marriage/other rows
    {"id": "finance_isa_check", "label": "ISA", "bbox": [372, 1050, 22, 22], "style": "style_check", "align": "center"},
    {"id": "finance_savings_check", "label": "적금상품", "bbox": [622, 1050, 22, 22], "style": "style_check", "align": "center"},
    {"id": "finance_other_check", "label": "금융 기타", "bbox": [372, 1072, 22, 22], "style": "style_check", "align": "center"},
    {"id": "finance_other_text", "label": "금융 기타 내용", "bbox": [442, 1068, 345, 26], "style": "style_small", "align": "left"},
    {"id": "finance_amount", "label": "금융 금액", "bbox": [823, 1057, 126, 35], "style": "style_amount", "align": "center"},
    {"id": "childcare_other_check", "label": "자녀양육 기타", "bbox": [372, 1112, 22, 22], "style": "style_check", "align": "center"},
    {"id": "childcare_other_text", "label": "자녀양육 기타 내용", "bbox": [442, 1108, 345, 26], "style": "style_small", "align": "left"},
    {"id": "childcare_amount", "label": "자녀양육 금액", "bbox": [823, 1108, 126, 35], "style": "style_amount", "align": "center"},
    {"id": "marriage_other_check", "label": "결혼자금 기타", "bbox": [372, 1152, 22, 22], "style": "style_check", "align": "center"},
    {"id": "marriage_other_text", "label": "결혼자금 기타 내용", "bbox": [442, 1148, 345, 26], "style": "style_small", "align": "left"},
    {"id": "marriage_amount", "label": "결혼자금 금액", "bbox": [823, 1148, 126, 35], "style": "style_amount", "align": "center"},
    {"id": "self_reliance_other_check", "label": "자립자활 기타", "bbox": [372, 1192, 22, 22], "style": "style_check", "align": "center"},
    {"id": "self_reliance_other_text", "label": "자립자활 기타 내용", "bbox": [442, 1188, 345, 26], "style": "style_small", "align": "left"},
    {"id": "self_reliance_amount", "label": "자립자활 금액", "bbox": [823, 1188, 126, 35], "style": "style_amount", "align": "center"},
    {"id": "usage_total_amount", "label": "총합", "bbox": [823, 1233, 126, 35], "style": "style_amount", "align": "center"},
    # date/signature
    {"id": "application_year", "label": "신청 연", "bbox": [480, 1328, 58, 36], "style": "style_text", "align": "center"},
    {"id": "application_month", "label": "신청 월", "bbox": [578, 1328, 42, 36], "style": "style_text", "align": "center"},
    {"id": "application_day", "label": "신청 일", "bbox": [646, 1328, 48, 36], "style": "style_text", "align": "center"},
    {"id": "signature_name", "label": "신청인 성명", "bbox": [530, 1370, 175, 34], "style": "style_text", "align": "left"},
]

# AppleMyungjo의 solid-square glyph는 중앙 정렬 시 하단으로 내려가 보여,
# RPT-01 checkbox 계열 bbox만 문서 전용으로 위쪽 보정한다.
for _field in FIELDS:
    if _field.get("style") == "style_check":
        _field["bbox"][1] -= 7
        _field["bbox"][3] += 3


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def field(spec: dict[str, Any]) -> dict[str, Any]:
    fid = spec["id"]
    overflow = spec.get("overflow", "shrink")
    fit = {
        "shrink": "shrink_to_fit",
        "clip": "clip",
        "allow": "allow_overflow",
        "wrap": "wrap",
    }.get(overflow, "shrink_to_fit")
    return {
        "field_id": fid,
        "label": spec["label"],
        "bbox": spec["bbox"],
        "bbox_format": "xywh",
        "source_detection_id": "manual_rpt01_blank_form_20260702",
        "source_text": "",
        "value_type": "money.krw" if fid.endswith("amount") or "amount" in fid else "free_text.short",
        "generator": f"pool_record:rpt01_profiles.{fid}",
        "style_class": spec["style"],
        "render_policy": {"align": spec.get("align", "left"), "valign": "middle", "fit": fit, "overflow": overflow},
        "export": {"json_path": fid.replace("_", "."), "csv_column": fid},
        "required": False,
        "notes": "RPT-01 자금사용계획서 blank form + filled reference 기반 수동 bbox/style 필드",
    }


def style(style_id: str, size: int, *, align: str = "left", opacity: float = 0.94, baseline_shift: int = 0) -> dict[str, Any]:
    return {
        "style_class": style_id,
        "font_family": FONT_FAMILY,
        "font_path": FONT,
        "font_size": size,
        "font_weight": "normal",
        "fill": RED,
        "opacity": opacity,
        "align": align,
        "valign": "middle",
        "line_spacing": 1.0,
        "letter_spacing": 0.0,
        "baseline_shift": baseline_shift,
        "overflow": "shrink",
        "confidence": 0.70,
        "source_detection_ids": ["manual_rpt01_blank_form_20260702"],
    }


def build_schema() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": "자산형성지원사업 자금사용계획서",
        "source_review": str(REVIEW_PAGE1.resolve()),
        "source_image": str(ORIGINAL_BLANK.resolve()),
        "source_inpainted": str(ORIGINAL_BLANK.resolve()),
        "image": {"width": 1191, "height": 1684},
        "fields": [field(item) for item in FIELDS],
        "groups": [
            {"group_id": "account_selection", "type": "checkbox_group", "fields": ["account_hope_check", "account_youth_check", "hope_join_month", "youth_join_month"]},
            {"group_id": "usage_plan", "type": "amount_table", "notes": "usage_* 금액 합계가 usage_total_amount와 일치하도록 faker profile에서 record 단위 생성"},
        ],
        "authoring_mode": "rpt01_fund_usage_plan_pipeline_ready_20260702",
        "quality_status": "pipeline_ready_candidate",
    }


def build_stylesheet() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "style_classes": [
            style("style_text", 23, opacity=0.93),
            style("style_text_small", 19, opacity=0.93),
            style("style_small", 17, opacity=0.93),
            style("style_small_center", 19, align="center", opacity=0.93),
            style("style_note", 16, align="center", opacity=0.90),
            style("style_amount", 21, align="center", opacity=0.93),
            style("style_check", 15, align="center", opacity=0.96),
        ],
        "notes": "RPT-01 page 2 filled reference의 빨간 명조 계열 기입값을 기준으로 AppleMyungjo를 선택했다. 전체 렌더/overlay 기준이며 crop 비교 미사용.",
    }


def build_semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    field_mapping = {field["field_id"]: field["export"]["json_path"] for field in schema["fields"]}
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": "자산형성지원사업 자금사용계획서",
        "purpose": "렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조",
        "semantic_schema": {
            "자금사용계획서": {
                "통장종류": {
                    "희망저축계좌II": "",
                    "청년내일저축계좌": "",
                    "희망저축계좌 가입기수": "",
                    "청년내일저축계좌 가입기수": "",
                    "가입연월 안내": "",
                },
                "신청인": {
                    "성명": "",
                    "생년월일": "",
                },
                "지급액": {
                    "총액": "",
                    "본인적립금": "",
                    "지원금": "",
                    "사용용도 계획 안내": "",
                },
                "사용용도계획": {
                    "주거 구입·임대": {
                        "자가구입": "",
                        "보증금": "",
                        "월세": "",
                        "대출상환": "",
                        "주택 유지 및 보수": "",
                        "기숙사비": "",
                        "기타": "",
                        "기타 내용": "",
                        "금액": "",
                    },
                    "본인·자녀의 고등교육·기술훈련": {
                        "자녀 학비": "",
                        "교재·교복": "",
                        "학자금 대출상환": "",
                        "시험 응시료": "",
                        "학원비": "",
                        "자격증 취득": "",
                        "기타": "",
                        "기타 내용": "",
                        "금액": "",
                    },
                    "창업·운영자금": {
                        "운용자금": "",
                        "기타": "",
                        "기타 내용": "",
                        "금액": "",
                    },
                    "의료비": {
                        "본인 의료비": "",
                        "가구원 의료비": "",
                        "의료보장구": "",
                        "돌봄 비용": "",
                        "기타": "",
                        "기타 내용": "",
                        "금액": "",
                    },
                    "금융자산형성": {
                        "ISA": "",
                        "적금상품": "",
                        "기타": "",
                        "기타 내용": "",
                        "금액": "",
                    },
                    "자녀양육·보육비": {
                        "기타": "",
                        "기타 내용": "",
                        "금액": "",
                    },
                    "결혼자금": {
                        "기타": "",
                        "기타 내용": "",
                        "금액": "",
                    },
                    "그밖의 자립·자활": {
                        "기타": "",
                        "기타 내용": "",
                        "금액": "",
                    },
                    "총합": "",
                },
                "신청일": {
                    "연": "",
                    "월": "",
                    "일": "",
                },
                "서명": {
                    "신청인 성명": "",
                },
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "schema.json은 렌더러 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 schema key-name 집합과 계층만 별도로 관리하기 위한 파일이다.",
            "현재 RPT-01은 수집된 정형 자금사용계획서 양식 기준이며 산문형 사업계획서 일반형은 범위 밖이다.",
        ],
    }


def krw(value: int) -> str:
    return f"{value:,}"


def make_profiles() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    names = ["홍길동", "김서연", "박민준", "이하은", "정도윤", "최지우"]
    births = ["1999.1.1.", "1997.3.14.", "2000.8.22.", "1998.11.5.", "1996.6.30.", "2001.2.18."]
    months = ["2022년 10월", "2023년 4월", "2024년 7월", "2025년 1월", "2025년 9월", "2026년 3월"]
    profiles: list[dict[str, str]] = []
    for idx, name in enumerate(names):
        is_youth = idx % 3 != 1
        year = 2025 + (idx % 2)
        month = 10 if idx % 2 == 0 else 6
        day = 30 - idx
        # Create correlated category amounts in units of 100,000 KRW.
        housing = rng.choice([0, 800_000, 1_000_000, 1_500_000])
        education = rng.choice([0, 900_000, 1_200_000, 1_800_000])
        startup = rng.choice([0, 500_000, 1_000_000])
        medical = rng.choice([0, 600_000, 900_000])
        finance = rng.choice([2_000_000, 3_000_000, 4_000_000, 5_000_000])
        childcare = rng.choice([0, 400_000, 700_000])
        marriage = rng.choice([0, 500_000])
        self_reliance = rng.choice([0, 300_000, 600_000])
        amounts = [housing, education, startup, medical, finance, childcare, marriage, self_reliance]
        total = sum(amounts)
        # Keep total in realistic grant split: personal and support are half each.
        if total % 2:
            total += 100_000
            finance += 100_000
        personal = total // 2
        support = total - personal
        record = {item["id"]: "" for item in FIELDS}
        record.update(
            {
                "account_hope_check": CHECK if not is_youth else "",
                "account_youth_check": CHECK if is_youth else "",
                "hope_join_month": months[idx] if not is_youth else "",
                "youth_join_month": months[idx] if is_youth else "",
                "youth_join_note": "(가입 연월을 기재)" if is_youth else "",
                "applicant_name": name,
                "birth_date": births[idx],
                "total_grant_amount_text": f"{krw(total)}원 (본인저축금+근로소득장려금 총액을 기재)",
                "personal_saving_text": f"{krw(personal)}원 (본인저축금을 기재)",
                "support_amount_text": f"{krw(support)}원 (근로소득장려금을 기재)",
                "usage_plan_note": "(지급액 총액에 대한 사용계획을 기재)",
                "housing_amount": krw(housing) if housing else "",
                "education_amount": krw(education) if education else "",
                "startup_amount": krw(startup) if startup else "",
                "medical_amount": krw(medical) if medical else "",
                "finance_amount": krw(finance) if finance else "",
                "childcare_amount": krw(childcare) if childcare else "",
                "marriage_amount": krw(marriage) if marriage else "",
                "self_reliance_amount": krw(self_reliance) if self_reliance else "",
                "usage_total_amount": krw(total),
                "application_year": str(year),
                "application_month": str(month),
                "application_day": str(day),
                "signature_name": name,
            }
        )
        if housing:
            record[rng.choice(["housing_rent_check", "housing_deposit_check", "housing_loan_check"])] = CHECK
        if education:
            record[rng.choice(["education_tuition_check", "education_academy_check", "education_certificate_check"])] = CHECK
        if startup:
            record["startup_working_capital_check"] = CHECK
        if medical:
            record[rng.choice(["medical_self_check", "medical_family_check", "medical_equipment_check"])] = CHECK
        if finance:
            record["finance_savings_check"] = CHECK
            if idx % 2 == 0:
                record["finance_other_check"] = CHECK
                record["finance_other_text"] = "개인계좌 저축"
        if childcare:
            record["childcare_other_check"] = CHECK
            record["childcare_other_text"] = "보육료 납부"
        if marriage:
            record["marriage_other_check"] = CHECK
            record["marriage_other_text"] = "예식 계약금"
        if self_reliance:
            record["self_reliance_other_check"] = CHECK
            record["self_reliance_other_text"] = "직업훈련비"
        profiles.append(record)
    return profiles


def build_faker_profile(schema: dict[str, Any]) -> dict[str, Any]:
    field_ids = [field["field_id"] for field in schema["fields"]]
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "locale": "ko_KR",
        "field_generators": {field_id: "literal:" for field_id in field_ids},
        "constraints": [{"type": "pick_record", "pool": "rpt01_profiles", "targets": {field_id: field_id for field_id in field_ids}}],
        "data_pools": {"rpt01_profiles": make_profiles()},
        "notes": "RPT-01 자금사용계획서 record profile. 통장종류, 가입월, 신청자, 지급액, 사용용도 항목별 금액, 총합을 하나의 record로 묶어 정합성을 유지한다.",
    }


def render_batch(schema_path: Path, style_path: Path, faker_path: Path, count: int = 5) -> dict[str, Any]:
    if BATCH_DIR.exists():
        shutil.rmtree(BATCH_DIR)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    images: list[Path] = []
    warnings = 0
    field_count = 0
    for idx in range(1, count + 1):
        sid = f"rpt01_{idx:06d}"
        result = render_authoring_preview(schema_path, style_path, faker_path, out_dir=BATCH_DIR, seed=20260702 + idx - 1, sample_id=sid)
        warnings += result.warning_count
        field_count = result.field_count
        images.append(result.image)
        samples.append(
            {
                "sample_id": sid,
                "image": str(result.image),
                "kv": str(result.kv),
                "bbox": str(result.bbox),
                "overlay": str(result.overlay),
                "validation_report": str(result.validation_report),
                "warning_count": result.warning_count,
            }
        )
    contact = make_contact_sheet(images)
    summary = {
        "schema_version": 1,
        "created_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "schema": str(schema_path),
        "stylesheet": str(style_path),
        "faker_profile": str(faker_path),
        "out_dir": str(BATCH_DIR),
        "count": count,
        "page_count": 1,
        "field_count": field_count,
        "warning_count": warnings,
        "contact_sheet": str(contact),
        "samples": samples,
    }
    write_json(BATCH_DIR / "summary.json", summary)
    return summary


def make_contact_sheet(images: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 18) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 290, 410
    sheet = Image.new("RGB", (len(images) * cell_w + 20, cell_h + 62), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(images):
        x = 20 + idx * cell_w
        draw.text((x, 16), f"rpt01_{idx + 1:06d}", font=font, fill=(25, 25, 25))
        im = Image.open(path).convert("RGB")
        im.thumbnail((cell_w - 20, cell_h - 20))
        y = 48
        sheet.paste(im, (x, y))
        draw.rectangle([x, y, x + im.width, y + im.height], outline=(155, 155, 155))
    out = BATCH_DIR / "contact_sheet.jpg"
    sheet.save(out, quality=92)
    return out


def compare(rendered: Path) -> Path:
    if CALIB_DIR.exists():
        shutil.rmtree(CALIB_DIR)
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    blank = Image.open(ORIGINAL_BLANK).convert("RGB")
    reference = Image.open(FILLED_REFERENCE).convert("RGB").resize(blank.size)
    render = Image.open(rendered).convert("RGB").resize(blank.size)
    diff = ImageChops.difference(reference, render)
    diff_amp = diff.point(lambda value: min(255, value * 4))
    overlay = Image.blend(reference, render, 0.5)
    labels = [("blank template", blank), ("filled reference", reference), ("render", render), ("amplified diff", diff_amp), ("50% overlay", overlay)]
    font = ImageFont.truetype(str(FONT_FALLBACK), 20) if FONT_FALLBACK.exists() else ImageFont.load_default()
    scale_w = 360
    thumbs = []
    for label, image in labels:
        thumb = image.copy()
        thumb.thumbnail((scale_w, 520))
        thumbs.append((label, thumb))
    sheet = Image.new("RGB", (scale_w * len(thumbs) + 24 * (len(thumbs) + 1), 590), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, thumb) in enumerate(thumbs):
        x = 24 + idx * (scale_w + 24)
        draw.text((x, 18), label, font=font, fill=(20, 20, 20))
        sheet.paste(thumb, (x, 56))
        draw.rectangle([x, 56, x + thumb.width, y := 56 + thumb.height], outline=(150, 150, 150))
    out = CALIB_DIR / "full_comparison.jpg"
    sheet.save(out, quality=92)
    diff.save(CALIB_DIR / "full_diff.png")
    overlay.save(CALIB_DIR / "full_overlay_50.png")
    return out


def write_progress(summary: dict[str, Any], comparison: Path, preview: Path) -> None:
    PROGRESS.write_text(
        f"""# 2026-07-02 RPT-01 자금사용계획서 파이프라인 준비 작업

## 목표
- `RPT-01 사업계획서·자금사용계획서` 중 현재 샘플이 확보된 `자산형성지원사업 자금사용계획서`를 순차 처리한다.
- page 1 빈 양식을 생산 템플릿으로 사용하고, page 2 기입 예시를 스타일/필드 의미 참고자료로 사용한다.
- 주주명부 방식과 동일하게 schema, stylesheet, faker_profile, preview, batch, full comparison을 남긴다.

## 입력 상태
- blank template: `{ORIGINAL_BLANK}`
- filled reference: `{FILLED_REFERENCE}`
- review page 1: `{REVIEW_PAGE1}`
- 기존 inpaint: 없음. page 1이 빈 양식이므로 별도 인페인팅 없이 원본 blank image를 `source_inpainted`로 사용했다.

## 구현 내용
- 통장종류 선택, 가입기수, 성명, 생년월일, 지급액 총액/본인적립금/지원금, 사용용도 체크박스, 항목별 금액, 총합, 신청일, 신청인 성명을 필드화했다.
- faker profile은 `rpt01_profiles` record pool을 사용하며, 항목별 금액 합계가 `usage_total_amount`와 일치하도록 생성했다.
- font-family는 filled reference의 빨간 명조 계열 기입값과 가장 유사한 `{FONT_FAMILY}`로 선택했다.
- crop 비교는 사용하지 않고 전체 문서/filled reference/render/overlay 비교만 생성했다.

## 산출물
- schema: `{AUTHORING / 'schema.json'}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
- stylesheet: `{AUTHORING / 'stylesheet.json'}`
- faker_profile: `{AUTHORING / 'faker_profile.json'}`
- preview: `{preview}`
- batch summary: `{BATCH_DIR / 'summary.json'}`
- contact sheet: `{BATCH_DIR / 'contact_sheet.jpg'}`
- comparison: `{comparison}`

## 검수 결과
- 생성 수: {summary['count']}장
- page_count: {summary['page_count']}
- field_count: {summary['field_count']}
- warning_count: {summary['warning_count']}

## 한계 및 다음 조치
- 현재 `RPT-01`은 사업계획서 전체가 아니라, 수집된 정형 `자금사용계획서` 양식에 대한 pipeline-ready 처리다.
- 기입 예시와 달리 사용용도 항목 선택 조합은 faker record별로 다양화했다.
- 향후 실제 사업계획서 산문형 샘플이 추가될 경우, 이 양식과 별도 문서 유형으로 분리하거나 clean-room/수집 대응이 필요하다.
""",
        encoding="utf-8",
    )


def main() -> None:
    for required in [ORIGINAL_BLANK, FILLED_REFERENCE, REVIEW_PAGE1]:
        if not required.exists():
            raise FileNotFoundError(required)
    AUTHORING.mkdir(parents=True, exist_ok=True)
    schema = build_schema()
    semantic_schema = build_semantic_schema(schema)
    stylesheet = build_stylesheet()
    faker = build_faker_profile(schema)
    schema_path = AUTHORING / "schema.json"
    style_path = AUTHORING / "stylesheet.json"
    faker_path = AUTHORING / "faker_profile.json"
    write_json(schema_path, schema)
    write_json(SEMANTIC_SCHEMA, semantic_schema)
    write_json(style_path, stylesheet)
    write_json(faker_path, faker)
    preview = render_authoring_preview(schema_path, style_path, faker_path, out_dir=OUT_DIR, seed=20260702, sample_id="preview_000001")
    summary = render_batch(schema_path, style_path, faker_path, count=5)
    comparison = compare(preview.image)
    update_manifest_artifact(DOC_ID, "authoring", schema_path)
    update_manifest_artifact(DOC_ID, "authoring_semantic_schema", SEMANTIC_SCHEMA)
    update_manifest_artifact(DOC_ID, "authoring_stylesheet", style_path)
    update_manifest_artifact(DOC_ID, "authoring_faker_profile", faker_path)
    update_manifest_artifact(DOC_ID, "authoring_preview", preview.image)
    update_manifest_artifact(DOC_ID, "authoring_overlay", preview.overlay)
    update_manifest_artifact(DOC_ID, "authoring_batch", BATCH_DIR / "summary.json")
    update_manifest_artifact(DOC_ID, "authoring_contact_sheet", BATCH_DIR / "contact_sheet.jpg")
    update_manifest_artifact(DOC_ID, "authoring_style_comparison", comparison)
    write_progress(summary, comparison, preview.image)
    print("preview", preview.image, "warnings", preview.warning_count)
    print("batch", BATCH_DIR / "summary.json", "warnings", summary["warning_count"])
    print("contact", BATCH_DIR / "contact_sheet.jpg")
    print("comparison", comparison)


if __name__ == "__main__":
    main()
