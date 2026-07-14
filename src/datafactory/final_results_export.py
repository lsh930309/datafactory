from __future__ import annotations

import hashlib
import html
import copy
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from PIL import Image

from .authoring import render_authoring_batch
from .first_priority_assessment import DOCUMENT_TYPES, FEASIBILITY_STATUSES, list_first_priority_assessments
from .handwriting import latest_accepted_handwriting_samples
from .library_sample import (
    LIBRARY_SAMPLE_DOMAINS,
    build_cleanroom_artifacts,
    fields_with_generators,
    resolve_pii_keys,
)
from .registry import RegistryData, load_registry, slugify_title
from .workbench import WORKBENCH_ROOT, list_work_items

ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = ROOT / "outputs" / "results"
BACKUP_ROOT = ROOT / ".bin" / "backups"


@dataclass(frozen=True)
class FinalExportOptions:
    count: int = 1
    out_dir: Path = RESULTS_ROOT
    seed: int = 20260703
    render_scale: int = 2
    clean: bool = True
    as_of_date: date | None = None


@dataclass(frozen=True)
class PipelineRenderResult:
    samples: list[dict[str, Path]]
    primary_schema: Path
    pii_keys: list[str]
    image_reports: list[dict[str, Any]]


def export_final_results(
    *,
    count: int = 1,
    out_dir: Path = RESULTS_ROOT,
    seed: int = 20260703,
    render_scale: int = 2,
    clean: bool = True,
    render_handwriting_as_printed: bool = False,
    as_of_date: date | None = None,
    scope_entries: Any | None = None,
    registry: RegistryData | None = None,
    root: Path = WORKBENCH_ROOT,
) -> dict[str, Any]:
    """Generate final deliverables for a selected scope without mutating workbench data."""

    if count <= 0:
        raise ValueError("count must be positive")
    as_of_date = as_of_date or date.today()
    registry = registry or load_registry()
    resolved_scope_entries = _resolve_scope_entries(scope_entries, registry=registry)
    out_dir = out_dir.resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = _prepare_results_dir(out_dir, run_id=run_id, clean=False)
    items_by_doc_id = {str(item["docId"]): item for item in list_work_items(registry=registry, root=root)}
    assessments = _assessment_rows_by_key(registry=registry, root=root)
    source_hashes = _source_hashes(items_by_doc_id)

    rows: list[dict[str, Any]] = []
    generated_documents: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    rendered_cache: dict[str, PipelineRenderResult] = {}
    cleanroom_cache: dict[str, PipelineRenderResult] = {}

    for scope_index, (domain, doc_id) in enumerate(resolved_scope_entries, start=1):
        doc = registry.documents.get(doc_id)
        item = items_by_doc_id.get(doc_id, {})
        title = doc.title if doc else str(item.get("title") or doc_id)
        doc_dir = out_dir / _safe_component(domain or "scope") / f"{_safe_component(doc_id)}_{slugify_title(title)}"
        assessment = assessments.get(f"{domain}::{doc_id}", {})
        row: dict[str, Any] = {
            "domain": domain,
            "index": scope_index,
            "docId": doc_id,
            "title": title,
            "documentType": str(assessment.get("documentType") or "unknown"),
            "documentTypeLabel": str(assessment.get("documentTypeLabel") or DOCUMENT_TYPES["unknown"]),
            "storedFeasibility": str(assessment.get("feasibility") or "unknown"),
            "storedFeasibilityLabel": str(assessment.get("feasibilityLabel") or FEASIBILITY_STATUSES["unknown"]),
            "outputDir": _display_path(doc_dir),
            "sampleCount": 0,
            "outputMode": "error",
            "outputType": "",
            "status": "ERROR",
            "message": "",
            "warnings": [],
            "warningCount": 0,
            "piiFileCount": 0,
            "imageReports": [],
        }
        try:
            mode = _resolve_output_mode(
                item,
                render_handwriting_as_printed=render_handwriting_as_printed,
                prefer_cleanroom=assessment.get("feasibility") == "impossible",
            )
            row["outputMode"] = mode
            row["temporaryPrintedHandwriting"] = bool(render_handwriting_as_printed and _is_handwriting_item(item) and mode == "pipeline")
            if mode == "pipeline":
                if doc_id not in rendered_cache:
                    rendered_cache[doc_id] = _render_pipeline_document(
                        item,
                        title=title,
                        count=count,
                        seed=seed + len(rendered_cache) * 1000,
                        render_scale=render_scale,
                        as_of_date=as_of_date,
                        work_dir=ROOT / ".bin" / "final_results_work" / run_id / f"{_safe_component(doc_id)}_{slugify_title(title)}",
                    )
                if clean and doc_dir.exists():
                    backup_dir = _backup_scope_output_dir(doc_dir, backup_dir=backup_dir, run_id=run_id)
                doc_dir.mkdir(parents=True, exist_ok=True)
                _copy_pipeline_samples(rendered_cache[doc_id], doc_dir)
                row["sampleCount"] = count
                row["piiFileCount"] = count if rendered_cache[doc_id].pii_keys else 0
                row["outputType"] = "jpg+json+bbox+schema" + ("+pii" if row["piiFileCount"] else "")
                row["generatedFileCount"] = sum(len(sample) for sample in rendered_cache[doc_id].samples) + 1
                row["imageReports"] = rendered_cache[doc_id].image_reports
            elif mode == "cleanroom_static":
                if doc_id not in cleanroom_cache:
                    cleanroom_cache[doc_id] = _render_cleanroom_document(
                        item,
                        work_dir=ROOT / ".bin" / "final_results_work" / run_id / f"{_safe_component(doc_id)}_{slugify_title(title)}_cleanroom",
                    )
                if clean and doc_dir.exists():
                    backup_dir = _backup_scope_output_dir(doc_dir, backup_dir=backup_dir, run_id=run_id)
                doc_dir.mkdir(parents=True, exist_ok=True)
                _copy_pipeline_samples(cleanroom_cache[doc_id], doc_dir)
                row["sampleCount"] = 1
                row["piiFileCount"] = 1 if cleanroom_cache[doc_id].pii_keys else 0
                row["outputType"] = "jpg+json+bbox+schema" + ("+pii" if row["piiFileCount"] else "")
                row["generatedFileCount"] = sum(len(sample) for sample in cleanroom_cache[doc_id].samples) + 1
                row["imageReports"] = cleanroom_cache[doc_id].image_reports
            elif mode == "handwriting":
                handwriting_work_dir = ROOT / ".bin" / "final_results_work" / run_id / f"{_safe_component(doc_id)}_{slugify_title(title)}_handwriting"
                handwriting_work_dir.mkdir(parents=True, exist_ok=True)
                copied = _copy_handwriting_samples(item, handwriting_work_dir, count=count)
                _validate_library_sample_directory(handwriting_work_dir, expected_sample_count=copied["sampleCount"])
                if clean and doc_dir.exists():
                    backup_dir = _backup_scope_output_dir(doc_dir, backup_dir=backup_dir, run_id=run_id)
                doc_dir.mkdir(parents=True, exist_ok=True)
                for path in handwriting_work_dir.iterdir():
                    if path.is_file():
                        shutil.copy2(path, doc_dir / path.name)
                row["sampleCount"] = copied["sampleCount"]
                row["piiFileCount"] = copied["piiFileCount"]
                row["outputType"] = "handwritten-scan+json+bbox+schema" + ("+pii" if row["piiFileCount"] else "")
                row["generatedFileCount"] = copied["generatedFileCount"]
                row["imageReports"] = copied["imageReports"]
            else:  # pragma: no cover - _resolve_output_mode currently raises.
                raise ValueError(f"unsupported output mode: {mode}")
            row["warnings"] = [
                *[warning for report in row["imageReports"] for warning in report.get("warnings", [])],
                *_deferred_multi_page_warnings(item, mode=mode),
            ]
            row["warningCount"] = len(row["warnings"])
            row["status"] = "OK"
            row["message"] = "generated" if not row["warnings"] else f"generated with {len(row['warnings'])} warning(s)"
            generated_documents.append(dict(row))
        except Exception as exc:  # Keep the export run useful even for partial failures.
            row["message"] = str(exc)
            errors.append({"domain": domain, "docId": doc_id, "title": title, "error": str(exc)})
        rows.append(row)

    changed_sources = _changed_sources(source_hashes)
    if changed_sources:
        _restore_changed_sources(changed_sources, backup_dir=backup_dir)
        errors.append({"domain": "", "docId": "", "title": "source_integrity", "error": f"source files changed and were restored: {len(changed_sources)}"})

    summary = _summary(rows, errors)
    manifest_path = out_dir / f"final_results_manifest_{run_id}.xlsx"
    _write_manifest_xlsx(manifest_path, rows, summary)
    summary_path = out_dir / "_run_summary.json"
    summary_payload = {
        "schema_version": 2,
        "run_id": run_id,
        "created_at": _now(),
        "as_of_date": as_of_date.isoformat(),
        "count_per_pipeline_document": count,
        "out_dir": _display_path(out_dir),
        "backup_dir": _display_path(backup_dir) if backup_dir else "",
        "manifest": _display_path(manifest_path),
        "render_handwriting_as_printed": bool(render_handwriting_as_printed),
        "summary": summary,
        "documents": rows,
        "errors": errors,
    }
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "summary": summary,
        "paths": {
            "outDir": _display_path(out_dir),
            "manifest": _display_path(manifest_path),
            "summary": _display_path(summary_path),
            "backupDir": _display_path(backup_dir) if backup_dir else "",
        },
        "documents": rows,
        "errors": errors,
    }


def _resolve_scope_entries(scope_entries: Any | None, *, registry: RegistryData) -> tuple[tuple[str, str], ...]:
    if scope_entries is None:
        defaults = tuple(
            (domain, doc.doc_id)
            for doc in sorted(registry.documents.values(), key=lambda item: (item.title, item.doc_id))
            for domain in doc.po_domains
            if domain in LIBRARY_SAMPLE_DOMAINS
        )
        if not defaults:
            raise ValueError("registry has no documents in supported library-sample domains")
        return defaults
    if not isinstance(scope_entries, list):
        raise ValueError("scope_entries must be a list")
    resolved: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in scope_entries:
        if isinstance(raw, str):
            domain = ""
            doc_id = raw.strip()
        elif isinstance(raw, dict):
            domain = str(raw.get("domain") or "").strip()
            doc_id = str(raw.get("docId") or raw.get("doc_id") or "").strip()
        else:
            continue
        if not doc_id or doc_id not in registry.documents:
            continue
        if domain not in LIBRARY_SAMPLE_DOMAINS:
            raise ValueError(f"unsupported library-sample domain: {domain}")
        key = (domain, doc_id)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(key)
    if not resolved:
        raise ValueError("scope_entries must contain at least one valid document")
    return tuple(resolved)


def _prepare_results_dir(out_dir: Path, *, run_id: str, clean: bool) -> Path | None:
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    if not clean or not out_dir.exists():
        out_dir.mkdir(parents=True, exist_ok=True)
        return None
    backup_dir = BACKUP_ROOT / f"final_results_export_run_{run_id}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / "outputs_results"
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(out_dir), str(target))
    out_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def _ensure_export_backup_dir(run_id: str) -> Path:
    backup_dir = BACKUP_ROOT / f"final_results_export_run_{run_id}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def _backup_scope_output_dir(doc_dir: Path, *, backup_dir: Path | None, run_id: str) -> Path:
    backup_dir = backup_dir or _ensure_export_backup_dir(run_id)
    try:
        relative = doc_dir.relative_to(ROOT)
    except ValueError:
        relative = Path(_safe_component(doc_dir.name))
    target = backup_dir / relative
    if target.exists():
        suffix = 2
        while target.with_name(f"{target.name}_{suffix}").exists():
            suffix += 1
        target = target.with_name(f"{target.name}_{suffix}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(doc_dir), str(target))
    return backup_dir


def _assessment_rows_by_key(*, registry: RegistryData, root: Path) -> dict[str, dict[str, Any]]:
    payload = list_first_priority_assessments(registry=registry, root=root)
    return {str(row.get("key")): row for row in payload.get("rows", []) if isinstance(row, dict)}


def _is_handwriting_item(item: dict[str, Any]) -> bool:
    writing_method = str((item.get("registry") or {}).get("writingMethod") or item.get("writingMethod") or "").strip()
    return writing_method == "수기"


def _has_authoring_bundle(item: dict[str, Any]) -> bool:
    return bool(item.get("latestAuthoringSchema") and item.get("latestAuthoringStylesheet") and item.get("latestAuthoringFakerProfile"))


def _resolve_output_mode(item: dict[str, Any], *, render_handwriting_as_printed: bool = False, prefer_cleanroom: bool = False) -> str:
    if prefer_cleanroom and item.get("latestCleanroomPdf"):
        return "cleanroom_static"
    if _is_handwriting_item(item):
        # Temporary printed-mode export for handwriting documents: use the normal
        # authoring renderer only. Handwriting QR bbox metadata lives under
        # schema.handwriting and is intentionally not rendered in this path.
        if render_handwriting_as_printed and _has_authoring_bundle(item):
            return "pipeline"
        if latest_accepted_handwriting_samples(item):
            return "handwriting"
        if item.get("latestCleanroomPdf"):
            return "cleanroom_static"
        if render_handwriting_as_printed:
            raise ValueError("no authoring bundle found for temporary printed handwriting export")
        raise ValueError("no accepted handwriting scans found; create a handwriting print pack and run scan intake first")
    if _has_authoring_bundle(item):
        return "pipeline"
    if item.get("latestCleanroomPdf"):
        return "cleanroom_static"
    raise ValueError("no authoring bundle, cleanroom PDF, or accepted handwriting scan found")


def _render_pipeline_document(
    item: dict[str, Any],
    *,
    title: str,
    count: int,
    seed: int,
    render_scale: int,
    work_dir: Path,
    as_of_date: date,
) -> PipelineRenderResult:
    doc_id = str(item["docId"])
    schema_path = _resolve_existing_path(item["latestAuthoringSchema"])
    stylesheet_path = _resolve_existing_path(item["latestAuthoringStylesheet"])
    faker_profile_path = _resolve_existing_path(item["latestAuthoringFakerProfile"])
    batch = render_authoring_batch(
        schema_path,
        stylesheet_path,
        faker_profile_path,
        out_dir=work_dir,
        count=count,
        seed=seed,
        sample_prefix="sample",
        clean=True,
        render_scale=render_scale,
        as_of_date=as_of_date,
    )
    schema = _read_json(schema_path)
    fields = [field for field in schema.get("fields", []) if isinstance(field, dict)]
    semantic_schema = _load_semantic_schema(schema_path, title=title)
    if not semantic_schema:
        raise ValueError(f"authoring schema has no primary semantic_schema: {schema_path}")
    field_paths = _field_semantic_paths(fields, semantic_schema=semantic_schema)
    primary_schema_path = work_dir / "schema.json"
    primary_schema_path.parent.mkdir(parents=True, exist_ok=True)
    primary_schema = _primary_schema_payload(semantic_schema, field_paths)
    primary_schema_path.write_text(json.dumps(primary_schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pii_keys = resolve_pii_keys(
        semantic_schema,
        fields=fields_with_generators(fields, _read_json(faker_profile_path)),
        privacy=schema.get("privacy"),
    )
    samples: list[dict[str, Any]] = []
    image_reports: list[dict[str, Any]] = []
    for index, sample in enumerate(batch.samples):
        final_sample_id = f"sample_{index:03d}"
        kv = _read_json(sample.kv)
        bbox = _read_json(sample.bbox)
        image_path = work_dir / f"{final_sample_id}.jpg"
        gt_path = work_dir / f"{final_sample_id}.json"
        bbox_path = work_dir / f"{final_sample_id}-bbox.json"
        image_reports.append(_write_jpg(sample.image, image_path))
        rendered_semantic_values = kv.get("semantic_values") if isinstance(kv.get("semantic_values"), dict) else None
        if rendered_semantic_values is None:
            raise ValueError(f"rendered sample has no semantic_values; final GT cannot be generated without primary schema mapping: {sample.kv}")
        gt_payload = _merge_schema_values(semantic_schema, rendered_semantic_values)
        gt_path.write_text(json.dumps(gt_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        normalized_bbox = _semantic_bbox_payload(semantic_schema, field_paths, bbox)
        bbox_path.write_text(json.dumps(normalized_bbox, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sample_paths = {"image": image_path, "gt": gt_path, "bbox": bbox_path}
        if pii_keys:
            pii_path = work_dir / f"{final_sample_id}-pii.json"
            pii_path.write_text(json.dumps(pii_keys, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            sample_paths["pii"] = pii_path
        samples.append(sample_paths)
    _validate_library_sample_directory(work_dir, expected_sample_count=count)
    return PipelineRenderResult(samples=samples, primary_schema=primary_schema_path, pii_keys=pii_keys, image_reports=image_reports)


def _copy_pipeline_samples(result: PipelineRenderResult, out_dir: Path) -> None:
    shutil.copy2(result.primary_schema, out_dir / "schema.json")
    for sample in result.samples:
        for path in sample.values():
            shutil.copy2(path, out_dir / path.name)


def _copy_handwriting_samples(item: dict[str, Any], out_dir: Path, *, count: int) -> dict[str, Any]:
    samples = latest_accepted_handwriting_samples(item)
    if not samples:
        raise ValueError("no accepted handwriting scans found")
    generated = 0
    image_reports: list[dict[str, Any]] = []
    schema_path = _handwriting_primary_schema_path(item)
    pii_keys: list[str] = []
    if schema_path and schema_path.exists():
        shutil.copy2(schema_path, out_dir / "schema.json")
        generated += 1
        if item.get("latestAuthoringSchema"):
            authoring_schema_path = _resolve_existing_path(item["latestAuthoringSchema"])
            authoring_schema = _read_json(authoring_schema_path)
            semantic_schema = _load_semantic_schema(authoring_schema_path)
            fields = [field for field in authoring_schema.get("fields", []) if isinstance(field, dict)]
            faker_profile = _read_json(_resolve_existing_path(item["latestAuthoringFakerProfile"])) if item.get("latestAuthoringFakerProfile") else {}
            pii_keys = resolve_pii_keys(
                semantic_schema,
                fields=fields_with_generators(fields, faker_profile),
                privacy=authoring_schema.get("privacy"),
            )
        else:
            semantic_schema = _read_json(schema_path)
            pii_keys = resolve_pii_keys(semantic_schema)
    copied_count = min(count, len(samples))
    for index, sample in enumerate(samples[:copied_count]):
        stem = f"sample_{index:03d}"
        image_target = out_dir / f"{stem}.jpg"
        image_reports.append(_write_jpg(sample.image, image_target))
        shutil.copy2(sample.gt, out_dir / f"{stem}.json")
        generated += 2
        if sample.bbox and sample.bbox.exists():
            shutil.copy2(sample.bbox, out_dir / f"{stem}-bbox.json")
            generated += 1
        if pii_keys:
            (out_dir / f"{stem}-pii.json").write_text(json.dumps(pii_keys, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            generated += 1
    return {
        "sampleCount": copied_count,
        "generatedFileCount": generated,
        "piiFileCount": copied_count if pii_keys else 0,
        "imageReports": image_reports,
    }


def _render_cleanroom_document(item: dict[str, Any], *, work_dir: Path) -> PipelineRenderResult:
    annotation_value = item.get("latestLibrarySampleAnnotation")
    if not annotation_value:
        raise ValueError("cleanroom library-sample annotation is required; existing result folder was preserved")
    annotation_path = _resolve_existing_path(annotation_value)
    artifacts = build_cleanroom_artifacts(annotation_path)
    source_image = Path(artifacts["source_image"])
    pages_dir = _cleanroom_pages_dir(item)
    if pages_dir is None or source_image.parent.resolve() != pages_dir.resolve():
        raise ValueError("cleanroom annotation source must be inside the generated cleanroom pages_dir")
    work_dir.mkdir(parents=True, exist_ok=True)
    image_path = work_dir / "sample_000.jpg"
    gt_path = work_dir / "sample_000.json"
    bbox_path = work_dir / "sample_000-bbox.json"
    schema_path = work_dir / "schema.json"
    image_report = _write_jpg(source_image, image_path)
    gt_path.write_text(json.dumps(artifacts["gt"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bbox_path.write_text(json.dumps(artifacts["bbox"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    schema_path.write_text(json.dumps(artifacts["schema"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sample_paths = {"image": image_path, "gt": gt_path, "bbox": bbox_path}
    pii_keys = list(artifacts["pii_keys"])
    if pii_keys:
        pii_path = work_dir / "sample_000-pii.json"
        pii_path.write_text(json.dumps(pii_keys, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sample_paths["pii"] = pii_path
    _validate_library_sample_directory(work_dir, expected_sample_count=1)
    return PipelineRenderResult(samples=[sample_paths], primary_schema=schema_path, pii_keys=pii_keys, image_reports=[image_report])


def _cleanroom_pages_dir(item: dict[str, Any]) -> Path | None:
    value = item.get("latestCleanroomPagesDir")
    if not value and isinstance(item.get("manifest"), dict):
        cleanroom = (item["manifest"].get("artifacts") or {}).get("cleanroom")
        if isinstance(cleanroom, dict):
            value = cleanroom.get("pages_dir")
    if not value:
        return None
    path = _resolve_workspace_path(Path(str(value)))
    return path if path.exists() and path.is_dir() else None


def _deferred_multi_page_warnings(item: dict[str, Any], *, mode: str) -> list[dict[str, Any]]:
    page_count = 0
    if mode == "cleanroom_static":
        pages_dir = _cleanroom_pages_dir(item)
        page_count = len([path for path in pages_dir.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}]) if pages_dir else 0
    elif mode == "pipeline" and item.get("documentDir"):
        authoring_dir = _resolve_workspace_path(Path(str(item["documentDir"]))) / "authoring"
        page_count = len([path for path in authoring_dir.glob("page_*") if path.is_dir()]) if authoring_dir.exists() else 0
    if page_count <= 1:
        return []
    return [
        {
            "code": "multi_page_export_deferred",
            "message": f"다중 페이지 page_N/_pNN 포장은 이번 범위에서 보류되어 대표 단일 페이지로 출력했습니다: 감지 {page_count}페이지",
            "detectedPageCount": page_count,
        }
    ]


def _validate_library_sample_directory(directory: Path, *, expected_sample_count: int) -> None:
    schema_path = directory / "schema.json"
    schema = _read_json(schema_path)
    if not isinstance(schema, dict) or not schema:
        raise ValueError("library-sample schema.json must be a non-empty JSON object")
    schema_paths = _semantic_leaf_paths(schema)
    if not schema_paths:
        raise ValueError("library-sample schema.json has no leaf keys")
    gt_paths = sorted(path for path in directory.iterdir() if re.fullmatch(r"sample_\d{3}\.json", path.name))
    if len(gt_paths) != expected_sample_count:
        raise ValueError(f"library-sample count mismatch: expected {expected_sample_count}, got {len(gt_paths)}")
    leaf_names = {path[-1] for path in schema_paths}
    for gt_path in gt_paths:
        stem = gt_path.stem
        image_path = directory / f"{stem}.jpg"
        if not image_path.exists():
            raise ValueError(f"library-sample JPG missing: {image_path.name}")
        with Image.open(image_path) as image:
            if image.format != "JPEG":
                raise ValueError(f"library-sample image must be JPG: {image_path.name}")
        gt = _read_json(gt_path)
        if not isinstance(gt, dict) or _semantic_leaf_paths(gt) != schema_paths:
            raise ValueError(f"library-sample GT keys/structure must match schema.json: {gt_path.name}")
        bbox_path = directory / f"{stem}-bbox.json"
        if bbox_path.exists():
            bbox_payload = _read_json(bbox_path)
            bbox_leaves = _bbox_leaf_items(bbox_payload)
            unknown_paths = set(bbox_leaves) - schema_paths
            if unknown_paths:
                raise ValueError(f"library-sample bbox has unknown schema paths: {sorted(unknown_paths)[:10]}")
            for path, bbox in bbox_leaves.items():
                coords = [bbox.get(axis) for axis in ("l", "t", "r", "b")]
                if not all(isinstance(value, (int, float)) and 0 <= float(value) <= 1 for value in coords):
                    raise ValueError(f"library-sample bbox coordinates must be in [0,1]: {path}")
                if float(coords[0]) >= float(coords[2]) or float(coords[1]) >= float(coords[3]):
                    raise ValueError(f"library-sample bbox must satisfy l<r and t<b: {path}")
        pii_path = directory / f"{stem}-pii.json"
        if pii_path.exists():
            pii = _read_json_value(pii_path)
            if not isinstance(pii, list) or any(not isinstance(key, str) or not key for key in pii):
                raise ValueError(f"library-sample PII file must be a string key list: {pii_path.name}")
            unknown_keys = set(pii) - leaf_names
            if unknown_keys:
                raise ValueError(f"library-sample PII file has unknown leaf keys: {sorted(unknown_keys)}")


def _bbox_leaf_items(value: Any, prefix: SemanticPath = ()) -> dict[SemanticPath, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    if {"l", "t", "r", "b"}.issubset(value):
        return {prefix: value}
    leaves: dict[SemanticPath, dict[str, Any]] = {}
    for key, child in value.items():
        leaves.update(_bbox_leaf_items(child, (*prefix, str(key))))
    return leaves


def _handwriting_primary_schema_path(item: dict[str, Any]) -> Path | None:
    manifest_value = item.get("latestHandwritingPrintPack") or (item.get("manifest", {}).get("artifacts", {}) if isinstance(item.get("manifest"), dict) else {}).get("handwriting_print_pack")
    if not manifest_value:
        return None
    manifest_path = _resolve_existing_path(manifest_value)
    payload = _read_json(manifest_path)
    schema_value = payload.get("schema") if isinstance(payload, dict) else None
    if not schema_value:
        return None
    return _resolve_existing_path(schema_value)


def _field_labels(fields: list[dict[str, Any]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for field in fields:
        field_id = str(field.get("field_id") or "")
        label = str(field.get("label") or field_id).strip()
        labels[field_id] = _clean_label(label or field_id)
    return labels


SemanticPath = tuple[str, ...]


def _field_semantic_paths(fields: list[dict[str, Any]], *, semantic_schema: dict[str, Any]) -> dict[str, SemanticPath]:
    """Return field_id -> pure semantic path used by GT/BBox exports."""

    schema_leaf_paths = _semantic_leaf_paths(semantic_schema)
    if not schema_leaf_paths:
        raise ValueError("primary semantic_schema must contain at least one leaf")
    paths: dict[str, SemanticPath] = {}
    path_owner: dict[SemanticPath, str] = {}
    for field in fields:
        field_id = str(field.get("field_id") or "")
        if not _field_export_enabled(field):
            continue
        semantic_path = _semantic_path_from_field(field)
        if semantic_path and _is_pure_semantic_path(semantic_path) and semantic_path in schema_leaf_paths:
            previous = path_owner.get(semantic_path)
            if previous:
                raise ValueError(f"duplicate field semantic_path mapping: {previous}, {field_id} -> {semantic_path}")
            path_owner[semantic_path] = field_id
            paths[field_id] = semantic_path
            continue
        if semantic_path and semantic_path not in schema_leaf_paths:
            raise ValueError(f"field semantic_path is not a primary schema leaf: {field_id} -> {semantic_path}")
        raise ValueError(f"final export requires semantic_path for field: {field_id}")
    unmapped = sorted(schema_leaf_paths - set(path_owner))
    if unmapped:
        raise ValueError(f"primary semantic_schema has unmapped leaves: {unmapped[:20]}")
    return paths


def _semantic_leaf_paths(value: Any, prefix: SemanticPath = ()) -> set[SemanticPath]:
    if isinstance(value, dict):
        paths: set[SemanticPath] = set()
        for key, child in value.items():
            paths.update(_semantic_leaf_paths(child, (*prefix, str(key))))
        return paths
    return {prefix} if prefix else set()


def _field_export_enabled(field: dict[str, Any]) -> bool:
    export = field.get("export") if isinstance(field.get("export"), dict) else {}
    value = export.get("include") if "include" in export else True
    return str(value).strip().lower() not in {"false", "0", "no", "off", "skip", "hidden"}


def _semantic_path_from_field(field: dict[str, Any]) -> SemanticPath:
    raw_path = field.get("semantic_path") or field.get("key_path")
    if isinstance(raw_path, list):
        return tuple(str(part).strip() for part in raw_path if str(part).strip())
    if isinstance(raw_path, str) and raw_path.strip():
        value = raw_path.strip()
        separator = "/" if "/" in value else "."
        return tuple(part.strip() for part in value.split(separator) if part.strip())
    return ()


def _is_pure_semantic_path(path: Sequence[str] | str) -> bool:
    banned = {"doc_id", "document_name", "sample_id", "labels", "annotations", "image", "bbox_format", "precision"}
    stripped = "/".join(path) if not isinstance(path, str) else path
    stripped = stripped.strip()
    if not stripped or stripped in banned:
        return False
    if re.search(r"[A-Za-z]", stripped):
        # English letters may be legitimate units such as USD/FOB/HS, but final
        # KIE keys should not remain all-English/internal.  Allow if Korean is
        # present as the semantic anchor.
        return bool(re.search(r"[가-힣]", stripped))
    return True


def _load_semantic_schema(schema_path: Path, *, title: str = "") -> dict[str, Any]:
    schema_payload = _read_json(schema_path)
    if isinstance(schema_payload.get("semantic_schema"), dict):
        return _strip_schema_metadata(schema_payload["semantic_schema"], title=title)
    path = schema_path.with_name("semantic_schema.json")
    if not path.exists():
        return {}
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {}
    return _strip_schema_metadata(payload, title=title)


def _strip_schema_metadata(payload: dict[str, Any], *, title: str = "") -> dict[str, Any]:
    """Extract the pure semantic tree from legacy or migrated schema files."""

    if isinstance(payload.get("semantic_schema"), dict):
        payload = payload["semantic_schema"]
    elif isinstance(payload.get("schema"), dict):
        payload = payload["schema"]
    metadata_keys = {
        "schema_version",
        "doc_id",
        "title",
        "created_at",
        "updated_at",
        "purpose",
        "notes",
        "field_mapping",
    }
    cleaned = {key: value for key, value in payload.items() if key not in metadata_keys}
    if title and len(cleaned) == 1 and title in cleaned and isinstance(cleaned[title], dict):
        cleaned = cleaned[title]
    return cleaned


def _merge_schema_values(semantic_schema: dict[str, Any], semantic_values: dict[str, Any]) -> dict[str, Any]:
    payload = _schema_value_template(semantic_schema)
    allow_extra = not bool(semantic_schema)

    def merge(target: dict[str, Any], source: dict[str, Any]) -> None:
        for key, value in source.items():
            if isinstance(value, dict):
                child = target.get(key)
                if not isinstance(child, dict) and (key in target or allow_extra):
                    child = {}
                    target[key] = child
                if not isinstance(child, dict):
                    continue
                merge(child, value)
            elif key in target or allow_extra:
                target[key] = value

    merge(payload, semantic_values)
    return payload


def _primary_schema_payload(semantic_schema: dict[str, Any], field_paths: dict[str, SemanticPath]) -> dict[str, Any]:
    if not semantic_schema:
        raise ValueError("primary semantic_schema is required for final export")
    return _schema_value_template(semantic_schema)


def _semantic_bbox_payload(
    semantic_schema: dict[str, Any],
    field_paths: dict[str, SemanticPath],
    payload: dict[str, Any],
) -> dict[str, Any]:
    # BBox export is an image annotation, not a field-position catalog.  Only
    # fields that actually produced a rendered annotation are emitted.  If a
    # generated value is empty and no glyph is rendered, the field is absent
    # from this payload rather than being force-filled from the source review
    # bbox.
    bbox_tree: dict[str, Any] = {}
    image = payload.get("image") if isinstance(payload.get("image"), dict) else {}
    width = max(1, int(image.get("width") or 1))
    height = max(1, int(image.get("height") or 1))
    for annotation in payload.get("annotations", []) if isinstance(payload.get("annotations"), list) else []:
        if not isinstance(annotation, dict):
            continue
        field_id = str(annotation.get("field") or "")
        path = field_paths.get(field_id)
        if not path:
            continue
        # Raw render annotations may still include fields whose resolved value is
        # empty, especially unchecked checkbox/vector-symbol fields.  Final GT
        # bbox must represent rendered value glyphs only; do not emit a location
        # for an empty target.
        if "text" in annotation and not str(annotation.get("text") or "").strip():
            continue
        bbox = annotation.get("bbox") if isinstance(annotation.get("bbox"), list) else [0, 0, 1, 1]
        x, y, w, h = [float(v) for v in bbox[:4]]
        normalize_x = lambda value: round(max(0.0, min(1.0, value / width)), 4)
        normalize_y = lambda value: round(max(0.0, min(1.0, value / height)), 4)
        _set_semantic_value(
            bbox_tree,
            path,
            {
                "l": normalize_x(x),
                "t": normalize_y(y),
                "r": normalize_x(x + w),
                "b": normalize_y(y + h),
            },
        )
    return bbox_tree


def _schema_value_template(value: Any, *, leaf: Any = "") -> Any:
    if isinstance(value, dict):
        return {key: _schema_value_template(child, leaf=leaf) for key, child in value.items()}
    if isinstance(value, list):
        return [_schema_value_template(child, leaf=leaf) for child in value]
    return copy.deepcopy(leaf)


def _set_semantic_value(payload: dict[str, Any], path: Sequence[str] | str, value: Any) -> None:
    """Set value in a semantic tree.

    Final schemas are intentionally flat (`{"성명": ""}`) unless a future
    document explicitly stores nested Korean paths.  Dotted paths are supported
    only when matching containers already exist, so a literal key containing
    dots/brackets never gets split unexpectedly.
    """

    if isinstance(path, str) and path in payload:
        payload[path] = value
        return
    if isinstance(path, str):
        separator = "/" if "/" in path else "."
        parts = [part for part in path.split(separator) if part]
    else:
        parts = [str(part) for part in path if str(part)]
    cursor: Any = payload
    for part in parts[:-1]:
        if not isinstance(cursor, dict):
            return
        cursor = cursor.setdefault(part, {})
    if isinstance(cursor, dict) and parts:
        cursor[parts[-1]] = value
    else:
        payload[str(path)] = value


def _sanitize_gt_labels(values: dict[str, Any], field_labels: dict[str, str]) -> dict[str, str]:
    output: dict[str, str] = {}
    base_seen: dict[str, int] = {}
    for field_id, value in values.items():
        base_key = _korean_key_for_field(str(field_id), field_labels)
        key = _dedupe_key(base_key, base_seen)
        output[key] = str(value)
    return output


def _korean_key_for_field(field_id: str, field_labels: dict[str, str]) -> str:
    label = _semantic_label(field_labels.get(field_id) or field_id)
    if not re.search(r"[가-힣]", label):
        return _field_id_to_korean_key(field_id)
    if re.fullmatch(r"체크(?:\s+[A-Za-z0-9_]+)?(?:\[\d+\])?", label):
        generated = _field_id_to_korean_key(field_id)
        return generated if generated.endswith("체크") else f"{generated}체크"
    # Common repeated-row labels are written like "주주 1 주주명" or "품목 3 금액".
    match = re.match(r"^(.+?)\s+(\d+)\s+(.+)$", label)
    if match:
        index = max(0, int(match.group(2)) - 1)
        return f"{_semantic_label(match.group(3))}[{index}]"
    # Labels like "account_2 기관점포명" or "loan_7 금액" come from table rows.
    match = re.match(r"^[A-Za-z가-힣]+[_\s-]+(\d+)\s+(.+)$", label)
    if match:
        index = max(0, int(match.group(1)) - 1)
        return f"{_semantic_label(match.group(2))}[{index}]"
    return label


def _field_id_to_korean_key(field_id: str) -> str:
    raw_tokens = [token for token in re.split(r"[_\W]+", field_id.lower()) if token]
    tokens: list[str] = []
    for token in raw_tokens:
        if re.fullmatch(r"p\d+|page\d+", token):
            continue
        match = re.fullmatch(r"(\d+)([a-z]+)", token)
        if match:
            tokens.extend([match.group(1), match.group(2)])
            continue
        match = re.fullmatch(r"([a-z]+)(\d+)", token)
        if match:
            tokens.extend([match.group(1), match.group(2)])
        else:
            tokens.append(token)
    row_index: int | None = None
    if len(tokens) >= 3:
        for idx, token in enumerate(tokens):
            prev = tokens[idx - 1] if idx > 0 else ""
            if token.isdigit() and prev in {"shareholder", "item", "account", "loan", "row", "section", "box", "land", "goods"}:
                row_index = max(0, int(token) - 1)
                tokens = tokens[idx + 1 :]
                break
    token_map = {
        "exporter": "수출자",
        "importer": "수입자",
        "producer": "생산자",
        "shipper": "송하인",
        "seller": "판매자",
        "consignee": "수하인",
        "buyer": "구매자",
        "invoice": "송장",
        "number": "번호",
        "no": "번호",
        "date": "일자",
        "name": "명",
        "email": "이메일",
        "e": "이메일",
        "mail": "이메일",
        "telephone": "전화번호",
        "phone": "전화번호",
        "fax": "팩스",
        "address": "주소",
        "line1": "주소1",
        "line2": "주소2",
        "line": "주소행",
        "blanket": "포괄",
        "period": "기간",
        "from": "시작",
        "to": "종료",
        "item": "품목",
        "serial": "일련",
        "description": "품명",
        "good": "물품",
        "goods": "물품",
        "quantity": "수량",
        "unit": "단위",
        "hs": "HS",
        "preference": "특혜",
        "criterion": "기준",
        "country": "국가",
        "origin": "원산지",
        "certification": "증명",
        "authorized": "권한자",
        "lc": "신용장",
        "reference": "참조번호",
        "departure": "출발일",
        "vessel": "선박",
        "flight": "항공편",
        "loading": "선적",
        "port": "항구",
        "terms": "조건",
        "delivery": "인도",
        "payment": "결제",
        "destination": "도착지",
        "price": "단가",
        "amount": "금액",
        "total": "합계",
        "net": "순",
        "gross": "총",
        "weight": "중량",
        "volume": "용적",
        "package": "포장",
        "packages": "포장",
        "packing": "포장명세",
        "list": "명세",
        "tel": "전화번호",
        "summary": "요약",
        "container": "컨테이너",
        "seal": "봉인",
        "footer": "하단",
        "company": "회사",
        "representative": "대표자",
        "remarks": "비고",
        "remark": "비고",
        "declaration": "신고",
        "certificate": "증명서",
        "customs": "세관",
        "declarant": "신고인",
        "applicant": "신청인",
        "business": "사업",
        "registration": "등록",
        "resident": "주민등록",
        "passport": "여권",
        "driver": "운전면허",
        "privacy": "개인정보",
        "solicitation": "투자권유",
        "agree": "동의",
        "disagree": "미동의",
        "optional": "선택",
        "required": "필수",
        "channel": "수신채널",
        "sms": "SMS",
        "paper": "서면",
        "all": "전체",
        "id": "신분증",
        "gov": "공무원증",
        "foreign": "외국인등록증",
        "welfare": "복지카드",
        "third": "제3자",
        "party": "제공",
        "issuer": "발급",
        "agency": "기관",
        "tracking": "배송추적",
        "dispatch": "발송",
        "barcode": "바코드",
        "consent": "동의",
        "info": "정보",
        "provided": "제공",
        "not": "미",
        "new": "신규",
        "change": "변경",
        "same": "동일",
        "existing": "기존",
        "lt": "미만",
        "gt": "초과",
        "m": "개월",
        "y": "년",
        "solicitation": "투자권유",
        "wanted": "희망",
        "stable": "안정형",
        "conservative": "안정추구형",
        "balanced": "위험중립형",
        "growth": "적극투자형",
        "aggressive": "공격투자형",
        "product": "상품",
        "knowledge": "지식",
        "very": "매우",
        "low": "낮음",
        "high": "높음",
        "portfolio": "포트폴리오",
        "loss": "손실",
        "principal": "원금",
        "any": "전액",
        "type": "유형",
        "derivative": "파생상품",
        "none": "없음",
        "agreement": "동의서",
        "age": "연령",
        "income": "소득",
        "decrease": "감소",
        "receipt": "접수",
        "year": "년",
        "month": "월",
        "day": "일",
        "shipping": "화인",
        "mark": "마크",
        "code": "코드",
        "material": "재질",
        "composition": "구성",
        "lot": "로트",
        "carton": "카톤",
        "range": "범위",
        "signed": "서명자",
        "by": "",
        "of": "",
        "and": "",
        "if": "",
        "other": "",
        "than": "",
        "as": "",
        "finance": "금융",
        "isa": "개인종합자산관리계좌",
        "yes": "예",
        "notify": "통지처",
        "city": "도시",
        "final": "최종",
        "carrier": "운송사",
        "sailing": "출항",
        "header": "헤더",
        "title": "제목",
        "dimensions": "규격",
        "dimension": "규격",
        "breakdown": "내역",
        "trade": "무역",
        "say": "포장수량문구",
        "only": "한정",
        "statement": "문구",
        "check": "체크",
    }
    translated = [token_map.get(token, token) for token in tokens]
    translated = [token for token in translated if token]
    key = "".join(translated) or field_id
    if row_index is not None:
        return f"{key}[{row_index}]"
    return key


def _dedupe_key(key: str, seen: dict[str, int]) -> str:
    if key not in seen:
        seen[key] = 0
        return key
    seen[key] += 1
    return f"{key}[{seen[key]}]"


def _clean_label(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = text.replace(" :", "").replace(":", "")
    return text or "값"


def _semantic_label(value: str) -> str:
    text = _clean_label(value)
    text = text.replace("FAX", "팩스").replace("Fax", "팩스")
    text = text.replace("II", "2")
    replacements = {
        "Account Name": "",
        "For and on behalf of": "",
        "page1 check": "체크",
        "페이지 1 체크": "체크",
        "page1": "",
        "Page 1": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    if re.match(r"^(D\d+|USD|FOB|HS)(\b|\s|[가-힣])", text):
        return _clean_label(text)
    # If a label contains a Korean semantic suffix after an English/internal
    # prefix, keep only the suffix.  This turns e.g. "Account Name 회사이름" into
    # "회사이름" and "page1 receipt_year" into a generated Korean fallback later.
    if re.search(r"[가-힣]", text):
        text = re.sub(r"^[A-Za-z0-9_./()& -]+(?=[가-힣])", "", text).strip()
        text = re.sub(r"\b[A-Za-z0-9]+_[A-Za-z0-9_]+\b", "", text).strip()
        text = re.sub(r"\s+", " ", text).strip()
    return _clean_label(text)


def _normalized_bbox_payload(
    payload: dict[str, Any],
    *,
    doc_id: str,
    title: str,
    sample_id: str,
    field_labels: dict[str, str],
    values: dict[str, Any],
) -> dict[str, Any]:
    image = payload.get("image") if isinstance(payload.get("image"), dict) else {}
    width = max(1, int(image.get("width") or 1))
    height = max(1, int(image.get("height") or 1))
    annotations = []
    for annotation in payload.get("annotations", []) if isinstance(payload.get("annotations"), list) else []:
        if not isinstance(annotation, dict):
            continue
        field_id = str(annotation.get("field") or "")
        bbox = annotation.get("bbox") if isinstance(annotation.get("bbox"), list) else [0, 0, 1, 1]
        x, y, w, h = [float(v) for v in bbox[:4]]
        annotations.append(
            {
                "field": field_id,
                "key": _korean_key_for_field(field_id, field_labels),
                "value": str(values.get(field_id, annotation.get("text") or "")),
                "bbox": {
                    "l": round(x / width, 4),
                    "t": round(y / height, 4),
                    "r": round((x + w) / width, 4),
                    "b": round((y + h) / height, 4),
                },
            }
        )
    return {
        "doc_id": doc_id,
        "document_name": title,
        "sample_id": sample_id,
        "bbox_format": "normalized_ltrb",
        "precision": 4,
        "image": {"width": width, "height": height},
        "annotations": annotations,
    }


def _write_jpg(source: Path, target: Path, *, recommended_max_bytes: int = 500 * 1024) -> dict[str, Any]:
    with Image.open(source) as image:
        if image.mode in {"RGBA", "LA"}:
            background = Image.new("RGB", image.size, (255, 255, 255))
            alpha = image.getchannel("A") if image.mode == "RGBA" else image.getchannel("A")
            background.paste(image.convert("RGBA"), mask=alpha)
            image = background
        else:
            image = image.convert("RGB")
        quality = 95
        for quality in (95, 90, 85, 80, 75, 70, 65, 60):
            try:
                image.save(target, "JPEG", quality=quality, subsampling=0, optimize=True)
            except OSError:
                # Pillow/libjpeg can reject optimize mode for high-entropy large
                # pages ("Suspension not allowed here"). Keep the same quality
                # and resolution, then continue the size-reduction loop.
                target.unlink(missing_ok=True)
                image.save(target, "JPEG", quality=quality, subsampling=0, optimize=False)
            if target.stat().st_size <= recommended_max_bytes:
                break
        width, height = image.size
    size_bytes = target.stat().st_size
    warnings: list[dict[str, Any]] = []
    if size_bytes > recommended_max_bytes:
        warnings.append(
            {
                "code": "jpg_over_recommended_size",
                "message": f"JPG가 권장 500KB를 초과합니다: {round(size_bytes / 1024, 1)}KB",
                "sizeBytes": size_bytes,
            }
        )
    if max(width, height) < 1400:
        warnings.append(
            {
                "code": "jpg_long_side_below_recommended",
                "message": f"JPG 긴 변이 권장 1400px 미만입니다: {max(width, height)}px",
                "width": width,
                "height": height,
            }
        )
    return {"path": _display_path(target), "width": width, "height": height, "sizeBytes": size_bytes, "quality": quality, "warnings": warnings}


def _source_hashes(items_by_doc_id: dict[str, dict[str, Any]]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for item in items_by_doc_id.values():
        for key in ("latestAuthoringSchema", "latestAuthoringStylesheet", "latestAuthoringFakerProfile"):
            value = item.get(key)
            if not value:
                continue
            path = _resolve_existing_path(value)
            hashes[str(path)] = _sha256(path)
        semantic = Path(str(item.get("documentDir") or "")) / "authoring" / "semantic_schema.json"
        semantic_path = _resolve_workspace_path(semantic)
        if semantic_path.exists():
            hashes[str(semantic_path)] = _sha256(semantic_path)
    assessment_path = ROOT / "first_priority_assessments.json"
    if assessment_path.exists():
        hashes[str(assessment_path)] = _sha256(assessment_path)
    return hashes


def _changed_sources(hashes: dict[str, str]) -> list[Path]:
    changed: list[Path] = []
    for raw_path, digest in hashes.items():
        path = Path(raw_path)
        if not path.exists() or _sha256(path) != digest:
            changed.append(path)
    return changed


def _restore_changed_sources(changed_sources: list[Path], *, backup_dir: Path | None) -> None:
    candidates = [
        Path((ROOT / ".bin/backups/latest_final_results_export_backup.txt").read_text(encoding="utf-8").strip())
        if (ROOT / ".bin/backups/latest_final_results_export_backup.txt").exists()
        else None,
        backup_dir,
    ]
    for changed in changed_sources:
        for candidate in candidates:
            if candidate is None:
                continue
            backup_path = candidate / changed.relative_to(ROOT)
            if backup_path.exists():
                changed.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, changed)
                break


def _summary(rows: list[dict[str, Any]], errors: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [row for row in rows if row.get("status") == "OK"]
    return {
        "scopeEntryCount": len(rows),
        "uniqueDocumentCount": len({row["docId"] for row in rows}),
        "okCount": len(ok_rows),
        "errorCount": len(errors),
        "pipelineScopeCount": len([row for row in ok_rows if row.get("outputMode") == "pipeline"]),
        "cleanroomScopeCount": len([row for row in ok_rows if row.get("outputMode") == "cleanroom_static"]),
        "handwritingScopeCount": len([row for row in ok_rows if row.get("outputMode") == "handwriting"]),
        "generatedFileCount": sum(int(row.get("generatedFileCount") or ((3 * int(row["sampleCount"]) + 1) if row.get("outputMode") == "pipeline" else int(row["sampleCount"]))) for row in ok_rows),
        "piiFileCount": sum(int(row.get("piiFileCount") or 0) for row in ok_rows),
        "warningCount": sum(int(row.get("warningCount") or 0) for row in ok_rows),
        "generatedAt": _now(),
    }


def _write_manifest_xlsx(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    matrix: list[list[Any]] = [
        ["레지스트리 도메인별 최종 산출물 매니페스트"],
        [
            f"생성: {summary['generatedAt']} · scope {summary['scopeEntryCount']}건 / 고유 {summary['uniqueDocumentCount']}종 · "
            f"pipeline {summary['pipelineScopeCount']}건 · cleanroom {summary['cleanroomScopeCount']}건 · handwriting {summary.get('handwritingScopeCount', 0)}건 · "
            f"PII {summary.get('piiFileCount', 0)}개 · 경고 {summary.get('warningCount', 0)}건 · 오류 {summary['errorCount']}건"
        ],
        [],
        ["분야", "순번", "문서ID", "문서명", "문서 속성", "저장된 작업판정", "최종 출력모드", "샘플 수", "산출물 형식", "상태", "출력 폴더", "오류/경고"],
    ]
    for row in rows:
        matrix.append(
            [
                row.get("domain", ""),
                row.get("index", ""),
                row.get("docId", ""),
                row.get("title", ""),
                row.get("documentTypeLabel", ""),
                row.get("storedFeasibilityLabel", ""),
                {"pipeline": "작업 가능: pipeline", "cleanroom_static": "작업 불가: cleanroom 정적 주석", "handwriting": "수기: scan+GT"}.get(str(row.get("outputMode")), "오류"),
                row.get("sampleCount", 0),
                row.get("outputType", ""),
                row.get("status", ""),
                row.get("outputDir", ""),
                " / ".join([str(row.get("message") or ""), *[str(warning.get("message") or warning.get("code") or "") for warning in row.get("warnings", [])]]).strip(" /"),
            ]
        )
    _write_simple_xlsx(path, matrix, sheet_name="최종산출물")


def _write_simple_xlsx(path: Path, matrix: list[list[Any]], *, sheet_name: str) -> None:
    shared_strings: list[str] = []
    shared_index: dict[str, int] = {}
    sheet_xml = _sheet_xml(matrix, shared_strings, shared_index)
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{html.escape(sheet_name, quote=True)}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/styles.xml", _styles_xml())
        archive.writestr("xl/sharedStrings.xml", _shared_strings_xml(shared_strings))
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def _sheet_xml(matrix: list[list[Any]], shared_strings: list[str], shared_index: dict[str, int]) -> str:
    last_col = max((len(row) for row in matrix), default=1)
    last_row = max(len(matrix), 1)
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
        f'<dimension ref="A1:{_col_name(last_col)}{last_row}"/>',
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>',
        '<cols>',
    ]
    widths = [10, 8, 12, 30, 16, 16, 20, 10, 16, 10, 52, 40]
    for index, width in enumerate(widths, start=1):
        parts.append(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>')
    parts.append("</cols><sheetData>")
    for row_idx, row in enumerate(matrix, start=1):
        parts.append(f'<row r="{row_idx}">')
        for col_idx, value in enumerate(row, start=1):
            style = 1 if row_idx == 1 else 2 if row_idx == 4 else 0
            parts.append(_cell_xml(row_idx, col_idx, value, style, shared_strings, shared_index))
        parts.append("</row>")
    parts.append("</sheetData>")
    if last_row >= 4:
        parts.append(f'<autoFilter ref="A4:{_col_name(last_col)}{last_row}"/>')
    parts.append('<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>')
    parts.append("</worksheet>")
    return "".join(parts)


def _cell_xml(row: int, col: int, value: Any, style: int, shared_strings: list[str], shared_index: dict[str, int]) -> str:
    ref = f"{_col_name(col)}{row}"
    style_attr = f' s="{style}"' if style else ""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    text = _clean_xml_text(str(value or ""))
    if text not in shared_index:
        shared_index[text] = len(shared_strings)
        shared_strings.append(text)
    return f'<c r="{ref}" t="s"{style_attr}><v>{shared_index[text]}</v></c>'


def _shared_strings_xml(shared_strings: list[str]) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">',
    ]
    for text in shared_strings:
        parts.append(f"<si><t>{html.escape(text, quote=False)}</t></si>")
    parts.append("</sst>")
    return "".join(parts)


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="3"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="16"/><name val="Arial"/></font><font><b/><sz val="10"/><name val="Arial"/></font></fonts>'
        '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFEAF1FF"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"/><right style="thin"/><top style="thin"/><bottom style="thin"/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _col_name(index: int) -> str:
    name = ""
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name or "A"


def _clean_xml_text(value: str) -> str:
    return "".join(ch for ch in value if ch in "\t\n\r" or ord(ch) >= 0x20)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_value(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_workspace_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _resolve_existing_path(value: Any) -> Path:
    path = _resolve_workspace_path(str(value or ""))
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def _display_path(path: str | Path) -> str:
    resolved = _resolve_workspace_path(path)
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _safe_component(value: str) -> str:
    text = re.sub(r"[/:*?\"<>|]+", "_", str(value)).strip()
    return text or "untitled"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
