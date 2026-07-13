from __future__ import annotations

from copy import deepcopy
from typing import Any


VISUAL_RENDER_POLICY_KEYS = ("align", "valign", "overflow", "checkbox_style", "fit")


def _anchor_id(field: dict[str, Any]) -> str:
    return str(field.get("bbox_label_id") or field.get("source_detection_id") or field.get("anchor_id") or "").strip()


def _render_enabled(field: dict[str, Any]) -> bool:
    policy = field.get("render_policy") if isinstance(field.get("render_policy"), dict) else {}
    value = policy.get("render", True)
    return not (value is False or str(value).strip().lower() in {"false", "0", "no", "off"})


def _fields_by(fields: list[dict[str, Any]], key) -> dict[str, list[dict[str, Any]]]:  # noqa: ANN001
    result: dict[str, list[dict[str, Any]]] = {}
    for field in fields:
        value = str(key(field) or "").strip()
        if value:
            result.setdefault(value, []).append(field)
    return result


def _style_map(stylesheet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(style.get("style_class")): style
        for style in stylesheet.get("style_classes", [])
        if isinstance(style, dict) and str(style.get("style_class") or "").strip()
    }


def _restore_visual_render_policy(current: dict[str, Any], previous: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    current_policy = deepcopy(current.get("render_policy")) if isinstance(current.get("render_policy"), dict) else {}
    previous_policy = previous.get("render_policy") if isinstance(previous.get("render_policy"), dict) else {}
    before = deepcopy(current_policy)
    preserved_render = current_policy.get("render") if "render" in current_policy else None
    for key in VISUAL_RENDER_POLICY_KEYS:
        if key in previous_policy:
            current_policy[key] = deepcopy(previous_policy[key])
        else:
            current_policy.pop(key, None)
    if preserved_render is not None:
        current_policy["render"] = preserved_render
    elif "render" in current_policy:
        current_policy.pop("render", None)
    return current_policy, current_policy != before


def remap_styles_from_previous(
    current_schema: dict[str, Any],
    current_stylesheet: dict[str, Any],
    previous_schema: dict[str, Any],
    previous_stylesheet: dict[str, Any],
    *,
    require_all_rendered: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Restore field styles from a prior authoring bundle without changing semantics.

    Physical bbox anchors are authoritative. Field IDs and existing previous
    style-class names are deterministic fallbacks for documents whose review
    anchors were regenerated during semantic-schema refinement.
    """

    schema = deepcopy(current_schema)
    stylesheet = deepcopy(current_stylesheet)
    previous_fields = [field for field in previous_schema.get("fields", []) if isinstance(field, dict)]
    current_fields = [field for field in schema.get("fields", []) if isinstance(field, dict)]
    previous_styles = _style_map(previous_stylesheet)
    current_styles = _style_map(current_stylesheet)
    by_anchor = _fields_by(previous_fields, _anchor_id)
    by_field_id = _fields_by(previous_fields, lambda field: field.get("field_id"))

    methods = {"anchor": 0, "field_id": 0, "style_class": 0}
    unresolved_rendered: list[str] = []
    unresolved_hidden: list[str] = []
    changed_style_refs = 0
    restored_render_policies = 0

    for field in current_fields:
        field_id = str(field.get("field_id") or "").strip()
        previous_field: dict[str, Any] | None = None
        target_style_class = ""
        method = ""

        anchor_candidates = by_anchor.get(_anchor_id(field), []) if _anchor_id(field) else []
        if len(anchor_candidates) == 1:
            previous_field = anchor_candidates[0]
            target_style_class = str(previous_field.get("style_class") or "").strip()
            method = "anchor"
        else:
            field_candidates = by_field_id.get(field_id, []) if field_id else []
            if len(field_candidates) == 1:
                previous_field = field_candidates[0]
                target_style_class = str(previous_field.get("style_class") or "").strip()
                method = "field_id"
            else:
                current_style_class = str(field.get("style_class") or "").strip()
                if current_style_class in previous_styles:
                    target_style_class = current_style_class
                    method = "style_class"

        if not target_style_class or target_style_class not in previous_styles:
            (unresolved_rendered if _render_enabled(field) else unresolved_hidden).append(field_id or "<unknown>")
            continue

        methods[method] += 1
        if field.get("style_class") != target_style_class:
            field["style_class"] = target_style_class
            changed_style_refs += 1
        if previous_field is not None:
            render_policy, changed = _restore_visual_render_policy(field, previous_field)
            if render_policy:
                field["render_policy"] = render_policy
            else:
                field.pop("render_policy", None)
            restored_render_policies += int(changed)

    if require_all_rendered and unresolved_rendered:
        raise ValueError(f"unresolved rendered style mappings: {', '.join(unresolved_rendered)}")

    referenced_styles = {
        str(field.get("style_class") or "").strip()
        for field in current_fields
        if str(field.get("style_class") or "").strip()
    }
    merged_styles = [deepcopy(style) for style in previous_stylesheet.get("style_classes", []) if isinstance(style, dict)]
    merged_names = {str(style.get("style_class") or "").strip() for style in merged_styles}
    for style_class in sorted(referenced_styles - merged_names):
        if style_class in current_styles:
            merged_styles.append(deepcopy(current_styles[style_class]))
            merged_names.add(style_class)
    stylesheet["style_classes"] = merged_styles

    report = {
        "fields": len(current_fields),
        "renderedFields": sum(_render_enabled(field) for field in current_fields),
        "methods": methods,
        "changedStyleReferences": changed_style_refs,
        "restoredRenderPolicies": restored_render_policies,
        "unresolvedRendered": unresolved_rendered,
        "unresolvedHidden": unresolved_hidden,
        "styleClasses": len(merged_styles),
    }
    return schema, stylesheet, report
