from __future__ import annotations

import binascii
import json
import shutil
import textwrap
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .authoring import _generate_values
from .fonts import load_font
from .policy import load_review_policy
from .registry import RegistryData, load_registry, slugify_title
from .workbench import WORKBENCH_ROOT, document_dir, render_pdf_pages, update_manifest_artifact

ROOT = Path(__file__).resolve().parents[2]
HANDWRITING_DIR = "handwriting_pipeline"
BARCODE_FORMAT = "datafactory-grid-v1"
BARCODE_MODULES = 61
BARCODE_QUIET_MODULES = 4
BARCODE_TOTAL_MODULES = BARCODE_MODULES + BARCODE_QUIET_MODULES * 2
BARCODE_DEFAULT_PIXEL_SIZE = 240
SOURCE_KIND_PRINT_PACK = "handwriting_print_pack"
SOURCE_KIND_SCANNED = "handwriting_scanned"
SOURCE_KIND_QR_REMOVED = "handwriting_qr_removed"
ACCEPTED_STATUS = "accepted"
REVIEW_REQUIRED_STATUS = "review_required"


@dataclass(frozen=True)
class HandwritingAcceptedSample:
    sample_id: str
    image: Path
    gt: Path
    bbox: Path | None
    source_scan: Path | None = None


def create_handwriting_print_pack(
    doc_id: str,
    *,
    count: int,
    seed: int = 20260708,
    run_id: str | None = None,
    qr_bbox: list[int] | tuple[int, int, int, int] | None = None,
    registry: RegistryData | None = None,
    root: Path = WORKBENCH_ROOT,
    allow_printed: bool = False,
) -> dict[str, Any]:
    """Create answer sheets, value/GT files, and QR-bearing blank templates.

    Handwriting documents must not be rendered with synthetic text.  This
    function only renders an operator answer sheet and a clean template with a
    machine-readable DataFactory barcode.  The final handwriting image must be
    produced by printing the template and writing values by hand.
    """

    if count <= 0:
        raise ValueError("count must be positive")
    registry = registry or load_registry()
    doc = registry.documents.get(doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {doc_id}")
    if not allow_printed and str(doc.writing_method).strip() != "수기":
        raise ValueError(f"handwriting print pack requires registry writingMethod=수기: {doc_id}")

    doc_root = document_dir(doc, root)
    authoring_dir = doc_root / "authoring"
    schema_path = authoring_dir / "schema.json"
    faker_profile_path = authoring_dir / "faker_profile.json"
    if not schema_path.exists() or not faker_profile_path.exists():
        raise FileNotFoundError(f"authoring schema/faker profile not found for {doc_id}")

    schema = _read_json(schema_path)
    faker_profile = _read_json(faker_profile_path)
    fields = [field for field in schema.get("fields", []) if isinstance(field, dict)]
    semantic_schema = _semantic_schema(schema)
    field_paths = _field_semantic_paths(fields)
    template_path = _resolve_template_image(schema)
    template = Image.open(template_path).convert("RGB")
    bbox = _resolve_qr_bbox(qr_bbox, width=template.width, height=template.height)
    resolved_run_id = run_id or _run_id()
    run_dir = doc_root / HANDWRITING_DIR / "print_packs" / resolved_run_id
    dirs = _ensure_dirs(run_dir, ["answer_sheets", "qr_templates", "barcodes", "values", "gt", "bbox"])

    primary_schema_path = run_dir / "schema.json"
    primary_schema_path.write_text(json.dumps(_primary_schema_payload(semantic_schema, field_paths), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    samples: list[dict[str, Any]] = []
    for index in range(count):
        sample_id = f"sample_{index:03d}"
        values, warnings = _generate_values(schema, faker_profile, __import__("random").Random(seed + index))
        gt_path = dirs["gt"] / f"{sample_id}.json"
        bbox_path = dirs["bbox"] / f"{sample_id}-bbox.json"
        values_path = dirs["values"] / f"{sample_id}.values.json"
        answer_png = dirs["answer_sheets"] / f"{sample_id}.png"
        answer_pdf = dirs["answer_sheets"] / f"{sample_id}.pdf"
        barcode_path = dirs["barcodes"] / f"{sample_id}.png"
        template_png = dirs["qr_templates"] / f"{sample_id}.png"
        template_pdf = dirs["qr_templates"] / f"{sample_id}.pdf"

        gt_payload = _semantic_values_payload(semantic_schema, field_paths, values)
        bbox_payload = _semantic_bbox_payload(schema, field_paths)
        gt_path.write_text(json.dumps(gt_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        bbox_path.write_text(json.dumps(bbox_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        values_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "source_kind": SOURCE_KIND_PRINT_PACK,
                    "doc_id": doc_id,
                    "sample_id": sample_id,
                    "run_id": resolved_run_id,
                    "values": values,
                    "generation_warnings": warnings,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        payload = {
            "project": "datafactory",
            "barcode_format": BARCODE_FORMAT,
            "doc_id": doc_id,
            "sample_id": sample_id,
            "run_id": resolved_run_id,
            "gt_path": _display_path(gt_path),
            "bbox_path": _display_path(bbox_path),
        }
        barcode = encode_barcode_image(payload, pixel_size=bbox[2])
        barcode.save(barcode_path)
        template_with_qr = template.copy()
        template_with_qr.paste(barcode.resize((bbox[2], bbox[3])), (bbox[0], bbox[1]))
        template_with_qr.save(template_png)
        template_with_qr.save(template_pdf, "PDF", resolution=200.0)
        _write_answer_sheet(
            answer_png,
            doc_title=doc.title,
            doc_id=doc_id,
            sample_id=sample_id,
            run_id=resolved_run_id,
            values=values,
            fields=fields,
            field_paths=field_paths,
        )
        Image.open(answer_png).convert("RGB").save(answer_pdf, "PDF", resolution=200.0)

        samples.append(
            {
                "sample_id": sample_id,
                "doc_id": doc_id,
                "run_id": resolved_run_id,
                "source_kind": SOURCE_KIND_PRINT_PACK,
                "qr_payload": payload,
                "qr_bbox": bbox,
                "template_size": [template.width, template.height],
                "answer_sheet": _display_path(answer_png),
                "answer_sheet_pdf": _display_path(answer_pdf),
                "qr_template": _display_path(template_png),
                "qr_template_pdf": _display_path(template_pdf),
                "barcode": _display_path(barcode_path),
                "values": _display_path(values_path),
                "gt": _display_path(gt_path),
                "bbox": _display_path(bbox_path),
                "status": "print_ready",
                "generation_warning_count": len(warnings),
            }
        )

    manifest = {
        "schema_version": 1,
        "source_kind": SOURCE_KIND_PRINT_PACK,
        "doc_id": doc_id,
        "title": doc.title,
        "run_id": resolved_run_id,
        "created_at": _now(),
        "count": count,
        "seed": seed,
        "barcode_format": BARCODE_FORMAT,
        "template": _display_path(template_path),
        "qr_bbox": bbox,
        "schema": _display_path(primary_schema_path),
        "samples": samples,
        "status": "print_ready",
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_manifest_artifact(doc_id, "handwriting_print_pack", manifest_path, registry=registry, root=root)
    return {"summary": {"docId": doc_id, "runId": resolved_run_id, "sampleCount": count, "status": "print_ready"}, "paths": {"runDir": _display_path(run_dir), "manifest": _display_path(manifest_path)}, "manifest": manifest}


def intake_handwriting_scans(
    *,
    doc_id: str | None = None,
    scan_paths: list[str | Path] | None = None,
    scan_dir: str | Path | None = None,
    print_pack_manifest: str | Path | None = None,
    run_id: str | None = None,
    registry: RegistryData | None = None,
    root: Path = WORKBENCH_ROOT,
) -> dict[str, Any]:
    """Decode scanned handwriting templates and pair them with prebuilt GT."""

    registry = registry or load_registry()
    candidates = _scan_input_paths(scan_paths=scan_paths, scan_dir=scan_dir)
    if not candidates:
        raise ValueError("scan_paths or scan_dir must contain at least one image/PDF")
    manifests = _candidate_print_pack_manifests(doc_id=doc_id, print_pack_manifest=print_pack_manifest, registry=registry, root=root)
    if not manifests:
        raise FileNotFoundError("no handwriting print pack manifest found")
    resolved_doc_id = doc_id or str(_read_json(manifests[-1]).get("doc_id") or "")
    if not resolved_doc_id:
        raise ValueError("doc_id could not be resolved")
    doc = registry.documents.get(resolved_doc_id)
    if doc is None:
        raise ValueError(f"unknown docId: {resolved_doc_id}")
    resolved_run_id = run_id or _run_id()
    run_dir = document_dir(doc, root) / HANDWRITING_DIR / "scanned_intake" / resolved_run_id
    dirs = _ensure_dirs(run_dir, ["raw_scans", "decoded", "qr_removed", "matched_gt", "review"])
    expanded_scans = _expand_scan_inputs(candidates)
    records: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []

    for index, source in enumerate(expanded_scans):
        raw_path = dirs["raw_scans"] / f"scan_{index:03d}{source.suffix.lower() or '.png'}"
        shutil.copy2(source, raw_path)
        record = _intake_single_scan(raw_path, manifests, dirs=dirs)
        records.append(record)
        if record.get("status") == ACCEPTED_STATUS:
            accepted.append(record)

    manifest = {
        "schema_version": 1,
        "source_kind": SOURCE_KIND_SCANNED,
        "doc_id": resolved_doc_id,
        "title": doc.title,
        "run_id": resolved_run_id,
        "created_at": _now(),
        "print_pack_manifests": [_display_path(path) for path in manifests],
        "scan_count": len(records),
        "accepted_count": len(accepted),
        "review_required_count": len([item for item in records if item.get("status") == REVIEW_REQUIRED_STATUS]),
        "records": records,
        "accepted_samples": [
            {
                "sample_id": item["sample_id"],
                "image": item["qr_removed"],
                "gt": item["matched_gt"],
                "bbox": item.get("matched_bbox", ""),
                "source_scan": item["raw_scan"],
            }
            for item in accepted
        ],
        "status": ACCEPTED_STATUS if accepted and len(accepted) == len(records) else REVIEW_REQUIRED_STATUS,
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_manifest_artifact(resolved_doc_id, "handwriting_scan_intake", manifest_path, registry=registry, root=root)
    return {"summary": {"docId": resolved_doc_id, "runId": resolved_run_id, "scanCount": len(records), "acceptedCount": len(accepted), "reviewRequiredCount": manifest["review_required_count"]}, "paths": {"runDir": _display_path(run_dir), "manifest": _display_path(manifest_path)}, "manifest": manifest}


def latest_accepted_handwriting_samples(item: dict[str, Any], *, root: Path = ROOT) -> list[HandwritingAcceptedSample]:
    manifest_value = item.get("latestHandwritingScanIntake") or (item.get("manifest", {}).get("artifacts", {}) if isinstance(item.get("manifest"), dict) else {}).get("handwriting_scan_intake")
    if not manifest_value:
        return []
    manifest_path = _resolve_path(manifest_value, base=root)
    if not manifest_path.exists():
        return []
    payload = _read_json(manifest_path)
    samples: list[HandwritingAcceptedSample] = []
    for raw in payload.get("accepted_samples", []) if isinstance(payload.get("accepted_samples"), list) else []:
        if not isinstance(raw, dict):
            continue
        image = _resolve_path(raw.get("image"), base=root)
        gt = _resolve_path(raw.get("gt"), base=root)
        bbox_value = raw.get("bbox")
        bbox = _resolve_path(bbox_value, base=root) if bbox_value else None
        if image.exists() and gt.exists():
            samples.append(HandwritingAcceptedSample(str(raw.get("sample_id") or image.stem), image, gt, bbox if bbox and bbox.exists() else None, _resolve_path(raw.get("source_scan"), base=root) if raw.get("source_scan") else None))
    return samples


def encode_barcode_image(payload: dict[str, Any], *, pixel_size: int = BARCODE_DEFAULT_PIXEL_SIZE) -> Image.Image:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(text, level=9)
    length = len(compressed)
    capacity_bytes = (BARCODE_MODULES * BARCODE_MODULES - 48) // 8
    if length > capacity_bytes:
        raise ValueError(f"barcode payload too large: {length} > {capacity_bytes}")
    crc = binascii.crc32(compressed) & 0xFFFFFFFF
    bits = _int_bits(length, 16) + _int_bits(crc, 32)
    for byte in compressed:
        bits.extend(_int_bits(byte, 8))
    while len(bits) < BARCODE_MODULES * BARCODE_MODULES:
        bits.append((len(bits) // 7 + len(bits)) % 2)

    module = max(2, int(pixel_size) // BARCODE_TOTAL_MODULES)
    size = BARCODE_TOTAL_MODULES * module
    image = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(image)
    for row in range(BARCODE_MODULES):
        for col in range(BARCODE_MODULES):
            if bits[row * BARCODE_MODULES + col]:
                x0 = (col + BARCODE_QUIET_MODULES) * module
                y0 = (row + BARCODE_QUIET_MODULES) * module
                draw.rectangle([x0, y0, x0 + module - 1, y0 + module - 1], fill="black")
    draw.rectangle([0, 0, size - 1, size - 1], outline="black", width=max(1, module))
    return image


def decode_barcode_image(image: Image.Image) -> dict[str, Any]:
    sample = image.convert("L").resize((BARCODE_TOTAL_MODULES, BARCODE_TOTAL_MODULES), Image.Resampling.BOX)
    pixels = sample.load()
    bits: list[int] = []
    for row in range(BARCODE_MODULES):
        for col in range(BARCODE_MODULES):
            x = col + BARCODE_QUIET_MODULES
            y = row + BARCODE_QUIET_MODULES
            bits.append(1 if int(pixels[x, y]) < 128 else 0)
    length = _bits_int(bits[:16])
    crc = _bits_int(bits[16:48])
    payload_bits = bits[48 : 48 + length * 8]
    if len(payload_bits) < length * 8:
        raise ValueError("barcode payload is truncated")
    data = bytes(_bits_int(payload_bits[index : index + 8]) for index in range(0, len(payload_bits), 8))
    if (binascii.crc32(data) & 0xFFFFFFFF) != crc:
        raise ValueError("barcode checksum mismatch")
    payload = json.loads(zlib.decompress(data).decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("barcode_format") != BARCODE_FORMAT:
        raise ValueError("unsupported barcode payload")
    return payload


def _intake_single_scan(raw_path: Path, manifests: list[Path], *, dirs: dict[str, Path]) -> dict[str, Any]:
    image = Image.open(raw_path).convert("RGB")
    failures: list[str] = []
    for manifest_path in reversed(manifests):
        manifest = _read_json(manifest_path)
        for sample in manifest.get("samples", []) if isinstance(manifest.get("samples"), list) else []:
            if not isinstance(sample, dict):
                continue
            try:
                bbox = _scaled_bbox(sample.get("qr_bbox"), sample.get("template_size"), [image.width, image.height], pad_ratio=0.0)
                crop = image.crop((bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3]))
                try:
                    payload = decode_barcode_image(crop)
                except Exception:
                    padded = _scaled_bbox(sample.get("qr_bbox"), sample.get("template_size"), [image.width, image.height], pad_ratio=0.03)
                    padded_crop = image.crop((padded[0], padded[1], padded[0] + padded[2], padded[1] + padded[3]))
                    payload = decode_barcode_image(padded_crop)
                    bbox = padded
                if payload.get("sample_id") != sample.get("sample_id") or payload.get("doc_id") != sample.get("doc_id"):
                    raise ValueError("decoded payload does not match candidate sample")
                return _accept_scan(raw_path, image, bbox, payload, sample, dirs=dirs)
            except Exception as exc:
                failures.append(f"{manifest_path.name}/{sample.get('sample_id')}: {exc}")
    review_path = dirs["review"] / f"{raw_path.stem}.json"
    record = {
        "raw_scan": _display_path(raw_path),
        "status": REVIEW_REQUIRED_STATUS,
        "reason": "barcode_decode_failed",
        "failures": failures[-8:],
        "review": _display_path(review_path),
    }
    review_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def _accept_scan(raw_path: Path, image: Image.Image, bbox: list[int], payload: dict[str, Any], sample: dict[str, Any], *, dirs: dict[str, Path]) -> dict[str, Any]:
    sample_id = str(payload["sample_id"])
    decoded_path = dirs["decoded"] / f"{sample_id}.json"
    qr_removed_path = dirs["qr_removed"] / f"{sample_id}.jpg"
    matched_gt_path = dirs["matched_gt"] / f"{sample_id}.json"
    matched_bbox_path = dirs["matched_gt"] / f"{sample_id}-bbox.json"
    decoded_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    removed = image.copy()
    draw = ImageDraw.Draw(removed)
    pad = 2
    draw.rectangle([bbox[0] - pad, bbox[1] - pad, bbox[0] + bbox[2] + pad, bbox[1] + bbox[3] + pad], fill="white")
    removed.save(qr_removed_path, "JPEG", quality=95)
    gt_source = _resolve_path(payload.get("gt_path"))
    if not gt_source.exists():
        raise FileNotFoundError(gt_source)
    shutil.copy2(gt_source, matched_gt_path)
    bbox_source = _resolve_path(payload.get("bbox_path") or sample.get("bbox"))
    matched_bbox = ""
    if bbox_source.exists():
        shutil.copy2(bbox_source, matched_bbox_path)
        matched_bbox = _display_path(matched_bbox_path)
    return {
        "raw_scan": _display_path(raw_path),
        "sample_id": sample_id,
        "doc_id": str(payload.get("doc_id") or ""),
        "print_pack_run_id": str(payload.get("run_id") or ""),
        "status": ACCEPTED_STATUS,
        "source_kind": SOURCE_KIND_QR_REMOVED,
        "decoded": _display_path(decoded_path),
        "qr_removed": _display_path(qr_removed_path),
        "matched_gt": _display_path(matched_gt_path),
        "matched_bbox": matched_bbox,
        "qr_bbox": bbox,
    }


def _write_answer_sheet(path: Path, *, doc_title: str, doc_id: str, sample_id: str, run_id: str, values: dict[str, str], fields: list[dict[str, Any]], field_paths: dict[str, str]) -> None:
    rows: list[tuple[str, str]] = []
    for field in fields:
        field_id = str(field.get("field_id") or "")
        if field_id not in values:
            continue
        key = field_paths.get(field_id) or str(field.get("label") or field_id)
        value = str(values.get(field_id) or "")
        if not value:
            continue
        rows.append((key, value))
    font_title = load_font(28)
    font_body = load_font(18)
    width = 1240
    line_height = 34
    height = max(1754, 180 + line_height * (len(rows) + 4))
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 45), "수기 작성 답안지", font=font_title, fill=(20, 26, 38))
    draw.text((60, 90), f"{doc_title} · {doc_id} · {sample_id} · run {run_id}", font=font_body, fill=(70, 78, 96))
    draw.text((60, 135), "작업자는 아래 값을 빈 템플릿의 대응 bbox에 손글씨로 베껴 적습니다. 이 답안지는 최종 이미지로 제출하지 않습니다.", font=font_body, fill=(120, 70, 0))
    y = 190
    for index, (key, value) in enumerate(rows, start=1):
        draw.text((60, y), f"{index:03d}. {key}", font=font_body, fill=(35, 45, 60))
        wrapped = textwrap.wrap(value, width=58) or [""]
        draw.text((460, y), wrapped[0], font=font_body, fill=(0, 0, 0))
        y += line_height
        for extra in wrapped[1:]:
            draw.text((460, y), extra, font=font_body, fill=(0, 0, 0))
            y += line_height
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    payload = schema.get("semantic_schema") if isinstance(schema.get("semantic_schema"), dict) else {}
    return _schema_value_template(payload)


def _field_semantic_paths(fields: list[dict[str, Any]]) -> dict[str, str]:
    paths: dict[str, str] = {}
    for field in fields:
        field_id = str(field.get("field_id") or "")
        semantic_path = field.get("semantic_path")
        if isinstance(semantic_path, list) and semantic_path:
            paths[field_id] = ".".join(str(part) for part in semantic_path if str(part))
            continue
        export = field.get("export") if isinstance(field.get("export"), dict) else {}
        paths[field_id] = str(export.get("json_path") or field.get("label") or field_id)
    return paths


def _semantic_values_payload(semantic_schema: dict[str, Any], field_paths: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    payload = _schema_value_template(semantic_schema)
    for field_id, path in field_paths.items():
        if field_id in values:
            _set_semantic_value(payload, path, str(values[field_id]))
    return payload


def _primary_schema_payload(semantic_schema: dict[str, Any], field_paths: dict[str, str]) -> dict[str, Any]:
    payload = _schema_value_template(semantic_schema)
    for path in field_paths.values():
        _set_semantic_value(payload, path, "")
    return payload


def _semantic_bbox_payload(schema: dict[str, Any], field_paths: dict[str, str]) -> dict[str, Any]:
    review_path = _resolve_path(schema.get("source_review") or "")
    if not review_path.exists():
        return {}
    policy = load_review_policy(review_path)
    labels = {label.id: label for label in policy.labels}
    width = max(1, int(schema.get("image", {}).get("width") or policy.image_width or 1))
    height = max(1, int(schema.get("image", {}).get("height") or policy.image_height or 1))
    payload: dict[str, Any] = {}
    for field in schema.get("fields", []) if isinstance(schema.get("fields"), list) else []:
        if not isinstance(field, dict):
            continue
        field_id = str(field.get("field_id") or "")
        path = field_paths.get(field_id)
        label = labels.get(str(field.get("bbox_label_id") or field.get("source_detection_id") or ""))
        if not path or label is None:
            continue
        x, y, w, h = label.bbox.to_list()
        _set_semantic_value(payload, path, {"l": round(x / width, 4), "t": round(y / height, 4), "r": round((x + w) / width, 4), "b": round((y + h) / height, 4)})
    return payload


def _schema_value_template(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _schema_value_template(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_schema_value_template(child) for child in value]
    return ""


def _set_semantic_value(payload: dict[str, Any], path: str, value: Any) -> None:
    if path in payload:
        payload[path] = value
        return
    parts = [part for part in str(path).split(".") if part]
    cursor: Any = payload
    for part in parts[:-1]:
        if not isinstance(cursor, dict):
            payload[path] = value
            return
        cursor = cursor.setdefault(part, {})
    if isinstance(cursor, dict) and parts:
        cursor[parts[-1]] = value
    else:
        payload[path] = value


def _resolve_template_image(schema: dict[str, Any]) -> Path:
    for key in ("source_inpainted", "source_image"):
        path = _resolve_path(schema.get(key) or "")
        if path.exists() and path.is_file():
            return path
    raise FileNotFoundError("schema.source_inpainted/source_image does not exist")


def _resolve_qr_bbox(value: list[int] | tuple[int, int, int, int] | None, *, width: int, height: int) -> list[int]:
    if value and len(value) == 4:
        x, y, w, h = [int(round(float(item))) for item in value]
        if w > 20 and h > 20:
            left = min(max(0, x), max(0, width - 1))
            top = min(max(0, y), max(0, height - 1))
            right = min(width, left + max(1, w))
            bottom = min(height, top + max(1, h))
            return [left, top, max(1, right - left), max(1, bottom - top)]
    size = min(BARCODE_DEFAULT_PIXEL_SIZE, max(96, int(min(width, height) * 0.16)))
    return [max(0, width - size - 24), 24, size, size]


def _scaled_bbox(bbox_value: Any, source_size: Any, target_size: list[int], *, pad_ratio: float = 0.0) -> list[int]:
    if not isinstance(bbox_value, list) or len(bbox_value) != 4:
        raise ValueError("sample has no qr_bbox")
    if not isinstance(source_size, list) or len(source_size) != 2:
        raise ValueError("sample has no template_size")
    sx, sy = max(1, float(source_size[0])), max(1, float(source_size[1]))
    tx, ty = max(1, float(target_size[0])), max(1, float(target_size[1]))
    x, y, w, h = [float(item) for item in bbox_value]
    scale_x, scale_y = tx / sx, ty / sy
    pad = int(round(min(w * scale_x, h * scale_y) * max(0.0, pad_ratio)))
    left = max(0, int(round(x * scale_x)) - pad)
    top = max(0, int(round(y * scale_y)) - pad)
    right = min(int(tx), int(round((x + w) * scale_x)) + pad)
    bottom = min(int(ty), int(round((y + h) * scale_y)) + pad)
    return [left, top, max(1, right - left), max(1, bottom - top)]


def _scan_input_paths(*, scan_paths: list[str | Path] | None, scan_dir: str | Path | None) -> list[Path]:
    paths: list[Path] = []
    for raw in scan_paths or []:
        path = _resolve_path(raw)
        if path.exists() and path.is_file():
            paths.append(path)
    if scan_dir:
        directory = _resolve_path(scan_dir)
        if directory.exists() and directory.is_dir():
            paths.extend(sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".pdf"}))
    return list(dict.fromkeys(paths))


def _expand_scan_inputs(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if path.suffix.lower() == ".pdf":
            expanded.extend(render_pdf_pages(path, scale=2.0, image_format="JPEG"))
        else:
            expanded.append(path)
    return expanded


def _candidate_print_pack_manifests(*, doc_id: str | None, print_pack_manifest: str | Path | None, registry: RegistryData, root: Path) -> list[Path]:
    if print_pack_manifest:
        path = _resolve_path(print_pack_manifest)
        return [path] if path.exists() else []
    manifests: list[Path] = []
    docs = [registry.documents[doc_id]] if doc_id and doc_id in registry.documents else list(registry.documents.values())
    for doc in docs:
        base = document_dir(doc, root) / HANDWRITING_DIR / "print_packs"
        if base.exists():
            manifests.extend(sorted(base.glob("*/manifest.json")))
    return manifests


def _ensure_dirs(root: Path, names: list[str]) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    result = {}
    for name in names:
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        result[name] = path
    return result


def _int_bits(value: int, width: int) -> list[int]:
    return [(int(value) >> shift) & 1 for shift in range(width - 1, -1, -1)]


def _bits_int(bits: list[int]) -> int:
    value = 0
    for bit in bits:
        value = (value << 1) | (1 if bit else 0)
    return value


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(value: Any, *, base: Path = ROOT) -> Path:
    text = str(value or "").strip()
    path = Path(text)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def _display_path(path: Path | str) -> str:
    path = Path(path)
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)

