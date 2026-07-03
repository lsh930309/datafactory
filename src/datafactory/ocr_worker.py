from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Sequence

from PIL import Image

from .ocr_detectors import PADDLEOCR_PRESETS, get_detector, normalize_paddleocr_preset, paddleocr_preset_params, _parse_paddle_result
from .ocr_export import write_ocr_eval


def run_ocr_eval(image: Path, *, engine: str, preset: str | None, out_dir: Path) -> dict[str, object]:
    normalized_engine = engine.lower().strip()
    normalized_preset = normalize_paddleocr_preset(preset) if normalized_engine == "paddleocr" else ""
    started_at = perf_counter()
    result = get_detector(normalized_engine, preset=normalized_preset).detect(image)
    elapsed_seconds = perf_counter() - started_at
    output_dir = out_dir / normalized_engine / normalized_preset / _safe_template_id(image) if normalized_preset else out_dir / normalized_engine / _safe_template_id(image)
    paths = write_ocr_eval(result, output_dir)
    return {
        "summary": {
            "engine": result.engine,
            "preset": normalized_preset or None,
            "source_image": str(result.source_image),
            "image": {"width": result.image_width, "height": result.image_height},
            "detection_count": len(result.detections),
            "elapsed_seconds": elapsed_seconds,
        },
        "paths": {name: str(path) for name, path in paths.items()},
    }


def run_paddle_crop_recognition(crops_json: Path, *, preset: str | None) -> dict[str, object]:
    normalized_preset = normalize_paddleocr_preset(preset)
    manifest = json.loads(crops_json.read_text(encoding="utf-8"))
    crops = manifest.get("crops", [])
    if not isinstance(crops, list):
        raise ValueError("crops_json must contain a crops list")

    try:
        from paddleocr import PaddleOCR  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PaddleOCR is not installed. Install it in an OCR-compatible venv to use crop recognition.") from exc

    started_at = perf_counter()
    ocr = PaddleOCR(
        lang="korean",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        **paddleocr_preset_params(normalized_preset),
    )
    candidates: list[dict[str, Any]] = []
    for item in crops:
        if not isinstance(item, dict):
            continue
        crop_path = Path(str(item.get("cropPath") or ""))
        raw = ocr.predict(str(crop_path)) if hasattr(ocr, "predict") else ocr.ocr(str(crop_path))
        detections = _parse_paddle_result(raw)
        text, confidence = _aggregate_crop_detections(detections)
        width = height = 0
        try:
            with Image.open(crop_path) as image:
                width, height = image.size
        except Exception:
            pass
        candidates.append(
            {
                "id": str(item.get("id") or ""),
                "oldText": str(item.get("oldText") or ""),
                "text": text,
                "confidence": confidence,
                "cropPath": str(crop_path),
                "bbox": item.get("bbox"),
                "image": {"width": width, "height": height},
                "detections": [detection.to_dict() for detection in detections],
            }
        )
    elapsed_seconds = perf_counter() - started_at
    return {
        "summary": {
            "engine": "paddleocr",
            "preset": normalized_preset,
            "count": len(candidates),
            "recognized": len([candidate for candidate in candidates if candidate.get("text")]),
            "elapsed_seconds": elapsed_seconds,
        },
        "candidates": candidates,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one isolated OCR detection job and write JSON result metadata.")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--engine", default="paddleocr", choices=["projection", "paddleocr", "doctr"])
    parser.add_argument("--preset", default="precise", choices=list(PADDLEOCR_PRESETS))
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--result-json", type=Path, required=True)
    parser.add_argument("--crops-json", type=Path)
    args = parser.parse_args(argv)

    if args.crops_json:
        payload = run_paddle_crop_recognition(args.crops_json, preset=args.preset)
    else:
        if args.image is None:
            raise ValueError("--image is required unless --crops-json is provided")
        payload = run_ocr_eval(args.image, engine=args.engine, preset=args.preset, out_dir=args.out_dir)
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    with args.result_json.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    # Paddle's native worker threads can crash during interpreter teardown on
    # macOS. This worker has already written its only output, so skip Python
    # cleanup in the isolated child process.
    if args.engine == "paddleocr":
        os._exit(0)
    return 0


def _aggregate_crop_detections(detections) -> tuple[str, float | None]:  # noqa: ANN001
    ordered = sorted(detections, key=lambda detection: (detection.bbox.y, detection.bbox.x))
    texts = [detection.text.strip() for detection in ordered if detection.text and detection.text.strip()]
    scores = [float(detection.confidence) for detection in ordered if detection.confidence is not None]
    text = " ".join(texts).strip()
    confidence = (sum(scores) / len(scores)) if scores else None
    return text, confidence


def _safe_template_id(path: Path) -> str:
    parent = path.parent.name
    if parent:
        return f"{parent}_{path.stem}"
    return path.stem


if __name__ == "__main__":
    raise SystemExit(main())
