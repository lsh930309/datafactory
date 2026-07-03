from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from PIL import Image, ImageStat

from .models import BBox
from .ocr_models import OcrDetection, OcrResult, bbox_to_polygon, polygon_to_bbox


class OcrDetector(Protocol):
    engine: str

    def detect(self, image_path: Path) -> OcrResult: ...


@dataclass(frozen=True)
class PaddleOcrPreset:
    name: str
    text_det_limit_side_len: int
    text_det_limit_type: str = "max"
    text_det_thresh: float | None = None
    text_det_box_thresh: float | None = None

    def kwargs(self) -> dict[str, Any]:
        values: dict[str, Any] = {
            "text_det_limit_side_len": self.text_det_limit_side_len,
            "text_det_limit_type": self.text_det_limit_type,
        }
        if self.text_det_thresh is not None:
            values["text_det_thresh"] = self.text_det_thresh
        if self.text_det_box_thresh is not None:
            values["text_det_box_thresh"] = self.text_det_box_thresh
        return values


PADDLEOCR_PRESETS: dict[str, PaddleOcrPreset] = {
    "fast": PaddleOcrPreset(name="fast", text_det_limit_side_len=960),
    "balanced": PaddleOcrPreset(name="balanced", text_det_limit_side_len=1280),
    "precise": PaddleOcrPreset(name="precise", text_det_limit_side_len=1920, text_det_thresh=0.25, text_det_box_thresh=0.5),
}


def normalize_paddleocr_preset(value: str | None) -> str:
    normalized = (value or "precise").lower().strip()
    if normalized not in PADDLEOCR_PRESETS:
        raise ValueError(f"unknown PaddleOCR preset: {value}")
    return normalized


def paddleocr_preset_params(value: str | None) -> dict[str, Any]:
    return PADDLEOCR_PRESETS[normalize_paddleocr_preset(value)].kwargs()


def get_detector(engine: str, *, preset: str | None = None) -> OcrDetector:
    normalized = engine.lower().strip()
    if normalized in {"projection", "builtin", "simple"}:
        return ProjectionTextDetector()
    if normalized == "paddleocr":
        return PaddleOcrDetector(preset=preset)
    if normalized == "doctr":
        return DoctrDetector()
    raise ValueError(f"Unknown OCR detector engine: {engine}")


class ProjectionTextDetector:
    """Lightweight dependency-free text-like region detector for harness testing.

    This is not production OCR. It exists so the detector evaluation/export/overlay
    pipeline can be exercised without installing heavyweight OCR packages.
    """

    engine = "projection"

    def __init__(self, *, threshold: int = 210, min_width: int = 8, min_height: int = 8) -> None:
        self.threshold = threshold
        self.min_width = min_width
        self.min_height = min_height

    def detect(self, image_path: Path) -> OcrResult:
        image = Image.open(image_path).convert("L")
        width, height = image.size
        # Downscale very large documents for fast connected component scan.
        max_side = 1800
        scale = min(1.0, max_side / max(width, height))
        work = image.resize((int(width * scale), int(height * scale))) if scale < 1.0 else image
        pixels = work.load()
        visited: set[tuple[int, int]] = set()
        components: list[BBox] = []
        w, h = work.size
        for y in range(0, h, 2):
            for x in range(0, w, 2):
                if (x, y) in visited or pixels[x, y] > self.threshold:
                    continue
                box = self._flood(work, x, y, visited)
                if box.width >= self.min_width and box.height >= self.min_height:
                    components.append(_scale_bbox(box, 1 / scale))
        detections = [
            OcrDetection(
                id=f"det_{idx:06d}",
                text="",
                confidence=None,
                bbox=box,
                polygon=bbox_to_polygon(box),
                level="unknown",
            )
            for idx, box in enumerate(_merge_nearby(components), start=1)
        ]
        return OcrResult(self.engine, image_path, width, height, detections, raw={"threshold": self.threshold, "scale": scale})

    def _flood(self, image: Image.Image, start_x: int, start_y: int, visited: set[tuple[int, int]]) -> BBox:
        pixels = image.load()
        w, h = image.size
        stack = [(start_x, start_y)]
        min_x = max_x = start_x
        min_y = max_y = start_y
        while stack:
            x, y = stack.pop()
            if (x, y) in visited or x < 0 or y < 0 or x >= w or y >= h:
                continue
            visited.add((x, y))
            if pixels[x, y] > self.threshold:
                continue
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
            for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                stack.append((x + dx, y + dy))
        return BBox(min_x, min_y, max(1, max_x - min_x + 1), max(1, max_y - min_y + 1))


class PaddleOcrDetector:
    engine = "paddleocr"

    def __init__(self, *, preset: str | None = None) -> None:
        self.preset = normalize_paddleocr_preset(preset)
        self.params = paddleocr_preset_params(self.preset)

    def detect(self, image_path: Path) -> OcrResult:
        try:
            from paddleocr import PaddleOCR  # type: ignore
        except ImportError as exc:
            raise RuntimeError("PaddleOCR is not installed. Install it in an OCR-compatible venv to use --engine paddleocr.") from exc

        image = Image.open(image_path)
        width, height = image.size
        ocr = PaddleOCR(
            lang="korean",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            **self.params,
        )
        raw = ocr.predict(str(image_path)) if hasattr(ocr, "predict") else ocr.ocr(str(image_path))
        detections = _parse_paddle_result(raw)
        raw_payload = {"preset": self.preset, "params": self.params, "raw": _compact_paddle_raw(raw)}
        return OcrResult(self.engine, image_path, width, height, detections, raw=raw_payload)


class DoctrDetector:
    engine = "doctr"

    def detect(self, image_path: Path) -> OcrResult:
        try:
            from doctr.io import DocumentFile  # type: ignore
            from doctr.models import ocr_predictor  # type: ignore
        except ImportError as exc:
            raise RuntimeError("docTR is not installed. Install python-doctr to use --engine doctr.") from exc

        image = Image.open(image_path)
        width, height = image.size
        doc = DocumentFile.from_images(str(image_path))
        model = ocr_predictor(pretrained=True, assume_straight_pages=True, export_as_straight_boxes=True)
        raw = model(doc).export()
        detections = _parse_doctr_export(raw, width, height)
        return OcrResult(self.engine, image_path, width, height, detections, raw=raw)


def _parse_paddle_result(raw: Any) -> list[OcrDetection]:
    pages = raw if isinstance(raw, list) else [raw]
    detections: list[OcrDetection] = []
    for page in pages:
        res = page.get("res", page) if isinstance(page, dict) else page
        if isinstance(res, dict) and ("rec_texts" in res or "dt_polys" in res or "rec_polys" in res):
            texts = res.get("rec_texts") or []
            scores = _as_list(res.get("rec_scores"))
            polys = _as_list(res.get("rec_polys") or res.get("dt_polys") or [])
            for text, poly, score in zip(texts, polys, scores or [None] * len(texts)):
                polygon = _clean_polygon(poly)
                detections.append(_ocr_det(len(detections) + 1, str(text), score, polygon, "word"))
        elif isinstance(res, list):
            for item in res:
                if isinstance(item, dict) and "text_region" in item:
                    detections.append(_ocr_det(len(detections) + 1, str(item.get("text", "")), item.get("confidence"), _clean_polygon(item["text_region"]), "word"))
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    polygon = _clean_polygon(item[0])
                    text, score = _parse_text_score(item[1])
                    detections.append(_ocr_det(len(detections) + 1, text, score, polygon, "word"))
    return detections


def _parse_doctr_export(raw: dict[str, Any], width: int, height: int) -> list[OcrDetection]:
    detections: list[OcrDetection] = []
    pages = raw.get("pages", []) if isinstance(raw, dict) else []
    for page in pages:
        for block in page.get("blocks", []):
            for line in block.get("lines", []):
                for word in line.get("words", []):
                    geometry = word.get("geometry")
                    if not geometry:
                        continue
                    # docTR export geometry is usually normalized [[x1,y1],[x2,y2]].
                    (x1, y1), (x2, y2) = geometry
                    polygon = [[int(x1 * width), int(y1 * height)], [int(x2 * width), int(y1 * height)], [int(x2 * width), int(y2 * height)], [int(x1 * width), int(y2 * height)]]
                    detections.append(_ocr_det(len(detections) + 1, str(word.get("value", "")), word.get("confidence"), polygon, "word"))
    return detections


def _ocr_det(index: int, text: str, score: Any, polygon: list[list[int]], level: str) -> OcrDetection:
    return OcrDetection(f"det_{index:06d}", text, float(score) if score is not None else None, polygon_to_bbox(polygon), polygon, level)  # type: ignore[arg-type]


def _parse_text_score(value: Any) -> tuple[str, float | None]:
    if isinstance(value, (list, tuple)) and value:
        text = str(value[0])
        score = float(value[1]) if len(value) > 1 and value[1] is not None else None
        return text, score
    return str(value), None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _clean_polygon(poly: Any) -> list[list[int]]:
    if hasattr(poly, "tolist"):
        poly = poly.tolist()
    return [[int(round(point[0])), int(round(point[1]))] for point in poly]


def _scale_bbox(bbox: BBox, factor: float) -> BBox:
    return BBox(int(bbox.x * factor), int(bbox.y * factor), max(1, int(bbox.width * factor)), max(1, int(bbox.height * factor)))


def _merge_nearby(boxes: list[BBox]) -> list[BBox]:
    # Keep the built-in detector conservative: merge tiny connected components into rough line-ish boxes.
    boxes = sorted(boxes, key=lambda b: (b.y, b.x))[:1000]
    merged: list[BBox] = []
    for box in boxes:
        if not merged:
            merged.append(box)
            continue
        prev = merged[-1]
        same_line = abs((prev.y + prev.height / 2) - (box.y + box.height / 2)) < max(prev.height, box.height) * 0.8
        close = box.x - prev.right < max(12, max(prev.height, box.height) * 1.5)
        if same_line and close:
            x1, y1 = min(prev.x, box.x), min(prev.y, box.y)
            x2, y2 = max(prev.right, box.right), max(prev.bottom, box.bottom)
            merged[-1] = BBox(x1, y1, x2 - x1, y2 - y1)
        else:
            merged.append(box)
    return [b for b in merged if b.width * b.height > 80]


def _compact_paddle_raw(raw: Any) -> Any:
    pages = raw if isinstance(raw, list) else [raw]
    compact: list[dict[str, Any]] = []
    for page in pages:
        res = page.get("res", page) if isinstance(page, dict) else page
        if isinstance(res, dict):
            compact.append({
                "input_path": res.get("input_path"),
                "page_index": res.get("page_index"),
                "text_det_params": _jsonish(res.get("text_det_params")),
                "rec_texts": _jsonish(_value_or_empty(res.get("rec_texts"))),
                "rec_scores": _jsonish(_value_or_empty(res.get("rec_scores"))),
                "rec_polys": _jsonish(_value_or_empty(_first_present(res, "rec_polys", "dt_polys"))),
                "rec_boxes": _jsonish(_value_or_empty(res.get("rec_boxes"))),
            })
        else:
            compact.append({"result": _jsonish(res)})
    return compact

def _value_or_empty(value: Any) -> Any:
    return [] if value is None else value


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _jsonish(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "tolist"):
        return _jsonish(value.tolist())
    if isinstance(value, dict):
        return {str(k): _jsonish(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonish(v) for v in value]
    return repr(value)
