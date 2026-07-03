from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

from datafactory.registry import FIRST_PRIORITY_DOC_IDS, FIRST_PRIORITY_SCOPE_ENTRIES, load_registry, normalize_title, slugify_title
from datafactory.workbench import import_seed_batch, import_seed_folder, list_work_items, save_seed_mapping, save_uploaded_seed_files, scan_seed_samples, trash_seed_folder
from datafactory.first_priority_assessment import export_first_priority_assessment_xlsx, list_first_priority_assessments, save_assessment_entry
from datafactory.models import BBox, FieldSpec, TemplateSpec
from datafactory.render import render_template


def test_registry_loads_title_first_documents_and_priority_flags() -> None:
    registry = load_registry()

    family = registry.documents["ID-05"]
    lease = registry.documents["APP-08"]
    finance = registry.documents["FIN-01"]

    assert family.title == "가족관계증명서"
    assert "임대차계약서" in lease.title
    assert finance.is_first_priority
    assert "FIN-01" in FIRST_PRIORITY_DOC_IDS
    assert finance.workflow_ids
    assert finance.domains
    assert len(FIRST_PRIORITY_SCOPE_ENTRIES) == 30
    assert len(FIRST_PRIORITY_DOC_IDS) == 28
    assert registry.to_dict()["summary"]["firstPriorityScopeEntryCount"] == 30
    assert registry.to_dict()["summary"]["firstPriorityDocumentCount"] == 28
    assert finance.first_priority_domains == ("금융", "제조")


def test_title_normalization_and_slug_keep_korean_readability() -> None:
    assert normalize_title("표준 임대차계약서_별지") == "표준임대차계약서별지"
    assert normalize_title("신분증 사본(주민·면허·여권)") == "신분증주민면허여권"
    assert slugify_title("신분증 사본(주민·면허·여권)").startswith("신분증_사본")


def test_seed_scan_matches_readable_folder_names(tmp_path: Path) -> None:
    registry = load_registry()
    seed_root = tmp_path / "seed_samples"
    folder = seed_root / unicodedata.normalize("NFD", "가족관계증명서")
    folder.mkdir(parents=True)
    (folder / "sample.jpg").write_bytes(b"fake image")
    unknown = seed_root / "없는문서"
    unknown.mkdir()
    (unknown / "sample.png").write_bytes(b"fake image")

    scan = scan_seed_samples(seed_root, registry)
    by_name = {unicodedata.normalize("NFC", item["name"]): item for item in scan["folders"]}

    assert by_name["가족관계증명서"]["status"] == "importable"
    assert by_name["가족관계증명서"]["matchStatus"] == "matched"
    assert by_name["가족관계증명서"]["matchedDocId"] == "ID-05"
    assert by_name["없는문서"]["status"] == "needsReview"
    assert by_name["없는문서"]["matchStatus"] == "unmatched"


def test_import_seed_folder_copies_to_workbench_manifest_without_touching_source(tmp_path: Path) -> None:
    registry = load_registry()
    seed_folder = tmp_path / "seed_samples" / "가족관계증명서"
    seed_folder.mkdir(parents=True)
    source = seed_folder / "sample.jpg"
    source.write_bytes(b"seed-original")
    workbench_root = tmp_path / "workbench" / "documents"

    result = import_seed_folder(seed_folder, "ID-05", registry=registry, root=workbench_root)

    copied_path = Path(result["copied"][0]["path"])
    if not copied_path.is_absolute():
        copied_path = Path.cwd() / copied_path
    assert source.read_bytes() == b"seed-original"
    assert copied_path.read_bytes() == b"seed-original"

    manifest_path = workbench_root / "가족관계증명서__ID-05" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["doc_id"] == "ID-05"
    assert manifest["title"] == "가족관계증명서"
    assert manifest["status"] == "sample_imported"
    assert manifest["samples"]

    item = next(item for item in list_work_items(registry=registry, root=workbench_root) if item["docId"] == "ID-05")
    assert item["status"] == "sample_imported"
    assert item["sampleCount"] == 1


def test_import_seed_folder_renders_missing_pdf_pages_before_copy(tmp_path: Path, monkeypatch) -> None:
    import datafactory.workbench as workbench_module

    registry = load_registry()
    seed_folder = tmp_path / "seed_samples" / "가족관계증명서"
    seed_folder.mkdir(parents=True)
    pdf = seed_folder / "family.pdf"
    pdf.write_bytes(b"%PDF")
    workbench_root = tmp_path / "workbench" / "documents"

    def fake_render(pdf_path: Path) -> list[Path]:
        rendered = pdf_path.with_name(f"{pdf_path.stem}_page_001.jpg")
        rendered.write_bytes(b"jpg-page")
        return [rendered]

    monkeypatch.setattr(workbench_module, "render_pdf_pages", fake_render)

    result = import_seed_folder(seed_folder, "ID-05", registry=registry, root=workbench_root)

    assert result["rendered"][0]["path"].endswith("family_page_001.jpg")
    assert any(item["source"].endswith("family.pdf") for item in result["copied"])
    assert any(item["source"].endswith("family_page_001.jpg") for item in result["copied"])
    item = next(item for item in list_work_items(registry=registry, root=workbench_root) if item["docId"] == "ID-05")
    assert item["sampleCount"] == 2


def test_import_seed_folder_skips_existing_pdf_rendered_pages(tmp_path: Path, monkeypatch) -> None:
    import datafactory.workbench as workbench_module

    registry = load_registry()
    seed_folder = tmp_path / "seed_samples" / "가족관계증명서"
    seed_folder.mkdir(parents=True)
    (seed_folder / "family.pdf").write_bytes(b"%PDF")
    (seed_folder / "family_page_001.jpg").write_bytes(b"jpg-page")
    workbench_root = tmp_path / "workbench" / "documents"

    def fail_render(pdf_path: Path) -> list[Path]:  # pragma: no cover - failure path
        raise AssertionError(f"render should be skipped for {pdf_path}")

    monkeypatch.setattr(workbench_module, "render_pdf_pages", fail_render)

    result = import_seed_folder(seed_folder, "ID-05", registry=registry, root=workbench_root)

    assert result["rendered"] == []
    assert result["renderSkipped"][0]["reason"] == "already_rendered"
    assert len(result["copied"]) == 2



def test_seed_scan_classifies_importable_and_already_imported(tmp_path: Path) -> None:
    registry = load_registry()
    seed_root = tmp_path / "seed_samples"
    seed_folder = seed_root / "가족관계증명서"
    seed_folder.mkdir(parents=True)
    (seed_folder / "sample.jpg").write_bytes(b"seed-original")
    workbench_root = tmp_path / "workbench" / "documents"

    before = scan_seed_samples(seed_root, registry, root=workbench_root)
    folder_before = before["folders"][0]
    assert folder_before["status"] == "importable"
    assert folder_before["matchStatus"] == "matched"
    assert folder_before["matchedDocId"] == "ID-05"

    import_seed_folder(seed_folder, "ID-05", registry=registry, root=workbench_root)
    after = scan_seed_samples(seed_root, registry, root=workbench_root)
    assert after["folders"][0]["status"] == "alreadyImported"


def test_manual_mapping_is_reused_by_next_seed_scan(tmp_path: Path) -> None:
    registry = load_registry()
    seed_root = tmp_path / "seed_samples"
    seed_folder = seed_root / "초본"
    seed_folder.mkdir(parents=True)
    (seed_folder / "sample.jpg").write_bytes(b"seed-original")
    workbench_root = tmp_path / "workbench" / "documents"

    before = scan_seed_samples(seed_root, registry, root=workbench_root)
    assert before["folders"][0]["status"] == "needsReview"

    mapping = save_seed_mapping("초본", "ID-04", registry=registry, root=workbench_root)
    assert mapping["docId"] == "ID-04"

    after = scan_seed_samples(seed_root, registry, root=workbench_root)
    folder = after["folders"][0]
    assert folder["status"] == "importable"
    assert folder["matchedDocId"] == "ID-04"
    assert folder["candidates"][0]["reason"] == "저장된 수동 매핑"


def test_batch_import_is_idempotent_for_same_seed_sources(tmp_path: Path) -> None:
    registry = load_registry()
    seed_root = tmp_path / "seed_samples"
    family = seed_root / "가족관계증명서"
    resident = seed_root / "주민등록등본"
    family.mkdir(parents=True)
    resident.mkdir(parents=True)
    (family / "family.jpg").write_bytes(b"family")
    (resident / "resident.jpg").write_bytes(b"resident")
    workbench_root = tmp_path / "workbench" / "documents"
    items = [
        {"seedFolder": str(family), "docId": "ID-05"},
        {"seedFolder": str(resident), "docId": "ID-04"},
    ]

    first = import_seed_batch(items, registry=registry, root=workbench_root)
    second = import_seed_batch(items, registry=registry, root=workbench_root)

    assert first["summary"]["copied"] == 2
    assert first["summary"]["skipped"] == 0
    assert second["summary"]["copied"] == 0
    assert second["summary"]["skipped"] == 2
    family_item = next(item for item in list_work_items(registry=registry, root=workbench_root) if item["docId"] == "ID-05")
    assert family_item["sampleCount"] == 1


def test_batch_import_summarizes_pdf_rendered_pages(tmp_path: Path, monkeypatch) -> None:
    import datafactory.workbench as workbench_module

    registry = load_registry()
    seed_folder = tmp_path / "seed_samples" / "가족관계증명서"
    seed_folder.mkdir(parents=True)
    (seed_folder / "family.pdf").write_bytes(b"%PDF")
    workbench_root = tmp_path / "workbench" / "documents"

    def fake_render(pdf_path: Path) -> list[Path]:
        rendered = pdf_path.with_name(f"{pdf_path.stem}_page_001.jpg")
        rendered.write_bytes(b"jpg-page")
        return [rendered]

    monkeypatch.setattr(workbench_module, "render_pdf_pages", fake_render)

    result = import_seed_batch([{"seedFolder": str(seed_folder), "docId": "ID-05"}], registry=registry, root=workbench_root)

    assert result["summary"]["rendered"] == 1
    assert result["summary"]["copied"] == 2


def test_work_items_expose_latest_inpainted_and_comparison_paths(tmp_path: Path) -> None:
    registry = load_registry()
    seed_folder = tmp_path / "seed_samples" / "가족관계증명서"
    seed_folder.mkdir(parents=True)
    (seed_folder / "sample.jpg").write_bytes(b"seed-original")
    workbench_root = tmp_path / "workbench" / "documents"
    import_seed_folder(seed_folder, "ID-05", registry=registry, root=workbench_root)

    inpaint_dir = workbench_root / "가족관계증명서__ID-05" / "inpaint" / "original_sample" / "lama"
    inpaint_dir.mkdir(parents=True)
    (inpaint_dir / "inpainted_lama.png").write_bytes(b"inpainted")
    (inpaint_dir / "comparison_lama.png").write_bytes(b"comparison")

    item = next(item for item in list_work_items(registry=registry, root=workbench_root) if item["docId"] == "ID-05")

    assert item["status"] == "inpaint_done"
    assert item["latestInpainted"].endswith("inpainted_lama.png")
    assert item["latestInpaintComparison"].endswith("comparison_lama.png")


def test_uploaded_seed_image_is_saved_mapped_and_imported(tmp_path: Path) -> None:
    registry = load_registry()
    seed_root = tmp_path / "seed_samples"
    workbench_root = tmp_path / "workbench" / "documents"

    result = save_uploaded_seed_files(
        "ID-05",
        [{"name": "family sample.png", "bytes": b"png-bytes"}],
        registry=registry,
        seed_root=seed_root,
        root=workbench_root,
    )

    seed_file = seed_root / "가족관계증명서" / "family_sample.png"
    assert seed_file.read_bytes() == b"png-bytes"
    assert result["selectedSample"].endswith(".png")
    assert result["import"]["copied"]

    scan = scan_seed_samples(seed_root, registry, root=workbench_root)
    folder = scan["folders"][0]
    assert folder["matchedDocId"] == "ID-05"
    assert folder["status"] == "alreadyImported"


def test_uploaded_seed_duplicate_name_is_not_overwritten(tmp_path: Path) -> None:
    registry = load_registry()
    seed_root = tmp_path / "seed_samples"
    workbench_root = tmp_path / "workbench" / "documents"

    first = save_uploaded_seed_files("ID-05", [{"name": "sample.jpg", "bytes": b"one"}], registry=registry, seed_root=seed_root, root=workbench_root)
    second = save_uploaded_seed_files("ID-05", [{"name": "sample.jpg", "bytes": b"two"}], registry=registry, seed_root=seed_root, root=workbench_root)

    first_path = tmp_path / first["saved"][0]["path"]
    second_path = tmp_path / second["saved"][0]["path"]
    assert first_path.read_bytes() == b"one"
    assert second_path.read_bytes() == b"two"
    assert first_path.name == "sample.jpg"
    assert second_path.name == "sample_2.jpg"


def test_uploaded_pdf_is_rendered_and_rendered_page_is_selected(tmp_path: Path, monkeypatch) -> None:
    import datafactory.workbench as workbench_module

    registry = load_registry()
    seed_root = tmp_path / "seed_samples"
    workbench_root = tmp_path / "workbench" / "documents"

    def fake_render(pdf_path: Path) -> list[Path]:
        rendered = pdf_path.with_name(f"{pdf_path.stem}_page_001.jpg")
        rendered.write_bytes(b"jpg-page")
        return [rendered]

    monkeypatch.setattr(workbench_module, "render_pdf_pages", fake_render)

    result = save_uploaded_seed_files(
        "ID-05",
        [{"name": "family.pdf", "bytes": b"%PDF"}],
        registry=registry,
        seed_root=seed_root,
        root=workbench_root,
    )

    assert result["rendered"][0]["path"].endswith("family_page_001.jpg")
    assert result["selectedSample"].endswith("family_page_001.jpg")
    item = next(item for item in list_work_items(registry=registry, root=workbench_root) if item["docId"] == "ID-05")
    assert any(sample.endswith("family.pdf") for sample in item["samples"])
    assert any(sample.endswith("family_page_001.jpg") for sample in item["samples"])


def test_uploaded_seed_rejects_unsupported_extension(tmp_path: Path) -> None:
    registry = load_registry()
    try:
        save_uploaded_seed_files(
            "ID-05",
            [{"name": "note.txt", "bytes": b"text"}],
            registry=registry,
            seed_root=tmp_path / "seed_samples",
            root=tmp_path / "workbench" / "documents",
        )
    except ValueError as exc:
        assert "unsupported upload extension" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("unsupported upload should fail")


def test_trash_seed_folder_moves_seed_only_to_trash(tmp_path: Path) -> None:
    seed_root = tmp_path / "seed_samples"
    seed_folder = seed_root / "가족관계증명서"
    seed_folder.mkdir(parents=True)
    (seed_folder / "sample.jpg").write_bytes(b"seed-original")
    workbench_root = tmp_path / "workbench" / "documents"

    result = trash_seed_folder(seed_folder, seed_root=seed_root, root=workbench_root)

    assert not seed_folder.exists()
    trash_path = Path(result["trashPath"])
    if not trash_path.is_absolute():
        trash_path = Path.cwd() / trash_path
    assert trash_path.exists()
    assert (trash_path / "sample.jpg").read_bytes() == b"seed-original"
    assert result["name"] == "가족관계증명서"


def test_trash_seed_folder_rejects_path_outside_seed_root(tmp_path: Path) -> None:
    seed_root = tmp_path / "seed_samples"
    seed_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    try:
        trash_seed_folder(outside, seed_root=seed_root, root=tmp_path / "workbench" / "documents")
    except ValueError as exc:
        assert "seed folder must be inside" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("outside folder should fail")


def test_first_priority_assessment_save_requires_reason_for_impossible(tmp_path: Path) -> None:
    registry = load_registry()
    workbench_root = tmp_path / "workbench" / "documents"

    try:
        save_assessment_entry(
            domain="금융",
            doc_id="FIN-01",
            document_type="prose_report",
            feasibility="impossible",
            comment="",
            registry=registry,
            root=workbench_root,
        )
    except ValueError as exc:
        assert "사유" in str(exc)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("impossible assessment without reason should fail")

    payload = save_assessment_entry(
        domain="금융",
        doc_id="FIN-01",
        document_type="prose_report",
        feasibility="impossible",
        comment="수십 페이지 보고서형으로 템플릿 합성이 어려움",
        registry=registry,
        root=workbench_root,
    )
    row = next(item for item in payload["rows"] if item["domain"] == "금융" and item["docId"] == "FIN-01")
    assert row["documentType"] == "prose_report"
    assert row["feasibility"] == "impossible"
    assert payload["summary"]["byFeasibility"]["impossible"] == 1


def test_first_priority_assessment_exports_single_sheet_xlsx(tmp_path: Path) -> None:
    registry = load_registry()
    workbench_root = tmp_path / "workbench" / "documents"
    save_assessment_entry(
        domain="제조",
        doc_id="TRD-07",
        document_type="structured_form",
        feasibility="possible",
        comment="샘플 확보 시 1-cycle 가능",
        registry=registry,
        root=workbench_root,
    )

    payload = list_first_priority_assessments(registry=registry, root=workbench_root)
    assert payload["summary"]["scopeEntryCount"] == 30
    assert payload["summary"]["uniqueDocumentCount"] == 28

    result = export_first_priority_assessment_xlsx(out_dir=tmp_path / "outputs", registry=registry, root=workbench_root)
    workbook_path = Path(result["path"])
    assert workbook_path.exists()
    with __import__("zipfile").ZipFile(workbook_path) as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
        assert "xl/worksheets/sheet1.xml" in names
        assert "xl/sharedStrings.xml" in names
        assert "docProps/core.xml" in names
        for name in names:
            if name.endswith(".xml") or name.endswith(".rels"):
                ET.fromstring(archive.read(name))
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        shared_strings = archive.read("xl/sharedStrings.xml").decode("utf-8")
        styles = archive.read("xl/styles.xml").decode("utf-8")
    assert "1차 목표 문서 생성 가능성 판정표" in shared_strings
    assert "TRD-07" in shared_strings
    assert sheet.find("<autoFilter") < sheet.find("<mergeCells")
    assert 't="inlineStr"' not in sheet
    assert 'r="B1"' not in sheet
    assert "<dxfs count=\"0\"/>" in styles
    assert "<tableStyles" in styles


def test_workbench_prefers_manual_cleanup_inpainted_template(tmp_path: Path) -> None:
    registry = load_registry()
    workbench_root = tmp_path / "workbench" / "documents"
    doc_root = workbench_root / "가족관계증명서__ID-05"
    (doc_root / "samples" / "original").mkdir(parents=True)
    (doc_root / "samples" / "original" / "sample.jpg").write_bytes(b"sample")
    lama_dir = doc_root / "inpaint" / "sample" / "lama"
    cleanup_dir = doc_root / "inpaint" / "sample" / "manual_cleanup"
    lama_dir.mkdir(parents=True)
    cleanup_dir.mkdir(parents=True)
    (lama_dir / "inpainted_lama.png").write_bytes(b"lama")
    (lama_dir / "comparison_lama.png").write_bytes(b"comparison")
    (cleanup_dir / "inpainted_lama.png").write_bytes(b"cleanup")
    (cleanup_dir / "comparison_lama.png").write_bytes(b"cleanup-comparison")
    (cleanup_dir / "manual_mask.png").write_bytes(b"mask")
    (doc_root / "manifest.json").write_text(
        json.dumps({"doc_id": "ID-05", "title": "가족관계증명서", "samples": [], "artifacts": {}}, ensure_ascii=False),
        encoding="utf-8",
    )

    item = next(item for item in list_work_items(registry=registry, root=workbench_root) if item["docId"] == "ID-05")

    assert item["hasInpaint"]
    assert item["hasInpaintCleanup"]
    assert item["latestInpainted"].endswith("manual_cleanup/inpainted_lama.png")
    assert item["latestInpaintComparison"].endswith("manual_cleanup/comparison_lama.png")


def test_workbench_exposes_cleanroom_final_artifacts(tmp_path: Path) -> None:
    registry = load_registry()
    workbench_root = tmp_path / "workbench" / "documents"
    doc_root = workbench_root / "회의록(이사회·주총)__ADM-01"
    cleanroom_root = doc_root / "samples" / "cleanroom"
    pages_dir = cleanroom_root / "pages"
    qa_dir = cleanroom_root / "qa"
    pages_dir.mkdir(parents=True)
    qa_dir.mkdir(parents=True)
    (pages_dir / "page_001.png").write_bytes(b"png")
    (cleanroom_root / "cleanroom_board_minutes.pdf").write_bytes(b"pdf")
    (qa_dir / "contact_sheet.jpg").write_bytes(b"jpg")
    (qa_dir / "source_vs_cleanroom_notes.md").write_text("ok", encoding="utf-8")
    (doc_root / "manifest.json").write_text(
        json.dumps(
            {
                "doc_id": "ADM-01",
                "title": "회의록(이사회·주총)",
                "status": "cleanroom_sample_ready",
                "samples": [],
                "artifacts": {
                    "cleanroom": {
                        "pdf": str(cleanroom_root / "cleanroom_board_minutes.pdf"),
                        "pages_dir": str(pages_dir),
                        "contact_sheet": str(qa_dir / "contact_sheet.jpg"),
                        "notes": str(qa_dir / "source_vs_cleanroom_notes.md"),
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    item = next(item for item in list_work_items(registry=registry, root=workbench_root) if item["docId"] == "ADM-01")

    assert item["status"] == "cleanroom_sample_ready"
    assert item["statusLabel"] == "클린룸 완료"
    assert item["latestCleanroomPreview"].endswith("samples/cleanroom/pages/page_001.png")
    assert item["latestCleanroomPdf"].endswith("samples/cleanroom/cleanroom_board_minutes.pdf")
    assert item["latestCleanroomContactSheet"].endswith("samples/cleanroom/qa/contact_sheet.jpg")
    assert item["latestCleanroomNotes"].endswith("samples/cleanroom/qa/source_vs_cleanroom_notes.md")


def test_render_template_skips_empty_values_without_annotations(tmp_path: Path) -> None:
    image_path = tmp_path / "template.png"
    Image.new("RGB", (220, 120), "white").save(image_path)
    template = TemplateSpec(
        template_id="empty-value-test",
        image_path=image_path,
        fields=[
            FieldSpec(name="visible", bbox=BBox(10, 10, 100, 30), font_size=18, include_gt=True),
            FieldSpec(name="empty", bbox=BBox(10, 60, 100, 30), font_size=18, include_gt=True),
        ],
    )

    _image, annotations = render_template(template, {"visible": "홍길동", "empty": ""})

    assert [annotation.field for annotation in annotations] == ["visible"]


def test_render_template_applies_opacity_and_letter_spacing(tmp_path: Path) -> None:
    image_path = tmp_path / "template.png"
    Image.new("RGB", (260, 80), "white").save(image_path)
    template = TemplateSpec(
        template_id="style-test",
        image_path=image_path,
        fields=[
            FieldSpec(
                name="faded",
                bbox=BBox(10, 10, 230, 50),
                font_size=24,
                color=(0, 0, 0),
                opacity=0.5,
                letter_spacing=8.0,
                align="left",
                include_gt=True,
            ),
        ],
    )

    image, annotations = render_template(template, {"faded": "ABCD"})

    dark_pixels = [
        pixel
        for pixel in image.crop((10, 10, 240, 60)).getdata()
        if pixel != (255, 255, 255)
    ]
    assert dark_pixels
    assert min(pixel[0] for pixel in dark_pixels) > 0
    assert annotations[0].bbox.width > 60


def test_render_template_supersampling_preserves_output_size_and_bbox_space(tmp_path: Path) -> None:
    image_path = tmp_path / "template_supersample.png"
    Image.new("RGB", (240, 120), "white").save(image_path)
    template = TemplateSpec(
        template_id="supersample-test",
        image_path=image_path,
        fields=[
            FieldSpec(name="value", bbox=BBox(30, 40, 120, 32), font_size=18, include_gt=True),
        ],
    )

    image, annotations = render_template(template, {"value": "ABC123"}, render_scale=2)

    assert image.size == (240, 120)
    assert annotations[0].requested_bbox.to_list() == [30, 40, 120, 32]
    assert 0 <= annotations[0].bbox.x < 240
    assert 0 <= annotations[0].bbox.y < 120


def test_render_template_wraps_and_allows_overflow(tmp_path: Path) -> None:
    image_path = tmp_path / "template_wrap.png"
    Image.new("RGB", (260, 160), "white").save(image_path)
    template = TemplateSpec(
        template_id="wrap-allow-test",
        image_path=image_path,
        fields=[
            FieldSpec(name="wrapped", bbox=BBox(10, 10, 90, 80), font_size=20, overflow="wrap", line_spacing=1.05, include_gt=True),
            FieldSpec(name="allowed", bbox=BBox(10, 110, 20, 25), font_size=20, overflow="allow", include_gt=True),
        ],
    )

    _image, annotations = render_template(template, {"wrapped": "가나다라마바사아자차카타파하", "allowed": "LONGTEXT"})

    wrapped = next(item for item in annotations if item.field == "wrapped")
    allowed = next(item for item in annotations if item.field == "allowed")
    assert wrapped.bbox.height > 20
    assert wrapped.bbox.width <= 95
    assert allowed.bbox.width > allowed.requested_bbox.width


def test_render_template_applies_baseline_shift(tmp_path: Path) -> None:
    image_path = tmp_path / "template_baseline.png"
    Image.new("RGB", (220, 120), "white").save(image_path)
    template_up = TemplateSpec(
        template_id="baseline-up",
        image_path=image_path,
        fields=[
            FieldSpec(name="value", bbox=BBox(20, 30, 160, 50), font_size=22, baseline_shift=-6, include_gt=True),
        ],
    )
    template_flat = TemplateSpec(
        template_id="baseline-flat",
        image_path=image_path,
        fields=[
            FieldSpec(name="value", bbox=BBox(20, 30, 160, 50), font_size=22, baseline_shift=0, include_gt=True),
        ],
    )

    _image_up, up_annotations = render_template(template_up, {"value": "기준값"})
    _image_flat, flat_annotations = render_template(template_flat, {"value": "기준값"})

    assert up_annotations[0].bbox.y == flat_annotations[0].bbox.y - 6
