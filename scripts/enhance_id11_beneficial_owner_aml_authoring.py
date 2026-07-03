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

DOC_ID = "ID-11"
DOC_TITLE = "실소유자 확인서(AML)"
DOC_DIR = ROOT / "workbench" / "documents" / "실소유자_확인서(AML)__ID-11"
AUTHORING = DOC_DIR / "authoring"
PAGE_DIRS = {page: AUTHORING / f"page_{page:03d}" for page in [1, 2, 3]}
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "ID-11_실소유자 확인서(AML)"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "ID-11_실소유자 확인서(AML)"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_id11_beneficial_owner_aml_pipeline_readiness.md"
PAGES = {
    1: DOC_DIR / "samples" / "original" / "실소유자확인서_page_001.jpg",
    2: DOC_DIR / "samples" / "original" / "실소유자확인서_page_002.jpg",
    3: DOC_DIR / "samples" / "original" / "실소유자확인서_page_003.jpg",
}
P1_TEMPLATE = DOC_DIR / "inpaint" / "original_실소유자확인서_page_001" / "lama" / "inpainted_lama.png"
FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()
DARK = [20, 20, 20]
CHECK = "✓"
EMPTY = ""


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def field(field_id: str, label: str, bbox: list[int], style_class: str, *, page: int, value_type: str = "free_text.short", align: str = "left", valign: str = "middle", json_path: str | None = None) -> dict[str, Any]:
    return {
        "field_id": field_id,
        "label": label,
        "bbox": bbox,
        "bbox_format": "xywh",
        "source_detection_id": "manual_id11_pipeline_ready_20260702",
        "source_text": "",
        "value_type": value_type,
        "generator": f"pool_record:id11_profiles.{field_id}",
        "style_class": style_class,
        "render_policy": {"align": align, "valign": valign, "fit": "shrink_to_fit", "overflow": "shrink"},
        "export": {"json_path": json_path or field_id.replace("_", "."), "csv_column": field_id},
        "required": False,
        "notes": f"ID-11 page {page} 생산용 수동 bbox/style 보정 필드. crop 비교 없이 전체 문서 기준으로 검수.",
    }


def style_class(style_id: str, size: int, *, align: str = "left", opacity: float = 0.92, color: list[int] | None = None, weight: str = "normal") -> dict[str, Any]:
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
        "line_spacing": 1.0,
        "letter_spacing": 0.0,
        "baseline_shift": 0,
        "overflow": "shrink",
        "confidence": 0.76,
        "source_detection_ids": ["manual_id11_pipeline_ready_20260702"],
    }


def template_for_page(page: int) -> Path:
    if page == 1 and P1_TEMPLATE.exists():
        return P1_TEMPLATE
    return PAGES[page]


# Page 1: existing reviewed coordinates, normalized into compact style classes.
P1_WRITER_TOP = [
    ("p1_writer_organization_name_top", "상단 작성인 기관명", [812, 524, 286, 30], "style_text", "left"),
    ("p1_writer_position_top", "상단 작성인 직책", [812, 557, 286, 30], "style_text", "left"),
    ("p1_writer_name_top", "상단 작성인 성명", [812, 590, 246, 30], "style_text", "left"),
]
P1_OWNER_COLS = [
    (1, 300, 185),
    (2, 496, 214),
    (3, 721, 204),
    (4, 934, 179),
]
P1_WRITER_BOTTOM = [
    ("p1_writer_organization_name_bottom", "하단 작성인 기관명", [502, 1397, 570, 30], "style_text", "left"),
    ("p1_writer_position_bottom", "하단 작성인 직책", [502, 1431, 570, 30], "style_text", "left"),
    ("p1_writer_name_bottom", "하단 작성인 성명", [502, 1464, 530, 30], "style_text", "left"),
]


def page1_fields() -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for fid, label, bbox, style, align in P1_WRITER_TOP:
        fields.append(field(fid, label, bbox, style, page=1, align=align, json_path=f"page1.writer.{fid}"))
    fields.append(field("p1_owner_path_25_percent_checkbox", "25% 이상 지분 소유자 체크", [1005, 751, 54, 31], "style_check", page=1, align="center", json_path="page1.owner_path.25_percent"))
    for idx, x, w in P1_OWNER_COLS:
        fields.extend([
            field(f"p1_owner_{idx}_name_ko", f"실소유자 {idx} 한글명", [x, 1083, w, 31], "style_text", page=1, align="left", json_path=f"page1.owners.{idx}.name_ko"),
            field(f"p1_owner_{idx}_name_en", f"실소유자 {idx} 영문명", [x, 1124, w, 28], "style_en", page=1, align="left", json_path=f"page1.owners.{idx}.name_en"),
            field(f"p1_owner_{idx}_birth_date", f"실소유자 {idx} 생년월일", [x, 1180, w, 32], "style_text", page=1, align="center", json_path=f"page1.owners.{idx}.birth_date"),
            field(f"p1_owner_{idx}_ownership_percent", f"실소유자 {idx} 지분율", [x, 1216, w - 22, 30], "style_text", page=1, align="right", json_path=f"page1.owners.{idx}.ownership_percent"),
            field(f"p1_owner_{idx}_nationality", f"실소유자 {idx} 국적", [x, 1310, w, 32], "style_text", page=1, align="center", json_path=f"page1.owners.{idx}.nationality"),
        ])
    for fid, label, bbox, style, align in P1_WRITER_BOTTOM:
        fields.append(field(fid, label, bbox, style, page=1, align=align, json_path=f"page1.writer.{fid}"))
    return fields


# Page 2: 법인 소유(출연)자 정보, 최대 5행.
P2_ROW_Y = [666, 783, 899, 1016, 1132]
P2_COLS = {
    # The printed personal/corporate checkboxes sit lower than the visual row top.
    "type_person_check": [162, 28, 18, 18],
    "type_corporation_check": [162, 56, 18, 18],
    # Keep the printed placeholder labels ((국문)/(영문성)/(영문명)) visible;
    # values start to the right of the labels instead of covering them.
    "name_ko": [318, 5, 176, 28],
    "name_en_surname": [318, 42, 176, 26],
    "name_en_given": [318, 78, 176, 26],
    "birth_or_reg_no": [512, 18, 125, 50],
    "nationality_or_address": [650, 18, 118, 50],
    "ownership_type_share": [783, 0, 18, 18],
    "ownership_percent": [907, 35, 160, 38],
}


def page2_fields() -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for idx, y in enumerate(P2_ROW_Y, start=1):
        fields.extend([
            field(f"p2_owner_{idx}_type_person_check", f"법인소유자 {idx} 개인 체크", [P2_COLS['type_person_check'][0], y + P2_COLS['type_person_check'][1], 26, 22], "style_check_small", page=2, align="center", json_path=f"page2.owners.{idx}.type_person"),
            field(f"p2_owner_{idx}_type_corporation_check", f"법인소유자 {idx} 법인 체크", [P2_COLS['type_corporation_check'][0], y + P2_COLS['type_corporation_check'][1], 26, 22], "style_check_small", page=2, align="center", json_path=f"page2.owners.{idx}.type_corporation"),
            field(f"p2_owner_{idx}_name_ko", f"법인소유자 {idx} 국문", [P2_COLS['name_ko'][0], y + P2_COLS['name_ko'][1], P2_COLS['name_ko'][2], P2_COLS['name_ko'][3]], "style_small", page=2, align="left", json_path=f"page2.owners.{idx}.name_ko"),
            field(f"p2_owner_{idx}_name_en_surname", f"법인소유자 {idx} 영문성", [P2_COLS['name_en_surname'][0], y + P2_COLS['name_en_surname'][1], P2_COLS['name_en_surname'][2], P2_COLS['name_en_surname'][3]], "style_small", page=2, align="left", json_path=f"page2.owners.{idx}.name_en_surname"),
            field(f"p2_owner_{idx}_name_en_given", f"법인소유자 {idx} 영문명", [P2_COLS['name_en_given'][0], y + P2_COLS['name_en_given'][1], P2_COLS['name_en_given'][2], P2_COLS['name_en_given'][3]], "style_small", page=2, align="left", json_path=f"page2.owners.{idx}.name_en_given"),
            field(f"p2_owner_{idx}_birth_or_reg_no", f"법인소유자 {idx} 생년월일/사업자번호", [P2_COLS['birth_or_reg_no'][0], y + P2_COLS['birth_or_reg_no'][1], P2_COLS['birth_or_reg_no'][2], P2_COLS['birth_or_reg_no'][3]], "style_small", page=2, align="center", json_path=f"page2.owners.{idx}.birth_or_reg_no"),
            field(f"p2_owner_{idx}_nationality_or_address", f"법인소유자 {idx} 국적/소재지", [P2_COLS['nationality_or_address'][0], y + P2_COLS['nationality_or_address'][1], P2_COLS['nationality_or_address'][2], P2_COLS['nationality_or_address'][3]], "style_small", page=2, align="center", json_path=f"page2.owners.{idx}.nationality_or_address"),
            field(f"p2_owner_{idx}_ownership_type_share_check", f"법인소유자 {idx} 지분 체크", [P2_COLS['ownership_type_share'][0], y + P2_COLS['ownership_type_share'][1], 26, 22], "style_check_small", page=2, align="center", json_path=f"page2.owners.{idx}.ownership_type_share"),
            field(f"p2_owner_{idx}_ownership_percent", f"법인소유자 {idx} 지분율", [P2_COLS['ownership_percent'][0], y + P2_COLS['ownership_percent'][1], P2_COLS['ownership_percent'][2], P2_COLS['ownership_percent'][3]], "style_small", page=2, align="center", json_path=f"page2.owners.{idx}.ownership_percent"),
        ])
    return fields


# Page 3: 사실상 지배자 여부 + 하단 확인/작성자.
def page3_fields() -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = [
        field("p3_controller_absent_check", "사실상 지배자 없음 체크", [235, 540, 24, 24], "style_check_small", page=3, align="center", json_path="page3.controller_absent"),
        field("p3_controller_present_check", "사실상 지배자 있음 체크", [235, 572, 24, 24], "style_check_small", page=3, align="center", json_path="page3.controller_present"),
        field("p3_confirmation_year", "확인 연", [480, 1576, 80, 32], "style_text", page=3, align="center", json_path="page3.confirmation.year"),
        field("p3_confirmation_month", "확인 월", [604, 1576, 50, 32], "style_text", page=3, align="center", json_path="page3.confirmation.month"),
        field("p3_confirmation_day", "확인 일", [707, 1576, 50, 32], "style_text", page=3, align="center", json_path="page3.confirmation.day"),
        field("p3_writer_name", "작성자 성명", [885, 1460, 205, 34], "style_text", page=3, align="left", json_path="page3.writer.name"),
    ]
    return fields


def build_schema(page: int, base_image: Path) -> dict[str, Any]:
    im = Image.open(PAGES[page])
    page_fields = {1: page1_fields, 2: page2_fields, 3: page3_fields}[page]()
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": f"{DOC_TITLE} page {page}",
        "page_index": page,
        "source_image": str(PAGES[page].resolve()),
        "source_inpainted": str(base_image.resolve()),
        "image": {"width": im.width, "height": im.height},
        "fields": page_fields,
        "groups": [
            {"group_id": "beneficial_owner" if page in {1, 2} else "controller_confirmation", "type": "aml_form", "notes": "ID-11 3-page production schema"},
        ],
        "authoring_mode": f"id11_page_{page}_pipeline_ready_20260702",
        "quality_status": "pipeline_ready_candidate",
    }


def build_stylesheet() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "style_classes": [
            style_class("style_text", 22, opacity=0.90),
            style_class("style_en", 18, opacity=0.90),
            style_class("style_small", 13, opacity=0.88),
            style_class("style_check", 20, align="center", opacity=0.94),
            style_class("style_check_small", 14, align="center", opacity=0.94),
        ],
        "notes": f"ID-11 원본의 양식 텍스트는 굵은 산세리프 계열이며 기입값은 일반 국문 산세리프가 가장 자연스러워 {FONT_FAMILY}를 선택했다. crop 비교는 사용하지 않고 전체 문서/overlay 기준으로 보정했다.",
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
            "실소유자 확인서(AML)": {
                "작성인 정보": {
                    "상단": {"기관명": "", "직책": "", "성명": ""},
                    "하단": {"기관명": "", "직책": "", "성명": ""},
                },
                "실소유자 확인": {
                    "판단경로": {
                        "25% 이상 지분 소유자": "",
                        "확인불가-최대 지분 소유자": "",
                        "확인불가-대표자 또는 과반수 선임 주주": "",
                        "확인불가-사실상 지배자": "",
                        "법인 또는 단체의 대표자": "",
                    },
                    "실소유자": [
                        {
                            "성명": {"한글": "", "영문": ""},
                            "생년월일": "",
                            "지분율": "",
                            "국적": "",
                        }
                    ],
                },
                "법인 소유자 및 출연자": [
                    {
                        "구분": {"개인": "", "법인": ""},
                        "성명 또는 상호명": {"국문": "", "영문성": "", "영문명": ""},
                        "생년월일 또는 사업자번호": "",
                        "국적 또는 법인소재지": "",
                        "소유 형태": {"지분": "", "재산": "", "기타": ""},
                        "지분율 또는 영향력 설명": "",
                    }
                ],
                "사실상 지배자": {
                    "존재 여부": {"존재하지 않음": "", "존재함": ""},
                    "지배자 정보": [
                        {
                            "구분": {"개인": "", "법인": ""},
                            "성명 또는 상호명": {"국문": "", "영문성": "", "영문명": ""},
                            "생년월일 또는 사업자번호": "",
                            "국적 또는 법인소재지": "",
                            "지배 형태": {
                                "의결권 과반수 행사": "",
                                "대표자 등 과반수 선임": "",
                                "임원 구성 또는 자금재산 운용 영향": "",
                                "주요 경영사항 영향": "",
                            },
                        }
                    ],
                },
                "확인": {"확인일": {"연": "", "월": "", "일": ""}, "작성자 성명": ""},
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "page_001/page_002/page_003 schema는 렌더러 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 KIE용 key-name 계층만 별도 관리한다.",
            "현재 faker 정책은 page 3 사실상 지배자 없음 케이스를 기본값으로 사용하며, 존재 케이스는 후속 profile 분기로 확장한다.",
        ],
    }


def make_profiles() -> list[dict[str, str]]:
    companies = [
        ("메트로솔루션 주식회사", "대리인", "정지민"),
        ("한빛정밀 주식회사", "대표이사", "김민준"),
        ("대한소재 주식회사", "재무담당이사", "박도윤"),
        ("세종바이오 주식회사", "대표이사", "윤지아"),
        ("아라전자 주식회사", "경영지원본부장", "강도현"),
        ("누리패키징 주식회사", "대표이사", "오서윤"),
    ]
    people = [
        ("이하선", "HAYUN", "LEE", "1981.10.21"),
        ("장재윤", "YUJUN", "JANG", "1984.03.01"),
        ("김민준", "MINJUN", "KIM", "1987.08.08"),
        ("윤지호", "JIHO", "YOON", "1990.01.15"),
        ("박도윤", "DOYUN", "PARK", "1979.07.24"),
        ("최서연", "SEOYEON", "CHOI", "1988.11.17"),
        ("정하준", "HAJUN", "JUNG", "1985.12.30"),
        ("오서윤", "SEOYUN", "OH", "1992.04.02"),
    ]
    orgs = [
        ("새론홀딩스 주식회사", "SAERON", "HOLDINGS", "110-81-47219", "서울"),
        ("미래파트너스 유한회사", "MIRAE", "PARTNERS", "214-86-30951", "경기"),
        ("한빛인베스트먼트", "HANBIT", "INVESTMENT", "105-87-22091", "서울"),
        ("대한소재우리사주조합", "DAEHAN", "ESOP", "301-82-11844", "충남"),
        ("세종바이오벤처스", "SEJONG", "VENTURES", "120-87-49021", "대전"),
    ]
    percents = [80, 10, 5, 5, 0]
    profiles: list[dict[str, str]] = []
    for idx, (company, position, writer) in enumerate(companies):
        record: dict[str, str] = {
            "p1_writer_organization_name_top": company,
            "p1_writer_position_top": position,
            "p1_writer_name_top": writer,
            "p1_owner_path_25_percent_checkbox": CHECK,
            "p1_writer_organization_name_bottom": company,
            "p1_writer_position_bottom": position,
            "p1_writer_name_bottom": writer,
            "p3_controller_absent_check": CHECK,
            "p3_controller_present_check": EMPTY,
            "p3_confirmation_year": "2026",
            "p3_confirmation_month": f"{(idx % 6) + 1:02d}",
            "p3_confirmation_day": f"{(idx * 3 + 7) % 28 + 1:02d}",
            "p3_writer_name": writer,
        }
        rotated = people[idx % len(people):] + people[: idx % len(people)]
        for owner_idx in range(1, 5):
            ko, given, surname, birth = rotated[owner_idx - 1]
            pct = [80, 10, 5, 5][owner_idx - 1]
            record.update({
                f"p1_owner_{owner_idx}_name_ko": ko,
                f"p1_owner_{owner_idx}_name_en": f"{given} {surname}",
                f"p1_owner_{owner_idx}_birth_date": birth,
                f"p1_owner_{owner_idx}_ownership_percent": str(pct),
                f"p1_owner_{owner_idx}_nationality": "대한민국",
            })
        for owner_idx in range(1, 6):
            if owner_idx <= 3:
                org_name, en1, en2, reg_no, loc = orgs[(idx + owner_idx - 1) % len(orgs)]
                pct = [55, 25, 20][owner_idx - 1]
                record.update({
                    f"p2_owner_{owner_idx}_type_person_check": EMPTY,
                    f"p2_owner_{owner_idx}_type_corporation_check": CHECK,
                    f"p2_owner_{owner_idx}_name_ko": org_name,
                    f"p2_owner_{owner_idx}_name_en_surname": en1,
                    f"p2_owner_{owner_idx}_name_en_given": en2,
                    f"p2_owner_{owner_idx}_birth_or_reg_no": reg_no,
                    f"p2_owner_{owner_idx}_nationality_or_address": loc,
                    f"p2_owner_{owner_idx}_ownership_type_share_check": CHECK,
                    f"p2_owner_{owner_idx}_ownership_percent": f"{pct}%",
                })
            else:
                for key in ["type_person_check", "type_corporation_check", "name_ko", "name_en_surname", "name_en_given", "birth_or_reg_no", "nationality_or_address", "ownership_type_share_check", "ownership_percent"]:
                    record[f"p2_owner_{owner_idx}_{key}"] = EMPTY
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
        "constraints": [{"type": "pick_record", "pool": "id11_profiles", "targets": {field_id: field_id for field_id in field_ids}}],
        "data_pools": {"id11_profiles": make_profiles()},
        "notes": "ID-11 record profile. page1 작성인/실소유자, page2 법인소유자, page3 확인 정보가 같은 record에서 일관되게 생성된다.",
    }


def make_contact_sheet(page_sets: list[list[Path]]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 210, 290
    sheet = Image.new("RGB", (len(page_sets) * cell_w + 20, cell_h * 3 + 72), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, paths in enumerate(page_sets):
        x = 20 + idx * cell_w
        draw.text((x, 14), f"id11_{idx + 1:06d}", font=font, fill=(25, 25, 25))
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


def render_batch(schema_paths: dict[int, Path], style_path: Path, faker_path: Path, *, count: int = 5) -> dict[str, Any]:
    if BATCH_DIR.exists():
        shutil.rmtree(BATCH_DIR)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    schema_field_count = sum(len(json.loads(path.read_text(encoding="utf-8")).get("fields", [])) for path in schema_paths.values())
    samples: list[dict[str, Any]] = []
    page_sets: list[list[Path]] = []
    warnings = 0
    for idx in range(1, count + 1):
        sid = f"id11_{idx:06d}"
        seed = 20260702 + idx - 1
        pages_payload: list[dict[str, Any]] = []
        rendered_paths: list[Path] = []
        for page in [1, 2, 3]:
            result = render_authoring_preview(schema_paths[page], style_path, faker_path, out_dir=BATCH_DIR, seed=seed, sample_id=f"{sid}_page_{page:03d}")
            warnings += result.warning_count
            rendered_paths.append(result.image)
            pages_payload.append({"page": page, "image": str(result.image), "kv": str(result.kv), "bbox": str(result.bbox), "overlay": str(result.overlay), "validation_report": str(result.validation_report), "warning_count": result.warning_count})
        page_sets.append(rendered_paths)
        samples.append({"sample_id": sid, "pages": pages_payload})
    contact = make_contact_sheet(page_sets)
    summary = {
        "schema_version": 1,
        "created_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "schemas": {f"page_{page:03d}": str(path) for page, path in schema_paths.items()},
        "stylesheet": str(style_path),
        "faker_profile": str(faker_path),
        "out_dir": str(BATCH_DIR),
        "count": count,
        "page_count": 3,
        "field_count_per_sample": schema_field_count,
        "warning_count": warnings,
        "contact_sheet": str(contact),
        "samples": samples,
    }
    write_json(BATCH_DIR / "summary.json", summary)
    return summary


def compare(page: int, rendered: Path) -> Path:
    out_dir = CALIB_DIR / f"page_{page:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    original = Image.open(PAGES[page]).convert("RGB")
    template = Image.open(template_for_page(page)).convert("RGB").resize(original.size)
    render = Image.open(rendered).convert("RGB").resize(original.size)
    diff = ImageChops.difference(template, render)
    diff_amp = diff.point(lambda value: min(255, value * 4))
    overlay = Image.blend(template, render, 0.5)
    labels = [("original", original), ("template", template), ("render", render), ("amplified diff", diff_amp), ("50% overlay", overlay)]
    font = ImageFont.truetype(str(FONT_FALLBACK), 18) if FONT_FALLBACK.exists() else ImageFont.load_default()
    scale_w = 300
    sheet = Image.new("RGB", (scale_w * len(labels) + 20 * (len(labels) + 1), 480), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(labels):
        thumb = image.copy(); thumb.thumbnail((scale_w, 410))
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
        f"""# 2026-07-02 ID-11 실소유자 확인서(AML) 파이프라인 준비 작업

## 목표
- `ID-11 실소유자 확인서(AML)`을 단일 순차 대상으로 처리한다.
- 기존 page 1 authoring을 3페이지 전체 생산용 schema/faker/style로 확장한다.
- 주주명부 방식과 동일하게 5세트 batch, 전체 문서 비교, 별도 진행 기록을 남긴다.
- crop 비교 루틴은 사용하지 않는다.

## 입력 상태
- page 1 original: `{PAGES[1]}`
- page 1 LaMa template: `{P1_TEMPLATE}`
- page 2 original blank form: `{PAGES[2]}`
- page 3 original blank form: `{PAGES[3]}`
- 기존 authoring은 page 1 중심 27개 필드였으므로 page 2/3 필드를 신규 확장했다.

## 구현 내용
- page 1: 작성인 정보, 25% 이상 지분 소유 체크, 최대 4명의 실소유자 성명/영문명/생년월일/지분율/국적, 하단 작성인 정보를 field화했다.
- page 2: 법인 소유(출연)자 정보 5행 중 3행을 record 기반으로 채우고 나머지는 공란 처리할 수 있도록 field화했다. `(국문)/(영문성)/(영문명)` 인쇄 라벨을 덮지 않도록 값 bbox를 라벨 오른쪽으로 분리했다.
- page 3: 사실상 지배자 없음 체크, 확인일자, 작성자 성명을 field화하고 상세 지배자 표는 현재 record 정책상 공란 보존한다.
- faker profile은 `id11_profiles` record pool을 사용해 3페이지 값이 하나의 synthetic AML record로 일관되게 생성되도록 했다.
- font-family는 원본 양식의 산세리프 시각 정보와 기존 렌더 결과를 기준으로 `{FONT_FAMILY}`를 선택했다.

## 산출물
- page 1 schema: `{PAGE_DIRS[1] / 'schema.json'}`
- page 2 schema: `{PAGE_DIRS[2] / 'schema.json'}`
- page 3 schema: `{PAGE_DIRS[3] / 'schema.json'}`
- stylesheet: `{AUTHORING / 'stylesheet.json'}`
- faker_profile: `{AUTHORING / 'faker_profile.json'}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
- batch summary: `{BATCH_DIR / 'summary.json'}`
- contact sheet: `{BATCH_DIR / 'contact_sheet.jpg'}`
- page 1 comparison: `{comparisons[1]}`
- page 2 comparison: `{comparisons[2]}`
- page 3 comparison: `{comparisons[3]}`

## 검수 결과
- 생성 수: {summary['count']}세트
- page_count: {summary['page_count']}
- field_count_per_sample: {summary['field_count_per_sample']}
- warning_count: {summary['warning_count']}

## 한계 및 다음 조치
- page 3은 현재 `사실상 지배자 없음` 정책을 기본값으로 사용한다. 사실상 지배자 존재 케이스가 필요하면 2-2 표 행과 체크박스 정책을 별도 profile 분기로 확장해야 한다.
- page 2/3는 원본 자체가 blank form이므로 별도 inpainting 없이 원본을 template로 사용한다.
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
    schemas: dict[int, Path] = {}
    for page in [1, 2, 3]:
        schema = build_schema(page, template_for_page(page))
        path = PAGE_DIRS[page] / "schema.json"
        write_json(path, schema)
        schemas[page] = path
    # Keep top-level schema pointing to page 1 for existing UI compatibility.
    write_json(AUTHORING / "schema.json", json.loads(schemas[1].read_text(encoding="utf-8")))
    style_path = AUTHORING / "stylesheet.json"
    faker_path = AUTHORING / "faker_profile.json"
    write_json(style_path, build_stylesheet())
    write_json(faker_path, build_faker_profile([schemas[1], schemas[2], schemas[3]]))
    write_json(SEMANTIC_SCHEMA, build_semantic_schema([schemas[1], schemas[2], schemas[3]]))

    previews: dict[int, Any] = {}
    for page in [1, 2, 3]:
        previews[page] = render_authoring_preview(schemas[page], style_path, faker_path, out_dir=OUT_DIR, seed=20260702, sample_id=f"preview_page_{page:03d}")
    summary = render_batch(schemas, style_path, faker_path, count=5)
    comparisons = {page: compare(page, previews[page].image) for page in [1, 2, 3]}

    update_manifest_artifact(DOC_ID, "authoring", AUTHORING / "schema.json")
    for page in [1, 2, 3]:
        update_manifest_artifact(DOC_ID, f"authoring_page_{page:03d}_schema", schemas[page])
        update_manifest_artifact(DOC_ID, f"authoring_page_{page:03d}_preview", previews[page].image)
        update_manifest_artifact(DOC_ID, f"authoring_page_{page:03d}_style_comparison", comparisons[page])
    update_manifest_artifact(DOC_ID, "authoring_stylesheet", style_path)
    update_manifest_artifact(DOC_ID, "authoring_faker_profile", faker_path)
    update_manifest_artifact(DOC_ID, "authoring_semantic_schema", SEMANTIC_SCHEMA)
    update_manifest_artifact(DOC_ID, "authoring_preview", previews[1].image)
    update_manifest_artifact(DOC_ID, "authoring_overlay", previews[1].overlay)
    update_manifest_artifact(DOC_ID, "authoring_batch", BATCH_DIR / "summary.json")
    update_manifest_artifact(DOC_ID, "authoring_contact_sheet", BATCH_DIR / "contact_sheet.jpg")
    update_manifest_artifact(DOC_ID, "authoring_style_comparison", comparisons[1])

    write_progress(summary, comparisons)
    for page in [1, 2, 3]:
        print(f"preview{page}", previews[page].image, "warnings", previews[page].warning_count)
    print("batch", BATCH_DIR / "summary.json", "warnings", summary["warning_count"])
    print("contact", BATCH_DIR / "contact_sheet.jpg")
    for page in [1, 2, 3]:
        print(f"comparison{page}", comparisons[page])


if __name__ == "__main__":
    main()
