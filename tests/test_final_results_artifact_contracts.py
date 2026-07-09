from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = ROOT / "outputs" / "results"


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _bbox_leaves(value: Any, prefix: str = "") -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    if {"l", "t", "r", "b"}.issubset(value.keys()):
        return {prefix: value}
    leaves: dict[str, dict[str, Any]] = {}
    for key, child in value.items():
        child_path = f"{prefix}/{key}" if prefix else str(key)
        leaves.update(_bbox_leaves(child, child_path))
    return leaves


def _value_at_path(payload: Any, path: str) -> Any:
    if isinstance(payload, dict) and path in payload:
        return payload[path]
    cursor = payload
    for part in path.split("/") if path else []:
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        elif isinstance(cursor, list) and part.isdigit() and int(part) < len(cursor):
            cursor = cursor[int(part)]
        else:
            return None
    return cursor


def _is_nonempty_scalar(value: Any) -> bool:
    return value is not None and not isinstance(value, (dict, list)) and str(value).strip() != ""


def _sample_gt_paths() -> list[Path]:
    if not RESULTS_ROOT.exists():
        return []
    return sorted(path for path in RESULTS_ROOT.glob("*/*/sample_*.json") if not path.name.endswith("-bbox.json"))


def test_final_results_bbox_only_points_to_rendered_nonempty_gt_values() -> None:
    """Final bbox is an actual rendered glyph bbox, never a source/review fallback.

    If a bbox leaf exists, the same semantic path must exist in the paired GT
    JSON and its value must be a non-empty scalar.  Empty checkboxes, skipped
    values, object/list nodes, and stale flat-path bboxes are all invalid.
    """

    gt_paths = _sample_gt_paths()
    if not gt_paths:
        pytest.skip("outputs/results has no generated sample JSON files")

    violations: list[str] = []
    checked_bbox_leaves = 0
    for gt_path in gt_paths:
        bbox_path = gt_path.with_name(f"{gt_path.stem}-bbox.json")
        if not bbox_path.exists():
            continue
        gt_payload = _json(gt_path)
        bbox_payload = _json(bbox_path)
        for semantic_path, bbox in _bbox_leaves(bbox_payload).items():
            checked_bbox_leaves += 1
            value = _value_at_path(gt_payload, semantic_path)
            if not _is_nonempty_scalar(value):
                violations.append(f"{bbox_path.relative_to(ROOT)}::{semantic_path} -> GT value {value!r}")
            for axis in ("l", "t", "r", "b"):
                coord = bbox.get(axis)
                if not isinstance(coord, (int, float)) or not 0 <= float(coord) <= 1:
                    violations.append(f"{bbox_path.relative_to(ROOT)}::{semantic_path}.{axis} invalid coord {coord!r}")
            if all(isinstance(bbox.get(axis), (int, float)) for axis in ("l", "t", "r", "b")):
                if float(bbox["l"]) >= float(bbox["r"]) or float(bbox["t"]) >= float(bbox["b"]):
                    violations.append(f"{bbox_path.relative_to(ROOT)}::{semantic_path} invalid ltrb order {bbox!r}")

    assert checked_bbox_leaves > 0, "no final result bbox leaves were checked"
    assert not violations, "invalid final-result bbox contract:\n" + "\n".join(violations[:80])
