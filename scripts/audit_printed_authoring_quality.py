#!/usr/bin/env python3
"""Audit printed authoring bundles against production schema/faker contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from datafactory.registry import load_registry
from datafactory.web_api import _authoring_bundle_consistency, _validate_faker_profile_contract
from datafactory.workbench import list_work_items


PRINTED_PIPELINE_DOC_IDS = (
    "ADM-04", "COL-03", "COL-05", "CRD-01", "CRD-02", "FIN-01", "ID-03",
    "QC-01", "QC-02", "RPT-01", "RPT-07", "SEC-01", "TRD-01", "TRD-02",
    "TRD-05", "TRD-06", "TRD-07", "FIN-08", "MED-04", "MED-05", "TRD-03",
    "TRD-04",
)


def _max_depth(value: Any, depth: int = 0) -> int:
    if not isinstance(value, dict) or not value:
        return depth
    return max(_max_depth(child, depth + 1) for child in value.values())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("doc_ids", nargs="*", help="Printed document IDs; default is the 22 supported printed-pipeline documents")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs" / "printed_authoring_quality_audit.json")
    args = parser.parse_args()

    registry = load_registry()
    requested = set(args.doc_ids or PRINTED_PIPELINE_DOC_IDS)
    rows: list[dict[str, Any]] = []
    for item in list_work_items(registry=registry):
        doc_id = str(item.get("docId") or "")
        doc = registry.documents.get(doc_id)
        if not doc or str(doc.writing_method).strip() == "수기" or doc_id not in requested:
            continue
        paths = [item.get("latestAuthoringSchema"), item.get("latestAuthoringFakerProfile")]
        if not all(paths):
            continue
        schema = json.loads(Path(str(paths[0])).read_text(encoding="utf-8"))
        faker = json.loads(Path(str(paths[1])).read_text(encoding="utf-8"))
        consistency = _authoring_bundle_consistency(schema, faker, strict_review_coverage=True)
        pool_errors = _validate_faker_profile_contract(
            faker,
            schema.get("fields") if isinstance(schema.get("fields"), list) else [],
            min_pool_size=20,
            min_record_pool_size=12,
        )
        semantic_schema = schema.get("semantic_schema") if isinstance(schema.get("semantic_schema"), dict) else {}
        rows.append(
            {
                "docId": doc_id,
                "title": doc.title,
                "ready": consistency["ready"] and not pool_errors,
                "hierarchyDepth": _max_depth(semantic_schema),
                "consistency": consistency,
                "poolErrors": pool_errors,
            }
        )
    missing = sorted(requested - {row["docId"] for row in rows})
    payload = {
        "schema_version": 1,
        "summary": {
            "documents": len(rows),
            "ready": sum(row["ready"] for row in rows),
            "failed": sum(not row["ready"] for row in rows),
            "missing": missing,
        },
        "documents": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    return 0 if not missing and payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
