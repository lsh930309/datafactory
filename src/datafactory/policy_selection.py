from __future__ import annotations

from typing import Any

from .policy import REVIEW_STATUSES, ReviewStatus


def apply_status_to_ids(rows: list[dict[str, Any]], ids: set[str], status: ReviewStatus) -> list[dict[str, Any]]:
    if status not in REVIEW_STATUSES:
        raise ValueError(f"invalid review status: {status}")
    return [{**row, "status": status} if str(row.get("id")) in ids else dict(row) for row in rows]


def selected_ids_from_altair_event(event: Any, rows: list[dict[str, Any]]) -> set[str]:
    """Extract bbox ids from a Streamlit Altair selection event.

    Supports both point/click selections carrying ids and interval/drag selections
    carrying x/y ranges in chart-display coordinates. The caller should provide
    rows with scaled center columns `cx` and `cy` when interval selection is used.
    """
    selection = _event_selection(event)
    selected: set[str] = set()
    for value in selection.values():
        selected.update(_ids_from_point_selection(value))
        selected.update(_ids_from_interval_selection(value, rows))
    return selected


def _event_selection(event: Any) -> dict[str, Any]:
    if event is None:
        return {}
    if isinstance(event, dict):
        raw = event.get("selection", event)
        return raw if isinstance(raw, dict) else {}
    raw = getattr(event, "selection", None)
    return raw if isinstance(raw, dict) else {}


def _ids_from_point_selection(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        if "id" in value:
            return _ids_from_point_selection(value["id"])
        # Some Streamlit/Altair versions return {"id": [..]} or
        # {"vlPoint": ..., "id": "..."}; also tolerate nested dictionaries.
        found: set[str] = set()
        for item in value.values():
            found.update(_ids_from_point_selection(item))
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for item in value:
            found.update(_ids_from_point_selection(item))
        return found
    return set()


def _ids_from_interval_selection(value: Any, rows: list[dict[str, Any]]) -> set[str]:
    if not isinstance(value, dict):
        return set()
    x_range = value.get("x")
    y_range = value.get("y")
    if not _is_range(x_range) or not _is_range(y_range):
        return set()
    x1, x2 = sorted([float(x_range[0]), float(x_range[1])])
    y1, y2 = sorted([float(y_range[0]), float(y_range[1])])
    selected: set[str] = set()
    for row in rows:
        if "cx" not in row or "cy" not in row:
            continue
        cx = float(row["cx"])
        cy = float(row["cy"])
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            selected.add(str(row["id"]))
    return selected


def _is_range(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value)
