from __future__ import annotations

import posixpath
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = ROOT / "registry" / "DEEP_Agent_문서분류_레지스트리_v2.2.xlsx"

SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"a": SPREADSHEET_NS, "r": REL_NS}


PO_DOMAIN_SUMMARY: dict[str, dict[str, int]] = {
    # registry/데이터구축_UIUX_1차_금융제조.pdf p.1 하단 "구축 대상 요약" 기준.
    # PO 문맥의 도메인은 업무분류 원문보다 거친 구축 범위 축이다.
    "금융": {"total": 37, "active": 17, "inactive": 20},
    "제조": {"total": 12, "active": 2, "inactive": 10},
    "보험": {"total": 17, "active": 3, "inactive": 14},
    "공공": {"total": 20, "active": 6, "inactive": 14},
    "의료": {"total": 9, "active": 1, "inactive": 8},
    "무역": {"total": 8, "active": 0, "inactive": 8},
    "건설": {"total": 9, "active": 3, "inactive": 6},
    "법무": {"total": 10, "active": 1, "inactive": 9},
    "회계": {"total": 9, "active": 2, "inactive": 7},
    "인사": {"total": 10, "active": 2, "inactive": 8},
    "교육": {"total": 12, "active": 3, "inactive": 9},
}
PO_DOMAIN_ORDER: tuple[str, ...] = tuple(PO_DOMAIN_SUMMARY)


def po_domain_for_workflow_domain(domain: str) -> str:
    value = str(domain or "").strip()
    if value.startswith("금융"):
        return "금융"
    prefix_map = {
        "제조": "제조",
        "보험": "보험",
        "공공": "공공",
        "의료": "의료",
        "무역": "무역",
        "건설": "건설",
        "법무": "법무",
        "회계": "회계",
        "인사": "인사",
        "교육": "교육",
    }
    for prefix, po_domain in prefix_map.items():
        if value.startswith(prefix):
            return po_domain
    return value


def _ordered_po_domains(values: set[str]) -> tuple[str, ...]:
    known = [domain for domain in PO_DOMAIN_ORDER if domain in values]
    extra = sorted(value for value in values if value not in PO_DOMAIN_SUMMARY)
    return tuple([*known, *extra])


FIRST_PRIORITY_SCOPE_ENTRIES: tuple[tuple[str, str], ...] = (
    # registry/데이터구축_UIUX_1차_금융제조.pdf p.2: 금융 · 비활성 20건 1차 우선
    ("금융", "ID-03"),
    ("금융", "FIN-01"),
    ("금융", "RPT-01"),
    ("금융", "ADM-01"),
    ("금융", "CRD-01"),
    ("금융", "CRD-02"),
    ("금융", "RPT-02"),
    ("금융", "COL-02"),
    ("금융", "COL-05"),
    ("금융", "ID-11"),
    ("금융", "APP-13"),
    ("금융", "RPT-08"),
    ("금융", "RPT-07"),
    ("금융", "SEC-03"),
    ("금융", "APP-12"),
    ("금융", "SEC-01"),
    ("금융", "FIN-11"),
    ("금융", "LGL-02"),
    ("금융", "RPT-06"),
    ("금융", "APP-14"),
    # registry/데이터구축_UIUX_1차_금융제조.pdf p.2-3: 제조 · 비활성 10건 1차 우선
    ("제조", "TRD-07"),
    ("제조", "ADM-04"),
    ("제조", "QC-02"),
    ("제조", "QC-01"),
    ("제조", "RPT-08"),
    ("제조", "FIN-01"),
    ("제조", "TRD-05"),
    ("제조", "TRD-01"),
    ("제조", "TRD-06"),
    ("제조", "TRD-02"),
)
FINANCE_PRIORITY_DOC_IDS = {doc_id for domain, doc_id in FIRST_PRIORITY_SCOPE_ENTRIES if domain == "금융"}
MANUFACTURING_PRIORITY_DOC_IDS = {doc_id for domain, doc_id in FIRST_PRIORITY_SCOPE_ENTRIES if domain == "제조"}
FIRST_PRIORITY_DOC_IDS = {doc_id for _, doc_id in FIRST_PRIORITY_SCOPE_ENTRIES}
FIRST_PRIORITY_DOMAINS_BY_DOC_ID: dict[str, tuple[str, ...]] = {
    doc_id: tuple(domain for domain, scoped_doc_id in FIRST_PRIORITY_SCOPE_ENTRIES if scoped_doc_id == doc_id)
    for doc_id in FIRST_PRIORITY_DOC_IDS
}


@dataclass(frozen=True)
class RegistryDocument:
    doc_id: str
    title: str
    issuer: str = ""
    genre: str = ""
    structure: str = ""
    modality: str = ""
    sensitivity: str = ""
    fields: str = ""
    notes: str = ""
    has_personal_info: str = ""
    personal_info_detail: str = ""
    validation_rules: str = ""
    validation_rule_codes: str = ""
    writing_method: str = ""
    aliases: tuple[str, ...] = ()
    workflow_ids: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    po_domains: tuple[str, ...] = ()
    is_first_priority: bool = False
    first_priority_domains: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "docId": self.doc_id,
            "title": self.title,
            "issuer": self.issuer,
            "genre": self.genre,
            "structure": self.structure,
            "modality": self.modality,
            "sensitivity": self.sensitivity,
            "fields": self.fields,
            "notes": self.notes,
            "hasPersonalInfo": self.has_personal_info,
            "personalInfoDetail": self.personal_info_detail,
            "validationRules": self.validation_rules,
            "validationRuleCodes": self.validation_rule_codes,
            "writingMethod": self.writing_method,
            "aliases": list(self.aliases),
            "workflowIds": list(self.workflow_ids),
            "domains": list(self.domains),
            "workflowDomains": list(self.domains),
            "poDomains": list(self.po_domains),
            "isFirstPriority": self.is_first_priority,
            "firstPriorityDomains": list(self.first_priority_domains),
            "firstPriorityScopeCount": len(self.first_priority_domains),
        }


@dataclass(frozen=True)
class RegistryWorkflow:
    workflow_id: str
    domain: str
    name: str
    description: str = ""
    output_doc_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflowId": self.workflow_id,
            "domain": self.domain,
            "name": self.name,
            "description": self.description,
            "outputDocId": self.output_doc_id,
        }


@dataclass(frozen=True)
class RegistryBinding:
    workflow_id: str
    doc_id: str
    direction: str
    required: str
    workflow_name: str = ""
    doc_title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflowId": self.workflow_id,
            "docId": self.doc_id,
            "direction": self.direction,
            "required": self.required,
            "workflowName": self.workflow_name,
            "docTitle": self.doc_title,
        }


@dataclass(frozen=True)
class RegistryData:
    documents: dict[str, RegistryDocument]
    workflows: dict[str, RegistryWorkflow]
    bindings: list[RegistryBinding]
    source_path: Path
    first_priority_doc_ids: set[str] = field(default_factory=lambda: set(FIRST_PRIORITY_DOC_IDS))
    first_priority_scope_entries: tuple[tuple[str, str], ...] = FIRST_PRIORITY_SCOPE_ENTRIES

    def to_dict(self) -> dict[str, Any]:
        workflow_domains = sorted({workflow.domain for workflow in self.workflows.values() if workflow.domain})
        po_domains = [domain for domain in PO_DOMAIN_ORDER if any(domain in doc.po_domains for doc in self.documents.values())]
        po_domain_counts = {domain: sum(1 for doc in self.documents.values() if domain in doc.po_domains) for domain in po_domains}
        return {
            "sourcePath": str(self.source_path),
            "summary": {
                "documentCount": len(self.documents),
                "workflowCount": len(self.workflows),
                "bindingCount": len(self.bindings),
                "domainCount": len(po_domains),
                "workflowDomainCount": len(workflow_domains),
                "firstPriorityDocumentCount": len([doc for doc in self.documents.values() if doc.is_first_priority]),
                "firstPriorityScopeEntryCount": len(self.first_priority_scope_entries),
            },
            "documents": [doc.to_dict() for doc in sorted(self.documents.values(), key=lambda item: (not item.is_first_priority, item.title, item.doc_id))],
            "workflows": [workflow.to_dict() for workflow in sorted(self.workflows.values(), key=lambda item: (item.domain, item.name, item.workflow_id))],
            "bindings": [binding.to_dict() for binding in self.bindings],
            "domains": po_domains,
            "poDomains": po_domains,
            "workflowDomains": workflow_domains,
            "poDomainCounts": po_domain_counts,
            "poDomainSummary": [
                {"id": domain, "label": domain, **PO_DOMAIN_SUMMARY[domain]}
                for domain in PO_DOMAIN_ORDER
            ],
            "firstPriorityDocIds": sorted(self.first_priority_doc_ids),
            "targetGroups": [
                {
                    "id": "first_priority",
                    "label": "기존 1차 목표",
                    "description": "현재 authoring/생성 가능성 판정 기본 대상 그룹입니다.",
                    "scopeEntries": [
                        {
                            "domain": domain,
                            "docId": doc_id,
                            "title": self.documents[doc_id].title if doc_id in self.documents else "",
                        }
                        for domain, doc_id in self.first_priority_scope_entries
                    ],
                }
            ],
            "firstPriorityScopeEntries": [
                {
                    "domain": domain,
                    "docId": doc_id,
                    "title": self.documents[doc_id].title if doc_id in self.documents else "",
                }
                for domain, doc_id in self.first_priority_scope_entries
            ],
        }


def load_registry(registry_path: Path = DEFAULT_REGISTRY_PATH) -> RegistryData:
    workbook = _read_xlsx(registry_path)
    documents = _parse_documents(workbook.get("1.문서마스터", []))
    workflows = _parse_workflows(workbook.get("2.업무분류", []))
    bindings = _parse_bindings(workbook.get("3.업무-문서매핑", []))
    aliases_by_doc = _parse_aliases(workbook.get("6.문서매핑", []))

    workflow_ids_by_doc: dict[str, set[str]] = {doc_id: set() for doc_id in documents}
    domains_by_doc: dict[str, set[str]] = {doc_id: set() for doc_id in documents}
    po_domains_by_doc: dict[str, set[str]] = {doc_id: set() for doc_id in documents}
    for binding in bindings:
        if binding.doc_id not in documents:
            continue
        workflow_ids_by_doc.setdefault(binding.doc_id, set()).add(binding.workflow_id)
        workflow = workflows.get(binding.workflow_id)
        if workflow and workflow.domain:
            domains_by_doc.setdefault(binding.doc_id, set()).add(workflow.domain)
            po_domains_by_doc.setdefault(binding.doc_id, set()).add(po_domain_for_workflow_domain(workflow.domain))
    for doc_id, domains in FIRST_PRIORITY_DOMAINS_BY_DOC_ID.items():
        if doc_id in documents:
            po_domains_by_doc.setdefault(doc_id, set()).update(domains)

    enriched: dict[str, RegistryDocument] = {}
    for doc_id, doc in documents.items():
        alias_values = tuple(_dedupe([*doc.aliases, *aliases_by_doc.get(doc_id, [])]))
        enriched[doc_id] = RegistryDocument(
            doc_id=doc.doc_id,
            title=doc.title,
            issuer=doc.issuer,
            genre=doc.genre,
            structure=doc.structure,
            modality=doc.modality,
            sensitivity=doc.sensitivity,
            fields=doc.fields,
            notes=doc.notes,
            has_personal_info=doc.has_personal_info,
            personal_info_detail=doc.personal_info_detail,
            validation_rules=doc.validation_rules,
            validation_rule_codes=doc.validation_rule_codes,
            writing_method=doc.writing_method,
            aliases=alias_values,
            workflow_ids=tuple(sorted(workflow_ids_by_doc.get(doc_id, set()))),
            domains=tuple(sorted(domains_by_doc.get(doc_id, set()))),
            po_domains=_ordered_po_domains(po_domains_by_doc.get(doc_id, set())),
            is_first_priority=doc_id in FIRST_PRIORITY_DOC_IDS,
            first_priority_domains=FIRST_PRIORITY_DOMAINS_BY_DOC_ID.get(doc_id, ()),
        )
    return RegistryData(documents=enriched, workflows=workflows, bindings=bindings, source_path=registry_path)


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value or "").lower()
    normalized = normalized.replace("사본", "")
    normalized = re.sub(r"[\s\-_/·()\[\]{}.,:;|]+", "", normalized)
    normalized = re.sub(r"[^0-9a-z가-힣]+", "", normalized)
    return normalized


def slugify_title(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value or "document").strip()
    slug = re.sub(r"[\\/:*?\"<>|\s]+", "_", normalized)
    slug = re.sub(r"_+", "_", slug).strip("._ ")
    return slug[:80] or "document"


def _parse_documents(rows: list[list[str]]) -> dict[str, RegistryDocument]:
    parsed = _dict_rows(rows)
    documents: dict[str, RegistryDocument] = {}
    for row in parsed:
        doc_id = row.get("문서ID", "").strip()
        title = row.get("문서명", "").strip()
        if not doc_id or not title:
            continue
        documents[doc_id] = RegistryDocument(
            doc_id=doc_id,
            title=title,
            issuer=row.get("발급주체", ""),
            genre=row.get("기능/장르", ""),
            structure=row.get("구조유형", ""),
            modality=row.get("Modality", ""),
            sensitivity=row.get("민감도", ""),
            fields=row.get("핵심 추출필드 (베이스 스키마)", ""),
            notes=row.get("비고", ""),
            has_personal_info=row.get("개인정보 포함여부", ""),
            personal_info_detail=row.get("포함 개인정보(상세)", ""),
            validation_rules=row.get("검증룰(문서별)", ""),
            validation_rule_codes=row.get("검증룰코드(VAL)", ""),
            writing_method=row.get("작성방식", ""),
        )
    return documents


def _parse_workflows(rows: list[list[str]]) -> dict[str, RegistryWorkflow]:
    parsed = _dict_rows(rows)
    workflows: dict[str, RegistryWorkflow] = {}
    for row in parsed:
        workflow_id = row.get("업무ID", "").strip()
        if not workflow_id:
            continue
        workflows[workflow_id] = RegistryWorkflow(
            workflow_id=workflow_id,
            domain=row.get("산업도메인", ""),
            name=row.get("업무명", ""),
            description=row.get("업무 설명", ""),
            output_doc_id=row.get("산출물ID", ""),
        )
    return workflows


def _parse_bindings(rows: list[list[str]]) -> list[RegistryBinding]:
    parsed = _dict_rows(rows)
    bindings: list[RegistryBinding] = []
    for row in parsed:
        workflow_id = row.get("업무ID", "").strip()
        doc_id = row.get("문서ID", "").strip()
        if not workflow_id or not doc_id:
            continue
        bindings.append(
            RegistryBinding(
                workflow_id=workflow_id,
                doc_id=doc_id,
                direction=row.get("방향(입력/산출)", ""),
                required=row.get("필수여부", ""),
                workflow_name=row.get("업무명", ""),
                doc_title=row.get("문서명", ""),
            )
        )
    return bindings


def _parse_aliases(rows: list[list[str]]) -> dict[str, list[str]]:
    parsed = _dict_rows(rows)
    aliases: dict[str, list[str]] = {}
    for row in parsed:
        doc_id = row.get("A 문서ID", "").strip()
        if not doc_id:
            continue
        values = [row.get("A 문서명", ""), row.get("B 문서유형", "")]
        split_values: list[str] = []
        for value in values:
            split_values.extend(piece.strip() for piece in re.split(r"[/,]", value or "") if piece.strip())
        aliases[doc_id] = _dedupe(split_values)
    return aliases


def _dict_rows(rows: list[list[str]]) -> list[dict[str, str]]:
    if not rows:
        return []
    header_index = 0
    for idx, row in enumerate(rows):
        if any(cell.strip() for cell in row):
            header_index = idx
            break
    headers = [cell.strip() for cell in rows[header_index]]
    result: list[dict[str, str]] = []
    for row in rows[header_index + 1 :]:
        if not any(cell.strip() for cell in row):
            continue
        item = {headers[idx]: row[idx].strip() if idx < len(row) else "" for idx in range(len(headers)) if headers[idx]}
        result.append(item)
    return result


def _read_xlsx(path: Path) -> dict[str, list[list[str]]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with zipfile.ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_targets = _sheet_targets(archive)
        return {name: _read_sheet(archive, target, shared_strings) for name, target in sheet_targets.items()}


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for si in root.findall("a:si", NS):
        values.append("".join(text.text or "" for text in si.findall(".//a:t", NS)))
    return values


def _sheet_targets(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    targets: dict[str, str] = {}
    for sheet in workbook.findall(".//a:sheet", NS):
        name = sheet.attrib["name"]
        rid = sheet.attrib[f"{{{REL_NS}}}id"]
        target = rid_to_target[rid].lstrip("/")
        if not target.startswith("xl/"):
            target = posixpath.normpath(posixpath.join("xl", target))
        targets[name] = target
    return targets


def _read_sheet(archive: zipfile.ZipFile, target: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(archive.read(target))
    rows: list[list[str]] = []
    for row_node in root.findall(".//a:sheetData/a:row", NS):
        row: list[str] = []
        for cell in row_node.findall("a:c", NS):
            column_index = _column_index(cell.attrib.get("r", "A1"))
            while len(row) < column_index:
                row.append("")
            row.append(_cell_value(cell, shared_strings))
        while row and row[-1] == "":
            row.pop()
        if any(cell.strip() for cell in row):
            rows.append(row)
    return rows


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//a:t", NS)).strip()
    value_node = cell.find("a:v", NS)
    if value_node is None or value_node.text is None:
        return ""
    raw = value_node.text
    if kind == "s" and raw:
        index = int(raw)
        return shared_strings[index].strip() if index < len(shared_strings) else ""
    return raw.strip()


def _column_index(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref)
    if not match:
        return 0
    index = 0
    for char in match.group(1):
        index = index * 26 + ord(char) - 64
    return index - 1


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        key = normalize_title(cleaned)
        if not cleaned or not key or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result
