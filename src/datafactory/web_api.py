from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter
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
from .inpaint import InpaintConfig, InpaintResult, inpaint_from_review_policy, lama_inpaint, render_mask_overlay
from .inpaint_export import write_inpaint_result
from .manual_cleanup import load_manual_mask, save_manual_mask
from .ocr_detectors import PADDLEOCR_PRESETS, normalize_paddleocr_preset
from .ocr_worker import run_ocr_eval
from .policy import ReviewPolicy, draft_review_policy, load_review_policy, review_summary, write_review_policy
from .registry import load_registry
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
    trash_seed_folder,
    revert_seed_import,
    update_manifest_artifact,
    workbench_subdir,
)

ROOT = Path(__file__).resolve().parents[2]
RENDER_OUTPUT_ROOT = ROOT / "outputs" / "render"


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
            "office_com_backend": "external_render_required",
            "ocr_recrop_review": True,
            "first_priority_assessment": True,
            "final_results_export": True,
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
        "## Faker profile 규칙",
        *[f"- {rule}" for rule in contract["faker_profile_rules"]],
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
        "",
    ]
    return "\n".join(lines) + "\n"


def authoring_agent_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(payload.get("docId") or "")
    if not doc_id:
        raise ValueError("docId is required")
    registry = load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    item = next((candidate for candidate in list_work_items(registry=registry) if candidate.get("docId") == doc_id), None)
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
        "contract": {
            "mode": "agentic_authoring_a_to_z",
            "input_formats": ["pdf", "jpg", "jpeg", "png", "docx"],
            "generation_paths": ["image-template", "editable-office-template"],
            "outputs": outputs,
            "workflow_steps": [
                "입력 파일, OCR, bbox review, 기존 authoring 파일을 먼저 읽고 근거 anchor를 정리한다.",
                "실제 문서명을 웹 검색해 작성 방법, 문서 의미, 포함 정보, 실제 샘플 양식, 공식/공공/기관/기업 설명을 수집한다.",
                "문서에 보이는 anchor와 리서치 근거를 연결해 schema_draft와 faker_profile_draft를 작성한다.",
                "불확실하거나 출처가 충돌하는 항목은 확정하지 않고 uncertainty_report에 남긴다.",
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
                "KIE 관점의 key-value hierarchy만 작성한다.",
                "모든 value는 빈 문자열로 둔다.",
                "key는 실제 문서에 보이는 라벨, 표제, placeholder, 주변 텍스트, 편집 가능한 anchor 기반 한국어 자연어를 우선한다.",
                "문서에 보이지 않는 추상 키, 업무 추론만으로 만든 키, downstream 편의용 임의 구조체를 만들지 않는다.",
                "웹 리서치로 발견한 일반 항목이라도 대응 anchor가 없으면 schema_draft에 자동 추가하지 않는다.",
            ],
            "faker_profile_rules": [
                "schema key의 의미가 충분히 명확하고 문서 anchor 또는 리서치 근거와 연결될 때만 faker rule을 제안한다.",
                "문서 필드의 의미와 실제 작성 관행을 근거로 타입, 형식, 값 범위, 선택지, 단위, 날짜/금액/식별번호 규칙을 제안한다.",
                "의미가 불확실한 key는 literal:, choice:, pool: 등을 임의 생성하지 말고 보류 사유를 기록한다.",
                "실제 개인정보, 실제 기업정보, 실제 계좌/식별번호처럼 오인 가능한 값은 만들지 않는다.",
                "합성 더미 값 규칙 또는 승인된 value pool 참조만 사용한다.",
                "faker_profile_draft의 각 rule은 관련 schema key, anchor, research_report 근거 ID를 추적 가능하게 남긴다.",
            ],
            "template_anchor_rules": [
                "PDF/JPG는 visible text, OCR, bbox 위치, 주변 텍스트를 anchor 근거로 삼는다.",
                "DOCX는 visible text, content control, form field, table cell, bookmark, placeholder 등 편집 가능한 anchor를 근거로 삼는다.",
                "숨은 메타데이터나 파일명만으로 schema key 또는 faker rule을 만들지 않는다.",
                "DOCX 경로에서는 원본 템플릿, 채워진 DOCX, 렌더링 PDF, 페이지 이미지, bbox/label/GT lineage가 manifest에 남아야 한다.",
            ],
            "application_rules": [
                "렌더러는 authoring 데이터를 임의 보정하지 않고 schema/style/faker/render_policy를 그대로 따른다.",
                "Agent 산출물은 바로 적용하지 않고 draft로 저장한다.",
                "기존 authoring 파일을 덮어쓰기 전 사용자 승인과 백업 경로가 필요하다.",
                "UI 확정 전에는 schema_draft, faker_profile_draft, value_pool_draft, research_report, uncertainty_report를 함께 검토 가능해야 한다.",
            ],
        },
        "inputs": {
            "registry": doc.to_dict(),
            "sample": item.get("samples", [None])[0] if item else "",
            "latestDetections": item.get("latestDetections") if item else "",
            "latestReview": item.get("latestReview") if item else "",
            "latestInpainted": item.get("latestInpainted") if item else "",
            "existingAuthoring": {
                "schema": item.get("latestAuthoringSchema") if item else "",
                "stylesheet": item.get("latestAuthoringStylesheet") if item else "",
                "fakerProfile": item.get("latestAuthoringFakerProfile") if item else "",
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


def _clear_manifest_artifacts(doc_id: str, artifact_keys: list[str]) -> None:
    registry = load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        return
    manifest_path = document_dir(doc) / "manifest.json"
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
    update_manifest_artifact(doc_id, "inpaint_cleanup_mask", paths.manual_mask)
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
    paths = write_inpaint_result(result, cleanup_dir)
    paths["mask_json"] = mask_paths.mask_json
    paths["manual_mask"] = mask_paths.manual_mask
    _augment_cleanup_summary(paths["summary"], paths=paths, elapsed_seconds=elapsed_seconds)
    update_manifest_artifact(doc_id, "inpaint_cleanup", paths["comparison"])
    update_manifest_artifact(doc_id, "inpaint_cleanup_inpainted", paths["inpainted"])
    update_manifest_artifact(doc_id, "inpaint_cleanup_mask", mask_paths.manual_mask)
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
    }


def _cleanup_dir(doc_id: str, policy: ReviewPolicy) -> Path:
    return _resolve_workspace_path(workbench_subdir(doc_id, "inpaint") / _safe_template_id(policy.source_image) / "manual_cleanup")



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
        "inpainted": cleanup_dir / "painted_template.png",
        "comparison": cleanup_dir / "comparison_paint.png",
        "summary": cleanup_dir / "paint_summary.json",
    }


def load_cleanup_paint_payload(*, doc_id: str, review_path: Path, base_image_path: Path | None = None) -> dict[str, Any]:
    policy = load_review_policy(review_path)
    cleanup_dir = _cleanup_dir(doc_id, policy)
    base_path = base_image_path or _resolve_workspace_path(policy.source_image)
    if base_image_path is None:
        existing = cleanup_dir / "painted_template.png"
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
    update_manifest_artifact(doc_id, "inpaint_cleanup", paths["comparison"])
    update_manifest_artifact(doc_id, "inpaint_cleanup_inpainted", paths["inpainted"])
    update_manifest_artifact(doc_id, "inpaint_cleanup_mask", paths["paint_json"])
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
                self._send_json(
                    {
                        "paths": _paths_to_client({"schema": result.schema, "stylesheet": result.stylesheet, "faker_profile": result.faker_profile}),
                        **result.payload,
                    }
                )
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
                self._send_json(
                    {
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
                )
                return
            if parsed.path == "/api/review/draft":
                detections_path = _resolve_workspace_path(str(payload.get("detectionsPath") or ""))
                doc_id = str(payload.get("docId") or "")
                default_out_dir = workbench_subdir(doc_id, "review") if doc_id else Path("outputs/reviews")
                out_dir = _resolve_workspace_path(str(payload.get("outDir") or default_out_dir))
                policy = draft_review_policy(detections_path)
                draft_dir = out_dir / _safe_template_id(policy.source_image)
                backup = backup_review_draft_outputs(draft_dir)
                paths = write_review_policy(policy, draft_dir)
                if doc_id:
                    update_manifest_artifact(doc_id, "review", paths["review"])
                self._send_json({"docId": doc_id or None, "paths": _paths_to_client(paths), "policy": policy_to_client(policy, review_path=paths["review"]), "backup": backup})
                return
            if parsed.path == "/api/review/save":
                self._send_json(save_policy_payload(payload))
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
                    clean=bool(payload.get("clean", True)),
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
                result = render_authoring_live_preview(
                    raw_schema,
                    raw_stylesheet,
                    raw_faker_profile,
                    out_dir=RENDER_OUTPUT_ROOT / "live_preview" / _safe_name(doc_id),
                    seed=seed,
                    sample_id="live_preview",
                    render_scale=render_scale,
                )
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
