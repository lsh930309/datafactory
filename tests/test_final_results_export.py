from __future__ import annotations

import json
import zipfile
from pathlib import Path

from PIL import Image

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


def test_resolve_scope_entries_defaults_to_registry_domain_bindings() -> None:
    registry = RegistryData(
        documents={"DOC-1": RegistryDocument(doc_id="DOC-1", title="테스트문서", po_domains=("금융",))},
        workflows={},
        bindings=[],
        source_path=Path("registry.xlsx"),
    )

    assert _resolve_scope_entries(None, registry=registry) == (("금융", "DOC-1"),)


def test_load_semantic_schema_prefers_canonical_embedded_schema_over_stale_sidecar(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps({"semantic_schema": {"신규구조": {"필드": ""}}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "semantic_schema.json").write_text(
        json.dumps({"구형구조": {"필드": ""}}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert fre._load_semantic_schema(schema_path) == {"신규구조": {"필드": ""}}


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


def test_resolve_scope_entries_rejects_unsupported_library_domain() -> None:
    registry = RegistryData(
        documents={"DOC-1": RegistryDocument(doc_id="DOC-1", title="테스트문서")},
        workflows={},
        bindings=[],
        source_path=Path("registry.xlsx"),
    )

    try:
        _resolve_scope_entries([{"domain": "기타", "docId": "DOC-1"}], registry=registry)
    except ValueError as exc:
        assert "unsupported library-sample domain" in str(exc)
    else:
        raise AssertionError("expected unsupported domain to fail")


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

    assert fre._resolve_output_mode(item, render_handwriting_as_printed=True, prefer_cleanroom=True) == "cleanroom_static"


def test_resolve_output_mode_uses_cleanroom_for_handwriting_without_authoring() -> None:
    item = {
        "registry": {"writingMethod": "수기"},
        "latestCleanroomPdf": "cleanroom.pdf",
    }

    assert fre._resolve_output_mode(item, render_handwriting_as_printed=True) == "cleanroom_static"


def test_primary_schema_payload_uses_only_primary_schema_leaves() -> None:
    semantic_schema = {
        "회사이름": "",
        "담보": {"종류": ""},
    }
    field_paths = {
        "account_name": ("회사이름",),
        "owner": ("대표자명",),
        "collateral_type": ("담보", "종류"),
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
        "patient_name": ("환자", "성명"),
        "issue_year": ("확인", "발급일자", "년"),
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


def test_final_export_preserves_existing_scope_dir_when_cleanroom_annotation_is_missing(tmp_path: Path, monkeypatch) -> None:
    registry = RegistryData(
        documents={"DOC-1": RegistryDocument(doc_id="DOC-1", title="테스트문서")},
        workflows={},
        bindings=[],
        source_path=Path("registry.xlsx"),
    )
    out_dir = tmp_path / "outputs" / "results"
    doc_dir = out_dir / "금융" / "DOC-1_테스트문서"
    doc_dir.mkdir(parents=True)
    stale = doc_dir / "sample_000.pdf"
    stale.write_bytes(b"legacy")
    cleanroom_pdf = tmp_path / "cleanroom.pdf"
    cleanroom_pdf.write_bytes(b"%PDF-test")

    monkeypatch.setattr(fre, "ROOT", tmp_path)
    monkeypatch.setattr(fre, "BACKUP_ROOT", tmp_path / ".bin" / "backups")
    monkeypatch.setattr(
        fre,
        "list_work_items",
        lambda *, registry, root: [{"docId": "DOC-1", "title": "테스트문서", "latestCleanroomPdf": str(cleanroom_pdf)}],
    )
    monkeypatch.setattr(fre, "_assessment_rows_by_key", lambda *, registry, root: {})
    monkeypatch.setattr(fre, "_source_hashes", lambda items_by_doc_id: {})
    monkeypatch.setattr(fre, "_changed_sources", lambda source_hashes: [])

    result = fre.export_final_results(count=1, out_dir=out_dir, scope_entries=[{"domain": "금융", "docId": "DOC-1"}], registry=registry, root=tmp_path)

    assert result["summary"]["errorCount"] == 1
    assert "annotation is required" in result["errors"][0]["error"]
    assert stale.read_bytes() == b"legacy"


def test_render_cleanroom_document_exports_static_jpg_json_bbox_schema_and_pii(tmp_path: Path, monkeypatch) -> None:
    pages_dir = tmp_path / "cleanroom" / "pages"
    pages_dir.mkdir(parents=True)
    image_path = pages_dir / "page_001.png"
    Image.new("RGB", (1400, 1800), "white").save(image_path)
    review_path = tmp_path / "review" / "review.json"
    review_path.parent.mkdir(parents=True)
    review_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_detections": str(tmp_path / "detections.json"),
                "source_image": str(image_path),
                "image": {"width": 1400, "height": 1800},
                "labels": [{"id": "name", "text": "홍길동", "confidence": 1.0, "bbox": [140, 180, 280, 90], "polygon": [], "status": "use", "auto_type": "field_value", "reason": "test"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    annotation_path = tmp_path / "library_sample" / "annotation.json"
    annotation_path.parent.mkdir(parents=True)
    annotation_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_image": str(image_path),
                "review_path": str(review_path),
                "fields": [{"key": "성명", "value": "홍길동", "bbox_label_id": "name"}],
                "privacy": {"include_keys": [], "exclude_keys": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(fre, "ROOT", tmp_path)

    result = fre._render_cleanroom_document(
        {
            "latestLibrarySampleAnnotation": str(annotation_path),
            "latestCleanroomPagesDir": str(pages_dir),
        },
        work_dir=tmp_path / "work",
    )

    names = {path.name for path in result.samples[0].values()}
    assert names == {"sample_000.jpg", "sample_000.json", "sample_000-bbox.json", "sample_000-pii.json"}
    assert json.loads(result.primary_schema.read_text(encoding="utf-8")) == {"성명": ""}
    assert result.pii_keys == ["성명"]


def test_cleanroom_multi_page_source_reports_deferred_single_page_warning(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    for index in range(2):
        Image.new("RGB", (10, 10), "white").save(pages_dir / f"page_{index + 1:03d}.png")

    warnings = fre._deferred_multi_page_warnings({"latestCleanroomPagesDir": str(pages_dir)}, mode="cleanroom_static")

    assert warnings[0]["code"] == "multi_page_export_deferred"
    assert warnings[0]["detectedPageCount"] == 2


def test_semantic_bbox_payload_rounds_to_four_decimals_and_has_only_ltrb() -> None:
    schema = {"성명": ""}
    field_paths = {"name": ("성명",)}
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
    field_paths = {"new": ("신청구분", "신규"), "increase": ("신청구분", "증대")}
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
    field_paths = {"name": ("성명",), "empty": ("미렌더링필드",)}
    payload = {
        "image": {"width": 1000, "height": 2000},
        "annotations": [
            {"field": "name", "bbox": [10, 20, 30, 40]},
        ],
    }

    result = _semantic_bbox_payload(schema, field_paths, payload)

    assert result == {"성명": {"l": 0.01, "t": 0.01, "r": 0.04, "b": 0.03}}


def test_semantic_bbox_payload_preserves_literal_slash_in_leaf_key() -> None:
    schema = {"대리인": {"주소(자택/직장)": ""}}
    field_paths = {"address": ("대리인", "주소(자택/직장)")}
    payload = {
        "image": {"width": 1000, "height": 1000},
        "annotations": [{"field": "address", "text": "서울시", "bbox": [100, 200, 300, 100]}],
    }

    assert _semantic_bbox_payload(schema, field_paths, payload) == {
        "대리인": {"주소(자택/직장)": {"l": 0.1, "t": 0.2, "r": 0.4, "b": 0.3}}
    }


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
