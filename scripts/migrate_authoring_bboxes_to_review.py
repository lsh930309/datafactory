#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from datafactory.authoring import migrate_authoring_schema_bboxes_to_review  # noqa: E402
from datafactory.registry import load_registry  # noqa: E402
from datafactory.workbench import document_dir, update_manifest_artifact  # noqa: E402


def _manifest_review_path(doc_root: Path) -> Path | None:
    manifest_path = doc_root / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            value = (manifest.get("artifacts") or {}).get("review")
            if value:
                path = Path(str(value))
                if not path.is_absolute():
                    path = ROOT / path
                if path.exists():
                    return path
        except Exception:
            pass
    candidates = [path for path in (doc_root / "review").glob("**/review.json") if path.exists()]
    if candidates:
        return sorted(candidates, key=lambda path: (path.stat().st_mtime, str(path)))[-1]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Move legacy authoring schema bboxes into canonical review.json files.")
    parser.add_argument("--doc-id", action="append", dest="doc_ids", help="Limit migration to one or more docIds.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    args = parser.parse_args()

    registry = load_registry()
    requested = set(args.doc_ids or [])
    results = []
    for doc in registry.documents.values():
        if requested and doc.doc_id not in requested:
            continue
        doc_root = document_dir(doc)
        schema_path = doc_root / "authoring" / "schema.json"
        if not schema_path.exists():
            continue
        review_path = _manifest_review_path(doc_root) or (doc_root / "review" / "authoring_migrated" / "review.json")
        result = migrate_authoring_schema_bboxes_to_review(schema_path, review_path=review_path)
        if result.get("review"):
            update_manifest_artifact(doc.doc_id, "review", result["review"], registry=registry)
        update_manifest_artifact(doc.doc_id, "authoring", schema_path, registry=registry)
        result = {"docId": doc.doc_id, "title": doc.title, **result}
        results.append(result)

    summary = {"document_count": len(results), "migrated_bbox_count": sum(int(item.get("migrated") or 0) for item in results), "documents": results}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"documents={summary['document_count']} migrated_bboxes={summary['migrated_bbox_count']}")
        for item in results:
            print(f"- {item['docId']} {item['title']}: migrated={item.get('migrated')} review={item.get('review')}")


if __name__ == "__main__":
    main()
