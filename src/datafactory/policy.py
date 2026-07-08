from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image

from .models import BBox

ReviewStatus = Literal["use", "keep", "ignore"]
AutoType = Literal[
    "field_value",
    "static_label",
    "table_cell",
    "long_paragraph",
    "header_footer",
    "stamp_or_seal",
    "watermark",
    "unknown",
]

REVIEW_STATUSES: tuple[ReviewStatus, ...] = ("use", "keep", "ignore")
AUTO_TYPES: tuple[AutoType, ...] = (
    "field_value",
    "static_label",
    "table_cell",
    "long_paragraph",
    "header_footer",
    "stamp_or_seal",
    "watermark",
    "unknown",
)

STATIC_LABEL_KEYWORDS = {
    "성명",
    "성 명",
    "생년월일",
    "주민등록번호",
    "주소",
    "발급일",
    "발급번호",
    "구분",
    "성별",
    "본",
    "등록기준지",
    "가족사항",
    "관계",
    "사업장명칭",
    "자격취득일",
    "자격상실일",
    "가입자성명",
    "납부자번호",
    "확인청구자",
    "세대주",
    "임대인",
    "임차인",
    "전화번호",
    "소재지",
    "계약",
    "보증금",
    "차임",
}

DATE_RE = re.compile(r"(?:19|20)\d{2}[.\-/년 ]+\d{1,2}[.\-/월 ]+\d{1,2}|\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}")
PHONE_RE = re.compile(r"0\d{1,2}[- )]?\d{3,4}[- ]?\d{4}")
ID_RE = re.compile(r"\d{6}[-*]\d{7}|\d{3,}[-*]\d{2,}")
AMOUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:원)?|\d+\s*원")
MOSTLY_NUMERIC_RE = re.compile(r"^[\d\s,.*\-/:~()]+$")


@dataclass(frozen=True)
class ReviewLabel:
    id: str
    text: str
    confidence: float | None
    bbox: BBox
    polygon: list[list[int]]
    status: ReviewStatus
    auto_type: AutoType
    reason: str
    locked: bool = False
    notes: str = ""
    original_text: str = ""
    original_confidence: float | None = None
    text_source: str = "paddle_initial"
    ocr_text_stale: bool = False
    rec_text: str = ""
    rec_confidence: float | None = None
    rec_engine: str = ""
    rec_updated_at: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ReviewLabel":
        return cls(
            id=str(raw["id"]),
            text=str(raw.get("text", "")),
            confidence=float(raw["confidence"]) if raw.get("confidence") is not None else None,
            bbox=BBox.from_list(raw["bbox"]),
            polygon=[[int(round(p[0])), int(round(p[1]))] for p in raw.get("polygon", [])],
            status=_review_status(raw.get("status", "keep")),
            auto_type=_auto_type(raw.get("auto_type", "unknown")),
            reason=str(raw.get("reason", "")),
            locked=bool(raw.get("locked", False)),
            notes=str(raw.get("notes", "")),
            original_text=str(raw.get("original_text", raw.get("text", ""))),
            original_confidence=(
                float(raw["original_confidence"] if raw.get("original_confidence") is not None else raw["confidence"])
                if raw.get("original_confidence") is not None or raw.get("confidence") is not None
                else None
            ),
            text_source=str(raw.get("text_source", "paddle_initial")),
            ocr_text_stale=bool(raw.get("ocr_text_stale", False)),
            rec_text=str(raw.get("rec_text", "")),
            rec_confidence=float(raw["rec_confidence"]) if raw.get("rec_confidence") is not None else None,
            rec_engine=str(raw.get("rec_engine", "")),
            rec_updated_at=str(raw.get("rec_updated_at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "confidence": self.confidence,
            "bbox": self.bbox.to_list(),
            "bbox_format": "xywh",
            "polygon": self.polygon,
            "status": self.status,
            "auto_type": self.auto_type,
            "reason": self.reason,
            "locked": self.locked,
            "notes": self.notes,
            "original_text": self.original_text,
            "original_confidence": self.original_confidence,
            "text_source": self.text_source,
            "ocr_text_stale": self.ocr_text_stale,
            "rec_text": self.rec_text,
            "rec_confidence": self.rec_confidence,
            "rec_engine": self.rec_engine,
            "rec_updated_at": self.rec_updated_at,
        }


@dataclass(frozen=True)
class ReviewPolicy:
    source_detections: Path
    source_image: Path
    image_width: int
    image_height: int
    labels: list[ReviewLabel]
    source_engine: str = "unknown"
    schema_version: int = 1
    created_at: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, base_dir: Path | None = None) -> "ReviewPolicy":
        base = base_dir or Path.cwd()
        source_detections = Path(raw["source_detections"])
        source_image = Path(raw["source_image"])
        if not source_detections.is_absolute():
            source_detections = _resolve_review_path(source_detections, base)
        if not source_image.is_absolute():
            source_image = _resolve_review_path(source_image, base)
        image = raw.get("image", {})
        return cls(
            schema_version=int(raw.get("schema_version", 1)),
            source_detections=source_detections,
            source_image=source_image,
            image_width=int(image.get("width", raw.get("image_width", 0))),
            image_height=int(image.get("height", raw.get("image_height", 0))),
            labels=[ReviewLabel.from_dict(item) for item in raw.get("labels", [])],
            source_engine=str(raw.get("source_engine") or _infer_engine(source_detections)),
            created_at=str(raw.get("created_at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "source_engine": self.source_engine,
            "source_detections": str(self.source_detections),
            "source_image": str(self.source_image),
            "image": {"width": self.image_width, "height": self.image_height},
            "summary": review_summary(self.labels),
            "labels": [label.to_dict() for label in self.labels],
        }


def draft_review_policy(detections_path: Path) -> ReviewPolicy:
    payload = json.loads(detections_path.read_text(encoding="utf-8"))
    source_image = Path(payload["source_image"])
    image = Image.open(source_image).convert("RGB")
    width, height = image.size
    labels = []
    for raw in payload.get("detections", []):
        label = _label_detection(raw, image, width, height)
        labels.append(label)
    return ReviewPolicy(
        source_detections=detections_path,
        source_image=source_image,
        image_width=width,
        image_height=height,
        labels=labels,
        source_engine=str(payload.get("engine") or _infer_engine(detections_path)),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def augment_blank_template_policy(policy: ReviewPolicy) -> tuple[ReviewPolicy, dict[str, Any]]:
    """Add machine-generated value-region candidates for blank form templates.

    PaddleOCR usually returns static labels on blank forms. For grid/table forms,
    this pass detects long horizontal/vertical rules and proposes empty cells as
    reviewable value targets. It is deliberately conservative and reversible:
    all generated labels are ordinary review labels with source
    ``visual_line_detect`` so the reviewer can delete, resize, or reclassify
    them before authoring.
    """

    image = Image.open(policy.source_image).convert("L")
    candidates = _detect_blank_template_cells(image, policy.labels)
    if not candidates:
        return policy, {"enabled": True, "method": "pil_line_projection", "candidateCount": 0}
    next_labels = [*policy.labels, *candidates]
    return (
        ReviewPolicy(
            schema_version=policy.schema_version,
            source_detections=policy.source_detections,
            source_image=policy.source_image,
            image_width=policy.image_width,
            image_height=policy.image_height,
            labels=next_labels,
            source_engine=f"{policy.source_engine}+visual_line_detect",
            created_at=policy.created_at,
        ),
        {"enabled": True, "method": "pil_line_projection", "candidateCount": len(candidates)},
    )


def load_review_policy(path: Path) -> ReviewPolicy:
    return ReviewPolicy.from_dict(json.loads(path.read_text(encoding="utf-8")), base_dir=path.parent)


def write_review_policy(policy: ReviewPolicy, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    review_path = output_dir / "review.json"
    overlay_path = output_dir / "review_overlay.png"
    with review_path.open("w", encoding="utf-8") as handle:
        json.dump(policy.to_dict(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    from .policy_visualize import render_policy_overlay

    image = Image.open(policy.source_image).convert("RGB")
    render_policy_overlay(image, policy).save(overlay_path)
    return {"review": review_path, "overlay": overlay_path}


def review_summary(labels: list[ReviewLabel]) -> dict[str, Any]:
    by_status = {status: 0 for status in REVIEW_STATUSES}
    by_type = {auto_type: 0 for auto_type in AUTO_TYPES}
    for label in labels:
        by_status[label.status] += 1
        by_type[label.auto_type] += 1
    return {"total": len(labels), "by_status": by_status, "by_auto_type": by_type}


def policy_from_edited_rows(base: ReviewPolicy, rows: list[dict[str, Any]]) -> ReviewPolicy:
    by_id = {row.get("id"): row for row in rows}
    labels: list[ReviewLabel] = []
    for label in base.labels:
        row = by_id.get(label.id, {})
        bbox = _bbox_from_edited_row(row, label.bbox, base.image_width, base.image_height)
        labels.append(
            ReviewLabel(
                id=label.id,
                text=label.text,
                confidence=label.confidence,
                bbox=bbox,
                polygon=_polygon_from_bbox(bbox) if bbox.to_list() != label.bbox.to_list() else label.polygon,
                status=_review_status(row.get("status", label.status)),
                auto_type=_auto_type(row.get("auto_type", label.auto_type)),
                reason=str(row.get("reason", label.reason)),
                locked=bool(row.get("locked", label.locked)),
                notes=str(row.get("notes", label.notes)),
                original_text=label.original_text,
                original_confidence=label.original_confidence,
                text_source=label.text_source,
                ocr_text_stale=label.ocr_text_stale,
                rec_text=label.rec_text,
                rec_confidence=label.rec_confidence,
                rec_engine=label.rec_engine,
                rec_updated_at=label.rec_updated_at,
            )
        )
    return ReviewPolicy(
        schema_version=base.schema_version,
        source_detections=base.source_detections,
        source_image=base.source_image,
        image_width=base.image_width,
        image_height=base.image_height,
        labels=labels,
        source_engine=base.source_engine,
        created_at=base.created_at,
    )


def _bbox_from_edited_row(row: dict[str, Any], fallback: BBox, image_width: int, image_height: int) -> BBox:
    if isinstance(row.get("bbox"), list):
        try:
            return BBox.from_list(row["bbox"]).clipped(image_width, image_height)
        except Exception:
            return fallback
    if all(key in row for key in ("x", "y", "w", "h")):
        try:
            return BBox(
                int(round(float(row["x"]))),
                int(round(float(row["y"]))),
                int(round(float(row["w"]))),
                int(round(float(row["h"]))),
            ).clipped(image_width, image_height)
        except Exception:
            return fallback
    return fallback


def _polygon_from_bbox(bbox: BBox) -> list[list[int]]:
    return [[bbox.x, bbox.y], [bbox.right, bbox.y], [bbox.right, bbox.bottom], [bbox.x, bbox.bottom]]


def review_rows(policy: ReviewPolicy) -> list[dict[str, Any]]:
    rows = []
    for label in policy.labels:
        bbox = label.bbox
        rows.append(
            {
                "id": label.id,
                "status": label.status,
                "auto_type": label.auto_type,
                "text": label.text,
                "confidence": label.confidence,
                "x": bbox.x,
                "y": bbox.y,
                "w": bbox.width,
                "h": bbox.height,
                "reason": label.reason,
                "notes": label.notes,
                "locked": label.locked,
                "original_text": label.original_text,
                "original_confidence": label.original_confidence,
                "text_source": label.text_source,
                "ocr_text_stale": label.ocr_text_stale,
                "rec_text": label.rec_text,
                "rec_confidence": label.rec_confidence,
                "rec_engine": label.rec_engine,
                "rec_updated_at": label.rec_updated_at,
            }
        )
    return rows


def use_labels(policy: ReviewPolicy, statuses: tuple[ReviewStatus, ...] = ("use",)) -> list[ReviewLabel]:
    return [label for label in policy.labels if label.status in statuses]


def _label_detection(raw: dict[str, Any], image: Image.Image, width: int, height: int) -> ReviewLabel:
    bbox = BBox.from_list(raw["bbox"]).clipped(width, height)
    text = str(raw.get("text", "")).strip()
    confidence = float(raw["confidence"]) if raw.get("confidence") is not None else None
    polygon = [[int(round(p[0])), int(round(p[1]))] for p in raw.get("polygon", [])]
    status, auto_type, reason = classify_detection(text, confidence, bbox, image, width, height)
    return ReviewLabel(
        id=str(raw.get("id", f"det_{len(text):04d}")),
        text=text,
        confidence=confidence,
        bbox=bbox,
        polygon=polygon,
        status=status,
        auto_type=auto_type,
        reason=reason,
        original_text=text,
        original_confidence=confidence,
        text_source="paddle_initial",
    )


def _detect_blank_template_cells(image: Image.Image, existing_labels: list[ReviewLabel]) -> list[ReviewLabel]:
    arr = np.asarray(image, dtype=np.uint8)
    height, width = arr.shape[:2]
    dark = arr < 185
    # Use longest contiguous dark run, not simple dark-pixel density. Density is
    # easily triggered by text rows and produced hundreds of false grid cells.
    horizontal = _line_centers_from_runs(_max_dark_runs(dark), threshold=max(120, int(width * 0.18)), merge_gap=4)
    vertical = _line_centers_from_runs(_max_dark_runs(dark.T), threshold=max(60, int(height * 0.05)), merge_gap=4)
    if len(horizontal) < 2 or len(vertical) < 2:
        return []
    existing_boxes = [label.bbox for label in existing_labels]
    labels: list[ReviewLabel] = []
    seen: set[tuple[int, int, int, int]] = set()
    for y1, y2 in zip(horizontal, horizontal[1:]):
        cell_h = y2 - y1
        if cell_h < 14 or cell_h > 120:
            continue
        for x1, x2 in zip(vertical, vertical[1:]):
            cell_w = x2 - x1
            if cell_w < 45 or cell_w > min(720, width):
                continue
            box = BBox(x=x1 + 2, y=y1 + 2, width=max(1, cell_w - 4), height=max(1, cell_h - 4)).clipped(width, height)
            if box.width < 18 or box.height < 10:
                continue
            if _box_dark_ratio(arr, box) > 0.10:
                continue
            if any(_intersection_ratio(box, existing) > 0.32 for existing in existing_boxes):
                continue
            key = tuple(box.to_list())
            if key in seen:
                continue
            seen.add(key)
            label_id = f"visual_{len(labels) + 1:04d}"
            labels.append(
                ReviewLabel(
                    id=label_id,
                    text="",
                    confidence=None,
                    bbox=box,
                    polygon=[[box.x, box.y], [box.right, box.y], [box.right, box.bottom], [box.x, box.bottom]],
                    status="keep",
                    auto_type="table_cell",
                    reason="blank template visual candidate from line detection; reviewer must mark use before authoring",
                    locked=False,
                    notes="빈 템플릿 값 입력 후보입니다. 실제 값 삽입 영역이면 사용으로 변경하세요.",
                    original_text="",
                    original_confidence=None,
                    text_source="visual_line_detect",
                    ocr_text_stale=False,
                )
            )
            if len(labels) >= 240:
                return labels
    return labels


def _max_dark_runs(dark: np.ndarray) -> np.ndarray:
    runs: list[int] = []
    for row in dark:
        best = 0
        current = 0
        for value in row:
            if bool(value):
                current += 1
                best = max(best, current)
            else:
                current = 0
        runs.append(best)
    return np.asarray(runs, dtype=np.int32)


def _line_centers_from_runs(runs: np.ndarray, *, threshold: int, merge_gap: int) -> list[int]:
    indexes = np.where(runs >= threshold)[0].tolist()
    if not indexes:
        return []
    groups: list[list[int]] = []
    current = [indexes[0]]
    for index in indexes[1:]:
        if index <= current[-1] + 1:
            current.append(index)
        else:
            groups.append(current)
            current = [index]
    groups.append(current)
    centers = [int(round((group[0] + group[-1]) / 2)) for group in groups]
    merged: list[int] = []
    for center in centers:
        if merged and center - merged[-1] <= merge_gap:
            merged[-1] = int(round((merged[-1] + center) / 2))
        else:
            merged.append(center)
    return merged


def _line_centers(profile: np.ndarray, *, threshold: float, min_run: int, merge_gap: int) -> list[int]:
    indexes = np.where(profile >= threshold)[0].tolist()
    if not indexes:
        return []
    groups: list[list[int]] = []
    current = [indexes[0]]
    for index in indexes[1:]:
        if index <= current[-1] + 1:
            current.append(index)
        else:
            if len(current) >= min_run:
                groups.append(current)
            current = [index]
    if len(current) >= min_run:
        groups.append(current)
    centers = [int(round((group[0] + group[-1]) / 2)) for group in groups]
    merged: list[int] = []
    for center in centers:
        if merged and center - merged[-1] <= merge_gap:
            merged[-1] = int(round((merged[-1] + center) / 2))
        else:
            merged.append(center)
    return merged


def _with_edges(positions: list[int], extent: int) -> list[int]:
    values = sorted(set([pos for pos in positions if 0 <= pos <= extent]))
    if not values:
        return [0, extent]
    if values[0] > 12:
        values.insert(0, 0)
    if extent - values[-1] > 12:
        values.append(extent)
    return values


def _box_dark_ratio(arr: np.ndarray, bbox: BBox) -> float:
    crop = arr[bbox.y : bbox.bottom, bbox.x : bbox.right]
    if crop.size == 0:
        return 0.0
    return float(np.count_nonzero(crop < 185) / crop.size)


def _intersection_ratio(a: BBox, b: BBox) -> float:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.right, b.right)
    y2 = min(a.bottom, b.bottom)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    intersection = (x2 - x1) * (y2 - y1)
    return float(intersection / max(1, min(a.width * a.height, b.width * b.height)))


def classify_detection(text: str, confidence: float | None, bbox: BBox, image: Image.Image, width: int, height: int) -> tuple[ReviewStatus, AutoType, str]:
    red_ratio = _red_ratio(image, bbox)
    y_rel = bbox.y / max(1, height)
    w_rel = bbox.width / max(1, width)
    h_rel = bbox.height / max(1, height)
    text_no_space = re.sub(r"\s+", "", text)

    if not text_no_space or (confidence is not None and confidence <= 0.05):
        return "ignore", "unknown", "empty text or near-zero confidence"
    if red_ratio >= 0.08:
        return "ignore", "stamp_or_seal", f"red pixel ratio {red_ratio:.2f}"
    if y_rel <= 0.055 or y_rel >= 0.92:
        return "keep", "header_footer", "near page header/footer"
    if w_rel >= 0.48 and len(text_no_space) >= 18:
        return "keep", "long_paragraph", "long wide text line"
    if _looks_static_label(text_no_space):
        return "keep", "static_label", "static document label keyword"
    if _looks_field_value(text_no_space):
        if w_rel <= 0.18 and h_rel <= 0.035 and MOSTLY_NUMERIC_RE.match(text_no_space):
            return "use", "table_cell", "small numeric/table-like value"
        return "use", "field_value", "value-like text pattern"
    if MOSTLY_NUMERIC_RE.match(text_no_space) and len(text_no_space) <= 10:
        return "use", "table_cell", "short numeric cell"
    if confidence is not None and confidence < 0.35:
        return "ignore", "unknown", "low confidence"
    return "keep", "unknown", "safe default keep"


def _looks_static_label(text: str) -> bool:
    if text in STATIC_LABEL_KEYWORDS:
        return True
    if any(keyword in text for keyword in STATIC_LABEL_KEYWORDS):
        return len(text) <= 18
    return False


def _looks_field_value(text: str) -> bool:
    if DATE_RE.search(text) or PHONE_RE.search(text) or ID_RE.search(text) or AMOUNT_RE.search(text):
        return True
    if re.search(r"\d", text) and len(text) >= 4 and not re.search(r"[가-힣]{6,}", text):
        return True
    return False


def _red_ratio(image: Image.Image, bbox: BBox) -> float:
    region = image.crop((bbox.x, bbox.y, bbox.right, bbox.bottom)).convert("RGB")
    arr = np.asarray(region, dtype=np.int16)
    if arr.size == 0:
        return 0.0
    red = arr[:, :, 0]
    green = arr[:, :, 1]
    blue = arr[:, :, 2]
    red_pixels = (red > 120) & (red > green * 1.25) & (red > blue * 1.25)
    return float(np.count_nonzero(red_pixels) / red_pixels.size)


def _review_status(value: Any) -> ReviewStatus:
    if value in REVIEW_STATUSES:
        return value  # type: ignore[return-value]
    return "keep"


def _auto_type(value: Any) -> AutoType:
    if value in AUTO_TYPES:
        return value  # type: ignore[return-value]
    return "unknown"


def _resolve_review_path(path: Path, base: Path) -> Path:
    base_candidate = (base / path).resolve()
    if base_candidate.exists():
        return base_candidate
    cwd_candidate = (Path.cwd() / path).resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    return base_candidate


def _infer_engine(path: Path) -> str:
    parts = path.parts
    if "ocr_eval" in parts:
        idx = parts.index("ocr_eval")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return "unknown"
