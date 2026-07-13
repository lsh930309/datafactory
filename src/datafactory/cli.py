from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Sequence

from PIL import Image

from .authoring import draft_authoring_bundle, render_authoring_batch, render_authoring_preview
from .fonts import default_font_path
from .inpaint import InpaintConfig, inpaint_from_detections, inpaint_from_review_policy
from .inpaint_export import write_inpaint_result
from .models import RenderJob
from .ocr_detectors import PADDLEOCR_PRESETS
from .ocr_worker import run_ocr_eval
from .pipeline import render_job
from .policy import draft_review_policy, write_review_policy
from .templates import load_template


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="datafactory", description="Synthetic document image generation toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect an image seed file")
    inspect_parser.add_argument("image", type=Path)

    draft_parser = subparsers.add_parser("draft-template", help="Create a starter manual template JSON for an image")
    draft_parser.add_argument("image", type=Path)
    draft_parser.add_argument("--out", type=Path, required=True)
    draft_parser.add_argument("--template-id", default=None)
    draft_parser.add_argument("--field", action="append", default=[], help="Field spec as name:type:x:y:w:h, can repeat")

    render_parser = subparsers.add_parser("render", help="Render synthetic samples from a template JSON")
    render_parser.add_argument("--template", type=Path, required=True)
    render_parser.add_argument("--count", type=int, default=1)
    render_parser.add_argument("--out", type=Path, required=True)
    render_parser.add_argument("--seed", type=int, default=1234)
    render_parser.add_argument("--image-ext", default="png", choices=["png", "jpg", "jpeg"])

    ocr_parser = subparsers.add_parser("ocr-eval", help="Run an OCR/text detector and write common JSON plus bbox overlay")
    ocr_parser.add_argument("image", type=Path)
    ocr_parser.add_argument("--engine", default="paddleocr", choices=["projection", "paddleocr", "doctr"], help="Detector engine. Default is paddleocr for real evaluation; projection is harness-only.")
    ocr_parser.add_argument("--preset", default="precise", choices=list(PADDLEOCR_PRESETS), help="PaddleOCR quality preset. Ignored by non-Paddle engines.")
    ocr_parser.add_argument("--out", type=Path, required=True)

    inpaint_parser = subparsers.add_parser("inpaint-detections", help="Inpaint all OCR detection bboxes without LaMa")
    inpaint_parser.add_argument("detections", type=Path, help="Path to an OCR detections.json file")
    inpaint_parser.add_argument("--out", type=Path, required=True)
    inpaint_parser.add_argument("--method", default="lama", choices=["telea", "ns", "fill", "lama"], help="Inpainting method. telea/ns require OpenCV; fill is a simple local background fallback.")
    inpaint_parser.add_argument("--mask-shape", default="bbox", choices=["bbox", "polygon"], help="Mask geometry. bbox is the current all-bbox experiment default.")
    inpaint_parser.add_argument("--padding", type=int, default=2, help="Pixels to expand each detection bbox before masking")
    inpaint_parser.add_argument("--dilation", type=int, default=1, help="Additional mask dilation radius in pixels")
    inpaint_parser.add_argument("--radius", type=float, default=3.0, help="OpenCV inpaint radius for telea/ns")
    inpaint_parser.add_argument("--lama-max-side", type=int, default=2400, help="Maximum LaMa inference canvas side. Use 0 for full-resolution inference.")

    review_parser = subparsers.add_parser("draft-review", help="Create an editable bbox review policy from OCR detections")
    review_parser.add_argument("detections", type=Path, help="Path to an OCR detections.json file")
    review_parser.add_argument("--out", type=Path, required=True)

    inpaint_review_parser = subparsers.add_parser("inpaint-review", help="Inpaint only bbox labels marked status=use in a review.json")
    inpaint_review_parser.add_argument("review", type=Path, help="Path to a review.json file")
    inpaint_review_parser.add_argument("--out", type=Path, required=True)
    inpaint_review_parser.add_argument("--method", default="lama", choices=["telea", "ns", "fill", "lama"])
    inpaint_review_parser.add_argument("--mask-shape", default="bbox", choices=["bbox", "polygon"])
    inpaint_review_parser.add_argument("--padding", type=int, default=2)
    inpaint_review_parser.add_argument("--dilation", type=int, default=1)
    inpaint_review_parser.add_argument("--radius", type=float, default=3.0)
    inpaint_review_parser.add_argument("--lama-max-side", type=int, default=2400)

    authoring_parser = subparsers.add_parser("draft-authoring", help="Create schema/stylesheet/faker authoring drafts from a reviewed bbox policy")
    authoring_parser.add_argument("--review", type=Path, required=True, help="Path to review.json")
    authoring_parser.add_argument("--base-image", type=Path, required=True, help="Inpainted template image to render onto")
    authoring_parser.add_argument("--out", type=Path, required=True, help="Authoring output directory")
    authoring_parser.add_argument("--doc-id", default=None)
    authoring_parser.add_argument("--title", default=None)

    render_authoring_parser = subparsers.add_parser("render-authoring", help="Render one preview from schema/stylesheet/faker authoring files")
    render_authoring_parser.add_argument("--schema", type=Path, required=True)
    render_authoring_parser.add_argument("--stylesheet", type=Path, required=True)
    render_authoring_parser.add_argument("--faker-profile", type=Path, required=True)
    render_authoring_parser.add_argument("--out", type=Path, required=True)
    render_authoring_parser.add_argument("--seed", type=int, default=1234)
    render_authoring_parser.add_argument("--sample-id", default="preview_000001")
    render_authoring_parser.add_argument("--as-of-date", type=date.fromisoformat, default=None, metavar="YYYY-MM-DD")

    render_authoring_batch_parser = subparsers.add_parser("render-authoring-batch", help="Render multiple synthetic samples from schema/stylesheet/faker authoring files")
    render_authoring_batch_parser.add_argument("--schema", type=Path, required=True)
    render_authoring_batch_parser.add_argument("--stylesheet", type=Path, required=True)
    render_authoring_batch_parser.add_argument("--faker-profile", type=Path, required=True)
    render_authoring_batch_parser.add_argument("--out", type=Path, required=True)
    render_authoring_batch_parser.add_argument("--count", type=int, default=5)
    render_authoring_batch_parser.add_argument("--seed", type=int, default=20260702)
    render_authoring_batch_parser.add_argument("--as-of-date", type=date.fromisoformat, default=None, metavar="YYYY-MM-DD")

    args = parser.parse_args(argv)
    if args.command == "inspect":
        return _inspect(args.image)
    if args.command == "draft-template":
        return _draft_template(args.image, args.out, args.template_id, args.field)
    if args.command == "render":
        template = load_template(args.template)
        samples = render_job(RenderJob(template=template, output_dir=args.out, count=args.count, seed=args.seed, image_ext=args.image_ext))
        print(f"Rendered {len(samples)} samples to {args.out}")
        return 0
    if args.command == "ocr-eval":
        payload = run_ocr_eval(args.image, engine=args.engine, preset=args.preset, out_dir=args.out)
        summary = payload["summary"]
        paths = {name: Path(path) for name, path in dict(payload["paths"]).items()}
        preset_text = f" preset={args.preset}" if args.engine == "paddleocr" else ""
        print(f"Detected {summary['detection_count']} region(s) with {args.engine}{preset_text}")
        for name, path in paths.items():
            print(f"{name}: {path}")
        return 0
    if args.command == "inpaint-detections":
        config = InpaintConfig(method=args.method, mask_shape=args.mask_shape, padding=args.padding, dilation=args.dilation, radius=args.radius, lama_max_side=args.lama_max_side)
        result = inpaint_from_detections(args.detections, config)
        paths = write_inpaint_result(result, args.out / _safe_template_id(result.source_image) / args.method)
        print(f"Inpainted {result.detection_count} region(s) from {args.detections}")
        print(f"mask_ratio: {result.mask_ratio:.4f}")
        for name, path in paths.items():
            print(f"{name}: {path}")
        return 0
    if args.command == "draft-review":
        policy = draft_review_policy(args.detections)
        paths = write_review_policy(policy, args.out / _safe_template_id(policy.source_image))
        print(f"Drafted review policy for {len(policy.labels)} detection(s)")
        for name, path in paths.items():
            print(f"{name}: {path}")
        return 0
    if args.command == "inpaint-review":
        config = InpaintConfig(method=args.method, mask_shape=args.mask_shape, padding=args.padding, dilation=args.dilation, radius=args.radius, lama_max_side=args.lama_max_side)
        result = inpaint_from_review_policy(args.review, config)
        paths = write_inpaint_result(result, args.out / _safe_template_id(result.source_image) / args.method)
        print(f"Inpainted {result.detection_count} reviewed use-region(s) from {args.review}")
        print(f"mask_ratio: {result.mask_ratio:.4f}")
        for name, path in paths.items():
            print(f"{name}: {path}")
        return 0
    if args.command == "draft-authoring":
        result = draft_authoring_bundle(args.review, base_image_path=args.base_image, out_dir=args.out, doc_id=args.doc_id, title=args.title)
        print(f"Drafted authoring bundle with {result.field_count} field(s)")
        print(f"schema: {result.schema}")
        print(f"stylesheet: {result.stylesheet}")
        print(f"faker_profile: {result.faker_profile}")
        return 0
    if args.command == "render-authoring":
        result = render_authoring_preview(args.schema, args.stylesheet, args.faker_profile, out_dir=args.out, seed=args.seed, sample_id=args.sample_id, as_of_date=args.as_of_date)
        print(f"Rendered authoring preview {result.sample_id} with {result.field_count} field(s), warnings={result.warning_count}")
        print(f"image: {result.image}")
        print(f"kv: {result.kv}")
        print(f"bbox: {result.bbox}")
        print(f"overlay: {result.overlay}")
        print(f"validation_report: {result.validation_report}")
        return 0
    if args.command == "render-authoring-batch":
        result = render_authoring_batch(args.schema, args.stylesheet, args.faker_profile, out_dir=args.out, count=args.count, seed=args.seed, as_of_date=args.as_of_date)
        print(f"Rendered authoring batch {result.sample_count} sample(s) with {result.field_count} field(s), warnings={result.warning_count}")
        print(f"out_dir: {result.out_dir}")
        print(f"summary: {result.summary}")
        print(f"manifest: {result.manifest}")
        return 0
    parser.error("unknown command")
    return 2


def _inspect(image_path: Path) -> int:
    with Image.open(image_path) as image:
        print(json.dumps({"path": str(image_path), "width": image.width, "height": image.height, "mode": image.mode}, ensure_ascii=False, indent=2))
    return 0


def _draft_template(image_path: Path, out: Path, template_id: str | None, field_specs: list[str]) -> int:
    with Image.open(image_path) as image:
        width, height = image.size
    fields = [_parse_field_spec(spec) for spec in field_specs] if field_specs else _default_fields(width, height)
    payload = {
        "template_id": template_id or _safe_template_id(image_path),
        "description": "Starter manual template. Adjust bbox coordinates before production generation.",
        "image_path": str(image_path.resolve()),
        "font_path": default_font_path(),
        "fields": fields,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Wrote starter template to {out}")
    return 0


def _parse_field_spec(spec: str) -> dict[str, object]:
    parts = spec.split(":")
    if len(parts) != 6:
        raise SystemExit(f"Invalid --field {spec!r}; expected name:type:x:y:w:h")
    name, field_type, x, y, w, h = parts
    return {
        "name": name,
        "type": field_type,
        "bbox": [int(x), int(y), int(w), int(h)],
        "font_size": max(12, int(int(h) * 0.7)),
        "color": [30, 30, 30],
        "align": "left",
        "valign": "middle",
        "clear_background": True,
    }


def _default_fields(width: int, height: int) -> list[dict[str, object]]:
    base_x = max(20, int(width * 0.18))
    base_y = max(20, int(height * 0.18))
    box_w = max(160, int(width * 0.22))
    box_h = max(30, int(height * 0.018))
    gap = max(12, int(box_h * 1.8))
    font_size = max(14, int(box_h * 0.7))
    return [
        {
            "name": "person_name",
            "type": "name",
            "bbox": [base_x, base_y, box_w, box_h],
            "font_size": font_size,
            "color": [30, 30, 30],
            "align": "left",
            "valign": "middle",
            "clear_background": True,
        },
        {
            "name": "issue_date",
            "type": "date",
            "bbox": [base_x, base_y + gap, box_w, box_h],
            "font_size": font_size,
            "color": [30, 30, 30],
            "align": "left",
            "valign": "middle",
            "clear_background": True,
        },
        {
            "name": "amount",
            "type": "amount",
            "bbox": [base_x, base_y + gap * 2, box_w, box_h],
            "font_size": font_size,
            "color": [30, 30, 30],
            "align": "right",
            "valign": "middle",
            "clear_background": True,
        },
    ]


def _safe_template_id(path: Path) -> str:
    return path.parent.name or path.stem


if __name__ == "__main__":
    raise SystemExit(main())
