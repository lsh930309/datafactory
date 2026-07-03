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

DOC_ID = "CRD-01"
DOC_TITLE = "신용정보조회서(NICE·KCB)"
DOC_DIR = ROOT / "workbench" / "documents" / "신용정보조회서(NICE·KCB)__CRD-01"
AUTHORING = DOC_DIR / "authoring"
TEMPLATE_DIR = AUTHORING / "templates"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "CRD-01_신용정보조회서(NICE·KCB)"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "CRD-01_신용정보조회서(NICE·KCB)"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_crd01_credit_information_report_pipeline_readiness.md"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
PAGES = {
    1: DOC_DIR / "samples" / "original" / "개인신용정보서_page_001.jpg",
    2: DOC_DIR / "samples" / "original" / "개인신용정보서_page_002.jpg",
}
FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()

# Fields are manually measured on the 734px-wide sample.  The original sample is filled,
# so these rectangles are also used to create a document-local clean template.
COMMON_FIELDS = [
    {"id": "issued_at", "label": "발급일시", "bbox": [75, 104, 150, 18], "style": "style_header", "align": "left"},
    {"id": "issue_number", "label": "발급번호", "bbox": [75, 122, 180, 18], "style": "style_header", "align": "left"},
    {"id": "page_number", "label": "페이지", "bbox": [708, 113, 18, 18], "style": "style_header", "align": "center"},
]
P1_PERSON_FIELDS = [
    {"id": "resident_registration_number", "label": "주민등록번호", "bbox": [180, 187, 120, 20], "style": "style_text", "align": "center"},
    {"id": "person_name", "label": "성명", "bbox": [400, 187, 100, 20], "style": "style_text", "align": "left"},
]
ACCOUNT_ROWS = [
    {"prefix": "account_1", "y": 288},
    {"prefix": "account_2", "y": 313},
]
LOAN_ROWS = [
    {"prefix": f"loan_{idx}", "y": y}
    for idx, y in enumerate([414, 439, 464, 489, 514, 539, 564, 589], start=1)
]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def field(spec: dict[str, Any], *, page: int) -> dict[str, Any]:
    fid = f"p{page}_{spec['id']}"
    return {
        "field_id": fid,
        "label": spec["label"],
        "bbox": spec["bbox"],
        "bbox_format": "xywh",
        "source_detection_id": "manual_crd01_filled_sample_20260702",
        "source_text": "",
        "value_type": "money.krw" if spec["id"].endswith("amount") else "free_text.short",
        "generator": f"pool_record:crd01_profiles.{fid}",
        "style_class": spec["style"],
        "render_policy": {"align": spec.get("align", "left"), "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        "export": {"json_path": fid.replace("_", "."), "csv_column": fid},
        "required": False,
        "notes": "CRD-01 filled sample을 blank template화한 뒤 수동 bbox/style 필드로 재구성",
    }


def account_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for row in ACCOUNT_ROWS:
        p, y = row["prefix"], row["y"]
        specs.extend(
            [
                {"id": f"{p}_category", "label": f"{p} 구분", "bbox": [37, y, 72, 22], "style": "style_small", "align": "center"},
                {"id": f"{p}_reason", "label": f"{p} 내역사유", "bbox": [112, y, 115, 22], "style": "style_small", "align": "center"},
                {"id": f"{p}_institution", "label": f"{p} 기관점포명", "bbox": [232, y, 342, 22], "style": "style_small", "align": "left"},
                {"id": f"{p}_registered_at", "label": f"{p} 등록사유발생일자", "bbox": [587, y, 96, 22], "style": "style_small", "align": "center"},
            ]
        )
    return specs


def loan_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for row in LOAN_ROWS:
        p, y = row["prefix"], row["y"]
        specs.extend(
            [
                {"id": f"{p}_category", "label": f"{p} 구분", "bbox": [35, y, 74, 22], "style": "style_small", "align": "center"},
                {"id": f"{p}_reason", "label": f"{p} 내역사유", "bbox": [112, y, 114, 22], "style": "style_small", "align": "center"},
                {"id": f"{p}_institution", "label": f"{p} 기관점포명", "bbox": [232, y, 263, 22], "style": "style_small", "align": "left"},
                {"id": f"{p}_registered_at", "label": f"{p} 등록사유발생일자", "bbox": [505, y, 112, 22], "style": "style_small", "align": "center"},
                {"id": f"{p}_amount", "label": f"{p} 금액", "bbox": [625, y, 75, 22], "style": "style_amount", "align": "right"},
            ]
        )
    return specs


def clear_rects_for_page(page: int) -> list[list[int]]:
    rects: list[list[int]] = []
    rects.extend([item["bbox"] for item in COMMON_FIELDS])
    if page == 1:
        rects.extend([item["bbox"] for item in P1_PERSON_FIELDS])
        rects.extend([item["bbox"] for item in account_specs()])
        rects.extend([item["bbox"] for item in loan_specs()])
    return rects


def fill_for_bbox(page: int, bbox: list[int]) -> tuple[int, int, int]:
    _x, y, _w, _h = bbox
    # CRD-01 has a blue header band and white table cells.  Using sampled pixels
    # can hit glyphs/table lines and leaves gray patches, so keep deterministic fills.
    if y < 160:
        return (184, 223, 248)
    return (255, 255, 255)


def make_blank_templates() -> dict[int, Path]:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[int, Path] = {}
    for page, src in PAGES.items():
        image = Image.open(src).convert("RGB")
        draw = ImageDraw.Draw(image)
        for bbox in clear_rects_for_page(page):
            x, y, w, h = bbox
            fill = fill_for_bbox(page, bbox)
            if y < 160:
                draw.rectangle([x, y, x + w, y + h], fill=fill)
            else:
                # Keep table grid lines by clearing inside the cell bounds only.
                draw.rectangle([x + 2, y + 2, x + w - 2, y + h - 2], fill=fill)
        if page == 1:
            # The filled sample has dense anti-aliased table text.  Clear whole row bands,
            # then redraw the simple grid so the template is clean enough for production preview.
            grid = (120, 120, 120)
            for box, xs, ys in [
                ([29, 287, 704, 337], [29, 109, 230, 578, 704], [287, 312, 337]),
                ([29, 412, 704, 613], [29, 109, 230, 498, 623, 704], [412, 437, 462, 487, 512, 537, 562, 587, 613]),
            ]:
                draw.rectangle(box, fill=(255, 255, 255))
                for xline in xs:
                    draw.line([(xline, box[1]), (xline, box[3])], fill=grid, width=1)
                for yline in ys:
                    draw.line([(box[0], yline), (box[2], yline)], fill=grid, width=1)
        out_path = TEMPLATE_DIR / f"blank_page_{page:03d}.png"
        image.save(out_path)
        out[page] = out_path
    return out

def style(style_id: str, size: int, *, align: str = "left", opacity: float = 0.90, color: list[int] | None = None) -> dict[str, Any]:
    return {
        "style_class": style_id,
        "font_family": FONT_FAMILY,
        "font_path": FONT,
        "font_size": size,
        "font_weight": "normal",
        "fill": color or [34, 34, 34],
        "opacity": opacity,
        "align": align,
        "valign": "middle",
        "line_spacing": 1.0,
        "letter_spacing": 0.0,
        "baseline_shift": 0,
        "overflow": "shrink",
        "confidence": 0.68,
        "source_detection_ids": ["manual_crd01_filled_sample_20260702"],
    }


def build_schema(page: int, template_path: Path) -> dict[str, Any]:
    specs = list(COMMON_FIELDS)
    if page == 1:
        specs.extend(P1_PERSON_FIELDS)
        specs.extend(account_specs())
        specs.extend(loan_specs())
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": f"{DOC_TITLE} page {page}",
        "page_index": page,
        "source_image": str(PAGES[page].resolve()),
        "source_inpainted": str(template_path.resolve()),
        "image": {"width": Image.open(PAGES[page]).width, "height": Image.open(PAGES[page]).height},
        "fields": [field(item, page=page) for item in specs],
        "groups": [
            {"group_id": "header", "type": "common_header"},
            {"group_id": "credit_rows", "type": "table_rows", "notes": "page1 account/loan rows are record-generated"},
        ],
        "authoring_mode": f"crd01_page_{page}_pipeline_ready_20260702",
        "quality_status": "pipeline_ready_candidate",
    }


def build_stylesheet() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "style_classes": [
            style("style_header", 11, opacity=0.88),
            style("style_text", 12, opacity=0.90),
            style("style_small", 10, opacity=0.90),
            style("style_amount", 10, align="right", opacity=0.90),
        ],
        "notes": "CRD-01 원본 표의 작고 짙은 산세리프 기입값과 가장 유사한 Apple SD Gothic Neo를 선택했다. 전체 문서/overlay 기준이며 crop 비교 미사용.",
    }


def build_semantic_schema(schema_paths: list[Path]) -> dict[str, Any]:
    field_mapping: dict[str, str] = {}
    for path in schema_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        field_mapping.update({field["field_id"]: field["export"]["json_path"] for field in data["fields"]})
    return {
        "schema_version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "purpose": "렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조",
        "semantic_schema": {
            "신용정보조회서": {
                "발급정보": {
                    "발급일시": "",
                    "발급번호": "",
                    "페이지": "",
                },
                "본인정보": {
                    "주민등록번호": "",
                    "성명": "",
                },
                "개설·발급정보": [
                    {
                        "구분": "",
                        "내역·사유": "",
                        "기관점포명": "",
                        "등록사유발생일자": "",
                    }
                ],
                "대출정보": [
                    {
                        "구분": "",
                        "내역·사유": "",
                        "기관점포명": "",
                        "등록사유발생일자": "",
                        "금액": "",
                    }
                ],
                "채무보증정보": {
                    "상태": "해당 내역이 없습니다.",
                },
                "신용도판단정보": {
                    "상태": "해당 내역이 없습니다.",
                },
                "공공정보": {
                    "상태": "해당 내역이 없습니다.",
                },
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "schema.json/page_001/page_002 schema는 렌더러 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 KIE용 key-name 계층만 별도 관리한다.",
            "page 2의 무내역 영역은 현재 템플릿 고정 문구로 보존하며, 동적 필드가 아니라 semantic 상태값으로 표현한다.",
        ],
    }


def amount(value: int) -> str:
    return f"{value:,}"


def date_str(year: int, month: int, day: int) -> str:
    return f"{year:04d}.{month:02d}.{day:02d}"


def make_profiles() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    names = ["이승훈", "김민지", "박도윤", "최서연", "정하준", "윤지아"]
    rrns = ["930309-1069114", "950714-2064821", "880523-1037246", "970201-2081935", "910630-1058327", "990418-2097412"]
    card_issuers = ["신한카드 (통합) [리스크총괄팀]", "삼성카드[심사부]", "국민카드[회원심사팀]", "현대카드[리스크관리팀]", "롯데카드[심사센터]"]
    loan_orgs = [
        "한국장학재단[학자금대출부]",
        "모아상호저축은행[본점]",
        "스마트저축은행[본점]",
        "서울보증보험[중앙지점]",
        "우리은행[여신관리부]",
        "하나캐피탈[개인금융팀]",
        "국민은행[소매여신부]",
        "신한은행[대출관리센터]",
        "농협은행[여신센터]",
        "케이뱅크[신용대출팀]",
    ]
    profiles: list[dict[str, str]] = []
    for idx, name in enumerate(names):
        issued = f"2026-06-{25 + idx:02d} {15 + idx:02d}:{(59 - idx) % 60:02d}"
        issue_no = f"{rng.randint(1000000,9999999)}-{rng.randint(10000,99999)}-{rng.randint(10000,99999)}"
        record: dict[str, str] = {
            "p1_issued_at": issued,
            "p1_issue_number": issue_no,
            "p1_page_number": "1",
            "p2_issued_at": issued,
            "p2_issue_number": issue_no,
            "p2_page_number": "2",
            "p1_resident_registration_number": rrns[idx],
            "p1_person_name": name,
        }
        for row in range(1, 3):
            card = card_issuers[(idx + row) % len(card_issuers)]
            record.update(
                {
                    f"p1_account_{row}_category": "개설발급",
                    f"p1_account_{row}_reason": "신용카드 (0081)",
                    f"p1_account_{row}_institution": card,
                    f"p1_account_{row}_registered_at": date_str(2018 + ((idx + row) % 7), (idx + row * 3) % 12 + 1, (idx * 5 + row * 7) % 27 + 1),
                }
            )
        for row in range(1, 9):
            reason = "학자금 (0031)" if row <= 5 else ("지급보증담보 (0031)" if row == 6 else "신용 (0031)")
            org = loan_orgs[(idx + row) % len(loan_orgs)]
            amt = rng.choice([49, 650, 1170, 1500, 3200, 4840, 8833, 12000, 19967])
            record.update(
                {
                    f"p1_loan_{row}_category": "대출",
                    f"p1_loan_{row}_reason": reason,
                    f"p1_loan_{row}_institution": org,
                    f"p1_loan_{row}_registered_at": date_str(2017 + ((idx + row) % 9), (idx + row * 2) % 12 + 1, (idx * 3 + row * 4) % 27 + 1),
                    f"p1_loan_{row}_amount": amount(amt),
                }
            )
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
        "constraints": [{"type": "pick_record", "pool": "crd01_profiles", "targets": {field_id: field_id for field_id in field_ids}}],
        "data_pools": {"crd01_profiles": make_profiles()},
        "notes": "CRD-01 record profile. page1/page2 header와 page1 개인/개설/대출정보를 하나의 record로 묶어 같은 seed에서 일관되게 렌더링한다.",
    }


def render_pair(schema1: Path, schema2: Path, style_path: Path, faker_path: Path, count: int = 5) -> dict[str, Any]:
    if BATCH_DIR.exists():
        shutil.rmtree(BATCH_DIR)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    pairs: list[list[Path]] = []
    warnings = 0
    field_count = len(json.loads(schema1.read_text(encoding="utf-8"))["fields"]) + len(json.loads(schema2.read_text(encoding="utf-8"))["fields"])
    for idx in range(1, count + 1):
        sid = f"crd01_{idx:06d}"
        seed = 20260702 + idx - 1
        r1 = render_authoring_preview(schema1, style_path, faker_path, out_dir=BATCH_DIR, seed=seed, sample_id=f"{sid}_page_001")
        r2 = render_authoring_preview(schema2, style_path, faker_path, out_dir=BATCH_DIR, seed=seed, sample_id=f"{sid}_page_002")
        warnings += r1.warning_count + r2.warning_count
        pairs.append([r1.image, r2.image])
        samples.append(
            {
                "sample_id": sid,
                "pages": [
                    {"page": 1, "image": str(r1.image), "kv": str(r1.kv), "bbox": str(r1.bbox), "overlay": str(r1.overlay), "validation_report": str(r1.validation_report), "warning_count": r1.warning_count},
                    {"page": 2, "image": str(r2.image), "kv": str(r2.kv), "bbox": str(r2.bbox), "overlay": str(r2.overlay), "validation_report": str(r2.validation_report), "warning_count": r2.warning_count},
                ],
            }
        )
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


def make_contact_sheet(pairs: list[list[Path]]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 220, 300
    sheet = Image.new("RGB", (len(pairs) * cell_w + 20, cell_h * 2 + 64), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, paths in enumerate(pairs):
        x = 20 + idx * cell_w
        draw.text((x, 14), f"crd01_{idx + 1:06d}", font=font, fill=(25, 25, 25))
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
        f"""# 2026-07-02 CRD-01 신용정보조회서 파이프라인 준비 작업

## 목표
- `CRD-01 신용정보조회서(NICE·KCB)`를 단일 순차 대상으로 처리한다.
- OCR/review/inpaint가 없는 filled sample만 있으므로, 문서 전용 blank template을 먼저 만든 뒤 합성값을 렌더링한다.
- 주주명부 방식과 동일하게 schema, stylesheet, faker_profile, preview, batch, full comparison을 남긴다.

## 입력 상태
- page 1 filled sample: `{PAGES[1]}`
- page 2 filled sample: `{PAGES[2]}`
- 기존 OCR/review/inpaint: 없음
- 생성 blank template: `{TEMPLATE_DIR}`

## 구현 내용
- page 1: 발급일시/발급번호/page, 주민등록번호, 성명, 개설·발급정보 2행, 대출정보 8행을 field화했다.
- page 2: 발급일시/발급번호/page만 field화하고, 채무보증/신용도판단/공공정보의 `해당 내역이 없습니다.` 구조는 보존했다.
- faker profile은 `crd01_profiles` record pool을 사용해 page1/page2 header와 개인/개설/대출정보가 같은 record에서 나오도록 했다.
- font-family는 원본 표의 작고 짙은 산세리프 인상에 가장 가까운 `{FONT_FAMILY}`로 선택했다.
- crop 비교는 사용하지 않고 전체 문서/blank/render/overlay 비교만 생성했다.

## 산출물
- page 1 schema: `{AUTHORING / 'page_001' / 'schema.json'}`
- page 2 schema: `{AUTHORING / 'page_002' / 'schema.json'}`
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
- 현재 blank template은 원본 filled sample의 값 영역을 문서 전용 좌표로 지운 것이다. 이후 실제 GUI cleanup/inpaint 단계로 더 깨끗한 템플릿을 만들 수 있다.
- 대출정보는 8행 고정 구조로 우선 구현했다. 실제 기관별 행 수가 달라지는 변형은 별도 row policy가 필요하다.
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
    p1 = AUTHORING / "page_001" / "schema.json"
    p2 = AUTHORING / "page_002" / "schema.json"
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
