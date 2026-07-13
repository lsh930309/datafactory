from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .inpaint import lama_inpaint

from .authoring import _generate_values, _template_from_authoring
from .fonts import load_font
from .policy import load_review_policy
from .render import render_template
from .registry import RegistryData, load_registry, slugify_title
from .workbench import WORKBENCH_ROOT, document_dir, render_pdf_pages, update_manifest_artifact

ROOT = Path(__file__).resolve().parents[2]
HANDWRITING_DIR = "handwriting_pipeline"
QR_FORMAT = "datafactory-qr-v1"
DEFAULT_WECHAT_QR_MODEL_DIR = Path("/Users/lsh930309/projects/SamsungLife/models/wechat_qrcode")
QR_DEFAULT_PIXEL_SIZE = 240
HANDWRITING_PREVIEW_FILL = [220, 0, 0]
SOURCE_KIND_PRINT_PACK = "handwriting_print_pack"
SOURCE_KIND_SCANNED = "handwriting_scanned"
SOURCE_KIND_QR_REMOVED = "handwriting_qr_removed"
ACCEPTED_STATUS = "accepted"
REVIEW_REQUIRED_STATUS = "review_required"
_WECHAT_DETECTOR: Any | None = None
_WECHAT_DETECTOR_ATTEMPTED = False


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
    """Create handwriting print packs.

    One print-pack sample is a two-page PDF:
    1. answer sheet: red no-style values rendered at handwriting bboxes
    2. problem sheet: printed-mode values rendered with stylesheet + QR marker

    The generated GT/schema/raw-bbox files are paired later with scanned pages
    after QR decoding and QR-region inpainting.
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
    stylesheet_path = authoring_dir / "stylesheet.json"
    stylesheet = _read_json(stylesheet_path) if stylesheet_path.exists() else {}
    fields = [field for field in schema.get("fields", []) if isinstance(field, dict)]
    semantic_schema = _semantic_schema(schema)
    field_paths = _field_semantic_paths(fields)
    handwriting_fields = _visible_fields_for_render_mode(fields, "handwriting")
    printed_fields = _visible_fields_for_render_mode(fields, "printed")
    if printed_fields and not stylesheet_path.exists():
        raise FileNotFoundError(f"stylesheet required for printed handwriting bbox fields: {stylesheet_path}")
    template_path = _resolve_template_image(schema)
    template = Image.open(template_path).convert("RGB")
    bbox = _resolve_qr_bbox(qr_bbox or _schema_qr_bbox(schema), width=template.width, height=template.height)
    resolved_run_id = run_id or _run_id()
    run_dir = doc_root / HANDWRITING_DIR / "print_packs" / resolved_run_id
    dirs = _ensure_dirs(run_dir, ["answer_sheets", "problem_sheets", "qr", "values", "gt", "bbox"])
    public_dir = _handwriting_public_doc_dir(doc, root=root)
    public_dir.mkdir(parents=True, exist_ok=True)

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
        qr_path = dirs["qr"] / f"{sample_id}.png"
        problem_png = dirs["problem_sheets"] / f"{sample_id}.png"
        public_pdf = public_dir / f"{sample_id}.pdf"
        public_gt = public_dir / f"{sample_id}.json"
        public_bbox = public_dir / f"{sample_id}-bbox.json"

        gt_payload = _semantic_values_payload(semantic_schema, field_paths, values)
        bbox_payload = _semantic_bbox_payload(schema, field_paths)
        gt_path.write_text(json.dumps(gt_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        bbox_path.write_text(json.dumps(bbox_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        public_gt.write_text(json.dumps(gt_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        public_bbox.write_text(json.dumps(bbox_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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

        answer_sheet = _render_answer_sheet(template_path, schema=schema, fields=handwriting_fields, values=values)
        answer_sheet.save(answer_png)
        printed_template = _render_printed_fields(template_path, schema=schema, stylesheet=stylesheet, fields=printed_fields, values=values)

        payload = {
            "doc_id": doc_id,
            "sample_id": sample_id,
            "run_id": resolved_run_id,
        }
        qr_image = encode_marker_image(payload, pixel_size=bbox[2])
        qr_image.save(qr_path)
        problem_sheet = printed_template.copy()
        problem_sheet.paste(qr_image.resize((bbox[2], bbox[3]), Image.Resampling.NEAREST), (bbox[0], bbox[1]))
        problem_sheet.save(problem_png)
        _save_two_page_pdf(public_pdf, [answer_sheet, problem_sheet])

        samples.append(
            {
                "sample_id": sample_id,
                "doc_id": doc_id,
                "run_id": resolved_run_id,
                "source_kind": SOURCE_KIND_PRINT_PACK,
                "qr_payload": payload,
                "qr_bbox": bbox,
                "template_size": [template.width, template.height],
                "print_pack_pdf": _display_path(public_pdf),
                "public_gt": _display_path(public_gt),
                "public_bbox": _display_path(public_bbox),
                "answer_sheet": _display_path(answer_png),
                "problem_sheet": _display_path(problem_png),
                "qr_image": _display_path(qr_path),
                "values": _display_path(values_path),
                "gt": _display_path(gt_path),
                "bbox": _display_path(bbox_path),
                "status": "print_ready",
                "generation_warning_count": len(warnings),
                "handwriting_field_count": len(handwriting_fields),
                "printed_field_count": len(printed_fields),
                "handwriting_fields": [str(field.get("field_id") or "") for field in handwriting_fields],
                "printed_fields": [str(field.get("field_id") or "") for field in printed_fields],
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
        "marker_format": QR_FORMAT,
        "barcode_format": QR_FORMAT,
        "template": _display_path(template_path),
        "qr_bbox": bbox,
        "schema": _display_path(primary_schema_path),
        "public_dir": _display_path(public_dir),
        "public_schema": _display_path(public_dir / "schema.json"),
        "samples": samples,
        "status": "print_ready",
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(primary_schema_path, public_dir / "schema.json")
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
    resolved_run_id = run_id or _run_id()
    resolved_doc_id = doc_id or ""
    doc = registry.documents.get(resolved_doc_id) if resolved_doc_id else None
    if resolved_doc_id and doc is None:
        raise ValueError(f"unknown docId: {resolved_doc_id}")
    run_dir = (document_dir(doc, root) / HANDWRITING_DIR / "scanned_intake" / resolved_run_id) if doc is not None else (_workbench_root_from_documents_root(root) / "handwriting_scan_intake" / resolved_run_id)
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
        "title": doc.title if doc is not None else "수기 스캔 통합 처리",
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
                "doc_id": item["doc_id"],
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
    accepted_doc_ids = sorted({str(item.get("doc_id") or "") for item in accepted if item.get("doc_id")})
    for accepted_doc_id in accepted_doc_ids or ([resolved_doc_id] if resolved_doc_id else []):
        update_manifest_artifact(accepted_doc_id, "handwriting_scan_intake", manifest_path, registry=registry, root=root)
    return {"summary": {"docId": resolved_doc_id, "runId": resolved_run_id, "scanCount": len(records), "acceptedCount": len(accepted), "reviewRequiredCount": manifest["review_required_count"]}, "paths": {"runDir": _display_path(run_dir), "manifest": _display_path(manifest_path)}, "manifest": manifest}


def render_handwriting_authoring_preview(
    doc_id: str,
    schema: dict[str, Any],
    stylesheet: dict[str, Any],
    faker_profile: dict[str, Any],
    *,
    out_dir: Path,
    seed: int = 1234,
    sample_id: str = "live_preview",
    qr_bbox: list[int] | tuple[int, int, int, int] | None = None,
) -> dict[str, Any]:
    """Render handwriting authoring preview with printed fields and red handwriting placeholders."""

    template_path = _resolve_template_image(schema)
    template = Image.open(template_path).convert("RGB")
    fields = [field for field in schema.get("fields", []) if isinstance(field, dict)]
    printed_fields = _visible_fields_for_render_mode(fields, "printed")
    handwriting_fields = _visible_fields_for_render_mode(fields, "handwriting")
    values, warnings = _generate_values(schema, faker_profile, __import__("random").Random(seed), force_visible=True)
    rendered = _render_handwriting_preview_fields(
        template_path,
        schema=schema,
        stylesheet=stylesheet,
        printed_fields=printed_fields,
        handwriting_fields=handwriting_fields,
        values=values,
    )
    bbox = _resolve_qr_bbox(qr_bbox or _schema_qr_bbox(schema), width=template.width, height=template.height)
    payload = {
        "doc_id": doc_id,
        "sample_id": sample_id,
        "run_id": "live_preview",
    }
    marker = encode_marker_image(payload, pixel_size=bbox[2]).resize((bbox[2], bbox[3]), Image.Resampling.NEAREST)
    rendered.paste(marker, (bbox[0], bbox[1]))
    out_dir.mkdir(parents=True, exist_ok=True)
    image_path = out_dir / f"{sample_id}.png"
    kv_path = out_dir / f"{sample_id}.kv.json"
    bbox_path = out_dir / f"{sample_id}.bbox.json"
    overlay_path = out_dir / f"{sample_id}.overlay.png"
    validation_path = out_dir / f"{sample_id}.validation_report.json"
    rendered.save(image_path)
    rendered.save(overlay_path)
    kv_path.write_text(json.dumps({"sample_id": sample_id, "doc_id": doc_id, "values": values}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bbox_path.write_text(json.dumps({"sample_id": sample_id, "doc_id": doc_id, "qr_bbox": bbox}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation_path.write_text(json.dumps({"warnings": warnings, "qr_bbox": bbox, "printed_field_count": len(printed_fields), "handwriting_field_count": len(handwriting_fields)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "image": image_path,
        "kv": kv_path,
        "bbox": bbox_path,
        "overlay": overlay_path,
        "validation_report": validation_path,
        "sample_id": sample_id,
        "field_count": len(fields),
        "warning_count": len(warnings),
        "qr_bbox": bbox,
        "printed_field_count": len(printed_fields),
        "handwriting_field_count": len(handwriting_fields),
    }


def latest_accepted_handwriting_samples(item: dict[str, Any], *, root: Path = ROOT) -> list[HandwritingAcceptedSample]:
    manifest_value = item.get("latestHandwritingScanIntake") or (item.get("manifest", {}).get("artifacts", {}) if isinstance(item.get("manifest"), dict) else {}).get("handwriting_scan_intake")
    if not manifest_value:
        return []
    manifest_path = _resolve_path(manifest_value, base=root)
    if not manifest_path.exists():
        return []
    payload = _read_json(manifest_path)
    samples: list[HandwritingAcceptedSample] = []
    expected_doc_id = str(item.get("docId") or item.get("doc_id") or "").strip()
    for raw in payload.get("accepted_samples", []) if isinstance(payload.get("accepted_samples"), list) else []:
        if not isinstance(raw, dict):
            continue
        if expected_doc_id and str(raw.get("doc_id") or "").strip() not in {"", expected_doc_id}:
            continue
        image = _resolve_path(raw.get("image"), base=root)
        gt = _resolve_path(raw.get("gt"), base=root)
        bbox_value = raw.get("bbox")
        bbox = _resolve_path(bbox_value, base=root) if bbox_value else None
        if image.exists() and gt.exists():
            samples.append(HandwritingAcceptedSample(str(raw.get("sample_id") or image.stem), image, gt, bbox if bbox and bbox.exists() else None, _resolve_path(raw.get("source_scan"), base=root) if raw.get("source_scan") else None))
    return samples


def encode_marker_image(payload: dict[str, Any], *, pixel_size: int = QR_DEFAULT_PIXEL_SIZE) -> Image.Image:
    return encode_qr_image(_minimal_qr_payload(payload), pixel_size=pixel_size)


def _qrcode_available() -> bool:
    try:
        import qrcode  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


def encode_qr_image(payload: dict[str, Any], *, pixel_size: int = QR_DEFAULT_PIXEL_SIZE) -> Image.Image:
    try:
        import qrcode  # type: ignore
    except Exception as exc:
        raise RuntimeError("qrcode[pil] is required for standard QR marker generation") from exc
    qr_payload = _minimal_qr_payload(payload)
    text = json.dumps(qr_payload, ensure_ascii=False, separators=(",", ":"))
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    if pixel_size > 0:
        image = image.resize((int(pixel_size), int(pixel_size)), Image.Resampling.NEAREST)
    return image


def decode_marker_image(image: Image.Image, *, wechat_detector: Any | None = None) -> dict[str, Any]:
    return decode_qr_image(image, wechat_detector=wechat_detector)


def decode_qr_image(image: Image.Image, *, wechat_detector: Any | None = None) -> dict[str, Any]:
    try:
        import numpy as np  # type: ignore
    except Exception as exc:
        raise RuntimeError("numpy is required for QR decoding") from exc
    rgb = image.convert("RGB")
    candidates: list[str] = []
    try:
        import cv2  # type: ignore
    except Exception:
        cv2 = None  # type: ignore[assignment]

    for candidate_image in _qr_decode_image_variants(rgb):
        array = np.asarray(candidate_image.convert("RGB"))
        if wechat_detector is not None:
            try:
                decoded, _points = wechat_detector.detectAndDecode(array)
                candidates.extend(_decoded_qr_texts(decoded))
            except Exception:
                pass
        if cv2 is not None:
            try:
                detector = cv2.QRCodeDetector()
                bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
                decoded, _points, _straight = detector.detectAndDecode(bgr)
                candidates.extend(_decoded_qr_texts(decoded))
            except Exception:
                pass
            try:
                decoded, _points, _straight = detector.detectAndDecodeCurved(bgr)
                candidates.extend(_decoded_qr_texts(decoded))
            except Exception:
                pass
    for text in candidates:
        if not text:
            continue
        payload = json.loads(str(text))
        if isinstance(payload, dict):
            return _minimal_qr_payload(payload)
    raise ValueError("qr decode failed")


def _decoded_qr_texts(decoded: Any) -> list[str]:
    if isinstance(decoded, str):
        return [decoded] if decoded else []
    if isinstance(decoded, (list, tuple)):
        return [str(item) for item in decoded if item]
    return []


def _qr_decode_image_variants(image: Image.Image) -> list[Image.Image]:
    variants: list[Image.Image] = [image]
    min_side = max(1, min(image.size))
    if min_side < 400:
        scale = min(8, max(2, int(640 / min_side)))
        target = (image.width * scale, image.height * scale)
        variants.append(image.resize(target, Image.Resampling.LANCZOS))
        variants.append(image.resize(target, Image.Resampling.NEAREST))
    return variants


def create_wechat_qr_detector(model_dir: str | Path | None = None) -> Any:
    try:
        import cv2  # type: ignore
    except Exception as exc:
        raise RuntimeError("OpenCV contrib is required for WeChat QR decoding") from exc
    ctor = getattr(cv2, "wechat_qrcode_WeChatQRCode", None)
    if ctor is None:
        module = getattr(cv2, "wechat_qrcode", None)
        ctor = getattr(module, "WeChatQRCode", None) if module is not None else None
    if ctor is None:
        raise RuntimeError("OpenCV WeChatQRCode API was not found. Install opencv-contrib-python-headless.")
    return ctor(*resolve_wechat_model_paths(model_dir))


def _wechat_detector_or_none() -> Any | None:
    global _WECHAT_DETECTOR, _WECHAT_DETECTOR_ATTEMPTED
    if _WECHAT_DETECTOR is not None:
        return _WECHAT_DETECTOR
    if _WECHAT_DETECTOR_ATTEMPTED:
        return None
    _WECHAT_DETECTOR_ATTEMPTED = True
    try:
        _WECHAT_DETECTOR = create_wechat_qr_detector()
    except Exception:
        _WECHAT_DETECTOR = None
    return _WECHAT_DETECTOR


def resolve_wechat_model_paths(model_dir: str | Path | None = None) -> tuple[str, str, str, str]:
    root = Path(model_dir or DEFAULT_WECHAT_QR_MODEL_DIR)
    files = ("detect.prototxt", "detect.caffemodel", "sr.prototxt", "sr.caffemodel")
    paths = tuple(root / name for name in files)
    if all(path.exists() for path in paths):
        return tuple(str(path) for path in paths)  # type: ignore[return-value]
    return ("", "", "", "")


def _intake_single_scan(raw_path: Path, manifests: list[Path], *, dirs: dict[str, Path]) -> dict[str, Any]:
    image = Image.open(raw_path).convert("RGB")
    failures: list[str] = []
    for manifest_path in reversed(manifests):
        manifest = _read_json(manifest_path)
        for sample in manifest.get("samples", []) if isinstance(manifest.get("samples"), list) else []:
            if not isinstance(sample, dict):
                continue
            try:
                payload: dict[str, Any] | None = None
                bbox: list[int] | None = None
                last_error: Exception | None = None
                for pad_ratio in (0.0, 0.1, 0.2):
                    candidate_bbox = _scaled_bbox(sample.get("qr_bbox"), sample.get("template_size"), [image.width, image.height], pad_ratio=pad_ratio)
                    crop = image.crop((candidate_bbox[0], candidate_bbox[1], candidate_bbox[0] + candidate_bbox[2], candidate_bbox[1] + candidate_bbox[3]))
                    try:
                        payload = decode_marker_image(crop, wechat_detector=_wechat_detector_or_none())
                        bbox = candidate_bbox
                        break
                    except Exception as exc:
                        last_error = exc
                if payload is None:
                    exact_bbox = _scaled_bbox(sample.get("qr_bbox"), sample.get("template_size"), [image.width, image.height], pad_ratio=0.0)
                    exact_crop = image.crop((exact_bbox[0], exact_bbox[1], exact_bbox[0] + exact_bbox[2], exact_bbox[1] + exact_bbox[3]))
                    if _matches_generated_qr(exact_crop, sample):
                        payload = _minimal_qr_payload(sample.get("qr_payload") if isinstance(sample.get("qr_payload"), dict) else sample)
                        bbox = exact_bbox
                    else:
                        raise last_error or ValueError("qr decode failed")
                if payload.get("sample_id") != sample.get("sample_id") or payload.get("doc_id") != sample.get("doc_id") or payload.get("run_id") != sample.get("run_id"):
                    raise ValueError("decoded payload does not match candidate sample")
                return _accept_scan(raw_path, image, bbox or [0, 0, 1, 1], payload, sample, dirs=dirs)
            except Exception as exc:
                failures.append(f"{manifest_path.name}/{sample.get('sample_id')}: {exc}")
    review_path = dirs["review"] / f"{raw_path.stem}.json"
    record = {
        "raw_scan": _display_path(raw_path),
        "status": REVIEW_REQUIRED_STATUS,
        "reason": "qr_decode_failed",
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
    removed, qr_remove_method = _remove_qr_marker(image, bbox)
    removed.save(qr_removed_path, "JPEG", quality=95)
    gt_source = _resolve_path(sample.get("gt") or sample.get("public_gt") or payload.get("gt_path"))
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
        "qr_remove_method": qr_remove_method,
    }


def _remove_qr_marker(image: Image.Image, bbox: list[int]) -> tuple[Image.Image, str]:
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    pad = 3
    draw.rectangle([bbox[0] - pad, bbox[1] - pad, bbox[0] + bbox[2] + pad, bbox[1] + bbox[3] + pad], fill=255)
    try:
        return lama_inpaint(image.convert("RGB"), mask, max_side=1800), "lama"
    except Exception:
        removed = image.copy()
        fallback_draw = ImageDraw.Draw(removed)
        fallback_draw.rectangle([bbox[0] - pad, bbox[1] - pad, bbox[0] + bbox[2] + pad, bbox[1] + bbox[3] + pad], fill="white")
        return removed, "white_fill_fallback"


def _render_answer_sheet(template_path: Path, *, schema: dict[str, Any], fields: list[dict[str, Any]], values: dict[str, str]) -> Image.Image:
    image = Image.open(template_path).convert("RGB")
    labels = _review_labels_by_id(schema)
    draw = ImageDraw.Draw(image)
    for field in fields:
        field_id = str(field.get("field_id") or "")
        value = str(values.get(field_id) or "").strip()
        label = labels.get(str(field.get("bbox_label_id") or field.get("source_detection_id") or ""))
        if not value or label is None:
            continue
        x, y, w, h = [int(round(item)) for item in label.bbox.to_list()]
        if w <= 0 or h <= 0:
            continue
        font_size = max(8, int(h * 0.72))
        font = load_font(font_size)
        while font_size > 8:
            bbox = draw.textbbox((0, 0), value, font=font)
            if bbox[2] - bbox[0] <= max(1, w - 4) and bbox[3] - bbox[1] <= max(1, h - 2):
                break
            font_size -= 1
            font = load_font(font_size)
        text_bbox = draw.textbbox((0, 0), value, font=font)
        text_h = text_bbox[3] - text_bbox[1]
        draw.text((x + 2, y + max(0, (h - text_h) // 2) - text_bbox[1]), value, font=font, fill=tuple(HANDWRITING_PREVIEW_FILL))
    return image


def _save_two_page_pdf(path: Path, images: list[Image.Image]) -> None:
    if not images:
        raise ValueError("at least one image is required")
    path.parent.mkdir(parents=True, exist_ok=True)
    pages = [image.convert("RGB") for image in images]
    pages[0].save(path, "PDF", resolution=200.0, save_all=True, append_images=pages[1:])


def _minimal_qr_payload(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("qr payload must be an object")
    result = {
        "doc_id": str(payload.get("doc_id") or "").strip(),
        "sample_id": str(payload.get("sample_id") or "").strip(),
        "run_id": str(payload.get("run_id") or "").strip(),
    }
    if not all(result.values()):
        raise ValueError("qr payload requires doc_id, sample_id, and run_id")
    return result


def _matches_generated_qr(crop: Image.Image, sample: dict[str, Any]) -> bool:
    qr_path_value = sample.get("qr_image")
    if not qr_path_value:
        return False
    qr_path = _resolve_path(qr_path_value)
    if not qr_path.exists():
        return False
    with Image.open(qr_path).convert("L") as expected:
        observed = crop.convert("L").resize(expected.size, Image.Resampling.BOX)
        diff_sum = 0
        for left, right in zip(observed.getdata(), expected.getdata()):
            diff_sum += abs(int(left) - int(right))
        mean_diff = diff_sum / max(1, expected.width * expected.height)
    return mean_diff <= 8.0


def _handwriting_public_doc_dir(doc: Any, *, root: Path) -> Path:
    base = _workbench_root_from_documents_root(root).parent / "handwriting"
    domain = (doc.po_domains[0] if getattr(doc, "po_domains", ()) else "") or (doc.domains[0] if getattr(doc, "domains", ()) else "") or "기타"
    return base / slugify_title(domain) / f"{slugify_title(doc.title)}_{slugify_title(doc.doc_id)}"


def _workbench_root_from_documents_root(root: Path) -> Path:
    if root.name == "documents" and root.parent.name == "workbench":
        return root.parent
    return ROOT / "workbench"


def _semantic_schema(schema: dict[str, Any]) -> dict[str, Any]:
    payload = schema.get("semantic_schema") if isinstance(schema.get("semantic_schema"), dict) else {}
    return _schema_value_template(payload)


def _field_semantic_paths(fields: list[dict[str, Any]]) -> dict[str, str]:
    paths: dict[str, str] = {}
    for field in fields:
        if not _field_export_enabled(field):
            continue
        field_id = str(field.get("field_id") or "")
        semantic_path = field.get("semantic_path")
        if isinstance(semantic_path, list) and semantic_path:
            paths[field_id] = ".".join(str(part) for part in semantic_path if str(part))
            continue
        export = field.get("export") if isinstance(field.get("export"), dict) else {}
        paths[field_id] = str(export.get("json_path") or field.get("label") or field_id)
    return paths


def _field_export_enabled(field: dict[str, Any]) -> bool:
    export = field.get("export") if isinstance(field.get("export"), dict) else {}
    include = export.get("include") if "include" in export else True
    return str(include).strip().lower() not in {"false", "0", "no", "off", "skip", "hidden"}


def _review_labels_by_id(schema: dict[str, Any]) -> dict[str, Any]:
    review_path = _resolve_path(schema.get("source_review") or "")
    if not review_path.exists():
        return {}
    policy = load_review_policy(review_path)
    return {label.id: label for label in policy.labels}


def _field_render_mode(field: dict[str, Any]) -> str:
    explicit = str(field.get("render_mode") or "").strip()
    if explicit in {"handwriting", "printed"}:
        return explicit
    return "printed"


def _fields_for_render_mode(fields: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    return [field for field in fields if _field_render_mode(field) == mode]


def _visible_fields_for_render_mode(fields: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    """Return fields that should be visibly painted for a handwriting sheet.

    Some schemas keep atomic primary leaves and an ``export:false`` composite
    field bound to the same bbox.  The atomic leaves belong in GT/schema, while
    the composite field is the only text that should be painted in that bbox.
    Rendering both causes overprinted answer sheets such as
    ``계좌종류`` + ``통화`` + ``계좌종류/통화`` on the same line.
    """

    candidates = _fields_for_render_mode(fields, mode)
    by_bbox: dict[str, list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for field in candidates:
        key = _field_visual_bbox_key(field)
        if key:
            by_bbox.setdefault(key, []).append(field)
        else:
            passthrough.append(field)
    visible: list[dict[str, Any]] = []
    for group in by_bbox.values():
        render_only = [field for field in group if not _field_export_enabled(field)]
        if render_only:
            visible.extend(render_only[:1])
        else:
            visible.extend(group)
    visible.extend(passthrough)
    return visible


def _field_visual_bbox_key(field: dict[str, Any]) -> str:
    label_id = str(field.get("bbox_label_id") or field.get("source_detection_id") or "").strip()
    if label_id:
        return f"label:{label_id}"
    bbox = field.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        return "bbox:" + ",".join(str(round(float(item), 3)) for item in bbox[:4])
    return ""


def _render_handwriting_preview_fields(
    template_path: Path,
    *,
    schema: dict[str, Any],
    stylesheet: dict[str, Any],
    printed_fields: list[dict[str, Any]],
    handwriting_fields: list[dict[str, Any]],
    values: dict[str, str],
) -> Image.Image:
    fields = [dict(field) for field in printed_fields]
    styles = [dict(style) for style in stylesheet.get("style_classes", []) if isinstance(style, dict)]
    styles_by_id = {str(style.get("style_class") or ""): style for style in styles}
    for field in handwriting_fields:
        preview_field = dict(field)
        original_style_class = str(preview_field.get("style_class") or "body_default")
        base_style = dict(styles_by_id.get(original_style_class) or styles_by_id.get("body_default") or {"style_class": "body_default"})
        preview_style_class = f"__handwriting_preview_{preview_field.get('field_id') or len(fields)}"
        base_style["style_class"] = preview_style_class
        base_style["fill"] = HANDWRITING_PREVIEW_FILL
        styles.append(base_style)
        preview_field["style_class"] = preview_style_class
        fields.append(preview_field)
    if not fields:
        return Image.open(template_path).convert("RGB")
    preview_stylesheet = dict(stylesheet)
    preview_stylesheet["style_classes"] = styles
    return _render_printed_fields(template_path, schema=schema, stylesheet=preview_stylesheet, fields=fields, values=values)


def _render_printed_fields(template_path: Path, *, schema: dict[str, Any], stylesheet: dict[str, Any], fields: list[dict[str, Any]], values: dict[str, str]) -> Image.Image:
    if not fields:
        return Image.open(template_path).convert("RGB")
    filtered_schema = dict(schema)
    filtered_schema["fields"] = fields
    template_spec, _warnings = _template_from_authoring(filtered_schema, stylesheet, template_path)
    image, _annotations = render_template(template_spec, values, render_scale=2)
    return image.convert("RGB")


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


def _schema_qr_bbox(schema: dict[str, Any]) -> Any:
    handwriting = schema.get("handwriting") if isinstance(schema.get("handwriting"), dict) else {}
    value = handwriting.get("qr_bbox") or schema.get("qr_bbox")
    if isinstance(value, dict):
        return [value.get("x"), value.get("y"), value.get("width"), value.get("height")]
    return value


def _resolve_qr_bbox(value: list[int] | tuple[int, int, int, int] | None, *, width: int, height: int) -> list[int]:
    if value and len(value) == 4:
        x, y, w, h = [int(round(float(item))) for item in value]
        if w > 20 and h > 20:
            side = min(max(w, h), max(1, width), max(1, height))
            left = min(max(0, x), max(0, width - side))
            top = min(max(0, y), max(0, height - side))
            return [left, top, side, side]
    size = min(QR_DEFAULT_PIXEL_SIZE, max(96, int(min(width, height) * 0.16)))
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
