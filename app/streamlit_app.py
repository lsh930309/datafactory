from __future__ import annotations

import io
import sys
import base64
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st
import altair as alt
import pandas as pd

from datafactory.inpaint import InpaintConfig, inpaint_from_review_policy
from datafactory.inpaint_export import write_inpaint_result
from datafactory.models import RenderJob
from datafactory.pipeline import render_job
from datafactory.policy import (
    AUTO_TYPES,
    REVIEW_STATUSES,
    draft_review_policy,
    load_review_policy,
    policy_from_edited_rows,
    review_rows,
    review_summary,
    write_review_policy,
)
from datafactory.policy_selection import apply_status_to_ids, selected_ids_from_altair_event
from datafactory.policy_visualize import render_policy_overlay
from datafactory.render import render_template
from datafactory.templates import load_template


def _editor_rows(edited: Any) -> list[dict[str, Any]]:
    if hasattr(edited, "to_dict"):
        data = edited.to_dict(orient="records")
        return [dict(row) for row in data]
    if isinstance(edited, list):
        return [dict(row) for row in edited]
    return []


def _safe_template_id(path: Path) -> str:
    return path.parent.name or path.stem


def _existing_detection_paths() -> list[str]:
    preferred = sorted(ROOT.glob("outputs/ocr_eval/paddleocr/*/detections.json"))
    others = sorted(path for path in ROOT.glob("outputs/ocr_eval/*/*/detections.json") if "/paddleocr/" not in str(path))
    paths = preferred + others
    return [str(path.relative_to(ROOT)) for path in paths]


def _existing_review_paths() -> list[str]:
    return [str(path.relative_to(ROOT)) for path in sorted(ROOT.glob("outputs/reviews/*/review.json"))]


def _policy_selection_chart(policy, *, display_width: int = 520):
    image = Image.open(policy.source_image).convert("RGB")
    scale = min(1.0, display_width / max(1, image.width))
    display_height = max(1, round(image.height * scale))
    display_width = max(1, round(image.width * scale))
    display = image.resize((display_width, display_height))
    buffer = io.BytesIO()
    display.save(buffer, format="PNG")
    image_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

    rows: list[dict[str, Any]] = []
    for label in policy.labels:
        box = label.bbox
        x = box.x * scale
        y = box.y * scale
        x2 = box.right * scale
        y2 = box.bottom * scale
        rows.append(
            {
                "id": label.id,
                "status": label.status,
                "auto_type": label.auto_type,
                "text": label.text,
                "confidence": label.confidence,
                "x": x,
                "y": y,
                "x2": x2,
                "y2": y2,
                "cx": (x + x2) / 2,
                "cy": (y + y2) / 2,
            }
        )
    bbox_df = pd.DataFrame(rows)
    horizontal_rows: list[dict[str, Any]] = []
    vertical_rows: list[dict[str, Any]] = []
    for row in rows:
        horizontal_rows.append({**row, "line_y": row["y"]})
        horizontal_rows.append({**row, "line_y": row["y2"]})
        vertical_rows.append({**row, "line_x": row["x"]})
        vertical_rows.append({**row, "line_x": row["x2"]})
    horizontal_df = pd.DataFrame(horizontal_rows)
    vertical_df = pd.DataFrame(vertical_rows)
    image_df = pd.DataFrame([{"url": image_url, "x": display_width / 2, "y": display_height / 2}])

    click = alt.selection_point(name="bbox_click", fields=["id"], on="click", clear="dblclick")
    drag = alt.selection_interval(name="bbox_drag", encodings=["x", "y"])
    x_scale = alt.Scale(domain=[0, display_width], nice=False)
    y_scale = alt.Scale(domain=[display_height, 0], nice=False)

    background = (
        alt.Chart(image_df)
        .mark_image(width=display_width, height=display_height)
        .encode(x=alt.X("x:Q", scale=x_scale, axis=None), y=alt.Y("y:Q", scale=y_scale, axis=None), url="url:N")
    )
    status_color = alt.Color(
        "status:N",
        scale=alt.Scale(domain=["use", "keep", "ignore"], range=["#00c853", "#448aff", "#ff5252"]),
        legend=alt.Legend(orient="bottom"),
    )
    horizontal_rules = (
        alt.Chart(horizontal_df)
        .mark_rule(strokeWidth=2)
        .encode(
            x=alt.X("x:Q", scale=x_scale, axis=None),
            x2="x2:Q",
            y=alt.Y("line_y:Q", scale=y_scale, axis=None),
            color=status_color,
            tooltip=["id:N", "status:N", "auto_type:N", "confidence:Q", "text:N"],
        )
    )
    vertical_rules = (
        alt.Chart(vertical_df)
        .mark_rule(strokeWidth=2)
        .encode(
            x=alt.X("line_x:Q", scale=x_scale, axis=None),
            y=alt.Y("y:Q", scale=y_scale, axis=None),
            y2="y2:Q",
            color=status_color,
            tooltip=["id:N", "status:N", "auto_type:N", "confidence:Q", "text:N"],
        )
    )
    points = (
        alt.Chart(bbox_df)
        .mark_circle(size=95, opacity=0.05)
        .encode(
            x=alt.X("cx:Q", scale=x_scale, axis=None),
            y=alt.Y("cy:Q", scale=y_scale, axis=None),
            tooltip=["id:N", "status:N", "auto_type:N", "text:N"],
        )
        .add_params(click, drag)
    )
    chart = (background + horizontal_rules + vertical_rules + points).properties(width=display_width, height=display_height).configure_view(stroke=None)
    return chart, rows


st.set_page_config(page_title="DataFactory v1", layout="wide")
st.title("DataFactory v1 - Synthetic Document Toolkit")
st.caption("Template rendering + PaddleOCR bbox review policy + selected-bbox inpainting")

preview_tab, review_tab = st.tabs(["Synthetic preview", "OCR bbox review"])

with preview_tab:
    with st.sidebar:
        st.header("Template")
        template_path = st.text_input("Template JSON path", value="templates/family_relation_demo.json")
        sample_count = st.number_input("Batch sample count", min_value=1, max_value=1000, value=10, step=1)
        seed = st.number_input("Random seed", min_value=0, max_value=999999999, value=20260626, step=1)
        output_dir = st.text_input("Output directory", value="outputs/gui_run")
        show_requested = st.checkbox("Show requested bboxes", value=True)
        show_actual = st.checkbox("Show actual rendered bboxes", value=True)

    load_clicked = st.button("Load preview", type="primary")

    if load_clicked or template_path:
        try:
            template = load_template(Path(template_path))
            preview_values = {field.name: field.value or f"<{field.type}>" for field in template.fields}
            preview, annotations = render_template(template, preview_values)
            overlay = preview.copy()
            draw = ImageDraw.Draw(overlay)
            if show_requested:
                for field in template.fields:
                    box = field.bbox
                    draw.rectangle([box.x, box.y, box.right, box.bottom], outline=(255, 180, 0), width=4)
            if show_actual:
                for annotation in annotations:
                    box = annotation.bbox
                    draw.rectangle([box.x, box.y, box.right, box.bottom], outline=(0, 180, 255), width=4)

            left, right = st.columns([2, 1])
            with left:
                st.subheader("Preview")
                st.image(overlay, caption="Orange=requested bbox, Blue=actual rendered bbox", use_container_width=True)
            with right:
                st.subheader("Template summary")
                st.write(
                    {
                        "template_id": template.template_id,
                        "image_path": str(template.image_path),
                        "fields": len(template.fields),
                        "image_size": preview.size,
                    }
                )
                st.json({field.name: preview_values[field.name] for field in template.fields})
                buffer = io.BytesIO()
                preview.save(buffer, format="PNG")
                st.download_button(
                    "Download preview PNG",
                    data=buffer.getvalue(),
                    file_name=f"{template.template_id}_preview.png",
                    mime="image/png",
                )

            with st.form("batch_render_form"):
                st.subheader("Batch render")
                st.write(f"Render {sample_count} sample(s) to `{output_dir}`.")
                submitted = st.form_submit_button("Render batch")
                if submitted:
                    samples = render_job(
                        RenderJob(
                            template=template,
                            output_dir=Path(output_dir),
                            count=int(sample_count),
                            seed=int(seed),
                        )
                    )
                    st.success(f"Rendered {len(samples)} sample(s) to {output_dir}")
                    st.code(str(Path(output_dir) / "manifest.jsonl"))
        except Exception as exc:  # pragma: no cover - UI guardrail
            st.error(f"Failed to load/render template: {exc}")
            st.exception(exc)

with review_tab:
    st.subheader("BBox review policy")
    st.write("PaddleOCR `detections.json`에서 자동 pre-label을 만들고, `use` bbox만 인페인팅합니다.")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        detection_options = _existing_detection_paths()
        default_detection = (
            "outputs/ocr_eval/paddleocr/전입세대확인서/detections.json"
            if Path("outputs/ocr_eval/paddleocr/전입세대확인서/detections.json").exists()
            else (detection_options[0] if detection_options else "")
        )
        selected_detection = st.selectbox(
            "Existing detections",
            options=detection_options or [default_detection],
            index=(detection_options.index(default_detection) if default_detection in detection_options else 0),
        )
        detections_path = st.text_input(
            "Detections JSON path",
            value=selected_detection,
        )
        review_options = _existing_review_paths()
        default_review = "outputs/reviews/전입세대확인서/review.json"
        selected_review = st.selectbox(
            "Existing reviews",
            options=review_options or [default_review],
            index=(review_options.index(default_review) if default_review in review_options else 0),
        )
        review_path = st.text_input("Review JSON path", value=selected_review)
    with col_b:
        review_out_dir = st.text_input("Review output dir", value="outputs/reviews")
        show_review_labels = st.checkbox("Show overlay labels", value=False)

    create_col, load_col, clear_col = st.columns(3)
    with create_col:
        if st.button("Create/overwrite draft review", type="primary"):
            try:
                policy = draft_review_policy(Path(detections_path))
                paths = write_review_policy(policy, Path(review_out_dir) / _safe_template_id(policy.source_image))
                st.session_state["review_policy"] = policy
                st.session_state["review_path"] = str(paths["review"])
                st.success(f"Draft review saved: {paths['review']}")
            except Exception as exc:  # pragma: no cover - UI guardrail
                st.error(f"Failed to draft review: {exc}")
                st.exception(exc)
    with load_col:
        if st.button("Load review JSON"):
            try:
                policy = load_review_policy(Path(review_path))
                st.session_state["review_policy"] = policy
                st.session_state["review_path"] = review_path
                st.success(f"Loaded review: {review_path}")
            except Exception as exc:  # pragma: no cover - UI guardrail
                st.error(f"Failed to load review: {exc}")
                st.exception(exc)
    with clear_col:
        if st.button("Clear loaded review"):
            st.session_state.pop("review_policy", None)
            st.session_state.pop("review_path", None)
            st.session_state["selected_bbox_ids"] = []
            st.rerun()

    policy = st.session_state.get("review_policy")
    if policy is not None:
        summary = review_summary(policy.labels)
        source_info = {
            "source_engine": policy.source_engine,
            "source_detections": str(policy.source_detections),
            "source_image": str(policy.source_image),
            "loaded_review": st.session_state.get("review_path", "<unsaved>"),
        }
        st.json(source_info)
        if policy.source_engine != "paddleocr":
            st.warning("현재 표시 중인 review가 PaddleOCR가 아닙니다. PaddleOCR detections를 선택한 뒤 `Create/overwrite draft review`를 눌러 새 review를 만드세요.")
        elif "projection" in str(policy.source_detections):
            st.warning("현재 source_detections 경로에 projection이 포함되어 있습니다. PaddleOCR 경로를 다시 로드하세요.")
        st.write(summary)
        image = Image.open(policy.source_image).convert("RGB")
        overlay = render_policy_overlay(image, policy, show_labels=show_review_labels)
        left, right = st.columns([1.35, 1])
        with left:
            st.markdown("### Canvas selection")
            st.caption("Click a bbox center or drag a rectangle over bbox centers, then apply a status button. Double-click clears Altair point selection.")
            chart, chart_rows = _policy_selection_chart(policy)
            event = st.altair_chart(chart, key="bbox_canvas", on_select="rerun")
            selected_ids = selected_ids_from_altair_event(event, chart_rows)
            if selected_ids:
                st.session_state["selected_bbox_ids"] = sorted(selected_ids)
            selected_ids = set(st.session_state.get("selected_bbox_ids", []))
            if selected_ids:
                st.success(f"Selected {len(selected_ids)} bbox(es): {', '.join(sorted(selected_ids)[:12])}{' ...' if len(selected_ids) > 12 else ''}")
            else:
                st.info("No bbox selected yet.")

            sel_col1, sel_col2, sel_col3, sel_col4 = st.columns(4)
            with sel_col1:
                if st.button("Selected -> use", disabled=not selected_ids):
                    rows = review_rows(policy)
                    st.session_state["review_policy"] = policy_from_edited_rows(policy, apply_status_to_ids(rows, selected_ids, "use"))
                    st.rerun()
            with sel_col2:
                if st.button("Selected -> keep", disabled=not selected_ids):
                    rows = review_rows(policy)
                    st.session_state["review_policy"] = policy_from_edited_rows(policy, apply_status_to_ids(rows, selected_ids, "keep"))
                    st.rerun()
            with sel_col3:
                if st.button("Selected -> ignore", disabled=not selected_ids):
                    rows = review_rows(policy)
                    st.session_state["review_policy"] = policy_from_edited_rows(policy, apply_status_to_ids(rows, selected_ids, "ignore"))
                    st.rerun()
            with sel_col4:
                if st.button("Clear selection"):
                    st.session_state["selected_bbox_ids"] = []
                    st.rerun()

            with st.expander("Static overlay preview", expanded=False):
                st.image(overlay, caption="Green=use, Blue=keep, Red=ignore", use_container_width=True)
        with right:
            st.markdown("### Editable labels")
            rows = review_rows(policy)
            edited = st.data_editor(
                rows,
                hide_index=True,
                use_container_width=True,
                height=540,
                column_config={
                    "status": st.column_config.SelectboxColumn("status", options=list(REVIEW_STATUSES), required=True),
                    "auto_type": st.column_config.SelectboxColumn("auto_type", options=list(AUTO_TYPES), required=True),
                    "locked": st.column_config.CheckboxColumn("locked"),
                },
                disabled=["id", "text", "confidence", "x", "y", "w", "h", "reason"],
                key="review_editor",
            )
            edited_rows = _editor_rows(edited)

            bulk_col1, bulk_col2, bulk_col3 = st.columns(3)
            with bulk_col1:
                if st.button("Low conf -> ignore"):
                    edited_rows = [
                        {**row, "status": "ignore"}
                        if row.get("confidence") is not None and float(row.get("confidence", 1.0)) < 0.35
                        else row
                        for row in edited_rows
                    ]
                    st.session_state["review_policy"] = policy_from_edited_rows(policy, edited_rows)
                    st.rerun()
            with bulk_col2:
                if st.button("Unknown -> keep"):
                    edited_rows = [{**row, "status": "keep"} if row.get("auto_type") == "unknown" else row for row in edited_rows]
                    st.session_state["review_policy"] = policy_from_edited_rows(policy, edited_rows)
                    st.rerun()
            with bulk_col3:
                if st.button("Values -> use"):
                    edited_rows = [
                        {**row, "status": "use"}
                        if row.get("auto_type") in {"field_value", "table_cell"}
                        else row
                        for row in edited_rows
                    ]
                    st.session_state["review_policy"] = policy_from_edited_rows(policy, edited_rows)
                    st.rerun()

            save_col, inpaint_col = st.columns(2)
            with save_col:
                if st.button("Save edited review"):
                    updated = policy_from_edited_rows(policy, edited_rows)
                    out_path = Path(st.session_state.get("review_path", review_path))
                    paths = write_review_policy(updated, out_path.parent)
                    st.session_state["review_policy"] = updated
                    st.session_state["review_path"] = str(paths["review"])
                    st.success(f"Saved: {paths['review']}")
            with inpaint_col:
                method = st.selectbox("Inpaint method", ["fill", "telea", "ns"], index=0)
                inpaint_out_dir = st.text_input("Inpaint out", value="outputs/inpaint_eval/paddleocr_reviewed_gui")
                if st.button("Inpaint use-only"):
                    try:
                        updated = policy_from_edited_rows(policy, edited_rows)
                        out_path = Path(st.session_state.get("review_path", review_path))
                        paths = write_review_policy(updated, out_path.parent)
                        result = inpaint_from_review_policy(
                            paths["review"],
                            InpaintConfig(method=method, mask_shape="bbox", padding=2, dilation=1, radius=3.0),
                        )
                        inpaint_paths = write_inpaint_result(result, Path(inpaint_out_dir) / _safe_template_id(result.source_image) / method)
                        st.success(f"Inpainted {result.detection_count} use-region(s), mask_ratio={result.mask_ratio:.4f}")
                        st.image(Image.open(inpaint_paths["comparison"]), caption=str(inpaint_paths["comparison"]), use_container_width=True)
                    except Exception as exc:  # pragma: no cover - UI guardrail
                        st.error(f"Failed to inpaint reviewed bboxes: {exc}")
                        st.exception(exc)
