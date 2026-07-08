from __future__ import annotations

import json
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry import RegistryData, RegistryDocument, load_registry, normalize_title, slugify_title

ROOT = Path(__file__).resolve().parents[2]
SEED_ROOT = ROOT / "seed_samples"
WORKBENCH_ROOT = ROOT / "workbench" / "documents"
SUPPORTED_SOURCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".tif", ".tiff", ".bmp", ".webp", ".docx"}
UPLOAD_SOURCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".docx"}
IMAGE_SOURCE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
EDITABLE_OFFICE_EXTENSIONS = {".docx"}
STATUS_LABELS = {
    "missing": "미적재",
    "sample_imported": "샘플 적재됨",
    "ocr_done": "BBox 완료",
    "review_done": "리뷰 완료",
    "inpaint_done": "인페인팅 완료",
    "cleanroom_sample_ready": "클린룸 완료",
    "collection_done": "수집 완료",
    "approved": "검수 완료",
}
INTAKE_STATUS_LABELS = {
    "importable": "자동 적재 가능",
    "needsReview": "확인 필요",
    "alreadyImported": "이미 적재됨",
}
SAMPLE_KINDS = {"filled_sample", "blank_template", "mixed_template"}

PROTECTED_TARGET_GROUP_IDS = {"first_priority"}


@dataclass(frozen=True)
class MatchCandidate:
    doc_id: str
    title: str
    score: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"docId": self.doc_id, "title": self.title, "score": self.score, "reason": self.reason}


def document_dir(doc: RegistryDocument, root: Path = WORKBENCH_ROOT) -> Path:
    return root / f"{slugify_title(doc.title)}__{doc.doc_id}"


def manifest_path(doc: RegistryDocument, root: Path = WORKBENCH_ROOT) -> Path:
    return document_dir(doc, root) / "manifest.json"


def seed_mappings_path(root: Path = WORKBENCH_ROOT) -> Path:
    return root.parent / "seed_mappings.json"


def target_groups_path(root: Path = WORKBENCH_ROOT) -> Path:
    return root.parent / "target_groups.json"


def default_target_groups(registry: RegistryData) -> list[dict[str, Any]]:
    return [
        {
            "id": "first_priority",
            "label": "기존 1차 목표",
            "description": "현재 authoring/생성 가능성 판정 기본 대상 그룹입니다.",
            "protected": True,
            "scopeEntries": [
                {
                    "domain": domain,
                    "docId": doc_id,
                    "title": registry.documents[doc_id].title if doc_id in registry.documents else "",
                }
                for domain, doc_id in registry.first_priority_scope_entries
            ],
        }
    ]


def list_target_groups(registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    registry = registry or load_registry()
    payload = _load_target_groups_payload(root=root)
    hidden_default_ids = set(payload.get("hidden_default_ids") or [])
    custom = _load_custom_target_groups(registry, root=root)
    defaults = [group for group in default_target_groups(registry) if group["id"] not in hidden_default_ids]
    groups = [*defaults, *custom]
    return {
        "path": _display_path(target_groups_path(root)),
        "groups": groups,
        "summary": {
            "defaultCount": len(defaults),
            "hiddenDefaultCount": len(hidden_default_ids),
            "customCount": len(custom),
            "groupCount": len(groups),
        },
    }


def save_target_group(payload: dict[str, Any], registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    registry = registry or load_registry()
    label = str(payload.get("label") or "").strip()
    if not label:
        raise ValueError("target group label is required")
    group_id = str(payload.get("id") or "").strip() or f"grp_{slugify_title(label)}"
    group_id = _safe_group_id(group_id)
    if group_id in PROTECTED_TARGET_GROUP_IDS:
        raise ValueError(f"protected target group cannot be modified: {group_id}")
    scope_entries = _normalize_target_scope_entries(payload.get("scopeEntries"), registry)
    if not scope_entries:
        raise ValueError("target group requires at least one document")
    group = {
        "id": group_id,
        "label": label,
        "description": str(payload.get("description") or "").strip(),
        "protected": False,
        "scopeEntries": scope_entries,
        "updatedAt": _now(),
    }
    existing_payload = _load_target_groups_payload(root=root)
    hidden_default_ids = list(existing_payload.get("hidden_default_ids") or [])
    custom = [item for item in _load_custom_target_groups(registry, root=root) if item.get("id") != group_id]
    custom.append(group)
    custom.sort(key=lambda item: (str(item.get("label") or ""), str(item.get("id") or "")))
    _write_json(target_groups_path(root), {"schema_version": 1, "hidden_default_ids": hidden_default_ids, "groups": custom, "updated_at": _now()})
    return {"group": group, **list_target_groups(registry, root=root)}


def delete_target_group(group_id: str, registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    registry = registry or load_registry()
    group_id = _safe_group_id(group_id)
    if group_id in PROTECTED_TARGET_GROUP_IDS:
        payload = _load_target_groups_payload(root=root)
        hidden_default_ids = list(dict.fromkeys([*(payload.get("hidden_default_ids") or []), group_id]))
        custom = _load_custom_target_groups(registry, root=root)
        _write_json(target_groups_path(root), {"schema_version": 1, "hidden_default_ids": hidden_default_ids, "groups": custom, "updated_at": _now()})
        return list_target_groups(registry, root=root)
    payload = _load_target_groups_payload(root=root)
    hidden_default_ids = list(payload.get("hidden_default_ids") or [])
    custom = _load_custom_target_groups(registry, root=root)
    next_groups = [item for item in custom if item.get("id") != group_id]
    if len(next_groups) == len(custom):
        raise ValueError(f"target group not found: {group_id}")
    _write_json(target_groups_path(root), {"schema_version": 1, "hidden_default_ids": hidden_default_ids, "groups": next_groups, "updated_at": _now()})
    return list_target_groups(registry, root=root)


def _load_target_groups_payload(root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    path = target_groups_path(root)
    if not path.exists():
        return {"schema_version": 1, "hidden_default_ids": [], "groups": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": 1, "hidden_default_ids": [], "groups": []}
    if not isinstance(payload, dict):
        return {"schema_version": 1, "hidden_default_ids": [], "groups": []}
    if not isinstance(payload.get("groups"), list):
        payload["groups"] = []
    if not isinstance(payload.get("hidden_default_ids"), list):
        payload["hidden_default_ids"] = []
    return payload


def _load_custom_target_groups(registry: RegistryData, root: Path = WORKBENCH_ROOT) -> list[dict[str, Any]]:
    payload = _load_target_groups_payload(root=root)
    raw_groups = payload.get("groups") if isinstance(payload, dict) else []
    groups: list[dict[str, Any]] = []
    for raw in raw_groups if isinstance(raw_groups, list) else []:
        if not isinstance(raw, dict):
            continue
        group_id = _safe_group_id(str(raw.get("id") or ""))
        if not group_id or group_id in PROTECTED_TARGET_GROUP_IDS:
            continue
        label = str(raw.get("label") or group_id).strip()
        scope_entries = _normalize_target_scope_entries(raw.get("scopeEntries"), registry)
        if not scope_entries:
            continue
        groups.append(
            {
                "id": group_id,
                "label": label,
                "description": str(raw.get("description") or "").strip(),
                "protected": False,
                "scopeEntries": scope_entries,
                "updatedAt": str(raw.get("updatedAt") or raw.get("updated_at") or ""),
            }
        )
    return groups


def _normalize_target_scope_entries(raw_entries: Any, registry: RegistryData) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    if not isinstance(raw_entries, list):
        return entries
    for raw in raw_entries:
        if isinstance(raw, str):
            doc_id = raw
            domain = ""
        elif isinstance(raw, dict):
            doc_id = str(raw.get("docId") or raw.get("doc_id") or "").strip()
            domain = str(raw.get("domain") or "").strip()
        else:
            continue
        if doc_id not in registry.documents:
            continue
        key = (domain, doc_id)
        if key in seen:
            continue
        seen.add(key)
        doc = registry.documents[doc_id]
        entries.append({"domain": domain, "docId": doc_id, "title": doc.title})
    return entries


def _safe_group_id(value: str) -> str:
    normalized = slugify_title(value).strip("_").lower()
    return normalized[:80]


def scan_seed_samples(seed_root: Path = SEED_ROOT, registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    registry = registry or load_registry()
    mappings = load_seed_mappings(root=root)
    folders: list[dict[str, Any]] = []
    summary = {"folderCount": 0, "matched": 0, "unmatched": 0, "importable": 0, "needsReview": 0, "alreadyImported": 0}
    if not seed_root.exists():
        return {"seedRoot": str(seed_root), "summary": summary, "folders": []}
    for folder in sorted((path for path in seed_root.iterdir() if path.is_dir() and not path.name.startswith(".")), key=lambda item: item.name):
        files = _source_files(folder)
        candidates = match_seed_folder(folder.name, registry, mappings=mappings)
        matched_doc_id = candidates[0].doc_id if len(candidates) == 1 and candidates[0].score >= 80 else None
        match_status = "matched" if matched_doc_id else "unmatched"
        intake_status = "needsReview"
        if matched_doc_id:
            intake_status = "alreadyImported" if _seed_folder_imported(folder, matched_doc_id, registry, root) else "importable"
        summary["folderCount"] += 1
        summary["matched" if matched_doc_id else "unmatched"] += 1
        summary[intake_status] += 1
        folders.append(
            {
                "folder": _display_path(folder),
                "name": folder.name,
                "fileCount": len(files),
                "files": [_display_path(path) for path in files],
                "status": intake_status,
                "statusLabel": INTAKE_STATUS_LABELS[intake_status],
                "matchStatus": match_status,
                "matchedDocId": matched_doc_id,
                "matchedTitle": registry.documents[matched_doc_id].title if matched_doc_id else None,
                "candidates": [candidate.to_dict() for candidate in candidates[:8]],
            }
        )
    return {"seedRoot": str(seed_root), "summary": summary, "folders": folders}


def match_seed_folder(folder_name: str, registry: RegistryData, *, mappings: dict[str, Any] | None = None) -> list[MatchCandidate]:
    folder_key = normalize_title(folder_name)
    if not folder_key:
        return []
    mappings = mappings or {}
    mapped_doc_id = mappings.get("byNormalizedName", {}).get(folder_key, {}).get("docId")
    if mapped_doc_id in registry.documents:
        doc = registry.documents[mapped_doc_id]
        return [MatchCandidate(doc_id=doc.doc_id, title=doc.title, score=100, reason="저장된 수동 매핑")]

    candidates: list[MatchCandidate] = []
    for doc in registry.documents.values():
        names = [doc.title, *doc.aliases]
        best: MatchCandidate | None = None
        for name in names:
            key = normalize_title(name)
            if not key:
                continue
            score = 0
            reason = ""
            if folder_key == key:
                score, reason = 100, "문서명/별칭과 정확히 일치"
            elif folder_key in key and len(folder_key) >= 3:
                score, reason = 88, "seed 폴더명이 문서명/별칭에 포함"
            elif key in folder_key and len(key) >= 3:
                score, reason = 85, "문서명/별칭이 seed 폴더명에 포함"
            else:
                overlap = _char_overlap(folder_key, key)
                if overlap >= 0.72 and min(len(folder_key), len(key)) >= 4:
                    score, reason = int(overlap * 70), "문자 유사도 후보"
            if score > 0 and (best is None or score > best.score):
                best = MatchCandidate(doc_id=doc.doc_id, title=doc.title, score=score, reason=reason)
        if best is not None:
            candidates.append(best)
    candidates.sort(key=lambda item: (-item.score, item.title, item.doc_id))
    if candidates and candidates[0].score >= 100:
        return [candidate for candidate in candidates if candidate.score == 100]
    return candidates


def import_seed_folder(seed_folder: Path, doc_id: str, registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT, *, remember_mapping: bool = False) -> dict[str, Any]:
    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    seed_folder = seed_folder.resolve()
    if not seed_folder.exists() or not seed_folder.is_dir():
        raise FileNotFoundError(seed_folder)
    render_info = render_missing_seed_pdf_pages(seed_folder)
    doc_root = document_dir(doc, root)
    sample_root = doc_root / "samples" / "original"
    sample_root.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(doc_root) or _base_manifest(doc, doc_root, registry)
    imported_sources = {sample.get("source") for sample in manifest.get("samples", []) if isinstance(sample, dict)}
    copied: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for source in _source_files(seed_folder):
        source_display = _display_path(source)
        if source_display in imported_sources:
            skipped.append({"path": _existing_sample_path(manifest, source_display) or "", "source": source_display, "reason": "already_imported"})
            continue
        relative = source.relative_to(seed_folder)
        destination = _unique_destination(sample_root / relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        item = _sample_manifest_item(destination, source)
        copied.append(item)
        imported_sources.add(source_display)
    manifest = _merge_manifest(doc, doc_root, seed_folder, copied, registry, existing_manifest=manifest)
    _write_json(doc_root / "manifest.json", manifest)
    if remember_mapping:
        save_seed_mapping(seed_folder.name, doc_id, registry=registry, root=root)
    return {
        "docId": doc.doc_id,
        "title": doc.title,
        "documentDir": _display_path(doc_root),
        "copied": copied,
        "skipped": skipped,
        "rendered": render_info["rendered"],
        "renderSkipped": render_info["skipped"],
        "warnings": render_info["warnings"],
        "manifest": manifest,
    }


def import_seed_batch(items: list[dict[str, Any]], registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    registry = registry or load_registry()
    results: list[dict[str, Any]] = []
    for item in items:
        seed_folder = Path(str(item.get("seedFolder") or ""))
        if not seed_folder.is_absolute():
            seed_folder = ROOT / seed_folder
        doc_id = str(item.get("docId") or "")
        if not doc_id:
            raise ValueError("each batch item requires docId")
        results.append(import_seed_folder(seed_folder, doc_id, registry=registry, root=root, remember_mapping=bool(item.get("rememberMapping"))))
    return {
        "summary": {
            "requested": len(items),
            "succeeded": len(results),
            "copied": sum(len(result.get("copied", [])) for result in results),
            "skipped": sum(len(result.get("skipped", [])) for result in results),
            "rendered": sum(len(result.get("rendered", [])) for result in results),
            "warnings": sum(len(result.get("warnings", [])) for result in results),
        },
        "results": results,
    }


def save_uploaded_seed_files(
    doc_id: str,
    files: list[dict[str, Any]],
    *,
    registry: RegistryData | None = None,
    seed_root: Path = SEED_ROOT,
    root: Path = WORKBENCH_ROOT,
) -> dict[str, Any]:
    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    if not files:
        raise ValueError("files are required")

    seed_folder = seed_root / slugify_title(doc.title)
    seed_folder.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, Any]] = []
    rendered: list[dict[str, Any]] = []
    warnings: list[str] = []

    for item in files:
        name = str(item.get("name") or "").strip()
        data = item.get("bytes")
        if not name:
            raise ValueError("uploaded file name is required")
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError(f"uploaded file has no bytes: {name}")
        destination = _unique_destination(seed_folder / _safe_file_name(name))
        suffix = destination.suffix.lower()
        if suffix not in UPLOAD_SOURCE_EXTENSIONS:
            raise ValueError(f"unsupported upload extension: {suffix}")
        destination.write_bytes(bytes(data))
        saved_item = {"path": _display_path(destination), "name": destination.name, "bytes": len(data)}
        saved.append(saved_item)
        if suffix == ".pdf":
            try:
                rendered_pages = render_pdf_pages(destination)
                rendered.extend({"path": _display_path(path), "source": saved_item["path"], "page": index + 1} for index, path in enumerate(rendered_pages))
            except Exception as exc:  # pragma: no cover - depends on optional PDF runtime
                warnings.append(f"PDF 렌더링 실패: {destination.name} · {exc}")

    import_result = import_seed_folder(seed_folder, doc.doc_id, registry=registry, root=root, remember_mapping=True)
    rendered.extend(import_result.get("rendered", []))
    warnings.extend(import_result.get("warnings", []))
    selected_sample = _first_image_path(import_result.get("copied", [])) or _first_image_path(import_result.get("manifest", {}).get("samples", []))
    return {
        "docId": doc.doc_id,
        "title": doc.title,
        "seedFolder": _display_path(seed_folder),
        "saved": saved,
        "rendered": rendered,
        "warnings": warnings,
        "import": import_result,
        "selectedSample": selected_sample,
    }


def render_pdf_pages(pdf_path: Path, *, scale: float = 2.0, image_format: str = "JPEG", quality: int = 92) -> list[Path]:
    try:
        import pypdfium2 as pdfium  # type: ignore
    except Exception as exc:  # pragma: no cover - optional runtime
        raise RuntimeError("pypdfium2가 설치되어 있지 않아 PDF를 이미지로 렌더링할 수 없습니다") from exc

    output_paths: list[Path] = []
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil().convert("RGB")
            destination = _unique_destination(pdf_path.with_name(f"{pdf_path.stem}_page_{index + 1:03d}.jpg"))
            image.save(destination, image_format, quality=quality)
            output_paths.append(destination)
            close = getattr(bitmap, "close", None)
            if callable(close):
                close()
            close = getattr(page, "close", None)
            if callable(close):
                close()
    finally:
        close = getattr(pdf, "close", None)
        if callable(close):
            close()
    return output_paths


def render_missing_seed_pdf_pages(seed_folder: Path) -> dict[str, Any]:
    rendered: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    warnings: list[str] = []
    for pdf_path in (path for path in _source_files(seed_folder) if path.suffix.lower() == ".pdf"):
        existing_pages = _rendered_pages_for_pdf(pdf_path)
        if existing_pages:
            skipped.append({"source": _display_path(pdf_path), "reason": "already_rendered", "pages": str(len(existing_pages))})
            continue
        try:
            rendered_pages = render_pdf_pages(pdf_path)
        except Exception as exc:  # pragma: no cover - depends on optional PDF runtime
            warnings.append(f"PDF 렌더링 실패: {pdf_path.name} · {exc}")
            continue
        rendered.extend({"path": _display_path(path), "source": _display_path(pdf_path), "page": index + 1} for index, path in enumerate(rendered_pages))
    return {"rendered": rendered, "skipped": skipped, "warnings": warnings}


def trash_seed_folder(seed_folder: Path, *, seed_root: Path = SEED_ROOT, root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    seed_root = seed_root.resolve()
    seed_folder = seed_folder.resolve()
    if seed_folder == seed_root or seed_root not in seed_folder.parents:
        raise ValueError("seed folder must be inside seed_samples")
    if not seed_folder.exists() or not seed_folder.is_dir():
        raise FileNotFoundError(seed_folder)
    trash_root = root.parent / ".trash" / "seed_samples"
    trash_root.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(trash_root / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{seed_folder.name}")
    shutil.move(str(seed_folder), str(destination))
    return {"name": seed_folder.name, "trashed": _display_path(seed_folder), "trashPath": _display_path(destination)}


def preview_seed_revert(doc_id: str, registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    doc_root = document_dir(doc, root)
    manifest = _read_manifest(doc_root) or _base_manifest(doc, doc_root, registry)
    removable: list[dict[str, Any]] = []
    for name in ("samples", "ocr", "review", "inpaint", "cleanup"):
        source = doc_root / name
        if not source.exists():
            continue
        files = [path for path in source.rglob("*") if path.is_file()]
        removable.append({"path": _display_path(source), "fileCount": len(files), "bytes": sum(path.stat().st_size for path in files)})
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    preserved_artifacts = sorted(str(key) for key in artifacts if str(key).startswith("authoring") or key == "cleanroom")
    return {
        "docId": doc.doc_id,
        "title": doc.title,
        "documentDir": _display_path(doc_root),
        "status": manifest.get("status", "missing"),
        "sampleCount": len(manifest.get("samples") or []),
        "sourceSeedFolders": list(manifest.get("source_seed_folders") or []),
        "willMove": removable,
        "willPreserveArtifacts": preserved_artifacts,
        "willResetStatusTo": "missing",
        "backupRoot": _display_path(root.parent / ".trash" / "seed_revert"),
    }



def revert_seed_import(doc_id: str, registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    """Move imported sample/pipeline artifacts aside and reset a document to sample-missing.

    The operation is intentionally non-destructive: directories and the previous
    manifest are moved/copied into workbench/.trash so manual work can be
    recovered if the user reverts the wrong document.
    """

    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    doc_root = document_dir(doc, root)
    manifest_path = doc_root / "manifest.json"
    manifest = _read_manifest(doc_root) or _base_manifest(doc, doc_root, registry)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    trash_root = root.parent / ".trash" / "seed_revert" / f"{timestamp}_{slugify_title(doc.title)}__{doc.doc_id}"
    trash_root.mkdir(parents=True, exist_ok=True)

    moved: list[dict[str, str]] = []
    for name in ("samples", "ocr", "review", "inpaint", "cleanup"):
        source = doc_root / name
        if not source.exists():
            continue
        destination = _unique_destination(trash_root / name)
        shutil.move(str(source), str(destination))
        moved.append({"from": _display_path(source), "to": _display_path(destination)})

    if manifest_path.exists():
        shutil.copy2(manifest_path, trash_root / "manifest.before_revert.json")

    preserved_artifacts = {}
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    for key, value in artifacts.items():
        if str(key).startswith("authoring") or key == "cleanroom":
            preserved_artifacts[key] = value
    manifest.update(
        {
            "source_seed_folders": [],
            "samples": [],
            "status": "missing",
            "updated_at": _now(),
            "artifacts": {"ocr": None, "review": None, "inpaint": None, **preserved_artifacts},
        }
    )
    doc_root.mkdir(parents=True, exist_ok=True)
    _write_json(manifest_path, manifest)
    return {
        "docId": doc.doc_id,
        "title": doc.title,
        "documentDir": _display_path(doc_root),
        "trashPath": _display_path(trash_root),
        "moved": moved,
        "manifest": manifest,
    }


def load_seed_mappings(root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    path = seed_mappings_path(root)
    if not path.exists():
        return {"schema_version": 1, "byNormalizedName": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": 1, "byNormalizedName": {}}
    if not isinstance(payload.get("byNormalizedName"), dict):
        payload["byNormalizedName"] = {}
    return payload


def save_seed_mapping(folder_name: str, doc_id: str, registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    key = normalize_title(folder_name)
    if not key:
        raise ValueError("folderName is empty after normalization")
    mappings = load_seed_mappings(root=root)
    mappings.setdefault("schema_version", 1)
    mappings.setdefault("byNormalizedName", {})[key] = {
        "folderName": folder_name,
        "docId": doc.doc_id,
        "title": doc.title,
        "updatedAt": _now(),
    }
    path = seed_mappings_path(root)
    _write_json(path, mappings)
    return mappings["byNormalizedName"][key]


def list_work_items(registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> list[dict[str, Any]]:
    registry = registry or load_registry()
    items: list[dict[str, Any]] = []
    for doc in sorted(registry.documents.values(), key=lambda item: (not item.is_first_priority, item.title, item.doc_id)):
        doc_root = document_dir(doc, root)
        manifest = _read_manifest(doc_root)
        samples = _sample_files(doc_root)
        artifact_flags = _artifact_flags(doc_root, manifest)
        status = _derive_status(manifest, samples, artifact_flags)
        items.append(
            {
                "docId": doc.doc_id,
                "title": doc.title,
                "documentDir": _display_path(doc_root),
                "status": status,
                "statusLabel": STATUS_LABELS[status],
                "sampleCount": len(samples),
                "samples": [_display_path(path) for path in samples],
                "sampleKind": str(manifest.get("sample_kind") or "filled_sample"),
                "sampleGenerationPaths": list(manifest.get("sample_generation_paths") or []),
                "hasEditableOfficeTemplate": "editable-office-template" in set(manifest.get("sample_generation_paths") or []),
                "officeRender": manifest.get("office_render") or {"required": False, "backend": "none", "status": "not_required"},
                "hasOcr": artifact_flags["has_ocr"],
                "hasReview": artifact_flags["has_review"],
                "hasInpaint": artifact_flags["has_inpaint"],
                "hasInpaintCleanup": artifact_flags["has_inpaint_cleanup"],
                "hasAuthoring": artifact_flags["has_authoring"],
                "hasAuthoringPreview": artifact_flags["has_authoring_preview"],
                "latestDetections": artifact_flags.get("latest_detections"),
                "latestReview": artifact_flags.get("latest_review"),
                "latestInpaintComparison": artifact_flags.get("latest_inpaint_comparison"),
                "latestInpainted": artifact_flags.get("latest_inpainted"),
                "latestInpaintCleanupComparison": artifact_flags.get("latest_inpaint_cleanup_comparison"),
                "latestInpaintCleanupMask": artifact_flags.get("latest_inpaint_cleanup_mask"),
                "latestAuthoringSchema": artifact_flags.get("latest_authoring_schema"),
                "latestAuthoringStylesheet": artifact_flags.get("latest_authoring_stylesheet"),
                "latestAuthoringFakerProfile": artifact_flags.get("latest_authoring_faker_profile"),
                "latestAuthoringPreview": artifact_flags.get("latest_authoring_preview"),
                "latestAuthoringOverlay": artifact_flags.get("latest_authoring_overlay"),
                "latestAuthoringBatch": artifact_flags.get("latest_authoring_batch"),
                "latestAuthoringAgentRequest": artifact_flags.get("latest_authoring_agent_request"),
                "latestAuthoringAgentPrompt": artifact_flags.get("latest_authoring_agent_prompt"),
                "latestAuthoringAgentAnchorMap": artifact_flags.get("latest_authoring_agent_anchor_map"),
                "latestAuthoringAgentRun": artifact_flags.get("latest_authoring_agent_run"),
                "latestAuthoringAgentSchemaDraft": artifact_flags.get("latest_authoring_agent_schema_draft"),
                "latestAuthoringAgentFakerProfileDraft": artifact_flags.get("latest_authoring_agent_faker_profile_draft"),
                "latestAuthoringAgentResearchReport": artifact_flags.get("latest_authoring_agent_research_report"),
                "latestDocxAnalysis": artifact_flags.get("latest_docx_analysis"),
                "latestDocxAnchorMap": artifact_flags.get("latest_docx_anchor_map"),
                "latestDocxRunManifest": artifact_flags.get("latest_docx_run_manifest"),
                "latestDocxValues": artifact_flags.get("latest_docx_values"),
                "latestDocxGt": artifact_flags.get("latest_docx_gt"),
                "latestDocxFilledDocx": artifact_flags.get("latest_docx_filled_docx"),
                "latestDocxRenderedPdf": artifact_flags.get("latest_docx_rendered_pdf"),
                "latestDocxPageImages": artifact_flags.get("latest_docx_page_images"),
                "latestDocxBbox": artifact_flags.get("latest_docx_bbox"),
                "latestDocxLabels": artifact_flags.get("latest_docx_labels"),
                "latestCleanroomPreview": artifact_flags.get("latest_cleanroom_preview"),
                "latestCleanroomPdf": artifact_flags.get("latest_cleanroom_pdf"),
                "latestCleanroomContactSheet": artifact_flags.get("latest_cleanroom_contact_sheet"),
                "latestCleanroomNotes": artifact_flags.get("latest_cleanroom_notes"),
                "manifest": manifest,
                "registry": doc.to_dict(),
            }
        )
    return items


def update_manifest_artifact(doc_id: str, artifact: str, path: str | Path, registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> None:
    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        return
    doc_root = document_dir(doc, root)
    manifest = _read_manifest(doc_root)
    if not manifest:
        manifest = _base_manifest(doc, doc_root, registry)
    artifacts = manifest.setdefault("artifacts", {})
    artifacts[artifact] = _display_path(path)
    manifest["updated_at"] = _now()
    _write_json(doc_root / "manifest.json", manifest)


def set_manifest_sample_kind(doc_id: str, sample_kind: str, registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    if sample_kind not in SAMPLE_KINDS:
        raise ValueError(f"sampleKind must be one of {sorted(SAMPLE_KINDS)}")
    doc_root = document_dir(doc, root)
    manifest = _read_manifest(doc_root) or _base_manifest(doc, doc_root, registry)
    manifest["sample_kind"] = sample_kind
    manifest["updated_at"] = _now()
    doc_root.mkdir(parents=True, exist_ok=True)
    _write_json(doc_root / "manifest.json", manifest)
    return manifest


def workbench_subdir(doc_id: str, subdir: str, registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> Path:
    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    target = document_dir(doc, root) / subdir
    target.mkdir(parents=True, exist_ok=True)
    return target


def _seed_folder_imported(seed_folder: Path, doc_id: str, registry: RegistryData, root: Path) -> bool:
    doc = registry.documents.get(doc_id)
    if doc is None:
        return False
    manifest = _read_manifest(document_dir(doc, root))
    if not manifest:
        return False
    seed_display = _display_path(seed_folder)
    if seed_display in set(manifest.get("source_seed_folders") or []):
        return True
    sources = {sample.get("source") for sample in manifest.get("samples", []) if isinstance(sample, dict)}
    source_files = {_display_path(path) for path in _source_files(seed_folder)}
    return bool(source_files) and source_files.issubset(sources)


def _merge_manifest(doc: RegistryDocument, doc_root: Path, seed_folder: Path, copied: list[dict[str, str]], registry: RegistryData, *, existing_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = existing_manifest or _read_manifest(doc_root) or _base_manifest(doc, doc_root, registry)
    source_folders = list(manifest.get("source_seed_folders") or [])
    seed_display = _display_path(seed_folder)
    if seed_display not in source_folders:
        source_folders.append(seed_display)
    samples_by_source = {sample.get("source"): sample for sample in manifest.get("samples", []) if isinstance(sample, dict) and sample.get("source")}
    for item in copied:
        samples_by_source[item["source"]] = item
    samples = list(samples_by_source.values())
    generation_paths = sorted({str(sample.get("generation_path") or "image-template") for sample in samples if isinstance(sample, dict)})
    editable_samples = [sample for sample in samples if isinstance(sample, dict) and sample.get("generation_path") == "editable-office-template"]
    manifest.update(
        {
            "source_seed_folders": source_folders,
            "samples": samples,
            "sample_generation_paths": generation_paths,
            "office_render": _office_render_manifest_state(editable_samples),
            "status": "sample_imported",
            "updated_at": _now(),
        }
    )
    return manifest


def _base_manifest(doc: RegistryDocument, doc_root: Path, registry: RegistryData) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "doc_id": doc.doc_id,
        "title": doc.title,
        "folder": _display_path(doc_root),
        "registry": doc.to_dict(),
        "source_seed_folders": [],
        "samples": [],
        "sample_kind": "filled_sample",
        "sample_generation_paths": [],
        "office_render": {"required": False, "backend": "none", "status": "not_required"},
        "status": "missing",
        "created_at": _now(),
        "updated_at": _now(),
        "artifacts": {"ocr": None, "review": None, "inpaint": None},
    }


def _source_files(folder: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in folder.rglob("*")
            if path.is_file() and not path.name.startswith(".") and path.suffix.lower() in SUPPORTED_SOURCE_EXTENSIONS
        ),
        key=lambda item: str(item),
    )


def _rendered_pages_for_pdf(pdf_path: Path) -> list[Path]:
    return sorted(pdf_path.parent.glob(f"{pdf_path.stem}_page_*.jpg"))


def _sample_generation_path(path: Path) -> str:
    return "editable-office-template" if path.suffix.lower() in EDITABLE_OFFICE_EXTENSIONS else "image-template"


def _sample_manifest_item(destination: Path, source: Path) -> dict[str, Any]:
    generation_path = _sample_generation_path(source)
    item: dict[str, Any] = {
        "path": _display_path(destination),
        "source": _display_path(source),
        "format": source.suffix.lower().lstrip("."),
        "generation_path": generation_path,
    }
    if generation_path == "editable-office-template":
        item["office_render"] = {
            "backend": "libreoffice-cli",
            "status": "external_render_required",
            "message": "DOCX 템플릿 렌더링은 LibreOffice CLI 기반 실험 경로입니다. 폰트 재현 문제가 해결되기 전까지 주 합성 파이프라인으로 사용하지 않습니다.",
        }
        item["lineage"] = {
            "original_template": _display_path(source),
            "imported_template": _display_path(destination),
            "filled_docx": "",
            "rendered_pdf": "",
            "page_images": [],
            "bbox_label_gt": [],
        }
    return item


def _office_render_manifest_state(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {"required": False, "backend": "none", "status": "not_required"}
    pending = [sample for sample in samples if (sample.get("office_render") or {}).get("status") != "rendered"]
    return {
        "required": True,
        "backend": "libreoffice-cli",
        "status": "external_render_required" if pending else "rendered",
        "template_count": len(samples),
        "pending_count": len(pending),
    }


def _first_image_path(items: list[dict[str, Any]]) -> str:
    for item in items:
        path = str(item.get("path") or "")
        if Path(path).suffix.lower() in IMAGE_SOURCE_EXTENSIONS:
            return path
    return ""


def _sample_files(doc_root: Path) -> list[Path]:
    sample_root = doc_root / "samples" / "original"
    if not sample_root.exists():
        return []
    return _source_files(sample_root)


def _artifact_flags(doc_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    ocr_paths = _mtime_sorted((doc_root / "ocr").glob("**/detections.json")) if (doc_root / "ocr").exists() else []
    review_paths = _mtime_sorted((doc_root / "review").glob("**/review.json")) if (doc_root / "review").exists() else []
    inpaint_paths = _mtime_sorted(
        path for path in (doc_root / "inpaint").glob("**/comparison_*.png") if "manual_cleanup" not in path.parts
    ) if (doc_root / "inpaint").exists() else []
    inpainted_paths = _mtime_sorted(
        path for path in (doc_root / "inpaint").glob("**/inpainted_*.png") if "manual_cleanup" not in path.parts
    ) if (doc_root / "inpaint").exists() else []
    cleanup_comparison_paths = _mtime_sorted(
        {*((doc_root / "inpaint").glob("**/manual_cleanup/comparison_*.png")), *((doc_root / "inpaint").glob("**/manual_cleanup/comparison_paint.png"))}
    ) if (doc_root / "inpaint").exists() else []
    cleanup_inpainted_paths = _mtime_sorted(
        {*((doc_root / "inpaint").glob("**/manual_cleanup/inpainted_*.png")), *((doc_root / "inpaint").glob("**/manual_cleanup/painted_template.png"))}
    ) if (doc_root / "inpaint").exists() else []
    cleanup_mask_paths = _mtime_sorted(
        {*((doc_root / "inpaint").glob("**/manual_cleanup/manual_mask.png")), *((doc_root / "inpaint").glob("**/manual_cleanup/paint.json"))}
    ) if (doc_root / "inpaint").exists() else []
    authoring_schema_paths = sorted((doc_root / "authoring").glob("schema.json")) if (doc_root / "authoring").exists() else []
    authoring_stylesheet_paths = sorted((doc_root / "authoring").glob("stylesheet.json")) if (doc_root / "authoring").exists() else []
    authoring_faker_paths = sorted((doc_root / "authoring").glob("faker_profile.json")) if (doc_root / "authoring").exists() else []
    authoring_preview_paths = (
        sorted(path for path in (doc_root / "authoring" / "render_preview").glob("preview_*.png") if ".overlay." not in path.name)
        if (doc_root / "authoring" / "render_preview").exists()
        else []
    )
    authoring_overlay_paths = sorted((doc_root / "authoring" / "render_preview").glob("preview_*.overlay.png")) if (doc_root / "authoring" / "render_preview").exists() else []
    authoring_agent_request_paths = sorted((doc_root / "authoring" / "agent_requests").glob("*/request.json")) if (doc_root / "authoring" / "agent_requests").exists() else []
    latest_agent_request_dir = authoring_agent_request_paths[-1].parent if authoring_agent_request_paths else None
    latest_agent_prompt = latest_agent_request_dir / "request.md" if latest_agent_request_dir else None
    latest_agent_anchor_map = latest_agent_request_dir / "anchor_map_draft.json" if latest_agent_request_dir else None
    authoring_agent_run_paths = sorted((doc_root / "authoring" / "agent_runs").glob("*/job.json")) if (doc_root / "authoring" / "agent_runs").exists() else []
    artifacts = manifest.get("artifacts", {}) if isinstance(manifest, dict) else {}
    manifest_ocr = _existing_display_path(artifacts.get("ocr"))
    manifest_review = _existing_display_path(artifacts.get("review"))
    cleanroom = _cleanroom_artifact_flags(artifacts.get("cleanroom"))
    latest_inpaint_comparison_path = inpaint_paths[-1] if inpaint_paths else None
    latest_inpainted_path = inpainted_paths[-1] if inpainted_paths else None
    latest_cleanup_comparison_path = cleanup_comparison_paths[-1] if cleanup_comparison_paths else None
    latest_cleanup_inpainted_path = cleanup_inpainted_paths[-1] if cleanup_inpainted_paths else None
    cleanup_comparison = _display_path(latest_cleanup_comparison_path) if latest_cleanup_comparison_path else artifacts.get("inpaint_cleanup")
    cleanup_inpainted = _display_path(latest_cleanup_inpainted_path) if latest_cleanup_inpainted_path else artifacts.get("inpaint_cleanup_inpainted")
    cleanup_mask = _display_path(cleanup_mask_paths[-1]) if cleanup_mask_paths else artifacts.get("inpaint_cleanup_mask")
    return {
        "has_ocr": bool(ocr_paths or artifacts.get("ocr")),
        "has_review": bool(review_paths or artifacts.get("review")),
        "has_inpaint": bool(inpaint_paths or inpainted_paths or artifacts.get("inpaint")),
        "has_inpaint_cleanup": bool(cleanup_comparison or cleanup_inpainted or cleanup_mask),
        "has_authoring": bool(authoring_schema_paths or artifacts.get("authoring")),
        "has_authoring_preview": bool(authoring_preview_paths or artifacts.get("authoring_preview")),
        "latest_detections": manifest_ocr or (_display_path(ocr_paths[-1]) if ocr_paths else artifacts.get("ocr")),
        "latest_review": manifest_review or (_display_path(review_paths[-1]) if review_paths else artifacts.get("review")),
        "latest_inpaint_comparison": _display_path(latest_inpaint_comparison_path) if latest_inpaint_comparison_path else artifacts.get("inpaint"),
        "latest_inpainted": _display_path(latest_inpainted_path) if latest_inpainted_path else _inpainted_from_comparison(artifacts.get("inpaint")),
        "latest_inpaint_cleanup_comparison": cleanup_comparison,
        "latest_inpaint_cleanup_mask": cleanup_mask,
        "latest_authoring_schema": _display_path(authoring_schema_paths[-1]) if authoring_schema_paths else artifacts.get("authoring"),
        "latest_authoring_stylesheet": _display_path(authoring_stylesheet_paths[-1]) if authoring_stylesheet_paths else artifacts.get("authoring_stylesheet"),
        "latest_authoring_faker_profile": _display_path(authoring_faker_paths[-1]) if authoring_faker_paths else artifacts.get("authoring_faker_profile"),
        "latest_authoring_preview": _display_path(authoring_preview_paths[-1]) if authoring_preview_paths else artifacts.get("authoring_preview"),
        "latest_authoring_overlay": _display_path(authoring_overlay_paths[-1]) if authoring_overlay_paths else artifacts.get("authoring_overlay"),
        "latest_authoring_batch": artifacts.get("authoring_batch"),
        "latest_authoring_agent_request": _display_path(authoring_agent_request_paths[-1]) if authoring_agent_request_paths else artifacts.get("authoring_agent_request"),
        "latest_authoring_agent_prompt": _display_path(latest_agent_prompt) if latest_agent_prompt and latest_agent_prompt.exists() else artifacts.get("authoring_agent_prompt"),
        "latest_authoring_agent_anchor_map": _display_path(latest_agent_anchor_map) if latest_agent_anchor_map and latest_agent_anchor_map.exists() else artifacts.get("authoring_agent_anchor_map"),
        "latest_authoring_agent_run": _display_path(authoring_agent_run_paths[-1]) if authoring_agent_run_paths else artifacts.get("authoring_agent_run"),
        "latest_authoring_agent_schema_draft": artifacts.get("authoring_agent_schema_draft"),
        "latest_authoring_agent_faker_profile_draft": artifacts.get("authoring_agent_faker_profile_draft"),
        "latest_authoring_agent_research_report": artifacts.get("authoring_agent_research_report"),
        "latest_docx_analysis": artifacts.get("docx_analysis"),
        "latest_docx_anchor_map": artifacts.get("docx_anchor_map"),
        "latest_docx_run_manifest": artifacts.get("docx_run_manifest"),
        "latest_docx_values": artifacts.get("docx_values"),
        "latest_docx_gt": artifacts.get("docx_gt"),
        "latest_docx_filled_docx": artifacts.get("docx_filled_docx"),
        "latest_docx_rendered_pdf": artifacts.get("docx_rendered_pdf"),
        "latest_docx_page_images": artifacts.get("docx_page_images"),
        "latest_docx_bbox": artifacts.get("docx_bbox"),
        "latest_docx_labels": artifacts.get("docx_labels"),
        **cleanroom,
    }


def _cleanroom_artifact_flags(raw: Any) -> dict[str, str]:
    cleanroom = raw if isinstance(raw, dict) else {}
    pdf = _existing_display_path(cleanroom.get("pdf"))
    contact_sheet = _existing_display_path(cleanroom.get("contact_sheet"))
    notes = _existing_display_path(cleanroom.get("notes"))
    preview = _first_existing_cleanroom_page(cleanroom.get("pages_dir")) or contact_sheet or ""
    return {
        "latest_cleanroom_preview": preview,
        "latest_cleanroom_pdf": pdf,
        "latest_cleanroom_contact_sheet": contact_sheet,
        "latest_cleanroom_notes": notes,
    }


def _first_existing_cleanroom_page(value: Any) -> str:
    if not value:
        return ""
    directory = Path(str(value))
    if not directory.is_absolute():
        directory = ROOT / directory
    if not directory.exists() or not directory.is_dir():
        return ""
    candidates = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SOURCE_EXTENSIONS
    )
    return _display_path(candidates[0]) if candidates else ""


def _existing_display_path(value: Any) -> str:
    if not value:
        return ""
    path = Path(str(value))
    if not path.is_absolute():
        path = ROOT / path
    return _display_path(path) if path.exists() else ""


def _mtime_sorted(paths: Any) -> list[Path]:
    return sorted((path for path in paths if path.exists()), key=lambda path: (path.stat().st_mtime, str(path)))


def _derive_status(manifest: dict[str, Any], samples: list[Path], artifacts: dict[str, Any]) -> str:
    manifest_status = manifest.get("status")
    if manifest_status in {"approved", "cleanroom_sample_ready", "collection_done"}:
        return str(manifest_status)
    if artifacts["has_inpaint"]:
        return "inpaint_done"
    if artifacts["has_review"]:
        return "review_done"
    if artifacts["has_ocr"]:
        return "ocr_done"
    if samples or manifest.get("samples"):
        return "sample_imported"
    return "missing"


def _inpainted_from_comparison(path_value: Any) -> str | None:
    if not path_value:
        return None
    comparison = ROOT / str(path_value) if not Path(str(path_value)).is_absolute() else Path(str(path_value))
    if not comparison.name.startswith("comparison_"):
        return None
    candidate = comparison.with_name(comparison.name.replace("comparison_", "inpainted_", 1))
    if candidate.exists():
        return _display_path(candidate)
    return None


def _read_manifest(doc_root: Path) -> dict[str, Any]:
    path = doc_root / "manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 10_000):
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate destination for {path}")


def _safe_file_name(name: str) -> str:
    candidate = Path(name).name
    suffix = Path(candidate).suffix.lower()
    stem = Path(candidate).stem
    safe_stem = slugify_title(unicodedata.normalize("NFC", stem))
    return f"{safe_stem}{suffix}"


def _existing_sample_path(manifest: dict[str, Any], source_display: str) -> str | None:
    for sample in manifest.get("samples", []):
        if isinstance(sample, dict) and sample.get("source") == source_display:
            return str(sample.get("path") or "")
    return None


def _char_overlap(left: str, right: str) -> float:
    left_chars = set(left)
    right_chars = set(right)
    if not left_chars or not right_chars:
        return 0.0
    return len(left_chars & right_chars) / float(len(left_chars | right_chars))


def _display_path(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
