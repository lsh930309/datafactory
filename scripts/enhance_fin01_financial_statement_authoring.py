#!/usr/bin/env python3
from __future__ import annotations

import json
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

DOC_ID = "FIN-01"
DOC_TITLE = "재무제표(재무상태표·손익계산서)"
DOC_DIR = ROOT / "workbench" / "documents" / "재무제표(재무상태표·손익계산서)__FIN-01"
AUTHORING = DOC_DIR / "authoring"
SCHEMA = AUTHORING / "schema.json"
STYLESHEET = AUTHORING / "stylesheet.json"
FAKER = AUTHORING / "faker_profile.json"
PREVIEW_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "FIN-01_재무제표(재무상태표·손익계산서)"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "FIN-01_재무제표(재무상태표·손익계산서)"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_fin01_financial_statement_pipeline_readiness.md"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
ORIGINAL = DOC_DIR / "samples" / "original" / "표준재무제표증명원＿지엘-1_page_001.jpg"
INPAINTED = DOC_DIR / "inpaint" / "original_표준재무제표증명원＿지엘-1_page_001" / "lama" / "inpainted_lama.png"
FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = "AppleSDGothicNeo" if FONT_APPLE.exists() else "default_korean"
NOW = datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def semantic_schema(fields: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "doc_id": DOC_ID,
        "title": DOC_TITLE,
        "updated_at": NOW,
        "purpose": "KIE label/value 의미 구조 정의. bbox/style/render_policy는 renderer 호환 schema.json 및 stylesheet.json에서 관리한다.",
        "scope": "표준재무제표증명 page 1",
        "schema": {
            "표준재무제표증명": {
                "페이지": "",
                "문서확인": {
                    "발급번호": "",
                    "문서확인번호": "",
                },
                "신청인": {
                    "구분": {
                        "개인": "",
                        "법인": "",
                    },
                    "상호_법인명": "",
                    "사업자등록번호": "",
                    "대표자명": "",
                    "주민_법인등록번호": "",
                    "업태": "",
                    "종목": "",
                    "주소_본점": "",
                },
                "사업연도": {
                    "시작일": "",
                    "종료일": "",
                },
                "첨부서류명": [
                    "표준재무상태표",
                    "표준손익계산서",
                    "부속명세서",
                ],
                "신고": {
                    "구분": "",
                    "일자": "",
                },
                "증명": {
                    "발급일": "",
                    "접수번호": "",
                    "담당부서": "",
                    "담당자": "",
                    "연락처": "",
                    "세무서장": "",
                },
            }
        },
        "field_mapping": {
            field["field_id"]: field.get("export", {}).get("json_path", field["field_id"])
            for field in fields
        },
        "notes": [
            "현재 의미 schema는 page 1 표준재무제표증명 표지/증명 페이지 기준이다.",
            "page 2~4 재무상태표/손익계산서/부속명세는 별도 표 구조 authoring이 필요하다.",
        ],
    }


def normalize_authoring_files() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    schema = read_json(SCHEMA)
    stylesheet = read_json(STYLESHEET)
    faker = read_json(FAKER)

    schema["updated_at"] = NOW
    schema["source_inpainted"] = str(INPAINTED.resolve())
    schema.setdefault("quality_status", "pipeline_ready_candidate")
    schema["quality_status"] = "pipeline_ready_page1_candidate"
    schema["authoring_mode"] = "fin01_page1_pipeline_ready_20260702"

    field_updates = {
        "page_number": {
            "bbox": [81, 170, 135, 27],
            "generator": "literal:(  1  /  4  )",
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "document_confirmation_number": {
            "bbox": [116, 325, 195, 28],
            "generator": "pattern:####-###-####-###",
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "applicant_type_individual_checkbox": {
            "bbox": [457, 332, 35, 35],
            "generator": "literal:☐",
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "applicant_type_corporate_checkbox": {
            "bbox": [617, 332, 36, 35],
            "generator": "literal:☑",
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "company_name": {
            "bbox": [314, 389, 296, 29],
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "business_registration_number": {
            "bbox": [874, 389, 185, 29],
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "representative_name": {
            "bbox": [314, 443, 296, 31],
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "corporate_registration_number_masked": {
            "bbox": [875, 443, 184, 31],
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "business_type": {
            "bbox": [314, 499, 780, 34],
            "render_policy": {"align": "left", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "business_item": {
            "bbox": [314, 568, 780, 30],
            "render_policy": {"align": "left", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "company_address": {
            "bbox": [314, 632, 780, 30],
            "render_policy": {"align": "left", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "fiscal_period_start": {
            "bbox": [385, 691, 165, 27],
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "fiscal_period_end": {
            "bbox": [385, 714, 165, 27],
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "filing_type": {
            "bbox": [388, 781, 150, 31],
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "filing_date": {
            "bbox": [894, 781, 175, 31],
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "certificate_issue_date": {
            "bbox": [704, 1083, 220, 45],
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "receipt_number": {
            "bbox": [248, 1118, 160, 27],
            "render_policy": {"align": "left", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "service_counter": {
            "bbox": [248, 1163, 160, 31],
            "render_policy": {"align": "left", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "tax_office_chief": {
            "bbox": [734, 1184, 195, 42],
            "render_policy": {"align": "center", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
        "tax_office_phone": {
            "bbox": [248, 1263, 160, 31],
            "render_policy": {"align": "left", "valign": "middle", "fit": "shrink_to_fit", "overflow": "shrink"},
        },
    }
    for field in schema.get("fields", []):
        update = field_updates.get(field.get("field_id"))
        if update:
            field.update({key: value for key, value in update.items() if key != "render_policy"})
            field["render_policy"] = update["render_policy"]
            field.setdefault("notes", "")
            field["notes"] = (field["notes"] + " 2차 bbox/schema 보정: 원본 page 1 시각 위치 기준으로 bbox/정렬을 재조정.").strip()

    stylesheet["updated_at"] = NOW
    stylesheet["notes"] = (
        "FIN-01 표준재무제표증명 page 1 생산용 스타일. 기존 수동 authoring 초안을 유지하되 "
        "전체 문서/overlay 기준으로 Apple SD Gothic Neo 계열 렌더링을 명시했다. crop 비교 미사용."
    )
    style_updates = {
        "style_page_number": {"font_size": 19, "opacity": 0.92, "baseline_shift": 0},
        "style_document_confirmation_number": {"font_size": 19, "opacity": 0.94, "baseline_shift": 0},
        "style_applicant_type_individual_checkbox": {"font_size": 28, "opacity": 0.95, "baseline_shift": -1},
        "style_applicant_type_corporate_checkbox": {"font_size": 30, "opacity": 0.95, "baseline_shift": -1},
        "style_company_name": {"font_size": 18, "opacity": 0.94, "baseline_shift": -1},
        "style_business_registration_number": {"font_size": 18, "opacity": 0.94, "baseline_shift": -1},
        "style_representative_name": {"font_size": 22, "opacity": 0.94, "baseline_shift": -1},
        "style_corporate_registration_number_masked": {"font_size": 18, "opacity": 0.94, "baseline_shift": -1},
        "style_business_type": {"font_size": 22, "opacity": 0.94, "baseline_shift": -1},
        "style_business_item": {"font_size": 20, "opacity": 0.94, "baseline_shift": -1},
        "style_company_address": {"font_size": 20, "opacity": 0.94, "baseline_shift": -1},
        "style_fiscal_period_start": {"font_size": 20, "opacity": 0.94, "baseline_shift": -1},
        "style_fiscal_period_end": {"font_size": 20, "opacity": 0.94, "baseline_shift": -1},
        "style_filing_type": {"font_size": 22, "opacity": 0.94, "baseline_shift": -1},
        "style_filing_date": {"font_size": 20, "opacity": 0.94, "baseline_shift": -1},
        "style_certificate_issue_date": {"font_size": 29, "opacity": 0.94, "baseline_shift": -1},
        "style_receipt_number": {"font_size": 17, "opacity": 0.94, "baseline_shift": -1},
        "style_service_counter": {"font_size": 21, "opacity": 0.94, "baseline_shift": -1},
        "style_tax_office_chief": {"font_size": 28, "opacity": 0.94, "baseline_shift": -1},
        "style_tax_office_phone": {"font_size": 18, "opacity": 0.94, "baseline_shift": -1},
    }
    for style in stylesheet.get("style_classes", []):
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style.setdefault("confidence", 0.58)
        if style.get("style_class") in style_updates:
            style.update(style_updates[style["style_class"]])

    faker["updated_at"] = NOW
    generators = faker.setdefault("field_generators", {})
    generators["page_number"] = "literal:(  1  /  4  )"
    generators["document_confirmation_number"] = "pattern:####-###-####-###"
    generators["filing_type"] = "choice:정 기 신 고|수 정 신 고|기 한 후 신 고"
    for record in faker.get("data_pools", {}).get("fin01_accounting_periods", []):
        if isinstance(record, dict):
            for key in ("start", "filing_date"):
                if key in record:
                    record[key] = str(record[key]).replace(".", ". ")
                    record[key] = " ".join(record[key].split())
            if "end" in record:
                end = str(record["end"]).replace(".", ". ")
                record["end"] = "~ " + " ".join(end.replace("~", "").split())
            if "filing_type" in record:
                record["filing_type"] = {
                    "정기 신고": "정 기 신 고",
                    "수정 신고": "수 정 신 고",
                    "기한후 신고": "기 한 후 신 고",
                }.get(str(record["filing_type"]), str(record["filing_type"]))
    faker["notes"] = (
        "FIN-01 page 1 표준재무제표증명 faker profile. 회사/기간/세무서 record pool 제약은 기존 수동 authoring을 유지하고, "
        "page_number는 원본 page 1 템플릿과 일치하도록 고정했다."
    )

    write_json(SCHEMA, schema)
    write_json(STYLESHEET, stylesheet)
    write_json(FAKER, faker)
    write_json(SEMANTIC_SCHEMA, semantic_schema(schema.get("fields", [])))
    return schema, stylesheet, faker


def render_batch(count: int = 5) -> dict[str, Any]:
    if BATCH_DIR.exists():
        shutil.rmtree(BATCH_DIR)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []
    images: list[Path] = []
    warnings = 0
    field_count = 0
    for idx in range(1, count + 1):
        sid = f"fin01_{idx:06d}"
        result = render_authoring_preview(SCHEMA, STYLESHEET, FAKER, out_dir=BATCH_DIR, seed=20260702 + idx - 1, sample_id=sid)
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
        "scope": "page_001_standard_financial_statement_certificate",
        "schema": str(SCHEMA),
        "stylesheet": str(STYLESHEET),
        "faker_profile": str(FAKER),
        "out_dir": str(BATCH_DIR),
        "count": count,
        "page_count": 1,
        "field_count": field_count,
        "warning_count": warnings,
        "contact_sheet": str(contact),
        "samples": samples,
        "limitations": [
            "현재 생산 준비 범위는 표준재무제표증명 page 1이다.",
            "원본 PDF의 page 2~4 재무상태표/손익계산서/부속명세 페이지는 별도 인페인팅과 표 구조 authoring이 필요하다.",
        ],
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
        draw.text((x, 16), f"fin01_{idx + 1:06d}", font=font, fill=(25, 25, 25))
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
    original = Image.open(ORIGINAL).convert("RGB")
    inpainted = Image.open(INPAINTED).convert("RGB").resize(original.size)
    render = Image.open(rendered).convert("RGB").resize(original.size)
    diff = ImageChops.difference(inpainted, render)
    diff_amp = diff.point(lambda value: min(255, value * 4))
    overlay = Image.blend(inpainted, render, 0.5)
    labels = [("original", original), ("inpainted", inpainted), ("render", render), ("amplified diff", diff_amp), ("50% overlay", overlay)]
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
        draw.rectangle([x, 56, x + thumb.width, 56 + thumb.height], outline=(150, 150, 150))
    out = CALIB_DIR / "full_comparison.jpg"
    sheet.save(out, quality=92)
    diff.save(CALIB_DIR / "full_diff.png")
    overlay.save(CALIB_DIR / "full_overlay_50.png")
    return out


def write_progress(summary: dict[str, Any], comparison: Path, preview: Path) -> None:
    PROGRESS.write_text(
        f"""# 2026-07-02 FIN-01 재무제표 파이프라인 준비 작업

## 목표
- `FIN-01 재무제표(재무상태표·손익계산서)`를 ID-03 방식에 맞춰 순차 보강한다.
- 기존 수동 authoring 초안을 표준 `outputs/pipeline_ready` 배치 산출물로 승격한다.
- crop 비교는 사용하지 않고 전체 문서/overlay 기준으로 확인한다.

## 입력 상태
- 원본 page 1: `{ORIGINAL}`
- LaMa inpaint page 1: `{INPAINTED}`
- 기존 authoring: `{AUTHORING}`
- 기존 수동 기록: `docs/manual_authoring/FIN-01_재무제표_표준재무제표증명.md`

## 이번 보강 내용
- stylesheet의 `font_family`를 현재 렌더 가능하고 원본 인상에 가장 가까운 `{FONT_FAMILY}`로 명시했다.
- `page_number`는 page 1 템플릿과 맞도록 원본형 공백을 포함한 literal로 고정했다.
- 문서확인번호는 원본 `5367-578-1853-764` 형식에 맞춰 `####-###-####-###` 패턴으로 조정했다.
- 회사명/대표자/사업자번호/업태/종목/주소/사업연도/신고구분/하단 접수정보 bbox를 원본 셀 경계 기준으로 넓게 재조정했다.
- 상단 회사/사업정보와 하단 세무서장 style size 및 baseline을 조정했다.
- 의미 중심 schema를 `semantic_schema.json`으로 분리했다.
- 기존 회사/기간/세무서 data pool 및 `pick_record` 정합성 제약은 유지했다.
- page 1 기준 5개 샘플 batch, contact sheet, full comparison을 생성했다.

## 산출물
- schema: `{SCHEMA}`
- stylesheet: `{STYLESHEET}`
- faker_profile: `{FAKER}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
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
- 현재 pipeline-ready 판정은 `표준재무제표증명 page 1`에 한정한다.
- 원본 PDF의 page 2~4는 재무상태표/손익계산서/부속명세 테이블이며, 정적 복사 시 회사명/사업자번호/금액 정합성이 깨진다.
- 따라서 FIN-01 전체 4페이지를 완전 생산 준비 상태로 만들려면 page 2~4에 대해 별도 인페인팅, 표 구조 bbox, 금액 합계 faker constraint를 추가해야 한다.
""",
        encoding="utf-8",
    )


def main() -> None:
    for required in [SCHEMA, STYLESHEET, FAKER, ORIGINAL, INPAINTED]:
        if not required.exists():
            raise FileNotFoundError(required)
    normalize_authoring_files()
    preview = render_authoring_preview(SCHEMA, STYLESHEET, FAKER, out_dir=PREVIEW_DIR, seed=20260702, sample_id="preview_000001")
    summary = render_batch(count=5)
    comparison = compare(preview.image)
    update_manifest_artifact(DOC_ID, "authoring", SCHEMA)
    update_manifest_artifact(DOC_ID, "authoring_stylesheet", STYLESHEET)
    update_manifest_artifact(DOC_ID, "authoring_faker_profile", FAKER)
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
