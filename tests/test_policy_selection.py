from __future__ import annotations

from datafactory.policy_selection import apply_status_to_ids, selected_ids_from_altair_event


def test_apply_status_to_ids() -> None:
    rows = [{"id": "a", "status": "keep"}, {"id": "b", "status": "keep"}]
    updated = apply_status_to_ids(rows, {"b"}, "use")
    assert updated == [{"id": "a", "status": "keep"}, {"id": "b", "status": "use"}]


def test_selected_ids_from_point_event_variants() -> None:
    rows = []
    assert selected_ids_from_altair_event({"selection": {"bbox_click": [{"id": "a"}, {"id": "b"}]}}, rows) == {"a", "b"}
    assert selected_ids_from_altair_event({"selection": {"bbox_click": {"id": ["a", "c"]}}}, rows) == {"a", "c"}


def test_selected_ids_from_interval_event() -> None:
    rows = [
        {"id": "a", "cx": 10, "cy": 10},
        {"id": "b", "cx": 50, "cy": 50},
        {"id": "c", "cx": 90, "cy": 90},
    ]
    event = {"selection": {"bbox_drag": {"x": [0, 60], "y": [0, 60]}}}
    assert selected_ids_from_altair_event(event, rows) == {"a", "b"}
