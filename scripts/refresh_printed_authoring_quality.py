#!/usr/bin/env python3
"""Re-infer and apply printed-document authoring bundles with strict quality gates.

This deliberately excludes registry documents whose writing method is ``수기``.
Each document runs through the workbench's schema pass, faker pass, validation
and repair pass. Final files are saved only after the draft contract succeeds;
the normal authoring backup hook protects the previous JSON bundle.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from datafactory.registry import load_registry
from datafactory.web_api import apply_authoring_agent_drafts_payload, authoring_agent_run_payload


LEGACY_PRINTED_DOC_IDS = (
    "ADM-04", "COL-03", "COL-05", "CRD-01", "CRD-02", "FIN-01", "ID-03",
    "QC-01", "QC-02", "RPT-01", "RPT-07", "SEC-01", "TRD-01", "TRD-02",
    "TRD-05", "TRD-06", "TRD-07",
)
MODERN_PRINTED_DOC_IDS = ("FIN-08", "MED-04", "MED-05", "TRD-03", "TRD-04")

QUALITY_INSTRUCTION = """이번 작업은 인쇄체 authoring 품질 재구축이다.
1. 전체 원본/인페인트 이미지와 use bbox를 source of truth로 삼아 실제 문서 KIE 구조를 반영한 계층형 primary semantic_schema를 만든다. 메타데이터는 넣지 않는다.
2. 모든 use bbox를 빠짐없이 binding한다. 의미가 불명확하면 생략하지 말고 검토필요 leaf로 연결한다.
3. 기존 stylesheet의 검증된 폰트/정렬/크기는 가능한 한 보존하고, 이번 작업의 중심을 schema와 faker 품질에 둔다.
4. 열린 scalar pool은 20개 이상, 상관관계 record pool은 12개 이상으로 만들고, 작은 폐쇄형 선택지는 pool_policies에 근거를 명시한다.
5. 날짜는 작업일 이후가 될 수 없고 현실의 선후관계를 지켜야 한다. 사업자등록번호는 checksum이 맞아야 하며 주민등록번호는 유효 생년월일과 뒷자리 마스킹을 사용한다.
6. 금리/비율/금액/합계/연령/체크박스/기관-질병-코드 등 서로 의존하는 값은 지원 constraint로 명시한다. 독립 생성으로 현실에서 불가능한 조합이 나오지 않게 한다.
7. 값 위치에 정적 단위가 인쇄되어 있으면 faker 값에 단위를 중복하지 않는다.
8. FIN-01과 QC-01의 다중 페이지 완결성은 이번 차수에서 확장하지 않는다. 현재 페이지의 KIE와 값 품질만 개선하고 uncertainty_report에 페이지 제한을 명시한다.
"""


def _refresh(doc_id: str, *, apply: bool) -> dict[str, Any]:
    run = authoring_agent_run_payload(
        {
            "docId": doc_id,
            "instruction": QUALITY_INSTRUCTION,
            "options": {
                "reasoningEffort": "medium",
                "fastMode": False,
                "scalarPoolMinSize": 20,
                "recordPoolMinSize": 12,
                "asOfDate": date.today().isoformat(),
            },
        },
        async_run=False,
    )
    result: dict[str, Any] = {
        "docId": doc_id,
        "status": run.get("status"),
        "jobPath": run.get("jobPath"),
        "requestPath": run.get("requestPath"),
        "validation": run.get("validation"),
        "repairSummary": run.get("repairSummary"),
    }
    if run.get("status") != "succeeded":
        result["error"] = run.get("error") or "agent inference failed"
        return result
    if not apply:
        result["status"] = "ready_for_review"
        return result
    applied = apply_authoring_agent_drafts_payload({"docId": doc_id, "requestPath": run.get("requestPath")})
    result.update(
        {
            "status": "applied",
            "paths": applied.get("paths"),
            "consistency": applied.get("consistency"),
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("doc_ids", nargs="*", help="Explicit registry doc IDs")
    parser.add_argument("--all", action="store_true", help="Run legacy and modern printed pipeline documents")
    parser.add_argument("--apply", action="store_true", help="Apply validated drafts after inference; default is review-only")
    parser.add_argument("--modern", action="store_true", help="Include the modern printed audit/enrichment set")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--report", type=Path, default=ROOT / "outputs" / "authoring_quality_refresh_report.json")
    args = parser.parse_args()

    selected = list(args.doc_ids)
    if args.all:
        selected = [*LEGACY_PRINTED_DOC_IDS, *(MODERN_PRINTED_DOC_IDS if args.all or args.modern else ())]
    elif args.modern:
        selected.extend(MODERN_PRINTED_DOC_IDS)
    if not selected:
        parser.error("provide doc_ids or --all")
    selected = list(dict.fromkeys(selected))

    registry = load_registry()
    invalid = [doc_id for doc_id in selected if doc_id not in registry.documents]
    handwriting = [doc_id for doc_id in selected if doc_id in registry.documents and str(registry.documents[doc_id].writing_method).strip() == "수기"]
    if invalid or handwriting:
        raise SystemExit(f"invalid={invalid}; handwriting is excluded={handwriting}")

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(3, args.workers))) as executor:
        futures = {executor.submit(_refresh, doc_id, apply=args.apply): doc_id for doc_id in selected}
        for future in as_completed(futures):
            doc_id = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # preserve other completed documents
                result = {"docId": doc_id, "status": "failed", "error": str(exc)}
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selected": selected,
        "applied": sum(item.get("status") == "applied" for item in results),
        "ready_for_review": sum(item.get("status") == "ready_for_review" for item in results),
        "failed": sum(item.get("status") not in {"applied", "ready_for_review"} for item in results),
        "results": sorted(results, key=lambda item: selected.index(str(item.get("docId")))),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if payload["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
