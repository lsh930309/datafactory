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

DOC_ID = "COL-05"
DOC_TITLE = "공시지가확인원"
DOC_DIR = ROOT / "workbench" / "documents" / "공시지가확인원__COL-05"
AUTHORING = DOC_DIR / "authoring"
PAGE1_DIR = AUTHORING / "page_001"
PAGE2_DIR = AUTHORING / "page_002"
TEMPLATE_DIR = AUTHORING / "templates"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "COL-05_공시지가확인원"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "COL-05_공시지가확인원"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_col05_public_land_price_pipeline_readiness.md"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
PAGES = {
    1: DOC_DIR / "samples" / "original" / "공시지가확인원_page_001.jpg",
    2: DOC_DIR / "samples" / "original" / "공시지가확인원_page_002.jpg",
}
FONT_MYUNGJO = Path("/System/Library/Fonts/Supplemental/AppleMyungjo.ttf")
FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_MYUNGJO if FONT_MYUNGJO.exists() else (FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK))
FONT_FAMILY = "AppleMyungjo" if FONT_MYUNGJO.exists() else ("AppleSDGothicNeo" if FONT_APPLE.exists() else "default_korean")
NOW = datetime.now(timezone.utc).isoformat()
DARK = [20, 20, 20]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def clear_rect(draw: ImageDraw.ImageDraw, bbox: list[int], *, inset: int = 2, fill: tuple[int, int, int] = (255, 255, 255)) -> None:
    x, y, w, h = bbox
    draw.rectangle([x + inset, y + inset, x + w - inset, y + h - inset], fill=fill)


def field(field_id: str, label: str, bbox: list[int], style_class: str, *, page: int, value_type: str = "free_text.short", align: str = "left", json_path: str | None = None) -> dict[str, Any]:
    return {
        "field_id": field_id,
        "label": label,
        "bbox": bbox,
        "bbox_format": "xywh",
        "source_detection_id": "manual_col05_pipeline_ready_20260702",
        "source_text": "",
        "value_type": value_type,
        "generator": f"pool_record:col05_profiles.{field_id}",
        "style_class": style_class,
        "render_policy": {"align": align, "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        "export": {"json_path": json_path or field_id.replace("_", "."), "csv_column": field_id},
        "required": False,
        "notes": f"COL-05 page {page} filled sample 기반 생산용 수동 bbox/style 보정 필드. crop 비교 미사용.",
    }


def style_class(style_id: str, size: int, *, align: str = "left", opacity: float = 0.92, color: list[int] | None = None) -> dict[str, Any]:
    return {
        "style_class": style_id,
        "font_family": FONT_FAMILY,
        "font_path": FONT,
        "font_size": size,
        "font_weight": "normal",
        "fill": color or DARK,
        "opacity": opacity,
        "align": align,
        "valign": "middle",
        "line_spacing": 1.0,
        "letter_spacing": 0.0,
        "baseline_shift": 0,
        "overflow": "shrink",
        "confidence": 0.74,
        "source_detection_ids": ["manual_col05_pipeline_ready_20260702"],
    }


def make_blank_templates() -> dict[int, Path]:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[int, Path] = {}
    for page, src in PAGES.items():
        image = Image.open(src).convert("RGB")
        draw = ImageDraw.Draw(image)
        clear_rect(draw, [368, 35, 340, 55], inset=0)
        # 접수번호/접수일 값 셀은 원본이 회색 배경이므로 white-fill하면 티가 크게 난다.
        for rect in [[178, 286, 392, 43], [657, 286, 242, 43]]:
            clear_rect(draw, rect, inset=3, fill=(205, 205, 205))
        for rect in [
            [326, 331, 302, 58],
            [790, 331, 320, 58],
            [327, 390, 462, 54],
            [326, 445, 790, 56],
        ]:
            clear_rect(draw, rect, inset=3)
        if page == 1:
            # Land price table data region; preserve grid lines by clearing cell interiors.
            for rect in [[92, 616, 141, 455], [234, 616, 284, 455], [519, 616, 112, 455], [631, 616, 136, 455], [768, 616, 112, 455], [881, 616, 114, 455], [996, 616, 120, 455]]:
                clear_rect(draw, rect, inset=3)
        out_path = TEMPLATE_DIR / f"blank_page_{page:03d}.png"
        image.save(out_path)
        out[page] = out_path
    return out


COMMON_FIELDS = [
    ("document_verification_number", "문서확인번호", [378, 49, 285, 32], "style_top_number", "free_text.short", "left"),
    ("receipt_number", "접수번호", [185, 289, 380, 38], "style_header_value", "free_text.short", "left"),
    ("receipt_date", "접수일", [715, 289, 170, 38], "style_header_value", "date.kr", "center"),
    ("applicant_name", "성명", [330, 336, 285, 48], "style_body_value", "person.name_ko", "center"),
    ("birth_or_business_number", "생년월일", [820, 336, 250, 48], "style_body_value", "free_text.short", "center"),
    ("applicant_address", "주소", [334, 395, 445, 45], "style_body_value", "address.ko", "left"),
    ("purpose", "용도", [334, 449, 750, 46], "style_body_value", "free_text.short", "left"),
]

ROW_YS = [618, 664, 709, 755, 800, 846, 891, 936, 982, 1027]
LAND_FIELDS: list[tuple[str, str, list[int], str, str, str]] = []
for idx, y in enumerate(ROW_YS, start=1):
    LAND_FIELDS.extend([
        (f"land_row_{idx}_year", f"공시지가 기준년도 {idx}", [99, y, 126, 42], "style_table_value", "free_text.short", "center"),
        (f"land_row_{idx}_location", f"토지소재지 {idx}", [242, y, 268, 42], "style_table_value", "address.ko", "center"),
        (f"land_row_{idx}_lot_number", f"지번 {idx}", [523, y, 103, 42], "style_table_value", "free_text.short", "center"),
        (f"land_row_{idx}_price", f"개별공시지가 {idx}", [637, y, 124, 42], "style_table_value", "money.krw", "right"),
        (f"land_row_{idx}_base_date", f"기준일자 {idx}", [773, y, 102, 42], "style_table_value", "free_text.short", "center"),
        (f"land_row_{idx}_announced_date", f"공시일자 {idx}", [886, y, 103, 42], "style_table_value", "date.kr", "center"),
        (f"land_row_{idx}_note", f"비고 {idx}", [1000, y, 108, 42], "style_table_value", "free_text.short", "center"),
    ])


def build_schema(page: int, template: Path) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    for fid, label, bbox, style, vtype, align in COMMON_FIELDS:
        pid = f"p{page}_{fid}"
        fields.append(field(pid, label, bbox, style, page=page, value_type=vtype, align=align, json_path=f"page{page}.header.{fid}"))
    if page == 1:
        for fid, label, bbox, style, vtype, align in LAND_FIELDS:
            fields.append(field(f"p1_{fid}", label, bbox, style, page=page, value_type=vtype, align=align, json_path=f"page1.land_price.{fid}"))
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
        "groups": [{"group_id": "land_price_rows", "type": "table" if page == 1 else "certificate_tail", "notes": "COL-05 filled sample 기반 생산용 schema"}],
        "authoring_mode": f"col05_page_{page}_pipeline_ready_20260702",
        "quality_status": "pipeline_ready_candidate",
    }


def build_stylesheet() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "style_classes": [
            style_class("style_top_number", 23, opacity=0.88),
            style_class("style_header_value", 21, opacity=0.90),
            style_class("style_body_value", 20, opacity=0.90),
            style_class("style_table_value", 18, opacity=0.90),
        ],
        "notes": f"COL-05 원본 기입값은 명조 계열 관공서 출력체에 가까워 {FONT_FAMILY}를 선택했다. 전체 문서/overlay 기준 보정, crop 비교 미사용.",
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
            "공시지가확인원": {
                "문서정보": {
                    "문서확인번호": "",
                    "접수번호": "",
                    "접수일": "",
                    "처리기간": "즉시",
                    "페이지": "",
                },
                "신청인": {
                    "성명": "",
                    "생년월일 또는 사업자등록번호": "",
                    "주소": "",
                    "전화": "",
                },
                "신청정보": {
                    "용도": "",
                },
                "신청대상토지": [
                    {
                        "가격기준년도": "",
                        "토지소재지": "",
                        "지번": "",
                        "개별공시지가": "",
                        "기준일자": "",
                        "공시일자": "",
                        "비고": "",
                    }
                ],
                "확인정보": {
                    "확인문구": "",
                    "발급일": "",
                    "발급기관": "",
                    "수수료": "",
                },
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "page_001/page_002 schema는 렌더러 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 KIE용 key-name 계층만 별도 관리한다.",
            "page 2 확인문구/발급기관/수수료는 현재 템플릿 정적 배경으로 보존되므로 semantic key만 명시한다.",
        ],
    }


def fmt_num(n: int) -> str:
    return f"{n:,}"


def make_profiles() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    applicants = [
        ("이승훈", "1993-03-09", "서울특별시 동대문구 제기로2길 28-12, 단독주택", "서울특별시 서초구 반포동", "0709-0007"),
        ("김민지", "1988-11-17", "서울특별시 강남구 논현로 508, 101동 1203호", "서울특별시 강남구 역삼동", "0832-0145"),
        ("박도윤", "1979-07-24", "경기도 성남시 분당구 판교역로 235", "경기도 성남시 분당구 삼평동", "0621-1020"),
        ("최서연", "1990-02-02", "부산광역시 해운대구 센텀중앙로 79", "부산광역시 해운대구 우동", "1498-0032"),
        ("정하준", "1985-12-30", "대전광역시 유성구 테크노중앙로 50", "대전광역시 유성구 관평동", "0445-0811"),
        ("윤지아", "1997-05-18", "광주광역시 북구 첨단과기로 123", "광주광역시 북구 오룡동", "1203-0456"),
    ]
    profiles: list[dict[str, str]] = []
    for idx, (name, birth, address, land_location, lot) in enumerate(applicants):
        issue_year = 2026
        receipt_date = f"{issue_year}-07-{idx + 1:02d}"
        verify = f"{rng.randint(1000,9999)}-{rng.randint(1000,9999)}-{rng.randint(1000,9999)}-{rng.randint(1000,9999)}"
        receipt = f"{issue_year}-IJ-{11650 + idx:05d}-{412741 + idx * 37:06d}"
        base_price = rng.randint(1_200_000, 8_500_000)
        record: dict[str, str] = {}
        for page in [1, 2]:
            prefix = f"p{page}_"
            record.update({
                f"{prefix}document_verification_number": verify,
                f"{prefix}receipt_number": receipt,
                f"{prefix}receipt_date": receipt_date,
                f"{prefix}applicant_name": name,
                f"{prefix}birth_or_business_number": birth,
                f"{prefix}applicant_address": address,
                f"{prefix}purpose": "금융기관 제출용" if idx % 2 == 0 else "담보평가 제출용",
            })
        for row, year in enumerate(range(2017, 2027), start=1):
            price = int(base_price * (1 + 0.055 * (year - 2017) + rng.uniform(-0.04, 0.08)))
            record.update({
                f"p1_land_row_{row}_year": str(year),
                f"p1_land_row_{row}_location": land_location if row == 1 else "",
                f"p1_land_row_{row}_lot_number": lot,
                f"p1_land_row_{row}_price": fmt_num(price),
                f"p1_land_row_{row}_base_date": "1월 1일 기준",
                f"p1_land_row_{row}_announced_date": f"{year}-05-{31 if year < 2020 else (29 if year == 2020 else 30)}",
                f"p1_land_row_{row}_note": "",
            })
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
        "constraints": [{"type": "pick_record", "pool": "col05_profiles", "targets": {field_id: field_id for field_id in field_ids}}],
        "data_pools": {"col05_profiles": make_profiles()},
        "notes": "COL-05 record profile. page1/page2 header와 page1 공시지가 연도별 행이 같은 record에서 일관되게 생성된다.",
    }


def make_contact_sheet(pairs: list[list[Path]]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 220, 300
    sheet = Image.new("RGB", (len(pairs) * cell_w + 20, cell_h * 2 + 64), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, paths in enumerate(pairs):
        x = 20 + idx * cell_w
        draw.text((x, 14), f"col05_{idx + 1:06d}", font=font, fill=(25, 25, 25))
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
    schema1_fields = len(json.loads(schema1.read_text(encoding="utf-8")).get("fields", []))
    schema2_fields = len(json.loads(schema2.read_text(encoding="utf-8")).get("fields", []))
    samples: list[dict[str, Any]] = []
    pairs: list[list[Path]] = []
    warnings = 0
    for idx in range(1, count + 1):
        sid = f"col05_{idx:06d}"
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
        "field_count_per_sample": schema1_fields + schema2_fields,
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
        f"""# 2026-07-02 COL-05 공시지가확인원 파이프라인 준비 작업

## 목표
- `COL-05 공시지가확인원`을 단일 순차 대상으로 처리한다.
- 샘플만 있는 상태에서 filled sample 기반 blank template, schema, stylesheet, faker_profile, 5세트 batch, 전체 문서 비교를 구성한다.
- crop 비교 루틴은 사용하지 않는다.

## 입력 상태
- page 1 original: `{PAGES[1]}`
- page 2 original: `{PAGES[2]}`
- 기존 OCR/review/inpaint/authoring: 없음

## 구현 내용
- page 1: 문서확인번호, 접수번호, 접수일, 신청인 정보, 용도, 연도별 개별공시지가 10행을 field화했다.
- page 2: 상단 공통 접수/신청인 정보를 field화하고, 하단 확인 문구·관인·바코드는 정적 배경으로 보존했다.
- filled sample의 값 영역만 white-fill로 제거해 문서 전용 blank template을 만들었다.
- faker profile은 `col05_profiles` record pool을 사용해 page1/page2 값과 연도별 지가 행이 같은 record에서 일관되게 생성되도록 했다.
- font-family는 원본 기입값의 명조 계열 관공서 출력체 시각 정보에 근거해 `{FONT_FAMILY}`를 선택했다.

## 산출물
- page 1 schema: `{PAGE1_DIR / 'schema.json'}`
- page 2 schema: `{PAGE2_DIR / 'schema.json'}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
- stylesheet: `{AUTHORING / 'stylesheet.json'}`
- faker_profile: `{AUTHORING / 'faker_profile.json'}`
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
- QR/바코드/관인은 현재 원본 정적 배경을 보존한다. 향후 검증번호와 연동되는 synthetic barcode가 필요하면 별도 생성기가 필요하다.
- 별도 LaMa inpainting 없이 white-fill 템플릿을 사용했으므로, 향후 GUI cleanup으로 더 자연스럽게 정리할 수 있다.
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
    schema1 = build_schema(1, blanks[1])
    schema2 = build_schema(2, blanks[2])
    p1 = PAGE1_DIR / "schema.json"
    p2 = PAGE2_DIR / "schema.json"
    style_path = AUTHORING / "stylesheet.json"
    faker_path = AUTHORING / "faker_profile.json"
    write_json(p1, schema1)
    write_json(p2, schema2)
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
