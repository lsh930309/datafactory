from __future__ import annotations

import json
import zipfile
from pathlib import Path

from datafactory import final_results_export as fre
from datafactory.final_results_export import (
    _field_semantic_paths,
    _merge_schema_values,
    _primary_schema_payload,
    _resolve_scope_entries,
    _semantic_bbox_payload,
    _summary,
    _write_manifest_xlsx,
)
from datafactory.registry import RegistryData, RegistryDocument


def test_resolve_scope_entries_defaults_to_registry_first_priority() -> None:
    registry = RegistryData(
        documents={"DOC-1": RegistryDocument(doc_id="DOC-1", title="테스트문서")},
        workflows={},
        bindings=[],
        source_path=Path("registry.xlsx"),
        first_priority_scope_entries=(("금융", "DOC-1"),),
    )

    assert _resolve_scope_entries(None, registry=registry) == (("금융", "DOC-1"),)


def test_resolve_scope_entries_accepts_selected_group_scope_and_deduplicates() -> None:
    registry = RegistryData(
        documents={
            "DOC-1": RegistryDocument(doc_id="DOC-1", title="테스트문서"),
            "DOC-2": RegistryDocument(doc_id="DOC-2", title="다른문서"),
        },
        workflows={},
        bindings=[],
        source_path=Path("registry.xlsx"),
    )

    result = _resolve_scope_entries(
        [
            {"domain": "금융", "docId": "DOC-1"},
            {"domain": "금융", "docId": "DOC-1"},
            {"domain": "제조", "doc_id": "DOC-2"},
            {"domain": "금융", "docId": "MISSING"},
        ],
        registry=registry,
    )

    assert result == (("금융", "DOC-1"), ("제조", "DOC-2"))


def test_resolve_output_mode_allows_handwriting_temporary_printed_export() -> None:
    item = {
        "writingMethod": "수기",
        "latestAuthoringSchema": "schema.json",
        "latestAuthoringStylesheet": "stylesheet.json",
        "latestAuthoringFakerProfile": "faker_profile.json",
    }

    assert fre._resolve_output_mode(item, render_handwriting_as_printed=True) == "pipeline"
    try:
        fre._resolve_output_mode(item)
    except ValueError as exc:
        assert "no accepted handwriting scans" in str(exc)
    else:
        raise AssertionError("expected handwriting document without accepted scans to require scan intake")


def test_resolve_output_mode_prefers_cleanroom_for_non_pipeline_scope() -> None:
    item = {
        "writingMethod": "수기",
        "latestAuthoringSchema": "schema.json",
        "latestAuthoringStylesheet": "stylesheet.json",
        "latestAuthoringFakerProfile": "faker_profile.json",
        "latestCleanroomPdf": "cleanroom.pdf",
    }

    assert fre._resolve_output_mode(item, render_handwriting_as_printed=True, prefer_cleanroom=True) == "cleanroom"


def test_resolve_output_mode_uses_cleanroom_for_handwriting_without_authoring() -> None:
    item = {
        "registry": {"writingMethod": "수기"},
        "latestCleanroomPdf": "cleanroom.pdf",
    }

    assert fre._resolve_output_mode(item, render_handwriting_as_printed=True) == "cleanroom"


def test_primary_schema_payload_uses_only_primary_schema_leaves() -> None:
    semantic_schema = {
        "회사이름": "",
        "담보": {"종류": ""},
    }
    field_paths = {
        "account_name": "회사이름",
        "owner": "대표자명",
        "collateral_type": "담보/종류",
    }

    assert _primary_schema_payload(semantic_schema, field_paths) == {
        "회사이름": "",
        "담보": {"종류": ""},
    }


def test_final_export_prefers_authoring_semantic_paths_over_flat_export_labels() -> None:
    fields = [
        {
            "field_id": "patient_name",
            "label": "환자의 성명",
            "semantic_path": ["환자", "성명"],
            "export": {"json_path": "환자의 성명", "csv_column": "환자의 성명"},
        },
        {
            "field_id": "issue_year",
            "label": "발급일자 년",
            "semantic_path": ["확인", "발급일자", "년"],
            "export": {"json_path": "발급일자 년", "csv_column": "발급일자 년"},
        },
        {
            "field_id": "display_period",
            "label": "입원·퇴원연월일",
            "semantic_path": ["진료내용", "입원퇴원연월일", "표시문구"],
            "export": {"json_path": "진료내용/입원퇴원연월일/표시문구", "include": False},
        },
    ]

    semantic_schema = {"환자": {"성명": ""}, "확인": {"발급일자": {"년": ""}}}

    assert _field_semantic_paths(fields, semantic_schema=semantic_schema) == {
        "patient_name": "환자/성명",
        "issue_year": "확인/발급일자/년",
    }


def test_merge_schema_values_does_not_append_flat_label_duplicates() -> None:
    schema = {"환자": {"성명": ""}, "확인": {"발급일자": {"년": ""}}}
    semantic_values = {
        "환자": {"성명": "홍길동"},
        "확인": {"발급일자": {"년": "2026"}},
        "환자의 성명": "루트로 새면 안 됨",
    }

    assert _merge_schema_values(schema, semantic_values) == {
        "환자": {"성명": "홍길동"},
        "확인": {"발급일자": {"년": "2026"}},
    }


def test_field_semantic_paths_rejects_unmapped_primary_schema_leaf() -> None:
    fields = [
        {"field_id": "patient_name", "semantic_path": ["환자", "성명"], "export": {"include": True}},
    ]
    semantic_schema = {"환자": {"성명": "", "주민등록번호": ""}}

    try:
        _field_semantic_paths(fields, semantic_schema=semantic_schema)
    except ValueError as exc:
        assert "unmapped leaves" in str(exc)
    else:
        raise AssertionError("expected unmapped primary schema leaf to fail")


def test_field_semantic_paths_rejects_export_label_fallback() -> None:
    fields = [
        {"field_id": "patient_name", "label": "환자의 성명", "export": {"json_path": "환자의 성명"}},
    ]
    semantic_schema = {"환자": {"성명": ""}}

    try:
        _field_semantic_paths(fields, semantic_schema=semantic_schema)
    except ValueError as exc:
        assert "semantic_path" in str(exc)
    else:
        raise AssertionError("expected missing semantic_path to fail")


def test_field_semantic_paths_rejects_duplicate_primary_schema_mapping() -> None:
    fields = [
        {"field_id": "patient_name_1", "semantic_path": ["환자", "성명"]},
        {"field_id": "patient_name_2", "semantic_path": ["환자", "성명"]},
    ]
    semantic_schema = {"환자": {"성명": ""}}

    try:
        _field_semantic_paths(fields, semantic_schema=semantic_schema)
    except ValueError as exc:
        assert "duplicate field semantic_path" in str(exc)
    else:
        raise AssertionError("expected duplicate semantic mapping to fail")


def test_summary_counts_primary_schema_once_per_pipeline_scope() -> None:
    rows = [
        {"docId": "DOC-1", "status": "OK", "outputMode": "pipeline", "sampleCount": 5},
        {"docId": "DOC-2", "status": "OK", "outputMode": "cleanroom", "sampleCount": 1},
        {"docId": "DOC-3", "status": "OK", "outputMode": "handwriting", "sampleCount": 2, "generatedFileCount": 7},
    ]

    summary = _summary(rows, [])

    assert summary["generatedFileCount"] == 24
    assert summary["handwritingScopeCount"] == 1


def test_scope_cleanup_backs_up_only_target_doc_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(fre, "ROOT", tmp_path)
    monkeypatch.setattr(fre, "BACKUP_ROOT", tmp_path / ".bin" / "backups")
    out_dir = tmp_path / "outputs" / "results"
    doc_dir = out_dir / "금융" / "DOC-1_테스트문서"
    other_dir = out_dir / "제조" / "DOC-2_다른문서"
    doc_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)
    (doc_dir / "sample_999.jpg").write_text("stale", encoding="utf-8")
    (other_dir / "sample_000.jpg").write_text("keep", encoding="utf-8")

    backup_dir = fre._prepare_results_dir(out_dir, run_id="20260708_000000", clean=False)
    backup_dir = fre._backup_scope_output_dir(doc_dir, backup_dir=backup_dir, run_id="20260708_000000")

    assert not doc_dir.exists()
    assert other_dir.exists()
    assert (other_dir / "sample_000.jpg").read_text(encoding="utf-8") == "keep"
    assert (backup_dir / "outputs" / "results" / "금융" / "DOC-1_테스트문서" / "sample_999.jpg").read_text(encoding="utf-8") == "stale"


def test_final_export_preserves_existing_scope_dir_when_strict_pipeline_fails(tmp_path: Path, monkeypatch) -> None:
    registry = RegistryData(
        documents={"DOC-1": RegistryDocument(doc_id="DOC-1", title="테스트문서")},
        workflows={},
        bindings=[],
        source_path=Path("registry.xlsx"),
    )
    out_dir = tmp_path / "outputs" / "results"
    doc_dir = out_dir / "금융" / "DOC-1_테스트문서"
    doc_dir.mkdir(parents=True)
    stale = doc_dir / "sample_000.json"
    stale.write_text("{\"legacy\": true}", encoding="utf-8")

    monkeypatch.setattr(fre, "ROOT", tmp_path)
    monkeypatch.setattr(fre, "BACKUP_ROOT", tmp_path / ".bin" / "backups")
    monkeypatch.setattr(
        fre,
        "list_work_items",
        lambda *, registry, root: [
            {
                "docId": "DOC-1",
                "title": "테스트문서",
                "latestAuthoringSchema": "schema.json",
                "latestAuthoringStylesheet": "stylesheet.json",
                "latestAuthoringFakerProfile": "faker_profile.json",
            }
        ],
    )
    monkeypatch.setattr(fre, "_assessment_rows_by_key", lambda *, registry, root: {})
    monkeypatch.setattr(fre, "_source_hashes", lambda items_by_doc_id: {})
    monkeypatch.setattr(fre, "_changed_sources", lambda source_hashes: [])

    def fail_render(*args, **kwargs):
        raise ValueError("primary semantic_schema has unmapped leaves")

    monkeypatch.setattr(fre, "_render_pipeline_document", fail_render)

    result = fre.export_final_results(count=1, out_dir=out_dir, scope_entries=[{"domain": "금융", "docId": "DOC-1"}], registry=registry, root=tmp_path)

    assert result["summary"]["errorCount"] == 1
    assert stale.exists()
    assert stale.read_text(encoding="utf-8") == "{\"legacy\": true}"


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


def test_semantic_bbox_payload_omits_empty_text_annotation() -> None:
    schema = {"신청구분": {"신규": "", "증대": ""}}
    field_paths = {"new": "신청구분/신규", "increase": "신청구분/증대"}
    payload = {
        "image": {"width": 1000, "height": 2000},
        "annotations": [
            {"field": "new", "text": "V", "bbox": [10, 20, 30, 40]},
            {"field": "increase", "text": "", "bbox": [50, 20, 30, 40]},
        ],
    }

    result = _semantic_bbox_payload(schema, field_paths, payload)

    assert result == {"신청구분": {"신규": {"l": 0.01, "t": 0.01, "r": 0.04, "b": 0.03}}}


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
