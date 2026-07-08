from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
import tempfile
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .authoring import _export_values_nested, _generate_values, _kv_payload
from .registry import load_registry, slugify_title
from .workbench import document_dir

ROOT = Path(__file__).resolve().parents[2]
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
ET.register_namespace("w", W_NS)

DOCX_STATUS_ORDER = {
    "external_render_required": 0,
    "analysis_ready": 10,
    "schema_ready": 20,
    "values_ready": 30,
    "filled_docx_ready": 40,
    "renderer_missing": 45,
    "rendered": 50,
    "bbox_gt_ready": 60,
    "failed": -1,
}


@dataclass(frozen=True)
class DocxSample:
    path: Path
    index: int


def analyze_docx_template(doc_id: str, *, sample_path: Path | None = None, registry: Any | None = None) -> dict[str, Any]:
    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    doc_root = document_dir(doc)
    sample = _resolve_docx_sample(doc_root, sample_path)
    out_dir = doc_root / "docx_pipeline"
    out_dir.mkdir(parents=True, exist_ok=True)

    analysis = _analyze_docx(sample.path, doc_id=doc_id, title=doc.title)
    analysis_path = out_dir / "docx_template_analysis.json"
    anchor_map_path = out_dir / "docx_anchor_map.json"
    _write_json(analysis_path, analysis)
    _write_json(anchor_map_path, {"schema_version": 1, "doc_id": doc_id, "title": doc.title, "source_docx": _display(sample.path), "anchors": analysis["anchors"]})
    _update_docx_manifest(doc_root, status="analysis_ready", artifacts={"docx_analysis": analysis_path, "docx_anchor_map": anchor_map_path})
    return {
        "docId": doc_id,
        "title": doc.title,
        "summary": analysis["summary"],
        "paths": {"analysis": _display(analysis_path), "anchorMap": _display(anchor_map_path)},
        "analysis": analysis,
    }


def draft_docx_authoring(doc_id: str, *, analysis_path: Path | None = None, registry: Any | None = None) -> dict[str, Any]:
    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    doc_root = document_dir(doc)
    if analysis_path is None:
        analysis_path = doc_root / "docx_pipeline" / "docx_template_analysis.json"
    if not analysis_path.exists():
        analyze_docx_template(doc_id, registry=registry)
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    anchors = [anchor for anchor in analysis.get("anchors", []) if isinstance(anchor, dict) and anchor.get("kind") == "value_cell"]
    if not anchors:
        raise ValueError("DOCX analysis has no value anchors")

    out_dir = doc_root / "authoring"
    out_dir.mkdir(parents=True, exist_ok=True)
    schema_path = out_dir / "schema.json"
    stylesheet_path = out_dir / "stylesheet.json"
    faker_profile_path = out_dir / "faker_profile.json"

    fields: list[dict[str, Any]] = []
    semantic_schema: dict[str, Any] = {}
    field_generators: dict[str, str] = {}
    used_ids: dict[str, int] = {}
    for index, anchor in enumerate(anchors, start=1):
        label = str(anchor.get("label") or anchor.get("header") or anchor.get("anchor_id") or f"field_{index}").strip()
        field_id = _unique_field_id(_romanize_field_id(label, fallback=f"field_{index:03d}"), used_ids)
        semantic_path = _semantic_path_for_anchor(anchor, field_id)
        rule = _faker_rule_for_label(label, anchor)
        field = {
            "field_id": field_id,
            "key": label,
            "label": label,
            "semantic_path": semantic_path,
            "anchor_id": anchor["anchor_id"],
            "docx_anchor_id": anchor["anchor_id"],
            "value": "",
            "value_type": _value_type_from_rule(rule),
            "generator": rule,
            "style_class": "docx_native",
            "export": {"json_path": "/".join(semantic_path), "csv_column": "_".join(semantic_path)},
            "visual_evidence": {
                "source": "docx_structure",
                "table_index": anchor.get("table_index"),
                "row_index": anchor.get("row_index"),
                "cell_index": anchor.get("cell_index"),
                "label": label,
            },
            "render_policy": {"mode": "docx_injection"},
        }
        fields.append(field)
        field_generators[field_id] = rule
        _set_nested_empty(semantic_schema, semantic_path)

    schema = {
        "schema_version": 1,
        "created_at": _now(),
        "doc_id": doc_id,
        "title": doc.title,
        "source_docx": str(Path(analysis.get("source_docx") or "")),
        "generation_path": "editable-office-template",
        "semantic_schema": semantic_schema,
        "fields": fields,
        "docx_anchor_map": _display(doc_root / "docx_pipeline" / "docx_anchor_map.json"),
        "groups": [],
    }
    stylesheet = {
        "schema_version": 1,
        "created_at": _now(),
        "doc_id": doc_id,
        "generation_path": "editable-office-template",
        "style_classes": [
            {
                "style_class": "docx_native",
                "font_family": "docx-template-native",
                "font_size": 0,
                "fill": [0, 0, 0],
                "align": "docx",
                "valign": "docx",
                "overflow": "docx_native",
                "source": "DOCX 값 주입 파이프라인에서는 이미지 렌더러 스타일을 사용하지 않고 원본 DOCX 셀 서식을 유지합니다.",
            }
        ],
    }
    faker_profile = {
        "schema_version": 1,
        "created_at": _now(),
        "doc_id": doc_id,
        "locale": "ko_KR",
        "field_generators": field_generators,
        "data_pools": {
            "business_types_ko": ["도소매업", "제조업", "서비스업", "건설업", "정보통신업"],
            "business_items_ko": ["전자부품", "산업용 장비", "소프트웨어", "건축자재", "사무용품"],
            "transaction_items_ko": ["시스템 구축 용역", "전산장비 납품", "부품 공급", "유지보수 용역", "소모품 납품"],
            "submission_purposes_ko": ["금융기관 제출용", "입찰 제출용", "거래처 제출용", "내부 증빙용"],
        },
        "constraints": [],
    }
    _write_json(schema_path, schema)
    _write_json(stylesheet_path, stylesheet)
    _write_json(faker_profile_path, faker_profile)
    _update_docx_manifest(
        doc_root,
        status="schema_ready",
        artifacts={"authoring": schema_path, "authoring_stylesheet": stylesheet_path, "authoring_faker_profile": faker_profile_path},
    )
    return {
        "docId": doc_id,
        "summary": {"fieldCount": len(fields), "anchorCount": len(anchors)},
        "paths": {"schema": _display(schema_path), "stylesheet": _display(stylesheet_path), "fakerProfile": _display(faker_profile_path)},
        "schema": schema,
        "stylesheet": stylesheet,
        "faker_profile": faker_profile,
        "fakerProfile": faker_profile,
    }


def generate_docx_outputs(
    doc_id: str,
    *,
    count: int = 1,
    seed: int = 20260708,
    render_pdf: bool = True,
    schema_path: Path | None = None,
    faker_profile_path: Path | None = None,
    sample_path: Path | None = None,
    registry: Any | None = None,
) -> dict[str, Any]:
    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    doc_root = document_dir(doc)
    sample = _resolve_docx_sample(doc_root, sample_path)
    schema_path = schema_path or doc_root / "authoring" / "schema.json"
    faker_profile_path = faker_profile_path or doc_root / "authoring" / "faker_profile.json"
    if not schema_path.exists() or not faker_profile_path.exists():
        draft_docx_authoring(doc_id, registry=registry)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    faker_profile = json.loads(faker_profile_path.read_text(encoding="utf-8"))
    analysis_path = doc_root / "docx_pipeline" / "docx_template_analysis.json"
    if not analysis_path.exists():
        analyze_docx_template(doc_id, sample_path=sample.path, registry=registry)
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    anchor_by_id = {str(anchor.get("anchor_id")): anchor for anchor in analysis.get("anchors", []) if isinstance(anchor, dict)}

    run_dir = doc_root / "docx_pipeline" / "runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    filled_dir = run_dir / "filled_docx"
    values_dir = run_dir / "values"
    gt_dir = run_dir / "gt"
    pdf_dir = run_dir / "rendered_pdf"
    image_dir = run_dir / "page_images"
    bbox_dir = run_dir / "bboxes"
    label_dir = run_dir / "labels"
    for directory in (filled_dir, values_dir, gt_dir, pdf_dir, image_dir, bbox_dir, label_dir):
        directory.mkdir(parents=True, exist_ok=True)

    renderer = _find_soffice() if render_pdf else ""
    samples: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    rng = random.Random(seed)
    latest_status = "filled_docx_ready"
    for index in range(1, max(1, count) + 1):
        sample_id = f"sample_{index:03d}"
        values, generation_warnings = _generate_values(schema, faker_profile, rng)
        warnings.extend({"sample_id": sample_id, **warning} for warning in generation_warnings)
        filled_docx = filled_dir / f"{sample_id}.docx"
        injected = _inject_values(sample.path, filled_docx, schema=schema, values=values, anchor_by_id=anchor_by_id)
        values_path = values_dir / f"{sample_id}.json"
        gt_path = gt_dir / f"{sample_id}.semantic.json"
        full_gt_path = gt_dir / f"{sample_id}.full.json"
        _write_json(values_path, _kv_payload(sample_id, schema, values))
        _write_json(gt_path, {"sample_id": sample_id, "doc_id": doc_id, "semantic_values": _export_values_nested(schema, values)})
        _write_json(full_gt_path, {"sample_id": sample_id, "doc_id": doc_id, "values": values, "schema": schema})
        sample_record: dict[str, Any] = {
            "sampleId": sample_id,
            "filledDocx": _display(filled_docx),
            "values": _display(values_path),
            "gt": _display(gt_path),
            "fullGt": _display(full_gt_path),
            "injectedFieldCount": len(injected),
            "renderedPdf": "",
            "pageImages": [],
            "bbox": "",
            "labels": "",
        }
        if renderer:
            pdf_path = _render_docx_to_pdf(filled_docx, pdf_dir, renderer=renderer)
            latest_status = "rendered"
            images = _render_pdf_pages(pdf_path, image_dir, sample_id=sample_id)
            bbox_payload = _extract_pdf_bboxes(pdf_path, schema=schema, values=values, injected=injected)
            bbox_path = bbox_dir / f"{sample_id}.json"
            labels_path = label_dir / f"{sample_id}.json"
            _write_json(bbox_path, bbox_payload)
            _write_json(labels_path, _labels_payload(sample_id, doc_id, bbox_payload, values))
            if bbox_payload.get("summary", {}).get("matched", 0) > 0:
                latest_status = "bbox_gt_ready"
            sample_record.update(
                {
                    "renderedPdf": _display(pdf_path),
                    "pageImages": [_display(path) for path in images],
                    "bbox": _display(bbox_path),
                    "labels": _display(labels_path),
                }
            )
        elif render_pdf:
            latest_status = "renderer_missing"
            warnings.append({"sample_id": sample_id, "type": "renderer_missing", "message": "LibreOffice/soffice CLI was not found; filled DOCX and GT were generated but PDF/bbox rendering is pending."})
        samples.append(sample_record)

    manifest_path = run_dir / "manifest.json"
    run_manifest = {
        "schema_version": 1,
        "created_at": _now(),
        "doc_id": doc_id,
        "title": doc.title,
        "source_docx": _display(sample.path),
        "schema": _display(schema_path),
        "faker_profile": _display(faker_profile_path),
        "renderer": renderer or "",
        "status": latest_status,
        "sample_count": len(samples),
        "samples": samples,
        "warnings": warnings,
    }
    _write_json(manifest_path, run_manifest)
    artifacts = {"docx_run_manifest": manifest_path}
    if samples:
        artifacts["docx_values"] = values_dir
        artifacts["docx_gt"] = gt_dir
        artifacts["docx_filled_docx"] = filled_dir
        if any(item.get("renderedPdf") for item in samples):
            artifacts["docx_rendered_pdf"] = pdf_dir
            artifacts["docx_page_images"] = image_dir
        if any(item.get("bbox") for item in samples):
            artifacts["docx_bbox"] = bbox_dir
            artifacts["docx_labels"] = label_dir
    _update_docx_manifest(doc_root, status=latest_status, artifacts=artifacts, latest_run=run_manifest)
    return {
        "docId": doc_id,
        "summary": {
            "status": latest_status,
            "sampleCount": len(samples),
            "warningCount": len(warnings),
            "rendererAvailable": bool(renderer),
            "renderPdf": render_pdf,
        },
        "paths": {"runManifest": _display(manifest_path), "runDir": _display(run_dir)},
        "samples": samples,
        "warnings": warnings,
    }


def _analyze_docx(path: Path, *, doc_id: str, title: str) -> dict[str, Any]:
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    anchors: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    for table_index, table in enumerate(root.findall(".//w:tbl", NS)):
        rows_payload: list[dict[str, Any]] = []
        header_by_cell: dict[int, str] = {}
        for row_index, row in enumerate(table.findall("./w:tr", NS)):
            cells = row.findall("./w:tc", NS)
            row_cells: list[dict[str, Any]] = []
            non_empty = [_cell_text(cell) for cell in cells if _cell_text(cell).strip()]
            row_label = _first_non_empty(non_empty)
            for cell_index, cell in enumerate(cells):
                text = _cell_text(cell).strip()
                grid_span = _grid_span(cell)
                width = _cell_width(cell)
                if row_index == 0 and text:
                    header_by_cell[cell_index] = text
                left_label = _nearest_left_label(cells, cell_index)
                header = header_by_cell.get(cell_index, "")
                label = _label_for_cell(text=text, left_label=left_label, header=header, row_label=row_label, table_index=table_index, row_index=row_index)
                cell_payload = {
                    "cell_index": cell_index,
                    "text": text,
                    "grid_span": grid_span,
                    "width_twips": width,
                    "label": label,
                    "is_empty": not bool(text),
                }
                row_cells.append(cell_payload)
                if not text:
                    anchor_id = f"docx_t{table_index:02d}_r{row_index:02d}_c{cell_index:02d}"
                    anchors.append(
                        {
                            "anchor_id": anchor_id,
                            "kind": "value_cell",
                            "table_index": table_index,
                            "row_index": row_index,
                            "cell_index": cell_index,
                            "label": label or anchor_id,
                            "header": header,
                            "left_label": left_label,
                            "row_label": row_label,
                            "grid_span": grid_span,
                            "width_twips": width,
                        }
                    )
            rows_payload.append({"row_index": row_index, "cells": row_cells})
        tables.append({"table_index": table_index, "row_count": len(rows_payload), "rows": rows_payload})
    return {
        "schema_version": 1,
        "created_at": _now(),
        "doc_id": doc_id,
        "title": title,
        "source_docx": _display(path),
        "summary": {"tableCount": len(tables), "anchorCount": len(anchors), "valueAnchorCount": len(anchors)},
        "tables": tables,
        "anchors": anchors,
    }


def _inject_values(source_docx: Path, out_docx: Path, *, schema: dict[str, Any], values: dict[str, str], anchor_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    target_by_anchor: dict[str, str] = {}
    for field in schema.get("fields", []):
        if not isinstance(field, dict):
            continue
        field_id = str(field.get("field_id") or "")
        anchor_id = str(field.get("docx_anchor_id") or field.get("anchor_id") or "")
        if field_id and anchor_id and field_id in values:
            target_by_anchor[anchor_id] = values[field_id]
    injected: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with zipfile.ZipFile(source_docx) as zf:
            zf.extractall(tmp_dir)
        document_xml = tmp_dir / "word" / "document.xml"
        root = ET.fromstring(document_xml.read_bytes())
        tables = root.findall(".//w:tbl", NS)
        for anchor_id, value in target_by_anchor.items():
            anchor = anchor_by_id.get(anchor_id)
            if not anchor:
                continue
            try:
                cell = tables[int(anchor["table_index"])].findall("./w:tr", NS)[int(anchor["row_index"])].findall("./w:tc", NS)[int(anchor["cell_index"])]
            except (IndexError, KeyError, ValueError):
                continue
            _replace_cell_text(cell, value)
            injected.append({"anchor_id": anchor_id, "value": value, "table_index": anchor.get("table_index"), "row_index": anchor.get("row_index"), "cell_index": anchor.get("cell_index")})
        document_xml.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
        out_docx.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_docx, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(path for path in tmp_dir.rglob("*") if path.is_file()):
                zf.write(file_path, file_path.relative_to(tmp_dir).as_posix())
    return injected


def _render_docx_to_pdf(docx_path: Path, out_dir: Path, *, renderer: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [renderer, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx_path)]
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120, check=False)
    pdf_path = out_dir / f"{docx_path.stem}.pdf"
    if completed.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(f"DOCX PDF render failed: {completed.stderr.strip() or completed.stdout.strip() or completed.returncode}")
    return pdf_path


def _render_pdf_pages(pdf_path: Path, out_dir: Path, *, sample_id: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    import fitz  # type: ignore

    doc = fitz.open(pdf_path)
    paths: list[Path] = []
    try:
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            path = out_dir / f"{sample_id}_page_{index:03d}.png"
            pix.save(path)
            paths.append(path)
    finally:
        doc.close()
    return paths


def _extract_pdf_bboxes(pdf_path: Path, *, schema: dict[str, Any], values: dict[str, str], injected: list[dict[str, Any]]) -> dict[str, Any]:
    import fitz  # type: ignore

    doc = fitz.open(pdf_path)
    used: set[tuple[int, float, float, float, float]] = set()
    boxes: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    field_by_anchor = {str(field.get("docx_anchor_id") or field.get("anchor_id") or ""): field for field in schema.get("fields", []) if isinstance(field, dict)}
    try:
        for item in injected:
            anchor_id = str(item.get("anchor_id") or "")
            field = field_by_anchor.get(anchor_id, {})
            field_id = str(field.get("field_id") or anchor_id)
            value = str(values.get(field_id) or item.get("value") or "")
            if not value.strip():
                continue
            match = None
            for page_index, page in enumerate(doc):
                rects = page.search_for(value)
                for rect in rects:
                    key = (page_index, round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2))
                    if key in used:
                        continue
                    used.add(key)
                    match = (page_index, page.rect, rect)
                    break
                if match:
                    break
            if not match:
                warnings.append({"field_id": field_id, "anchor_id": anchor_id, "type": "pdf_text_bbox_not_found", "value": value})
                continue
            page_index, page_rect, rect = match
            boxes.append(
                {
                    "field_id": field_id,
                    "anchor_id": anchor_id,
                    "page": page_index + 1,
                    "value": value,
                    "bbox_pdf_points": [round(rect.x0, 3), round(rect.y0, 3), round(rect.x1, 3), round(rect.y1, 3)],
                    "page_size_points": [round(page_rect.width, 3), round(page_rect.height, 3)],
                    "semantic_path": field.get("semantic_path"),
                    "key": field.get("key") or field.get("label") or field_id,
                    "source": "docx_injection_pdf_text_search",
                }
            )
    finally:
        doc.close()
    return {"schema_version": 1, "source_pdf": _display(pdf_path), "summary": {"requested": len(injected), "matched": len(boxes), "missing": len(warnings)}, "boxes": boxes, "warnings": warnings}


def _labels_payload(sample_id: str, doc_id: str, bbox_payload: dict[str, Any], values: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "sample_id": sample_id,
        "doc_id": doc_id,
        "source": "docx_pipeline",
        "labels": [
            {
                "field_id": box.get("field_id"),
                "key": box.get("key"),
                "value": values.get(str(box.get("field_id") or ""), box.get("value")),
                "page": box.get("page"),
                "bbox": box.get("bbox_pdf_points"),
                "semantic_path": box.get("semantic_path"),
            }
            for box in bbox_payload.get("boxes", [])
        ],
    }


def _replace_cell_text(cell: ET.Element, value: str) -> None:
    """Replace only the visible cell value while preserving DOCX formatting."""

    paragraphs = cell.findall("./w:p", NS)
    p = paragraphs[0] if paragraphs else ET.SubElement(cell, f"{{{W_NS}}}p")
    p_pr = p.find("w:pPr", NS)
    run_props = _paragraph_default_run_props(p_pr)
    for child in list(p):
        if child is not p_pr:
            p.remove(child)
    r = ET.SubElement(p, f"{{{W_NS}}}r")
    if run_props is not None:
        r.append(run_props)
    t = ET.SubElement(r, f"{{{W_NS}}}t")
    t.text = value
    if value.startswith(" ") or value.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    first_value_paragraph_seen = False
    for child in list(cell):
        if child.tag != f"{{{W_NS}}}p":
            continue
        if child is p and not first_value_paragraph_seen:
            first_value_paragraph_seen = True
            continue
        if first_value_paragraph_seen:
            cell.remove(child)


def _paragraph_default_run_props(p_pr: ET.Element | None) -> ET.Element | None:
    if p_pr is None:
        return None
    r_pr = p_pr.find("w:rPr", NS)
    return deepcopy(r_pr) if r_pr is not None else None


def _resolve_docx_sample(doc_root: Path, sample_path: Path | None) -> DocxSample:
    if sample_path is not None:
        path = sample_path.resolve()
        if not path.exists() or path.suffix.lower() != ".docx":
            raise ValueError(f"not a DOCX sample: {sample_path}")
        return DocxSample(path=path, index=0)
    samples = sorted((doc_root / "samples" / "original").glob("*.docx"))
    if not samples:
        raise ValueError("document has no editable-office DOCX sample")
    return DocxSample(path=samples[0].resolve(), index=0)


def _cell_text(cell: ET.Element) -> str:
    return "".join(text.text or "" for text in cell.findall(".//w:t", NS))


def _grid_span(cell: ET.Element) -> int:
    node = cell.find(".//w:gridSpan", NS)
    if node is None:
        return 1
    try:
        return max(1, int(node.attrib.get(f"{{{W_NS}}}val") or "1"))
    except ValueError:
        return 1


def _cell_width(cell: ET.Element) -> int | None:
    node = cell.find(".//w:tcW", NS)
    if node is None:
        return None
    try:
        return int(node.attrib.get(f"{{{W_NS}}}w") or "0")
    except ValueError:
        return None


def _nearest_left_label(cells: list[ET.Element], cell_index: int) -> str:
    for index in range(cell_index - 1, -1, -1):
        text = _cell_text(cells[index]).strip()
        if text:
            return _clean_label(text)
    return ""


def _label_for_cell(*, text: str, left_label: str, header: str, row_label: str, table_index: int, row_index: int) -> str:
    if text:
        return _clean_label(text)
    if table_index == 2 and row_index > 0 and header:
        return f"거래내역 {row_index} {header}"
    return _clean_label(left_label or header or row_label)


def _clean_label(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or "값"


def _first_non_empty(values: list[str]) -> str:
    for value in values:
        cleaned = _clean_label(value)
        if cleaned:
            return cleaned
    return ""


def _semantic_path_for_anchor(anchor: dict[str, Any], field_id: str) -> list[str]:
    table_index = int(anchor.get("table_index") or 0)
    row_index = int(anchor.get("row_index") or 0)
    label = _clean_label(str(anchor.get("label") or field_id))
    if table_index == 1:
        return ["신청인", label]
    if table_index == 2:
        if "합" in label:
            return ["합계", label]
        return ["거래내역", f"행{row_index:02d}", re.sub(r"^거래내역\s+\d+\s+", "", label)]
    if table_index == 3:
        return ["발급자", label]
    return [f"표{table_index}", label]


def _set_nested_empty(root: dict[str, Any], path: list[str]) -> None:
    current = root
    for part in path[:-1]:
        current = current.setdefault(part, {})
    current[path[-1]] = ""


def _romanize_field_id(label: str, *, fallback: str) -> str:
    mapping = {
        "상호": "company_name",
        "사업자등록번호": "business_registration_number",
        "대표자": "representative_name",
        "연락처": "phone_number",
        "주소": "address",
        "업태": "business_type",
        "종목": "business_item",
        "용도": "purpose",
        "제출처": "submit_to",
        "번호": "line_no",
        "일자": "transaction_date",
        "품명": "item_name",
        "수량": "quantity",
        "단가": "unit_price",
        "금액": "amount",
        "세액": "tax_amount",
        "합계": "total_amount",
        "대표이사": "ceo_name",
    }
    compact = re.sub(r"\s+", "", label)
    for key, value in mapping.items():
        if key in compact:
            prefix = "transaction_" if "거래내역" in compact else ""
            row_match = re.search(r"거래내역\s*(\d+)", label)
            row = f"_{int(row_match.group(1)):02d}" if row_match else ""
            return f"{prefix}{value}{row}".strip("_")
    ascii_id = re.sub(r"[^0-9A-Za-z_]+", "_", label).strip("_").lower()
    return ascii_id or fallback


def _unique_field_id(base: str, used: dict[str, int]) -> str:
    base = base or "field"
    count = used.get(base, 0) + 1
    used[base] = count
    return base if count == 1 else f"{base}_{count:02d}"


def _faker_rule_for_label(label: str, anchor: dict[str, Any]) -> str:
    text = re.sub(r"\s+", "", label)
    if "사업자등록번호" in text:
        return "pattern:###-##-#####"
    if any(token in text for token in ("연락처", "전화")):
        return "person.phone_kr"
    if any(token in text for token in ("주소", "소재지")):
        return "address.ko"
    if any(token in text for token in ("상호", "제출처")):
        return "company.name_ko"
    if any(token in text for token in ("대표자", "대표이사")):
        return "person.name_ko"
    if "업태" in text:
        return "pool:business_types_ko"
    if "종목" in text:
        return "pool:business_items_ko"
    if "용도" in text:
        return "pool:submission_purposes_ko"
    if "일자" in text or "일" == text:
        return "date.kr"
    if "품명" in text:
        return "pool:transaction_items_ko"
    if "수량" in text:
        return "pattern:##"
    if any(token in text for token in ("단가", "금액", "세액", "합계")):
        return "money.krw"
    if "번호" in text:
        return "pattern:##"
    return "free_text.short"


def _value_type_from_rule(rule: str) -> str:
    normalized = rule.strip()
    if normalized in {"person.name_ko", "person.phone_kr", "date.kr", "money.krw", "company.name_ko", "address.ko", "free_text.short"}:
        return normalized
    if normalized.startswith("pool:") or normalized.startswith("pattern:"):
        return "free_text.short"
    return "free_text.short"


def _find_soffice() -> str:
    detected = shutil.which("soffice") or shutil.which("libreoffice")
    if detected:
        return detected
    mac_app = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    if mac_app.exists() and mac_app.is_file():
        return str(mac_app)
    return ""


def _update_docx_manifest(doc_root: Path, *, status: str, artifacts: dict[str, Path], latest_run: dict[str, Any] | None = None) -> None:
    manifest_path = doc_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    artifact_payload = manifest.setdefault("artifacts", {})
    for key, path in artifacts.items():
        artifact_payload[key] = _display(path)
    office_render = dict(manifest.get("office_render") or {})
    current_status = str(office_render.get("status") or "external_render_required")
    if DOCX_STATUS_ORDER.get(status, 0) >= DOCX_STATUS_ORDER.get(current_status, 0) or status in {"failed", "renderer_missing"}:
        office_render["status"] = status
    office_render["backend"] = "libreoffice-cli"
    office_render["required"] = True
    office_render["updated_at"] = _now()
    if latest_run is not None:
        office_render["latest_run"] = {"manifest": artifacts.get("docx_run_manifest") and _display(artifacts["docx_run_manifest"]), "status": latest_run.get("status"), "sample_count": latest_run.get("sample_count")}
    manifest["office_render"] = office_render
    manifest["updated_at"] = _now()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _display(path: Path | str) -> str:
    path = Path(path)
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
