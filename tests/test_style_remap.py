from __future__ import annotations

import pytest

from datafactory.style_remap import remap_styles_from_previous


def _style(name: str, *, size: int) -> dict[str, object]:
    return {
        "style_class": name,
        "font_family": "Batang",
        "font_path": "fonts/batang.ttc",
        "font_size": size,
        "fill": [24, 24, 24],
        "align": "center",
    }


def test_style_remap_prefers_anchor_and_restores_visual_render_policy() -> None:
    previous_schema = {
        "fields": [
            {
                "field_id": "old_name",
                "bbox_label_id": "anchor_1",
                "style_class": "old_name_style",
                "render_mode": "handwriting",
                "render_policy": {"align": "right", "valign": "bottom", "overflow": "shrink"},
            }
        ]
    }
    current_schema = {
        "fields": [
            {
                "field_id": "new_name",
                "bbox_label_id": "anchor_1",
                "style_class": "agent_default",
                "render_mode": "printed",
                "render_policy": {"render": True, "align": "left", "valign": "middle", "overflow": "clip"},
            }
        ]
    }

    schema, stylesheet, report = remap_styles_from_previous(
        current_schema,
        {"style_classes": [_style("agent_default", size=28)]},
        previous_schema,
        {"style_classes": [_style("old_name_style", size=17)]},
    )

    field = schema["fields"][0]
    assert field["style_class"] == "old_name_style"
    assert field["render_mode"] == "handwriting"
    assert field["render_policy"] == {"render": True, "align": "right", "valign": "bottom", "overflow": "shrink"}
    assert stylesheet["style_classes"][0]["font_size"] == 17
    assert report["methods"] == {"anchor": 1, "field_id": 0, "style_class": 0}
    assert report["restoredRenderModes"] == 1


def test_style_remap_uses_field_id_then_existing_previous_style_class() -> None:
    previous_schema = {
        "fields": [
            {"field_id": "same_field", "bbox_label_id": "old_a", "style_class": "field_style"},
            {"field_id": "legacy_other", "bbox_label_id": "old_b", "style_class": "shared_style"},
        ]
    }
    current_schema = {
        "fields": [
            {"field_id": "same_field", "bbox_label_id": "new_a", "style_class": "agent_style"},
            {"field_id": "new_other", "bbox_label_id": "new_b", "style_class": "shared_style"},
        ]
    }

    schema, _stylesheet, report = remap_styles_from_previous(
        current_schema,
        {"style_classes": [_style("agent_style", size=28), _style("shared_style", size=28)]},
        previous_schema,
        {"style_classes": [_style("field_style", size=15), _style("shared_style", size=19)]},
    )

    assert [field["style_class"] for field in schema["fields"]] == ["field_style", "shared_style"]
    assert report["methods"] == {"anchor": 0, "field_id": 1, "style_class": 1}


def test_style_remap_keeps_unmapped_hidden_field_but_rejects_unmapped_rendered_field() -> None:
    current_stylesheet = {"style_classes": [_style("new_hidden", size=13)]}
    hidden_schema = {
        "fields": [
            {
                "field_id": "hidden_composite_source",
                "bbox_label_id": "new_anchor",
                "style_class": "new_hidden",
                "render_policy": {"render": False},
            }
        ]
    }

    schema, stylesheet, report = remap_styles_from_previous(
        hidden_schema,
        current_stylesheet,
        {"fields": []},
        {"style_classes": []},
    )

    assert schema["fields"][0]["style_class"] == "new_hidden"
    assert stylesheet["style_classes"][0]["style_class"] == "new_hidden"
    assert report["unresolvedHidden"] == ["hidden_composite_source"]

    rendered_schema = {"fields": [{**hidden_schema["fields"][0], "render_policy": {"render": True}}]}
    with pytest.raises(ValueError, match="unresolved rendered style mappings"):
        remap_styles_from_previous(
            rendered_schema,
            current_stylesheet,
            {"fields": []},
            {"style_classes": []},
        )
