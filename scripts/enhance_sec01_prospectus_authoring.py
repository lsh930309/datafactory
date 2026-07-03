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

DOC_ID = "SEC-01"
DOC_TITLE = "투자설명서·증권신고서"
DOC_DIR = ROOT / "workbench" / "documents" / "투자설명서·증권신고서__SEC-01"
AUTHORING = DOC_DIR / "authoring"
SCHEMA_PATH = AUTHORING / "schema.json"
STYLE_PATH = AUTHORING / "stylesheet.json"
FAKER_PATH = AUTHORING / "faker_profile.json"
OUT_DIR = AUTHORING / "render_preview"
BATCH_DIR = ROOT / "outputs" / "pipeline_ready" / "SEC-01_투자설명서·증권신고서"
CALIB_DIR = ROOT / "outputs" / "style_calibration" / "SEC-01_투자설명서·증권신고서"
SEMANTIC_SCHEMA = AUTHORING / "semantic_schema.json"
PROGRESS = ROOT / "docs/reports/pipeline_ready/20260702_sec01_prospectus_pipeline_readiness.md"
ORIGINAL = DOC_DIR / "samples" / "original" / "투자설명서_page_001.jpg"
TEMPLATE = DOC_DIR / "inpaint" / "original_투자설명서_page_001" / "lama" / "inpainted_lama.png"

FONT_BATANG = ROOT / "fonts" / "batang.ttc"
FONT_GOTHIC_BOLD = ROOT / "fonts" / "malgunbd.ttf"
FONT_APPLE = Path("/System/Library/Fonts/AppleSDGothicNeo.ttc")
FONT = str(FONT_GOTHIC_BOLD if FONT_GOTHIC_BOLD.exists() else (FONT_BATANG if FONT_BATANG.exists() else FONT_APPLE))
FONT_FAMILY = "MalgunGothicBold" if FONT_GOTHIC_BOLD.exists() else ("Batang" if FONT_BATANG.exists() else "AppleSDGothicNeo")
FONT_FALLBACK = ROOT / "fonts" / "malgun.ttf"
NOW = datetime.now(timezone.utc).isoformat()

FUNDS = [
    ("삼성KODEX 코리아배당성장 증권상장지수투자신탁[주식]", "삼성자산운용주식회사", "http://www.samsungfund.com", "2등급(높은위험)", "상장지수투자신탁 수익증권", "10조좌"),
    ("ARIRANG 차이나전기차 증권상장지수투자신탁[주식]", "한화자산운용주식회사", "http://www.hanwhafund.com", "1등급(매우높은위험)", "상장지수집합투자기구 수익증권", "5,000억좌"),
    ("TIGER 미국테크TOP10 INDXX 증권상장지수투자신탁[주식]", "미래에셋자산운용주식회사", "http://www.tigeretf.com", "2등급(높은위험)", "투자신탁 수익증권", "8조좌"),
    ("ACE 단기채권알파 증권투자신탁[채권]", "한국투자신탁운용주식회사", "http://www.kim.co.kr", "5등급(낮은위험)", "투자신탁 수익증권", "2조좌"),
    ("KBSTAR 글로벌리얼티인컴 증권상장지수투자신탁[재간접형]", "케이비자산운용주식회사", "http://www.kbam.co.kr", "3등급(다소높은위험)", "상장지수투자신탁 수익증권", "3조좌"),
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def make_records() -> list[dict[str, str]]:
    # The intro paragraph left in the template names the Samsung KODEX fund, so keep
    # product identity fixed and vary only document dates to avoid internal inconsistency.
    fund, manager, url, grade, sec_type, total = FUNDS[0]
    records: list[dict[str, str]] = []
    for idx in range(12):
        year = 2024 + (idx % 2)
        month = [1, 2, 3, 5, 7, 9][idx % 6]
        day = [3, 10, 17, 21, 25, 28][idx % 6]
        prep = datetime(year, month, day)
        eff = prep + timedelta(days=14)
        records.append(
            {
                "investment_risk_grade_label": "투자 위험 등급",
                "investment_risk_grade": grade,
                "fund_name": fund,
                "asset_manager_name": manager,
                "disclosure_reference_text": f"집합투자업자({url}) 및 금융투자협회(www.kofia.or.kr) 홈페이지 참조",
                "prospectus_preparation_date": f"{prep.year}. {prep.month}. {prep.day}",
                "securities_registration_effective_date": f"{eff.year}. {eff.month}. {eff.day}",
                "offered_security_type": sec_type,
                "offering_total_amount": f"[모집(매출) 총액 : {total}]",
                "offering_period_description": "이 집합투자기구는 별도의 모집(매출)기간이 정해져 있지 않으며, 계속하여 모집할 수 있습니다.",
            }
        )
    return records


def style_size(field_id: str) -> int:
    if field_id in {"investment_risk_grade_label", "investment_risk_grade"}:
        return 16
    if field_id in {"fund_name", "asset_manager_name"}:
        return 19
    if field_id == "disclosure_reference_text":
        return 15
    if field_id in {"prospectus_preparation_date", "securities_registration_effective_date"}:
        return 19
    if field_id == "offered_security_type":
        return 18
    if field_id == "offering_total_amount":
        return 17
    if field_id == "offering_period_description":
        return 18
    return 17


def align_for(field_id: str) -> str:
    if field_id in {"investment_risk_grade_label", "investment_risk_grade", "prospectus_preparation_date", "securities_registration_effective_date"}:
        return "center"
    return "left"


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
            "authoring_mode": "sec01_pipeline_ready_20260702",
            "quality_status": "pipeline_ready_candidate",
        }
    )
    bbox_overrides = {
        "investment_risk_grade_label": [178, 62, 136, 20],
        "investment_risk_grade": [168, 84, 154, 25],
        "fund_name": [414, 432, 520, 28],
        "asset_manager_name": [414, 481, 220, 28],
        "disclosure_reference_text": [413, 537, 650, 47],
        "offering_total_amount": [155, 792, 285, 22],
        "offering_period_description": [468, 835, 560, 70],
    }
    for field in schema.get("fields", []):
        fid = str(field["field_id"])
        field["generator"] = f"pool_record:sec01_prospectus_records.{fid}"
        if fid in bbox_overrides:
            field["bbox"] = bbox_overrides[fid]
        policy = field.setdefault("render_policy", {})
        policy["align"] = align_for(fid)
        policy["valign"] = "middle"
        policy["fit"] = "shrink_to_fit"
        policy["overflow"] = "wrap" if fid == "offering_period_description" else "shrink"
        field["notes"] = "SEC-01 투자설명서 첫 페이지 생산용 보정 필드. 위험등급/펀드명/운용사/일자/증권종류/모집정보를 record 기반으로 일관 생성."
    return schema


def update_stylesheet(stylesheet: dict[str, Any]) -> dict[str, Any]:
    stylesheet = json.loads(json.dumps(stylesheet, ensure_ascii=False))
    stylesheet.update(
        {
            "updated_at": NOW,
            "doc_id": DOC_ID,
            "notes": f"SEC-01 투자설명서 style 보정. 원본 본문은 명조/바탕 계열 PDF 출력체이므로 전체 렌더링 결과를 기준으로 {FONT_FAMILY}을 선택했다. crop 비교는 제외하고 full comparison/50% overlay/contact sheet만 사용했다.",
        }
    )
    for style in stylesheet.get("style_classes", []):
        fid = str(style.get("style_class", "")).removeprefix("style_")
        style["font_family"] = FONT_FAMILY
        style["font_path"] = FONT
        style["font_weight"] = "normal"
        style["font_size"] = style_size(fid)
        style["fill"] = [255, 255, 255] if fid in {"investment_risk_grade_label", "investment_risk_grade"} else [18, 18, 18]
        style["opacity"] = 1.0
        style["align"] = align_for(fid)
        style["valign"] = "middle"
        style["line_spacing"] = 1.05
        style["letter_spacing"] = 0.0
        style["baseline_shift"] = 0
        style["overflow"] = "wrap" if fid == "offering_period_description" else "shrink"
        style["confidence"] = 0.86
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
            "constraints": [{"type": "pick_record", "pool": "sec01_prospectus_records", "targets": {fid: fid for fid in field_ids}}],
            "data_pools": {"sec01_prospectus_records": make_records()},
            "notes": "SEC-01 생산용 profile. 펀드명, 운용사, 위험등급, 작성기준일, 효력발생일, 모집증권 종류와 모집총액을 하나의 record로 생성한다.",
        }
    )
    return faker



def build_semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    field_mapping = {
        field["field_id"]: field.get("export", {}).get("json_path", field["field_id"])
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
            "투자설명서·증권신고서": {
                "투자위험등급": {"표제": "", "등급": ""},
                "집합투자기구": {"명칭": "", "집합투자업자": ""},
                "판매회사 및 공시": {"공시참조 안내": ""},
                "신고 및 모집 정보": {
                    "작성기준일": "",
                    "증권신고서 효력발생일": "",
                    "모집증권 종류": "",
                    "모집총액": "",
                    "모집기간": "",
                },
            }
        },
        "field_mapping": field_mapping,
        "notes": [
            "schema.json은 렌더러 호환을 위해 bbox/style/generator 정보를 유지한다.",
            "semantic_schema.json은 KIE용 key-name 계층만 별도 관리한다.",
            "현재 template에 남아 있는 도입부 펀드명과 일관되도록 product identity는 Samsung KODEX 기준으로 고정한다.",
        ],
    }

def make_contact_sheet(sample_paths: list[Path]) -> Path:
    font = ImageFont.truetype(str(FONT_FALLBACK), 16) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 180, 250
    sheet = Image.new("RGB", (len(sample_paths) * cell_w + 20, cell_h + 58), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(sample_paths):
        x = 20 + idx * cell_w
        draw.text((x, 15), f"sec01_{idx + 1:06d}", font=font, fill=(30, 30, 30))
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
    scale_w = 205
    sheet = Image.new("RGB", (scale_w * len(labels) + 18 * (len(labels) + 1), 360), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, image) in enumerate(labels):
        thumb = image.copy()
        thumb.thumbnail((scale_w, 300))
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
        f"""# 2026-07-02 SEC-01 투자설명서·증권신고서 파이프라인 준비 작업

## 목표
- `SEC-01 투자설명서·증권신고서`를 단일 순차 대상으로 처리한다.
- 현재 workbench authoring 범위인 투자설명서 첫 페이지 10개 필드를 생산 준비화한다.
- crop 비교 루틴은 제외하고 전체 문서 렌더, 50% overlay, contact sheet 기준으로만 style을 보정한다.

## 입력 상태
- original: `{ORIGINAL}`
- LaMa template: `{TEMPLATE}`
- 기존 authoring: 1페이지 10개 필드, preview 동작 가능 상태.

## 구현 내용
- font-family는 본문 명조/바탕 계열 PDF 출력체 시각 정보에 가장 가까운 `{FONT_FAMILY}`로 지정했다.
- 상단 투자위험등급 칸은 배경색 위 흰색 텍스트로 보정했다.
- 기존 독립 faker 규칙을 `sec01_prospectus_records` 단일 record pool로 치환했다.
- template 도입부에 남아 있는 펀드명과 충돌하지 않도록 product identity는 Samsung KODEX 기준으로 고정하고, 작성/효력일은 2024~2025 과거일 범위에서 생성한다.
- 위험등급, 펀드명, 운용사, 공시참조 URL, 작성기준일, 효력발생일, 모집증권 종류/총액/기간이 같은 record에서 생성된다.
- KIE용 key-name 계층은 `semantic_schema.json`으로 분리했다.

## 산출물
- schema: `{SCHEMA_PATH}`
- stylesheet: `{STYLE_PATH}`
- faker_profile: `{FAKER_PATH}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
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

## 한계 및 다음 조치
- 현재는 첫 페이지 표지성 정보만 동적화했다. 투자설명서 전체 본문은 장문 산문/공시 문서 성격이 강하므로 별도 확장 기준이 필요하다.
- 하단 붉은 경고문과 다수 본문 고정 문구는 template 정적 요소를 유지한다.
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
    write_json(SEMANTIC_SCHEMA, build_semantic_schema(schema))

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix="sec01", clean=True)
    contact = make_contact_sheet([sample.image for sample in batch.samples])
    comparison = compare(preview.image)
    summary = read_json(batch.summary)
    summary["page_count"] = 1
    summary["field_count_per_sample"] = summary.get("field_count")
    summary["contact_sheet"] = str(contact)
    summary["style_comparison"] = str(comparison)
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
