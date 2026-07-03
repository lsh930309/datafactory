from __future__ import annotations

import json
import zipfile
from pathlib import Path

from datafactory.final_results_export import (
    _semantic_bbox_payload,
    _semantic_values_payload,
    _write_manifest_xlsx,
)


def test_semantic_values_payload_clones_schema_without_metadata() -> None:
    schema = {
        "회사이름": "",
        "주주명[0]": "",
        "주주명[1]": "",
    }
    field_paths = {
        "account_name": "회사이름",
        "shareholder_1_name": "주주명[0]",
        "shareholder_2_name": "주주명[1]",
    }
    values = {
        "account_name": "가나다상사",
        "shareholder_1_name": "홍길동",
        "shareholder_2_name": "김철수",
    }

    assert _semantic_values_payload(schema, field_paths, values) == {
        "회사이름": "가나다상사",
        "주주명[0]": "홍길동",
        "주주명[1]": "김철수",
    }


def test_semantic_bbox_payload_rounds_to_four_decimals_and_has_only_ltrb() -> None:
    schema = {"성명": ""}
    field_paths = {"name": "성명"}
    payload = {
        "image": {"width": 1000, "height": 2000},
        "annotations": [
            {"field": "name", "text": "홍길동", "bbox": [123, 456, 78, 90]},
        ],
    }

    result = _semantic_bbox_payload(schema, field_paths, payload)

    assert result == {"성명": {"l": 0.123, "t": 0.228, "r": 0.201, "b": 0.273}}


def test_semantic_bbox_payload_omits_fields_without_rendered_annotation() -> None:
    schema = {"성명": "", "미렌더링필드": ""}
    field_paths = {"name": "성명", "empty": "미렌더링필드"}
    payload = {
        "image": {"width": 1000, "height": 2000},
        "annotations": [
            {"field": "name", "bbox": [10, 20, 30, 40]},
        ],
    }

    result = _semantic_bbox_payload(schema, field_paths, payload)

    assert result == {"성명": {"l": 0.01, "t": 0.01, "r": 0.04, "b": 0.03}}


def test_write_manifest_xlsx_creates_valid_zip_parts(tmp_path: Path) -> None:
    path = tmp_path / "manifest.xlsx"
    rows = [
        {
            "domain": "금융",
            "index": 1,
            "docId": "ID-03",
            "title": "주주명부",
            "documentTypeLabel": "정형양식",
            "storedFeasibilityLabel": "작업 가능",
            "outputMode": "pipeline",
            "sampleCount": 1,
            "outputType": "jpg+json+bbox",
            "status": "OK",
            "outputDir": "outputs/results/금융/ID-03_주주명부",
            "message": "generated",
        }
    ]
    summary = {
        "generatedAt": "2026-07-03T00:00:00+00:00",
        "scopeEntryCount": 1,
        "uniqueDocumentCount": 1,
        "pipelineScopeCount": 1,
        "cleanroomScopeCount": 0,
        "errorCount": 0,
    }

    _write_manifest_xlsx(path, rows, summary)

    assert path.exists()
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        assert "[Content_Types].xml" in names
        assert "xl/workbook.xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        assert "xl/sharedStrings.xml" in names
        shared = archive.read("xl/sharedStrings.xml").decode("utf-8")
        assert "주주명부" in shared
        assert "\x00" not in shared
