#!/usr/bin/env python3
"""Restore printed-document styles after semantic authoring refinement."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from datafactory.style_remap import remap_styles_from_previous


PRINTED_PIPELINE_DOC_IDS = (
    "ADM-04", "COL-03", "COL-05", "CRD-01", "CRD-02", "FIN-01", "ID-03",
    "QC-01", "QC-02", "RPT-01", "RPT-07", "SEC-01", "TRD-01", "TRD-02",
    "TRD-05", "TRD-06", "TRD-07", "FIN-08", "MED-04", "MED-05", "TRD-03",
    "TRD-04",
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _current_authoring_dirs() -> dict[str, Path]:
    result: dict[str, Path] = {}
    for schema_path in (ROOT / "workbench" / "documents").glob("*/authoring/schema.json"):
        schema = _read(schema_path)
        doc_id = str(schema.get("doc_id") or "").strip()
        if doc_id:
            result[doc_id] = schema_path.parent
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-root", type=Path, required=True, help="Backup root containing <DOC-ID>_authoring directories")
    parser.add_argument("--apply", action="store_true", help="Write remapped schema.json and stylesheet.json; default is audit-only")
    parser.add_argument("--report", type=Path, default=ROOT / "outputs" / "printed_stylesheet_remap_report.json")
    parser.add_argument("doc_ids", nargs="*", default=PRINTED_PIPELINE_DOC_IDS)
    args = parser.parse_args()

    previous_root = args.previous_root.resolve()
    current_dirs = _current_authoring_dirs()
    selected = list(dict.fromkeys(args.doc_ids or PRINTED_PIPELINE_DOC_IDS))
    timestamp = datetime.now(timezone.utc).isoformat()
    backup_root: Path | None = None
    if args.apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_root = ROOT / ".bin" / "backups" / f"printed_stylesheet_remap_apply_{stamp}"

    rows: list[dict[str, Any]] = []
    for doc_id in selected:
        current_dir = current_dirs.get(doc_id)
        previous_dir = previous_root / f"{doc_id}_authoring"
        if current_dir is None or not previous_dir.exists():
            raise FileNotFoundError(f"missing authoring bundle: doc={doc_id}, current={current_dir}, previous={previous_dir}")
        current_schema_path = current_dir / "schema.json"
        current_stylesheet_path = current_dir / "stylesheet.json"
        current_schema = _read(current_schema_path)
        current_stylesheet = _read(current_stylesheet_path)
        previous_schema = _read(previous_dir / "schema.json")
        previous_stylesheet = _read(previous_dir / "stylesheet.json")
        schema, stylesheet, report = remap_styles_from_previous(
            current_schema,
            current_stylesheet,
            previous_schema,
            previous_stylesheet,
        )
        schema["updated_at"] = timestamp
        stylesheet["updated_at"] = timestamp
        stylesheet["source"] = {
            "kind": "restored_previous_authoring_styles",
            "mapping_priority": ["bbox_anchor", "field_id", "style_class"],
        }
        if args.apply:
            assert backup_root is not None
            backup_dir = backup_root / doc_id
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current_schema_path, backup_dir / "schema.json")
            shutil.copy2(current_stylesheet_path, backup_dir / "stylesheet.json")
            _write(current_schema_path, schema)
            _write(current_stylesheet_path, stylesheet)
        rows.append({"docId": doc_id, **report})

    payload = {
        "schema_version": 1,
        "created_at": timestamp,
        "applied": bool(args.apply),
        "previousRoot": str(previous_root),
        "backupRoot": str(backup_root) if backup_root else "",
        "summary": {
            "documents": len(rows),
            "fields": sum(row["fields"] for row in rows),
            "renderedFields": sum(row["renderedFields"] for row in rows),
            "changedStyleReferences": sum(row["changedStyleReferences"] for row in rows),
            "restoredRenderPolicies": sum(row["restoredRenderPolicies"] for row in rows),
            "unresolvedRendered": sum(len(row["unresolvedRendered"]) for row in rows),
            "unresolvedHidden": sum(len(row["unresolvedHidden"]) for row in rows),
        },
        "documents": rows,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    _write(args.report, payload)
    print(json.dumps(payload["summary"], ensure_ascii=False))
    if backup_root:
        print(f"backup={backup_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
