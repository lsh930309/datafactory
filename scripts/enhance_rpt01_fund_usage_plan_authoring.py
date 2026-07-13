#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from datafactory.authoring import render_authoring_preview, save_authoring_bundle
from datafactory.workbench import update_manifest_artifact
from datafactory.authoring_backup import backup_authoring_json_before_write
from datafactory.web_api import _authoring_bundle_consistency, _validate_faker_profile_contract

DOC_ID = "RPT-01"
DOC_TITLE = "사업계획서·자금사용계획서"
DOC_DIR = ROOT / "workbench" / "documents" / "사업계획서·자금사용계획서__RPT-01"
AUTHORING = DOC_DIR / "authoring"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "RPT-01_사업계획서·자금사용계획서"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "RPT-01_사업계획서·자금사용계획서"
PROGRESS = ROOT / "outputs/reports/pipeline_ready/20260713_rpt01_fund_usage_plan_restoration.md"
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


SEMANTIC_PATHS: dict[str, list[str]] = {
    "account_hope_check": ["통장정보", "통장종류", "희망저축계좌II"],
    "account_youth_check": ["통장정보", "통장종류", "청년내일저축계좌"],
    "hope_join_month": ["통장정보", "가입기수", "희망저축계좌II"],
    "youth_join_month": ["통장정보", "가입기수", "청년내일저축계좌"],
    "applicant_name": ["신청인", "성명"],
    "birth_date": ["신청인", "생년월일"],
    "total_grant_amount_text": ["지급정보", "지급액 총액"],
    "personal_saving_text": ["지급정보", "본인적립금"],
    "support_amount_text": ["지급정보", "지원금"],
    "usage_total_amount": ["사용용도계획", "총합"],
    "application_year": ["신청정보", "신청일", "연"],
    "application_month": ["신청정보", "신청일", "월"],
    "application_day": ["신청정보", "신청일", "일"],
    "signature_name": ["신청정보", "신청인 성명"],
}

_CATEGORY_PATHS = {
    "housing": "주거 구입·임대",
    "education": "본인·자녀의 고등교육·기술훈련",
    "startup": "창업·운영자금",
    "medical": "의료비",
    "finance": "금융자산형성",
    "childcare": "자녀양육·보육비",
    "marriage": "결혼자금",
    "self_reliance": "그밖의 자립·자활",
}
_CATEGORY_LEAVES = {
    "housing_self_purchase_check": ("housing", "자가구입"),
    "housing_deposit_check": ("housing", "보증금"),
    "housing_rent_check": ("housing", "월세"),
    "housing_loan_check": ("housing", "대출상환"),
    "housing_repair_check": ("housing", "주택 유지 및 보수"),
    "housing_dorm_check": ("housing", "기숙사비"),
    "housing_other_check": ("housing", "기타 선택"),
    "housing_other_text": ("housing", "기타 내용"),
    "housing_amount": ("housing", "금액"),
    "education_tuition_check": ("education", "자녀 학비"),
    "education_books_check": ("education", "교재·교복"),
    "education_loan_check": ("education", "학자금 대출상환"),
    "education_exam_check": ("education", "시험 응시료"),
    "education_academy_check": ("education", "학원비"),
    "education_certificate_check": ("education", "자격증 취득"),
    "education_other_check": ("education", "기타 선택"),
    "education_other_text": ("education", "기타 내용"),
    "education_amount": ("education", "금액"),
    "startup_working_capital_check": ("startup", "운용자금"),
    "startup_other_check": ("startup", "기타 선택"),
    "startup_other_text": ("startup", "기타 내용"),
    "startup_amount": ("startup", "금액"),
    "medical_self_check": ("medical", "본인 의료비"),
    "medical_family_check": ("medical", "가구원 의료비"),
    "medical_equipment_check": ("medical", "의료보장구"),
    "medical_care_check": ("medical", "돌봄 비용"),
    "medical_other_check": ("medical", "기타 선택"),
    "medical_other_text": ("medical", "기타 내용"),
    "medical_amount": ("medical", "금액"),
    "finance_isa_check": ("finance", "개인종합자산관리계좌(ISA)"),
    "finance_savings_check": ("finance", "적금상품 가입"),
    "finance_other_check": ("finance", "기타 선택"),
    "finance_other_text": ("finance", "기타 내용"),
    "finance_amount": ("finance", "금액"),
    "childcare_other_check": ("childcare", "기타 선택"),
    "childcare_other_text": ("childcare", "기타 내용"),
    "childcare_amount": ("childcare", "금액"),
    "marriage_other_check": ("marriage", "기타 선택"),
    "marriage_other_text": ("marriage", "기타 내용"),
    "marriage_amount": ("marriage", "금액"),
    "self_reliance_other_check": ("self_reliance", "기타 선택"),
    "self_reliance_other_text": ("self_reliance", "기타 내용"),
    "self_reliance_amount": ("self_reliance", "금액"),
}
for _field_id, (_category, _leaf) in _CATEGORY_LEAVES.items():
    SEMANTIC_PATHS[_field_id] = ["사용용도계획", _CATEGORY_PATHS[_category], _leaf]

RENDER_ONLY_FIELDS = {"usage_plan_note"}


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
    expected_ids = {item["id"] for item in FIELDS}
    candidates = [AUTHORING / "schema.json", *sorted((AUTHORING / "backups").glob("*/schema.json"), reverse=True)]
    recovered: dict[str, Any] | None = None
    recovered_from: Path | None = None
    for candidate in candidates:
        if not candidate.exists():
            continue
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        fields = payload.get("fields") if isinstance(payload.get("fields"), list) else []
        if {str(item.get("field_id") or "") for item in fields if isinstance(item, dict)} != expected_ids:
            continue
        if Path(str(payload.get("source_image") or "")).name != ORIGINAL_BLANK.name:
            continue
        recovered = deepcopy(payload)
        recovered_from = candidate
        break
    if recovered is None or recovered_from is None:
        raise RuntimeError("no complete 58-field page_001 authoring bundle is available for RPT-01 recovery")

    semantic_schema = build_semantic_schema()
    with Image.open(ORIGINAL_BLANK) as source_image:
        image_width, image_height = source_image.size
    review = json.loads(REVIEW_PAGE1.read_text(encoding="utf-8"))
    use_ids = {str(item.get("id") or "") for item in review.get("labels", []) if isinstance(item, dict) and item.get("status") == "use"}
    fields_by_id = {str(item.get("field_id")): item for item in recovered["fields"] if isinstance(item, dict)}
    normalized_fields: list[dict[str, Any]] = []
    for spec in FIELDS:
        field_id = spec["id"]
        item = deepcopy(fields_by_id[field_id])
        bbox_label_id = str(item.get("bbox_label_id") or item.get("source_detection_id") or "")
        if bbox_label_id not in use_ids:
            raise RuntimeError(f"{field_id} does not map to a page_001 use bbox: {bbox_label_id}")
        if field_id in RENDER_ONLY_FIELDS:
            item.pop("semantic_path", None)
            item["export"] = {"include": False, "json_path": "", "csv_column": ""}
            item.setdefault("render_policy", {})["render"] = False
        else:
            path = SEMANTIC_PATHS[field_id]
            item["semantic_path"] = path
            item["export"] = {"json_path": "/".join(path), "csv_column": "/".join(path)}
        item["generator"] = "literal:"
        item["render_mode"] = "printed"
        item["required"] = False
        item["notes"] = "page_001 빈 템플릿의 review use bbox에 연결됨. page_002는 값·스타일 예제 참고자료로만 사용."
        normalized_fields.append(item)

    recovered.update(
        {
            "schema_version": 1,
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "title": "자산형성지원사업 자금사용계획서",
            "sample_kind": "blank_template",
            "source_review": str(REVIEW_PAGE1.resolve()),
            "source_image": str(ORIGINAL_BLANK.resolve()),
            "source_inpainted": str(ORIGINAL_BLANK.resolve()),
            "image": {"width": image_width, "height": image_height},
            "reference_images": [{"path": str(FILLED_REFERENCE.resolve()), "role": "filled_example", "render_source": False}],
            "bbox_source": {"canonical": "review", "review_path": str(REVIEW_PAGE1.resolve())},
            "semantic_schema": semantic_schema,
            "fields": normalized_fields,
            "groups": [
                {"group_id": "account_selection", "type": "checkbox_group", "fields": ["account_hope_check", "account_youth_check", "hope_join_month", "youth_join_month"]},
                {"group_id": "usage_plan", "type": "amount_table", "notes": "category amounts sum to usage_total_amount through one correlated record"},
            ],
            "authoring_mode": "rpt01_blank_template_restored_and_refined_20260713",
            "quality_status": "restored_and_validated",
            "recovery_source": str(recovered_from.resolve()),
        }
    )
    recovered.pop("anchor_map_ref", None)
    return recovered


def build_stylesheet(schema: dict[str, Any]) -> dict[str, Any]:
    current_path = AUTHORING / "stylesheet.json"
    if current_path.exists():
        current = json.loads(current_path.read_text(encoding="utf-8"))
        classes = current.get("style_classes") if isinstance(current.get("style_classes"), list) else []
        class_ids = {str(item.get("style_class") or "") for item in classes if isinstance(item, dict)}
        expected = {str(field.get("style_class") or "") for field in schema["fields"]}
        if expected <= class_ids:
            current["notes"] = [
                "page_002 filled example을 참고해 복원·재매핑된 58개 bbox별 스타일을 보존한다.",
                "page_001만 실제 렌더 템플릿이며 page_002는 렌더 source로 사용하지 않는다.",
            ]
            return current
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


def build_semantic_schema() -> dict[str, Any]:
    semantic_schema: dict[str, Any] = {}
    for path in SEMANTIC_PATHS.values():
        cursor = semantic_schema
        for part in path[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[path[-1]] = ""
    return semantic_schema


def krw(value: int) -> str:
    return f"{value:,}"


def make_profiles() -> list[dict[str, str]]:
    names = [
        "김민준", "이서연", "박도윤", "최하은", "정현우", "강지우", "조시윤", "윤서준",
        "장예린", "임지호", "한수아", "오민재", "서다은", "신준서", "권유진", "황태윤",
        "안채원", "송건우", "전소윤", "홍재민", "문가은", "배시우", "백나연", "유도현",
    ]
    other_uses = {
        "housing": ["이사비", "중개보수", "입주청소비", "도배·장판 교체비", "보일러 수리비", "창호 보수비"],
        "education": ["온라인강의 수강료", "실습재료비", "전문서적 구입비", "직업훈련 교통비", "교육용 장비 대여료", "현장실습비"],
        "startup": ["사업장 임차료", "원재료 구입비", "포장재 구입비", "온라인몰 구축비", "업무용 장비 구입비", "시제품 제작비"],
        "medical": ["치과 치료비", "재활치료비", "처방약 구입비", "건강검진비", "간병용품 구입비", "수술 후 관리비"],
        "finance": ["주택청약종합저축", "정기예금 가입", "연금저축 납입", "비상예비자금 예치", "주거자금 적립", "창업준비자금 적립"],
        "childcare": ["아이돌봄서비스 본인부담금", "보육시설 특별활동비", "급식비", "통학차량비", "영유아 교구 구입비", "긴급돌봄 이용료"],
        "marriage": ["예식장 대관료", "예식 식대", "웨딩촬영비", "신혼집 이사비", "혼수용품 구입비", "청첩장 제작비"],
        "self_reliance": ["운전면허 취득비", "면접복장 구입비", "업무용 컴퓨터 구입비", "직업상담비", "취업교육 참가비", "작업도구 구입비"],
    }
    category_fields = {
        "housing": {
            "amount": "housing_amount",
            "choices": ["housing_self_purchase_check", "housing_deposit_check", "housing_rent_check", "housing_loan_check", "housing_repair_check", "housing_dorm_check", "housing_other_check"],
            "other_check": "housing_other_check",
            "other_text": "housing_other_text",
        },
        "education": {
            "amount": "education_amount",
            "choices": ["education_tuition_check", "education_books_check", "education_loan_check", "education_exam_check", "education_academy_check", "education_certificate_check", "education_other_check"],
            "other_check": "education_other_check",
            "other_text": "education_other_text",
        },
        "startup": {"amount": "startup_amount", "choices": ["startup_working_capital_check", "startup_other_check"], "other_check": "startup_other_check", "other_text": "startup_other_text"},
        "medical": {"amount": "medical_amount", "choices": ["medical_self_check", "medical_family_check", "medical_equipment_check", "medical_care_check", "medical_other_check"], "other_check": "medical_other_check", "other_text": "medical_other_text"},
        "finance": {"amount": "finance_amount", "choices": ["finance_isa_check", "finance_savings_check", "finance_other_check"], "other_check": "finance_other_check", "other_text": "finance_other_text"},
        "childcare": {"amount": "childcare_amount", "choices": ["childcare_other_check"], "other_check": "childcare_other_check", "other_text": "childcare_other_text"},
        "marriage": {"amount": "marriage_amount", "choices": ["marriage_other_check"], "other_check": "marriage_other_check", "other_text": "marriage_other_text"},
        "self_reliance": {"amount": "self_reliance_amount", "choices": ["self_reliance_other_check"], "other_check": "self_reliance_other_check", "other_text": "self_reliance_other_text"},
    }
    categories = list(category_fields)
    profiles: list[dict[str, str]] = []
    for idx, name in enumerate(names):
        is_youth = idx % 3 != 2
        application_date = date(2024 + idx % 3, 1 + idx % 7, 3 + idx % 10)
        join_date = application_date - timedelta(days=180 + (idx % 6) * 30)
        birth_year = (1990 + idx % 14) if is_youth else (1980 + idx % 12)
        birth_date = date(birth_year, 1 + idx % 12, 1 + (idx * 3) % 27)
        record = {item["id"]: "" for item in FIELDS}
        active_count = 2 + idx % 4
        active_categories = {categories[(idx + offset * 2) % len(categories)] for offset in range(active_count)}
        amounts: dict[str, int] = {}
        for category, spec in category_fields.items():
            if category not in active_categories:
                amounts[category] = 0
                continue
            amount = (4 + ((idx * 3 + categories.index(category)) % 18)) * 100_000
            if amount % 200_000:
                amount += 100_000
            amounts[category] = amount
            choice = spec["choices"][(idx + categories.index(category)) % len(spec["choices"])]
            record[choice] = CHECK
            if choice == spec["other_check"]:
                record[spec["other_text"]] = other_uses[category][idx % len(other_uses[category])]
            record[spec["amount"]] = krw(amount)
        total = sum(amounts.values())
        personal = total // 2
        support = total - personal
        record.update(
            {
                "account_hope_check": CHECK if not is_youth else "",
                "account_youth_check": CHECK if is_youth else "",
                "hope_join_month": f"{join_date.year}년 {join_date.month}월" if not is_youth else "",
                "youth_join_month": f"{join_date.year}년 {join_date.month}월" if is_youth else "",
                "applicant_name": name,
                "birth_date": f"{birth_date.year}.{birth_date.month}.{birth_date.day}.",
                "total_grant_amount_text": f"{krw(total)}원 (본인저축금+근로소득장려금 총액을 기재)",
                "personal_saving_text": f"{krw(personal)}원 (본인저축금을 기재)",
                "support_amount_text": f"{krw(support)}원 (근로소득장려금을 기재)",
                "usage_plan_note": "",
                "usage_total_amount": krw(total),
                "application_year": str(application_date.year),
                "application_month": str(application_date.month),
                "application_day": str(application_date.day),
                "signature_name": name,
            }
        )
        profiles.append(record)
    return profiles


def validate_profiles(profiles: list[dict[str, str]]) -> None:
    amount_fields = [
        "housing_amount", "education_amount", "startup_amount", "medical_amount",
        "finance_amount", "childcare_amount", "marriage_amount", "self_reliance_amount",
    ]

    def amount(value: str) -> int:
        digits = "".join(char for char in str(value).split("원", 1)[0] if char.isdigit())
        return int(digits or 0)

    for index, record in enumerate(profiles):
        if set(record) != {item["id"] for item in FIELDS}:
            raise ValueError(f"profile {index} does not cover all 58 fields")
        if sum(bool(record[field]) for field in ("account_hope_check", "account_youth_check")) != 1:
            raise ValueError(f"profile {index} must select exactly one account type")
        if bool(record["hope_join_month"]) != bool(record["account_hope_check"]):
            raise ValueError(f"profile {index} hope account join month mismatch")
        if bool(record["youth_join_month"]) != bool(record["account_youth_check"]):
            raise ValueError(f"profile {index} youth account join month mismatch")
        category_sum = sum(amount(record[field]) for field in amount_fields)
        total = amount(record["usage_total_amount"])
        if category_sum != total:
            raise ValueError(f"profile {index} usage amount sum mismatch: {category_sum} != {total}")
        if amount(record["total_grant_amount_text"]) != total:
            raise ValueError(f"profile {index} grant total mismatch")
        if amount(record["personal_saving_text"]) + amount(record["support_amount_text"]) != total:
            raise ValueError(f"profile {index} grant split mismatch")
        if record["signature_name"] != record["applicant_name"]:
            raise ValueError(f"profile {index} applicant/signature mismatch")
        application = date(int(record["application_year"]), int(record["application_month"]), int(record["application_day"]))
        if application > date(2026, 7, 13):
            raise ValueError(f"profile {index} application date exceeds as_of_date")


def build_faker_profile(schema: dict[str, Any]) -> dict[str, Any]:
    field_ids = [field["field_id"] for field in schema["fields"]]
    profiles = make_profiles()
    validate_profiles(profiles)
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "locale": "ko_KR",
        "as_of_date": "2026-07-13",
        "field_generators": {field_id: "literal:" for field_id in field_ids},
        "constraints": [{"type": "pick_record", "pool": "rpt01_profiles", "targets": {field_id: field_id for field_id in field_ids}}],
        "data_pools": {"rpt01_profiles": profiles},
        "pool_policies": {
            "rpt01_profiles": {
                "kind": "correlated_record",
                "min_size": 24,
                "synthetic_only": True,
                "evidence_note": "page_002 작성 예제와 page_001 양식의 관계를 기준으로 계좌종류·가입월·신청자·항목 선택·금액·합계·신청일·서명을 한 레코드로 묶음",
            }
        },
        "field_rules": [
            {"relationship": "exclusive_account_type", "fields": ["account_hope_check", "account_youth_check"], "rule": "exactly one is selected and only its join month is populated"},
            {"relationship": "grant_split", "fields": ["total_grant_amount_text", "personal_saving_text", "support_amount_text"], "rule": "total equals personal saving plus support"},
            {"relationship": "usage_sum", "fields": [field_id for field_id in field_ids if field_id.endswith("_amount")], "rule": "category amounts sum to usage_total_amount"},
            {"relationship": "identity_copy", "fields": ["applicant_name", "signature_name"], "rule": "signature name equals applicant name"},
        ],
        "notes": "24개 상관관계 record pool. 모든 58개 use bbox에 값을 제공하면서 통장종류, 가입월, 지급액 분할, 사용용도 선택·금액·총합, 신청일, 서명 정합성을 함께 유지한다.",
    }


def render_batch(schema_path: Path, style_path: Path, faker_path: Path, count: int = 5) -> dict[str, Any]:
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
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(
        f"""# 2026-07-13 RPT-01 자금사용계획서 복원 및 품질 개선

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
- faker profile은 24개의 `rpt01_profiles` 상관관계 record pool을 사용하며, 항목별 금액 합계가 `usage_total_amount`와 일치하도록 생성했다.
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
- warning은 선택되지 않은 선택형/기타 필드가 렌더되지 않았다는 `not_rendered` 알림이며, 값이 없는 필드는 최종 GT bbox에서 제외된다.

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
    stylesheet = build_stylesheet(schema)
    faker = build_faker_profile(schema)
    schema_path = AUTHORING / "schema.json"
    style_path = AUTHORING / "stylesheet.json"
    faker_path = AUTHORING / "faker_profile.json"
    consistency = _authoring_bundle_consistency(schema, faker, strict_review_coverage=True, min_pool_size=20)
    faker_errors = _validate_faker_profile_contract(faker, schema["fields"], min_pool_size=20, min_record_pool_size=12)
    if consistency["errors"] or faker_errors:
        raise RuntimeError(json.dumps({"consistency": consistency, "faker_errors": faker_errors}, ensure_ascii=False, indent=2))
    save_authoring_bundle(
        schema_path,
        style_path,
        faker_path,
        schema=schema,
        stylesheet=stylesheet,
        faker_profile=faker,
    )
    preview = render_authoring_preview(schema_path, style_path, faker_path, out_dir=OUT_DIR, seed=20260702, sample_id="preview_000001")
    summary = render_batch(schema_path, style_path, faker_path, count=5)
    comparison = compare(preview.image)
    update_manifest_artifact(DOC_ID, "authoring", schema_path)
    update_manifest_artifact(DOC_ID, "review", REVIEW_PAGE1)
    update_manifest_artifact(DOC_ID, "authoring_semantic_schema", SEMANTIC_SCHEMA)
    update_manifest_artifact(DOC_ID, "authoring_stylesheet", style_path)
    update_manifest_artifact(DOC_ID, "authoring_faker_profile", faker_path)
    update_manifest_artifact(DOC_ID, "authoring_preview", preview.image)
    update_manifest_artifact(DOC_ID, "authoring_overlay", preview.overlay)
    update_manifest_artifact(DOC_ID, "authoring_batch", BATCH_DIR / "summary.json")
    update_manifest_artifact(DOC_ID, "authoring_contact_sheet", BATCH_DIR / "contact_sheet.jpg")
    update_manifest_artifact(DOC_ID, "authoring_style_comparison", comparison)
    write_progress(summary, comparison, preview.image)
    print("consistency", json.dumps(consistency["summary"], ensure_ascii=False), "record_pool", len(faker["data_pools"]["rpt01_profiles"]))
    print("preview", preview.image, "warnings", preview.warning_count)
    print("batch", BATCH_DIR / "summary.json", "warnings", summary["warning_count"])
    print("contact", BATCH_DIR / "contact_sheet.jpg")
    print("comparison", comparison)


if __name__ == "__main__":
    main()
