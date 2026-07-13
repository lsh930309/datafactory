from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .policy import load_review_policy

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PII_POLICY_PATH = ROOT / "workbench" / "library_sample_pii_policy.json"
LIBRARY_SAMPLE_DOMAINS = ("금융", "제조", "의료", "무역", "보험", "공공", "회계", "건설")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}


def load_pii_policy(path: Path | None = None) -> dict[str, Any]:
    policy_path = path or DEFAULT_PII_POLICY_PATH
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"PII policy must be a JSON object: {policy_path}")
    patterns = payload.get("include_key_patterns")
    if not isinstance(patterns, list):
        raise ValueError("PII policy include_key_patterns must be a list")
    for pattern in patterns:
        re.compile(str(pattern))
    return payload


def semantic_leaf_paths(value: Any, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    if isinstance(value, dict):
        paths: list[tuple[str, ...]] = []
        for key, child in value.items():
            paths.extend(semantic_leaf_paths(child, (*prefix, str(key))))
        return paths
    return [prefix] if prefix else []


def normalize_privacy(value: Any) -> dict[str, list[str]]:
    raw = value if isinstance(value, dict) else {}
    includes = _unique_strings(raw.get("include_keys"))
    excludes = _unique_strings(raw.get("exclude_keys"))
    return {"include_keys": includes, "exclude_keys": excludes}


def fields_with_generators(fields: Iterable[dict[str, Any]], faker_profile: Any) -> list[dict[str, Any]]:
    profile = faker_profile if isinstance(faker_profile, dict) else {}
    generators = profile.get("field_generators") if isinstance(profile.get("field_generators"), dict) else {}
    output: list[dict[str, Any]] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        field_id = str(field.get("field_id") or "")
        output.append({**field, "generator": generators.get(field_id) or field.get("generator") or field.get("faker_rule") or ""})
    return output


def validate_privacy(semantic_schema: dict[str, Any], privacy: Any) -> dict[str, Any]:
    normalized = normalize_privacy(privacy)
    keys = _unique_strings(path[-1] for path in semantic_leaf_paths(semantic_schema))
    known = set(keys)
    include = set(normalized["include_keys"])
    exclude = set(normalized["exclude_keys"])
    errors: list[dict[str, Any]] = []
    for key in sorted((include | exclude) - known):
        errors.append({"code": "privacy_unknown_key", "key": key, "message": f"semantic schema에 없는 PII key입니다: {key}"})
    for key in sorted(include & exclude):
        errors.append({"code": "privacy_conflicting_override", "key": key, "message": f"PII include/exclude에 동시에 지정되었습니다: {key}"})
    return {
        "ready": not errors,
        "errors": errors,
        "warnings": [],
        "privacy": normalized,
        "summary": {"errorCount": len(errors), "warningCount": 0, "semanticKeyCount": len(keys)},
    }


def privacy_payload(
    semantic_schema: dict[str, Any],
    *,
    fields: Iterable[dict[str, Any]] | None = None,
    privacy: Any = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_pii_policy()
    normalized = normalize_privacy(privacy)
    validation = validate_privacy(semantic_schema, normalized)
    field_metadata = _field_metadata_by_leaf(fields or [])
    leaf_keys = _unique_strings(path[-1] for path in semantic_leaf_paths(semantic_schema))
    defaults: list[str] = []
    reasons: dict[str, list[str]] = {}
    exact = {str(value).strip() for value in policy.get("include_exact_keys", []) if str(value).strip()}
    patterns = [re.compile(str(value)) for value in policy.get("include_key_patterns", [])]
    value_types = {str(value).strip() for value in policy.get("include_value_types", []) if str(value).strip()}
    generators = {str(value).strip() for value in policy.get("include_generators", []) if str(value).strip()}
    for key in leaf_keys:
        match_key = re.sub(r"\[\d+\]$", "", key)
        key_reasons: list[str] = []
        if match_key in exact:
            key_reasons.append("exact_key")
        if any(pattern.search(match_key) for pattern in patterns):
            key_reasons.append("key_pattern")
        metadata = field_metadata.get(key, {})
        if metadata.get("value_types", set()) & value_types:
            key_reasons.append("value_type")
        if metadata.get("generators", set()) & generators:
            key_reasons.append("generator")
        if key_reasons:
            defaults.append(key)
            reasons[key] = key_reasons
    include = set(normalized["include_keys"])
    exclude = set(normalized["exclude_keys"])
    resolved = [key for key in leaf_keys if (key in set(defaults) or key in include) and key not in exclude]
    field_states = {
        key: {
            "mode": "include" if key in include else ("exclude" if key in exclude else "inherit"),
            "defaultIncluded": key in set(defaults),
            "resolvedIncluded": key in set(resolved),
            "reasons": reasons.get(key, []),
        }
        for key in leaf_keys
    }
    return {
        "schemaVersion": int(policy.get("schema_version") or 1),
        "defaultKeys": defaults,
        "resolvedKeys": resolved,
        "includeKeys": normalized["include_keys"],
        "excludeKeys": normalized["exclude_keys"],
        "fieldStates": field_states,
        "validation": validation,
    }


def resolve_pii_keys(
    semantic_schema: dict[str, Any],
    *,
    fields: Iterable[dict[str, Any]] | None = None,
    privacy: Any = None,
    policy: dict[str, Any] | None = None,
) -> list[str]:
    payload = privacy_payload(semantic_schema, fields=fields, privacy=privacy, policy=policy)
    if payload["validation"]["errors"]:
        first = payload["validation"]["errors"][0]
        raise ValueError(f"privacy validation failed: {first['code']} ({first.get('key', '')})")
    return list(payload["resolvedKeys"])


def list_cleanroom_pages(pages_dir: Path) -> list[Path]:
    if not pages_dir.exists() or not pages_dir.is_dir():
        return []
    return sorted(path.resolve() for path in pages_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)


def cleanroom_annotation_path(document_dir: Path) -> Path:
    return document_dir / "library_sample" / "annotation.json"


def load_cleanroom_annotation(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"cleanroom annotation must be a JSON object: {path}")
    return payload


def save_cleanroom_annotation(
    path: Path,
    payload: dict[str, Any],
    *,
    pages_dir: Path,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pages = list_cleanroom_pages(pages_dir)
    allowed_pages = {page.resolve() for page in pages}
    source_image = _resolve_path(payload.get("sourceImage") or payload.get("source_image"), base=path.parent)
    if source_image not in allowed_pages:
        raise ValueError("sourceImage must be one of the generated cleanroom pages")
    review_path = _resolve_path(payload.get("reviewPath") or payload.get("review_path"), base=path.parent)
    review = load_review_policy(review_path)
    if review.source_image.resolve() != source_image:
        raise ValueError("review source_image must match the selected cleanroom page")
    use_labels = {label.id: label for label in review.labels if label.status == "use"}
    raw_fields = payload.get("fields")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise ValueError("at least one cleanroom annotation field is required")
    fields: list[dict[str, str]] = []
    keys: set[str] = set()
    bbox_ids: set[str] = set()
    for index, raw in enumerate(raw_fields):
        if not isinstance(raw, dict):
            raise ValueError(f"fields[{index}] must be an object")
        key = str(raw.get("key") or "").strip()
        bbox_id = str(raw.get("bboxLabelId") or raw.get("bbox_label_id") or "").strip()
        if not key:
            raise ValueError(f"fields[{index}].key is required")
        if key in keys:
            raise ValueError(f"duplicate cleanroom annotation key: {key}")
        if bbox_id not in use_labels:
            raise ValueError(f"fields[{index}].bboxLabelId must reference a use label: {bbox_id}")
        if bbox_id in bbox_ids:
            raise ValueError(f"duplicate cleanroom bboxLabelId: {bbox_id}")
        keys.add(key)
        bbox_ids.add(bbox_id)
        value = str(raw.get("value") if raw.get("value") is not None else use_labels[bbox_id].text)
        fields.append({"key": key, "value": value, "bbox_label_id": bbox_id})
    missing = sorted(set(use_labels) - bbox_ids)
    if missing:
        raise ValueError(f"all use labels must be mapped to flat fields; missing: {missing[:20]}")
    schema = {field["key"]: "" for field in fields}
    privacy = normalize_privacy(payload.get("privacy"))
    pii = privacy_payload(schema, privacy=privacy, policy=policy)
    if pii["validation"]["errors"]:
        raise ValueError(f"privacy validation failed: {pii['validation']['errors'][0]['code']}")
    saved = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_image": str(source_image),
        "review_path": str(review_path),
        "fields": fields,
        "privacy": privacy,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        history = path.parent / "history"
        history.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        (history / f"annotation_{stamp}.json").write_bytes(path.read_bytes())
    _write_json_atomic(path, saved)
    return saved


def build_cleanroom_artifacts(annotation_path: Path, *, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    annotation = load_cleanroom_annotation(annotation_path)
    if annotation is None:
        raise ValueError("cleanroom library-sample annotation is required")
    source_image = _resolve_path(annotation.get("source_image"), base=annotation_path.parent)
    review_path = _resolve_path(annotation.get("review_path"), base=annotation_path.parent)
    if not source_image.exists():
        raise ValueError(f"cleanroom source image not found: {source_image}")
    review = load_review_policy(review_path)
    if review.source_image.resolve() != source_image:
        raise ValueError("review source_image must match the cleanroom annotation source_image")
    use_labels = {label.id: label for label in review.labels if label.status == "use"}
    raw_fields = annotation.get("fields") if isinstance(annotation.get("fields"), list) else []
    if not raw_fields:
        raise ValueError("cleanroom annotation has no fields")
    schema: dict[str, str] = {}
    gt: dict[str, str] = {}
    bbox: dict[str, dict[str, float]] = {}
    used_labels: set[str] = set()
    for raw in raw_fields:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("key") or "").strip()
        bbox_id = str(raw.get("bbox_label_id") or raw.get("bboxLabelId") or "").strip()
        if not key or key in schema:
            raise ValueError(f"invalid or duplicate cleanroom annotation key: {key}")
        label = use_labels.get(bbox_id)
        if label is None or bbox_id in used_labels:
            raise ValueError(f"invalid or duplicate cleanroom annotation bbox label: {bbox_id}")
        used_labels.add(bbox_id)
        value = str(raw.get("value") if raw.get("value") is not None else label.text)
        schema[key] = ""
        gt[key] = value
        if value.strip():
            bbox[key] = {
                "l": round(max(0.0, min(1.0, label.bbox.x / max(1, review.image_width))), 4),
                "t": round(max(0.0, min(1.0, label.bbox.y / max(1, review.image_height))), 4),
                "r": round(max(0.0, min(1.0, label.bbox.right / max(1, review.image_width))), 4),
                "b": round(max(0.0, min(1.0, label.bbox.bottom / max(1, review.image_height))), 4),
            }
    if used_labels != set(use_labels):
        raise ValueError("all use labels must be represented in cleanroom annotation fields")
    pii_keys = resolve_pii_keys(schema, privacy=annotation.get("privacy"), policy=policy)
    return {
        "source_image": source_image,
        "review_path": review_path,
        "schema": schema,
        "gt": gt,
        "bbox": bbox,
        "pii_keys": pii_keys,
        "privacy": normalize_privacy(annotation.get("privacy")),
    }


def _field_metadata_by_leaf(fields: Iterable[dict[str, Any]]) -> dict[str, dict[str, set[str]]]:
    metadata: dict[str, dict[str, set[str]]] = {}
    for field in fields:
        if not isinstance(field, dict):
            continue
        raw_path = field.get("semantic_path") or field.get("key_path")
        if isinstance(raw_path, list):
            parts = [str(part).strip() for part in raw_path if str(part).strip()]
        elif isinstance(raw_path, str):
            parts = [part.strip() for part in re.split(r"[/.]", raw_path) if part.strip()]
        else:
            parts = []
        if not parts:
            continue
        leaf = parts[-1]
        value_type = str(field.get("value_type") or "").strip()
        generator = str(field.get("generator") or field.get("faker_rule") or "").strip()
        target = metadata.setdefault(leaf, {"value_types": set(), "generators": set()})
        if value_type:
            target["value_types"].add(value_type)
        if generator:
            target["generators"].add(generator)
    return metadata


def _unique_strings(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, Iterable):
        return []
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def _resolve_path(value: Any, *, base: Path) -> Path:
    if not value:
        raise ValueError("required path is missing")
    path = Path(str(value))
    if not path.is_absolute():
        root_candidate = (ROOT / path).resolve()
        path = root_candidate if root_candidate.exists() else (base / path).resolve()
    return path.resolve()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
