from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import date, datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter, sleep
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from PIL import Image, ImageChops, ImageDraw

from .authoring import (
    approve_authoring_draft_to_library,
    authoring_library_payload,
    authoring_review_prune_candidates,
    draft_authoring_bundle,
    draft_stylesheet_from_review,
    load_authoring_bundle,
    migrate_authoring_schema_bboxes_to_review,
    prune_authoring_fields_by_review,
    render_authoring_batch,
    render_authoring_live_preview,
    render_authoring_preview,
    review_anchor_map,
    save_authoring_bundle,
    semantic_schema_to_authoring_schema,
    update_authoring_source_inpainted,
)
from .first_priority_assessment import export_first_priority_assessment_xlsx, list_first_priority_assessments, save_assessment_entry
from .fonts import default_font_id, list_font_faces
from .final_results_export import export_final_results
from .handwriting import QR_FORMAT, DEFAULT_WECHAT_QR_MODEL_DIR, create_handwriting_print_pack, intake_handwriting_scans, render_handwriting_authoring_preview
from .docx_pipeline import analyze_docx_template, draft_docx_authoring, generate_docx_outputs
from .inpaint import InpaintConfig, InpaintResult, inpaint_from_review_policy, lama_inpaint, render_mask_overlay
from .inpaint_export import write_inpaint_result
from .manual_cleanup import load_manual_mask, save_manual_mask
from .ocr_detectors import PADDLEOCR_PRESETS, normalize_paddleocr_preset
from .ocr_worker import run_ocr_eval
from .policy import ReviewPolicy, augment_blank_template_policy, draft_review_policy, load_review_policy, review_summary, write_review_policy
from .registry import load_registry
from .style_remap import remap_styles_from_previous
from .workbench import (
    delete_target_group,
    document_dir,
    import_seed_batch,
    import_seed_folder,
    list_work_items,
    list_target_groups,
    preview_seed_revert,
    save_seed_mapping,
    save_target_group,
    save_uploaded_seed_files,
    scan_seed_samples,
    set_manifest_sample_kind,
    trash_seed_folder,
    revert_seed_import,
    update_manifest_artifact,
    workbench_subdir,
)

ROOT = Path(__file__).resolve().parents[2]
RENDER_OUTPUT_ROOT = ROOT / "outputs" / "render"
AUTHORING_AGENT_REQUIRED_OUTPUTS = [
    "schema_draft.json",
    "stylesheet_draft.json",
    "faker_profile_draft.json",
    "value_pool_draft.json",
    "research_report.json",
    "uncertainty_report.json",
    "anchor_map_draft.json",
    "application_notes.md",
]
AUTHORING_AGENT_JSON_OUTPUTS = {name for name in AUTHORING_AGENT_REQUIRED_OUTPUTS if name.endswith(".json")}
DEFAULT_AUTHORING_AGENT_SCALAR_POOL_MIN_SIZE = 20
DEFAULT_AUTHORING_AGENT_RECORD_POOL_MIN_SIZE = 12
AUTHORING_AGENT_REASONING_EFFORTS = {"low", "medium", "high"}
AUTHORING_AGENT_SUPPORTED_FAKER_RULES = [
    "literal:<고정 더미 문자열>",
    "choice:<값1>|<값2>|<값3>",
    "pool:<data_pools 이름>",
    "same_as:<다른 field_id>",
    "pattern:<# 숫자, A 대문자, a 소문자, * 영문대문자/숫자 패턴>",
    "template:<문자열과 {{지원 rule}} 조합>",
    "person.name_ko",
    "person.phone_kr",
    "person.rrn",
    "date.kr",
    "date.year",
    "date.month",
    "date.day",
    "money.krw",
    "business_reg_no",
    "company.name_ko",
    "medical.institution_ko",
    "address.ko",
    "free_text.short",
    "checkbox.bool",
]
AUTHORING_AGENT_SUPPORTED_CONSTRAINT_RULES = [
    "`pick_record`은 field 간 값 짝을 같은 레코드에서 뽑아야 할 때만 사용한다. 형식은 반드시 `{type:'pick_record', pool:'record_pool_name', targets:{field_id:'record_key', other_field_id:'other_record_key'}}`이다.",
    "`pick_record`의 `targets`는 반드시 `schema_draft.fields[].field_id -> data_pools.<pool>[] 객체의 key` 방향이다. `{record_key: field_id}` 방향으로 쓰지 않는다.",
    "`pick_record`의 레코드 목록은 constraint 내부 `records`에 넣지 않는다. 반드시 `faker_profile_draft.json.data_pools.<pool>`에 object 배열로 둔다. 예: `data_pools.diagnosis_records=[{name:'급성 기관지염', code:'J20.9'}]`.",
    "`pick_record`로 연결되는 field라도 `field_generators`에는 렌더러가 지원하는 안전한 기본 rule을 둔다. 다만 최종 값은 constraint가 같은 record에서 덮어쓴다.",
    "`copy`는 `{type:'copy', source:'source_field_id', target:'target_field_id'}`로 작성한다. source/target은 모두 schema binding field_id여야 한다.",
    "`exclusive_choice`는 `{type:'exclusive_choice', targets:[field_id...]}`로 작성하며 동일 그룹 체크박스 중 정확히 하나만 선택되어야 할 때 사용한다.",
    "`primary_secondary_group`은 수술 행별 주수술/부수술 체크박스에만 사용한다. 형식은 `{type:'primary_secondary_group', rows:[{primary:'수술1_주수술', secondary:'수술1_부수술'}, ...]}`이며 정확히 한 행만 주수술=true, 나머지는 부수술=true가 된다.",
    "`date_group`은 `{type:'date_group', year:'field_id', month:'field_id', day:'field_id', min_year:2020, max_year:2027}`로 작성해 분리된 연/월/일 bbox가 항상 유효한 한 날짜가 되게 한다. 템플릿에 `20` 같은 세기 prefix가 이미 인쇄되어 연도 bbox가 뒤 2자리만 받는 경우에만 `year_format:'yy'`를 추가한다.",
    "`date_order`는 `{type:'date_order', start:{year,month,day}, end:{year,month,day}, min_days:0, max_days:60}` 또는 start/end가 각각 단일 `date.kr` field_id인 형태로 작성해 종료일이 시작일보다 빠르지 않게 한다.",
    "`date_not_before`는 `{type:'date_not_before', source:'source_date_field_id', target:{year:'field_id', month:'field_id', day:'field_id'}, min_days:0, max_days:90}`로 작성해 target 날짜가 source 날짜보다 과거가 되지 않게 한다. source/target은 단일 date.kr field 또는 year/month/day group을 사용할 수 있다.",
    "`date_not_after`는 `{type:'date_not_after', target:'date_field_id', max:'as_of_date'}`로 작성해 target 날짜가 작업일보다 미래가 되지 않게 한다. target은 단일 date.kr field 또는 year/month/day group을 사용할 수 있고, max는 `as_of_date` 또는 다른 날짜 field/group이다.",
    "`sum`은 `{type:'sum', sources:[field_id...], target:'field_id', format:'money.krw'}`로 작성해 합계/소계/총액 bbox가 구성 항목의 합과 일치하게 한다.",
    "`numeric_range`는 `{type:'numeric_range', target:'field_id', min:0, max:20, decimals:2, suffix:'%'}`로 작성해 금리, 비율, 수량, 금액 등의 현실 범위를 제한한다.",
    "`numeric_compare`는 `{type:'numeric_compare', left:'equity_field_id', operator:'<=', right:'assets_field_id'}`로 작성해 두 숫자 field 사이의 대소 관계를 보장한다. operator는 `<`, `<=`, `>`, `>=`만 허용한다.",
    "`age_from_rrn`은 `{type:'age_from_rrn', rrn:'rrn_field_id', age:'age_field_id', issue:{year:'field_id', month:'field_id', day:'field_id'}}`로 작성해 발급일 기준 만 나이를 주민등록번호와 일치시킨다.",
    "지원하지 않는 관계, 단일 문자열 내부의 복잡한 날짜 순서, 조건부 선택/복합 수식은 자연어 constraint로 쓰지 말고 uncertainty_report에 보류 사유와 필요한 bbox/schema 조정을 기록한다.",
]


def runtime_health() -> dict[str, Any]:
    try:
        import cv2  # type: ignore

        opencv = {"available": True, "version": str(getattr(cv2, "__version__", "unknown"))}
    except Exception as exc:
        opencv = {"available": False, "error": str(exc)}
    try:
        import simple_lama_inpainting  # type: ignore
        import torch  # type: ignore

        lama = {
            "available": True,
            "package": "simple-lama-inpainting",
            "torch_version": str(getattr(torch, "__version__", "unknown")),
            "device": "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu"),
            "model_env": bool(__import__("os").environ.get("LAMA_MODEL")),
        }
    except Exception as exc:
        lama = {"available": False, "error": str(exc)}
    try:
        import pypdfium2 as pdfium  # type: ignore

        pdf_render = {"available": True, "package": "pypdfium2", "version": str(getattr(pdfium, "__version__", "unknown"))}
    except Exception as exc:
        pdf_render = {"available": False, "error": str(exc)}
    return {
        "ok": True,
        "python": sys.executable,
        "python_version": sys.version.split()[0],
        "opencv": opencv,
        "lama": lama,
        "pdfRender": pdf_render,
        "root": str(ROOT),
        "features": {
            "lama_resize": True,
            "seed_images": True,
            "ocr_detect_endpoint": True,
            "staged_gui": True,
            "registry": True,
            "seed_scan": True,
            "seed_import": True,
            "seed_import_batch": True,
            "seed_mapping": True,
            "seed_upload": True,
            "seed_trash": True,
            "pdf_render": pdf_render["available"],
            "work_items": True,
            "workbench": True,
            "authoring_1cycle": True,
            "editable_office_template": True,
            "docx_renderer_backend": "libreoffice-cli-experimental",
            "ocr_recrop_review": True,
            "first_priority_assessment": True,
            "final_results_export": True,
            "handwriting_pipeline": True,
            "handwriting_marker": QR_FORMAT,
            "handwriting_barcode": QR_FORMAT,
            "wechat_qr_model_dir": str(DEFAULT_WECHAT_QR_MODEL_DIR),
            "wechat_qr_models_present": all((DEFAULT_WECHAT_QR_MODEL_DIR / name).exists() for name in ("detect.prototxt", "detect.caffemodel", "sr.prototxt", "sr.caffemodel")),
            "manual_template_cleanup": True,
            "font_registry": True,
            "ocr_presets": list(PADDLEOCR_PRESETS),
            "inpaint_methods": ["fill", "telea", "ns", "lama"],
        },
    }


def list_assets(root: Path = ROOT) -> dict[str, list[str]]:
    images = sorted(
        path
        for ext in ("*.jpg", "*.jpeg", "*.png")
        for path in (root / "seed_samples").rglob(ext)
        if path.is_file() and not path.name.startswith(".")
    )
    detections = sorted(root.glob("outputs/ocr_eval/paddleocr/*/detections.json"))
    detections += sorted(path for path in root.glob("outputs/ocr_eval/*/*/detections.json") if "/paddleocr/" not in str(path))
    reviews = sorted(root.glob("outputs/reviews/*/review.json"))
    return {
        "images": [_display_path(path, root) for path in images],
        "detections": [_display_path(path, root) for path in detections],
        "reviews": [_display_path(path, root) for path in reviews],
    }


def policy_to_client(policy: ReviewPolicy, *, review_path: Path | None = None) -> dict[str, Any]:
    data = policy.to_dict()
    image_path = _resolve_workspace_path(policy.source_image)
    data["review_path"] = _display_path(review_path, ROOT) if review_path is not None else None
    data["image_url"] = f"/api/image?path={_display_path(image_path, ROOT)}"
    data["summary"] = review_summary(policy.labels)
    return data


def save_policy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw_policy = payload.get("policy")
    if not isinstance(raw_policy, dict):
        raise ValueError("payload.policy must be an object")
    policy = ReviewPolicy.from_dict(raw_policy, base_dir=ROOT)
    doc_id = str(payload.get("docId") or "")
    default_review_path = "outputs/reviews/review/review.json"
    if doc_id:
        default_review_path = str(workbench_subdir(doc_id, "review") / _safe_template_id(policy.source_image) / "review.json")
    review_path = _resolve_workspace_path(str(payload.get("reviewPath") or raw_policy.get("review_path") or default_review_path))
    paths = write_review_policy(policy, review_path.parent)
    pruned_authoring: dict[str, Any] | None = None
    sidecar_drafts: dict[str, Any] | None = None
    if doc_id:
        update_manifest_artifact(doc_id, "review", paths["review"])
        sidecar_drafts = _write_review_sidecar_drafts(doc_id, paths["review"], policy)
        if bool(payload.get("pruneAuthoring")):
            schema_path, stylesheet_path, faker_profile_path = _authoring_paths_from_payload(payload, doc_id)
            if schema_path.exists() and stylesheet_path.exists() and faker_profile_path.exists():
                pruned_authoring = prune_authoring_fields_by_review(
                    schema_path,
                    stylesheet_path,
                    faker_profile_path,
                    policy=policy,
                )
                update_manifest_artifact(doc_id, "authoring", schema_path)
                update_manifest_artifact(doc_id, "authoring_stylesheet", stylesheet_path)
                update_manifest_artifact(doc_id, "authoring_faker_profile", faker_profile_path)
    return {"paths": _paths_to_client(paths), "policy": policy_to_client(policy, review_path=paths["review"]), "prunedAuthoring": pruned_authoring, "authoringSidecarDrafts": sidecar_drafts}


def registry_payload() -> dict[str, Any]:
    registry = load_registry()
    payload = registry.to_dict()
    payload["targetGroups"] = list_target_groups(registry=registry)["groups"]
    return payload


def scan_review_legacy_issues() -> dict[str, Any]:
    registry = load_registry()
    items = []
    total_ignore = 0
    for doc in registry.documents.values():
        doc_root = document_dir(doc)
        if not doc_root.exists():
            continue
        review_paths = sorted(path for path in doc_root.glob("review/**/review.json") if "/backups/" not in str(path))
        for review_path in review_paths:
            policy = load_review_policy(review_path)
            ignore_labels = [label for label in policy.labels if label.status == "ignore"]
            if not ignore_labels:
                continue
            total_ignore += len(ignore_labels)
            items.append(
                {
                    "docId": doc.doc_id,
                    "title": doc.title,
                    "reviewPath": _display_path(review_path, ROOT),
                    "ignoreCount": len(ignore_labels),
                    "labelIds": [label.id for label in ignore_labels],
                }
            )
    return {"summary": {"documentCount": len(items), "ignoreCount": total_ignore}, "items": items}


def remove_ignore_bboxes_payload(payload: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(payload.get("docId") or "")
    if not doc_id:
        raise ValueError("docId is required")
    review_path = _resolve_workspace_path(str(payload.get("reviewPath") or ""))
    policy = load_review_policy(review_path)
    removed = [label for label in policy.labels if label.status == "ignore"]
    if not removed:
        return {"docId": doc_id, "removed": 0, "backup": None, "paths": {"review": _display_path(review_path, ROOT)}}
    backup = backup_review_draft_outputs(review_path.parent)
    cleaned = ReviewPolicy(
        source_detections=policy.source_detections,
        source_image=policy.source_image,
        image_width=policy.image_width,
        image_height=policy.image_height,
        labels=[label for label in policy.labels if label.status != "ignore"],
        source_engine=policy.source_engine,
        schema_version=policy.schema_version,
        created_at=policy.created_at,
    )
    paths = write_review_policy(cleaned, review_path.parent)
    update_manifest_artifact(doc_id, "review", paths["review"])
    return {
        "docId": doc_id,
        "removed": len(removed),
        "removedLabelIds": [label.id for label in removed],
        "backup": backup,
        "paths": _paths_to_client(paths),
        "policy": policy_to_client(cleaned, review_path=paths["review"]),
    }


def scan_manual_cleanup_legacy() -> dict[str, Any]:
    registry = load_registry()
    items = []
    for item in list_work_items(registry=registry):
        doc = registry.documents.get(str(item.get("docId") or ""))
        if doc is None:
            continue
        doc_root = document_dir(doc)
        for cleanup_dir in sorted(doc_root.glob("inpaint/**/manual_cleanup")):
            if not cleanup_dir.is_dir():
                continue
            promoted_candidate = cleanup_dir / "painted_template.png"
            legacy_candidate = cleanup_dir / "inpainted_lama.png"
            comparison_candidate = cleanup_dir / "comparison_paint.png"
            if not comparison_candidate.exists():
                comparison_candidate = cleanup_dir / "comparison_lama.png"
            items.append(
                {
                    "docId": item["docId"],
                    "title": item["title"],
                    "cleanupDir": _display_path(cleanup_dir, ROOT),
                    "templateId": cleanup_dir.parent.name,
                    "hasPaintResult": promoted_candidate.exists(),
                    "hasLegacyInpaintResult": legacy_candidate.exists(),
                    "promoteSource": _display_path(promoted_candidate if promoted_candidate.exists() else legacy_candidate, ROOT) if (promoted_candidate.exists() or legacy_candidate.exists()) else "",
                    "comparisonSource": _display_path(comparison_candidate, ROOT) if comparison_candidate.exists() else "",
                    "currentInpainted": str(item.get("latestInpainted") or ""),
                }
            )
    return {"summary": {"legacyCleanupCount": len(items)}, "items": items}


def promote_manual_cleanup_payload(payload: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(payload.get("docId") or "")
    cleanup_dir = _resolve_workspace_path(str(payload.get("cleanupDir") or ""))
    if not doc_id:
        raise ValueError("docId is required")
    if cleanup_dir.name != "manual_cleanup" or ROOT not in cleanup_dir.resolve().parents:
        raise ValueError("cleanupDir must be a manual_cleanup directory inside the workspace")
    if not cleanup_dir.exists() or not cleanup_dir.is_dir():
        raise FileNotFoundError(cleanup_dir)
    source_image = cleanup_dir / "painted_template.png"
    if not source_image.exists():
        source_image = cleanup_dir / "inpainted_lama.png"
    if not source_image.exists():
        raise FileNotFoundError("manual_cleanup has no promoted inpaint result")
    comparison = cleanup_dir / "comparison_paint.png"
    if not comparison.exists():
        comparison = cleanup_dir / "comparison_lama.png"

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = ROOT / "workbench" / ".trash" / "manual_cleanup_promote" / f"{timestamp}_{_safe_name(doc_id)}_{_safe_name(cleanup_dir.parent.name)}"
    backup_root.mkdir(parents=True, exist_ok=True)
    target_dir = cleanup_dir.parent / "lama"
    target_dir.mkdir(parents=True, exist_ok=True)
    for existing_name in ("inpainted_lama.png", "comparison_lama.png", "summary.json"):
        existing = target_dir / existing_name
        if existing.exists():
            backup_existing_dir = backup_root / "previous_lama"
            backup_existing_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(existing, backup_existing_dir / existing.name)
    promoted_inpainted = target_dir / "inpainted_lama.png"
    promoted_comparison = target_dir / "comparison_lama.png"
    shutil.copy2(source_image, promoted_inpainted)
    if comparison.exists():
        shutil.copy2(comparison, promoted_comparison)
    summary_path = target_dir / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "strategy": "promoted_manual_cleanup_result",
                "source_cleanup_dir": _display_path(cleanup_dir, ROOT),
                "source_image": _display_path(source_image, ROOT),
                "outputs": {
                    "inpainted": _display_path(promoted_inpainted, ROOT),
                    "comparison": _display_path(promoted_comparison, ROOT) if promoted_comparison.exists() else "",
                },
                "backup": _display_path(backup_root, ROOT),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    removed_dir = backup_root / "manual_cleanup"
    shutil.move(str(cleanup_dir), str(removed_dir))
    update_manifest_artifact(doc_id, "inpaint", promoted_comparison if promoted_comparison.exists() else promoted_inpainted)
    _clear_manifest_artifacts(doc_id, ["inpaint_cleanup", "inpaint_cleanup_inpainted", "inpaint_cleanup_mask"])
    return {
        "docId": doc_id,
        "promoted": {
            "inpainted": _display_path(promoted_inpainted, ROOT),
            "comparison": _display_path(promoted_comparison, ROOT) if promoted_comparison.exists() else "",
            "summary": _display_path(summary_path, ROOT),
        },
        "backup": _display_path(backup_root, ROOT),
        "removedManualCleanup": _display_path(removed_dir, ROOT),
    }


def _authoring_agent_prompt_markdown(request: dict[str, Any]) -> str:
    contract = request["contract"]
    registry = request["inputs"].get("registry") or {}
    lines = [
        f"# Agentic Authoring Request: {request['title']} ({request['docId']})",
        "",
        "## 목표",
        "문서 이미지/OCR/BBox review와 실제 문서 리서치 근거를 사용해 authoring 초안을 A-to-Z로 생성한다.",
        "산출물은 즉시 적용하지 않는 draft이며, UI에서 사용자 승인/수정/백업 후 확정한다.",
        "",
        "## 사용자 지시",
        request.get("instruction") or "(추가 지시 없음)",
        "",
        "## 입력 문서 컨텍스트",
        f"- 제목: {request['title']}",
        f"- 문서 ID: {request['docId']}",
        f"- PO 도메인: {', '.join(registry.get('poDomains') or registry.get('domains') or []) or '-'}",
        f"- 업무 도메인: {', '.join(registry.get('workflowDomains') or []) or '-'}",
        "",
        "## 필수 산출물",
        *[f"- `{name}`" for name in contract["outputs"]],
        "",
        "## 웹 리서치 필수 규칙",
        *[f"- {rule}" for rule in contract["web_research_rules"]],
        "",
        "## Schema 규칙",
        *[f"- {rule}" for rule in contract["schema_rules"]],
        "",
        "## 시각 근거 우선 규칙",
        *[f"- {rule}" for rule in contract["visual_source_of_truth_rules"]],
        "",
        "## Faker profile 규칙",
        *[f"- {rule}" for rule in contract["faker_profile_rules"]],
        "",
        "## 지원 Faker relationship constraint 문법",
        *[f"- {rule}" for rule in contract.get("constraint_rules", [])],
        "",
        "## 지원 Faker rule 문법",
        "faker_profile_draft.json.field_generators 값은 아래 형식만 사용한다.",
        *[f"- `{rule}`" for rule in AUTHORING_AGENT_SUPPORTED_FAKER_RULES],
        "",
        "금지 예시: `date_between:-365d:+0d|format:%Y/%m/%d`, `time|format:%H:%M:%S`, `decimal_range:10..99`, `identifier.document_confirmation`, `area.square_meter`, `land_use.zoning`, `building.structure`, `text.short`, `count_triplet`, `lot_number`, `page_count_label`.",
        "",
        "## DOCX/빈 템플릿 anchor 규칙",
        *[f"- {rule}" for rule in contract["template_anchor_rules"]],
        "",
        "## 적용/검수 정책",
        *[f"- {rule}" for rule in contract["application_rules"]],
        "",
        "## 입력 파일",
        f"- sample: {request['inputs'].get('sample') or '-'}",
        f"- latestReview: {request['inputs'].get('latestReview') or '-'}",
        f"- latestInpainted: {request['inputs'].get('latestInpainted') or '-'}",
        f"- visualEvidenceManifest: {(request.get('generated_sidecars') or {}).get('visualEvidenceManifest') or '-'}",
        "",
    ]
    return "\n".join(lines) + "\n"


def _authoring_agent_options(payload: dict[str, Any]) -> dict[str, Any]:
    raw_options = payload.get("options") if isinstance(payload.get("options"), dict) else payload
    reasoning = str(raw_options.get("reasoningEffort") or raw_options.get("reasoning") or "medium").strip().lower()
    if reasoning not in AUTHORING_AGENT_REASONING_EFFORTS:
        reasoning = "medium"
    fast_mode = bool(raw_options.get("fastMode", False))
    try:
        scalar_pool_min_size = int(raw_options.get("scalarPoolMinSize") or raw_options.get("minPoolSize") or raw_options.get("fakerMinPoolSize") or DEFAULT_AUTHORING_AGENT_SCALAR_POOL_MIN_SIZE)
    except (TypeError, ValueError):
        scalar_pool_min_size = DEFAULT_AUTHORING_AGENT_SCALAR_POOL_MIN_SIZE
    try:
        record_pool_min_size = int(raw_options.get("recordPoolMinSize") or DEFAULT_AUTHORING_AGENT_RECORD_POOL_MIN_SIZE)
    except (TypeError, ValueError):
        record_pool_min_size = DEFAULT_AUTHORING_AGENT_RECORD_POOL_MIN_SIZE
    scalar_pool_min_size = max(1, min(100, scalar_pool_min_size))
    record_pool_min_size = max(1, min(100, record_pool_min_size))
    mode = str(raw_options.get("mode") or "authoring").strip().lower()
    if mode not in {"authoring", "bbox_correction"}:
        mode = "authoring"
    as_of_date = _parse_as_of_date(raw_options.get("asOfDate"))
    return {
        "reasoningEffort": reasoning,
        "fastMode": fast_mode,
        "minPoolSize": scalar_pool_min_size,
        "scalarPoolMinSize": scalar_pool_min_size,
        "recordPoolMinSize": record_pool_min_size,
        "asOfDate": as_of_date.isoformat(),
        "mode": mode,
    }


def _parse_as_of_date(value: Any) -> date:
    raw = str(value or "").strip()
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("asOfDate must use YYYY-MM-DD format") from exc


def authoring_agent_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    options = _authoring_agent_options(payload)
    doc_id = str(payload.get("docId") or "")
    if not doc_id:
        raise ValueError("docId is required")
    registry = load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    item = next((candidate for candidate in list_work_items(registry=registry) if candidate.get("docId") == doc_id), None)
    samples = item.get("samples") if item and isinstance(item.get("samples"), list) else []
    sample_kind = str((item or {}).get("sampleKind") or "filled_sample")
    docx_context: dict[str, Any] | None = None
    if item and item.get("hasEditableOfficeTemplate"):
        try:
            docx_context = analyze_docx_template(doc_id, registry=registry)
        except Exception as exc:
            docx_context = {"error": str(exc)}
    created_at = datetime.now(timezone.utc).isoformat()
    request_dir = workbench_subdir(doc_id, "authoring") / "agent_requests" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    request_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        "schema_draft.json",
        "stylesheet_draft.json",
        "faker_profile_draft.json",
        "value_pool_draft.json",
        "research_report.json",
        "uncertainty_report.json",
        "anchor_map_draft.json",
        "application_notes.md",
    ]
    request = {
        "schema_version": 2,
        "status": "ready_for_agent",
        "docId": doc_id,
        "title": doc.title,
        "instruction": str(payload.get("instruction") or "").strip(),
        "options": options,
        "contract": {
            "mode": "agentic_bbox_correction" if options["mode"] == "bbox_correction" else "agentic_authoring_a_to_z",
            "inference_options": options,
            "pipeline": {
                "stages": ["schema_pass", "faker_pass", "validation_repair_pass"],
                "primary_schema": "schema_draft.json.semantic_schema",
                "binding_layer": "schema_draft.json.fields|field_bindings",
                "runtime_faker": "faker_profile_draft.json.field_generators+data_pools+constraints",
                "missing_use_anchor_policy": "materialize_under_검토필요_and_report_repair",
            },
            "sample_kind": sample_kind,
            "input_formats": ["pdf", "jpg", "jpeg", "png", "docx"],
            "generation_paths": ["image-template", "editable-office-template"],
            "outputs": outputs,
            "workflow_steps": [
                "입력 파일, OCR, bbox review, 기존 authoring 파일을 먼저 읽고 근거 anchor를 정리한다.",
                "실제 문서명을 웹 검색해 작성 방법, 문서 의미, 포함 정보, 실제 샘플 양식, 공식/공공/기관/기업 설명을 수집한다.",
                "1차 pass에서는 문서/시각/OCR/리서치 근거로 primary semantic_schema와 모든 use bbox binding을 먼저 확정한다.",
                "2차 pass에서는 확정된 schema/field_id를 기준으로 faker_profile_draft의 data pool과 relationship constraint를 확장한다.",
                "불확실하거나 출처가 충돌하는 항목은 검토필요 leaf 또는 uncertainty_report에 남긴다.",
                "모든 산출물은 draft로만 저장하며 적용/덮어쓰기는 UI 승인 이후 수행한다.",
            ],
            "web_research_rules": [
                "schema/faker 초안 생성 전에 실제 문서명과 유사 명칭을 웹 검색한다.",
                "공식/원문/공공기관/법령/제도 설명/실제 샘플 양식을 우선 출처로 사용한다.",
                "research_report에는 검색일, 검색어, 출처 URL, 출처 유형, 요약, 필드별 반영 근거를 기록한다.",
                "리서치는 문서에 보이는 anchor의 의미 해석과 faker profile 정밀화를 위한 보조 근거일 뿐, 템플릿에 없는 필드를 자동 추가하는 근거가 아니다.",
                "출처 간 내용이 다르거나 실제 템플릿 anchor와 연결되지 않으면 faker rule을 확정하지 않고 uncertainty_report에 남긴다.",
            ],
            "schema_rules": [
                "`schema_draft.json`은 constrained full authoring draft이다. Agent가 의미 판단과 bbox mapping을 함께 수행하되, 시스템이 deterministic하게 분할할 수 있는 JSON만 작성한다.",
                "`schema_draft.json.semantic_schema`는 사용자와 GT가 보는 primary schema이다. 메타데이터 없이 KIE 관점의 key-value hierarchy만 작성하고 모든 leaf value는 빈 문자열로 둔다.",
                "현재 primary schema 런타임은 JSON object hierarchy만 지원한다. 배열/list를 사용하지 말고 반복 행은 `검수내역/행1/...`, `검수내역/행2/...`처럼 명시적 object key로 구조화한다.",
                "`schema_draft.json.fields` 또는 `schema_draft.json.field_bindings`는 semantic_schema leaf와 bbox anchor를 연결하기 위한 binding layer로만 사용한다.",
                "각 binding은 `field_id`, 한국어 `key` 또는 `label`, `semantic_path`, `anchor_id`, 빈 `value`, 선택적 `label_anchor_ids`, `value_type`, `faker_rule`/`generator`, `style_class`, `unit_policy`, `research_evidence_ids`, `visual_evidence`를 포함한다.",
                "각 binding의 `semantic_path`는 반드시 `semantic_schema`의 leaf path와 정확히 일치해야 한다. 단, 화면 렌더링만을 위한 복합 표시 필드는 `export:{include:false}`를 명시하고 semantic_schema leaf 매핑에서 제외할 수 있다.",
                "각 binding의 `anchor_id`는 anchor_map_draft에 존재해야 하며, 값 target인 `use` anchor여야 한다. 라벨 bbox는 `label_anchor_ids`에만 둔다.",
                "key는 실제 문서에 보이는 라벨, 표제, placeholder, 주변 텍스트, 편집 가능한 anchor 기반 한국어 자연어를 우선한다.",
                "문서에 보이지 않는 추상 키, 업무 추론만으로 만든 키, downstream 편의용 임의 구조체를 만들지 않는다.",
                "웹 리서치로 발견한 일반 항목이라도 대응 anchor가 없으면 schema_draft에 자동 추가하지 않는다.",
                "`use` anchor는 절대 생략하지 않는다. 의미가 불확실해도 반드시 `검토필요/<anchor_id 또는 보이는 label>` primary leaf와 binding field를 만들고 `review_required:true`, 낮은 confidence, uncertainty_report 항목을 남긴다.",
                "`unmapped_use_anchors`는 성공 산출물에서 금지한다. 모든 use anchor coverage는 100%여야 한다.",
                "예: primary semantic schema에는 `입원일`, `퇴원일`을 분리 저장하되 문서에는 `입원: yyyy-mm-dd, 퇴원: yyyy-mm-dd` 한 줄로 찍어야 한다면, 분리 leaf field는 `render_policy:{render:false}`로 두고 복합 표시 field는 같은 anchor에 `export:{include:false}`로 둔다.",
            ],
            "visual_source_of_truth_rules": [
                "전체 템플릿 이미지가 최상위 source of truth이다. 웹 리서치, 문서명, 라벨 텍스트, 관행보다 실제 전체 문서 이미지에서 보이는 레이아웃/라벨/값 위치 관계가 우선한다.",
                "agent_requests의 visual_evidence_manifest.json은 전체 템플릿 이미지 경로와 bbox 위치 인덱스이다. 먼저 전체 이미지를 보고 문맥을 판단하고, crops/*.png는 작은 글자나 경계가 애매할 때만 확대 보조 자료로 확인한다.",
                "값 위치 바로 옆/안에 정적 단위나 prefix/suffix가 실제로 인쇄되어 있는지는 전체 이미지의 문맥에서 판단하고, 필요한 경우 해당 crop으로 확대 확인한다.",
                "라벨에만 단위 의미가 있고 값 위치에는 별도 정적 단위가 없으면, 그 단위가 자연스러운 값 표기의 일부인지 판단해 포함할 수 있다. 예: 호수/가구수/세대수 값은 `0호/0가구/0세대`처럼 생성한다.",
                "전체 이미지에서 보이는 시각 근거와 OCR/리서치가 충돌하면 전체 이미지 근거를 따르고, 결정 근거를 faker_profile_draft.json.field_rules 또는 uncertainty_report.json에 기록한다.",
            ],
            "faker_profile_rules": [
                "schema key의 의미가 충분히 명확하고 문서 anchor 또는 리서치 근거와 연결될 때만 faker rule을 제안한다.",
                "문서 필드의 의미와 실제 작성 관행을 근거로 타입, 형식, 값 범위, 선택지, 단위, 날짜/금액/식별번호 규칙을 제안하되, 반드시 현재 DataFactory 렌더러가 지원하는 rule 문법만 사용한다.",
                f"날짜와 연령 관계는 요청의 고정 기준일 `{options['asOfDate']}`을 기준으로 설계한다. 미래 날짜를 만들지 말고 실행 시각에 따라 결과가 달라지는 암묵적 today를 전제로 하지 않는다.",
                "서로 독립적으로 생성하면 문서 유효성이 깨지는 field들은 `faker_profile_draft.json.constraints`에 명시적으로 모델링한다. 예: 체크박스 택1, 시작/종료일 순서, 행/열 합계, 본인부담금/공단부담금/총액 관계.",
                "지원 constraint 타입은 `pick_record`, `copy`, `exclusive_choice`, `primary_secondary_group`, `date_group`, `date_order`, `date_not_before`, `date_not_after`, `sum`, `numeric_range`, `numeric_compare`, `age_from_rrn`뿐이다. 지원하지 않는 수식 DSL이나 자연어 constraint는 쓰지 말고 uncertainty_report에 보류한다.",
                "연/월/일이 각각 다른 bbox로 분리된 날짜 placeholder에는 `date.year`, `date.month`, `date.day`를 우선 사용한다. 날짜의 월/일/연도에 `pattern:##` 또는 `pattern:####`를 쓰지 않는다.",
                "문서 이미지/템플릿의 값 입력 위치 바로 옆/안에 `㎡`, `m²`, `m2`, `%`, `m`, `원`, `명`, `건`, `동`, `층` 같은 단위가 이미 정적 텍스트로 남아 있으면 faker 값에는 그 단위를 포함하지 않는다.",
                "`호/가구/세대`처럼 라벨에만 단위 의미가 있고 값 위치에 별도 정적 단위가 없는 복합 값은 단위를 포함해 생성한다. 단위 포함/제외 근거를 field_rules 또는 uncertainty_report에 기록한다.",
                "faker_profile_draft.json에는 렌더러가 직접 읽는 `field_generators` 객체를 반드시 포함하고, key는 schema_draft.fields[].field_id, value는 지원 rule 문자열이어야 한다.",
                f"지원 rule 문법: {', '.join(AUTHORING_AGENT_SUPPORTED_FAKER_RULES)}.",
                f"`pool:<name>`을 쓰는 경우 faker_profile_draft.json의 `data_pools.<name>`에 반드시 실제 scalar 합성 값 배열을 함께 정의한다. 열린 scalar pool은 최소 {options['scalarPoolMinSize']}개, `pick_record`용 상관관계 record pool은 최소 {options['recordPoolMinSize']}개의 다양하고 현실적인 값을 포함해야 하며, data_pools에 없는 pool 이름은 절대 쓰지 않는다.",
                "법령/서식상 선택지가 고정된 작은 폐쇄형 pool만 `pool_policies.<name>={closed_set:true, exception_kind:'legal_or_form_closed_set', evidence:'...'}`와 근거를 명시해 최소 크기 예외로 인정한다. 단순히 자료를 충분히 만들지 못한 pool이나 현실의 개방형 record pool에는 이 예외를 사용하지 않는다.",
                "`date_between:`, `time|format:`, `decimal_range:`, `identifier.*`, `area.*`, `land_use.*`, `building.*`, `text.short`, `count_triplet`, `lot_number`, `page_count_label`처럼 현재 렌더러가 모르는 custom rule/type 이름은 field_generators 값으로 쓰지 않는다.",
                "지원 문법만으로 정밀 형식을 표현하기 어렵다면 `pattern:`, `choice:`, `pool:`, `template:` 중 하나로 근사하고, 근사 사유와 원래 의도는 field_rules 또는 uncertainty_report에 기록한다.",
                "의미가 불확실한 key는 literal:, choice:, pool: 등을 임의 생성하지 말고 보류 사유를 기록한다.",
                "실제 개인정보, 실제 기업정보, 실제 계좌/식별번호처럼 오인 가능한 값은 만들지 않는다.",
                "합성 더미 값 규칙 또는 승인된 value pool 참조만 사용한다.",
                "faker_profile_draft의 각 rule은 관련 schema key, anchor, research_report 근거 ID를 추적 가능하게 남긴다. 추적용 상세 목록은 선택적으로 `field_rules`에 중복 기록할 수 있지만, 최종 적용 기준은 `field_generators`이다.",
                "constraints의 각 항목도 관련 schema key, anchor, research_report 근거 ID를 `note`, `evidence_ids`, `field_rules` 중 하나에 추적 가능하게 남긴다.",
            ],
            "constraint_rules": AUTHORING_AGENT_SUPPORTED_CONSTRAINT_RULES,
            "template_anchor_rules": [
                "PDF/JPG는 visible text, OCR, bbox 위치, 주변 텍스트를 anchor 근거로 삼는다.",
                "DOCX는 visible text, content control, form field, table cell, bookmark, placeholder 등 편집 가능한 anchor를 근거로 삼는다.",
                "DOCX 경로에서는 docx_template_analysis.json과 docx_anchor_map.json의 value_cell anchor를 schema field anchor_id/docx_anchor_id로 사용한다.",
                "DOCX 경로의 stylesheet는 이미지 렌더링용이 아니라 lineage 호환용이다. 실제 값 삽입은 원본 DOCX 셀 서식을 유지한 채 DOCX XML에 값을 주입한다.",
                "DOCX 경로의 GT는 PDF OCR 결과가 아니라 faker value set을 source of truth로 한다. 다만 현재 DOCX 경로는 LibreOffice 폰트 재현 품질 문제가 해결되기 전까지 실험/보류 기능이다.",
                "숨은 메타데이터나 파일명만으로 schema key 또는 faker rule을 만들지 않는다.",
                "DOCX 경로에서는 원본 템플릿, 채워진 DOCX, 선택적 LibreOffice 렌더링 결과, GT lineage가 manifest에 남아야 한다. 외부 GUI 앱 자동화 렌더러는 사용하지 않는다.",
                "sample_kind가 blank_template이면 OCR/static label/keep bbox는 라벨 근거(label_anchor_ids)로만 쓰고 schema field의 anchor_id로 쓰지 않는다.",
                "sample_kind가 blank_template이면 schema field의 anchor_id는 반드시 리뷰에서 use로 확정된 값 입력 후보, 체크박스, 표 셀, manual bbox, visual_line_detect bbox 중 하나여야 한다.",
                "sample_kind가 blank_template이고 값 삽입 영역을 찾을 수 없으면 field를 만들지 말고 uncertainty_report에 남긴다.",
            ],
            "application_rules": [
                "렌더러는 authoring 데이터를 임의 보정하지 않고 schema/style/faker/render_policy를 그대로 따른다.",
                "Agent 산출물은 바로 적용하지 않고 draft로 저장한다.",
                "기존 authoring 파일을 덮어쓰기 전 사용자 승인과 백업 경로가 필요하다.",
                "UI 확정 전에는 schema_draft, faker_profile_draft, value_pool_draft, research_report, uncertainty_report를 함께 검토 가능해야 한다.",
            ],
        },
        "agent_contract_summary": {
            "use_anchor_coverage_required": True,
            "unknown_use_anchor_policy": "create primary semantic leaf under 검토필요 and mark review_required",
            "faker_profile_workflow": "internal_two_pass_schema_then_pool_expansion",
            "scalar_pool_min_size": options["scalarPoolMinSize"],
            "record_pool_min_size": options["recordPoolMinSize"],
            "as_of_date": options["asOfDate"],
        },
        "inputs": {
            "registry": doc.to_dict(),
            "sampleKind": sample_kind,
            "sample": samples[0] if samples else "",
            "latestDetections": item.get("latestDetections") if item else "",
            "latestReview": item.get("latestReview") if item else "",
            "latestInpainted": item.get("latestInpainted") if item else "",
            "existingAuthoring": {
                "schema": item.get("latestAuthoringSchema") if item else "",
                "stylesheet": item.get("latestAuthoringStylesheet") if item else "",
                "fakerProfile": item.get("latestAuthoringFakerProfile") if item else "",
            },
            "docx": {
                "enabled": bool(item and item.get("hasEditableOfficeTemplate")),
                "officeRender": item.get("officeRender") if item else {},
                "analysis": (docx_context or {}).get("paths", {}).get("analysis", ""),
                "anchorMap": (docx_context or {}).get("paths", {}).get("anchorMap", ""),
                "summary": (docx_context or {}).get("summary", {}),
                "error": (docx_context or {}).get("error", ""),
            },
        },
        "created_at": created_at,
    }
    path = request_dir / "request.json"
    prompt_path = request_dir / "request.md"
    generated_sidecars: dict[str, str] = {}
    latest_review = str(request["inputs"].get("latestReview") or "")
    if latest_review:
        try:
            anchor_map_path = request_dir / "anchor_map_draft.json"
            review_anchor_map(_resolve_workspace_path(latest_review), out_path=anchor_map_path, doc_id=doc_id, title=doc.title)
            generated_sidecars["anchorMapDraft"] = _display_path(anchor_map_path, ROOT)
        except Exception as exc:
            generated_sidecars["anchorMapError"] = str(exc)
        try:
            visual_manifest_path = _write_authoring_visual_evidence_manifest(
                doc_id=doc_id,
                review_path=_resolve_workspace_path(latest_review),
                request_dir=request_dir,
                visual_source_path=_resolve_workspace_path(str(request["inputs"].get("latestInpainted") or "")) if request["inputs"].get("latestInpainted") else None,
            )
            generated_sidecars["visualEvidenceManifest"] = _display_path(visual_manifest_path, ROOT)
        except Exception as exc:
            generated_sidecars["visualEvidenceError"] = str(exc)
    request["generated_sidecars"] = generated_sidecars
    path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prompt_path.write_text(_authoring_agent_prompt_markdown(request), encoding="utf-8")
    update_manifest_artifact(doc_id, "authoring_agent_request", path)
    update_manifest_artifact(doc_id, "authoring_agent_prompt", prompt_path)
    if generated_sidecars.get("anchorMapDraft"):
        update_manifest_artifact(doc_id, "authoring_agent_anchor_map", _resolve_workspace_path(generated_sidecars["anchorMapDraft"]))
    return {
        "docId": doc_id,
        "status": "ready_for_agent",
        "paths": {"request": _display_path(path, ROOT), "prompt": _display_path(prompt_path, ROOT)},
        "request": request,
    }


def _write_authoring_visual_evidence_manifest(
    *,
    doc_id: str,
    review_path: Path,
    request_dir: Path,
    visual_source_path: Path | None = None,
    padding: int = 64,
) -> Path:
    policy = load_review_policy(review_path)
    visual_source = visual_source_path if visual_source_path and visual_source_path.exists() else policy.source_image
    visual_source = visual_source.resolve()
    crop_dir = request_dir / "visual_evidence" / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    with Image.open(visual_source) as image:
        source_image = image.convert("RGB")
        for index, label in enumerate(policy.labels, start=1):
            if label.status != "use":
                continue
            padded = label.bbox.padded(padding).clipped(policy.image_width, policy.image_height)
            crop_path = crop_dir / f"crop_{index:04d}_{_safe_name(label.id)}.png"
            source_image.crop((padded.x, padded.y, padded.right, padded.bottom)).save(crop_path)
            entries.append(
                {
                    "anchor_id": label.id,
                    "status": label.status,
                    "auto_type": label.auto_type,
                    "text": label.text,
                    "text_source": label.text_source,
                    "confidence": label.confidence,
                    "bbox": label.bbox.to_list(),
                    "padded_bbox": padded.to_list(),
                    "bbox_format": "xywh",
                    "crop_path": _display_path(crop_path, ROOT),
                    "visual_checklist": [
                        "Use this crop only as a zoom aid after checking the full template image context.",
                        "If static unit/prefix/suffix is visible at the value position, omit it from the generated value.",
                        "If unit words appear only in the label and not beside the value position, keep them when they are part of the natural value notation.",
                    ],
                }
            )
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "doc_id": doc_id,
        "source_review": _display_path(review_path, ROOT),
        "visual_source": _display_path(visual_source, ROOT),
        "source_image": _display_path(policy.source_image, ROOT),
        "image": {"width": policy.image_width, "height": policy.image_height},
        "padding": padding,
        "source_of_truth_policy": [
            "The full template image is the primary visual source of truth; crops are zoom aids, not replacements for full-page context.",
            "Unit/prefix/suffix decisions must be made from value-position visual evidence, not from label text alone.",
        ],
        "crops": entries,
    }
    manifest_path = request_dir / "visual_evidence_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def authoring_agent_run_payload(payload: dict[str, Any], *, async_run: bool = True) -> dict[str, Any]:
    """Start a real Codex-backed authoring inference job.

    This is intentionally more than a request-package generator: the launched
    Codex process must create the draft output files declared by the contract.
    The files remain drafts in the request directory until the user explicitly
    approves/saves them.
    """

    request_payload = authoring_agent_request_payload(payload)
    doc_id = str(request_payload["docId"])
    request_path = _resolve_workspace_path(request_payload["paths"]["request"])
    request_dir = request_path.parent
    run_dir = workbench_subdir(doc_id, "authoring") / "agent_runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    job_path = run_dir / "job.json"
    prompt_path = run_dir / "codex_exec_prompt.md"
    last_message_path = run_dir / "codex_last_message.md"
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    options = request_payload.get("request", {}).get("options") if isinstance(request_payload.get("request"), dict) else _authoring_agent_options(payload)
    prompt = _authoring_agent_exec_prompt(request_path=request_path, request_dir=request_dir, run_dir=run_dir)
    prompt_path.write_text(prompt, encoding="utf-8")
    job = {
        "schema_version": 1,
        "jobId": run_dir.name,
        "docId": doc_id,
        "status": "queued",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "startedAt": None,
        "finishedAt": None,
        "requestPath": _display_path(request_path, ROOT),
        "requestDir": _display_path(request_dir, ROOT),
        "runDir": _display_path(run_dir, ROOT),
        "promptPath": _display_path(prompt_path, ROOT),
        "lastMessagePath": _display_path(last_message_path, ROOT),
        "stdoutPath": _display_path(stdout_path, ROOT),
        "stderrPath": _display_path(stderr_path, ROOT),
        "requiredOutputs": list(AUTHORING_AGENT_REQUIRED_OUTPUTS),
        "outputs": {},
        "validation": {"missing": list(AUTHORING_AGENT_REQUIRED_OUTPUTS), "invalidJson": [], "ready": False},
        "options": options,
    }
    _write_agent_job(job_path, job)
    update_manifest_artifact(doc_id, "authoring_agent_run", job_path)
    update_manifest_artifact(doc_id, "authoring_agent_prompt_exec", prompt_path)
    if async_run:
        thread = threading.Thread(
            target=_run_authoring_agent_job,
            args=(job_path, request_path, request_dir, run_dir, prompt_path, last_message_path, stdout_path, stderr_path),
            daemon=True,
        )
        thread.start()
        return _agent_job_payload(job_path)
    _run_authoring_agent_job(job_path, request_path, request_dir, run_dir, prompt_path, last_message_path, stdout_path, stderr_path)
    return _agent_job_payload(job_path)


def authoring_agent_run_status_payload(payload: dict[str, Any]) -> dict[str, Any]:
    job_path_value = str(payload.get("jobPath") or "")
    if job_path_value:
        job_path = _resolve_workspace_path(job_path_value)
    else:
        doc_id = str(payload.get("docId") or "")
        if not doc_id:
            raise ValueError("jobPath or docId is required")
        run_root = workbench_subdir(doc_id, "authoring") / "agent_runs"
        job_paths = sorted(run_root.glob("*/job.json")) if run_root.exists() else []
        if not job_paths:
            raise FileNotFoundError(f"no authoring agent run for {doc_id}")
        job_path = job_paths[-1]
    return _agent_job_payload(job_path)


def apply_authoring_agent_drafts_payload(payload: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(payload.get("docId") or "")
    if not doc_id:
        raise ValueError("docId is required")
    request_path_value = str(payload.get("requestPath") or "")
    if request_path_value:
        request_path = _resolve_workspace_path(request_path_value)
    else:
        run_status = authoring_agent_run_status_payload({"docId": doc_id})
        request_path = _resolve_workspace_path(str(run_status.get("requestPath") or ""))
    request_dir = request_path.parent
    schema_draft_path = request_dir / "schema_draft.json"
    stylesheet_draft_path = request_dir / "stylesheet_draft.json"
    faker_profile_draft_path = request_dir / "faker_profile_draft.json"
    anchor_map_path = request_dir / "anchor_map_draft.json"
    for required in (schema_draft_path, stylesheet_draft_path, faker_profile_draft_path):
        if not required.exists():
            raise FileNotFoundError(required)
    schema_draft = json.loads(schema_draft_path.read_text(encoding="utf-8"))
    stylesheet_draft = json.loads(stylesheet_draft_path.read_text(encoding="utf-8"))
    faker_profile_draft = json.loads(faker_profile_draft_path.read_text(encoding="utf-8"))
    anchor_map = json.loads(anchor_map_path.read_text(encoding="utf-8")) if anchor_map_path.exists() else None
    registry = load_registry()
    doc = registry.documents.get(doc_id)
    item = next((candidate for candidate in list_work_items(registry=registry) if candidate.get("docId") == doc_id), None)
    source_review = str((item or {}).get("latestReview") or schema_draft.get("source_review") or "")
    source_image = str((anchor_map or {}).get("source_image") or schema_draft.get("source_image") or ((item or {}).get("samples") or [""])[0] or "")
    source_inpainted = str((item or {}).get("latestInpainted") or schema_draft.get("source_inpainted") or source_image)
    schema = semantic_schema_to_authoring_schema(
        schema_draft,
        anchor_map=anchor_map,
        source_review=source_review,
        source_image=source_image,
        source_inpainted=source_inpainted,
        doc_id=doc_id,
        title=doc.title if doc else str(schema_draft.get("title") or ""),
    )
    authoring_dir = workbench_subdir(doc_id, "authoring")
    existing_schema_path = authoring_dir / "schema.json"
    existing_stylesheet_path = authoring_dir / "stylesheet.json"
    existing_schema = json.loads(existing_schema_path.read_text(encoding="utf-8")) if existing_schema_path.exists() else None
    regression = _validate_authoring_agent_apply_regression(existing_schema, schema)
    if regression["errors"]:
        first = regression["errors"][0]
        raise ValueError(
            f"authoring agent apply regression blocked: {first.get('code')} "
            f"({regression['summary']['previousFieldCount']} -> {regression['summary']['candidateFieldCount']} fields)"
        )
    applied_review_path: Path | None = None
    if isinstance(anchor_map, dict) and isinstance(anchor_map.get("anchors"), list):
        applied_review_path = _write_authoring_agent_anchor_review(
            doc_id,
            request_dir,
            anchor_map,
            source_review=source_review,
            source_image=source_image,
        )
        schema["source_review"] = str(applied_review_path.resolve())
        schema["bbox_source"] = {"canonical": "review", "review_path": str(applied_review_path.resolve())}
        schema["anchor_map_ref"] = _display_path(anchor_map_path, ROOT)
    style_remap: dict[str, Any] | None = None
    if existing_schema is not None and existing_stylesheet_path.exists():
        if "handwriting" not in schema and isinstance(existing_schema.get("handwriting"), dict):
            schema["handwriting"] = json.loads(json.dumps(existing_schema["handwriting"]))
        schema, stylesheet_draft, style_remap = remap_styles_from_previous(
            schema,
            stylesheet_draft,
            existing_schema,
            json.loads(existing_stylesheet_path.read_text(encoding="utf-8")),
            require_all_rendered=False,
        )
    consistency = _raise_if_authoring_inconsistent(schema, faker_profile_draft, strict_review_coverage=True)
    result = save_authoring_bundle(
        authoring_dir / "schema.json",
        authoring_dir / "stylesheet.json",
        authoring_dir / "faker_profile.json",
        schema=schema,
        stylesheet=stylesheet_draft,
        faker_profile=faker_profile_draft,
    )
    update_manifest_artifact(doc_id, "authoring", result.schema)
    update_manifest_artifact(doc_id, "authoring_stylesheet", result.stylesheet)
    update_manifest_artifact(doc_id, "authoring_faker_profile", result.faker_profile)
    update_manifest_artifact(doc_id, "authoring_agent_applied_request", request_path)
    if anchor_map_path.exists():
        update_manifest_artifact(doc_id, "authoring_anchor_map", anchor_map_path)
    if applied_review_path is not None:
        update_manifest_artifact(doc_id, "authoring_agent_applied_review", applied_review_path)
    return {
        "docId": doc_id,
        "requestPath": _display_path(request_path, ROOT),
        "paths": _paths_to_client({"schema": result.schema, "stylesheet": result.stylesheet, "faker_profile": result.faker_profile}),
        "consistency": consistency,
        "regression": regression,
        "styleRemap": style_remap,
        **result.payload,
    }


def _validate_authoring_agent_apply_regression(
    existing_schema: dict[str, Any] | None,
    candidate_schema: dict[str, Any],
    *,
    minimum_field_retention: float = 1.0,
) -> dict[str, Any]:
    """Detect silent destructive replacement before an agent draft is saved.

    The ordinary consistency validator proves that a candidate is internally
    complete relative to its own review.  It cannot notice that the candidate
    accidentally switched pages or discarded most of an already-authored
    document.  This comparison protects that previous contract while allowing
    new documents and coordinate-only bbox edits on the same source page.
    """

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    previous_fields = existing_schema.get("fields") if isinstance(existing_schema, dict) and isinstance(existing_schema.get("fields"), list) else []
    candidate_fields = candidate_schema.get("fields") if isinstance(candidate_schema.get("fields"), list) else []
    previous_ids = {
        str(field.get("bbox_label_id") or field.get("source_detection_id") or "").strip()
        for field in previous_fields
        if isinstance(field, dict) and str(field.get("bbox_label_id") or field.get("source_detection_id") or "").strip()
    }
    candidate_ids = {
        str(field.get("bbox_label_id") or field.get("source_detection_id") or "").strip()
        for field in candidate_fields
        if isinstance(field, dict) and str(field.get("bbox_label_id") or field.get("source_detection_id") or "").strip()
    }
    previous_count = len(previous_fields)
    candidate_count = len(candidate_fields)
    retained_ids = previous_ids & candidate_ids

    def source_identity(value: Any) -> str:
        text = str(value or "").strip()
        return str(_resolve_workspace_path(text).resolve()) if text else ""

    previous_source = source_identity(existing_schema.get("source_image")) if isinstance(existing_schema, dict) else ""
    candidate_source = source_identity(candidate_schema.get("source_image"))
    if previous_count and previous_source and candidate_source and previous_source != candidate_source:
        errors.append(
            {
                "code": "authoring_agent_source_image_changed",
                "previous": _display_path(Path(previous_source), ROOT),
                "candidate": _display_path(Path(candidate_source), ROOT),
                "message": "agent draft cannot silently replace the source page of an existing authoring bundle",
            }
        )

    field_retention = candidate_count / previous_count if previous_count else 1.0
    if previous_count and field_retention < minimum_field_retention:
        errors.append(
            {
                "code": "authoring_agent_existing_field_coverage_drop",
                "previous": previous_count,
                "candidate": candidate_count,
                "retention": round(field_retention, 4),
                "minimum": minimum_field_retention,
                "message": "agent draft discarded too much of the existing authoring contract",
            }
        )
    elif previous_ids and len(retained_ids) / len(previous_ids) < minimum_field_retention:
        warnings.append(
            {
                "code": "authoring_agent_anchor_identity_changed",
                "previous": len(previous_ids),
                "retained": len(retained_ids),
                "message": "most anchor ids changed while field coverage was retained; verify intentional bbox splitting",
            }
        )

    return {
        "ready": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "previousFieldCount": previous_count,
            "candidateFieldCount": candidate_count,
            "previousAnchorCount": len(previous_ids),
            "candidateAnchorCount": len(candidate_ids),
            "retainedAnchorCount": len(retained_ids),
            "fieldRetention": round(field_retention, 4),
        },
    }


def _write_authoring_agent_anchor_review(
    doc_id: str,
    request_dir: Path,
    anchor_map: dict[str, Any],
    *,
    source_review: str,
    source_image: str,
) -> Path:
    """Materialize agent anchors as the runtime bbox review source.

    Persisted authoring schemas store bbox label ids, not coordinates. The UI
    and renderer resolve those ids from ``schema.source_review``. Therefore an
    applied agent draft that adds/splits anchors must also publish a
    review-policy shaped source file containing those anchors.
    """

    source_image_path = _resolve_workspace_path(str(anchor_map.get("source_image") or source_image or ""))
    image_info = anchor_map.get("image") if isinstance(anchor_map.get("image"), dict) else {}
    width = int(image_info.get("width") or 0)
    height = int(image_info.get("height") or 0)
    if (not width or not height) and source_image_path.exists():
        with Image.open(source_image_path) as image:
            width, height = image.size
    source_review_path = _resolve_workspace_path(str(anchor_map.get("source_review") or source_review or request_dir / "anchor_map_draft.json"))
    labels: list[dict[str, Any]] = []
    for anchor in anchor_map.get("anchors") or []:
        if not isinstance(anchor, dict):
            continue
        anchor_id = str(anchor.get("anchor_id") or anchor.get("id") or "").strip()
        bbox = anchor.get("bbox")
        if not anchor_id or not isinstance(bbox, list) or len(bbox) != 4:
            continue
        try:
            x, y, box_width, box_height = [int(round(float(value))) for value in bbox]
        except (TypeError, ValueError):
            continue
        if box_width <= 0 or box_height <= 0:
            continue
        status = str(anchor.get("status") or "keep").strip().lower()
        if status not in {"use", "keep", "ignore"}:
            status = "keep"
        auto_type = str(anchor.get("auto_type") or anchor.get("type") or "unknown").strip()
        if auto_type not in {"field_value", "static_label", "table_cell", "long_paragraph", "header_footer", "stamp_or_seal", "watermark", "unknown"}:
            auto_type = "unknown"
        render_mode = str(anchor.get("render_mode") or "printed").strip()
        if render_mode not in {"handwriting", "printed"}:
            render_mode = "printed"
        text = str(anchor.get("text") or anchor.get("suggested_schema_key") or "")
        labels.append(
            {
                "id": anchor_id,
                "text": text,
                "confidence": anchor.get("confidence"),
                "bbox": [x, y, box_width, box_height],
                "bbox_format": "xywh",
                "polygon": [[x, y], [x + box_width, y], [x + box_width, y + box_height], [x, y + box_height]],
                "status": status,
                "auto_type": auto_type,
                "reason": str(anchor.get("reason") or "materialized from authoring agent anchor map"),
                "locked": bool(anchor.get("locked", False)),
                "notes": str(anchor.get("notes") or ""),
                "original_text": text,
                "original_confidence": anchor.get("confidence"),
                "text_source": str(anchor.get("text_source") or anchor.get("source") or "authoring_agent_anchor_map"),
                "ocr_text_stale": False,
                "rec_text": "",
                "rec_confidence": None,
                "rec_engine": "",
                "rec_updated_at": "",
                "render_mode": render_mode,
            }
        )
    status_counts: dict[str, int] = {}
    auto_type_counts: dict[str, int] = {}
    for label in labels:
        status_counts[str(label["status"])] = status_counts.get(str(label["status"]), 0) + 1
        auto_type_counts[str(label["auto_type"])] = auto_type_counts.get(str(label["auto_type"]), 0) + 1
    review_payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_engine": "authoring_agent_anchor_map",
        "source_detections": _display_path(source_review_path, ROOT),
        "source_image": _display_path(source_image_path, ROOT),
        "image": {"width": width, "height": height},
        "summary": {"total": len(labels), "by_status": status_counts, "by_auto_type": auto_type_counts},
        "labels": labels,
    }
    out_path = workbench_subdir(doc_id, "authoring") / "agent_applied_reviews" / request_dir.name / "review.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def _authoring_agent_exec_prompt(*, request_path: Path, request_dir: Path, run_dir: Path, stage: str = "full") -> str:
    stage_instruction = {
        "schema": """## Current pass: 1/2 schema and evidence freeze
- Produce or replace only schema_draft.json, stylesheet_draft.json, research_report.json, uncertainty_report.json, and anchor_map_draft.json.
- Do not author faker_profile_draft.json or value_pool_draft.json in this pass.
- Freeze a complete primary semantic hierarchy and 100% use-anchor binding coverage. Field IDs written here are the immutable contract for pass 2.
""",
        "faker": """## Current pass: 2/2 faker and relationship expansion
- Treat the existing schema_draft.json, anchor_map_draft.json, research_report.json, and stylesheet_draft.json from pass 1 as fixed inputs.
- Do not rename field_id, change semantic_path, drop bindings, or restructure semantic_schema in this pass.
- Produce or replace faker_profile_draft.json, value_pool_draft.json, uncertainty_report.json, and application_notes.md.
- Expand realistic pools and supported relationships, then validate every fixed binding has exactly one supported field generator.
""",
        "validation_repair": """## Current pass: validation repair
- Read the current draft files and the appended machine validation errors.
- Make the smallest changes needed to satisfy the contract. Preserve the pass-1 semantic hierarchy, field IDs, semantic paths, anchors, and validated stylesheet unless a reported error explicitly requires changing them.
- Never silence an error by dropping a use anchor, semantic leaf, generator, pool relationship, or research evidence.
- Re-run JSON/coverage/pool/constraint checks before finishing.
""",
    }.get(stage, "## Current pass: full draft generation\n")
    return f"""# Codex authoring inference job

{stage_instruction}

You are running as a local Codex subprocess for the DataFactory workbench.

## Required behavior
- Read the request package: `{_display_path(request_path, ROOT)}`.
- Read every input file referenced by the request when it exists.
- Treat `generated_sidecars.visualEvidenceManifest` as the visual index for the full template image and bbox locations when present.
- Inspect the full template image as the primary visual source of truth for field targets, static labels, prefix/suffix, and unit handling. Use crop images only as optional zoom aids for ambiguous or small regions. Do not infer unit inclusion/exclusion from label text alone.
- Use live web search for the document type research required by the request contract.
- Follow `contract.sample_kind` strictly. If it is `blank_template`, treat OCR text bboxes as static label evidence unless review status/role proves they are value regions.
- Generate the full draft outputs listed below.
- Write outputs only inside this request directory: `{_display_path(request_dir, ROOT)}`.
- Do not overwrite final `schema.json`, `stylesheet.json`, or `faker_profile.json`.
- Do not edit source code, registry files, workbench manifests, or samples.
- Respect the current pass boundary. The outer job runner invokes separate Codex processes for schema/evidence and faker/relationship work.
- If a use anchor is uncertain, do not omit it. Create a `검토필요/<anchor_id or visible label>` primary schema leaf, bind the anchor, set `review_required:true`, use a conservative supported faker rule such as `free_text.short`, and record the uncertainty.
- For blank templates, never use a static label/keep bbox as `schema_draft.fields[].anchor_id`. Use `label_anchor_ids` for label evidence and use only a confirmed value-region/checkbox/table-cell/manual/visual-line-detect anchor as the field target.

## Required output files
{chr(10).join(f"- `{name}`" for name in AUTHORING_AGENT_REQUIRED_OUTPUTS)}

## Output contracts
- `schema_draft.json`: constrained full authoring draft with `schema_version`, `doc_id`, `title`, primary `semantic_schema`, and binding layer `fields` or `field_bindings`. `semantic_schema` must be a metadata-free KIE key-value hierarchy whose leaf values are empty strings. The binding layer is only the bridge from semantic leaf to bbox target; each binding must include `field_id`, `key` or `label`, `semantic_path`, `anchor_id`, `value` as an empty string, and optional `label_anchor_ids`, `value_type`, `faker_rule`/`generator`, `style_class`, `unit_policy`, `research_evidence_ids`, and `visual_evidence`.
- Every binding `semantic_path` must point to an existing `semantic_schema` leaf. Exception: if a field is only a composite render string and should not enter the primary semantic schema, set `export:{{"include":false}}`; then its `semantic_path` may be a render-only path. Every binding `anchor_id` must exist in `anchor_map_draft.json` and target a `use` value-region anchor. `unmapped_use_anchors` is not allowed: every use anchor must have a binding, using `검토필요/...` when uncertain.
- For split-primary/composite-render cases, keep the primary semantic fields as hidden render fields with `render_policy:{{"render":false}}` and create a separate visible composite field with `export:{{"include":false}}`. Example: store `입원일` and `퇴원일` separately, but render one visible string like `입원: yyyy-mm-dd, 퇴원: yyyy-mm-dd`.
- `stylesheet_draft.json`: draft render style classes or field style hints; keep conservative defaults if visual style is uncertain.
- `faker_profile_draft.json`: must include `field_generators` as the renderer-compatible source of truth. It may also include `field_rules` for traceability, but every `field_generators` value must use only the supported rule grammar below. Do not use real personal/company/account data.
- `value_pool_draft.json`: reusable value pools proposed by the agent, with source/usage notes.
- `research_report.json`: search date, queries, source URLs, source type, summaries, and field-level evidence links.
- `uncertainty_report.json`: unresolved fields, conflicting evidence, low-confidence faker rules, and user decisions needed.
- `anchor_map_draft.json`: preserve or improve the anchor map from the request package.
- For `blank_template`, `anchor_map_draft.json` must distinguish value targets from labels using `status`, `auto_type`, `role`, `text_source`, or `provenance`. Static labels may be listed, but schema field targets must point to value targets only.
- `application_notes.md`: concise Korean notes explaining what was generated, what remains uncertain, and how to approve/apply.

## Supported faker rule grammar
Use only these forms in `faker_profile_draft.json.field_generators`.
{chr(10).join(f"- `{rule}`" for rule in AUTHORING_AGENT_SUPPORTED_FAKER_RULES)}

Do not put unsupported semantic type names in `field_generators`.
Before adding or removing a unit suffix in any generated value, inspect the full template image around the target bbox; use the crop only as a zoom aid if needed. If the unit remains as static text at the value position, omit the unit from the faker value. If the unit appears only in the label, such as 호/가구/세대, keep the unit in the generated value when it is part of the natural value notation.
If you use `pool:<name>`, define `data_pools.<name>` as an array of scalar synthetic values in the same `faker_profile_draft.json`; never reference an undefined pool. Open scalar pools must meet request.options.scalarPoolMinSize and `pick_record` object pools must meet request.options.recordPoolMinSize. Only a genuinely fixed legal/form scalar choice set may be smaller, and then its policy must include `closed_set:true`, `exception_kind:'legal_or_form_closed_set'`, and a non-empty evidence note. Record pools never receive this exception.
Examples of forbidden generator values: `date_between:-365d:+0d|format:%Y/%m/%d`, `time|format:%H:%M:%S`, `decimal_range:10..99`, `identifier.document_confirmation`, `area.square_meter`, `land_use.zoning`, `building.structure`, `text.short`, `count_triplet`, `lot_number`, `page_count_label`.
If precision would require an unsupported rule, approximate with `pattern:`, `choice:`, `pool:`, or `template:` and record the limitation in `uncertainty_report.json`.

## Supported faker relationship constraint grammar
`faker_profile_draft.json.constraints` is optional, but if present every item must use exactly one supported renderer contract below.
{chr(10).join(f"- {rule}" for rule in AUTHORING_AGENT_SUPPORTED_CONSTRAINT_RULES)}

## Completion criteria
Before finishing, verify all required files exist, all JSON files parse, every use anchor has a schema binding, every binding has a matching `field_generators` entry, every `field_generators` key matches a schema binding field_id, every pool reference exists and meets its scalar/record minimum or has a valid closed-set policy, and every `constraints` item follows the exact supported relationship constraint grammar above.
Return a short Korean final summary only after the files are written.

## Run directory
Use this run directory only for logs or scratch notes if needed: `{_display_path(run_dir, ROOT)}`.
"""


def _run_authoring_agent_job(
    job_path: Path,
    request_path: Path,
    request_dir: Path,
    run_dir: Path,
    prompt_path: Path,
    last_message_path: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> None:
    job = _read_agent_job(job_path)
    job.update({
        "status": "running",
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "passState": {"current": "schema", "completed": [], "planned": ["schema", "faker", "validation_repair"]},
    })
    _write_agent_job(job_path, job)
    options = job.get("options") if isinstance(job.get("options"), dict) else {}
    reasoning_effort = str(options.get("reasoningEffort") or "medium").strip().lower()
    if reasoning_effort not in AUTHORING_AGENT_REASONING_EFFORTS:
        reasoning_effort = "medium"
    def command_for(message_path: Path) -> list[str]:
        command = [
            "codex",
            "--search",
            "--ask-for-approval",
            "never",
            "-c",
            f'model_reasoning_effort="{reasoning_effort}"',
        ]
        if not bool(options.get("fastMode", False)):
            command.extend(["--disable", "fast_mode"])
        command.extend([
            "exec",
            "--cd",
            str(ROOT),
            "--sandbox",
            "workspace-write",
            "--output-last-message",
            str(message_path),
            "-",
        ])
        return command
    def run_codex(command: list[str], stage_prompt: str) -> tuple[subprocess.CompletedProcess[str], int]:
        completed: subprocess.CompletedProcess[str] | None = None
        for attempt in range(1, 4):
            completed = subprocess.run(
                command,
                input=stage_prompt,
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=60 * 30,
                check=False,
            )
            combined = f"{completed.stdout or ''}\n{completed.stderr or ''}".lower()
            transient = "selected model is at capacity" in combined or "network error" in combined
            if completed.returncode == 0 or not transient or attempt == 3:
                return completed, attempt
            sleep(5 * attempt)
        assert completed is not None
        return completed, 3
    try:
        stage_results: list[dict[str, Any]] = []
        frozen_artifacts: dict[str, tuple[str, Path]] = {}
        def restore_frozen_artifacts() -> list[str]:
            violations: list[str] = []
            for name, (expected_hash, frozen_copy) in frozen_artifacts.items():
                source = request_dir / name
                actual_hash = hashlib.sha256(source.read_bytes()).hexdigest() if source.exists() else "missing"
                if actual_hash != expected_hash:
                    violations.append(name)
                    shutil.copy2(frozen_copy, source)
            return violations

        completed = None
        for stage in ("schema", "faker"):
            stage_prompt_path = run_dir / f"codex_{stage}_pass_prompt.md"
            stage_message_path = run_dir / f"codex_{stage}_pass_last_message.md"
            stage_stdout_path = run_dir / f"{stage}_pass_stdout.log"
            stage_stderr_path = run_dir / f"{stage}_pass_stderr.log"
            stage_prompt = _authoring_agent_exec_prompt(
                request_path=request_path,
                request_dir=request_dir,
                run_dir=run_dir,
                stage=stage,
            )
            stage_prompt_path.write_text(stage_prompt, encoding="utf-8")
            command = command_for(stage_message_path)
            completed, attempt_count = run_codex(command, stage_prompt)
            stage_stdout_path.write_text(completed.stdout or "", encoding="utf-8")
            stage_stderr_path.write_text(completed.stderr or "", encoding="utf-8")
            stage_results.append(
                {
                    "stage": stage,
                    "returnCode": completed.returncode,
                    "promptPath": _display_path(stage_prompt_path, ROOT),
                    "lastMessagePath": _display_path(stage_message_path, ROOT),
                    "stdoutPath": _display_path(stage_stdout_path, ROOT),
                    "stderrPath": _display_path(stage_stderr_path, ROOT),
                    "command": command,
                    "attemptCount": attempt_count,
                }
            )
            if stage == "schema" and completed.returncode == 0:
                for name in ("schema_draft.json", "stylesheet_draft.json", "anchor_map_draft.json", "research_report.json"):
                    source = request_dir / name
                    if not source.exists():
                        continue
                    frozen_copy = run_dir / f"frozen_{name}"
                    shutil.copy2(source, frozen_copy)
                    frozen_artifacts[name] = (hashlib.sha256(source.read_bytes()).hexdigest(), frozen_copy)
            elif stage == "faker" and completed.returncode == 0:
                violations = restore_frozen_artifacts()
                if violations:
                    stage_results[-1]["frozenArtifactViolations"] = violations
            live_job = _read_agent_job(job_path)
            completed_stages = [item["stage"] for item in stage_results if item["returnCode"] == 0]
            live_job["passState"] = {
                "current": "faker" if stage == "schema" and completed.returncode == 0 else "validation_repair" if stage == "faker" and completed.returncode == 0 else stage,
                "completed": completed_stages,
                "planned": ["schema", "faker", "validation_repair"],
            }
            live_job["stages"] = stage_results
            _write_agent_job(job_path, live_job)
            if completed.returncode != 0:
                break
        assert completed is not None
        stdout_path.write_text("\n".join((run_dir / f"{stage['stage']}_pass_stdout.log").read_text(encoding="utf-8") for stage in stage_results), encoding="utf-8")
        stderr_path.write_text("\n".join((run_dir / f"{stage['stage']}_pass_stderr.log").read_text(encoding="utf-8") for stage in stage_results), encoding="utf-8")
        final_message = run_dir / f"codex_{stage_results[-1]['stage']}_pass_last_message.md"
        if final_message.exists():
            shutil.copy2(final_message, last_message_path)
        validation = _validate_authoring_agent_outputs(request_dir)
        if completed.returncode == 0 and not validation["ready"]:
            stage = "validation_repair"
            stage_prompt_path = run_dir / "codex_validation_repair_pass_prompt.md"
            stage_message_path = run_dir / "codex_validation_repair_pass_last_message.md"
            stage_stdout_path = run_dir / "validation_repair_pass_stdout.log"
            stage_stderr_path = run_dir / "validation_repair_pass_stderr.log"
            stage_prompt = _authoring_agent_exec_prompt(
                request_path=request_path,
                request_dir=request_dir,
                run_dir=run_dir,
                stage=stage,
            ) + "\n## Machine validation result to repair\n```json\n" + json.dumps(validation, ensure_ascii=False, indent=2) + "\n```\n"
            stage_prompt_path.write_text(stage_prompt, encoding="utf-8")
            command = command_for(stage_message_path)
            completed, attempt_count = run_codex(command, stage_prompt)
            stage_stdout_path.write_text(completed.stdout or "", encoding="utf-8")
            stage_stderr_path.write_text(completed.stderr or "", encoding="utf-8")
            stage_results.append(
                {
                    "stage": stage,
                    "returnCode": completed.returncode,
                    "promptPath": _display_path(stage_prompt_path, ROOT),
                    "lastMessagePath": _display_path(stage_message_path, ROOT),
                    "stdoutPath": _display_path(stage_stdout_path, ROOT),
                    "stderrPath": _display_path(stage_stderr_path, ROOT),
                    "command": command,
                    "attemptCount": attempt_count,
                }
            )
            violations = restore_frozen_artifacts()
            if violations:
                stage_results[-1]["frozenArtifactViolations"] = violations
            validation = _validate_authoring_agent_outputs(request_dir)
        stdout_path.write_text("\n".join((run_dir / f"{stage['stage']}_pass_stdout.log").read_text(encoding="utf-8") for stage in stage_results), encoding="utf-8")
        stderr_path.write_text("\n".join((run_dir / f"{stage['stage']}_pass_stderr.log").read_text(encoding="utf-8") for stage in stage_results), encoding="utf-8")
        final_message = run_dir / f"codex_{stage_results[-1]['stage']}_pass_last_message.md"
        if final_message.exists():
            shutil.copy2(final_message, last_message_path)
        job = _read_agent_job(job_path)
        job.update(
            {
                "status": "succeeded" if completed.returncode == 0 and validation["ready"] else "failed",
                "finishedAt": datetime.now(timezone.utc).isoformat(),
                "returnCode": completed.returncode,
                "command": stage_results[-1]["command"],
                "stages": stage_results,
                "outputs": validation["outputs"],
                "validation": validation,
                "repairSummary": validation.get("repairSummary") or {},
                "passState": {
                    "current": "completed" if completed.returncode == 0 and validation["ready"] else "failed",
                    "completed": list(dict.fromkeys([*[item["stage"] for item in stage_results if item["returnCode"] == 0], *(["validation_repair"] if validation["ready"] else [])])),
                    "planned": ["schema", "faker", "validation_repair"],
                },
            }
        )
        if completed.returncode != 0:
            job["error"] = f"codex exec failed with exit code {completed.returncode}"
        elif not validation["ready"]:
            job["error"] = "codex exec finished but required draft outputs are missing or invalid"
    except Exception as exc:  # pragma: no cover - defensive for manual job runtime
        stderr_path.write_text(str(exc), encoding="utf-8")
        validation = _validate_authoring_agent_outputs(request_dir)
        job = _read_agent_job(job_path)
        job.update(
            {
                "status": "failed",
                "finishedAt": datetime.now(timezone.utc).isoformat(),
                "returnCode": None,
                "outputs": validation["outputs"],
                "validation": validation,
                "error": str(exc),
            }
        )
    _write_agent_job(job_path, job)
    update_manifest_artifact(str(job.get("docId") or ""), "authoring_agent_run", job_path)
    if job.get("status") == "succeeded":
        update_manifest_artifact(str(job.get("docId") or ""), "authoring_agent_schema_draft", request_dir / "schema_draft.json")
        update_manifest_artifact(str(job.get("docId") or ""), "authoring_agent_faker_profile_draft", request_dir / "faker_profile_draft.json")
        update_manifest_artifact(str(job.get("docId") or ""), "authoring_agent_research_report", request_dir / "research_report.json")



def _request_pool_min_sizes(request_dir: Path) -> tuple[int, int]:
    request_path = request_dir / "request.json"
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_AUTHORING_AGENT_SCALAR_POOL_MIN_SIZE, DEFAULT_AUTHORING_AGENT_RECORD_POOL_MIN_SIZE
    options = request.get("options") if isinstance(request.get("options"), dict) else {}
    try:
        scalar_min = max(1, min(100, int(options.get("scalarPoolMinSize") or options.get("minPoolSize") or DEFAULT_AUTHORING_AGENT_SCALAR_POOL_MIN_SIZE)))
    except (TypeError, ValueError):
        scalar_min = DEFAULT_AUTHORING_AGENT_SCALAR_POOL_MIN_SIZE
    try:
        record_min = max(1, min(100, int(options.get("recordPoolMinSize") or DEFAULT_AUTHORING_AGENT_RECORD_POOL_MIN_SIZE)))
    except (TypeError, ValueError):
        record_min = DEFAULT_AUTHORING_AGENT_RECORD_POOL_MIN_SIZE
    return scalar_min, record_min


def _request_min_pool_size(request_dir: Path) -> int:
    """Backward-compatible scalar pool minimum accessor."""
    return _request_pool_min_sizes(request_dir)[0]


def _semantic_schema_set_leaf(root: dict[str, Any], path: list[str], value: str = "") -> None:
    cursor = root
    for part in path[:-1]:
        existing = cursor.get(part)
        if not isinstance(existing, dict):
            existing = {}
            cursor[part] = existing
        cursor = existing
    if path:
        cursor[path[-1]] = value


def _unique_semantic_path(root: dict[str, Any], anchor_id: str, label: str = "") -> list[str]:
    base = label.strip() or anchor_id.strip() or "미확인"
    safe = _safe_name(base) or "미확인"
    # Keep Korean-facing root stable while using a safe deterministic leaf token.
    candidate = ["검토필요", safe]
    leaves = {path for path, _value in _iter_semantic_leaf_values(root)}
    if "/".join(candidate) not in leaves:
        return candidate
    index = 2
    while True:
        next_candidate = ["검토필요", f"{safe}_{index}"]
        if "/".join(next_candidate) not in leaves:
            return next_candidate
        index += 1


def _ensure_use_anchor_placeholders(parsed_json: dict[str, Any], request_dir: Path) -> dict[str, Any]:
    """Guarantee draft coverage for every use anchor before contract validation.

    Agent omission is hard to control perfectly.  Rather than accepting missing
    use anchors or letting final export fail later, materialize a low-confidence
    primary semantic leaf under ``검토필요`` and a conservative faker rule.
    """

    schema = parsed_json.get("schema_draft.json") if isinstance(parsed_json.get("schema_draft.json"), dict) else None
    anchor_map = parsed_json.get("anchor_map_draft.json") if isinstance(parsed_json.get("anchor_map_draft.json"), dict) else None
    faker_profile = parsed_json.get("faker_profile_draft.json") if isinstance(parsed_json.get("faker_profile_draft.json"), dict) else None
    if not isinstance(schema, dict) or not isinstance(anchor_map, dict) or not isinstance(faker_profile, dict):
        return {"materializedUseAnchors": [], "materializedCount": 0, "removedUnmappedDeclaration": False}
    semantic_schema = schema.get("semantic_schema")
    if not isinstance(semantic_schema, dict):
        semantic_schema = {}
        schema["semantic_schema"] = semantic_schema
    fields = _schema_draft_bindings(schema)
    if not isinstance(fields, list):
        fields = []
        schema["fields"] = fields
    generators = faker_profile.get("field_generators")
    if not isinstance(generators, dict):
        generators = {}
        faker_profile["field_generators"] = generators
    anchors = _anchor_map_by_id(anchor_map)
    use_anchor_ids = [anchor_id for anchor_id, anchor in anchors.items() if str(anchor.get("status") or "").strip().lower() == "use"]
    mapped_anchor_ids = {
        str(field.get("anchor_id") or field.get("bbox_label_id") or field.get("source_detection_id") or "").strip()
        for field in fields
        if isinstance(field, dict)
    }
    changed = False
    materialized: list[str] = []
    for anchor_id in use_anchor_ids:
        if anchor_id in mapped_anchor_ids:
            continue
        anchor = anchors.get(anchor_id) or {}
        label = str(anchor.get("text") or anchor.get("suggested_schema_key") or anchor_id).strip()
        path = _unique_semantic_path(semantic_schema, anchor_id, label)
        _semantic_schema_set_leaf(semantic_schema, path, "")
        field_id = f"review_required_{_safe_name(anchor_id) or len(fields) + 1}"
        existing_ids = {str(field.get("field_id") or "") for field in fields if isinstance(field, dict)}
        suffix = 2
        base_field_id = field_id
        while field_id in existing_ids:
            field_id = f"{base_field_id}_{suffix}"
            suffix += 1
        fields.append(
            {
                "field_id": field_id,
                "key": path[-1],
                "label": label or path[-1],
                "semantic_path": path,
                "anchor_id": anchor_id,
                "value": "",
                "value_type": "free_text.short",
                "faker_rule": "free_text.short",
                "review_required": True,
                "confidence": 0.05,
                "notes": "자동 보강: agent가 use bbox를 매핑하지 않아 검토필요 primary leaf로 연결함",
            }
        )
        generators[field_id] = "free_text.short"
        materialized.append(anchor_id)
        changed = True
    removed_unmapped_declaration = schema.pop("unmapped_use_anchors", None) is not None
    if removed_unmapped_declaration:
        changed = True
    if changed:
        (request_dir / "schema_draft.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (request_dir / "faker_profile_draft.json").write_text(json.dumps(faker_profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "materializedUseAnchors": materialized,
        "materializedCount": len(materialized),
        "removedUnmappedDeclaration": removed_unmapped_declaration,
    }


def _authoring_bundle_consistency(schema: dict[str, Any], faker_profile: dict[str, Any], *, strict_review_coverage: bool = True, min_pool_size: int = 1) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    semantic_schema = schema.get("semantic_schema") if isinstance(schema.get("semantic_schema"), dict) else {}
    semantic_leaf_paths = {path for path, value in _iter_semantic_leaf_values(semantic_schema) if path}
    if not semantic_leaf_paths:
        errors.append({"code": "authoring_missing_semantic_schema", "message": "primary semantic_schema must contain at least one KIE leaf"})
    fields = schema.get("fields") if isinstance(schema.get("fields"), list) else []
    field_ids: set[str] = set()
    exported_paths: list[str] = []
    bbox_ids: set[str] = set()
    for index, field in enumerate(fields):
        if not isinstance(field, dict):
            errors.append({"code": "authoring_field_not_object", "index": index})
            continue
        field_id = str(field.get("field_id") or "").strip()
        if not field_id:
            errors.append({"code": "authoring_field_missing_id", "index": index})
            continue
        if field_id in field_ids:
            errors.append({"code": "authoring_duplicate_field_id", "field": field_id})
        field_ids.add(field_id)
        bbox_id = str(field.get("bbox_label_id") or field.get("source_detection_id") or "").strip()
        if bbox_id:
            bbox_ids.add(bbox_id)
        if _binding_export_enabled(field):
            path = _binding_semantic_path(field)
            if not path:
                errors.append({"code": "authoring_field_missing_semantic_path", "field": field_id})
            elif semantic_leaf_paths and path not in semantic_leaf_paths:
                errors.append({"code": "authoring_field_semantic_path_missing", "field": field_id, "semantic_path": path})
            exported_paths.append(path)
    duplicates = sorted({path for path in exported_paths if path and exported_paths.count(path) > 1})
    for path in duplicates:
        errors.append({"code": "authoring_duplicate_semantic_path", "semantic_path": path})
    unmapped_leaves = sorted(semantic_leaf_paths - {path for path in exported_paths if path})
    for path in unmapped_leaves[:30]:
        errors.append({"code": "authoring_semantic_leaf_unmapped", "semantic_path": path})
    errors.extend(_validate_faker_profile_contract(faker_profile, fields, min_pool_size=min_pool_size))
    if strict_review_coverage:
        bbox_source = schema.get("bbox_source") if isinstance(schema.get("bbox_source"), dict) else {}
        review_value = str(schema.get("source_review") or bbox_source.get("review_path") or "")
        if review_value:
            try:
                policy = load_review_policy(_resolve_workspace_path(review_value))
                use_ids = {label.id for label in policy.labels if label.status == "use"}
                missing = sorted(use_ids - bbox_ids)
                if missing:
                    errors.append({"code": "authoring_unmapped_use_bboxes", "anchor_ids": missing[:30], "count": len(missing), "message": "all use bbox labels must have authoring fields"})
            except Exception as exc:
                warnings.append({"code": "authoring_review_coverage_skipped", "message": str(exc)})
    return {"ready": not errors, "errors": errors, "warnings": warnings, "summary": {"errorCount": len(errors), "warningCount": len(warnings), "fieldCount": len(field_ids), "semanticLeafCount": len(semantic_leaf_paths)}}


def _raise_if_authoring_inconsistent(schema: dict[str, Any], faker_profile: dict[str, Any], *, strict_review_coverage: bool = True) -> dict[str, Any]:
    validation = _authoring_bundle_consistency(schema, faker_profile, strict_review_coverage=strict_review_coverage)
    if validation["errors"]:
        first = validation["errors"][0]
        raise ValueError(f"authoring consistency validation failed: {first.get('code')} ({validation['summary']['errorCount']} errors)")
    return validation

def _validate_authoring_agent_outputs(request_dir: Path) -> dict[str, Any]:
    outputs: dict[str, str] = {}
    missing: list[str] = []
    invalid_json: list[dict[str, str]] = []
    parsed_json: dict[str, Any] = {}
    for name in AUTHORING_AGENT_REQUIRED_OUTPUTS:
        path = request_dir / name
        if not path.exists():
            missing.append(name)
            continue
        outputs[name] = _display_path(path, ROOT)
        if name in AUTHORING_AGENT_JSON_OUTPUTS:
            try:
                parsed_json[name] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                invalid_json.append({"name": name, "error": str(exc)})
    contract_errors: list[dict[str, Any]] = []
    min_pool_size, min_record_pool_size = _request_pool_min_sizes(request_dir)
    repair_summary = {"materializedUseAnchors": [], "materializedCount": 0, "removedUnmappedDeclaration": False}
    if not invalid_json:
        repair_summary = _ensure_use_anchor_placeholders(parsed_json, request_dir)
        contract_errors.extend(
            _validate_schema_draft_contract(
                parsed_json,
                min_pool_size=min_pool_size,
                min_record_pool_size=min_record_pool_size,
            )
        )
        contract_errors.extend(_validate_blank_template_agent_contract(request_dir, parsed_json))
    return {
        "ready": not missing and not invalid_json and not contract_errors,
        "missing": missing,
        "invalidJson": invalid_json,
        "contractErrors": contract_errors,
        "outputs": outputs,
        "repairSummary": repair_summary,
        "summary": {
            "required": len(AUTHORING_AGENT_REQUIRED_OUTPUTS),
            "present": len(outputs),
            "missing": len(missing),
            "invalidJson": len(invalid_json),
            "contractErrors": len(contract_errors),
        },
    }


def _validate_schema_draft_contract(
    parsed_json: dict[str, Any],
    *,
    min_pool_size: int = 1,
    min_record_pool_size: int = 1,
) -> list[dict[str, Any]]:
    schema = parsed_json.get("schema_draft.json") if isinstance(parsed_json.get("schema_draft.json"), dict) else {}
    anchor_map = parsed_json.get("anchor_map_draft.json") if isinstance(parsed_json.get("anchor_map_draft.json"), dict) else {}
    faker_profile = parsed_json.get("faker_profile_draft.json") if isinstance(parsed_json.get("faker_profile_draft.json"), dict) else {}
    research_report = parsed_json.get("research_report.json") if isinstance(parsed_json.get("research_report.json"), dict) else {}
    errors: list[dict[str, Any]] = []
    semantic_leaf_paths: set[str] = set()
    semantic_schema = schema.get("semantic_schema")
    if not isinstance(semantic_schema, dict):
        errors.append({"code": "schema_missing_semantic_schema", "message": "schema_draft.json must include metadata-free semantic_schema object"})
    else:
        for path, value in _iter_semantic_leaf_values(semantic_schema):
            if path:
                semantic_leaf_paths.add(path)
            if value != "":
                errors.append({"code": "schema_semantic_value_not_empty", "path": path, "message": "semantic_schema leaf values must be empty strings"})
        if not semantic_leaf_paths:
            errors.append({"code": "schema_empty_semantic_schema", "message": "semantic_schema must contain at least one KIE leaf"})
    fields = _schema_draft_bindings(schema)
    if not isinstance(fields, list):
        errors.append({"code": "schema_fields_missing", "message": "schema_draft.json must include fields or field_bindings binding list"})
        return errors
    anchors = _anchor_map_by_id(anchor_map)
    mapped_anchor_ids: set[str] = set()
    research_source_ids = _research_source_ids(research_report)
    for field in fields:
        if not isinstance(field, dict):
            continue
        field_id = str(field.get("field_id") or field.get("key") or field.get("label") or "")
        if "value" in field and field.get("value") != "":
            errors.append({"code": "schema_field_value_not_empty", "field": field_id, "message": "schema_draft.fields[].value must remain an empty string"})
        semantic_path = _binding_semantic_path(field)
        export_only_render = not _binding_export_enabled(field)
        if not semantic_path and not export_only_render:
            errors.append({"code": "schema_field_missing_semantic_path", "field": field_id, "message": "schema binding must define semantic_path/key/json_path"})
        elif semantic_leaf_paths and semantic_path not in semantic_leaf_paths and not export_only_render:
            errors.append({"code": "schema_field_semantic_path_missing", "field": field_id, "semantic_path": semantic_path, "message": "binding semantic_path must point to an existing semantic_schema leaf"})
        anchor_id = str(field.get("anchor_id") or field.get("bbox_label_id") or field.get("source_detection_id") or "").strip()
        if not anchor_id:
            errors.append({"code": "schema_field_missing_anchor", "field": field_id, "message": "schema binding must define anchor_id"})
        elif anchors:
            anchor = anchors.get(anchor_id)
            if anchor is None:
                errors.append({"code": "schema_field_anchor_missing", "field": field_id, "anchor_id": anchor_id, "message": "binding anchor_id must exist in anchor_map_draft"})
            else:
                mapped_anchor_ids.add(anchor_id)
                status = str(anchor.get("status") or "").strip().lower()
                role = str(anchor.get("role") or anchor.get("anchor_role") or "").strip().lower()
                if status and status != "use":
                    errors.append({"code": "schema_field_anchor_not_use", "field": field_id, "anchor_id": anchor_id, "status": status, "message": "binding anchor_id must target a use value anchor"})
                if role and role in {"static_label", "label", "keep"}:
                    errors.append({"code": "schema_field_anchor_is_label", "field": field_id, "anchor_id": anchor_id, "role": role, "message": "label/static anchors must be label_anchor_ids, not field targets"})
        for evidence_id in _binding_research_evidence_ids(field):
            if research_source_ids and evidence_id not in research_source_ids:
                errors.append({"code": "schema_field_unknown_research_evidence", "field": field_id, "research_evidence_id": evidence_id, "message": "research_evidence_ids must refer to research_report.sources[].id"})
    errors.extend(
        _validate_faker_profile_contract(
            faker_profile,
            fields,
            min_pool_size=min_pool_size,
            min_record_pool_size=min_record_pool_size,
        )
    )
    if anchors:
        use_anchor_ids = {anchor_id for anchor_id, anchor in anchors.items() if str(anchor.get("status") or "").strip().lower() == "use"}
        prohibited_unmapped = _unmapped_use_anchor_ids(schema)
        if prohibited_unmapped:
            errors.append({"code": "schema_unmapped_use_anchors_prohibited", "anchor_ids": sorted(prohibited_unmapped)[:20], "count": len(prohibited_unmapped), "message": "unmapped_use_anchors is prohibited; create 검토필요 bindings instead"})
        unmapped = sorted(use_anchor_ids - mapped_anchor_ids)
        if unmapped:
            errors.append({"code": "schema_unmapped_use_anchors", "anchor_ids": unmapped[:20], "count": len(unmapped), "message": "every use anchor must be mapped; create 검토필요 bindings when uncertain"})
    return errors


def _schema_draft_bindings(schema: dict[str, Any]) -> list[Any] | None:
    if isinstance(schema.get("fields"), list):
        return schema.get("fields")
    if isinstance(schema.get("field_bindings"), list):
        return schema.get("field_bindings")
    return None


def _binding_semantic_path(field: dict[str, Any]) -> str:
    raw_path = field.get("semantic_path") or field.get("key_path")
    if isinstance(raw_path, list):
        return "/".join(str(part).strip() for part in raw_path if str(part).strip())
    for key in ("semantic_path", "json_path", "key"):
        value = field.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().replace(".", "/") if "/" not in value and "." in value else value.strip()
    export = field.get("export") if isinstance(field.get("export"), dict) else {}
    value = export.get("json_path")
    if isinstance(value, str) and value.strip():
        return value.strip()
    label = str(field.get("label") or "").strip()
    return label


def _binding_export_enabled(field: dict[str, Any]) -> bool:
    export = field.get("export") if isinstance(field.get("export"), dict) else {}
    value = export.get("include") if "include" in export else field.get("export_include") if "export_include" in field else True
    return str(value).strip().lower() not in {"false", "0", "no", "off", "skip", "hidden"}


def _anchor_map_by_id(anchor_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    anchors: dict[str, dict[str, Any]] = {}
    for anchor in anchor_map.get("anchors", []) if isinstance(anchor_map.get("anchors"), list) else []:
        if not isinstance(anchor, dict):
            continue
        anchor_id = str(anchor.get("anchor_id") or anchor.get("id") or "").strip()
        if anchor_id:
            anchors[anchor_id] = anchor
    return anchors


def _research_source_ids(research_report: dict[str, Any]) -> set[str]:
    return {
        str(source.get("id")).strip()
        for source in research_report.get("sources", [])
        if isinstance(source, dict) and str(source.get("id") or "").strip()
    }


def _binding_research_evidence_ids(field: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for key in ("research_evidence_ids", "source_ids"):
        if isinstance(field.get(key), list):
            values.extend(field.get(key) or [])
    evidence = field.get("evidence") if isinstance(field.get("evidence"), dict) else {}
    for key in ("research_evidence_ids", "source_ids"):
        if isinstance(evidence.get(key), list):
            values.extend(evidence.get(key) or [])
    return [str(value).strip() for value in values if str(value).strip()]


def _validate_faker_profile_contract(
    faker_profile: dict[str, Any],
    fields: list[Any],
    *,
    min_pool_size: int = 1,
    min_record_pool_size: int = 1,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    generators = faker_profile.get("field_generators")
    if not isinstance(generators, dict):
        errors.append({"code": "faker_missing_field_generators", "message": "faker_profile_draft.json must include field_generators object"})
        return errors
    field_ids = {str(field.get("field_id") or "").strip() for field in fields if isinstance(field, dict) and str(field.get("field_id") or "").strip()}
    for field_id in sorted(field_ids - {str(key) for key in generators.keys()}):
        errors.append({"code": "faker_missing_field_generator", "field": field_id, "message": "every schema binding field_id must have a field_generators rule"})
    for field_id, rule_value in generators.items():
        rule = str(rule_value or "").strip()
        if field_ids and str(field_id) not in field_ids:
            errors.append({"code": "faker_unknown_field", "field": str(field_id), "message": "field_generators key must match a schema binding field_id"})
        if not _faker_rule_supported(rule):
            errors.append({"code": "faker_unsupported_rule", "field": str(field_id), "rule": rule, "message": "faker rule is outside renderer-supported grammar"})
        if rule.lower().startswith("pool:"):
            pool_name = rule.split(":", 1)[1].strip()
            pool = _faker_pool_values(faker_profile, pool_name)
            if not pool:
                errors.append({"code": "faker_missing_pool", "field": str(field_id), "pool": pool_name, "message": "pool rule must define data_pools.<name> with scalar values"})
            elif len(pool) < max(1, min_pool_size) and not _faker_pool_is_closed_set(faker_profile, pool_name):
                errors.append({"code": "faker_pool_too_small", "field": str(field_id), "pool": pool_name, "count": len(pool), "min": max(1, min_pool_size), "message": "pool rule must meet the configured minimum scalar value count"})
    errors.extend(_validate_faker_constraints_contract(faker_profile, field_ids, min_record_pool_size=min_record_pool_size))
    return errors


def _validate_faker_constraints_contract(
    faker_profile: dict[str, Any],
    field_ids: set[str],
    *,
    min_record_pool_size: int = 1,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    constraints = faker_profile.get("constraints")
    if constraints is None:
        return errors
    if not isinstance(constraints, list):
        return [{"code": "faker_constraints_not_list", "message": "faker_profile_draft.json.constraints must be a list when present"}]
    supported = {"pick_record", "copy", "exclusive_choice", "primary_secondary_group", "date_group", "date_order", "date_not_before", "date_not_after", "sum", "numeric_range", "numeric_compare", "age_from_rrn"}
    for index, constraint in enumerate(constraints):
        if not isinstance(constraint, dict):
            errors.append({"code": "faker_constraint_not_object", "index": index, "message": "each constraint must be an object"})
            continue
        ctype = str(constraint.get("type") or "").strip().lower()
        if ctype not in supported:
            errors.append({"code": "faker_constraint_unsupported_type", "index": index, "type": ctype, "message": "constraint type is not supported by renderer"})
            continue
        if ctype == "pick_record":
            pool_name = str(constraint.get("pool") or "").strip()
            targets = constraint.get("targets")
            if not pool_name or not isinstance(targets, dict) or not targets:
                errors.append({"code": "faker_constraint_invalid_pick_record", "index": index, "message": "pick_record requires pool and non-empty targets mapping"})
                continue
            records = [item for item in _faker_pool_raw_values(faker_profile, pool_name) if isinstance(item, dict)]
            if not records:
                errors.append({"code": "faker_constraint_missing_record_pool", "index": index, "pool": pool_name, "message": "pick_record requires data_pools.<pool> object records"})
            elif len(records) < max(1, min_record_pool_size):
                errors.append({"code": "faker_record_pool_too_small", "index": index, "pool": pool_name, "count": len(records), "min": max(1, min_record_pool_size), "message": "pick_record pool must meet the configured minimum record count"})
            _validate_constraint_field_refs(errors, index, field_ids, targets.keys())
        elif ctype == "copy":
            _validate_constraint_field_refs(errors, index, field_ids, [constraint.get("source"), constraint.get("target")])
        elif ctype == "exclusive_choice":
            targets = _constraint_ref_list(constraint.get("targets"))
            if len(targets) < 2:
                errors.append({"code": "faker_constraint_invalid_exclusive_choice", "index": index, "message": "exclusive_choice requires at least two targets"})
            _validate_constraint_field_refs(errors, index, field_ids, targets)
        elif ctype == "primary_secondary_group":
            rows = constraint.get("rows")
            refs: list[Any] = []
            if not isinstance(rows, list) or not rows:
                errors.append({"code": "faker_constraint_invalid_primary_secondary_group", "index": index, "message": "primary_secondary_group requires non-empty rows"})
            else:
                for row in rows:
                    if not isinstance(row, dict) or not str(row.get("primary") or "").strip() or not str(row.get("secondary") or "").strip():
                        errors.append({"code": "faker_constraint_invalid_primary_secondary_group", "index": index, "message": "each primary_secondary_group row requires primary and secondary"})
                        continue
                    refs.extend([row.get("primary"), row.get("secondary")])
            _validate_constraint_field_refs(errors, index, field_ids, refs)
        elif ctype == "date_group":
            refs = [constraint.get("year"), constraint.get("month"), constraint.get("day")]
            if not all(str(ref or "").strip() for ref in refs):
                errors.append({"code": "faker_constraint_invalid_date_group", "index": index, "message": "date_group requires year/month/day"})
            _validate_constraint_field_refs(errors, index, field_ids, refs)
        elif ctype == "date_order":
            refs: list[Any] = []
            for key in ("start", "end"):
                group = constraint.get(key)
                if not _constraint_date_ref_complete(group):
                    errors.append({"code": "faker_constraint_invalid_date_order", "index": index, "message": "date_order requires start/end date fields or complete year/month/day groups"})
                refs.extend(_constraint_date_ref_fields(group))
            _validate_constraint_field_refs(errors, index, field_ids, refs)
        elif ctype == "date_not_before":
            refs: list[Any] = []
            source = constraint.get("source") or constraint.get("after")
            target = constraint.get("target") or constraint.get("date")
            if not _constraint_date_ref_complete(source):
                errors.append({"code": f"faker_constraint_invalid_{ctype}", "index": index, "message": f"{ctype} requires source date field or complete source date group"})
            refs.extend(_constraint_date_ref_fields(source))
            if not _constraint_date_ref_complete(target):
                errors.append({"code": f"faker_constraint_invalid_{ctype}", "index": index, "message": f"{ctype} requires target date field or complete target date group"})
            refs.extend(_constraint_date_ref_fields(target))
            _validate_constraint_field_refs(errors, index, field_ids, refs)
        elif ctype == "date_not_after":
            target = constraint.get("target") or constraint.get("date")
            maximum = constraint.get("max") or constraint.get("not_after") or "as_of_date"
            refs: list[Any] = []
            if not _constraint_date_ref_complete(target):
                errors.append({"code": "faker_constraint_invalid_date_not_after", "index": index, "message": "date_not_after requires target date field or complete target date group"})
            refs.extend(_constraint_date_ref_fields(target))
            if str(maximum).strip().lower() not in {"as_of_date", "today"}:
                if not _constraint_date_ref_complete(maximum):
                    errors.append({"code": "faker_constraint_invalid_date_not_after", "index": index, "message": "date_not_after max must be as_of_date or a date field/group"})
                refs.extend(_constraint_date_ref_fields(maximum))
            _validate_constraint_field_refs(errors, index, field_ids, refs)
        elif ctype == "sum":
            sources = _constraint_ref_list(constraint.get("sources"))
            target = str(constraint.get("target") or "").strip()
            if not sources or not target:
                errors.append({"code": "faker_constraint_invalid_sum", "index": index, "message": "sum requires sources and target"})
            _validate_constraint_field_refs(errors, index, field_ids, [*sources, target])
        elif ctype == "numeric_range":
            target = str(constraint.get("target") or "").strip()
            minimum = constraint.get("min")
            maximum = constraint.get("max")
            if not target or not isinstance(minimum, (int, float)) or not isinstance(maximum, (int, float)) or float(minimum) > float(maximum):
                errors.append({"code": "faker_constraint_invalid_numeric_range", "index": index, "message": "numeric_range requires target and numeric min <= max"})
            _validate_constraint_field_refs(errors, index, field_ids, [target])
        elif ctype == "numeric_compare":
            left = str(constraint.get("left") or "").strip()
            right = str(constraint.get("right") or "").strip()
            operator = str(constraint.get("operator") or "").strip()
            if not left or not right or operator not in {"<", "<=", ">", ">=", "lt", "lte", "gt", "gte"}:
                errors.append({"code": "faker_constraint_invalid_numeric_compare", "index": index, "message": "numeric_compare requires left/right and a supported comparison operator"})
            _validate_constraint_field_refs(errors, index, field_ids, [left, right])
        elif ctype == "age_from_rrn":
            refs = [constraint.get("rrn"), constraint.get("age")]
            issue = constraint.get("issue")
            if not all(str(ref or "").strip() for ref in refs):
                errors.append({"code": "faker_constraint_invalid_age_from_rrn", "index": index, "message": "age_from_rrn requires rrn and age field refs"})
            if not isinstance(issue, dict) or not all(str(issue.get(part) or "").strip() for part in ("year", "month", "day")):
                errors.append({"code": "faker_constraint_invalid_age_from_rrn", "index": index, "message": "age_from_rrn requires complete issue year/month/day group"})
            if isinstance(issue, dict):
                refs.extend(issue.get(part) for part in ("year", "month", "day"))
            _validate_constraint_field_refs(errors, index, field_ids, refs)
    return errors


def _constraint_ref_list(value: Any) -> list[str]:
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _constraint_date_ref_complete(value: Any) -> bool:
    if isinstance(value, dict):
        return all(str(value.get(part) or "").strip() for part in ("year", "month", "day"))
    return bool(str(value or "").strip())


def _constraint_date_ref_fields(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return [value.get(part) for part in ("year", "month", "day")]
    return [value]


def _validate_constraint_field_refs(errors: list[dict[str, Any]], index: int, field_ids: set[str], refs: Any) -> None:
    for ref in refs:
        field_id = str(ref or "").strip()
        if field_id and field_ids and field_id not in field_ids:
            errors.append({"code": "faker_constraint_unknown_field", "index": index, "field": field_id, "message": "constraint field reference must match schema binding field_id"})


def _faker_pool_raw_values(faker_profile: dict[str, Any], pool_name: str) -> list[Any]:
    pools = faker_profile.get("data_pools")
    if isinstance(pools, dict):
        value = pools.get(pool_name)
        return value if isinstance(value, list) else []
    if isinstance(pools, list):
        for item in pools:
            if isinstance(item, dict) and str(item.get("name") or "") == pool_name and isinstance(item.get("values"), list):
                return item.get("values") or []
    return []


def _faker_pool_is_closed_set(faker_profile: dict[str, Any], pool_name: str) -> bool:
    policies = faker_profile.get("pool_policies")
    if not isinstance(policies, dict):
        return False
    policy = policies.get(pool_name)
    return (
        isinstance(policy, dict)
        and policy.get("closed_set") is True
        and str(policy.get("exception_kind") or "").strip() == "legal_or_form_closed_set"
        and bool(str(policy.get("evidence") or "").strip())
    )


def _faker_rule_supported(rule: str) -> bool:
    normalized = str(rule or "").strip()
    lower = normalized.lower()
    if not normalized:
        return False
    if lower.startswith(("literal:", "choice:", "pool:", "same_as:", "pattern:", "template:")):
        return True
    return lower in {
        "person.name_ko",
        "person.phone_kr",
        "person.rrn",
        "date.kr",
        "date.year",
        "date.month",
        "date.day",
        "money.krw",
        "business_reg_no",
        "company.name_ko",
        "medical.institution_ko",
        "address.ko",
        "free_text.short",
        "checkbox.bool",
        "bool.checkbox",
    }


def _faker_pool_values(faker_profile: dict[str, Any], pool_name: str) -> list[Any]:
    pools = faker_profile.get("data_pools")
    if isinstance(pools, dict):
        value = pools.get(pool_name)
        return [item for item in value if not isinstance(item, dict) and str(item).strip()] if isinstance(value, list) else []
    if isinstance(pools, list):
        for item in pools:
            if isinstance(item, dict) and str(item.get("name") or "") == pool_name and isinstance(item.get("values"), list):
                return [value for value in item.get("values", []) if not isinstance(value, dict) and str(value).strip()]
    return []


def _unmapped_use_anchor_ids(schema: dict[str, Any]) -> set[str]:
    items = schema.get("unmapped_use_anchors")
    if not isinstance(items, list):
        return set()
    anchor_ids: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            anchor_id = str(item.get("anchor_id") or item.get("id") or "").strip()
        else:
            anchor_id = str(item or "").strip()
        if anchor_id:
            anchor_ids.add(anchor_id)
    return anchor_ids


def _iter_semantic_leaf_values(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        leaves: list[tuple[str, Any]] = []
        for key, child in value.items():
            child_prefix = f"{prefix}/{key}" if prefix else str(key)
            leaves.extend(_iter_semantic_leaf_values(child, child_prefix))
        return leaves
    if isinstance(value, list):
        leaves = []
        for index, child in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            leaves.extend(_iter_semantic_leaf_values(child, child_prefix))
        return leaves
    return [(prefix, value)]


def _validate_blank_template_agent_contract(request_dir: Path, parsed_json: dict[str, Any]) -> list[dict[str, str]]:
    request_path = request_dir / "request.json"
    if not request_path.exists():
        return []
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    sample_kind = str((request.get("inputs") or {}).get("sampleKind") or (request.get("contract") or {}).get("sample_kind") or "filled_sample")
    if sample_kind != "blank_template":
        return []
    schema = parsed_json.get("schema_draft.json") if isinstance(parsed_json.get("schema_draft.json"), dict) else {}
    anchor_map = parsed_json.get("anchor_map_draft.json") if isinstance(parsed_json.get("anchor_map_draft.json"), dict) else {}
    anchors = {
        str(anchor.get("anchor_id") or anchor.get("id") or ""): anchor
        for anchor in anchor_map.get("anchors", [])
        if isinstance(anchor, dict) and str(anchor.get("anchor_id") or anchor.get("id") or "")
    }
    errors: list[dict[str, str]] = []
    value_anchor_ids = {anchor_id for anchor_id, anchor in anchors.items() if _blank_template_anchor_is_value_target(anchor)}
    if not value_anchor_ids:
        errors.append({"code": "blank_template_no_value_anchors", "message": "blank_template requires at least one value-region/use/manual/visual-line-detect anchor"})
    seen_targets: dict[str, list[tuple[str, bool]]] = {}
    fields = _schema_draft_bindings(schema) or []
    for field in fields:
        if not isinstance(field, dict):
            continue
        field_id = str(field.get("field_id") or field.get("key") or field.get("label") or "")
        anchor_id = str(field.get("anchor_id") or field.get("bbox_label_id") or field.get("source_detection_id") or "")
        if not anchor_id:
            errors.append({"code": "blank_template_field_without_anchor", "field": field_id, "message": "blank_template field must define a value target anchor_id"})
            continue
        anchor = anchors.get(anchor_id)
        if anchor is None:
            errors.append({"code": "blank_template_missing_anchor", "field": field_id, "anchor_id": anchor_id, "message": "field anchor_id is not present in anchor_map_draft"})
            continue
        if not _blank_template_anchor_is_value_target(anchor):
            errors.append({"code": "blank_template_static_label_as_field_anchor", "field": field_id, "anchor_id": anchor_id, "message": "static label/keep anchor cannot be used as schema field target"})
        render_policy = field.get("render_policy") if isinstance(field.get("render_policy"), dict) else {}
        seen_targets.setdefault(anchor_id, []).append((field_id, render_policy.get("render") is not False))
    for anchor_id, target_fields in seen_targets.items():
        rendered_fields = [field_id for field_id, rendered in target_fields if rendered]
        if len(rendered_fields) > 1:
            for field_id in rendered_fields[1:]:
                errors.append({"code": "blank_template_duplicate_field_anchor", "field": field_id, "anchor_id": anchor_id, "message": f"anchor already has rendered field {rendered_fields[0]}"})
    return errors


def _blank_template_anchor_is_value_target(anchor: dict[str, Any]) -> bool:
    status = str(anchor.get("status") or "").lower()
    role = str(anchor.get("role") or anchor.get("anchor_role") or "").lower()
    auto_type = str(anchor.get("auto_type") or anchor.get("type") or "").lower()
    source = str(anchor.get("source") or anchor.get("text_source") or "").lower()
    provenance = anchor.get("provenance")
    provenance_text = json.dumps(provenance, ensure_ascii=False).lower() if isinstance(provenance, (dict, list)) else str(provenance or "").lower()
    if status in {"keep", "ignore"} or role in {"static_label", "label", "header", "instruction_text"} or auto_type in {"static_label", "header_footer", "long_paragraph"}:
        return False
    if status != "use":
        return False
    if role in {"value", "value_region", "field_target", "input", "checkbox"}:
        return True
    return any(token in f"{role} {auto_type} {source} {provenance_text}" for token in ("value", "checkbox", "table_cell", "manual", "visual_line_detect", "opencv_grid", "grid"))



def _payload_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _visual_line_detection_requested(payload: dict[str, Any]) -> bool:
    return _payload_bool(payload.get("includeVisualLineDetection"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ocr_detection_result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    image_path = _resolve_workspace_path(str(payload.get("imagePath") or ""))
    engine = str(payload.get("engine") or "paddleocr")
    if engine not in {"paddleocr", "projection", "doctr"}:
        raise ValueError("engine must be one of paddleocr, projection, doctr")
    preset = normalize_paddleocr_preset(str(payload.get("preset") or "precise")) if engine == "paddleocr" else ""
    doc_id = str(payload.get("docId") or "")
    default_out_dir = workbench_subdir(doc_id, "ocr") if doc_id else Path("outputs/ocr_eval")
    out_dir = _resolve_workspace_path(str(payload.get("outDir") or default_out_dir))
    started_at = perf_counter()
    print(f"Starting OCR detection engine={engine} preset={preset or '-'} image={image_path}", flush=True)
    payload_result = _run_paddle_ocr_subprocess(image_path, preset=preset, out_dir=out_dir) if engine == "paddleocr" else run_ocr_eval(image_path, engine=engine, preset=preset, out_dir=out_dir)
    elapsed_seconds = perf_counter() - started_at
    summary = dict(payload_result["summary"])
    paths = {name: Path(path) for name, path in dict(payload_result["paths"]).items()}
    summary["elapsed_seconds"] = elapsed_seconds
    if doc_id:
        update_manifest_artifact(doc_id, "ocr", paths["detections"])
    print(f"Finished OCR detection engine={engine} preset={preset or '-'} count={summary['detection_count']} elapsed={elapsed_seconds:.2f}s", flush=True)
    return {
        "docId": doc_id or None,
        "summary": {
            "engine": summary["engine"],
            "preset": summary.get("preset"),
            "source_image": _display_path(summary["source_image"], ROOT),
            "image": summary["image"],
            "detection_count": summary["detection_count"],
            "elapsed_seconds": summary["elapsed_seconds"],
        },
        "paths": _paths_to_client(paths),
        "overlayUrl": f"/api/file?path={_display_path(paths['overlay'], ROOT)}",
    }


def _ocr_job_path_from_payload(payload: dict[str, Any]) -> Path:
    job_path_value = str(payload.get("jobPath") or "")
    if job_path_value:
        return _resolve_workspace_path(job_path_value)
    doc_id = str(payload.get("docId") or "")
    if not doc_id:
        raise ValueError("jobPath or docId is required")
    job_root = workbench_subdir(doc_id, "ocr") / "jobs"
    job_paths = sorted(job_root.glob("*/job.json")) if job_root.exists() else []
    if not job_paths:
        raise FileNotFoundError(f"no OCR detection job for {doc_id}")
    return job_paths[-1]


def ocr_detection_status_payload(payload: dict[str, Any]) -> dict[str, Any]:
    job_path = _ocr_job_path_from_payload(payload)
    return _agent_job_payload(job_path)


def ocr_detection_start_payload(payload: dict[str, Any], *, async_run: bool = True) -> dict[str, Any]:
    doc_id = str(payload.get("docId") or "")
    if not doc_id:
        raise ValueError("docId is required")
    image_path = _resolve_workspace_path(str(payload.get("imagePath") or ""))
    engine = str(payload.get("engine") or "paddleocr")
    preset = normalize_paddleocr_preset(str(payload.get("preset") or "precise")) if engine == "paddleocr" else ""
    run_dir = workbench_subdir(doc_id, "ocr") / "jobs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    job_path = run_dir / "job.json"
    job = {
        "schema_version": 1,
        "jobType": "ocr_detection",
        "jobId": run_dir.name,
        "docId": doc_id,
        "status": "queued",
        "createdAt": _utc_now(),
        "startedAt": None,
        "finishedAt": None,
        "engine": engine,
        "preset": preset or None,
        "imagePath": _display_path(image_path, ROOT),
        "request": {**payload, "imagePath": _display_path(image_path, ROOT)},
        "result": None,
        "error": None,
    }
    _write_agent_job(job_path, job)
    update_manifest_artifact(doc_id, "ocr_detection_job", job_path)
    if async_run:
        thread = threading.Thread(target=_run_ocr_detection_job, args=(job_path,), daemon=True)
        thread.start()
        return _agent_job_payload(job_path)
    _run_ocr_detection_job(job_path)
    return _agent_job_payload(job_path)


def _run_ocr_detection_job(job_path: Path) -> None:
    job = _read_agent_job(job_path)
    job["status"] = "running"
    job["startedAt"] = _utc_now()
    _write_agent_job(job_path, job)
    try:
        result = _ocr_detection_result_payload(dict(job.get("request") or {}))
        job = _read_agent_job(job_path)
        job["status"] = "completed"
        job["finishedAt"] = _utc_now()
        job["result"] = result
        job["summary"] = result.get("summary")
        job["paths"] = result.get("paths")
        job["error"] = None
    except Exception as exc:  # pragma: no cover - defensive for manual OCR runtime
        job = _read_agent_job(job_path)
        job["status"] = "failed"
        job["finishedAt"] = _utc_now()
        job["error"] = str(exc)
    _write_agent_job(job_path, job)


def _read_agent_job(job_path: Path) -> dict[str, Any]:
    return json.loads(job_path.read_text(encoding="utf-8"))


def _write_agent_job(job_path: Path, job: dict[str, Any]) -> None:
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _agent_job_payload(job_path: Path) -> dict[str, Any]:
    job = _read_agent_job(job_path)
    return {**job, "jobPath": _display_path(job_path, ROOT)}


def _clear_manifest_artifacts(doc_id: str, artifact_keys: list[str]) -> None:
    registry = load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        return
    manifest_path = document_dir(doc, ROOT / "workbench" / "documents") / "manifest.json"
    if not manifest_path.exists():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return
    for key in artifact_keys:
        artifacts.pop(key, None)
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_review_sidecar_drafts(doc_id: str, review_path: Path, policy: ReviewPolicy) -> dict[str, Any]:
    authoring_dir = workbench_subdir(doc_id, "authoring")
    draft_dir = authoring_dir / "review_sidecars" / _safe_template_id(policy.source_image)
    stylesheet_path = draft_dir / "stylesheet_draft_from_review.json"
    anchor_map_path = draft_dir / "anchor_map_draft.json"
    stylesheet = draft_stylesheet_from_review(review_path, out_path=stylesheet_path, doc_id=doc_id)
    anchors = review_anchor_map(review_path, out_path=anchor_map_path, doc_id=doc_id)
    update_manifest_artifact(doc_id, "authoring_stylesheet_draft", stylesheet_path)
    update_manifest_artifact(doc_id, "authoring_anchor_map", anchor_map_path)
    return {
        "stylesheetDraft": _display_path(stylesheet_path, ROOT),
        "anchorMapDraft": _display_path(anchor_map_path, ROOT),
        "summary": {"styleClassCount": len(stylesheet.get("style_classes") or []), "anchorCount": len(anchors.get("anchors") or [])},
    }

def _authoring_paths_from_payload(payload: dict[str, Any], doc_id: str) -> tuple[Path, Path, Path]:
    authoring_dir = workbench_subdir(doc_id, "authoring")
    schema_path = _resolve_workspace_path(str(payload.get("schemaPath") or authoring_dir / "schema.json"))
    stylesheet_path = _resolve_workspace_path(str(payload.get("stylesheetPath") or authoring_dir / "stylesheet.json"))
    faker_profile_path = _resolve_workspace_path(str(payload.get("fakerProfilePath") or authoring_dir / "faker_profile.json"))
    return schema_path, stylesheet_path, faker_profile_path


def authoring_review_prune_candidates_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw_policy = payload.get("policy")
    if not isinstance(raw_policy, dict):
        raise ValueError("payload.policy must be an object")
    policy = ReviewPolicy.from_dict(raw_policy, base_dir=ROOT)
    doc_id = str(payload.get("docId") or "")
    if not doc_id:
        raise ValueError("docId is required")
    schema_path, _stylesheet_path, _faker_profile_path = _authoring_paths_from_payload(payload, doc_id)
    return {"docId": doc_id, **authoring_review_prune_candidates(schema_path, policy)}


def recognize_review_crops_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw_policy = payload.get("policy")
    if not isinstance(raw_policy, dict):
        raise ValueError("payload.policy must be an object")
    policy = ReviewPolicy.from_dict(raw_policy, base_dir=ROOT)
    doc_id = str(payload.get("docId") or "")
    preset = normalize_paddleocr_preset(str(payload.get("preset") or "precise"))
    padding = max(0, int(payload.get("padding") or 0))
    raw_label_ids = payload.get("labelIds")
    selected_ids = {str(item) for item in raw_label_ids if item is not None} if isinstance(raw_label_ids, list) else set()
    labels = [
        label
        for label in policy.labels
        if (label.id in selected_ids) or (not selected_ids and label.ocr_text_stale)
    ]
    if not labels:
        return {
            "summary": {"engine": "paddleocr", "preset": preset, "count": 0, "recognized": 0, "elapsed_seconds": 0.0},
            "candidates": [],
            "recUpdatedAt": datetime.now(timezone.utc).isoformat(),
        }

    image_path = _resolve_workspace_path(policy.source_image)
    out_root = workbench_subdir(doc_id, "ocr_recrop") if doc_id else Path("outputs/ocr_recrop")
    run_dir = _resolve_workspace_path(out_root) / _safe_template_id(policy.source_image) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir.mkdir(parents=True, exist_ok=True)

    crops: list[dict[str, Any]] = []
    with Image.open(image_path) as opened_image:
        image = opened_image.convert("RGB")
        for index, label in enumerate(labels, start=1):
            crop_box = label.bbox.padded(padding).clipped(policy.image_width, policy.image_height)
            crop_path = run_dir / f"crop_{index:04d}_{_safe_name(label.id)}.png"
            image.crop((crop_box.x, crop_box.y, crop_box.right, crop_box.bottom)).save(crop_path)
            crops.append(
                {
                    "id": label.id,
                    "oldText": label.text,
                    "oldConfidence": label.confidence,
                    "bbox": crop_box.to_list(),
                    "originalBbox": label.bbox.to_list(),
                    "cropPath": str(crop_path),
                }
            )

    manifest_path = run_dir / "crop_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "sourceImage": str(image_path),
                "image": {"width": policy.image_width, "height": policy.image_height},
                "padding": padding,
                "crops": crops,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run_paddle_crop_recognition_subprocess(manifest_path, preset=preset, out_dir=run_dir)
    rec_updated_at = datetime.now(timezone.utc).isoformat()
    candidates = []
    for candidate in result.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        item = dict(candidate)
        if item.get("cropPath"):
            item["cropPath"] = _display_path(item["cropPath"], ROOT)
        candidates.append(item)
    summary = dict(result.get("summary") or {})
    summary["manifest"] = _display_path(manifest_path, ROOT)
    return {"summary": summary, "candidates": candidates, "recUpdatedAt": rec_updated_at}


def load_cleanup_mask_payload(*, doc_id: str, review_path: Path) -> dict[str, Any]:
    policy = load_review_policy(review_path)
    cleanup_dir = _cleanup_dir(doc_id, policy)
    mask_payload = load_manual_mask(cleanup_dir, size=(policy.image_width, policy.image_height))
    paths: dict[str, Path] = {}
    for name, filename in {
        "mask_json": "mask.json",
        "manual_mask": "manual_mask.png",
        "mask_overlay": "mask_overlay.png",
        "inpainted": "inpainted_lama.png",
        "comparison": "comparison_lama.png",
        "summary": "summary.json",
    }.items():
        candidate = cleanup_dir / filename
        if candidate.exists():
            paths[name] = candidate
    response: dict[str, Any] = {
        "docId": doc_id,
        "reviewPath": _display_path(review_path, ROOT),
        "exists": bool(paths),
        "mask": mask_payload,
        "paths": _paths_to_client(paths),
    }
    if paths.get("manual_mask"):
        response["manualMaskUrl"] = f"/api/file?path={_display_path(paths['manual_mask'], ROOT)}"
    if paths.get("comparison"):
        response["comparisonUrl"] = f"/api/file?path={_display_path(paths['comparison'], ROOT)}"
    return response


def save_cleanup_mask_payload(payload: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(payload.get("docId") or "")
    if not doc_id:
        raise ValueError("docId is required")
    review_path = _resolve_workspace_path(str(payload.get("reviewPath") or ""))
    policy = load_review_policy(review_path)
    cleanup_dir = _cleanup_dir(doc_id, policy)
    mask_payload, paths = save_manual_mask(payload.get("mask"), directory=cleanup_dir, size=(policy.image_width, policy.image_height))
    client_paths = _paths_to_client(paths.as_dict())
    return {
        "docId": doc_id,
        "reviewPath": _display_path(review_path, ROOT),
        "mask": mask_payload,
        "paths": client_paths,
        "manualMaskUrl": f"/api/file?path={client_paths['manual_mask']}",
    }


def run_cleanup_inpaint_payload(payload: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(payload.get("docId") or "")
    if not doc_id:
        raise ValueError("docId is required")
    review_path = _resolve_workspace_path(str(payload.get("reviewPath") or ""))
    base_image_path = _resolve_workspace_path(str(payload.get("baseImagePath") or ""))
    policy = load_review_policy(review_path)
    cleanup_dir = _cleanup_dir(doc_id, policy)
    mask_payload, mask_paths = save_manual_mask(payload.get("mask"), directory=cleanup_dir, size=(policy.image_width, policy.image_height))
    lama_max_side = int(payload.get("lamaMaxSide") or 2400)
    started_at = perf_counter()
    print(f"Starting manual cleanup postprocess doc={doc_id} base={base_image_path} lama_max_side={lama_max_side}", flush=True)
    result = _inpaint_cleanup_template(
        base_image_path=base_image_path,
        mask_path=mask_paths.manual_mask,
        detections_path=mask_paths.mask_json,
        lama_max_side=lama_max_side,
        detection_count=len(mask_payload.get("strokes") or []),
    )
    elapsed_seconds = perf_counter() - started_at
    backup = _backup_existing_inpaint_outputs(doc_id, cleanup_dir)
    paths = write_inpaint_result(result, cleanup_dir)
    paths["mask_json"] = mask_paths.mask_json
    paths["manual_mask"] = mask_paths.manual_mask
    _augment_cleanup_summary(paths["summary"], paths=paths, elapsed_seconds=elapsed_seconds)
    update_manifest_artifact(doc_id, "inpaint", paths["comparison"])
    _clear_manifest_artifacts(doc_id, ["inpaint_cleanup", "inpaint_cleanup_inpainted", "inpaint_cleanup_mask"])
    synced_authoring = _sync_authoring_source_inpainted_for_doc(doc_id, source_image=policy.source_image, inpainted_path=paths["inpainted"])
    print(f"Finished manual cleanup postprocess doc={doc_id} elapsed={elapsed_seconds:.2f}s", flush=True)
    client_paths = _paths_to_client(paths)
    return {
        "docId": doc_id,
        "reviewPath": _display_path(review_path, ROOT),
        "mask": mask_payload,
        "summary": result.summary(paths) | {"elapsed_seconds": elapsed_seconds, "manual_mask_count": len(mask_payload.get("strokes") or [])},
        "paths": client_paths,
        "comparisonUrl": f"/api/file?path={client_paths['comparison']}",
        "manualMaskUrl": f"/api/file?path={client_paths['manual_mask']}",
        "syncedAuthoringTemplates": synced_authoring,
        "backup": _display_path(backup, ROOT) if backup else "",
    }


def _cleanup_dir(doc_id: str, policy: ReviewPolicy) -> Path:
    return _resolve_workspace_path(workbench_subdir(doc_id, "inpaint") / _safe_template_id(policy.source_image) / "lama")


def _backup_existing_inpaint_outputs(doc_id: str, inpaint_dir: Path) -> Path | None:
    existing = [
        path
        for path in (
            inpaint_dir / "inpainted_lama.png",
            inpaint_dir / "comparison_lama.png",
            inpaint_dir / "summary.json",
            inpaint_dir / "paint.json",
        )
        if path.exists()
    ]
    if not existing:
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_dir = ROOT / "workbench" / ".trash" / "inpaint_overwrite" / f"{timestamp}_{_safe_name(doc_id)}_{_safe_name(inpaint_dir.parent.name)}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in existing:
        shutil.copy2(path, backup_dir / path.name)
    return backup_dir



def empty_cleanup_paint_payload(width: int, height: int) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "tool": "paint_cleanup",
        "image": {"width": int(width), "height": int(height)},
        "strokes": [],
        "selected_color": [255, 255, 255],
        "brush_radius": 10,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def normalize_cleanup_paint_payload(payload: dict[str, Any] | None, *, width: int, height: int) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    strokes: list[dict[str, Any]] = []
    for index, stroke in enumerate(raw.get("strokes") or []):
        if not isinstance(stroke, dict):
            continue
        points = []
        for point in stroke.get("points") or []:
            if not isinstance(point, dict):
                continue
            try:
                x = int(round(float(point.get("x"))))
                y = int(round(float(point.get("y"))))
            except (TypeError, ValueError):
                continue
            points.append({"x": max(0, min(width - 1, x)), "y": max(0, min(height - 1, y))})
        if not points:
            continue
        color = _normalize_rgb(stroke.get("color") or raw.get("selected_color") or [255, 255, 255])
        radius = _clamped_int(stroke.get("radius") or raw.get("brush_radius") or 10, default=10, minimum=1, maximum=160)
        strokes.append(
            {
                "id": str(stroke.get("id") or f"paint_{index + 1:04d}"),
                "type": "brush",
                "color": color,
                "radius": radius,
                "points": points,
            }
        )
    return {
        "schema_version": 2,
        "tool": "paint_cleanup",
        "image": {"width": int(width), "height": int(height)},
        "strokes": strokes,
        "selected_color": _normalize_rgb(raw.get("selected_color") or [255, 255, 255]),
        "brush_radius": _clamped_int(raw.get("brush_radius") or 10, default=10, minimum=1, maximum=160),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _clamped_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        numeric = default
    return max(minimum, min(maximum, numeric))


def _normalize_rgb(value: Any) -> list[int]:
    raw = value if isinstance(value, (list, tuple)) else []
    result: list[int] = []
    for index in range(3):
        try:
            channel = int(round(float(raw[index])))
        except (IndexError, TypeError, ValueError):
            channel = 255
        result.append(max(0, min(255, channel)))
    return result


def _render_cleanup_paint(base_image_path: Path, payload: dict[str, Any]) -> Image.Image:
    image = Image.open(base_image_path).convert("RGB")
    normalized = normalize_cleanup_paint_payload(payload, width=image.width, height=image.height)
    draw = ImageDraw.Draw(image)
    for stroke in normalized.get("strokes") or []:
        points = [(int(point["x"]), int(point["y"])) for point in stroke.get("points") or []]
        if not points:
            continue
        radius = int(stroke.get("radius") or 10)
        color = tuple(_normalize_rgb(stroke.get("color")))
        if len(points) == 1:
            x, y = points[0]
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
            continue
        draw.line(points, fill=color, width=radius * 2, joint="curve")
        for x, y in points:
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    return image


def _cleanup_paint_paths(cleanup_dir: Path) -> dict[str, Path]:
    return {
        "paint_json": cleanup_dir / "paint.json",
        "inpainted": cleanup_dir / "inpainted_lama.png",
        "comparison": cleanup_dir / "comparison_lama.png",
        "summary": cleanup_dir / "summary.json",
    }


def load_cleanup_paint_payload(*, doc_id: str, review_path: Path, base_image_path: Path | None = None) -> dict[str, Any]:
    policy = load_review_policy(review_path)
    cleanup_dir = _cleanup_dir(doc_id, policy)
    base_path = base_image_path or _resolve_workspace_path(policy.source_image)
    if base_image_path is None:
        existing = _cleanup_paint_paths(cleanup_dir)["inpainted"]
        if existing.exists():
            base_path = existing
    with Image.open(base_path) as base:
        width, height = base.size
    paint_path = cleanup_dir / "paint.json"
    if paint_path.exists():
        try:
            paint = json.loads(paint_path.read_text(encoding="utf-8"))
        except Exception:
            paint = {}
    else:
        paint = empty_cleanup_paint_payload(width, height)
    saved_base = str(paint.get("base_image_path") or "") if isinstance(paint, dict) else ""
    if saved_base:
        saved_base_path = _resolve_workspace_path(saved_base)
        if saved_base_path.exists():
            base_path = saved_base_path
            with Image.open(base_path) as base:
                width, height = base.size
    paint = normalize_cleanup_paint_payload(paint, width=width, height=height)
    paint["base_image_path"] = _display_path(base_path, ROOT)
    paths = {name: path for name, path in _cleanup_paint_paths(cleanup_dir).items() if path.exists()}
    return {
        "docId": doc_id,
        "reviewPath": _display_path(review_path, ROOT),
        "baseImagePath": _display_path(base_path, ROOT),
        "exists": bool(paths),
        "paint": paint,
        "paths": _paths_to_client(paths),
        "imageUrl": f"/api/file?path={_display_path(paths.get('inpainted', base_path), ROOT)}",
    }


def save_cleanup_paint_payload(payload: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(payload.get("docId") or "")
    if not doc_id:
        raise ValueError("docId is required")
    review_path = _resolve_workspace_path(str(payload.get("reviewPath") or ""))
    base_image_path = _resolve_workspace_path(str(payload.get("baseImagePath") or ""))
    policy = load_review_policy(review_path)
    cleanup_dir = _cleanup_dir(doc_id, policy)
    cleanup_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(base_image_path) as source_base:
        base = source_base.convert("RGB")
    paint = normalize_cleanup_paint_payload(payload.get("paint"), width=base.width, height=base.height)
    paint["base_image_path"] = _display_path(base_image_path, ROOT)
    rendered = _render_cleanup_paint(base_image_path, paint)
    paths = _cleanup_paint_paths(cleanup_dir)
    backup = _backup_existing_inpaint_outputs(doc_id, cleanup_dir)
    paths["paint_json"].write_text(json.dumps(paint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rendered.save(paths["inpainted"])
    diff = ImageChops.difference(base, rendered)
    comparison = Image.new("RGB", (base.width * 2, base.height), "white")
    comparison.paste(base, (0, 0))
    comparison.paste(rendered, (base.width, 0))
    comparison.save(paths["comparison"])
    paths["summary"].write_text(
        json.dumps(
            {
                "schema_version": 1,
                "strategy": "eyedropper_brush_template_cleanup",
                "stroke_count": len(paint.get("strokes") or []),
                "changed_bbox": diff.getbbox(),
                "outputs": {name: _display_path(path, ROOT) for name, path in paths.items()},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    update_manifest_artifact(doc_id, "inpaint", paths["comparison"])
    _clear_manifest_artifacts(doc_id, ["inpaint_cleanup", "inpaint_cleanup_inpainted", "inpaint_cleanup_mask"])
    synced_authoring = _sync_authoring_source_inpainted_for_doc(doc_id, source_image=policy.source_image, inpainted_path=paths["inpainted"])
    client_paths = _paths_to_client(paths)
    return {
        "docId": doc_id,
        "reviewPath": _display_path(review_path, ROOT),
        "baseImagePath": _display_path(base_image_path, ROOT),
        "paint": paint,
        "summary": {"stroke_count": len(paint.get("strokes") or []), "strategy": "eyedropper_brush_template_cleanup"},
        "paths": client_paths,
        "imageUrl": f"/api/file?path={client_paths['inpainted']}",
        "comparisonUrl": f"/api/file?path={client_paths['comparison']}",
        "syncedAuthoringTemplates": synced_authoring,
        "backup": _display_path(backup, ROOT) if backup else "",
    }


def backup_review_draft_outputs(output_dir: Path) -> dict[str, str] | None:
    review_path = output_dir / "review.json"
    overlay_path = output_dir / "review_overlay.png"
    existing = [path for path in (review_path, overlay_path) if path.exists()]
    if not existing:
        return None
    backup_dir = output_dir / "backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for path in existing:
        destination = backup_dir / path.name
        import shutil
        shutil.copy2(path, destination)
        copied[path.stem] = _display_path(destination, ROOT)
    return {"dir": _display_path(backup_dir, ROOT), **copied}


def _sync_authoring_source_inpainted_for_doc(doc_id: str, *, source_image: Path, inpainted_path: Path) -> dict[str, Any]:
    authoring_dir = _resolve_workspace_path(workbench_subdir(doc_id, "authoring"))
    schema_paths: list[Path] = []
    main_schema = authoring_dir / "schema.json"
    if main_schema.exists():
        schema_paths.append(main_schema)
    if authoring_dir.exists():
        schema_paths.extend(sorted(path for path in authoring_dir.glob("page_*/schema.json") if path not in schema_paths))
    results = [
        update_authoring_source_inpainted(schema_path, source_image=source_image, inpainted_path=inpainted_path)
        for schema_path in schema_paths
    ]
    updated = [item for item in results if item.get("updated")]
    return {
        "sourceImage": _display_path(source_image, ROOT),
        "sourceInpainted": _display_path(inpainted_path, ROOT),
        "checked": len(results),
        "updated": len(updated),
        "items": results,
    }


def _sync_authoring_template_from_schema_path(schema_path: Path) -> dict[str, Any] | None:
    if not schema_path.exists():
        return None
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    doc_id = str(schema.get("doc_id") or "").strip()
    if not doc_id:
        return None
    return _sync_authoring_template_from_latest_work_item(doc_id)


def _sync_authoring_template_from_latest_work_item(doc_id: str) -> dict[str, Any] | None:
    registry = load_registry()
    for item in list_work_items(registry=registry):
        if str(item.get("docId") or "") == doc_id:
            return _sync_authoring_template_from_work_item(item)
    return None


def _sync_authoring_template_from_work_item(item: dict[str, Any]) -> dict[str, Any] | None:
    doc_id = str(item.get("docId") or "").strip()
    review_path_value = str(item.get("latestReview") or "").strip()
    inpainted_path_value = str(item.get("latestInpainted") or "").strip()
    if not doc_id or not review_path_value or not inpainted_path_value:
        return None
    try:
        policy = load_review_policy(_resolve_workspace_path(review_path_value))
    except Exception:
        return None
    inpainted_path = _resolve_workspace_path(inpainted_path_value)
    if not inpainted_path.exists():
        return None
    return _sync_authoring_source_inpainted_for_doc(doc_id, source_image=policy.source_image, inpainted_path=inpainted_path)


def _inpaint_cleanup_template(*, base_image_path: Path, mask_path: Path, detections_path: Path, lama_max_side: int, detection_count: int) -> InpaintResult:
    base_image = Image.open(base_image_path).convert("RGB")
    manual_mask = Image.open(mask_path).convert("L").point(lambda value: 255 if value > 0 else 0)
    if manual_mask.size != base_image.size:
        raise ValueError(f"manual mask size mismatch: {manual_mask.size} != {base_image.size}")
    mask_pixels = sum(count for value, count in enumerate(manual_mask.histogram()) if value > 0)
    inpainted = base_image.copy() if mask_pixels == 0 else lama_inpaint(base_image, manual_mask, max_side=lama_max_side)
    mask_overlay = render_mask_overlay(base_image, manual_mask)
    return InpaintResult(
        source_image=base_image_path,
        detections_path=detections_path,
        image_width=base_image.width,
        image_height=base_image.height,
        detection_count=detection_count,
        mask_pixels=mask_pixels,
        mask_ratio=mask_pixels / float(base_image.width * base_image.height),
        method="lama",
        mask_shape="polygon",
        padding=0,
        dilation=0,
        radius=3.0,
        lama_max_side=lama_max_side,
        image=inpainted,
        mask=manual_mask,
        mask_overlay=mask_overlay,
    )


def _augment_cleanup_summary(summary_path: Path, *, paths: dict[str, Path], elapsed_seconds: float) -> None:
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        summary = {}
    summary["elapsed_seconds"] = elapsed_seconds
    summary["cleanup"] = {
        "strategy": "postprocess_inpainted_template_with_manual_mask",
        "outputs": {name: str(path) for name, path in paths.items()},
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class DataFactoryRequestHandler(BaseHTTPRequestHandler):
    server_version = "DataFactoryWebAPI/0.1"

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self._send_json(runtime_health())
                return
            if parsed.path == "/api/assets":
                self._send_json(list_assets())
                return
            if parsed.path == "/api/fonts":
                query = parse_qs(parsed.query)
                refresh = (query.get("refresh") or [""])[0].lower() in {"1", "true", "yes"}
                fonts = list_font_faces(refresh=refresh)
                self._send_json({"defaultFontId": default_font_id(), "fonts": fonts})
                return
            if parsed.path == "/api/outputs/batches":
                self._send_json(list_output_batches())
                return
            if parsed.path == "/api/registry":
                self._send_json(registry_payload())
                return
            if parsed.path == "/api/target-groups":
                self._send_json(list_target_groups(registry=load_registry()))
                return
            if parsed.path == "/api/seed/scan":
                self._send_json(scan_seed_samples(registry=load_registry()))
                return
            if parsed.path == "/api/audit/reviews":
                self._send_json(scan_review_legacy_issues())
                return
            if parsed.path == "/api/audit/manual-cleanup":
                self._send_json(scan_manual_cleanup_legacy())
                return
            if parsed.path == "/api/work-items":
                registry = load_registry()
                items = list_work_items(registry=registry)
                self._send_json(
                    {
                        "summary": {
                            "total": len(items),
                            "imported": len([item for item in items if item["status"] != "missing"]),
                            "bboxDone": len([item for item in items if item["hasOcr"]]),
                            "reviewDone": len([item for item in items if item["hasReview"]]),
                            "inpaintDone": len([item for item in items if item["hasInpaint"]]),
                        },
                        "items": items,
                    }
                )
                return
            if parsed.path == "/api/first-priority/assessments":
                self._send_json(list_first_priority_assessments(registry=load_registry()))
                return
            if parsed.path == "/api/review":
                review_path = _query_path(parsed.query)
                policy = load_review_policy(review_path)
                self._send_json(policy_to_client(policy, review_path=review_path))
                return
            if parsed.path == "/api/cleanup-mask":
                query = parse_qs(parsed.query)
                doc_id = _first_query_value(query, "docId")
                review_path = _resolve_workspace_path(_first_query_value(query, "reviewPath"))
                self._send_json(load_cleanup_mask_payload(doc_id=doc_id, review_path=review_path))
                return
            if parsed.path == "/api/cleanup-paint":
                query = parse_qs(parsed.query)
                doc_id = _first_query_value(query, "docId")
                review_path = _resolve_workspace_path(_first_query_value(query, "reviewPath"))
                base_value = _first_query_value(query, "baseImagePath")
                base_image_path = _resolve_workspace_path(base_value) if base_value else None
                self._send_json(load_cleanup_paint_payload(doc_id=doc_id, review_path=review_path, base_image_path=base_image_path))
                return
            if parsed.path == "/api/authoring":
                query = parse_qs(parsed.query)
                schema_path = _resolve_workspace_path(_first_query_value(query, "schema"))
                stylesheet_path = _resolve_workspace_path(_first_query_value(query, "stylesheet"))
                faker_profile_path = _resolve_workspace_path(_first_query_value(query, "fakerProfile"))
                _sync_authoring_template_from_schema_path(schema_path)
                result = load_authoring_bundle(schema_path, stylesheet_path, faker_profile_path)
                consistency = _authoring_bundle_consistency(result.payload["schema"], result.payload["faker_profile"], strict_review_coverage=True)
                self._send_json(
                    {
                        "paths": _paths_to_client({"schema": result.schema, "stylesheet": result.stylesheet, "faker_profile": result.faker_profile}),
                        "consistency": consistency,
                        **result.payload,
                    }
                )
                return
            if parsed.path == "/api/authoring/agent-run-status":
                query = parse_qs(parsed.query)
                payload: dict[str, Any] = {}
                if query.get("jobPath"):
                    payload["jobPath"] = unquote(query["jobPath"][0])
                if query.get("docId"):
                    payload["docId"] = unquote(query["docId"][0])
                self._send_json(authoring_agent_run_status_payload(payload))
                return
            if parsed.path == "/api/ocr/detect/status":
                query = parse_qs(parsed.query)
                payload: dict[str, Any] = {}
                if query.get("jobPath"):
                    payload["jobPath"] = unquote(query["jobPath"][0])
                if query.get("docId"):
                    payload["docId"] = unquote(query["docId"][0])
                self._send_json(ocr_detection_status_payload(payload))
                return
            if parsed.path in {"/api/image", "/api/file"}:
                file_path = _query_path(parsed.query)
                self._send_file(file_path)
                return
            self._send_json({"error": f"Unknown endpoint: {parsed.path}"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - exercised by manual server use
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        try:
            parsed = urlparse(self.path)
            payload = self._read_json()
            if parsed.path == "/api/seed/import":
                seed_folder = _resolve_workspace_path(str(payload.get("seedFolder") or ""))
                doc_id = str(payload.get("docId") or "")
                if not doc_id:
                    raise ValueError("docId is required")
                self._send_json(import_seed_folder(seed_folder, doc_id, registry=load_registry(), remember_mapping=bool(payload.get("rememberMapping"))))
                return
            if parsed.path == "/api/seed/import-batch":
                raw_items = payload.get("items")
                if not isinstance(raw_items, list):
                    raise ValueError("items must be a list")
                items: list[dict[str, Any]] = []
                for item in raw_items:
                    if not isinstance(item, dict):
                        raise ValueError("each batch item must be an object")
                    items.append(
                        {
                            "seedFolder": str(_resolve_workspace_path(str(item.get("seedFolder") or ""))),
                            "docId": str(item.get("docId") or ""),
                            "rememberMapping": bool(item.get("rememberMapping")),
                        }
                    )
                self._send_json(import_seed_batch(items, registry=load_registry()))
                return
            if parsed.path == "/api/seed/mapping":
                folder_name = str(payload.get("folderName") or "")
                doc_id = str(payload.get("docId") or "")
                if not folder_name or not doc_id:
                    raise ValueError("folderName and docId are required")
                self._send_json({"mapping": save_seed_mapping(folder_name, doc_id, registry=load_registry())})
                return
            if parsed.path == "/api/seed/upload":
                doc_id = str(payload.get("docId") or "")
                raw_files = payload.get("files")
                if not doc_id:
                    raise ValueError("docId is required")
                if not isinstance(raw_files, list) or not raw_files:
                    raise ValueError("files must be a non-empty list")
                files: list[dict[str, Any]] = []
                for item in raw_files:
                    if not isinstance(item, dict):
                        raise ValueError("each file must be an object")
                    name = str(item.get("name") or "")
                    data = str(item.get("dataBase64") or "")
                    if "," in data and data.split(",", 1)[0].startswith("data:"):
                        data = data.split(",", 1)[1]
                    try:
                        decoded = base64.b64decode(data, validate=True)
                    except Exception as exc:
                        raise ValueError(f"invalid base64 payload: {name}") from exc
                    files.append({"name": name, "contentType": str(item.get("contentType") or ""), "bytes": decoded})
                self._send_json(save_uploaded_seed_files(doc_id, files, registry=load_registry()))
                return
            if parsed.path == "/api/seed/trash":
                seed_folder = _resolve_workspace_path(str(payload.get("seedFolder") or ""))
                self._send_json(trash_seed_folder(seed_folder))
                return
            if parsed.path == "/api/seed/revert-preview":
                doc_id = str(payload.get("docId") or "")
                if not doc_id:
                    raise ValueError("docId is required")
                self._send_json(preview_seed_revert(doc_id, registry=load_registry()))
                return
            if parsed.path == "/api/seed/revert":
                doc_id = str(payload.get("docId") or "")
                if not doc_id:
                    raise ValueError("docId is required")
                self._send_json(revert_seed_import(doc_id, registry=load_registry()))
                return
            if parsed.path == "/api/target-groups/save":
                self._send_json(save_target_group(payload, registry=load_registry()))
                return
            if parsed.path == "/api/target-groups/delete":
                self._send_json(delete_target_group(str(payload.get("id") or ""), registry=load_registry()))
                return
            if parsed.path == "/api/ocr/detect":
                self._send_json(_ocr_detection_result_payload(payload))
                return
            if parsed.path == "/api/ocr/detect/start":
                self._send_json(ocr_detection_start_payload(payload), status=HTTPStatus.ACCEPTED)
                return
            if parsed.path == "/api/review/draft":
                detections_path = _resolve_workspace_path(str(payload.get("detectionsPath") or ""))
                doc_id = str(payload.get("docId") or "")
                sample_kind = str(payload.get("sampleKind") or "")
                default_out_dir = workbench_subdir(doc_id, "review") if doc_id else Path("outputs/reviews")
                out_dir = _resolve_workspace_path(str(payload.get("outDir") or default_out_dir))
                policy = draft_review_policy(detections_path)
                visual_detection: dict[str, Any] | None = None
                if sample_kind == "blank_template":
                    if _visual_line_detection_requested(payload):
                        policy, visual_detection = augment_blank_template_policy(policy)
                    else:
                        visual_detection = {"enabled": False, "method": "pil_line_projection", "candidateCount": 0, "reason": "not_requested"}
                draft_dir = out_dir / _safe_template_id(policy.source_image)
                backup = backup_review_draft_outputs(draft_dir)
                paths = write_review_policy(policy, draft_dir)
                if doc_id:
                    if sample_kind:
                        set_manifest_sample_kind(doc_id, sample_kind)
                    update_manifest_artifact(doc_id, "review", paths["review"])
                self._send_json({"docId": doc_id or None, "paths": _paths_to_client(paths), "policy": policy_to_client(policy, review_path=paths["review"]), "backup": backup, "visualDetection": visual_detection})
                return
            if parsed.path == "/api/review/save":
                self._send_json(save_policy_payload(payload))
                return
            if parsed.path == "/api/work-item/sample-kind":
                doc_id = str(payload.get("docId") or "")
                sample_kind = str(payload.get("sampleKind") or "")
                manifest = set_manifest_sample_kind(doc_id, sample_kind)
                self._send_json({"docId": doc_id, "sampleKind": manifest.get("sample_kind"), "manifest": manifest})
                return
            if parsed.path == "/api/review/remove-ignore":
                self._send_json(remove_ignore_bboxes_payload(payload))
                return
            if parsed.path == "/api/review/recognize-crops":
                self._send_json(recognize_review_crops_payload(payload))
                return
            if parsed.path == "/api/authoring/review-prune-candidates":
                self._send_json(authoring_review_prune_candidates_payload(payload))
                return
            if parsed.path == "/api/first-priority/assessment":
                self._send_json(
                    save_assessment_entry(
                        domain=str(payload.get("domain") or ""),
                        doc_id=str(payload.get("docId") or ""),
                        document_type=str(payload.get("documentType") or "unknown"),
                        feasibility=str(payload.get("feasibility") or "unknown"),
                        comment=str(payload.get("comment") or ""),
                        registry=load_registry(),
                    )
                )
                return
            if parsed.path == "/api/first-priority/export-xlsx":
                out_dir = _resolve_workspace_path(str(payload.get("outDir") or "outputs/first_priority_assessment"))
                result = export_first_priority_assessment_xlsx(out_dir=out_dir, registry=load_registry())
                path = _resolve_workspace_path(result["path"])
                self._send_json(
                    {
                        "summary": result["summary"],
                        "rowCount": result["rowCount"],
                        "path": _display_path(path, ROOT),
                        "url": f"/api/file?path={_display_path(path, ROOT)}",
                    }
                )
                return
            if parsed.path == "/api/results/final-export":
                count = int(payload.get("count") or 1)
                seed = int(payload.get("seed") or 20260703)
                render_scale = int(payload.get("renderScale") or 2)
                out_dir = _resolve_workspace_path(str(payload.get("outDir") or "outputs/results"))
                result = export_final_results(
                    count=count,
                    out_dir=out_dir,
                    seed=seed,
                    render_scale=render_scale,
                    as_of_date=_parse_as_of_date(payload.get("asOfDate")),
                    clean=bool(payload.get("clean", True)),
                    render_handwriting_as_printed=bool(payload.get("renderHandwritingAsPrinted", False)),
                    scope_entries=payload.get("scopeEntries") if "scopeEntries" in payload else None,
                    registry=load_registry(),
                )
                manifest_path = _resolve_workspace_path(result["paths"]["manifest"])
                summary_path = _resolve_workspace_path(result["paths"]["summary"])
                self._send_json(
                    {
                        **result,
                        "urls": {
                            "manifest": f"/api/file?path={_display_path(manifest_path, ROOT)}",
                            "summary": f"/api/file?path={_display_path(summary_path, ROOT)}",
                        },
                    }
                )
                return
            if parsed.path == "/api/handwriting/print-pack":
                doc_id = str(payload.get("docId") or "")
                if not doc_id:
                    raise ValueError("docId is required")
                count = max(1, min(100, int(payload.get("count") or 5)))
                seed = int(payload.get("seed") or 20260708)
                qr_bbox = payload.get("qrBbox") if isinstance(payload.get("qrBbox"), list) else None
                result = create_handwriting_print_pack(
                    doc_id,
                    count=count,
                    seed=seed,
                    qr_bbox=qr_bbox,
                    run_id=str(payload.get("runId") or "") or None,
                    allow_printed=bool(payload.get("allowPrinted", False)),
                    registry=load_registry(),
                )
                manifest_path = _resolve_workspace_path(result["paths"]["manifest"])
                sample_pdf_urls = [
                    f"/api/file?path={str(sample.get('print_pack_pdf') or '')}"
                    for sample in result.get("manifest", {}).get("samples", [])
                    if isinstance(sample, dict) and sample.get("print_pack_pdf")
                ]
                self._send_json({**result, "urls": {"manifest": f"/api/file?path={_display_path(manifest_path, ROOT)}", "printPackPdfs": sample_pdf_urls}})
                return
            if parsed.path == "/api/handwriting/scan-upload-intake":
                doc_id = str(payload.get("docId") or "") or None
                raw_files = payload.get("files")
                if not isinstance(raw_files, list) or not raw_files:
                    raise ValueError("files must be a non-empty list")
                run_id = str(payload.get("runId") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
                upload_dir = ROOT / "workbench" / "handwriting_scan_uploads" / run_id
                upload_dir.mkdir(parents=True, exist_ok=True)
                scan_paths: list[str] = []
                for index, item in enumerate(raw_files):
                    if not isinstance(item, dict):
                        raise ValueError("each file must be an object")
                    name = _safe_name(str(item.get("name") or f"scan_{index:03d}.pdf"))
                    suffix = Path(name).suffix.lower() or ".pdf"
                    data = str(item.get("dataBase64") or "")
                    if "," in data and data.split(",", 1)[0].startswith("data:"):
                        data = data.split(",", 1)[1]
                    decoded = base64.b64decode(data, validate=True)
                    out_path = upload_dir / f"{index:03d}_{Path(name).stem}{suffix}"
                    out_path.write_bytes(decoded)
                    scan_paths.append(str(out_path))
                result = intake_handwriting_scans(
                    doc_id=doc_id,
                    scan_paths=scan_paths,
                    scan_dir=None,
                    print_pack_manifest=str(payload.get("printPackManifest") or "") or None,
                    run_id=run_id,
                    registry=load_registry(),
                )
                manifest_path = _resolve_workspace_path(result["paths"]["manifest"])
                self._send_json({**result, "uploadDir": _display_path(upload_dir, ROOT), "urls": {"manifest": f"/api/file?path={_display_path(manifest_path, ROOT)}"}})
                return
            if parsed.path == "/api/handwriting/scan-intake":
                scan_paths = payload.get("scanPaths") if isinstance(payload.get("scanPaths"), list) else None
                result = intake_handwriting_scans(
                    doc_id=str(payload.get("docId") or "") or None,
                    scan_paths=scan_paths,
                    scan_dir=str(payload.get("scanDir") or "") or None,
                    print_pack_manifest=str(payload.get("printPackManifest") or "") or None,
                    run_id=str(payload.get("runId") or "") or None,
                    registry=load_registry(),
                )
                manifest_path = _resolve_workspace_path(result["paths"]["manifest"])
                self._send_json({**result, "urls": {"manifest": f"/api/file?path={_display_path(manifest_path, ROOT)}"}})
                return
            if parsed.path == "/api/docx/analyze":
                doc_id = str(payload.get("docId") or "")
                if not doc_id:
                    raise ValueError("docId is required")
                self._send_json(analyze_docx_template(doc_id, registry=load_registry()))
                return
            if parsed.path == "/api/docx/draft-authoring":
                doc_id = str(payload.get("docId") or "")
                if not doc_id:
                    raise ValueError("docId is required")
                self._send_json(draft_docx_authoring(doc_id, registry=load_registry()))
                return
            if parsed.path == "/api/docx/generate":
                doc_id = str(payload.get("docId") or "")
                if not doc_id:
                    raise ValueError("docId is required")
                count = max(1, min(100, int(payload.get("count") or 1)))
                seed = int(payload.get("seed") or 20260708)
                render_pdf = bool(payload.get("renderPdf", True))
                schema_path = _resolve_workspace_path(str(payload.get("schemaPath") or "")) if payload.get("schemaPath") else None
                faker_profile_path = _resolve_workspace_path(str(payload.get("fakerProfilePath") or "")) if payload.get("fakerProfilePath") else None
                self._send_json(
                    generate_docx_outputs(
                        doc_id,
                        count=count,
                        seed=seed,
                        render_pdf=render_pdf,
                        schema_path=schema_path,
                        faker_profile_path=faker_profile_path,
                        registry=load_registry(),
                    )
                )
                return
            if parsed.path == "/api/cleanup-mask":
                self._send_json(save_cleanup_mask_payload(payload))
                return
            if parsed.path == "/api/cleanup-paint":
                self._send_json(save_cleanup_paint_payload(payload))
                return
            if parsed.path == "/api/cleanup-inpaint":
                self._send_json(run_cleanup_inpaint_payload(payload))
                return
            if parsed.path == "/api/manual-cleanup/promote":
                self._send_json(promote_manual_cleanup_payload(payload))
                return
            if parsed.path == "/api/inpaint":
                saved: dict[str, Any] | None = None
                doc_id = str(payload.get("docId") or "")
                if doc_id:
                    current_item = next((candidate for candidate in list_work_items() if candidate.get("docId") == doc_id), None)
                    if str((current_item or {}).get("sampleKind") or "") == "blank_template":
                        raise ValueError("blank_template samples do not need inpainting; review value-region bboxes and run agent authoring instead")
                review_path_value = str(payload.get("reviewPath") or "")
                review_path = _resolve_workspace_path(review_path_value) if review_path_value else None
                if isinstance(payload.get("policy"), dict):
                    saved = save_policy_payload(payload)
                    review_path = _resolve_workspace_path(saved["paths"]["review"])
                if review_path is None:
                    raise ValueError("reviewPath or policy is required")
                method = str(payload.get("method") or "lama")
                if method not in {"fill", "telea", "ns", "lama"}:
                    raise ValueError("method must be one of fill, telea, ns, lama")
                default_out_dir = workbench_subdir(doc_id, "inpaint") if doc_id else Path("outputs/inpaint_eval/react_reviewed")
                out_dir = _resolve_workspace_path(str(payload.get("outDir") or default_out_dir))
                lama_max_side = int(payload.get("lamaMaxSide") or 2400)
                started_at = perf_counter()
                print(f"Starting inpaint method={method} review={review_path} lama_max_side={lama_max_side}", flush=True)
                result = inpaint_from_review_policy(
                    review_path,
                    InpaintConfig(method=method, mask_shape="bbox", padding=2, dilation=1, radius=3.0, lama_max_side=lama_max_side),
                )
                elapsed_seconds = perf_counter() - started_at
                print(f"Finished inpaint method={method} regions={result.detection_count} elapsed={elapsed_seconds:.2f}s", flush=True)
                paths = write_inpaint_result(result, out_dir / _safe_template_id(result.source_image) / method)
                synced_authoring: dict[str, Any] | None = None
                if doc_id:
                    update_manifest_artifact(doc_id, "inpaint", paths["comparison"])
                    synced_authoring = _sync_authoring_source_inpainted_for_doc(doc_id, source_image=result.source_image, inpainted_path=paths["inpainted"])
                self._send_json(
                    {
                        "docId": doc_id or None,
                        "saved": saved,
                        "summary": result.summary(paths) | {"elapsed_seconds": elapsed_seconds},
                        "paths": _paths_to_client(paths),
                        "comparisonUrl": f"/api/file?path={_display_path(paths['comparison'], ROOT)}",
                        "syncedAuthoringTemplates": synced_authoring,
                    }
                )
                return
            if parsed.path == "/api/authoring/draft":
                self._send_json(
                    {
                        "error": "authoring_draft_disabled",
                        "message": "Schema 초안 생성은 기존 authoring 데이터를 덮어쓸 위험이 있어 비활성화되었습니다.",
                    },
                    status=410,
                )
                return
            if parsed.path == "/api/authoring/agent-request":
                self._send_json(authoring_agent_request_payload(payload))
                return
            if parsed.path == "/api/authoring/agent-run":
                self._send_json(authoring_agent_run_payload(payload, async_run=not bool(payload.get("sync"))))
                return
            if parsed.path == "/api/authoring/agent-run-status":
                self._send_json(authoring_agent_run_status_payload(payload))
                return
            if parsed.path == "/api/authoring/migrate-bboxes":
                doc_id = str(payload.get("docId") or "")
                if not doc_id:
                    raise ValueError("docId is required")
                authoring_dir = workbench_subdir(doc_id, "authoring")
                schema_path = _resolve_workspace_path(str(payload.get("schemaPath") or authoring_dir / "schema.json"))
                review_path_value = str(payload.get("reviewPath") or "")
                review_path = _resolve_workspace_path(review_path_value) if review_path_value else None
                result = migrate_authoring_schema_bboxes_to_review(schema_path, review_path=review_path)
                if result.get("review"):
                    update_manifest_artifact(doc_id, "review", _resolve_workspace_path(str(result["review"])))
                update_manifest_artifact(doc_id, "authoring", schema_path)
                self._send_json({"docId": doc_id, "summary": result})
                return
            if parsed.path == "/api/authoring/render-preview":
                doc_id = str(payload.get("docId") or "")
                if not doc_id:
                    raise ValueError("docId is required")
                _sync_authoring_template_from_latest_work_item(doc_id)
                authoring_dir = workbench_subdir(doc_id, "authoring")
                schema_path = _resolve_workspace_path(str(payload.get("schemaPath") or authoring_dir / "schema.json"))
                stylesheet_path = _resolve_workspace_path(str(payload.get("stylesheetPath") or authoring_dir / "stylesheet.json"))
                faker_profile_path = _resolve_workspace_path(str(payload.get("fakerProfilePath") or authoring_dir / "faker_profile.json"))
                seed = int(payload.get("seed") or 1234)
                render_scale = int(payload.get("renderScale") or 2)
                result = render_authoring_preview(
                    schema_path,
                    stylesheet_path,
                    faker_profile_path,
                    out_dir=authoring_dir / "render_preview",
                    seed=seed,
                    render_scale=render_scale,
                    as_of_date=_parse_as_of_date(payload.get("asOfDate")),
                )
                update_manifest_artifact(doc_id, "authoring_preview", result.image)
                update_manifest_artifact(doc_id, "authoring_overlay", result.overlay)
                self._send_json(
                    {
                        "docId": doc_id,
                        "summary": {"sample_id": result.sample_id, "field_count": result.field_count, "warning_count": result.warning_count},
                        "paths": _paths_to_client(
                            {
                                "image": result.image,
                                "kv": result.kv,
                                "bbox": result.bbox,
                                "overlay": result.overlay,
                                "validation_report": result.validation_report,
                                "manifest": result.manifest,
                            }
                        ),
                        "imageUrl": f"/api/file?path={_display_path(result.image, ROOT)}",
                        "overlayUrl": f"/api/file?path={_display_path(result.overlay, ROOT)}",
                    }
                )
                return
            if parsed.path == "/api/authoring/live-preview":
                doc_id = str(payload.get("docId") or "")
                if not doc_id:
                    raise ValueError("docId is required")
                raw_schema = payload.get("schema")
                raw_stylesheet = payload.get("stylesheet")
                raw_faker_profile = payload.get("fakerProfile")
                if not isinstance(raw_schema, dict) or not isinstance(raw_stylesheet, dict) or not isinstance(raw_faker_profile, dict):
                    raise ValueError("schema, stylesheet and fakerProfile are required")
                seed = int(payload.get("seed") or 1234)
                render_scale = int(payload.get("renderScale") or 2)
                as_of_date = _parse_as_of_date(payload.get("asOfDate"))
                consistency = _raise_if_authoring_inconsistent(raw_schema, raw_faker_profile, strict_review_coverage=False)
                if bool(payload.get("handwritingPreview")):
                    result = render_handwriting_authoring_preview(
                        doc_id,
                        raw_schema,
                        raw_stylesheet,
                        raw_faker_profile,
                        out_dir=RENDER_OUTPUT_ROOT / "live_preview" / _safe_name(doc_id),
                        seed=seed,
                        sample_id="live_preview",
                        qr_bbox=payload.get("qrBbox") if isinstance(payload.get("qrBbox"), list) else None,
                    )
                    paths = {key: result[key] for key in ("image", "kv", "bbox", "overlay", "validation_report")}
                    self._send_json(
                        {
                            "docId": doc_id,
                            "summary": {"sample_id": result["sample_id"], "field_count": result["field_count"], "warning_count": result["warning_count"], "printed_field_count": result["printed_field_count"], "handwriting_field_count": result["handwriting_field_count"], "qr_bbox": result["qr_bbox"]},
                            "consistency": consistency,
                            "paths": _paths_to_client(paths),
                            "imageUrl": f"/api/file?path={_display_path(result['image'], ROOT)}",
                        }
                    )
                else:
                    result = render_authoring_live_preview(
                        raw_schema,
                        raw_stylesheet,
                        raw_faker_profile,
                        out_dir=RENDER_OUTPUT_ROOT / "live_preview" / _safe_name(doc_id),
                        seed=seed,
                        sample_id="live_preview",
                        render_scale=render_scale,
                        as_of_date=as_of_date,
                    )
                    self._send_json(
                        {
                            "docId": doc_id,
                            "summary": {"sample_id": result.sample_id, "field_count": result.field_count, "warning_count": result.warning_count},
                            "consistency": consistency,
                            "paths": _paths_to_client(
                                {
                                    "image": result.image,
                                    "kv": result.kv,
                                    "bbox": result.bbox,
                                    "overlay": result.overlay,
                                    "validation_report": result.validation_report,
                                }
                            ),
                            "imageUrl": f"/api/file?path={_display_path(result.image, ROOT)}",
                        }
                    )
                return
            if parsed.path == "/api/authoring/render-batch":
                doc_ids = payload.get("docIds")
                count = int(payload.get("count") or 5)
                seed = int(payload.get("seed") or 20260702)
                render_scale = int(payload.get("renderScale") or 2)
                out_dir = _resolve_workspace_path(str(payload.get("outDir") or "outputs/render/batch_authoring_20260702"))
                if doc_ids is not None and not isinstance(doc_ids, list):
                    raise ValueError("docIds must be a list when provided")
                result = render_authoring_batch_for_work_items(
                    doc_ids=[str(item) for item in doc_ids] if doc_ids is not None else None,
                    count=count,
                    seed=seed,
                    out_dir=out_dir,
                    render_scale=render_scale,
                    as_of_date=_parse_as_of_date(payload.get("asOfDate")),
                )
                self._send_json(result)
                return
            if parsed.path == "/api/authoring/library":
                library = authoring_library_payload(ROOT / "workbench" / "authoring_library")
                self._send_json({**library, "library_root": _display_path(Path(library["library_root"]), ROOT)})
                return
            if parsed.path == "/api/authoring/approve-drafts":
                request_path = _resolve_workspace_path(str(payload.get("requestPath") or ""))
                result = approve_authoring_draft_to_library(
                    request_path,
                    library_root=ROOT / "workbench" / "authoring_library",
                    note=str(payload.get("note") or ""),
                )
                approval = result["approval"]
                approval = {**approval, "path": _display_path(approval["path"], ROOT), "request": _display_path(approval["request"], ROOT), "copied": [{**item, "path": _display_path(item["path"], ROOT)} for item in approval.get("copied", [])]}
                self._send_json({**result, "library": _display_path(result["library"], ROOT), "index": _display_path(result["index"], ROOT), "approval": approval})
                return
            if parsed.path == "/api/authoring/apply-agent-drafts":
                self._send_json(apply_authoring_agent_drafts_payload(payload))
                return
            if parsed.path == "/api/authoring/semantic-to-authoring":
                semantic_schema = payload.get("semanticSchema")
                if not isinstance(semantic_schema, dict):
                    raise ValueError("semanticSchema is required")
                anchor_map = payload.get("anchorMap") if isinstance(payload.get("anchorMap"), dict) else None
                doc_id = str(payload.get("docId") or "") or None
                schema = semantic_schema_to_authoring_schema(
                    semantic_schema,
                    anchor_map=anchor_map,
                    source_review=str(payload.get("sourceReview") or "") or None,
                    source_image=str(payload.get("sourceImage") or "") or None,
                    source_inpainted=str(payload.get("sourceInpainted") or "") or None,
                    doc_id=doc_id,
                    title=str(payload.get("title") or "") or None,
                )
                self._send_json({"schema": schema, "summary": {"fieldCount": len(schema.get("fields") or [])}})
                return
            if parsed.path == "/api/authoring/validate":
                raw_schema = payload.get("schema")
                raw_faker_profile = payload.get("fakerProfile")
                if not isinstance(raw_schema, dict) or not isinstance(raw_faker_profile, dict):
                    raise ValueError("schema and fakerProfile are required")
                self._send_json({"consistency": _authoring_bundle_consistency(raw_schema, raw_faker_profile, strict_review_coverage=bool(payload.get("strictReviewCoverage", True)))})
                return
            if parsed.path == "/api/authoring/save":
                doc_id = str(payload.get("docId") or "")
                if not doc_id:
                    raise ValueError("docId is required")
                authoring_dir = workbench_subdir(doc_id, "authoring")
                schema_path = _resolve_workspace_path(str(payload.get("schemaPath") or authoring_dir / "schema.json"))
                stylesheet_path = _resolve_workspace_path(str(payload.get("stylesheetPath") or authoring_dir / "stylesheet.json"))
                faker_profile_path = _resolve_workspace_path(str(payload.get("fakerProfilePath") or authoring_dir / "faker_profile.json"))
                raw_schema = payload.get("schema")
                raw_stylesheet = payload.get("stylesheet")
                raw_faker_profile = payload.get("fakerProfile")
                if not isinstance(raw_schema, dict) or not isinstance(raw_stylesheet, dict) or not isinstance(raw_faker_profile, dict):
                    raise ValueError("schema, stylesheet and fakerProfile are required")
                consistency = _raise_if_authoring_inconsistent(raw_schema, raw_faker_profile, strict_review_coverage=True)
                result = save_authoring_bundle(
                    schema_path,
                    stylesheet_path,
                    faker_profile_path,
                    schema=raw_schema,
                    stylesheet=raw_stylesheet,
                    faker_profile=raw_faker_profile,
                )
                update_manifest_artifact(doc_id, "authoring", result.schema)
                update_manifest_artifact(doc_id, "authoring_stylesheet", result.stylesheet)
                update_manifest_artifact(doc_id, "authoring_faker_profile", result.faker_profile)
                self._send_json(
                    {
                        "docId": doc_id,
                        "paths": _paths_to_client({"schema": result.schema, "stylesheet": result.stylesheet, "faker_profile": result.faker_profile}),
                        "consistency": consistency,
                        **result.payload,
                    }
                )
                return
            self._send_json({"error": f"Unknown endpoint: {parsed.path}"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - exercised by manual server use
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(path)
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._cors_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def list_output_batches() -> dict[str, Any]:
    batches: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for output_root in (ROOT / "outputs", RENDER_OUTPUT_ROOT):
        if not output_root.exists():
            continue
        for summary_path in sorted(output_root.glob("batch_*/summary.json")):
            resolved = summary_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                data = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            batches.append(
                {
                    "name": summary_path.parent.name,
                    "summary": _display_path(summary_path, ROOT),
                    "outDir": _display_path(summary_path.parent, ROOT),
                    "createdAt": data.get("created_at"),
                    "documentCount": data.get("document_count", 0),
                    "sampleCount": data.get("sample_count", 0),
                    "warningCount": data.get("warning_count", 0),
                }
            )
    return {"batches": batches}


def render_authoring_batch_for_work_items(
    *,
    doc_ids: list[str] | None,
    count: int,
    seed: int,
    out_dir: Path,
    render_scale: int = 2,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    registry = load_registry()
    items = list_work_items(registry=registry)
    requested = set(doc_ids or [])
    selected = [item for item in items if (not requested or item["docId"] in requested) and item.get("latestAuthoringSchema") and item.get("latestAuthoringStylesheet") and item.get("latestAuthoringFakerProfile")]
    if requested:
        found = {item["docId"] for item in selected}
        missing = sorted(requested - found)
        if missing:
            raise ValueError(f"authoring bundle not found for docIds: {', '.join(missing)}")
    if not selected:
        raise ValueError("no authoring-ready documents found")

    out_dir.mkdir(parents=True, exist_ok=True)
    root_manifest = out_dir / "manifest.jsonl"
    root_manifest.unlink(missing_ok=True)
    documents: list[dict[str, Any]] = []
    warning_count = 0
    sample_count = 0
    for doc_index, item in enumerate(selected, start=1):
        doc_id = str(item["docId"])
        _sync_authoring_template_from_work_item(item)
        doc_title = str(item.get("title") or doc_id)
        doc_out = out_dir / f"{_safe_name(doc_id)}_{_safe_name(doc_title)}"
        batch = render_authoring_batch(
            _resolve_workspace_path(str(item["latestAuthoringSchema"])),
            _resolve_workspace_path(str(item["latestAuthoringStylesheet"])),
            _resolve_workspace_path(str(item["latestAuthoringFakerProfile"])),
            out_dir=doc_out,
            count=count,
            seed=seed + (doc_index - 1) * 1000,
            clean=True,
            render_scale=render_scale,
            as_of_date=as_of_date,
        )
        update_manifest_artifact(doc_id, "authoring_batch", batch.summary, registry=registry)
        doc_payload = {
            "docId": doc_id,
            "title": doc_title,
            "outDir": _display_path(batch.out_dir, ROOT),
            "summary": _display_path(batch.summary, ROOT),
            "manifest": _display_path(batch.manifest, ROOT),
            "sampleCount": batch.sample_count,
            "fieldCount": batch.field_count,
            "warningCount": batch.warning_count,
            "firstImage": _display_path(batch.samples[0].image, ROOT) if batch.samples else "",
            "firstOverlay": _display_path(batch.samples[0].overlay, ROOT) if batch.samples else "",
        }
        documents.append(doc_payload)
        warning_count += batch.warning_count
        sample_count += batch.sample_count
        with root_manifest.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(doc_payload, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    summary_path = out_dir / "summary.json"
    summary_payload = {
        "schema_version": 1,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "outDir": _display_path(out_dir, ROOT),
        "document_count": len(documents),
        "sample_count": sample_count,
        "count_per_document": count,
        "warning_count": warning_count,
        "documents": documents,
    }
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "summary": {
            "documentCount": len(documents),
            "sampleCount": sample_count,
            "countPerDocument": count,
            "warningCount": warning_count,
        },
        "paths": {
            "outDir": _display_path(out_dir, ROOT),
            "summary": _display_path(summary_path, ROOT),
            "manifest": _display_path(root_manifest, ROOT),
        },
        "documents": documents,
    }


def _safe_name(value: str) -> str:
    name = "".join(ch if ch.isalnum() or ch in "가-힣_-()·" else "_" for ch in value).strip("_")
    while "__" in name:
        name = name.replace("__", "_")
    return name[:80] or "document"


def _query_path(query: str) -> Path:
    values = parse_qs(query).get("path")
    if not values:
        raise ValueError("missing query parameter: path")
    return _resolve_workspace_path(unquote(values[0]))


def _first_query_value(query: dict[str, list[str]], name: str) -> str:
    values = query.get(name)
    if not values:
        raise ValueError(f"missing query parameter: {name}")
    return unquote(values[0])


def _resolve_workspace_path(value: str | Path) -> Path:
    if not value:
        raise ValueError("empty path")
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise ValueError(f"path escapes workspace: {value}")
    return resolved


def _display_path(path: str | Path, root: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


def _paths_to_client(paths: dict[str, Path]) -> dict[str, str]:
    return {name: _display_path(path, ROOT) for name, path in paths.items()}


def _run_paddle_ocr_subprocess(image_path: Path, *, preset: str, out_dir: Path) -> dict[str, Any]:
    """Run PaddleOCR outside the long-lived API process.

    Paddle loads native worker threads that can segfault during Ctrl+C shutdown on
    macOS. Keeping it in a short-lived child process prevents the API server
    itself from importing libpaddle and makes normal GUI shutdown much quieter.
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    result_fd, result_name = tempfile.mkstemp(prefix="paddle_ocr_", suffix=".json", dir=out_dir)
    os.close(result_fd)
    result_path = Path(result_name)
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "datafactory.ocr_worker",
            "--image",
            str(image_path),
            "--engine",
            "paddleocr",
            "--preset",
            preset,
            "--out-dir",
            str(out_dir),
            "--result-json",
            str(result_path),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"PaddleOCR worker failed with exit code {completed.returncode}: {detail[-4000:]}")
    try:
        with result_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    finally:
        result_path.unlink(missing_ok=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("summary"), dict) or not isinstance(payload.get("paths"), dict):
        raise RuntimeError("PaddleOCR worker returned invalid metadata")
    return payload


def _run_paddle_crop_recognition_subprocess(crops_json: Path, *, preset: str, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    result_fd, result_name = tempfile.mkstemp(prefix="paddle_crop_ocr_", suffix=".json", dir=out_dir)
    os.close(result_fd)
    result_path = Path(result_name)
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "datafactory.ocr_worker",
            "--crops-json",
            str(crops_json),
            "--engine",
            "paddleocr",
            "--preset",
            preset,
            "--out-dir",
            str(out_dir),
            "--result-json",
            str(result_path),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"PaddleOCR crop worker failed with exit code {completed.returncode}: {detail[-4000:]}")
    try:
        with result_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    finally:
        result_path.unlink(missing_ok=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("summary"), dict) or not isinstance(payload.get("candidates"), list):
        raise RuntimeError("PaddleOCR crop worker returned invalid metadata")
    return payload


def _safe_template_id(path: Path) -> str:
    parent = path.parent.name
    if parent:
        return f"{parent}_{path.stem}"
    return path.stem


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the DataFactory React GUI backend API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DataFactoryRequestHandler)
    print(f"DataFactory API listening on http://{args.host}:{args.port}")
    print(f"Workspace root: {ROOT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - manual use
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
