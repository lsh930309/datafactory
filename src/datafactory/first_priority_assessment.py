from __future__ import annotations

import html
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry import UNCLASSIFIED_DOMAIN, RegistryData, load_registry, slugify_title
from .workbench import WORKBENCH_ROOT, list_work_items

DOCUMENT_TYPES: dict[str, str] = {
    "unknown": "미지정",
    "structured_form": "정형양식",
    "free_form": "자유양식",
    "prose_report": "산문/보고서형",
}
FEASIBILITY_STATUSES: dict[str, str] = {
    "unknown": "미정",
    "possible": "작업 가능",
    "impossible": "작업 불가",
}


@dataclass(frozen=True)
class AssessmentEntry:
    key: str
    domain: str
    doc_id: str
    document_type: str = "unknown"
    feasibility: str = "unknown"
    comment: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "domain": self.domain,
            "docId": self.doc_id,
            "documentType": self.document_type,
            "documentTypeLabel": DOCUMENT_TYPES.get(self.document_type, DOCUMENT_TYPES["unknown"]),
            "feasibility": self.feasibility,
            "feasibilityLabel": FEASIBILITY_STATUSES.get(self.feasibility, FEASIBILITY_STATUSES["unknown"]),
            "comment": self.comment,
            "updatedAt": self.updated_at,
            "requiresComment": self.feasibility == "impossible" and not self.comment.strip(),
        }


def assessment_store_path(root: Path = WORKBENCH_ROOT) -> Path:
    return root.parent / "first_priority_assessments.json"


def scope_key(domain: str, doc_id: str) -> str:
    return f"{domain}::{doc_id}"


def load_assessment_store(root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    path = assessment_store_path(root)
    if not path.exists():
        return {"schema_version": 1, "entries": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": 1, "entries": {}}
    if not isinstance(payload.get("entries"), dict):
        payload["entries"] = {}
    payload.setdefault("schema_version", 1)
    return payload


def save_assessment_entry(
    *,
    domain: str,
    doc_id: str,
    document_type: str,
    feasibility: str,
    comment: str = "",
    registry: RegistryData | None = None,
    root: Path = WORKBENCH_ROOT,
) -> dict[str, Any]:
    registry = registry or load_registry()
    _validate_scope(domain, doc_id, registry)
    if document_type not in DOCUMENT_TYPES:
        raise ValueError("documentType must be one of: " + ", ".join(DOCUMENT_TYPES))
    if feasibility not in FEASIBILITY_STATUSES:
        raise ValueError("feasibility must be one of: " + ", ".join(FEASIBILITY_STATUSES))
    normalized_comment = str(comment or "").strip()
    if feasibility == "impossible" and not normalized_comment:
        raise ValueError("작업 불가 문서는 사유/절충안을 반드시 입력해야 합니다")

    store = load_assessment_store(root)
    key = scope_key(domain, doc_id)
    store.setdefault("entries", {})[key] = {
        "key": key,
        "domain": domain,
        "docId": doc_id,
        "documentType": document_type,
        "feasibility": feasibility,
        "comment": normalized_comment,
        "updatedAt": _now(),
    }
    store["updated_at"] = _now()
    path = assessment_store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return list_first_priority_assessments(registry=registry, root=root)


def list_first_priority_assessments(registry: RegistryData | None = None, root: Path = WORKBENCH_ROOT) -> dict[str, Any]:
    registry = registry or load_registry()
    store = load_assessment_store(root)
    saved_entries = store.get("entries", {}) if isinstance(store.get("entries"), dict) else {}
    work_by_doc = {item["docId"]: item for item in list_work_items(registry=registry, root=root)}
    rows: list[dict[str, Any]] = []
    for index, (domain, doc_id, scope_kind) in enumerate(_assessment_scope_entries(registry), start=1):
        doc = registry.documents.get(doc_id)
        if doc is None:
            continue
        saved = saved_entries.get(scope_key(domain, doc_id), {})
        entry = _entry_from_saved(domain, doc_id, saved)
        work = work_by_doc.get(doc_id, {})
        row = {
            **entry.to_dict(),
            "index": index,
            "title": doc.title,
            "issuer": doc.issuer,
            "registryGenre": doc.genre,
            "registryStructure": doc.structure,
            "registryNotes": doc.notes,
            "sampleCount": int(work.get("sampleCount") or 0),
            "workStatus": str(work.get("status") or "missing"),
            "workStatusLabel": str(work.get("statusLabel") or "미적재"),
            "hasOcr": bool(work.get("hasOcr")),
            "hasReview": bool(work.get("hasReview")),
            "hasInpaint": bool(work.get("hasInpaint")),
            "hasAuthoring": bool(work.get("hasAuthoring")),
            "documentDir": str(work.get("documentDir") or ""),
            "scopeKind": scope_kind,
            "isFirstPriority": False,
        }
        rows.append(row)
    return {
        "schemaVersion": 1,
        "updatedAt": str(store.get("updated_at") or ""),
        "documentTypes": [{"id": key, "label": label} for key, label in DOCUMENT_TYPES.items()],
        "feasibilityStatuses": [{"id": key, "label": label} for key, label in FEASIBILITY_STATUSES.items()],
        "summary": _summary(rows),
        "rows": rows,
    }


def export_first_priority_assessment_xlsx(
    *,
    out_dir: Path,
    registry: RegistryData | None = None,
    root: Path = WORKBENCH_ROOT,
) -> dict[str, Any]:
    payload = list_first_priority_assessments(registry=registry, root=root)
    rows = payload["rows"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"first_priority_assessment_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
    _write_xlsx(out_path, rows, payload["summary"])
    return {"path": str(out_path), "summary": payload["summary"], "rowCount": len(rows)}


def _entry_from_saved(domain: str, doc_id: str, saved: Any) -> AssessmentEntry:
    data = saved if isinstance(saved, dict) else {}
    document_type = str(data.get("documentType") or "unknown")
    feasibility = str(data.get("feasibility") or "unknown")
    if document_type not in DOCUMENT_TYPES:
        document_type = "unknown"
    if feasibility not in FEASIBILITY_STATUSES:
        feasibility = "unknown"
    return AssessmentEntry(
        key=scope_key(domain, doc_id),
        domain=domain,
        doc_id=doc_id,
        document_type=document_type,
        feasibility=feasibility,
        comment=str(data.get("comment") or ""),
        updated_at=str(data.get("updatedAt") or ""),
    )


def _assessment_scope_entries(registry: RegistryData) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for doc in sorted(registry.documents.values(), key=lambda item: (item.title, item.doc_id)):
        domains = tuple(doc.po_domains) or (UNCLASSIFIED_DOMAIN,)
        for domain in domains:
            key = (domain, doc.doc_id)
            if key in seen:
                continue
            seen.add(key)
            entries.append((domain, doc.doc_id, "registry_domain"))
    return entries


def _default_assessment_domain(doc: Any) -> str:
    domains = list(getattr(doc, "po_domains", ()) or ()) or list(getattr(doc, "domains", ()) or ())
    return str(domains[0] if domains else UNCLASSIFIED_DOMAIN)


def _validate_scope(domain: str, doc_id: str, registry: RegistryData) -> None:
    if doc_id not in registry.documents:
        raise ValueError(f"unknown docId: {doc_id}")
    if not str(domain or "").strip():
        raise ValueError("domain is required")


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_domain: dict[str, int] = {}
    by_type = {key: 0 for key in DOCUMENT_TYPES}
    by_feasibility = {key: 0 for key in FEASIBILITY_STATUSES}
    missing_required_reason = 0
    for row in rows:
        by_domain[row["domain"]] = by_domain.get(row["domain"], 0) + 1
        by_type[row["documentType"]] = by_type.get(row["documentType"], 0) + 1
        by_feasibility[row["feasibility"]] = by_feasibility.get(row["feasibility"], 0) + 1
        if row.get("requiresComment"):
            missing_required_reason += 1
    return {
        "scopeEntryCount": len(rows),
        "uniqueDocumentCount": len({row["docId"] for row in rows}),
        "byDomain": by_domain,
        "byDocumentType": by_type,
        "byFeasibility": by_feasibility,
        "missingRequiredReason": missing_required_reason,
        "generatedAt": _now(),
    }


def _write_xlsx(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    matrix = _xlsx_matrix(rows, summary)
    shared_strings: list[str] = []
    shared_string_index: dict[str, int] = {}
    sheet_xml = _sheet_xml(matrix, shared_strings, shared_string_index)
    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><fileVersion appName="xl"/><workbookPr defaultThemeVersion="166925"/><bookViews><workbookView xWindow="0" yWindow="0" windowWidth="28800" windowHeight="17600"/></bookViews><sheets><sheet name="문서판정" sheetId="1" r:id="rId1"/></sheets><calcPr calcId="191029"/></workbook>"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>"""
    workbook_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>"""
    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/styles.xml", _styles_xml())
        archive.writestr("xl/sharedStrings.xml", _shared_strings_xml(shared_strings))
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        archive.writestr("docProps/core.xml", _core_props_xml())
        archive.writestr("docProps/app.xml", _app_props_xml())

def _xlsx_matrix(rows: list[dict[str, Any]], summary: dict[str, Any]) -> list[list[dict[str, Any]]]:
    cells: list[list[dict[str, Any]]] = []
    cells.append([_cell("전체 문서 생성 가능성 판정표", 1)])
    cells.append([_cell(f"생성: {summary['generatedAt']} · 총 {summary['scopeEntryCount']}건 / 고유 {summary['uniqueDocumentCount']}종", 2)])
    cells.append([])
    cells.append([_cell("작업 가능", 3), _cell(summary["byFeasibility"].get("possible", 0), 10), _cell("작업 불가", 3), _cell(summary["byFeasibility"].get("impossible", 0), 10), _cell("미정", 3), _cell(summary["byFeasibility"].get("unknown", 0), 10), _cell("불가 사유 누락", 3), _cell(summary.get("missingRequiredReason", 0), 10)])
    cells.append([_cell("정형양식", 3), _cell(summary["byDocumentType"].get("structured_form", 0), 10), _cell("자유양식", 3), _cell(summary["byDocumentType"].get("free_form", 0), 10), _cell("산문/보고서형", 3), _cell(summary["byDocumentType"].get("prose_report", 0), 10), _cell("미지정", 3), _cell(summary["byDocumentType"].get("unknown", 0), 10)])
    cells.append([])
    headers = ["분야", "순번", "문서ID", "문서명", "문서 속성", "작업 상태", "코멘트/불가 사유/절충안", "샘플", "현재 단계", "BBox", "리뷰", "인페인트", "작업 폴더"]
    cells.append([_cell(value, 4) for value in headers])
    current_domain = ""
    domain_index = 0
    for row in rows:
        if row["domain"] != current_domain:
            current_domain = row["domain"]
            domain_index += 1
            cells.append([_cell(f"{current_domain} 영역", 5), *[_cell("", 5) for _ in headers[1:]]])
        feasibility_style = {"possible": 6, "impossible": 7, "unknown": 8}.get(row["feasibility"], 8)
        cells.append(
            [
                _cell(row["domain"], 9),
                _cell(domain_index, 10),
                _cell(row["docId"], 9),
                _cell(row["title"], 9),
                _cell(row["documentTypeLabel"], 9),
                _cell(row["feasibilityLabel"], feasibility_style),
                _cell(row["comment"], 11),
                _cell(row["sampleCount"], 10),
                _cell(row["workStatusLabel"], 9),
                _cell("Y" if row["hasOcr"] else "", 12),
                _cell("Y" if row["hasReview"] else "", 12),
                _cell("Y" if row["hasInpaint"] else "", 12),
                _cell(row["documentDir"], 11),
            ]
        )
    return cells


def _cell(value: Any, style: int = 0) -> dict[str, Any]:
    return {"value": value, "style": style}


def _sheet_xml(matrix: list[list[dict[str, Any]]], shared_strings: list[str], shared_string_index: dict[str, int]) -> str:
    widths = [10, 7, 11, 24, 16, 14, 44, 8, 14, 8, 8, 10, 34]
    xml = ["<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"]
    xml.append("<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">")
    xml.append(f"<dimension ref=\"A1:M{max(7, len(matrix))}\"/>")
    xml.append("<sheetViews><sheetView showGridLines=\"0\" workbookViewId=\"0\"><pane ySplit=\"7\" topLeftCell=\"A8\" activePane=\"bottomLeft\" state=\"frozen\"/><selection pane=\"bottomLeft\" activeCell=\"A8\" sqref=\"A8\"/></sheetView></sheetViews>")
    xml.append("<sheetFormatPr defaultRowHeight=\"15\"/>")
    xml.append("<cols>")
    for idx, width in enumerate(widths, start=1):
        xml.append(f"<col min=\"{idx}\" max=\"{idx}\" width=\"{width}\" customWidth=\"1\"/>")
    xml.append("</cols><sheetData>")
    for row_index, row in enumerate(matrix, start=1):
        height_attr = " ht=\"36\" customHeight=\"1\"" if row_index >= 8 else ""
        xml.append(f"<row r=\"{row_index}\"{height_attr}>")
        for col_index, cell in enumerate(row, start=1):
            xml.append(_cell_xml(row_index, col_index, cell.get("value"), int(cell.get("style") or 0), shared_strings, shared_string_index))
        xml.append("</row>")
    xml.append("</sheetData>")
    last_row = max(7, len(matrix))
    xml.append(f"<autoFilter ref=\"A7:M{last_row}\"/>")
    xml.append("<mergeCells count=\"2\"><mergeCell ref=\"A1:M1\"/><mergeCell ref=\"A2:M2\"/></mergeCells>")
    xml.append("<pageMargins left=\"0.7\" right=\"0.7\" top=\"0.75\" bottom=\"0.75\" header=\"0.3\" footer=\"0.3\"/>")
    xml.append("</worksheet>")
    return "".join(xml)


def _cell_xml(row: int, col: int, value: Any, style: int, shared_strings: list[str], shared_string_index: dict[str, int]) -> str:
    ref = f"{_col_name(col)}{row}"
    style_attr = f" s=\"{style}\"" if style else ""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return f"<c r=\"{ref}\"{style_attr}><v>{value}</v></c>"
    text = _clean_xml_text(str(value or ""))
    if text not in shared_string_index:
        shared_string_index[text] = len(shared_strings)
        shared_strings.append(text)
    return f"<c r=\"{ref}\" t=\"s\"{style_attr}><v>{shared_string_index[text]}</v></c>"


def _shared_strings_xml(shared_strings: list[str]) -> str:
    parts = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>",
        f"<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" count=\"{len(shared_strings)}\" uniqueCount=\"{len(shared_strings)}\">",
    ]
    for text in shared_strings:
        parts.append(f"<si><t>{html.escape(text, quote=False)}</t></si>")
    parts.append("</sst>")
    return "".join(parts)


def _clean_xml_text(value: str) -> str:
    # Excel repairs files that contain XML 1.0 control characters. Remove them
    # defensively before writing any worksheet/shared string part.
    return "".join(ch for ch in value if ch in "\t\n\r" or ord(ch) >= 0x20)

def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="5"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="16"/><color rgb="FFFFFFFF"/><name val="Arial"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Arial"/></font><font><b/><sz val="10"/><color rgb="FF1D2433"/><name val="Arial"/></font><font><sz val="10"/><color rgb="FF475467"/><name val="Arial"/></font></fonts>
<fills count="8"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF101828"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1E66F5"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFEAF1FF"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE8F7EE"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFEBEE"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFF8DF"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FFD8DEEA"/></left><right style="thin"><color rgb="FFD8DEEA"/></right><top style="thin"><color rgb="FFD8DEEA"/></top><bottom style="thin"><color rgb="FFD8DEEA"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="13">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="4" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="5" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="6" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="7" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="5" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
<dxfs count="0"/>
<tableStyles count="0" defaultTableStyle="TableStyleMedium9" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>"""


def _core_props_xml() -> str:
    now = _ooxml_now()
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>전체 문서 생성 가능성 판정표</dc:title><dc:creator>DataFactory</dc:creator><cp:lastModifiedBy>DataFactory</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>"""


def _app_props_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>DataFactory</Application><DocSecurity>0</DocSecurity><ScaleCrop>false</ScaleCrop><HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>1</vt:i4></vt:variant></vt:vector></HeadingPairs><TitlesOfParts><vt:vector size="1" baseType="lpstr"><vt:lpstr>문서판정</vt:lpstr></vt:vector></TitlesOfParts><Company></Company><LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged><AppVersion>16.0300</AppVersion></Properties>"""


def _col_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ooxml_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
