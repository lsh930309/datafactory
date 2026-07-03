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

DOC_ID = "CRD-02"
DOC_TITLE = "기업신용등급평가서"
DOC_DIR = ROOT / "workbench" / "documents" / "기업신용등급평가서__CRD-02"
AUTHORING = DOC_DIR / "authoring"
PAGE1_DIR = AUTHORING / "page_001"
PAGE2_DIR = AUTHORING / "page_002"
TEMPLATE_DIR = AUTHORING / "templates"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "CRD-02_기업신용등급평가서"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "CRD-02_기업신용등급평가서"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_crd02_corporate_credit_rating_pipeline_readiness.md"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
PAGES = {
    1: DOC_DIR / "samples" / "original" / "기업신용평가서_page_001.jpg",
    2: DOC_DIR / "samples" / "original" / "기업신용평가서_page_002.jpg",
}
PAGE1_INPAINT = DOC_DIR / "inpaint" / "original_기업신용평가서_page_001" / "manual_cleanup" / "inpainted_lama.png"
FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()
NAVY = [0, 0, 125]
DARK = [30, 30, 30]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def field(
    field_id: str,
    label: str,
    bbox: list[int],
    style_class: str,
    *,
    page: int,
    value_type: str = "free_text.short",
    align: str = "left",
    overflow: str = "shrink",
    json_path: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    fit = {"shrink": "shrink_to_fit", "clip": "clip", "allow": "allow_overflow", "wrap": "wrap"}.get(overflow, "shrink_to_fit")
    return {
        "field_id": field_id,
        "label": label,
        "bbox": bbox,
        "bbox_format": "xywh",
        "source_detection_id": "manual_crd02_pipeline_ready_20260702",
        "source_text": "",
        "value_type": value_type,
        "generator": f"pool_record:crd02_profiles.{field_id}",
        "style_class": style_class,
        "render_policy": {"align": align, "valign": "middle", "fit": fit, "overflow": overflow},
        "export": {"json_path": json_path or field_id.replace("_", "."), "csv_column": field_id},
        "required": False,
        "notes": notes or f"CRD-02 page {page} 생산용 수동 bbox/style 보정 필드. crop 비교 없이 전체 문서/overlay 기준으로 검수.",
    }


def style_class(
    style_id: str,
    size: int,
    *,
    align: str = "left",
    opacity: float = 0.90,
    color: list[int] | None = None,
    weight: str = "normal",
    letter_spacing: float = 0.0,
    line_spacing: float = 1.0,
) -> dict[str, Any]:
    return {
        "style_class": style_id,
        "font_family": FONT_FAMILY,
        "font_path": FONT,
        "font_size": size,
        "font_weight": weight,
        "fill": color or DARK,
        "opacity": opacity,
        "align": align,
        "valign": "middle",
        "line_spacing": line_spacing,
        "letter_spacing": letter_spacing,
        "baseline_shift": 0,
        "overflow": "shrink",
        "confidence": 0.78,
        "source_detection_ids": ["manual_crd02_pipeline_ready_20260702"],
    }


def sample_fill(image: Image.Image, x: int, y: int) -> tuple[int, int, int]:
    px = image.getpixel((max(0, min(image.width - 1, x)), max(0, min(image.height - 1, y))))
    if isinstance(px, int):
        return (px, px, px)
    return tuple(px[:3])  # type: ignore[return-value]


def clear_rect(draw: ImageDraw.ImageDraw, bbox: list[int], *, fill: tuple[int, int, int], inset: int = 2) -> None:
    x, y, w, h = bbox
    draw.rectangle([x + inset, y + inset, x + w - inset, y + h - inset], fill=fill)


def redraw_page2_grids(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image)
    grid = (40, 68, 80)
    # 기업개요 표
    x0, x1 = 129, 1050
    xs = [129, 294, 555, 767, 1050]
    ys = [230, 259, 288, 317, 346, 375, 405]
    # Do not repaint label cells: the original labels are static and must be preserved.
    # Only redraw table grid lines after value-cell clearing.
    for x in xs:
        if x in [555, 767]:
            draw.line([(x, ys[0]), (x, ys[-2])], fill=grid, width=1)
        else:
            draw.line([(x, ys[0]), (x, ys[-1])], fill=grid, width=1)
    for y in ys:
        draw.line([(x0, y), (x1, y)], fill=grid, width=1)
    # 주요재무현황/비율 표 테두리 복구
    for top, bottom, rows in [
        (467, 612, [467, 496, 525, 554, 583, 612]),
        (672, 960, [672, 701, 730, 759, 788, 817, 846, 875, 904, 933, 960]),
    ]:
        xs2 = [129, 360, 590, 821, 1050]
        for y in rows:
            draw.line([(129, y), (1050, y)], fill=grid, width=1)
        for x in xs2:
            draw.line([(x, top), (x, bottom)], fill=grid, width=1)
        draw.rectangle([129, top, 1050, rows[1]], outline=grid, width=1)
    # 특기사항 박스
    draw.rectangle([129, 1041, 1050, 1125], outline=grid, width=1)


def make_blank_templates() -> dict[int, Path]:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[int, Path] = {}

    # Page 1: start from user-cleaned LaMa template, then deterministically erase residual glyphs.
    p1_src = PAGE1_INPAINT if PAGE1_INPAINT.exists() else PAGES[1]
    p1 = Image.open(p1_src).convert("RGB")
    d1 = ImageDraw.Draw(p1)
    white = (255, 255, 255)
    for rect in [
        [202, 132, 215, 24],
        [202, 160, 205, 24],
        [145, 390, 285, 58],
        [366, 476, 354, 441],
        [755, 842, 305, 70],
    ]:
        clear_rect(d1, rect, fill=white, inset=1)
    # Restore table grid where page-1 value cells were scrubbed.
    grid = (36, 70, 82)
    for y in [476, 520, 565, 610, 655, 734, 779, 824, 869, 915]:
        d1.line([(135, y), (720, y)], fill=grid, width=1)
    for x in [135, 365, 720]:
        d1.line([(x, 476), (x, 915)], fill=grid, width=1)
    p1_out = TEMPLATE_DIR / "blank_page_001.png"
    p1.save(p1_out)
    out[1] = p1_out

    # Page 2: create a clean value-template from filled page by clearing data cells.
    p2 = Image.open(PAGES[2]).convert("RGB")
    d2 = ImageDraw.Draw(p2)
    # Header numbers
    for rect in [[205, 132, 210, 24]]:
        clear_rect(d2, rect, fill=white, inset=1)
    # Company overview values
    for rect in [
        [294, 230, 261, 29],
        [767, 230, 283, 29],
        [294, 259, 261, 29],
        [767, 259, 283, 29],
        [294, 288, 261, 29],
        [767, 288, 283, 29],
        [294, 317, 261, 29],
        [767, 317, 283, 29],
        [294, 346, 261, 29],
        [767, 346, 283, 29],
        [294, 375, 756, 30],
    ]:
        clear_rect(d2, rect, fill=white, inset=2)
    # Financial table headers and values.
    for rect in [
        [360, 467, 230, 29], [590, 467, 231, 29], [821, 467, 229, 29],
        [360, 496, 230, 116], [590, 496, 231, 116], [821, 496, 229, 116],
        [360, 672, 230, 29], [590, 672, 231, 29], [821, 672, 229, 29],
        [360, 701, 230, 259], [590, 701, 231, 259], [821, 701, 229, 259],
        [130, 1042, 919, 82],
    ]:
        clear_rect(d2, rect, fill=white, inset=2)
    redraw_page2_grids(p2)
    p2_out = TEMPLATE_DIR / "blank_page_002.png"
    p2.save(p2_out)
    out[2] = p2_out
    return out


PAGE1_FIELDS = [
    ("certificate_serial_number", "일련번호", [206, 134, 210, 21], "style_header", "free_text.short", "left"),
    ("issue_number", "교부번호", [206, 161, 205, 22], "style_header", "free_text.short", "left"),
    ("recipient_company_name", "수신 기업체명", [149, 400, 175, 40], "style_recipient", "company.name_ko", "left"),
    ("recipient_suffix", "수신처 접미어", [330, 400, 70, 40], "style_recipient", "free_text.short", "left"),
    ("evaluated_company_name", "기업체", [374, 482, 325, 29], "style_table_value", "company.name_ko", "left"),
    ("representative_name", "대표자", [374, 526, 160, 30], "style_table_value", "person.name_ko", "left"),
    ("corporate_registration_number", "법인등록번호", [374, 571, 210, 29], "style_table_value", "free_text.short", "left"),
    ("business_registration_number", "사업자등록번호", [374, 617, 180, 29], "style_table_value", "free_text.short", "left"),
    ("headquarters_address", "주소", [374, 664, 335, 61], "style_table_value", "address.ko", "left"),
    ("fiscal_year_end", "재무결산기준일", [374, 740, 180, 30], "style_table_value", "date.kr", "left"),
    ("rating_evaluation_date", "등급평가일", [374, 781, 180, 30], "style_table_value", "date.kr", "left"),
    ("rating_valid_until", "등급유효기한", [374, 825, 180, 30], "style_table_value", "date.kr", "left"),
    ("submission_purpose", "제출처 및 용도", [374, 876, 185, 29], "style_table_value", "free_text.short", "left"),
    ("credit_rating", "기업신용평가등급", [775, 638, 230, 90], "style_credit_rating", "free_text.short", "center"),
    ("rating_description", "등급 설명", [755, 842, 300, 68], "style_rating_description", "free_text.long", "left"),
]

P2_OVERVIEW = [
    ("p2_certificate_serial_number", "일련번호", [206, 134, 210, 21], "style_header", "free_text.short", "left"),
    ("p2_company_name", "기업체", [304, 232, 235, 25], "style_p2_cell", "company.name_ko", "left"),
    ("p2_corporate_registration_number", "법인등록번호", [777, 232, 195, 25], "style_p2_cell", "free_text.short", "left"),
    ("p2_representative_name", "대표자", [304, 261, 160, 25], "style_p2_cell", "person.name_ko", "left"),
    ("p2_business_registration_number", "사업자등록번호", [777, 261, 180, 25], "style_p2_cell", "free_text.short", "left"),
    ("p2_established_date", "설립일자", [304, 290, 160, 25], "style_p2_cell", "date.kr", "left"),
    ("p2_employee_count", "종업원수", [777, 290, 130, 25], "style_p2_cell", "free_text.short", "left"),
    ("p2_company_type", "기업형태", [304, 319, 180, 25], "style_p2_cell", "free_text.short", "left"),
    ("p2_company_size", "기업규모", [777, 319, 180, 25], "style_p2_cell", "free_text.short", "left"),
    ("p2_industry", "업종", [304, 348, 240, 25], "style_p2_small", "free_text.short", "left"),
    ("p2_main_products", "주요매출품목", [777, 348, 245, 25], "style_p2_cell", "free_text.short", "left"),
    ("p2_headquarters_address", "주소", [304, 377, 720, 25], "style_p2_cell", "address.ko", "left"),
]

FIN_ROWS = [
    ("total_assets", "총자산", 496),
    ("equity_capital", "자기자본", 525),
    ("sales", "매출액", 554),
    ("net_income", "당기순이익", 583),
]
RATIO_ROWS = [
    ("operating_margin", "매출액영업이익률", 701),
    ("ordinary_margin", "매출액경상이익률", 730),
    ("current_ratio", "유동비율", 759),
    ("debt_dependency", "차입금의존도", 788),
    ("debt_ratio", "부채비율", 817),
    ("asset_growth", "총자산증가율", 846),
    ("sales_growth", "매출액증가율", 875),
    ("capital_turnover", "총자본회전율", 904),
    ("receivable_turnover", "매출채권회전율", 933),
]
YEAR_COLS = [("y1", 360, 230), ("y2", 590, 231), ("y3", 821, 229)]


def build_page_schema(page: int, template: Path) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    if page == 1:
        for fid, label, bbox, style, vtype, align in PAGE1_FIELDS:
            fields.append(
                field(
                    fid,
                    label,
                    bbox,
                    style,
                    page=page,
                    value_type=vtype,
                    align=align,
                    overflow="wrap" if fid == "rating_description" else "shrink",
                    json_path=f"page1.{fid}",
                )
            )
    else:
        for fid, label, bbox, style, vtype, align in P2_OVERVIEW:
            fields.append(field(fid, label, bbox, style, page=page, value_type=vtype, align=align, json_path=f"page2.overview.{fid}"))
        for key, x, w in YEAR_COLS:
            fields.append(field(f"p2_financial_year_{key}", f"주요재무현황 {key} 기준연월", [x, 469, w, 25], "style_p2_header", page=page, align="center", json_path=f"page2.financial.years.{key}"))
        for row_key, label, y in FIN_ROWS:
            for key, x, w in YEAR_COLS:
                fields.append(field(f"p2_financial_{row_key}_{key}", f"{label} {key}", [x + 6, y + 2, w - 12, 25], "style_p2_number", page=page, value_type="money.krw", align="right", json_path=f"page2.financial.{row_key}.{key}"))
        for key, x, w in YEAR_COLS:
            fields.append(field(f"p2_ratio_year_{key}", f"주요재무비율 {key} 기준연월", [x, 674, w, 25], "style_p2_header", page=page, align="center", json_path=f"page2.ratios.years.{key}"))
        for row_key, label, y in RATIO_ROWS:
            for key, x, w in YEAR_COLS:
                fields.append(field(f"p2_ratio_{row_key}_{key}", f"{label} {key}", [x + 8, y + 2, w - 16, 25], "style_p2_number", page=page, align="right", json_path=f"page2.ratios.{row_key}.{key}"))
        fields.append(field("p2_special_note", "특기사항", [133, 1044, 900, 35], "style_p2_cell", page=page, align="left", json_path="page2.special_note"))
    im = Image.open(PAGES[page])
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": f"{DOC_TITLE} page {page}",
        "page_index": page,
        "source_image": str(PAGES[page].resolve()),
        "source_inpainted": str(template.resolve()),
        "image": {"width": im.width, "height": im.height},
        "fields": fields,
        "groups": [
            {"group_id": "page1_certificate" if page == 1 else "page2_financial_tables", "type": "credit_rating_certificate", "notes": "CRD-02 생산용 확장 schema"},
        ],
        "authoring_mode": f"crd02_page_{page}_pipeline_ready_20260702",
        "quality_status": "pipeline_ready_candidate",
    }


def build_stylesheet() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "style_classes": [
            style_class("style_header", 15, opacity=0.92),
            style_class("style_recipient", 27, opacity=0.92),
            style_class("style_table_value", 22, opacity=0.88),
            style_class("style_credit_rating", 61, align="center", opacity=0.95, color=NAVY),
            style_class("style_rating_description", 17, opacity=0.93, color=DARK, line_spacing=1.18),
            style_class("style_p2_cell", 16, opacity=0.90),
            style_class("style_p2_small", 14, opacity=0.90),
            style_class("style_p2_header", 16, align="center", opacity=0.92, weight="bold"),
            style_class("style_p2_number", 15, align="right", opacity=0.90),
        ],
        "notes": "CRD-02 원본 렌더링의 굵고 선명한 국문 산세리프와 가장 유사한 Apple SD Gothic Neo를 선택했다. crop 비교는 제외하고 전체 문서 비교/overlay 기준으로 크기와 정렬을 보정했다.",
    }


def build_semantic_schema(schema_paths: list[Path]) -> dict[str, Any]:
    field_mapping: dict[str, str] = {}
    for path in schema_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        field_mapping.update({field["field_id"]: field["export"]["json_path"] for field in data.get("fields", [])})
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "purpose": "렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조",
        "semantic_schema": {
            "기업신용등급평가서": {
                "발급정보": {
                    "일련번호": "",
                    "교부번호": "",
                },
                "수신처": {
                    "기업명": "",
                    "접미어": "",
                },
                "평가대상기업": {
                    "기업체": "",
                    "대표자": "",
                    "법인등록번호": "",
                    "사업자등록번호": "",
                    "주소": "",
                    "재무결산기준일": "",
                    "등급평가일": "",
                    "등급유효기한": "",
                    "제출처 및 용도": "",
                },
                "신용평가": {
                    "기업신용평가등급": "",
                    "등급설명": "",
                },
                "기업개요": {
                    "기업체": "",
                    "법인등록번호": "",
                    "대표자": "",
                    "사업자등록번호": "",
                    "설립일자": "",
                    "종업원수": "",
                    "기업형태": "",
                    "기업규모": "",
                    "업종": "",
                    "주요매출품목": "",
                    "주소": "",
                },
                "주요재무현황": {
                    "기준연월": [],
                    "총자산": [],
                    "자기자본": [],
                    "매출액": [],
                    "당기순이익": [],
                },
                "주요재무비율": {
                    "기준연월": [],
                    "매출액영업이익률": [],
                    "매출액경상이익률": [],
                    "유동비율": [],
                    "차입금의존도": [],
                    "부채비율": [],
                    "총자산증가율": [],
                    "매출액증가율": [],
                    "총자본회전율": [],
                    "매출채권회전율": [],
                },
                "특기사항": "",
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "page_001/page_002 schema는 렌더러 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 KIE용 key-name 계층만 별도 관리한다.",
        ],
    }


def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_pct(v: float) -> str:
    return "-" if v is None else f"{v:.2f}"


def year_months(base_year: int) -> tuple[str, str, str]:
    return (f"{base_year - 2}년 12월", f"{base_year - 1}년 12월", f"{base_year}년 12월")


def make_profiles() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    companies = [
        ("서울평가정보", "홍길동", "서울특별시 영등포구 국회대로70길 23, 10층", "데이터베이스 및 온라인정보 제공업", "신용조회", "코스닥상장", "중소기업", "1992.04.23"),
        ("청명금속", "박도윤", "전라북도 전주시 덕진구 팔복로 59", "비철금속 압연 및 압출업", "알루미늄 부품", "외감", "중소기업", "2008.03.17"),
        ("한빛정밀", "이서준", "경기도 안산시 단원구 별망로 141", "기계장비 제조업", "정밀가공품", "일반", "중소기업", "2011.09.02"),
        ("대한소재", "김민지", "충청남도 천안시 서북구 직산읍 공단로 82", "화학소재 제조업", "산업용 필름", "외감", "중견기업", "2001.06.28"),
        ("새론패션", "최서연", "서울특별시 성동구 아차산로 103", "의복 액세서리 제조업", "패션잡화", "일반", "중소기업", "2017.11.14"),
        ("미래모빌리티", "정하준", "대구광역시 달서구 성서공단로 11", "자동차 부품 제조업", "전장모듈", "외감", "중견기업", "2004.02.05"),
        ("세종바이오", "윤지아", "대전광역시 유성구 테크노중앙로 50", "의약품 연구개발업", "진단시약", "코스닥상장", "중소기업", "2013.08.21"),
        ("아라전자", "강도현", "부산광역시 해운대구 센텀중앙로 79", "전자부품 제조업", "센서모듈", "외감", "중소기업", "2006.12.04"),
        ("누리패키징", "오서윤", "광주광역시 북구 첨단과기로 123", "포장재 제조업", "친환경 포장재", "일반", "중소기업", "2015.05.19"),
        ("동원테크놀로지", "조현우", "경상남도 창원시 성산구 완암로 50", "산업용 로봇 제조업", "자동화 설비", "외감", "중견기업", "1999.10.08"),
    ]
    ratings = ["AA+", "AA-", "A+", "A", "BBB+", "AA", "A-", "BBB", "BB+", "A+"]
    purposes = ["공공기관 제출용", "조달청 입찰 제출용", "협력업체 평가용", "납품업체 평가용", "계약심사 제출용"]
    notes = ["특기사항 없음", "최근 3개년 영업현금흐름 양호", "매출처 다변화 진행 중", "신규 설비투자에 따른 차입금 증가", "특기사항 없음"]
    profiles: list[dict[str, str]] = []
    for idx, company in enumerate(companies):
        name, rep, addr, industry, product, ctype, size, established = company
        base_year = 2024 + (idx % 2)
        years = year_months(base_year)
        rating = ratings[idx % len(ratings)]
        serial = f"PPR-{base_year + 1}-{(idx % 9) + 1}-{21299 + idx * 137}-U"
        issue = f"SCRI-{base_year + 1}{(idx % 12) + 1:02d}{(idx * 4 + 5) % 28 + 1:02d}-{idx + 9:03d}"
        corp = f"110{idx + 111:03d}-{853419 + idx * 731:06d}"
        biz = f"{114 + idx:03d}-{(81 + idx) % 90:02d}-{47958 + idx * 193:05d}"
        eval_month = ((idx + 3) % 12) + 1
        eval_day = ((idx * 4 + 9) % 28) + 1
        eval_date = f"{base_year + 1}년 {eval_month:02d}월 {eval_day:02d}일"
        valid_date = f"{base_year + 2}년 {eval_month:02d}월 {max(1, eval_day - 1):02d}일"
        assets3 = [rng.randint(45_000, 180_000) for _ in range(3)]
        assets3.sort()
        equity = [int(v * rng.uniform(0.35, 0.72)) for v in assets3]
        sales = [rng.randint(25_000, 160_000) for _ in range(3)]
        sales.sort()
        income = [max(250, int(s * rng.uniform(0.035, 0.16))) for s in sales]
        record: dict[str, str] = {
            "certificate_serial_number": serial,
            "issue_number": issue,
            "recipient_company_name": name,
            "recipient_suffix": "귀중",
            "evaluated_company_name": name,
            "representative_name": rep,
            "corporate_registration_number": corp,
            "business_registration_number": biz,
            "headquarters_address": addr,
            "fiscal_year_end": f"{base_year}년 12월 31일",
            "rating_evaluation_date": eval_date,
            "rating_valid_until": valid_date,
            "submission_purpose": purposes[idx % len(purposes)],
            "credit_rating": rating,
            "rating_description": f"상기등급은 회사채에 대한\n신용평가등급 {rating}에 준하는 등급임",
            "p2_certificate_serial_number": serial,
            "p2_company_name": name,
            "p2_corporate_registration_number": corp,
            "p2_representative_name": rep,
            "p2_business_registration_number": biz,
            "p2_established_date": established,
            "p2_employee_count": f"{rng.randint(35, 420)} 명",
            "p2_company_type": ctype,
            "p2_company_size": size,
            "p2_industry": industry,
            "p2_main_products": product,
            "p2_headquarters_address": addr,
            "p2_special_note": notes[idx % len(notes)],
        }
        for key, ym in zip(["y1", "y2", "y3"], years):
            record[f"p2_financial_year_{key}"] = ym
            record[f"p2_ratio_year_{key}"] = ym
        for col_idx, key in enumerate(["y1", "y2", "y3"]):
            record[f"p2_financial_total_assets_{key}"] = fmt_int(assets3[col_idx])
            record[f"p2_financial_equity_capital_{key}"] = fmt_int(equity[col_idx])
            record[f"p2_financial_sales_{key}"] = fmt_int(sales[col_idx])
            record[f"p2_financial_net_income_{key}"] = fmt_int(income[col_idx])
            op = income[col_idx] / max(sales[col_idx], 1) * 100 * rng.uniform(0.75, 1.05)
            ordinary = op * rng.uniform(0.75, 1.12)
            current = rng.uniform(95, 420) if rating.startswith(("A", "AA")) else rng.uniform(65, 250)
            debt_dep = rng.uniform(0, 42)
            debt_ratio = max(20, (assets3[col_idx] - equity[col_idx]) / max(equity[col_idx], 1) * 100)
            asset_growth = rng.uniform(-6, 24) if col_idx else rng.uniform(-3, 12)
            sales_growth = rng.uniform(-9, 28) if col_idx else rng.uniform(-5, 12)
            cap_turn = sales[col_idx] / max(assets3[col_idx], 1)
            rec_turn = rng.uniform(8, 45)
            ratios = {
                "operating_margin": op,
                "ordinary_margin": ordinary,
                "current_ratio": current,
                "debt_dependency": debt_dep,
                "debt_ratio": debt_ratio,
                "asset_growth": asset_growth,
                "sales_growth": sales_growth,
                "capital_turnover": cap_turn,
                "receivable_turnover": rec_turn,
            }
            for row_key, value in ratios.items():
                record[f"p2_ratio_{row_key}_{key}"] = fmt_pct(value)
        profiles.append(record)
    return profiles


def build_faker_profile(schema_paths: list[Path]) -> dict[str, Any]:
    field_ids: list[str] = []
    for path in schema_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        field_ids.extend(field["field_id"] for field in data["fields"])
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "locale": "ko_KR",
        "field_generators": {field_id: "literal:" for field_id in field_ids},
        "constraints": [{"type": "pick_record", "pool": "crd02_profiles", "targets": {field_id: field_id for field_id in field_ids}}],
        "data_pools": {"crd02_profiles": make_profiles()},
        "notes": "CRD-02 record profile. page1 인증서 값과 page2 기업개요/재무/비율 값이 같은 record에서 일관되게 생성된다.",
    }


def make_contact_sheet(pairs: list[list[Path]]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 220, 300
    sheet = Image.new("RGB", (len(pairs) * cell_w + 20, cell_h * 2 + 64), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, paths in enumerate(pairs):
        x = 20 + idx * cell_w
        draw.text((x, 14), f"crd02_{idx + 1:06d}", font=font, fill=(25, 25, 25))
        for row, path in enumerate(paths):
            image = Image.open(path).convert("RGB")
            image.thumbnail((cell_w - 18, cell_h - 32))
            y = 44 + row * cell_h
            draw.text((x, y - 17), f"page {row + 1}", font=font, fill=(70, 70, 70))
            sheet.paste(image, (x, y))
            draw.rectangle([x, y, x + image.width, y + image.height], outline=(155, 155, 155))
    out = BATCH_DIR / "contact_sheet.jpg"
    sheet.save(out, quality=92)
    return out


def render_pair(schema1: Path, schema2: Path, style_path: Path, faker_path: Path, *, count: int = 5) -> dict[str, Any]:
    if BATCH_DIR.exists():
        shutil.rmtree(BATCH_DIR)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    pairs: list[list[Path]] = []
    warnings = 0
    schema1_fields = len(json.loads(schema1.read_text(encoding="utf-8")).get("fields", []))
    schema2_fields = len(json.loads(schema2.read_text(encoding="utf-8")).get("fields", []))
    field_count = schema1_fields + schema2_fields
    for idx in range(1, count + 1):
        sid = f"crd02_{idx:06d}"
        seed = 20260702 + idx - 1
        r1 = render_authoring_preview(schema1, style_path, faker_path, out_dir=BATCH_DIR, seed=seed, sample_id=f"{sid}_page_001")
        r2 = render_authoring_preview(schema2, style_path, faker_path, out_dir=BATCH_DIR, seed=seed, sample_id=f"{sid}_page_002")
        warnings += r1.warning_count + r2.warning_count
        pairs.append([r1.image, r2.image])
        samples.append({
            "sample_id": sid,
            "pages": [
                {"page": 1, "image": str(r1.image), "kv": str(r1.kv), "bbox": str(r1.bbox), "overlay": str(r1.overlay), "validation_report": str(r1.validation_report), "warning_count": r1.warning_count},
                {"page": 2, "image": str(r2.image), "kv": str(r2.kv), "bbox": str(r2.bbox), "overlay": str(r2.overlay), "validation_report": str(r2.validation_report), "warning_count": r2.warning_count},
            ],
        })
    contact = make_contact_sheet(pairs)
    summary = {
        "schema_version": 1,
        "created_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "schemas": {"page_001": str(schema1), "page_002": str(schema2)},
        "stylesheet": str(style_path),
        "faker_profile": str(faker_path),
        "out_dir": str(BATCH_DIR),
        "count": count,
        "page_count": 2,
        "field_count_per_sample": field_count,
        "warning_count": warnings,
        "contact_sheet": str(contact),
        "samples": samples,
    }
    write_json(BATCH_DIR / "summary.json", summary)
    return summary


def compare(page: int, blank: Path, rendered: Path) -> Path:
    out_dir = CALIB_DIR / f"page_{page:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    original = Image.open(PAGES[page]).convert("RGB")
    blank_im = Image.open(blank).convert("RGB").resize(original.size)
    render = Image.open(rendered).convert("RGB").resize(original.size)
    diff = ImageChops.difference(blank_im, render)
    diff_amp = diff.point(lambda value: min(255, value * 4))
    overlay = Image.blend(blank_im, render, 0.5)
    labels = [("original filled", original), ("blank template", blank_im), ("render", render), ("amplified diff", diff_amp), ("50% overlay", overlay)]
    font = ImageFont.truetype(str(FONT_FALLBACK), 18) if FONT_FALLBACK.exists() else ImageFont.load_default()
    scale_w = 300
    thumbs = []
    for label, image in labels:
        thumb = image.copy()
        thumb.thumbnail((scale_w, 410))
        thumbs.append((label, thumb))
    sheet = Image.new("RGB", (scale_w * len(thumbs) + 20 * (len(thumbs) + 1), 480), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, thumb) in enumerate(thumbs):
        x = 20 + idx * (scale_w + 20)
        draw.text((x, 18), label, font=font, fill=(20, 20, 20))
        sheet.paste(thumb, (x, 52))
        draw.rectangle([x, 52, x + thumb.width, 52 + thumb.height], outline=(150, 150, 150))
    out = out_dir / "full_comparison.jpg"
    sheet.save(out, quality=92)
    diff.save(out_dir / "full_diff.png")
    overlay.save(out_dir / "full_overlay_50.png")
    return out


def write_progress(summary: dict[str, Any], comparisons: dict[int, Path]) -> None:
    PROGRESS.write_text(
        f"""# 2026-07-02 CRD-02 기업신용등급평가서 파이프라인 준비 작업

## 목표
- `CRD-02 기업신용등급평가서`를 단일 순차 대상으로 처리한다.
- 주주명부 방식과 동일하게 bbox/schema/faker/style을 문서별로 고정하고, 5세트 batch 렌더와 전체 문서 비교 산출물을 남긴다.
- crop 비교 루틴은 사용하지 않는다.

## 입력 상태
- page 1 original: `{PAGES[1]}`
- page 1 cleanup template seed: `{PAGE1_INPAINT}`
- page 2 original filled sample: `{PAGES[2]}`
- 기존 page 1 authoring은 14개 필드였으나, 위치/스타일이 원본 대비 크고 잔상이 남아 있어 재보정했다.

## 구현 내용
- page 1: 일련번호, 교부번호, 수신/평가 대상 회사, 수신처 접미어, 대표자, 법인/사업자등록번호, 주소, 기준일/평가일/유효기한, 제출처, 신용등급, 등급 설명 내 등급을 재정렬했다.
- page 2: 기존 미지원 상태였던 기업개요, 주요재무현황, 주요재무비율, 특기사항을 신규 field화했다.
- filled sample page 2는 값 영역만 deterministic white-fill로 제거하고 표 grid를 복구해 blank template로 사용했다.
- faker profile은 `crd02_profiles` record pool을 사용해 page 1 인증서 값과 page 2 기업개요/재무/비율 값이 한 record에서 일관되게 생성되도록 했다.
- font-family는 원본의 선명한 국문 산세리프 시각 정보에 근거해 `{FONT_FAMILY}`를 선택했다.

## 산출물
- page 1 schema: `{PAGE1_DIR / 'schema.json'}`
- page 2 schema: `{PAGE2_DIR / 'schema.json'}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
- stylesheet: `{AUTHORING / 'stylesheet.json'}`
- faker_profile: `{AUTHORING / 'faker_profile.json'}`
- page 1 blank template: `{TEMPLATE_DIR / 'blank_page_001.png'}`
- page 2 blank template: `{TEMPLATE_DIR / 'blank_page_002.png'}`
- batch summary: `{BATCH_DIR / 'summary.json'}`
- contact sheet: `{BATCH_DIR / 'contact_sheet.jpg'}`
- page 1 comparison: `{comparisons[1]}`
- page 2 comparison: `{comparisons[2]}`

## 검수 결과
- 생성 수: {summary['count']}세트
- page_count: {summary['page_count']}
- field_count_per_sample: {summary['field_count_per_sample']}
- warning_count: {summary['warning_count']}

## 한계 및 다음 조치
- page 1 우측 등급 배경은 원본 보안무늬 위에 등급만 치환하는 구조라 LaMa cleanup의 배경 잔상 품질에 영향을 받는다. 현재는 추가 white-fill 후 전체 문서 시각 비교 기준으로 수용 가능한 수준까지 보정했다.
- page 2는 원본 filled sample을 기반으로 값 영역을 제거한 템플릿이므로, 추후 GUI cleanup으로 더 깨끗한 blank template를 만들면 품질이 더 좋아진다.
""",
        encoding="utf-8",
    )


def main() -> None:
    for required in PAGES.values():
        if not required.exists():
            raise FileNotFoundError(required)
    AUTHORING.mkdir(parents=True, exist_ok=True)
    if CALIB_DIR.exists():
        shutil.rmtree(CALIB_DIR)
    blanks = make_blank_templates()
    schema1 = build_page_schema(1, blanks[1])
    schema2 = build_page_schema(2, blanks[2])
    p1 = PAGE1_DIR / "schema.json"
    p2 = PAGE2_DIR / "schema.json"
    style_path = AUTHORING / "stylesheet.json"
    faker_path = AUTHORING / "faker_profile.json"
    write_json(p1, schema1)
    write_json(p2, schema2)
    # Keep top-level schema pointing to page 1 for existing UI compatibility.
    write_json(AUTHORING / "schema.json", schema1)
    write_json(SEMANTIC_SCHEMA, build_semantic_schema([p1, p2]))
    write_json(style_path, build_stylesheet())
    write_json(faker_path, build_faker_profile([p1, p2]))
    preview1 = render_authoring_preview(p1, style_path, faker_path, out_dir=OUT_DIR, seed=20260702, sample_id="preview_page_001")
    preview2 = render_authoring_preview(p2, style_path, faker_path, out_dir=OUT_DIR, seed=20260702, sample_id="preview_page_002")
    summary = render_pair(p1, p2, style_path, faker_path, count=5)
    comparisons = {1: compare(1, blanks[1], preview1.image), 2: compare(2, blanks[2], preview2.image)}

    update_manifest_artifact(DOC_ID, "authoring", AUTHORING / "schema.json")
    update_manifest_artifact(DOC_ID, "authoring_semantic_schema", SEMANTIC_SCHEMA)
    update_manifest_artifact(DOC_ID, "authoring_page_001_schema", p1)
    update_manifest_artifact(DOC_ID, "authoring_page_002_schema", p2)
    update_manifest_artifact(DOC_ID, "authoring_stylesheet", style_path)
    update_manifest_artifact(DOC_ID, "authoring_faker_profile", faker_path)
    update_manifest_artifact(DOC_ID, "authoring_preview", preview1.image)
    update_manifest_artifact(DOC_ID, "authoring_page_002_preview", preview2.image)
    update_manifest_artifact(DOC_ID, "authoring_overlay", preview1.overlay)
    update_manifest_artifact(DOC_ID, "authoring_batch", BATCH_DIR / "summary.json")
    update_manifest_artifact(DOC_ID, "authoring_contact_sheet", BATCH_DIR / "contact_sheet.jpg")
    update_manifest_artifact(DOC_ID, "authoring_style_comparison", comparisons[1])
    update_manifest_artifact(DOC_ID, "authoring_page_002_style_comparison", comparisons[2])
    write_progress(summary, comparisons)

    print("preview1", preview1.image, "warnings", preview1.warning_count)
    print("preview2", preview2.image, "warnings", preview2.warning_count)
    print("batch", BATCH_DIR / "summary.json", "warnings", summary["warning_count"])
    print("contact", BATCH_DIR / "contact_sheet.jpg")
    print("comparison1", comparisons[1])
    print("comparison2", comparisons[2])


if __name__ == "__main__":
    main()
