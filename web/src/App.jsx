import { useEffect, useMemo, useRef, useState } from 'react';

const STATUS = ['use', 'keep'];
const STATUS_COLORS = { use: '#00c853', keep: '#448aff', ignore: '#ff5252' };
const STATUS_LABELS = { use: '사용', keep: '미사용', ignore: '기존 무시' };
const STATUS_DESCRIPTIONS = {
  use: '값/개인정보처럼 인페인팅 및 합성 대상으로 사용할 영역',
  keep: '양식/라벨처럼 합성 대상에서 제외하고 템플릿에 남길 영역',
  ignore: '기존 데이터 호환용 상태입니다. 새 지정은 삭제를 사용하세요.',
};
const BBOX_RENDER_MODES = ['handwriting', 'printed'];
const BBOX_RENDER_MODE_LABELS = { handwriting: '필기체', printed: '인쇄체' };
const BBOX_RENDER_MODE_DESCRIPTIONS = {
  handwriting: '답안지에 값만 출력하고 작업자가 빈 템플릿에 손글씨로 작성합니다.',
  printed: '수기 print pack 템플릿에 기존 스타일시트를 적용해 기계 렌더링합니다.',
};
const AUTO_TYPE_LABELS = {
  field_value: '값/개인정보',
  static_label: '고정 라벨',
  table_cell: '표 셀',
  long_paragraph: '긴 문단',
  header_footer: '머리말/꼬리말',
  stamp_or_seal: '도장/인장',
  watermark: '워터마크',
  unknown: '미분류',
};
const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'];
const UPLOAD_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.pdf', '.docx'];
const DEFAULT_OCR_PRESET = 'precise';
const DEFAULT_AUTHORING_AGENT_CAPABILITIES = {
  defaultModel: 'gpt-5.6-terra',
  defaultReasoningEffort: 'medium',
  executionModes: ['two_pass', 'single_pass', 'schema_only', 'faker_only', 'validation_repair', 'targeted_revision'],
  models: [
    {
      id: 'gpt-5.6-terra',
      label: 'gpt-5.6-terra',
      description: '',
      defaultReasoningEffort: 'medium',
      reasoningEfforts: ['low', 'medium', 'high', 'xhigh', 'max', 'ultra'],
      supportsFastMode: true,
    },
  ],
};
const AUTHORING_AGENT_EXECUTION_MODE_LABELS = {
  two_pass: '정밀 2패스',
  single_pass: '빠른 1패스',
  schema_only: 'Schema만 재실행',
  faker_only: 'Faker만 재실행',
  validation_repair: '검증 보정만',
  targeted_revision: '요청 보정',
};
const AUTHORING_AGENT_TERMINAL_STATUSES = new Set(['succeeded', 'failed', 'needs_repair', 'cancelled', 'timed_out', 'interrupted']);
const SELECTED_DOCUMENT_STORAGE_KEY = 'datafactory.selectedDocId';
const VIEWPORT_MODES = [
  ['auto', '자동'],
  ['fit', '전체 맞춤'],
  ['width', '폭 맞춤'],
  ['actual', '100%'],
];
const INTAKE_TABS = [
  ['importable', '자동 적재 가능'],
  ['needsReview', '확인 필요'],
  ['alreadyImported', '이미 적재됨'],
];
const WORKFLOW_STAGES = [
  ['sample', '샘플'],
  ['ocr', 'BBox'],
  ['review', '리뷰'],
  ['inpaint', '인페인트'],
  ['cleanup', '보정'],
  ['authoring', '합성'],
];
const COMPLETED_WORK_STATUSES = new Set(['approved', 'cleanroom_sample_ready', 'collection_done']);
const WORK_STATUS_GROUPS = [
  ['not_started', '미착수'],
  ['in_progress', '진행중'],
  ['done', '완료'],
];
const WORK_STATUS_GROUP_LABELS = Object.fromEntries(WORK_STATUS_GROUPS);
const WORK_STATUS_TO_GROUP = {
  missing: 'not_started',
  sample_imported: 'in_progress',
  ocr_done: 'in_progress',
  review_done: 'in_progress',
  inpaint_done: 'in_progress',
  cleanroom_sample_ready: 'done',
  collection_done: 'done',
  approved: 'done',
};
const SAMPLE_AVAILABILITY_FILTERS = [
  ['needs_synthesis', '합성 필요'],
  ['internal_ready', '사내 샘플 준비'],
  ['workbench_loaded', '워크벤치 적재'],
  ['finalized', '대체/완료'],
];
const SAMPLE_AVAILABILITY_LABELS = Object.fromEntries(SAMPLE_AVAILABILITY_FILTERS);
const WRITING_METHOD_LABELS = {
  인쇄: '인쇄',
  수기: '수기',
};

const DOCUMENT_TYPE_LABELS = {
  unknown: '미지정',
  structured_form: '정형양식',
  free_form: '자유양식',
  prose_report: '산문/보고서형',
};
const FEASIBILITY_LABELS = {
  unknown: '미정',
  possible: '작업 가능',
  impossible: '작업 불가',
};
const FALLBACK_FAKER_RULE_EXAMPLES = [
  'person.name_ko',
  'person.phone_kr',
  'person.rrn',
  'date.kr',
  'date.year',
  'date.month',
  'date.day',
  'money.krw',
  'company.name_ko',
  'address.ko',
  'free_text.short',
  'choice:남|여|기타',
  'literal:서울특별시',
  'template:{{company.name_ko}}는 {{date.kr}}에 설립됨',
  'pattern:###-####-####',
];

async function apiJson(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
  } catch (err) {
    throw new Error(`API 연결이 끊겼습니다. 장시간 작업은 백그라운드 작업 상태를 확인하세요. (${err.message || String(err)})`);
  }
  let payload;
  try {
    payload = await response.json();
  } catch (err) {
    throw new Error(`API 응답 JSON 파싱 실패: HTTP ${response.status}`);
  }
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function storedSelectedDocumentId() {
  if (typeof window === 'undefined') return '';
  try {
    return window.localStorage.getItem(SELECTED_DOCUMENT_STORAGE_KEY) || '';
  } catch {
    return '';
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function basename(path = '') {
  return path.split('/').filter(Boolean).at(-1) || path;
}
function normalizeSearchText(value = '') {
  return String(value || '').normalize('NFKC').toLowerCase().replace(/[\s_\-·.,()[\]{}]/g, '');
}
function toggleArrayValue(values, value) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}
function sampleAvailabilityGroup(item) {
  if (COMPLETED_WORK_STATUSES.has(item?.status)) return 'finalized';
  if ((item?.sampleCount || 0) > 0) return 'workbench_loaded';
  if ((item?.seeds || []).some((folder) => folder.matchedDocId === item?.docId)) return 'internal_ready';
  return 'needs_synthesis';
}
function workStatusGroup(item) {
  return item?.progressGroup || WORK_STATUS_TO_GROUP[item?.status] || 'not_started';
}
function matchesSampleAvailabilityFilter(item, selectedFilters = []) {
  return !selectedFilters.length || selectedFilters.includes(item?.sampleAvailability || sampleAvailabilityGroup(item));
}
function shortPath(path = '') {
  return path.split('/').filter(Boolean).slice(-3).join('/');
}
function isImagePath(path = '') {
  return IMAGE_EXTENSIONS.some((ext) => path.toLowerCase().endsWith(ext));
}
function fileUrl(path = '', version = 0) {
  const params = new URLSearchParams({ path });
  if (version) params.set('v', String(version));
  return `/api/file?${params.toString()}`;
}
function rgbToHex(value) {
  const rgb = Array.isArray(value) ? value : [32, 32, 32];
  return `#${rgb.slice(0, 3).map((channel) => Math.max(0, Math.min(255, Number(channel) || 0)).toString(16).padStart(2, '0')).join('')}`;
}
function hexToRgb(value) {
  const normalized = String(value || '').replace('#', '').trim();
  if (!/^[0-9a-fA-F]{6}$/.test(normalized)) return [32, 32, 32];
  return [0, 2, 4].map((offset) => parseInt(normalized.slice(offset, offset + 2), 16));
}
function clampNumber(value, min, max) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return min;
  return Math.max(min, Math.min(max, numeric));
}
function styleForField(field, styles = []) {
  if (!field) return null;
  return styles.find((style) => style.style_class === field.style_class) || styles.find((style) => style.style_class === 'body_default') || styles[0] || null;
}
function fontFamilyKey(value) {
  return String(value || '').trim().toLowerCase().replace(/^\./, '').replace(/[^0-9a-z가-힣]+/g, '');
}
function fontIdForStyle(style, fonts = []) {
  if (!style || !fonts.length) return '';
  const targetPath = style.font_path || '';
  const targetIndex = Number(style.font_index || 0);
  const byPath = fonts.find((font) => (font.path === targetPath || font.absolutePath === targetPath) && Number(font.index || 0) === targetIndex);
  if (byPath) return byPath.id;
  const family = fontFamilyKey(style.font_family);
  const weight = String(style.font_weight || '').toLowerCase();
  const fontStyle = String(style.font_style || '').toLowerCase();
  const byFamily = fonts.find((font) => fontFamilyKey(font.family) === family && (!weight || font.weight === weight) && (!fontStyle || font.fontStyle === fontStyle));
  return byFamily?.id || '';
}
function uniqueStyleClassId(base, styles = []) {
  const ids = new Set(styles.map((style) => style.style_class));
  const stem = String(base || 'style').replace(/[^a-zA-Z0-9_가-힣-]/g, '_') || 'style';
  let candidate = `style_${stem}`;
  let index = 2;
  while (ids.has(candidate)) {
    candidate = `style_${stem}_${index}`;
    index += 1;
  }
  return candidate;
}
function imageUrl(path = '', version = 0) {
  const params = new URLSearchParams({ path });
  if (version) params.set('v', String(version));
  return `/api/image?${params.toString()}`;
}
function isUploadFile(file) {
  const name = file?.name || '';
  return UPLOAD_EXTENSIONS.some((ext) => name.toLowerCase().endsWith(ext));
}
function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error(`파일을 읽을 수 없습니다: ${file.name}`));
    reader.readAsDataURL(file);
  });
}
function bboxOf(label) {
  const values = Array.isArray(label?.bbox) ? label.bbox.map((value) => Number(value)) : [0, 0, 0, 0];
  const [x = 0, y = 0, width = 0, height = 0] = values.map((value) => (Number.isFinite(value) ? value : 0));
  return { x, y, width, height, right: x + width, bottom: y + height, cx: x + width / 2, cy: y + height / 2 };
}
function polygonFromBox(box) {
  return [[box.x, box.y], [box.x + box.width, box.y], [box.x + box.width, box.y + box.height], [box.x, box.y + box.height]];
}
function clampBox(box, imageWidth, imageHeight, minSize = 4) {
  const width = Math.max(minSize, Math.min(Math.round(box.width), imageWidth));
  const height = Math.max(minSize, Math.min(Math.round(box.height), imageHeight));
  const x = Math.max(0, Math.min(Math.round(box.x), imageWidth - width));
  const y = Math.max(0, Math.min(Math.round(box.y), imageHeight - height));
  return { x, y, width, height };
}
function boxFromPoints(start, end, imageWidth, imageHeight) {
  const x1 = Math.max(0, Math.min(start.x, end.x));
  const y1 = Math.max(0, Math.min(start.y, end.y));
  const x2 = Math.min(imageWidth, Math.max(start.x, end.x));
  const y2 = Math.min(imageHeight, Math.max(start.y, end.y));
  return clampBox({ x: x1, y: y1, width: x2 - x1, height: y2 - y1 }, imageWidth, imageHeight);
}
function updatePolicyLabelBox(policy, labelId, box) {
  const bounded = clampBox(box, policy.image.width, policy.image.height);
  return {
    ...policy,
    labels: policy.labels.map((label) => (
      label.id === labelId
        ? {
            ...label,
            bbox: [bounded.x, bounded.y, bounded.width, bounded.height],
            polygon: polygonFromBox(bounded),
            reason: label.reason || 'manual bbox edit',
            original_text: label.original_text ?? label.text ?? '',
            original_confidence: label.original_confidence ?? label.confidence ?? null,
            ocr_text_stale: true,
            text_source: label.text_source || 'paddle_initial',
          }
        : label
    )),
  };
}
function addPolicyLabel(policy, box) {
  const bounded = clampBox(box, policy.image.width, policy.image.height);
  const label = {
    id: `manual_${Date.now()}`,
    text: '',
    confidence: null,
    bbox: [bounded.x, bounded.y, bounded.width, bounded.height],
    bbox_format: 'xywh',
    polygon: polygonFromBox(bounded),
    status: 'use',
    auto_type: 'field_value',
    reason: 'manual bbox',
    locked: false,
    notes: '',
    original_text: '',
    original_confidence: null,
    text_source: 'manual_bbox',
    ocr_text_stale: true,
    rec_text: '',
    rec_confidence: null,
    rec_engine: '',
    rec_updated_at: '',
    render_mode: 'printed',
  };
  return { policy: { ...policy, labels: [...policy.labels, label] }, label };
}
function summary(labels = []) {
  const byStatus = Object.fromEntries(STATUS.map((status) => [status, 0]));
  for (const label of labels) byStatus[label.status] = (byStatus[label.status] || 0) + 1;
  return { total: labels.length, byStatus };
}
function relabel(policy, selectedIds, status) {
  const ids = new Set(selectedIds);
  return { ...policy, labels: policy.labels.map((label) => (ids.has(label.id) ? { ...label, status } : label)) };
}
function staleRecognitionLabels(policy) {
  return (policy?.labels || []).filter((label) => label.ocr_text_stale);
}
function confidenceLabel(value) {
  return value === null || value === undefined ? '-' : `${Math.round(Number(value) * 1000) / 10}%`;
}
function recommendedRecognitionChoice(candidate) {
  const cropText = String(candidate?.text || '').trim();
  const oldText = String(candidate?.oldText || '').trim();
  const confidence = Number(candidate?.confidence || 0);
  if (!oldText && cropText) return 'crop';
  if (cropText && cropText !== oldText && confidence >= 0.95) return 'crop';
  if (oldText) return 'old';
  return cropText ? 'crop' : 'manual';
}
function autoViewportMode(width, height) {
  return (height || 1) >= (width || 1) ? 'width' : 'fit';
}
function isTextEditingTarget(target) {
  if (!target) return false;
  const tag = target.tagName?.toLowerCase();
  return tag === 'input' || tag === 'textarea' || tag === 'select' || target.isContentEditable;
}
function workItemStageState(item, stage) {
  if (!item) return false;
  if (COMPLETED_WORK_STATUSES.has(item.status)) return true;
  if (stage === 'sample') return item.sampleCount > 0 || item.status !== 'missing';
  if (stage === 'ocr') return Boolean(item.hasOcr);
  if (stage === 'review') return Boolean(item.hasReview);
  if (stage === 'inpaint') return Boolean(item.hasInpaint);
  if (stage === 'cleanup') return Boolean(item.hasInpaintCleanup);
  if (stage === 'authoring') return Boolean(item.hasAuthoring || item.hasAuthoringPreview);
  return false;
}
function workItemNextAction(item) {
  if (!item) return '';
  if (item.status === 'approved') return '완료: 검수 완료';
  if (item.status === 'cleanroom_sample_ready') return '완료: 클린룸 검수 완료';
  if (item.status === 'collection_done') return '완료: 실문서 수집 완료';
  if (isHandwritingItem(item)) {
    if (Number(item.handwritingAcceptedCount || 0) > 0) return `완료: 수기 스캔 ${item.handwritingAcceptedCount}건 매칭`;
    if (item.hasHandwritingPrintPack) return '다음: 수기 스캔 intake';
    if (item.hasAuthoring) return '다음: 수기 print pack 생성';
    return '다음: schema/faker';
  }
  if (item.isNonPipeline) return '합성 제외: 최종 샘플 준비 필요';
  if (item.hasPendingSeed) return '다음: seed 적재';
  if (item.needsSynthesis) return '다음: 합성 필요 여부 검토';
  if (!workItemStageState(item, 'sample')) return '다음: 샘플 추가';
  if (!workItemStageState(item, 'ocr')) return '다음: BBox 검출';
  if (!workItemStageState(item, 'review')) return '다음: BBox 리뷰';
  if (item.sampleKind === 'blank_template' && !workItemStageState(item, 'authoring')) return '다음: blank authoring';
  if (!workItemStageState(item, 'inpaint')) return '다음: 인페인팅';
  if (!workItemStageState(item, 'cleanup')) return '선택: 템플릿 클린업';
  if (!workItemStageState(item, 'authoring')) return '다음: schema/faker';
  return item.hasAuthoringPreview ? '완료: 합성 preview 있음' : '다음: preview 생성';
}
function workItemIsComplete(item) {
  return Boolean(item && (COMPLETED_WORK_STATUSES.has(item.status) || handwritingReady(item) || item.hasAuthoringPreview));
}
function workItemTone(item) {
  if (!item) return 'missing';
  if (item.isNonPipeline && !COMPLETED_WORK_STATUSES.has(item.status)) return 'non-pipeline';
  if (item.hasPendingSeed) return 'pending-seed';
  if (item.needsCollection) return 'needs-collection';
  if (COMPLETED_WORK_STATUSES.has(item.status)) return item.status;
  if (workItemStageState(item, 'authoring')) return 'authoring-ready';
  return item.status || 'missing';
}
function writingMethodLabel(itemOrDoc) {
  const method = String(itemOrDoc?.registry?.writingMethod || itemOrDoc?.writingMethod || '').trim();
  return WRITING_METHOD_LABELS[method] || '작성방식 미지정';
}
function writingMethodTone(itemOrDoc) {
  const method = String(itemOrDoc?.registry?.writingMethod || itemOrDoc?.writingMethod || '').trim();
  if (method === '수기') return 'handwriting';
  if (method === '인쇄') return 'printed';
  return 'unknown';
}
function isHandwritingItem(itemOrDoc) {
  return String(itemOrDoc?.registry?.writingMethod || itemOrDoc?.writingMethod || '').trim() === '수기';
}
function handwritingReady(item) {
  return isHandwritingItem(item) && Number(item?.handwritingAcceptedCount || 0) > 0;
}
function itemHasAuthoringBundle(item) {
  return Boolean(item?.latestAuthoringSchema && item?.latestAuthoringStylesheet && item?.latestAuthoringFakerProfile);
}
function finalExportReady(item, options = {}) {
  if (item?.latestCleanroomPdf && item?.isNonPipeline) return Boolean(item?.hasLibrarySampleAnnotation);
  if (isHandwritingItem(item)) {
    if (options.handwritingAsPrinted && itemHasAuthoringBundle(item)) return true;
    if (handwritingReady(item)) return true;
    return Boolean(item?.latestCleanroomPdf && item?.hasLibrarySampleAnnotation);
  }
  if (itemHasAuthoringBundle(item)) return true;
  return Boolean(item?.latestCleanroomPdf && item?.hasLibrarySampleAnnotation);
}
function cleanroomArtifact(item) {
  const cleanroom = item?.manifest?.artifacts?.cleanroom || {};
  return {
    previewPath: item?.latestCleanroomPreview || cleanroom.contact_sheet || '',
    pdfPath: item?.latestCleanroomPdf || cleanroom.pdf || '',
    contactSheet: item?.latestCleanroomContactSheet || cleanroom.contact_sheet || '',
    notes: item?.latestCleanroomNotes || cleanroom.notes || '',
    quality: cleanroom.quality_judgement || '',
  };
}
function finalOutputForItem(item, isNonPipeline, selectedSample = '') {
  if (!item) return null;
  const cleanroom = cleanroomArtifact(item);
  if (isNonPipeline && (cleanroom.previewPath || cleanroom.pdfPath)) {
    return { locked: true, kind: 'cleanroom', label: '클린룸 최종 샘플', ...cleanroom };
  }
  if (handwritingReady(item)) {
    return { locked: true, kind: 'handwriting', label: '수기 스캔 최종 샘플', previewPath: item.latestHandwritingAcceptedImage || '', pdfPath: '', contactSheet: '', notes: item.latestHandwritingMatchedGt || '', quality: `accepted ${item.handwritingAcceptedCount}` };
  }
  if (!isNonPipeline && !COMPLETED_WORK_STATUSES.has(item.status)) return null;
  if (cleanroom.previewPath || cleanroom.pdfPath) {
    return { locked: true, kind: 'cleanroom', label: '클린룸 최종 샘플', ...cleanroom };
  }
  if (item.status === 'collection_done') {
    const imageSample = (item.samples || []).find(isImagePath) || (isImagePath(selectedSample) ? selectedSample : '');
    const pdfSample = (item.samples || []).find((path) => path.toLowerCase().endsWith('.pdf')) || '';
    return { locked: true, kind: 'collection', label: '수집 완료 실문서', previewPath: imageSample || pdfSample, pdfPath: pdfSample, contactSheet: '', notes: '', quality: 'collection_done' };
  }
  if (isNonPipeline) {
    return { locked: true, kind: 'missing_final', label: '작업 불가 · 최종 샘플 미적재', previewPath: '', pdfPath: '', contactSheet: '', notes: '', quality: '' };
  }
  return null;
}
function assessmentTone(feasibility = 'unknown') {
  if (feasibility === 'possible') return 'possible';
  if (feasibility === 'impossible') return 'impossible';
  return 'unknown';
}
function emptyCleanupMask(width = 1200, height = 1600) {
  return {
    schema_version: 2,
    tool: 'paint_cleanup',
    image: { width, height },
    strokes: [],
    selected_color: [255, 255, 255],
    brush_radius: 10,
    updated_at: new Date().toISOString(),
  };
}
function cleanupStrokeId() {
  return `cleanup_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}
function localDateInputValue(now = new Date()) {
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}
function formatElapsedSeconds(value) {
  const total = Math.max(0, Math.round(Number(value) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours) return `${hours}시간 ${minutes}분 ${seconds}초`;
  if (minutes) return `${minutes}분 ${seconds}초`;
  return `${seconds}초`;
}
function pointDistance(left, right) {
  return Math.hypot((left?.x || 0) - (right?.x || 0), (left?.y || 0) - (right?.y || 0));
}

function App() {
  const suppressRestoreDocRef = useRef('');
  const [health, setHealth] = useState(null);
  const [registry, setRegistry] = useState(null);
  const [workPayload, setWorkPayload] = useState({ summary: {}, items: [] });
  const [assessmentPayload, setAssessmentPayload] = useState({ summary: {}, rows: [], documentTypes: [], feasibilityStatuses: [] });
  const [assessmentEdits, setAssessmentEdits] = useState({});
  const [assessmentExport, setAssessmentExport] = useState(null);
  const [finalExportCount, setFinalExportCount] = useState(1);
  const [authoringAsOfDate, setAuthoringAsOfDate] = useState(() => localDateInputValue());
  const [finalExportHandwritingAsPrinted, setFinalExportHandwritingAsPrinted] = useState(false);
  const [finalExportResult, setFinalExportResult] = useState(null);
  const [assessmentPopover, setAssessmentPopover] = useState(null);
  const [seedScan, setSeedScan] = useState({ summary: {}, folders: [] });
  const [selectedDocId, setSelectedDocId] = useState(storedSelectedDocumentId);
  const [selectedSample, setSelectedSample] = useState('');
  const [manualSeedFolder, setManualSeedFolder] = useState('');
  const [manualDocId, setManualDocId] = useState('');
  const [intakeTab, setIntakeTab] = useState('importable');
  const [search, setSearch] = useState('');
  const [domainFilters, setDomainFilters] = useState([]);
  const [statusFilters, setStatusFilters] = useState([]);
  const [sampleAvailabilityFilters, setSampleAvailabilityFilters] = useState([]);
  const [activeTargetGroupId, setActiveTargetGroupId] = useState('domain_금융');
  const [targetGroupDraft, setTargetGroupDraft] = useState({ id: '', label: '', description: '', scopeEntries: [] });
  const [targetGroupDocId, setTargetGroupDocId] = useState('');
  const [targetGroupEditing, setTargetGroupEditing] = useState(false);
  const [policy, setPolicy] = useState(null);
  const [reviewPath, setReviewPath] = useState('');
  const [selectedIds, setSelectedIds] = useState([]);
  const [lamaMaxSide, setLamaMaxSide] = useState(2400);
  const [ocrPreset] = useState(DEFAULT_OCR_PRESET);
  const [blankTemplateLineDetectEnabled, setBlankTemplateLineDetectEnabled] = useState(false);
  const [detectionResult, setDetectionResult] = useState(null);
  const [inpaintResult, setInpaintResult] = useState(null);
  const [inpaintVersion, setInpaintVersion] = useState(0);
  const [cleanupMask, setCleanupMask] = useState(emptyCleanupMask());
  const [cleanupDirty, setCleanupDirty] = useState(false);
  const [cleanupHistory, setCleanupHistory] = useState([]);
  const [selectedCleanupId, setSelectedCleanupId] = useState('');
  const [cleanupResult, setCleanupResult] = useState(null);
  const [cleanupVersion, setCleanupVersion] = useState(0);
  const [cleanupTool, setCleanupTool] = useState('brush');
  const [cleanupBaseImagePath, setCleanupBaseImagePath] = useState('');
  const [authoringResult, setAuthoringResult] = useState(null);
  const [authoringBatchResult, setAuthoringBatchResult] = useState(null);
  const [authoringBundle, setAuthoringBundle] = useState(null);
  const [authoringDirty, setAuthoringDirty] = useState(false);
  const [selectedAuthoringFieldId, setSelectedAuthoringFieldId] = useState('');
  const [selectedAuthoringFieldIds, setSelectedAuthoringFieldIds] = useState([]);
  const [authoringVersion, setAuthoringVersion] = useState(0);
  const [authoringViewMode, setAuthoringViewMode] = useState('template');
  const [authoringPreviewStale, setAuthoringPreviewStale] = useState(false);
  const [authoringLivePreview, setAuthoringLivePreview] = useState(null);
  const [authoringLivePreviewVersion, setAuthoringLivePreviewVersion] = useState(0);
  const authoringPreviewSeq = useRef(0);
  const authoringAgentTerminalRefreshRef = useRef('');
  const authoringAgentTerminalOffsetRef = useRef(0);
  const authoringAgentTerminalJobRef = useRef('');
  const authoringAgentTerminalPreRef = useRef(null);
  const authoringAgentStatusRefreshInFlightRef = useRef(false);
  const authoringAgentHydratedJobRef = useRef('');
  const [fontPayload, setFontPayload] = useState({ defaultFontId: '', fonts: [] });
  const [canvasMode, setCanvasMode] = useState('review');
  const [viewportMode, setViewportMode] = useState('auto');
  const [bboxEditMode, setBboxEditMode] = useState('select');
  const [reviewDirty, setReviewDirty] = useState(false);
  const [reviewHistory, setReviewHistory] = useState([]);
  const [dropActive, setDropActive] = useState(false);
  const [uploadFiles, setUploadFiles] = useState([]);
  const [uploadDocId, setUploadDocId] = useState('');
  const [uploadSearch, setUploadSearch] = useState('');
  const [uploadWarnings, setUploadWarnings] = useState([]);
  const [recognitionPopover, setRecognitionPopover] = useState(null);
  const [reviewPrunePopover, setReviewPrunePopover] = useState(null);
  const [seedRevertPreview, setSeedRevertPreview] = useState(null);
  const [reviewAudit, setReviewAudit] = useState(null);
  const [manualCleanupAudit, setManualCleanupAudit] = useState(null);
  const [authoringAgentInstruction, setAuthoringAgentInstruction] = useState('');
  const [authoringAgentRevisionInstruction, setAuthoringAgentRevisionInstruction] = useState('');
  const [authoringAgentCapabilities, setAuthoringAgentCapabilities] = useState(DEFAULT_AUTHORING_AGENT_CAPABILITIES);
  const [authoringAgentModel, setAuthoringAgentModel] = useState(DEFAULT_AUTHORING_AGENT_CAPABILITIES.defaultModel);
  const [authoringAgentReasoning, setAuthoringAgentReasoning] = useState('medium');
  const [authoringAgentFastMode, setAuthoringAgentFastMode] = useState(false);
  const [authoringAgentExecutionMode, setAuthoringAgentExecutionMode] = useState('two_pass');
  const [authoringAgentTimeBudgetEnabled, setAuthoringAgentTimeBudgetEnabled] = useState(false);
  const [authoringAgentTimeBudgetMinutes, setAuthoringAgentTimeBudgetMinutes] = useState(20);
  const [authoringAgentScalarPoolMinSize, setAuthoringAgentScalarPoolMinSize] = useState(20);
  const [authoringAgentRecordPoolMinSize, setAuthoringAgentRecordPoolMinSize] = useState(12);
  const [authoringAgentRequest, setAuthoringAgentRequest] = useState(null);
  const [authoringAgentRun, setAuthoringAgentRun] = useState(null);
  const [authoringAgentConflictPopover, setAuthoringAgentConflictPopover] = useState(null);
  const [authoringAgentConflictResolutions, setAuthoringAgentConflictResolutions] = useState({});
  const [focusedAuthoringAgentConflictId, setFocusedAuthoringAgentConflictId] = useState('');
  const [authoringAgentTerminalText, setAuthoringAgentTerminalText] = useState('');
  const [authoringAgentTerminalOpen, setAuthoringAgentTerminalOpen] = useState(false);
  const [authoringAgentTerminalAutoScroll, setAuthoringAgentTerminalAutoScroll] = useState(true);
  const [authoringAgentClock, setAuthoringAgentClock] = useState(Date.now());
  const [authoringLibrary, setAuthoringLibrary] = useState(null);
  const [authoringApprovalResult, setAuthoringApprovalResult] = useState(null);
  const [docxPipelineResult, setDocxPipelineResult] = useState(null);
  const [docxGenerateCount, setDocxGenerateCount] = useState(1);
  const [handwritingPrintPackResult, setHandwritingPrintPackResult] = useState(null);
  const [handwritingPackCount, setHandwritingPackCount] = useState(1);
  const [handwritingScanDir, setHandwritingScanDir] = useState('');
  const [handwritingScanFiles, setHandwritingScanFiles] = useState([]);
  const [handwritingScanWarnings, setHandwritingScanWarnings] = useState([]);
  const [handwritingScanPopoverOpen, setHandwritingScanPopoverOpen] = useState(false);
  const [handwritingScanIntakeResult, setHandwritingScanIntakeResult] = useState(null);
  const [authoringQrEditMode, setAuthoringQrEditMode] = useState(false);
  const [cleanroomLibrary, setCleanroomLibrary] = useState(null);
  const [cleanroomEditing, setCleanroomEditing] = useState(false);
  const [cleanroomFields, setCleanroomFields] = useState([]);
  const [cleanroomPrivacy, setCleanroomPrivacy] = useState({ include_keys: [], exclude_keys: [] });
  const [deepOcrPreview, setDeepOcrPreview] = useState(null);
  const [deepOcrSelections, setDeepOcrSelections] = useState({});
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  function selectAuthoringFields(ids) {
    const normalized = [...new Set((Array.isArray(ids) ? ids : [ids]).filter(Boolean))];
    setSelectedAuthoringFieldIds(normalized);
    setSelectedAuthoringFieldId(normalized[0] || '');
  }

  const documents = registry?.documents || [];
  const targetGroups = registry?.targetGroups || [];
  const emptyTargetGroup = { id: '', label: '목표 그룹 없음', description: '', protected: true, scopeEntries: [] };
  const activeTargetGroup = targetGroups.find((group) => group.id === activeTargetGroupId) || targetGroups[0] || emptyTargetGroup;
  const items = workPayload.items || [];
  const seedFolders = seedScan.folders || [];
  const selectedItem = useMemo(() => items.find((item) => item.docId === selectedDocId) || null, [items, selectedDocId]);
  const selectedDoc = selectedItem?.registry || documents.find((doc) => doc.docId === selectedDocId) || null;
  const selectedSampleKind = selectedItem?.sampleKind || 'filled_sample';
  const selectedIsBlankTemplate = selectedSampleKind === 'blank_template';
  const matchedSeedFolders = useMemo(() => seedFolders.filter((folder) => folder.matchedDocId === selectedDocId), [seedFolders, selectedDocId]);
  const intakeFolders = useMemo(() => seedFolders.filter((folder) => folder.status === intakeTab), [seedFolders, intakeTab]);
  const importableFolders = useMemo(() => seedFolders.filter((folder) => folder.status === 'importable' && folder.matchedDocId), [seedFolders]);
  const stats = useMemo(() => summary(policy?.labels || []), [policy]);
  const staleLabels = useMemo(() => staleRecognitionLabels(policy), [policy]);
  const selected = useMemo(() => new Set(selectedIds), [selectedIds]);
  const selectedReviewLabels = useMemo(() => (policy?.labels || []).filter((label) => selected.has(label.id)), [policy, selected]);
  const canUseLama = Boolean(health?.lama?.available);
  const isBusy = Boolean(busy);
  const uploadOpen = uploadFiles.length > 0;
  const assessmentRows = assessmentPayload.rows || [];
  const assessmentRowsByDocId = useMemo(() => {
    const byDoc = new Map();
    for (const row of assessmentRows) {
      if (!byDoc.has(row.docId)) byDoc.set(row.docId, []);
      byDoc.get(row.docId).push(row);
    }
    return byDoc;
  }, [assessmentRows]);
  const documentTypeOptions = assessmentPayload.documentTypes?.length ? assessmentPayload.documentTypes : Object.entries(DOCUMENT_TYPE_LABELS).map(([id, label]) => ({ id, label }));
  const feasibilityOptions = assessmentPayload.feasibilityStatuses?.length ? assessmentPayload.feasibilityStatuses : Object.entries(FEASIBILITY_LABELS).map(([id, label]) => ({ id, label }));
  const selectedAssessmentRows = useMemo(() => assessmentRowsByDocId.get(selectedDocId) || [], [assessmentRowsByDocId, selectedDocId]);
  const selectedIsNonPipeline = useMemo(
    () => selectedAssessmentRows.some((row) => row.feasibility === 'impossible'),
    [selectedAssessmentRows],
  );
  const selectedIsHandwriting = isHandwritingItem(selectedItem || selectedDoc);
  const authoringQrBox = authoringBundle?.schema?.handwriting?.qr_bbox || null;

  const enrichedItems = useMemo(() => items.map((item) => {
    const seeds = seedFolders.filter((folder) => folder.matchedDocId === item.docId);
    const hasPendingSeed = seeds.some((folder) => folder.status === 'importable');
    const hasInternalSample = seeds.length > 0;
    const sampleAvailable = (item.sampleCount || 0) > 0 || hasInternalSample || COMPLETED_WORK_STATUSES.has(item.status);
    const needsCollection = item.status === 'missing' && !sampleAvailable;
    const assessmentRowsForDoc = assessmentRowsByDocId.get(item.docId) || [];
    const isNonPipeline = assessmentRowsForDoc.some((row) => row.feasibility === 'impossible');
    const enriched = { ...item, seeds, hasPendingSeed, hasInternalSample, sampleAvailable, needsCollection, isNonPipeline, assessmentRows: assessmentRowsForDoc };
    const sampleAvailability = sampleAvailabilityGroup(enriched);
    return {
      ...enriched,
      sampleAvailability,
      sampleAvailabilityLabel: SAMPLE_AVAILABILITY_LABELS[sampleAvailability] || '미분류',
      needsSynthesis: sampleAvailability === 'needs_synthesis',
    };
  }), [items, seedFolders, assessmentRowsByDocId]);
  const needsCollectionItems = useMemo(() => enrichedItems.filter((item) => item.needsSynthesis), [enrichedItems]);
  const targetGroupDocOrder = useMemo(() => {
    const order = new Map();
    (activeTargetGroup.scopeEntries || []).forEach((entry, index) => {
      if (!order.has(entry.docId)) order.set(entry.docId, index);
    });
    return order;
  }, [activeTargetGroup]);
  const targetGroupAllItems = useMemo(() => (
    enrichedItems
      .filter((item) => targetGroupDocOrder.has(item.docId))
      .sort((left, right) => (targetGroupDocOrder.get(left.docId) ?? 9999) - (targetGroupDocOrder.get(right.docId) ?? 9999))
  ), [enrichedItems, targetGroupDocOrder]);
  const targetGroupItems = useMemo(() => (
    targetGroupAllItems.filter((item) => matchesSampleAvailabilityFilter(item, sampleAvailabilityFilters))
  ), [targetGroupAllItems, sampleAvailabilityFilters]);
  const targetGroupFinalExportReadyItems = useMemo(() => (
    targetGroupItems.filter((item) => finalExportReady(item, { handwritingAsPrinted: finalExportHandwritingAsPrinted }))
  ), [targetGroupItems, finalExportHandwritingAsPrinted]);
  const targetGroupFinalExportMissingItems = useMemo(() => (
    targetGroupItems.filter((item) => !finalExportReady(item, { handwritingAsPrinted: finalExportHandwritingAsPrinted }))
  ), [targetGroupItems, finalExportHandwritingAsPrinted]);
  const targetGroupFinalExportScopeEntries = useMemo(() => {
    const readyDocIds = new Set(targetGroupFinalExportReadyItems.map((item) => item.docId));
    const seen = new Set();
    const entries = [];
    for (const entry of activeTargetGroup.scopeEntries || []) {
      const docId = entry?.docId || entry?.doc_id || '';
      if (!readyDocIds.has(docId)) continue;
      const domain = entry?.domain || '';
      const key = `${domain}::${docId}`;
      if (seen.has(key)) continue;
      seen.add(key);
      entries.push({ domain, docId, title: entry?.title || '' });
    }
    if (entries.length) return entries;
    for (const item of targetGroupFinalExportReadyItems) {
      const doc = item.registry || {};
      const domain = doc.poDomains?.[0] || doc.domains?.[0] || '';
      const key = `${domain}::${item.docId}`;
      if (seen.has(key)) continue;
      seen.add(key);
      entries.push({ domain, docId: item.docId, title: item.title });
    }
    return entries;
  }, [activeTargetGroup, targetGroupFinalExportReadyItems]);
  const selectedManualCleanupItems = useMemo(() => (
    (manualCleanupAudit?.items || []).filter((item) => item.docId === selectedDocId)
  ), [manualCleanupAudit, selectedDocId]);
  const selectedFinalOutput = useMemo(
    () => finalOutputForItem(selectedItem, selectedIsNonPipeline, selectedSample),
    [selectedItem, selectedIsNonPipeline, selectedSample],
  );
  const selectedWorkflowLocked = Boolean(selectedFinalOutput?.locked && !cleanroomEditing);

  const filteredItems = useMemo(() => {
    const query = normalizeSearchText(search);
    const activeDomains = new Set(domainFilters);
    const activeStatuses = new Set(statusFilters);
    return enrichedItems.filter((item) => {
      const doc = item.registry || {};
      const haystack = normalizeSearchText(`${item.title} ${item.docId} ${(doc.aliases || []).join(' ')} ${(doc.poDomains || []).join(' ')} ${(doc.workflowDomains || doc.domains || []).join(' ')}`);
      if (query && !haystack.includes(query)) return false;
      if (activeDomains.size && !(doc.poDomains || []).some((domain) => activeDomains.has(domain))) return false;
      if (activeStatuses.size && !activeStatuses.has(workStatusGroup(item))) return false;
      if (!matchesSampleAvailabilityFilter(item, sampleAvailabilityFilters)) return false;
      return true;
    });
  }, [enrichedItems, search, domainFilters, statusFilters, sampleAvailabilityFilters]);

  const uploadDocOptions = useMemo(() => {
    const query = normalizeSearchText(uploadSearch);
    if (!query) return documents.slice(0, 40);
    return documents.filter((doc) => normalizeSearchText(`${doc.title} ${doc.docId} ${(doc.aliases || []).join(' ')} ${(doc.poDomains || []).join(' ')} ${(doc.workflowDomains || doc.domains || []).join(' ')}`).includes(query)).slice(0, 60);
  }, [documents, uploadSearch]);

  async function refreshAll({ preserveSelection = true } = {}) {
    const [nextHealth, nextRegistry, nextWork, nextAssessment, nextSeed, nextFonts, nextAuthoringLibrary, nextAgentCapabilities] = await Promise.all([
      apiJson('/api/health'),
      apiJson('/api/registry'),
      apiJson('/api/work-items'),
      apiJson('/api/first-priority/assessments'),
      apiJson('/api/seed/scan'),
      apiJson('/api/fonts').catch(() => ({ defaultFontId: '', fonts: [] })),
      apiJson('/api/authoring/library', { method: 'POST', body: JSON.stringify({}) }).catch(() => null),
      apiJson('/api/authoring/agent-capabilities').catch(() => DEFAULT_AUTHORING_AGENT_CAPABILITIES),
    ]);
    setHealth(nextHealth);
    setRegistry(nextRegistry);
    setWorkPayload(nextWork);
    setAssessmentPayload(nextAssessment);
    setSeedScan(nextSeed);
    setFontPayload(nextFonts);
    if (nextAuthoringLibrary) setAuthoringLibrary(nextAuthoringLibrary);
    const nextModels = Array.isArray(nextAgentCapabilities?.models) && nextAgentCapabilities.models.length
      ? nextAgentCapabilities.models
      : DEFAULT_AUTHORING_AGENT_CAPABILITIES.models;
    const normalizedCapabilities = { ...DEFAULT_AUTHORING_AGENT_CAPABILITIES, ...nextAgentCapabilities, models: nextModels };
    setAuthoringAgentCapabilities(normalizedCapabilities);
    setAuthoringAgentModel((current) => {
      const nextModel = nextModels.find((model) => model.id === current)
        || nextModels.find((model) => model.id === normalizedCapabilities.defaultModel)
        || nextModels[0];
      return nextModel.id;
    });
    setSelectedDocId((current) => {
      if (preserveSelection && current && nextWork.items.some((item) => item.docId === current)) return current;
      const pendingSeed = nextSeed.folders.find((folder) => folder.status === 'importable' && folder.matchedDocId);
      const imported = nextWork.items.find((item) => item.status !== 'missing');
      return pendingSeed?.matchedDocId || imported?.docId || nextWork.items[0]?.docId || '';
    });
  }

  function run(action) {
    action().catch((exc) => {
      setError(exc.message);
      setMessage('');
      setBusy('');
    });
  }

  function selectDocument(docId) {
    if (!docId || docId === selectedDocId) return;
    if (reviewDirty && !window.confirm('저장하지 않은 BBox 리뷰 수정이 있습니다. 문서를 전환할까요?')) return;
    setAssessmentPopover(null);
    setReviewPrunePopover(null);
    setAuthoringAgentConflictPopover(null);
    setAuthoringAgentConflictResolutions({});
    setFocusedAuthoringAgentConflictId('');
    setSelectedDocId(docId);
  }

  function resetReviewHistory() {
    setReviewHistory([]);
  }

  function resetCleanupState(width = policy?.image?.width || 1200, height = policy?.image?.height || 1600) {
    setCleanupMask(emptyCleanupMask(width, height));
    setCleanupDirty(false);
    setCleanupHistory([]);
    setSelectedCleanupId('');
    setCleanupResult(null);
    setCleanupVersion(0);
    setCleanupTool('brush');
    setCleanupBaseImagePath('');
  }

  function setEditedPolicy(nextPolicy, options = {}) {
    const { remember = true, snapshot = policy } = options;
    if (remember && snapshot) {
      setReviewHistory((current) => [...current.slice(-49), snapshot]);
    }
    setPolicy(nextPolicy);
    setReviewDirty(true);
  }

  function undoReview() {
    if (!reviewHistory.length || !policy) return;
    const previous = reviewHistory[reviewHistory.length - 1];
    const nextHistory = reviewHistory.slice(0, -1);
    const validIds = new Set((previous.labels || []).map((label) => label.id));
    setPolicy(previous);
    setReviewHistory(nextHistory);
    setSelectedIds((current) => current.filter((id) => validIds.has(id)));
    setReviewDirty(nextHistory.length > 0);
    setMessage('BBox 변경을 실행 취소했습니다.');
  }

  function deleteSelectedBboxes() {
    if (!policy || !selectedIds.length) return;
    const ids = new Set(selectedIds);
    setEditedPolicy({ ...policy, labels: policy.labels.filter((label) => !ids.has(label.id)) });
    setSelectedIds([]);
    setMessage(`선택 BBox ${ids.size}개를 삭제했습니다. 실행 취소할 수 있습니다.`);
  }

  function editTargetGroup(group = activeTargetGroup) {
    setTargetGroupDraft({
      id: group?.protected ? '' : (group?.id || ''),
      label: group?.protected ? `${group.label} 복사본` : (group?.label || ''),
      description: group?.description || '',
      scopeEntries: (group?.scopeEntries || []).map((entry) => ({ domain: entry.domain || '', docId: entry.docId, title: entry.title || '' })),
    });
    setTargetGroupDocId(selectedDocId || documents[0]?.docId || '');
    setTargetGroupEditing(true);
  }

  function createTargetGroupDraft() {
    setTargetGroupDraft({
      id: '',
      label: '',
      description: '',
      scopeEntries: selectedDocId && selectedDoc ? [{ domain: selectedDoc.poDomains?.[0] || selectedDoc.domains?.[0] || '', docId: selectedDoc.docId, title: selectedDoc.title }] : [],
    });
    setTargetGroupDocId(selectedDocId || documents[0]?.docId || '');
    setTargetGroupEditing(true);
  }

  function targetGroupScopeDomainsForItem(item) {
    const poDomains = item?.registry?.poDomains || [];
    const active = domainFilters.filter((domain) => poDomains.includes(domain));
    if (active.length) return active;
    return [poDomains[0] || item?.registry?.domains?.[0] || ''];
  }

  function currentFilterLabel() {
    const parts = [];
    if (search.trim()) parts.push(`검색:${search.trim()}`);
    if (domainFilters.length) parts.push(domainFilters.join('+'));
    if (statusFilters.length) parts.push(statusFilters.map((id) => WORK_STATUS_GROUP_LABELS[id]).join('+'));
    if (sampleAvailabilityFilters.length) parts.push(sampleAvailabilityFilters.map((id) => SAMPLE_AVAILABILITY_LABELS[id]).join('+'));
    return parts.join(' · ') || '전체 문서';
  }

  function createTargetGroupDraftFromFilteredItems() {
    const seen = new Set();
    const scopeEntries = [];
    for (const item of filteredItems) {
      for (const domain of targetGroupScopeDomainsForItem(item)) {
        const key = `${domain}::${item.docId}`;
        if (seen.has(key)) continue;
        seen.add(key);
        scopeEntries.push({ domain, docId: item.docId, title: item.title });
      }
    }
    if (!scopeEntries.length) {
      setMessage('현재 필터 결과에 그룹으로 만들 문서가 없습니다.');
      return;
    }
    const filterLabel = currentFilterLabel();
    setTargetGroupDraft({
      id: '',
      label: `필터 그룹 - ${filterLabel}`.slice(0, 80),
      description: `문서 현황판 필터 결과에서 생성한 목표 그룹 초안입니다. 필터: ${filterLabel}`,
      scopeEntries,
    });
    setTargetGroupDocId(scopeEntries[0]?.docId || selectedDocId || documents[0]?.docId || '');
    setTargetGroupEditing(true);
    setMessage(`필터 결과 ${scopeEntries.length}개 scope를 목표 그룹 초안으로 불러왔습니다. 그룹명을 확인한 뒤 저장하세요.`);
  }

  function addDocToTargetGroupDraft(docId = targetGroupDocId) {
    const doc = documents.find((item) => item.docId === docId);
    if (!doc) return;
    setTargetGroupDraft((current) => {
      if ((current.scopeEntries || []).some((entry) => entry.docId === doc.docId)) return current;
      return { ...current, scopeEntries: [...(current.scopeEntries || []), { domain: doc.poDomains?.[0] || doc.domains?.[0] || '', docId: doc.docId, title: doc.title }] };
    });
  }

  function removeDocFromTargetGroupDraft(docId) {
    setTargetGroupDraft((current) => ({ ...current, scopeEntries: (current.scopeEntries || []).filter((entry) => entry.docId !== docId) }));
  }

  async function saveTargetGroupDraft() {
    if (!targetGroupDraft.label.trim() || !targetGroupDraft.scopeEntries.length) return;
    setBusy('targetGroupSave');
    setError('');
    try {
      const payload = await apiJson('/api/target-groups/save', {
        method: 'POST',
        body: JSON.stringify(targetGroupDraft),
      });
      setRegistry((current) => ({ ...(current || {}), targetGroups: payload.groups }));
      setActiveTargetGroupId(payload.group.id);
      setTargetGroupEditing(false);
      setMessage(`목표 그룹 저장 완료: ${payload.group.label}`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  async function deleteActiveTargetGroup() {
    if (!activeTargetGroup?.id) return;
    const actionText = activeTargetGroup.protected ? '숨김 처리' : '삭제';
    if (!window.confirm(`${activeTargetGroup.label} 목표 그룹을 ${actionText}할까요? 문서/산출물은 삭제하지 않고 그룹 목록에서만 제거합니다.`)) return;
    setBusy('targetGroupDelete');
    setError('');
    try {
      const payload = await apiJson('/api/target-groups/delete', {
        method: 'POST',
        body: JSON.stringify({ id: activeTargetGroup.id }),
      });
      setRegistry((current) => ({ ...(current || {}), targetGroups: payload.groups }));
      setActiveTargetGroupId(payload.groups[0]?.id || '');
      setTargetGroupEditing(false);
      setMessage(activeTargetGroup.protected ? '기본 목표 그룹을 숨김 처리했습니다.' : '목표 그룹을 삭제했습니다.');
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  function setSelectedBboxStatus(status) {
    if (!policy || !selectedIds.length || !STATUS.includes(status)) return;
    setEditedPolicy(relabel(policy, selectedIds, status));
    setMessage(`선택 BBox ${selectedIds.length}개 → ${STATUS_LABELS[status]}`);
  }


  async function scanReviewLegacyIssues() {
    setBusy('reviewAudit');
    setError('');
    try {
      const payload = await apiJson('/api/audit/reviews');
      setReviewAudit(payload);
      setMessage(`Review legacy 스캔 완료: ignore bbox ${payload.summary.ignoreCount}개 / 문서 ${payload.summary.documentCount}종`);
    } finally {
      setBusy('');
    }
  }

  async function removeCurrentIgnoreBboxes() {
    if (!policy || !reviewPath || stats.byStatus.ignore <= 0) return;
    if (!window.confirm(`현재 리뷰의 기존 무시(ignore) bbox ${stats.byStatus.ignore}개를 백업 후 제거할까요?`)) return;
    setBusy('removeIgnore');
    setError('');
    try {
      const payload = await apiJson('/api/review/remove-ignore', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId, reviewPath }),
      });
      setPolicy(payload.policy);
      setSelectedIds([]);
      setReviewDirty(false);
      setMessage(`ignore bbox 제거 완료: ${payload.removed}개 · 백업 ${payload.backup?.dir || '없음'}`);
      await refreshAll({ preserveSelection: true });
      await scanReviewLegacyIssues();
    } finally {
      setBusy('');
    }
  }

  async function scanManualCleanupLegacy() {
    setBusy('manualCleanupAudit');
    setError('');
    try {
      const payload = await apiJson('/api/audit/manual-cleanup');
      setManualCleanupAudit(payload);
      setMessage(`manual_cleanup 스캔 완료: ${payload.summary.legacyCleanupCount}개`);
    } finally {
      setBusy('');
    }
  }

  async function promoteManualCleanup(item) {
    if (!item?.cleanupDir) return;
    if (!window.confirm(`${item.title}의 manual_cleanup 결과를 최종 인페인트 결과로 승격하고 manual_cleanup 폴더를 백업 보관함으로 이동할까요?`)) return;
    setBusy('manualCleanupPromote');
    setError('');
    try {
      const payload = await apiJson('/api/manual-cleanup/promote', {
        method: 'POST',
        body: JSON.stringify({ docId: item.docId, cleanupDir: item.cleanupDir }),
      });
      setMessage(`manual_cleanup 승격 완료: ${payload.promoted.inpainted} · 백업 ${payload.backup}`);
      setManualCleanupAudit(null);
      await refreshAll({ preserveSelection: true });
      await scanManualCleanupLegacy();
    } finally {
      setBusy('');
    }
  }

  function authoringAgentOptions(mode = 'authoring', executionMode = authoringAgentExecutionMode) {
    return {
      mode,
      model: authoringAgentModel,
      reasoningEffort: authoringAgentReasoning,
      fastMode: authoringAgentFastMode,
      executionMode,
      timeBudgetMinutes: authoringAgentTimeBudgetEnabled ? clampNumber(authoringAgentTimeBudgetMinutes, 5, 60) : null,
      minPoolSize: clampNumber(authoringAgentScalarPoolMinSize, 1, 100),
      scalarPoolMinSize: clampNumber(authoringAgentScalarPoolMinSize, 1, 100),
      recordPoolMinSize: clampNumber(authoringAgentRecordPoolMinSize, 1, 100),
      asOfDate: authoringAsOfDate,
    };
  }

  async function createAuthoringAgentRequest(mode = 'authoring') {
    if (!selectedDocId) return;
    setBusy(mode === 'bbox_correction' ? 'authoringAgentBboxRequest' : 'authoringAgentRequest');
    setError('');
    try {
      const payload = await apiJson('/api/authoring/agent-request', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          sourceImage: selectedSample,
          reviewPath,
          instruction: authoringAgentInstruction,
          options: authoringAgentOptions(mode),
        }),
      });
      setAuthoringAgentRequest(payload);
      setMessage(`${mode === 'bbox_correction' ? 'BBox 보정' : 'Agent authoring'} 요청 패키지 생성 완료: ${payload.paths.request}${payload.paths.prompt ? ` · ${payload.paths.prompt}` : ''}`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  async function updateSelectedSampleKind(sampleKind) {
    if (!selectedDocId || selectedSampleKind === sampleKind) return;
    setBusy('sampleKind');
    setError('');
    try {
      const payload = await apiJson('/api/work-item/sample-kind', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId, sampleKind }),
      });
      setMessage(`샘플 유형 저장: ${payload.sampleKind === 'blank_template' ? '빈 템플릿' : payload.sampleKind === 'mixed_template' ? '혼합 템플릿' : '값 채워진 샘플'}`);
      if (sampleKind === 'blank_template') {
        setInpaintResult(null);
        setInpaintVersion(0);
        resetCleanupState();
        if (canvasMode === 'inpaint' || canvasMode === 'cleanup') setCanvasMode('review');
      }
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  function resetAuthoringAgentTerminal(jobPath = '') {
    authoringAgentTerminalJobRef.current = jobPath;
    authoringAgentTerminalOffsetRef.current = 0;
    setAuthoringAgentTerminalText('');
  }

  async function runAuthoringAgentInference(mode = 'authoring', executionMode = authoringAgentExecutionMode, instruction = authoringAgentInstruction) {
    if (!selectedDocId) return;
    const requestPath = (authoringAgentRun?.docId === selectedDocId ? authoringAgentRun?.requestPath : '')
      || (authoringAgentRequest?.docId === selectedDocId ? authoringAgentRequest?.paths?.request : '')
      || selectedItem?.latestAuthoringAgentRequest
      || '';
    if (['faker_only', 'validation_repair', 'targeted_revision'].includes(executionMode) && !requestPath) {
      setError(`${AUTHORING_AGENT_EXECUTION_MODE_LABELS[executionMode]}에는 기존 Agent request가 필요합니다.`);
      return;
    }
    if (executionMode === 'targeted_revision' && !instruction.trim()) {
      setError('요청 보정 내용을 입력하세요.');
      return;
    }
    setBusy(mode === 'bbox_correction' ? 'authoringAgentBboxRun' : 'authoringAgentRun');
    setError('');
    authoringAgentTerminalRefreshRef.current = '';
    resetAuthoringAgentTerminal();
    setAuthoringAgentTerminalOpen(true);
    try {
      const payload = await apiJson('/api/authoring/agent-run', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          sourceImage: selectedSample,
          reviewPath,
          instruction,
          options: authoringAgentOptions(mode, executionMode),
          ...(['schema_only', 'faker_only', 'validation_repair', 'targeted_revision'].includes(executionMode) && requestPath ? { requestPath } : {}),
        }),
      });
      resetAuthoringAgentTerminal(payload.jobPath || '');
      setAuthoringAgentRequest({ docId: payload.docId, paths: { request: payload.requestPath }, request: null });
      setAuthoringAgentRun(payload);
      if (executionMode === 'targeted_revision') setAuthoringAgentRevisionInstruction('');
      setMessage(`${mode === 'bbox_correction' ? 'BBox 보정 Agent' : AUTHORING_AGENT_EXECUTION_MODE_LABELS[executionMode] || 'Agent 추론'} job 시작: ${payload.jobPath}`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  async function refreshAuthoringAgentRunStatus(jobPath = (authoringAgentRun?.docId === selectedDocId ? authoringAgentRun?.jobPath : '') || selectedItem?.latestAuthoringAgentRun) {
    if (!jobPath && !selectedDocId) return null;
    if (authoringAgentStatusRefreshInFlightRef.current) return null;
    authoringAgentStatusRefreshInFlightRef.current = true;
    if (jobPath && authoringAgentTerminalJobRef.current !== jobPath) resetAuthoringAgentTerminal(jobPath);
    try {
      let payload = null;
      let chunkCount = 0;
      do {
        const query = new URLSearchParams(jobPath ? { jobPath } : { docId: selectedDocId });
        query.set('terminalOffset', String(authoringAgentTerminalOffsetRef.current));
        payload = await apiJson(`/api/authoring/agent-run-status?${query.toString()}`);
        if (payload.terminal) {
          const chunk = String(payload.terminal.text || '');
          authoringAgentTerminalOffsetRef.current = Number(payload.terminal.nextOffset || authoringAgentTerminalOffsetRef.current);
          if (chunk) setAuthoringAgentTerminalText((current) => `${current}${chunk}`.slice(-2_000_000));
        }
        chunkCount += 1;
      } while (payload?.terminal?.hasMore && chunkCount < 32);
      setAuthoringAgentRun(payload);
      const terminalKey = `${payload.jobPath || jobPath || ''}:${payload.status}:${payload.finishedAt || ''}`;
      if (payload.status === 'succeeded') {
        if (authoringAgentTerminalRefreshRef.current !== terminalKey) {
          authoringAgentTerminalRefreshRef.current = terminalKey;
          const scopeLabel = payload.validation?.scope === 'schema' ? 'Schema pass' : '전체 draft';
          setMessage(`Agent 추론 완료: ${scopeLabel} ${payload.validation?.summary?.present || 0}/${payload.validation?.summary?.required || 0}개 생성`);
          await refreshAll({ preserveSelection: true });
        }
      } else if (payload.status === 'needs_repair') {
        if (authoringAgentTerminalRefreshRef.current !== terminalKey) {
          authoringAgentTerminalRefreshRef.current = terminalKey;
          setMessage('Agent 추론은 끝났지만 draft 검증 보정이 필요합니다. 검증 보정만 재실행할 수 있습니다.');
          await refreshAll({ preserveSelection: true });
        }
      } else if (['failed', 'cancelled', 'timed_out', 'interrupted'].includes(payload.status)) {
        if (authoringAgentTerminalRefreshRef.current !== terminalKey) {
          authoringAgentTerminalRefreshRef.current = terminalKey;
          setError(`Agent 추론 ${payload.status}: ${payload.error || '실행을 완료하지 못했습니다.'}`);
          await refreshAll({ preserveSelection: true });
        }
      } else {
        authoringAgentTerminalRefreshRef.current = '';
      }
      return payload;
    } finally {
      authoringAgentStatusRefreshInFlightRef.current = false;
    }
  }

  async function cancelAuthoringAgentRun() {
    const jobPath = (authoringAgentRun?.docId === selectedDocId ? authoringAgentRun?.jobPath : '') || selectedItem?.latestAuthoringAgentRun;
    if (!jobPath) return;
    setBusy('authoringAgentCancel');
    setError('');
    try {
      const payload = await apiJson('/api/authoring/agent-run/cancel', {
        method: 'POST',
        body: JSON.stringify({ jobPath }),
      });
      setAuthoringAgentRun(payload);
      setMessage(payload.status === 'cancelled' ? 'Agent 실행을 취소했습니다.' : 'Agent 실행에 취소 신호를 보냈습니다.');
    } finally {
      setBusy('');
    }
  }


  function applyAuthoringRawJson(section, rawText) {
    if (!authoringBundle) return;
    try {
      const parsed = JSON.parse(rawText);
      setAuthoringBundle((current) => ({ ...current, [section]: parsed }));
      setAuthoringDirty(true);
      if (authoringResult?.paths?.image || selectedItem?.latestAuthoringPreview) setAuthoringPreviewStale(true);
      setMessage(`${section} raw JSON을 적용했습니다. 저장 전까지 파일에는 반영되지 않습니다.`);
    } catch (err) {
      setError(`${section} JSON 파싱 실패: ${err.message || String(err)}`);
    }
  }

  async function validateAuthoringConsistency({ strictReviewCoverage = true } = {}) {
    if (!authoringBundle) return null;
    setBusy('authoringValidate');
    setError('');
    try {
      const payload = await apiJson('/api/authoring/validate', {
        method: 'POST',
        body: JSON.stringify({
          schema: authoringBundle.schema,
          fakerProfile: authoringBundle.faker_profile,
          strictReviewCoverage,
        }),
      });
      setAuthoringBundle((current) => ({ ...(current || {}), consistency: payload.consistency }));
      const summary = payload.consistency?.summary || {};
      if (payload.consistency?.ready) {
        setMessage(`Authoring 정합성 OK: field ${summary.fieldCount || 0}개 · semantic leaf ${summary.semanticLeafCount || 0}개`);
      } else {
        setError(`Authoring 정합성 오류 ${summary.errorCount || 0}건: ${payload.consistency?.errors?.[0]?.code || 'unknown'}`);
      }
      return payload;
    } finally {
      setBusy('');
    }
  }

  function applySemanticSchemaRawJson(rawText) {
    if (!authoringBundle) return;
    try {
      const parsed = JSON.parse(rawText);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('semantic schema는 JSON object여야 합니다.');
      }
      setAuthoringBundle((current) => ({
        ...current,
        schema: syncSemanticSchemaToAuthoringFields(current.schema || {}, parsed),
      }));
      setAuthoringDirty(true);
      if (authoringResult?.paths?.image || selectedItem?.latestAuthoringPreview) setAuthoringPreviewStale(true);
      setMessage('Semantic schema primary JSON을 적용했고, full schema field binding의 semantic_path/export를 자동 연동했습니다.');
    } catch (err) {
      setError(`semantic schema JSON 파싱 실패: ${err.message || String(err)}`);
    }
  }

  async function loadAuthoringLibrary() {
    setBusy('authoringLibrary');
    setError('');
    try {
      const payload = await apiJson('/api/authoring/library', { method: 'POST', body: JSON.stringify({}) });
      setAuthoringLibrary(payload);
      setMessage(`Authoring 라이브러리 로드: profile ${payload.summary.profileTypeCount}종 · pool ${payload.summary.valuePoolCount}개 · 승인 ${payload.summary.approvalCount}건`);
    } finally {
      setBusy('');
    }
  }

  async function approveAuthoringDraftsToLibrary() {
    const requestPath = authoringAgentRequest?.paths?.request || selectedItem?.latestAuthoringAgentRequest;
    if (!requestPath) return;
    setBusy('authoringApproveDrafts');
    setError('');
    try {
      const payload = await apiJson('/api/authoring/approve-drafts', {
        method: 'POST',
        body: JSON.stringify({ requestPath, note: authoringAgentInstruction }),
      });
      setAuthoringApprovalResult(payload);
      await loadAuthoringLibrary();
      setMessage(`Authoring draft 라이브러리 승인 기록 완료: copied ${payload.summary.copied} · missing ${payload.summary.missing}`);
    } finally {
      setBusy('');
    }
  }

  function focusAuthoringAgentConflict(conflict) {
    if (!conflict) return;
    setFocusedAuthoringAgentConflictId(conflict.id);
    if (conflict.fieldId) selectAuthoringFields([conflict.fieldId]);
    setCanvasMode('authoring');
    setViewportMode('fit');
  }

  function setAuthoringAgentConflictResolution(conflictId, actionId) {
    setAuthoringAgentConflictResolutions((current) => ({ ...current, [conflictId]: actionId }));
  }

  function useRecommendedAuthoringAgentConflictResolutions() {
    const conflicts = authoringAgentConflictPopover?.conflicts || [];
    setAuthoringAgentConflictResolutions(Object.fromEntries(conflicts.map((conflict) => [conflict.id, conflict.recommendedAction])));
  }

  function closeAuthoringAgentConflictPopover() {
    setAuthoringAgentConflictPopover(null);
    setAuthoringAgentConflictResolutions({});
    setFocusedAuthoringAgentConflictId('');
  }

  async function commitAuthoringAgentDrafts(requestPath, preflight, resolutions = {}) {
    setBusy('authoringApplyAgentDrafts');
    setError('');
    try {
      const payload = await apiJson('/api/authoring/apply-agent-drafts', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          requestPath,
          preflightToken: preflight?.preflightToken || '',
          resolutions,
        }),
      });
      closeAuthoringAgentConflictPopover();
      setAuthoringBundle(payload);
      setAuthoringDirty(false);
      setAuthoringResult(null);
      setAuthoringVersion((value) => value + 1);
      const reconciliation = payload.bboxReconciliation;
      const reconciliationText = reconciliation?.resolvedCount ? ` · BBox 충돌 ${reconciliation.resolvedCount}건 반영` : '';
      setMessage(`Agent draft를 최종 Authoring에 적용했습니다: field ${payload.summary.field_count}개${reconciliationText}`);
      await refreshAll({ preserveSelection: true });
      return payload;
    } finally {
      setBusy('');
    }
  }

  async function applyAuthoringAgentDrafts() {
    const requestPath = authoringAgentRun?.requestPath || authoringAgentRequest?.paths?.request || selectedItem?.latestAuthoringAgentRequest;
    if (!selectedDocId || !requestPath) return;
    setBusy('authoringApplyAgentDrafts');
    setError('');
    try {
      const preflight = await apiJson('/api/authoring/apply-agent-drafts/preflight', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId, requestPath }),
      });
      if (preflight.conflicts?.length) {
        if (!authoringBundle) await loadAuthoringBundle({}, { silentBusy: true });
        setAuthoringAgentConflictPopover(preflight);
        setAuthoringAgentConflictResolutions({});
        focusAuthoringAgentConflict(preflight.conflicts[0]);
        setMessage(`Agent draft 적용 전에 BBox 변경 충돌 ${preflight.conflicts.length}건을 확인해 주세요.`);
        return preflight;
      }
      return await commitAuthoringAgentDrafts(requestPath, preflight, {});
    } finally {
      setBusy('');
    }
  }

  async function analyzeDocxTemplate() {
    if (!selectedDocId) return;
    setBusy('docxAnalyze');
    setError('');
    try {
      const payload = await apiJson('/api/docx/analyze', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId }),
      });
      setDocxPipelineResult(payload);
      setMessage(`DOCX 구조 분석 완료: table ${payload.summary?.tableCount || 0}개 · anchor ${payload.summary?.anchorCount || 0}개`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  async function draftDocxAuthoring() {
    if (!selectedDocId) return;
    setBusy('docxDraft');
    setError('');
    try {
      const payload = await apiJson('/api/docx/draft-authoring', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId }),
      });
      setDocxPipelineResult(payload);
      setAuthoringBundle({
        schema: payload.schema,
        stylesheet: payload.stylesheet,
        faker_profile: payload.faker_profile || payload.fakerProfile,
        summary: { field_count: payload.summary?.fieldCount || 0 },
      });
      setAuthoringDirty(false);
      setAuthoringResult(null);
      setAuthoringVersion((value) => value + 1);
      setMessage(`DOCX anchor 기반 Authoring 초안 생성: field ${payload.summary?.fieldCount || 0}개`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  async function generateDocxSamples() {
    if (!selectedDocId) return;
    const count = Math.max(1, Math.min(100, Number(docxGenerateCount) || 1));
    setDocxGenerateCount(count);
    setBusy('docxGenerate');
    setError('');
    try {
      const payload = await apiJson('/api/docx/generate', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          count,
          seed: 20260708,
          schemaPath: authoringPaths.schema || selectedItem?.latestAuthoringSchema || '',
          fakerProfilePath: authoringPaths.faker_profile || selectedItem?.latestAuthoringFakerProfile || '',
        }),
      });
      setDocxPipelineResult(payload);
      const rendererNote = payload.summary?.rendererAvailable ? '' : ' · LibreOffice 없음: PDF 렌더 대기';
      setMessage(`DOCX 값 주입 파이프라인 완료: ${payload.summary?.sampleCount || 0}건 · ${payload.summary?.status || 'unknown'}${rendererNote}`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  async function createHandwritingPrintPack() {
    if (!selectedDocId) return;
    const count = Math.max(1, Math.min(100, Number(handwritingPackCount) || 1));
    setHandwritingPackCount(count);
    setBusy('handwritingPrintPack');
    setError('');
    try {
      const payload = await apiJson('/api/handwriting/print-pack', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId, count, seed: 20260708, qrBbox: authoringQrBox || undefined }),
      });
      setHandwritingPrintPackResult(payload);
      setMessage(`수기 print pack 생성 완료: ${payload.summary?.sampleCount || count}건 · ${payload.paths?.runDir}`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  function openHandwritingScanPopover(files) {
    const accepted = Array.from(files || []).filter((file) => /\.(pdf|png|jpe?g|tiff?|bmp|webp)$/i.test(file.name));
    const rejected = Array.from(files || []).filter((file) => !accepted.includes(file));
    if (!accepted.length) {
      if ((files || []).length) setError('스캔 처리 지원 파일 형식은 PDF, PNG, JPG/JPEG, TIFF, BMP, WEBP입니다.');
      setHandwritingScanPopoverOpen(true);
      return;
    }
    setHandwritingScanFiles(accepted);
    setHandwritingScanWarnings(rejected.map((file) => `${file.name}: 지원하지 않는 형식이라 제외됨`));
    setHandwritingScanPopoverOpen(true);
    setError('');
  }

  function closeHandwritingScanPopover() {
    if (busy === 'handwritingScanUpload') return;
    setHandwritingScanFiles([]);
    setHandwritingScanWarnings([]);
    setHandwritingScanPopoverOpen(false);
  }

  async function uploadHandwritingScansAndIntake() {
    if (!handwritingScanFiles.length) return;
    setBusy('handwritingScanUpload');
    setError('');
    try {
      const files = await Promise.all(handwritingScanFiles.map(async (file) => ({
        name: file.name,
        contentType: file.type,
        dataBase64: await readFileAsDataUrl(file),
      })));
      const payload = await apiJson('/api/handwriting/scan-upload-intake', {
        method: 'POST',
        body: JSON.stringify({
          files,
        }),
      });
      setHandwritingScanFiles([]);
      setHandwritingScanWarnings([]);
      setHandwritingScanPopoverOpen(false);
      setHandwritingScanIntakeResult(payload);
      setMessage(`스캔 문서 처리 완료: accepted ${payload.summary?.acceptedCount || 0}건 · review ${payload.summary?.reviewRequiredCount || 0}건`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  async function runHandwritingScanIntake() {
    if (!selectedDocId) return;
    setBusy('handwritingScanIntake');
    setError('');
    try {
      const payload = await apiJson('/api/handwriting/scan-intake', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          scanDir: handwritingScanDir,
          printPackManifest: selectedItem?.latestHandwritingPrintPack || '',
        }),
      });
      setHandwritingScanIntakeResult(payload);
      setMessage(`수기 스캔 intake 완료: accepted ${payload.summary?.acceptedCount || 0}건 · review ${payload.summary?.reviewRequiredCount || 0}건`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  function assessmentValue(row, field) {
    return assessmentEdits[row.key]?.[field] ?? row[field] ?? '';
  }

  function setAssessmentEdit(row, patch) {
    setAssessmentEdits((current) => ({ ...current, [row.key]: { ...(current[row.key] || {}), ...patch } }));
  }

  function openAssessmentPopover(event, item) {
    event.preventDefault();
    event.stopPropagation();
    const rows = assessmentRowsByDocId.get(item.docId) || [];
    setAssessmentPopover({
      docId: item.docId,
      title: item.title,
      x: event.clientX,
      y: event.clientY,
      rows,
    });
  }

  async function saveAssessmentRow(row) {
    if (!row) return;
    const documentType = assessmentValue(row, 'documentType') || 'unknown';
    const feasibility = assessmentValue(row, 'feasibility') || 'unknown';
    const comment = assessmentValue(row, 'comment') || '';
    if (feasibility === 'impossible' && !comment.trim()) {
      setError('작업 불가 문서는 사유 또는 절충안을 반드시 입력해야 합니다.');
      setMessage('');
      return;
    }
    setBusy(`assessment:${row.key}`);
    setError('');
    try {
      const payload = await apiJson('/api/first-priority/assessment', {
        method: 'POST',
        body: JSON.stringify({ domain: row.domain, docId: row.docId, documentType, feasibility, comment }),
      });
      setAssessmentPayload(payload);
      setAssessmentEdits((current) => {
        const next = { ...current };
        delete next[row.key];
        return next;
      });
      setMessage(`판정 저장 완료: ${row.domain} · ${row.title}`);
    } finally {
      setBusy('');
    }
  }

  async function exportAssessmentXlsx() {
    setBusy('assessmentExport');
    setError('');
    try {
      const payload = await apiJson('/api/first-priority/export-xlsx', {
        method: 'POST',
        body: JSON.stringify({ outDir: 'outputs/document_assessment' }),
      });
      setAssessmentExport(payload);
      setMessage(`문서 판정표 XLSX 출력 완료: ${payload.path}`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  async function exportFinalResults() {
    const count = Math.max(1, Math.min(100, Number(finalExportCount) || 1));
    const scopeEntries = targetGroupFinalExportScopeEntries;
    if (!scopeEntries.length) {
      setMessage('현재 선택한 목표 그룹에 최종 산출물로 생성할 문서가 없습니다.');
      return;
    }
    setFinalExportCount(count);
    setBusy('finalResultsExport');
    setError('');
    setMessage(`${activeTargetGroup.label} ${targetGroupItems.length}종(${scopeEntries.length} scope)을 각 ${count}장씩 outputs/results에 최종 산출물로 생성 중입니다.${finalExportHandwritingAsPrinted ? ' 수기 문서는 임시 인쇄체 렌더링 모드로 처리합니다.' : ''}`);
    try {
      const payload = await apiJson('/api/results/final-export', {
        method: 'POST',
        body: JSON.stringify({
          count,
          outDir: 'outputs/results',
          seed: 20260703,
          renderScale: 2,
          clean: true,
          renderHandwritingAsPrinted: finalExportHandwritingAsPrinted,
          scopeEntries,
          asOfDate: authoringAsOfDate,
        }),
      });
      setFinalExportResult(payload);
      setMessage(`${activeTargetGroup.label} 최종 산출물 생성 완료: OK ${payload.summary.okCount}건 · 오류 ${payload.summary.errorCount}건 · PII ${payload.summary.piiFileCount || 0}개 · 경고 ${payload.summary.warningCount || 0}건 · ${payload.paths.outDir}`);
    } finally {
      setBusy('');
    }
  }

  function hasFiles(event) {
    return Array.from(event.dataTransfer?.types || []).includes('Files');
  }

  function openUploadPopover(files) {
    const accepted = Array.from(files || []).filter(isUploadFile);
    const rejected = Array.from(files || []).filter((file) => !isUploadFile(file));
    if (!accepted.length) {
      setError('지원 파일 형식은 PDF, PNG, JPG/JPEG, DOCX입니다.');
      setMessage('');
      return;
    }
    setUploadFiles(accepted);
    setUploadWarnings(rejected.map((file) => `${file.name}: 지원하지 않는 형식이라 제외됨`));
    setUploadSearch('');
    setUploadDocId(selectedDocId || documents[0]?.docId || '');
    setDropActive(false);
    setError('');
  }

  function handleDragOver(event) {
    if (!hasFiles(event)) return;
    event.preventDefault();
    setDropActive(true);
  }

  function handleDragLeave(event) {
    if (event.currentTarget === event.target) setDropActive(false);
  }

  function handleDrop(event) {
    if (!hasFiles(event)) return;
    event.preventDefault();
    openUploadPopover(event.dataTransfer.files);
  }

  function closeUploadPopover() {
    if (busy === 'upload') return;
    setUploadFiles([]);
    setUploadWarnings([]);
    setUploadSearch('');
  }

  async function uploadDroppedFiles() {
    if (!uploadFiles.length || !uploadDocId) return;
    setBusy('upload');
    setError('');
    setMessage(`${uploadFiles.length}개 파일을 seed_samples에 적재 중입니다.`);
    try {
      const files = await Promise.all(uploadFiles.map(async (file) => ({
        name: file.name,
        contentType: file.type,
        dataBase64: await readFileAsDataUrl(file),
      })));
      const payload = await apiJson('/api/seed/upload', {
        method: 'POST',
        body: JSON.stringify({ docId: uploadDocId, files }),
      });
      setUploadFiles([]);
      setUploadWarnings([]);
      suppressRestoreDocRef.current = payload.docId;
      await refreshAll({ preserveSelection: true });
      setSelectedDocId(payload.docId);
      if (payload.selectedSample) setSelectedSample(payload.selectedSample);
      setPolicy(null);
      setReviewPath('');
      setSelectedIds([]);
      setRecognitionPopover(null);
      setReviewDirty(false);
      resetReviewHistory();
      setDetectionResult(null);
      setInpaintResult(null);
      setInpaintVersion(0);
      resetCleanupState();
      setAuthoringResult(null);
      setAuthoringBatchResult(null);
      setAuthoringBundle(null);
      setAuthoringDirty(false);
      selectAuthoringFields([]);
      setAuthoringVersion(0);
      setAuthoringViewMode('template');
      setAuthoringPreviewStale(false);
      setCanvasMode('review');
      const renderedCount = payload.rendered?.length || 0;
      const warningText = payload.warnings?.length ? ` · 경고 ${payload.warnings.length}개` : '';
      setMessage(`드롭 적재 완료: ${payload.title} · 저장 ${payload.saved.length}개 · PDF 렌더링 ${renderedCount}개 · 신규 ${payload.import.copied.length}개${warningText}`);
    } finally {
      setBusy('');
    }
  }

  useEffect(() => {
    run(() => refreshAll({ preserveSelection: true }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedDocId) return;
    try {
      window.localStorage.setItem(SELECTED_DOCUMENT_STORAGE_KEY, selectedDocId);
    } catch {
      // Browser storage can be disabled without blocking the workbench.
    }
  }, [selectedDocId]);

  useEffect(() => {
    suppressRestoreDocRef.current = '';
    setManualDocId(selectedDocId || '');
    setManualSeedFolder('');
    setPolicy(null);
    setReviewPath('');
    setSelectedIds([]);
    setRecognitionPopover(null);
    resetReviewHistory();
    setDetectionResult(null);
    setBlankTemplateLineDetectEnabled(false);
    setInpaintResult(null);
    setInpaintVersion(0);
    resetCleanupState();
    setAuthoringResult(null);
    setAuthoringBatchResult(null);
    setAuthoringBundle(null);
    setAuthoringDirty(false);
    selectAuthoringFields([]);
    setAuthoringVersion(0);
    setAuthoringLivePreview(null);
    setAuthoringLivePreviewVersion(0);
    setAuthoringViewMode('template');
    setAuthoringPreviewStale(false);
    setAuthoringAgentRequest(null);
    setAuthoringAgentRun(null);
    setAuthoringAgentConflictPopover(null);
    setAuthoringAgentConflictResolutions({});
    setFocusedAuthoringAgentConflictId('');
    setAuthoringAgentRevisionInstruction('');
    resetAuthoringAgentTerminal();
    setAuthoringAgentTerminalOpen(false);
    setDocxPipelineResult(null);
    setCanvasMode('review');
    setBboxEditMode('select');
    setReviewDirty(false);
    setCleanroomLibrary(null);
    setCleanroomEditing(false);
    setCleanroomFields([]);
    setCleanroomPrivacy({ include_keys: [], exclude_keys: [] });
    setDeepOcrPreview(null);
    setDeepOcrSelections({});
  }, [selectedDocId]);

  useEffect(() => {
    if (!selectedIsBlankTemplate && blankTemplateLineDetectEnabled) {
      setBlankTemplateLineDetectEnabled(false);
    }
  }, [selectedIsBlankTemplate, blankTemplateLineDetectEnabled]);

  useEffect(() => {
    setSelectedSample((current) => {
      const cleanroomPages = cleanroomLibrary?.pages || [];
      if (cleanroomEditing) {
        if (current && cleanroomPages.some((page) => page.path === current)) return current;
        return cleanroomPages[0]?.path || '';
      }
      if (current && selectedItem?.samples?.includes(current)) return current;
      return selectedItem?.samples?.find(isImagePath) || selectedItem?.samples?.[0] || '';
    });
  }, [selectedItem?.docId, selectedItem?.samples, cleanroomEditing, cleanroomLibrary?.pages]);

  useEffect(() => {
    if (!cleanroomEditing || !policy) return;
    const useLabels = (policy.labels || []).filter((label) => label.status === 'use');
    setCleanroomFields((current) => {
      const byId = new Map(current.map((field) => [field.bboxLabelId, field]));
      return useLabels.map((label) => ({
        key: byId.get(label.id)?.key || '',
        value: byId.get(label.id)?.value ?? label.text ?? '',
        bboxLabelId: label.id,
      }));
    });
  }, [cleanroomEditing, policy]);

  useEffect(() => {
    if (!cleanroomEditing || !selectedSample) return;
    const page = (cleanroomLibrary?.pages || []).find((item) => item.path === selectedSample);
    const result = page?.deepOcr?.status === 'completed' ? page.deepOcr.result : null;
    setDeepOcrPreview(result);
    setDeepOcrSelections(defaultDeepOcrSelections(result));
  }, [cleanroomEditing, cleanroomLibrary?.pages, selectedSample]);

  useEffect(() => {
    if (!selectedItem || selectedItem.docId !== selectedDocId) return undefined;
    if (suppressRestoreDocRef.current === selectedItem.docId) return undefined;
    let cancelled = false;
    const version = Date.now();
    if (selectedWorkflowLocked) {
      setPolicy(null);
      setReviewPath('');
      setSelectedIds([]);
      setRecognitionPopover(null);
      resetReviewHistory();
      setInpaintResult(null);
      setInpaintVersion(0);
      resetCleanupState();
      setAuthoringResult(null);
      setAuthoringBatchResult(null);
      setAuthoringBundle(null);
      setAuthoringDirty(false);
      selectAuthoringFields([]);
      setAuthoringVersion(0);
      setAuthoringViewMode('template');
      setAuthoringPreviewStale(false);
      setCanvasMode('final');
      return undefined;
    }
    const hasInpainted = !selectedIsBlankTemplate && Boolean(selectedItem.latestInpainted);
    const hasAuthoring = Boolean(selectedItem.latestAuthoringSchema || selectedItem.latestAuthoringPreview);
    const hasAuthoringPreview = Boolean(selectedItem.latestAuthoringPreview);

    if (hasInpainted) {
      setInpaintVersion(version);
      setInpaintResult({
        docId: selectedItem.docId,
        paths: {
          inpainted: selectedItem.latestInpainted,
          comparison: selectedItem.latestInpaintComparison || '',
        },
        comparisonUrl: selectedItem.latestInpaintComparison ? fileUrl(selectedItem.latestInpaintComparison, version) : '',
        restored: true,
      });
      setCanvasMode('inpaint');
    } else {
      setInpaintResult(null);
      setInpaintVersion(0);
      resetCleanupState();
      setAuthoringResult(null);
      setAuthoringBatchResult(null);
      setAuthoringBundle(null);
      setAuthoringDirty(false);
      selectAuthoringFields([]);
      setAuthoringVersion(0);
      setAuthoringViewMode('template');
      setAuthoringPreviewStale(false);
      setCanvasMode('review');
    }

    if (selectedItem.latestAuthoringBatch) {
      setAuthoringBatchResult({ docId: selectedItem.docId, paths: { summary: selectedItem.latestAuthoringBatch }, restored: true });
    } else {
      setAuthoringBatchResult(null);
    }

    if (hasAuthoring) {
      setAuthoringVersion(hasAuthoringPreview ? version : 0);
      setAuthoringViewMode(hasAuthoringPreview ? 'preview' : 'template');
      setAuthoringPreviewStale(false);
      setAuthoringResult({
        docId: selectedItem.docId,
        paths: {
          image: selectedItem.latestAuthoringPreview || '',
          overlay: selectedItem.latestAuthoringOverlay || '',
          schema: selectedItem.latestAuthoringSchema || '',
          stylesheet: selectedItem.latestAuthoringStylesheet || '',
          faker_profile: selectedItem.latestAuthoringFakerProfile || '',
        },
        restored: true,
      });
    } else {
      setAuthoringResult(null);
      setAuthoringBatchResult(null);
      setAuthoringBundle(null);
      setAuthoringDirty(false);
      selectAuthoringFields([]);
      setAuthoringVersion(0);
      setAuthoringViewMode('template');
      setAuthoringPreviewStale(false);
    }

    if (!selectedItem.latestReview) {
      setPolicy(null);
      setReviewPath('');
      setSelectedIds([]);
      setRecognitionPopover(null);
      resetReviewHistory();
      return undefined;
    }

    apiJson(`/api/review?path=${encodeURIComponent(selectedItem.latestReview)}`)
      .then((loaded) => {
        if (cancelled) return;
	      setPolicy(loaded);
	      setReviewPath(loaded.review_path || selectedItem.latestReview);
	      setSelectedIds([]);
	      setRecognitionPopover(null);
	      setReviewDirty(false);
	      resetReviewHistory();
	      if (hasInpainted) setCanvasMode('inpaint');
      })
      .catch((exc) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedDocId, selectedWorkflowLocked, selectedIsBlankTemplate, selectedItem?.docId, selectedItem?.latestReview, selectedItem?.latestInpainted, selectedItem?.latestInpaintComparison, selectedItem?.latestAuthoringPreview, selectedItem?.latestAuthoringOverlay, selectedItem?.latestAuthoringSchema, selectedItem?.latestAuthoringStylesheet, selectedItem?.latestAuthoringFakerProfile, selectedItem?.latestAuthoringBatch]);

  useEffect(() => {
    if (!uploadOpen) return;
    if (!uploadDocId || !documents.some((doc) => doc.docId === uploadDocId)) {
      setUploadDocId(selectedDocId || documents[0]?.docId || '');
    }
  }, [documents, selectedDocId, uploadDocId, uploadOpen]);


  useEffect(() => {
    if (!targetGroups.length) {
      if (activeTargetGroupId) setActiveTargetGroupId('');
      return;
    }
    if (!targetGroups.some((group) => group.id === activeTargetGroupId)) {
      setActiveTargetGroupId(targetGroups[0].id);
    }
  }, [targetGroups, activeTargetGroupId]);

  async function importSeed(folderPath, docId = selectedDocId, { rememberMapping = false } = {}) {
    if (!folderPath || !docId) return;
    setBusy('import');
    setError('');
    setMessage('seed_samples 원본을 보존한 채 작업 폴더로 복제 적재 중입니다.');
    try {
      const payload = await apiJson('/api/seed/import', {
        method: 'POST',
        body: JSON.stringify({ seedFolder: folderPath, docId, rememberMapping }),
      });
      setSelectedDocId(payload.docId);
      setSelectedSample(payload.copied.find((item) => isImagePath(item.path))?.path || payload.manifest?.samples?.find((item) => isImagePath(item.path))?.path || '');
      const renderedText = payload.rendered?.length ? ` · PDF 렌더링 ${payload.rendered.length}개` : '';
      const warningText = payload.warnings?.length ? ` · 경고 ${payload.warnings.length}개` : '';
      setMessage(`샘플 적재 완료: ${payload.title} · 신규 ${payload.copied.length}개 · 중복 ${payload.skipped?.length || 0}개${renderedText}${warningText}`);
      await refreshAll();
    } finally {
      setBusy('');
    }
  }

  async function importAllImportable() {
    if (!importableFolders.length) return;
    setBusy('batchImport');
    setError('');
    setMessage(`자동 적재 가능 ${importableFolders.length}개 폴더를 일괄 적재 중입니다.`);
    try {
      const payload = await apiJson('/api/seed/import-batch', {
        method: 'POST',
        body: JSON.stringify({ items: importableFolders.map((folder) => ({ seedFolder: folder.folder, docId: folder.matchedDocId })) }),
      });
      const first = payload.results?.[0];
      if (first?.docId) setSelectedDocId(first.docId);
      const renderedText = payload.summary.rendered ? ` · PDF 렌더링 ${payload.summary.rendered}개` : '';
      const warningText = payload.summary.warnings ? ` · 경고 ${payload.summary.warnings}개` : '';
      setMessage(`일괄 적재 완료: 폴더 ${payload.summary.succeeded}개 · 신규 ${payload.summary.copied}개 · 중복 ${payload.summary.skipped}개${renderedText}${warningText}`);
      await refreshAll({ preserveSelection: false });
    } finally {
      setBusy('');
    }
  }

  async function trashSeedFolder(folderPath, folderName = '') {
    if (!folderPath) return;
    const label = folderName || basename(folderPath);
    if (!window.confirm(`seed_samples/${label} 폴더를 보관함으로 이동할까요?\n작업 폴더와 산출물은 유지되고 seed 원본 폴더만 이동됩니다.`)) return;
    setBusy('trashSeed');
    setError('');
    setMessage('seed_samples 폴더를 보관함으로 이동 중입니다.');
    try {
      const payload = await apiJson('/api/seed/trash', {
        method: 'POST',
        body: JSON.stringify({ seedFolder: folderPath }),
      });
      if (manualSeedFolder === folderPath) {
        setManualSeedFolder('');
        setManualDocId(selectedDocId || '');
      }
      setMessage(`Seed 폴더 보관함 이동 완료: ${payload.name} → ${payload.trashPath}`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  async function revertSelectedSeedImport() {
    if (!selectedDocId || !selectedItem?.sampleCount) return;
    const preview = seedRevertPreview?.docId === selectedDocId ? seedRevertPreview : await previewSelectedSeedRevert({ silent: true });
    const moveText = (preview?.willMove || []).map((item) => `- ${item.path} (${item.fileCount} files)`).join('\n');
    if (!window.confirm(`${selectedItem.title}의 적재 샘플과 OCR/BBox/인페인팅 산출물을 보관함으로 이동하고 미적재 상태로 되돌릴까요?\n\n이동 예정:\n${moveText || '- 이동 대상 없음'}\n\nAuthoring JSON과 cleanroom 산출물은 보존됩니다.`)) return;
    setBusy('seedRevert');
    setError('');
    setMessage('선택 문서의 seed 적재 상태를 되돌리는 중입니다.');
    try {
      const payload = await apiJson('/api/seed/revert', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId }),
      });
      setSelectedSample('');
      setPolicy(null);
      setReviewPath('');
      setSelectedIds([]);
      resetReviewHistory();
      setDetectionResult(null);
      setInpaintResult(null);
      setInpaintVersion(0);
      resetCleanupState();
      setSeedRevertPreview(null);
      setMessage(`Seed 적재 되돌리기 완료: ${payload.title} · 백업 ${payload.trashPath}`);
      await refreshAll({ preserveSelection: true });
    } finally {
      setBusy('');
    }
  }

  async function previewSelectedSeedRevert({ silent = false } = {}) {
    if (!selectedDocId) return null;
    if (!silent) {
      setBusy('seedRevertPreview');
      setError('');
    }
    try {
      const payload = await apiJson('/api/seed/revert-preview', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId }),
      });
      setSeedRevertPreview(payload);
      if (!silent) setMessage(`되돌리기 미리보기: 이동 대상 ${payload.willMove.length}개 · 백업 루트 ${payload.backupRoot}`);
      return payload;
    } finally {
      if (!silent) setBusy('');
    }
  }

  async function saveMappingAndImport(folder) {
    const docId = manualDocId || folder.candidates?.[0]?.docId || selectedDocId;
    if (!folder?.folder || !docId) return;
    await importSeed(folder.folder, docId, { rememberMapping: true });
    setIntakeTab('importable');
  }

  async function waitForOcrDetectionJob(jobPath) {
    while (true) {
      await delay(2000);
      const status = await apiJson(`/api/ocr/detect/status?jobPath=${encodeURIComponent(jobPath)}`);
      if (status.status === 'completed') return status.result || status;
      if (status.status === 'failed') throw new Error(status.error || 'BBox 검출 작업 실패');
      const started = status.startedAt ? ` · 시작 ${new Date(status.startedAt).toLocaleTimeString()}` : '';
      setMessage(`BBox 검출 작업 진행 중: ${status.engine || 'paddleocr'} ${status.preset || ocrPreset}${started}`);
    }
  }

  async function runOcrDetect() {
    if (!selectedSample || !selectedDocId) return;
    setBusy('detect');
    setError('');
    const includeLineDetection = selectedIsBlankTemplate && blankTemplateLineDetectEnabled;
    setMessage(includeLineDetection ? 'PaddleOCR BBox 검출 작업을 백그라운드로 시작합니다. 완료 후 선/그리드 후보를 추가 생성합니다.' : 'PaddleOCR BBox 검출 작업을 백그라운드로 시작합니다.');
    try {
      const job = await apiJson('/api/ocr/detect/start', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId, imagePath: selectedSample, engine: 'paddleocr', preset: ocrPreset, sampleKind: selectedSampleKind }),
      });
      setMessage(`BBox 검출 작업 시작: ${job.jobPath || job.jobId}`);
      const payload = await waitForOcrDetectionJob(job.jobPath);
      setDetectionResult(payload);
      setMessage(`BBox 검출 완료: ${payload.summary.detection_count}개 · ${payload.summary.preset || ocrPreset} · ${payload.summary.elapsed_seconds.toFixed(1)}초`);
      await createDraft(payload.paths.detections, { silentBusy: true });
      await refreshAll();
    } finally {
      setBusy('');
    }
  }

  async function createDraft(detectionsPath = selectedItem?.latestDetections, { silentBusy = false } = {}) {
    if (!detectionsPath || !selectedDocId) return;
    if (!silentBusy) setBusy('draft');
    setError('');
    setMessage('검출 결과에서 리뷰 정책을 생성 중입니다.');
    try {
      const payload = await apiJson('/api/review/draft', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          detectionsPath,
          sampleKind: selectedSampleKind,
          includeVisualLineDetection: selectedIsBlankTemplate && blankTemplateLineDetectEnabled,
        }),
      });
      setPolicy(payload.policy);
      setReviewPath(payload.paths.review);
      setSelectedIds([]);
      setRecognitionPopover(null);
      setReviewDirty(false);
      resetReviewHistory();
      setInpaintResult(null);
      setInpaintVersion(0);
      resetCleanupState();
      setAuthoringResult(null);
      setAuthoringBatchResult(null);
      setAuthoringBundle(null);
      setAuthoringDirty(false);
      selectAuthoringFields([]);
      setAuthoringVersion(0);
      setAuthoringViewMode('template');
      setAuthoringPreviewStale(false);
      setCanvasMode('review');
      suppressRestoreDocRef.current = selectedDocId;
      const visualCount = payload.visualDetection?.candidateCount || 0;
      const visualSkipped = selectedIsBlankTemplate && payload.visualDetection?.enabled === false;
      setMessage(
        visualCount
          ? `리뷰 정책 생성 완료: ${payload.paths.review} · 선/그리드 후보 ${visualCount}개`
          : visualSkipped
            ? `리뷰 정책 생성 완료: ${payload.paths.review} · 선/그리드 후보 미적용`
            : `리뷰 정책 생성 완료: ${payload.paths.review}`,
      );
      await refreshAll();
    } finally {
      if (!silentBusy) setBusy('');
    }
  }

  async function loadReview(path = selectedItem?.latestReview) {
    if (!path) return;
    setBusy('loadReview');
    setError('');
    try {
      const loaded = await apiJson(`/api/review?path=${encodeURIComponent(path)}`);
      setPolicy(loaded);
      setReviewPath(loaded.review_path || path);
      setSelectedIds([]);
      setRecognitionPopover(null);
      setReviewDirty(false);
      resetReviewHistory();
      setInpaintResult(null);
      setInpaintVersion(0);
      resetCleanupState();
      setAuthoringResult(null);
      setAuthoringBatchResult(null);
      setAuthoringBundle(null);
      setAuthoringDirty(false);
      selectAuthoringFields([]);
      setAuthoringVersion(0);
      setAuthoringViewMode('template');
      setAuthoringPreviewStale(false);
      setCanvasMode('review');
      setMessage(`리뷰 로드: ${loaded.review_path || path}`);
    } finally {
      setBusy('');
    }
  }

  async function runCropRecognition({ mode = 'apply', labelIds = null, policyOverride = null } = {}) {
    const targetPolicy = policyOverride || policy;
    if (!targetPolicy || !selectedDocId) return;
    const ids = labelIds || (selectedIds.length ? selectedIds : staleRecognitionLabels(targetPolicy).map((label) => label.id));
    if (!ids.length) {
      setMessage('재인식할 수정 BBox가 없습니다.');
      return;
    }
    setBusy('recognizeCrops');
    setError('');
    setMessage(`수정 BBox ${ids.length}개를 crop OCR로 재인식 중입니다.`);
    try {
      const payload = await apiJson('/api/review/recognize-crops', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          policy: targetPolicy,
          labelIds: ids,
          preset: ocrPreset,
          padding: 2,
        }),
      });
      if (!payload.candidates?.length) {
        setMessage('재인식 후보가 없습니다.');
        return;
      }
      const choices = Object.fromEntries(payload.candidates.map((candidate) => [
        candidate.id,
        {
          mode: recommendedRecognitionChoice(candidate),
          manual: candidate.oldText || candidate.text || '',
        },
      ]));
      setRecognitionPopover({ ...payload, mode, choices, policySnapshot: targetPolicy });
      setMessage(`Crop OCR 완료: ${payload.summary?.recognized || 0}/${payload.summary?.count || payload.candidates.length}개 인식`);
    } finally {
      setBusy('');
    }
  }

  function updateRecognitionChoice(labelId, patch) {
    setRecognitionPopover((current) => {
      if (!current) return current;
      return {
        ...current,
        choices: {
          ...(current.choices || {}),
          [labelId]: { ...(current.choices?.[labelId] || {}), ...patch },
        },
      };
    });
  }

  function buildPolicyWithRecognitionChoices({ forceMode = null } = {}) {
    if (!recognitionPopover || !policy) return policy;
    const candidates = new Map((recognitionPopover.candidates || []).map((candidate) => [candidate.id, candidate]));
    return {
      ...policy,
      labels: (policy.labels || []).map((label) => {
        const candidate = candidates.get(label.id);
        if (!candidate) return label;
        const choice = recognitionPopover.choices?.[label.id] || {};
        const mode = forceMode || choice.mode || recommendedRecognitionChoice(candidate);
        const manual = String(choice.manual ?? '').trim();
        const cropText = String(candidate.text || '').trim();
        const oldText = String(label.text ?? candidate.oldText ?? '').trim();
        const nextText = mode === 'manual' ? manual : (mode === 'crop' ? cropText : oldText);
        return {
          ...label,
          text: nextText,
          confidence: mode === 'crop' ? candidate.confidence ?? null : (mode === 'manual' ? null : label.confidence ?? null),
          original_text: label.original_text ?? candidate.oldText ?? oldText,
          original_confidence: label.original_confidence ?? label.confidence ?? null,
          text_source: mode === 'crop' ? 'paddle_recrop' : (mode === 'manual' ? 'manual_override' : 'initial_kept'),
          ocr_text_stale: false,
          rec_text: cropText,
          rec_confidence: candidate.confidence ?? null,
          rec_engine: recognitionPopover.summary?.engine || 'paddleocr',
          rec_updated_at: recognitionPopover.recUpdatedAt || new Date().toISOString(),
        };
      }),
    };
  }

  async function applyRecognitionChoices({ saveAfter = false, forceMode = null } = {}) {
    const nextPolicy = buildPolicyWithRecognitionChoices({ forceMode });
    if (!nextPolicy) return;
    setRecognitionPopover(null);
    setEditedPolicy(nextPolicy, { snapshot: policy });
    setMessage(saveAfter ? '재인식 선택값을 적용하고 리뷰를 저장합니다.' : '재인식 선택값을 적용했습니다. 필요하면 리뷰 저장을 눌러 확정하세요.');
    if (saveAfter) await saveReview({ skipRecognition: true, policyOverride: nextPolicy });
  }

  async function fetchReviewPruneCandidates(targetPolicy) {
    if (!selectedDocId || !targetPolicy) return null;
    const paths = resolveAuthoringPaths();
    if (!paths.schema) return null;
    return apiJson('/api/authoring/review-prune-candidates', {
      method: 'POST',
      body: JSON.stringify({
        docId: selectedDocId,
        schemaPath: paths.schema,
        stylesheetPath: paths.stylesheet,
        fakerProfilePath: paths.faker_profile,
        policy: targetPolicy,
      }),
    });
  }

  async function saveReview({ skipRecognition = false, policyOverride = null, skipPruneConfirm = false, pruneAuthoring = false } = {}) {
    const targetPolicy = policyOverride || policy;
    if (!targetPolicy || !selectedDocId) return;
    const stale = staleRecognitionLabels(targetPolicy);
    if (!skipRecognition && stale.length) {
      await runCropRecognition({ mode: 'save', labelIds: stale.map((label) => label.id), policyOverride: targetPolicy });
      return;
    }
    if (!skipPruneConfirm) {
      const candidates = await fetchReviewPruneCandidates(targetPolicy);
      if ((candidates?.fields || []).length) {
        setReviewPrunePopover({ ...candidates, policy: targetPolicy });
        return;
      }
    }
    setBusy('save');
    setError('');
    try {
      const authoringPaths = resolveAuthoringPaths();
      const payload = await apiJson('/api/review/save', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          reviewPath,
          policy: targetPolicy,
          pruneAuthoring,
          schemaPath: authoringPaths.schema,
          stylesheetPath: authoringPaths.stylesheet,
          fakerProfilePath: authoringPaths.faker_profile,
        }),
      });
      setPolicy(payload.policy);
      setReviewPath(payload.paths.review);
      setRecognitionPopover(null);
      setReviewPrunePopover(null);
      setInpaintResult(null);
      setInpaintVersion(0);
      resetCleanupState();
      setAuthoringResult(null);
      setAuthoringBatchResult(null);
      setAuthoringBundle(null);
      setAuthoringDirty(false);
      selectAuthoringFields([]);
      setAuthoringVersion(0);
      setAuthoringViewMode('template');
      setAuthoringPreviewStale(false);
      setCanvasMode('review');
      setReviewDirty(false);
      resetReviewHistory();
      suppressRestoreDocRef.current = selectedDocId;
      const prunedCount = payload.prunedAuthoring?.removed_count || 0;
      setMessage(prunedCount ? `리뷰 저장 완료 · Authoring field ${prunedCount}개 삭제: ${payload.paths.review}` : `리뷰 저장 완료: ${payload.paths.review}`);
      await refreshAll();
    } finally {
      setBusy('');
    }
  }

  async function runInpaint() {
    if (!policy || !selectedDocId) return;
    setBusy('inpaint');
    setError('');
    setInpaintResult(null);
    resetCleanupState(policy.image?.width, policy.image?.height);
    setMessage(`LaMa 인페인팅 실행 중입니다. max_side=${lamaMaxSide}`);
    try {
      const payload = await apiJson('/api/inpaint', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId, reviewPath, policy, method: 'lama', lamaMaxSide }),
      });
      if (payload.saved?.policy) {
        setPolicy(payload.saved.policy);
        setReviewPath(payload.saved.paths.review);
        setReviewDirty(false);
        resetReviewHistory();
      }
      suppressRestoreDocRef.current = '';
      const version = Date.now();
      setInpaintVersion(version);
      setInpaintResult({
        ...payload,
        comparisonUrl: payload.paths?.comparison ? fileUrl(payload.paths.comparison, version) : payload.comparisonUrl,
      });
      setCanvasMode('inpaint');
      setAuthoringResult(null);
      setAuthoringBatchResult(null);
      setAuthoringBundle(null);
      setAuthoringDirty(false);
      selectAuthoringFields([]);
      setAuthoringVersion(0);
      setAuthoringViewMode('template');
      setAuthoringPreviewStale(false);
      const elapsed = payload.summary.elapsed_seconds == null ? '' : ` · ${payload.summary.elapsed_seconds.toFixed(1)}초`;
      setMessage(`LaMa 완료: ${payload.summary.detection_count}개 사용 영역 · mask ${(payload.summary.mask_ratio * 100).toFixed(2)}%${elapsed}`);
      await refreshAll();
    } finally {
      setBusy('');
    }
  }

  function setEditedCleanupMask(nextMask, options = {}) {
    const { remember = true, snapshot = cleanupMask } = options;
    if (remember && snapshot) setCleanupHistory((current) => [...current.slice(-49), snapshot]);
    setCleanupMask(nextMask);
    setCleanupDirty(true);
  }

  function undoCleanupMask() {
    if (!cleanupHistory.length) return;
    const previous = cleanupHistory[cleanupHistory.length - 1];
    setCleanupMask(previous);
    setCleanupHistory((current) => current.slice(0, -1));
    setSelectedCleanupId('');
    setCleanupDirty(true);
    setMessage('브러시 보정 변경을 실행 취소했습니다.');
  }

  function addCleanupStroke(points, options = {}) {
    if (!policy || !points?.length) return;
    const base = cleanupMask || emptyCleanupMask(policy.image.width, policy.image.height);
    const color = options.color || base.selected_color || [255, 255, 255];
    const radius = options.radius || base.brush_radius || 10;
    const stroke = { id: cleanupStrokeId(), type: 'brush', color, radius, points };
    setEditedCleanupMask({ ...base, image: { width: policy.image.width, height: policy.image.height }, strokes: [...(base.strokes || []), stroke], selected_color: color, brush_radius: radius, updated_at: new Date().toISOString() });
    setSelectedCleanupId(stroke.id);
  }

  function updateCleanupPaintSettings(patch) {
    const base = cleanupMask || emptyCleanupMask(policy?.image?.width || 1200, policy?.image?.height || 1600);
    setCleanupMask({ ...base, ...patch, updated_at: new Date().toISOString() });
  }

  function sampleCleanupColor(color) {
    updateCleanupPaintSettings({ selected_color: color });
    setCleanupTool('brush');
    setMessage(`스포이드 색상 선택: #${color.map((channel) => channel.toString(16).padStart(2, '0')).join('')}`);
  }

  function deleteSelectedCleanupMask() {
    if (!selectedCleanupId || !cleanupMask?.strokes?.length) return;
    setEditedCleanupMask({ ...cleanupMask, strokes: cleanupMask.strokes.filter((stroke) => stroke.id !== selectedCleanupId), updated_at: new Date().toISOString() });
    setSelectedCleanupId('');
    setMessage('선택한 브러시 stroke를 삭제했습니다.');
  }

  async function loadCleanupMask({ silentBusy = false } = {}) {
    const sourceReviewPath = reviewPath || selectedItem?.latestReview || '';
    if (!selectedDocId || !sourceReviewPath || !policy) return null;
    if (!silentBusy) setBusy('cleanupLoad');
    setError('');
    try {
      const query = new URLSearchParams({ docId: selectedDocId, reviewPath: sourceReviewPath, baseImagePath: inpaintedPath || selectedItem?.latestInpainted || '' });
      const payload = await apiJson(`/api/cleanup-paint?${query.toString()}`);
      setCleanupMask(payload.paint || emptyCleanupMask(policy.image.width, policy.image.height));
      setCleanupBaseImagePath(payload.baseImagePath || inpaintedPath || selectedItem?.latestInpainted || '');
      setCleanupDirty(false);
      setCleanupHistory([]);
      setSelectedCleanupId('');
      if (payload.paths?.inpainted) {
        const version = Date.now();
        setCleanupVersion(version);
        setCleanupResult({ ...payload, comparisonUrl: payload.paths?.comparison ? fileUrl(payload.paths.comparison, version) : payload.comparisonUrl });
      } else {
        setCleanupResult(null);
        setCleanupVersion(0);
      }
      if (!silentBusy) setMessage(payload.exists ? '저장된 브러시 클린업을 불러왔습니다.' : '아직 저장된 브러시 클린업이 없습니다.');
      return payload;
    } finally {
      if (!silentBusy) setBusy('');
    }
  }

  async function saveCleanupMask({ silentBusy = false } = {}) {
    const sourceReviewPath = reviewPath || selectedItem?.latestReview || '';
    if (!selectedDocId || !sourceReviewPath || !policy) return null;
    if (!silentBusy) setBusy('cleanupSave');
    setError('');
    try {
      const baseImagePath = cleanupBaseImagePath || inpaintResult?.baseImagePath || inpaintedPath || selectedItem?.latestInpainted || '';
      const payload = await apiJson('/api/cleanup-paint', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId, reviewPath: sourceReviewPath, baseImagePath, paint: cleanupMask || emptyCleanupMask(policy.image.width, policy.image.height) }),
      });
      setCleanupMask(payload.paint);
      setCleanupBaseImagePath(payload.baseImagePath || baseImagePath);
      setCleanupDirty(false);
      setCleanupHistory([]);
      setSelectedCleanupId('');
      const version = Date.now();
      setCleanupVersion(version);
      setCleanupResult({ ...payload, comparisonUrl: payload.paths?.comparison ? fileUrl(payload.paths.comparison, version) : payload.comparisonUrl });
      setInpaintVersion(version);
      setInpaintResult((current) => ({ ...(current || {}), ...payload, paths: { ...(current?.paths || {}), ...payload.paths } }));
      if (!silentBusy) setMessage(`브러시 클린업 저장 완료: ${payload.paths.inpainted}`);
      return payload;
    } finally {
      if (!silentBusy) setBusy('');
    }
  }

  async function draftAuthoring() {
    const baseImagePath = inpaintResult?.paths?.inpainted || selectedItem?.latestInpainted || '';
    const sourceReviewPath = reviewPath || selectedItem?.latestReview || '';
    if (!selectedDocId || !sourceReviewPath || !baseImagePath) return;
    setBusy('authoringDraft');
    setError('');
    setMessage('리뷰 bbox에서 schema/stylesheet/faker 초안을 생성 중입니다.');
    try {
      const payload = await apiJson('/api/authoring/draft', {
        method: 'POST',
        body: JSON.stringify({ docId: selectedDocId, reviewPath: sourceReviewPath, baseImagePath }),
      });
      setAuthoringResult((current) => ({
        ...(current || {}),
        docId: selectedDocId,
        paths: { ...(current?.paths || {}), ...payload.paths },
        summary: payload.summary,
      }));
      await loadAuthoringBundle(payload.paths, { silentBusy: true });
      setCanvasMode('authoring');
      setAuthoringViewMode('template');
      setAuthoringPreviewStale(false);
      setMessage(`Authoring 초안 생성 완료: field ${payload.summary.field_count}개`);
      await refreshAll();
    } finally {
      setBusy('');
    }
  }

  function resolveAuthoringPaths(paths = {}) {
    return {
      schema: paths.schema || authoringBundle?.paths?.schema || authoringResult?.paths?.schema || selectedItem?.latestAuthoringSchema || '',
      stylesheet: paths.stylesheet || authoringBundle?.paths?.stylesheet || authoringResult?.paths?.stylesheet || selectedItem?.latestAuthoringStylesheet || '',
      faker_profile: paths.faker_profile || authoringBundle?.paths?.faker_profile || authoringResult?.paths?.faker_profile || selectedItem?.latestAuthoringFakerProfile || '',
    };
  }

  async function loadAuthoringBundle(paths = {}, { silentBusy = false } = {}) {
    const resolved = resolveAuthoringPaths(paths);
    if (!resolved.schema || !resolved.stylesheet || !resolved.faker_profile) return null;
    if (!silentBusy) setBusy('authoringLoad');
    setError('');
    try {
      const query = new URLSearchParams({
        schema: resolved.schema,
        stylesheet: resolved.stylesheet,
        fakerProfile: resolved.faker_profile,
      });
      const payload = await apiJson(`/api/authoring?${query.toString()}`);
      setAuthoringBundle(payload);
      if (payload.fonts?.items) setFontPayload({ defaultFontId: payload.fonts.defaultFontId || '', fonts: payload.fonts.items });
      setAuthoringDirty(false);
      {
        const fieldIds = (payload.schema?.fields || []).filter(hasRenderableAuthoringBbox).map((field) => field.field_id);
        const kept = selectedAuthoringFieldIds.filter((id) => fieldIds.includes(id));
        selectAuthoringFields(kept.length ? kept : (fieldIds[0] ? [fieldIds[0]] : []));
      }
      setAuthoringResult((current) => ({
        ...(current || {}),
        docId: selectedDocId,
        paths: { ...(current?.paths || {}), ...payload.paths },
        summary: payload.summary,
      }));
      setCanvasMode('authoring');
      setAuthoringViewMode('template');
      setAuthoringPreviewStale(false);
      if (!silentBusy) setMessage(`Authoring 불러오기 완료: field ${payload.summary.field_count}개`);
      return payload;
    } finally {
      if (!silentBusy) setBusy('');
    }
  }

  async function saveAuthoringBundle({ silentBusy = false } = {}) {
    if (!selectedDocId || !authoringBundle) return null;
    const resolved = resolveAuthoringPaths(authoringBundle.paths);
    if (!resolved.schema || !resolved.stylesheet || !resolved.faker_profile) return null;
    if (!silentBusy) setBusy('authoringSave');
    setError('');
    try {
      const payload = await apiJson('/api/authoring/save', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          schemaPath: resolved.schema,
          stylesheetPath: resolved.stylesheet,
          fakerProfilePath: resolved.faker_profile,
          schema: authoringBundle.schema,
          stylesheet: authoringBundle.stylesheet,
          fakerProfile: authoringBundle.faker_profile,
        }),
      });
      setAuthoringBundle(payload);
      if (payload.fonts?.items) setFontPayload({ defaultFontId: payload.fonts.defaultFontId || '', fonts: payload.fonts.items });
      setAuthoringDirty(false);
      {
        const fieldIds = (payload.schema?.fields || []).filter(hasRenderableAuthoringBbox).map((field) => field.field_id);
        const kept = selectedAuthoringFieldIds.filter((id) => fieldIds.includes(id));
        selectAuthoringFields(kept.length ? kept : (fieldIds[0] ? [fieldIds[0]] : []));
      }
      setAuthoringResult((current) => ({
        ...(current || {}),
        docId: selectedDocId,
        paths: { ...(current?.paths || {}), ...payload.paths },
        summary: payload.summary,
      }));
      if (!silentBusy) {
        setMessage(`Authoring 저장 완료: field ${payload.summary.field_count}개`);
        await refreshAll();
      }
      return payload;
    } finally {
      if (!silentBusy) setBusy('');
    }
  }

  function updateDocumentPrivacyKey(key, mode) {
    if (!key || !authoringBundle) return;
    setAuthoringBundle((current) => {
      const currentPrivacy = current.schema?.privacy || {};
      const include = new Set(currentPrivacy.include_keys || []);
      const exclude = new Set(currentPrivacy.exclude_keys || []);
      include.delete(key);
      exclude.delete(key);
      if (mode === 'include') include.add(key);
      if (mode === 'exclude') exclude.add(key);
      return {
        ...current,
        schema: {
          ...current.schema,
          privacy: { include_keys: [...include], exclude_keys: [...exclude] },
        },
      };
    });
    setAuthoringDirty(true);
  }

  function defaultDeepOcrSelections(result) {
    return Object.fromEntries((result?.matches || []).map((match) => [
      String(match.fieldIndex),
      {
        enabled: match.status === 'exact' && Boolean(match.bboxLabelId),
        bboxLabelId: match.status === 'exact' ? (match.bboxLabelId || '') : '',
      },
    ]));
  }

  function setDeepOcrResult(result) {
    setDeepOcrPreview(result || null);
    setDeepOcrSelections(defaultDeepOcrSelections(result));
  }

  async function loadCleanroomLibrary({ edit = false } = {}) {
    if (!selectedDocId) return null;
    setBusy('cleanroomLibraryLoad');
    setError('');
    try {
      const payload = await apiJson(`/api/library-sample/cleanroom?docId=${encodeURIComponent(selectedDocId)}`);
      setCleanroomLibrary(payload);
      const annotation = payload.annotation || {};
      setCleanroomFields((annotation.fields || []).map((field) => ({
        key: field.key || '',
        value: field.value ?? '',
        bboxLabelId: field.bbox_label_id || field.bboxLabelId || '',
      })));
      setCleanroomPrivacy(annotation.privacy || { include_keys: [], exclude_keys: [] });
      if (edit) {
        setCleanroomEditing(true);
        const sourceImage = annotation.source_image || payload.pages?.[0]?.path || '';
        setSelectedSample(sourceImage);
        const page = (payload.pages || []).find((item) => item.path === sourceImage);
        setDeepOcrResult(page?.deepOcr?.status === 'completed' ? page.deepOcr.result : null);
        setCanvasMode('review');
        if (annotation.review_path) await loadReview(annotation.review_path);
      }
      setMessage(payload.ready ? 'Cleanroom 라이브러리 샘플 주석을 불러왔습니다.' : '대표 cleanroom 페이지를 선택하고 OCR/BBox 리뷰를 시작하세요.');
      return payload;
    } finally {
      setBusy('');
    }
  }

  async function waitForDeepOcrJob(jobPath) {
    while (true) {
      await delay(1000);
      const status = await apiJson(`/api/library-sample/cleanroom/deep-ocr/status?jobPath=${encodeURIComponent(jobPath)}`);
      if (status.status === 'completed') return status;
      if (status.status === 'failed') {
        const code = status.errorCode ? ` (${status.errorCode})` : '';
        throw new Error(`${status.error || 'Deep OCR 작업 실패'}${code}`);
      }
      setMessage('Deep OCR key/value 추출 작업이 진행 중입니다. 외부 API 응답을 기다리는 중입니다.');
    }
  }

  async function runDeepOcr({ forceRefresh = false } = {}) {
    if (!selectedDocId || !selectedSample || !policy) return;
    setBusy('deepOcr');
    setError('');
    setMessage(forceRefresh ? 'DeepAgent 외부 API를 다시 호출합니다.' : 'DeepAgent OCR 결과를 확인하고, 동일 이미지 캐시가 없으면 외부 API를 호출합니다.');
    try {
      const job = await apiJson('/api/library-sample/cleanroom/deep-ocr/start', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          sourceImage: selectedSample,
          policy,
          forceRefresh,
        }),
      });
      const completed = await waitForDeepOcrJob(job.jobPath);
      const result = completed.result || null;
      setDeepOcrResult(result);
      setCleanroomLibrary((current) => current ? {
        ...current,
        pages: (current.pages || []).map((page) => (page.path === selectedSample ? { ...page, deepOcr: completed } : page)),
      } : current);
      const summary = result?.summary || {};
      const cacheText = summary.cacheHit ? ' · 동일 이미지 캐시 사용' : ' · 외부 API 호출';
      setMessage(`Deep OCR 완료: ${summary.fieldCount || 0}개 · exact ${summary.exactCount || 0} · 확인 필요 ${(summary.ambiguousCount || 0) + (summary.unmatchedCount || 0)}${cacheText}`);
      return completed;
    } finally {
      setBusy('');
    }
  }

  function updateDeepOcrSelection(fieldIndex, patch) {
    setDeepOcrSelections((current) => ({
      ...current,
      [String(fieldIndex)]: { ...(current[String(fieldIndex)] || { enabled: false, bboxLabelId: '' }), ...patch },
    }));
  }

  function applyDeepOcrSelections() {
    if (!policy || !deepOcrPreview) return;
    const labelsById = new Map((policy.labels || []).map((label) => [label.id, label]));
    const accepted = [];
    const usedBboxIds = new Set();
    const usedKeys = new Set(cleanroomFields.filter((field) => field.key).map((field) => field.key));
    let skipped = 0;
    for (const match of deepOcrPreview.matches || []) {
      const selection = deepOcrSelections[String(match.fieldIndex)] || {};
      const bboxLabelId = String(selection.bboxLabelId || '');
      const key = String(match.key || '').trim();
      if (!selection.enabled) continue;
      const existing = cleanroomFields.find((field) => field.bboxLabelId === bboxLabelId);
      const duplicateKey = key && usedKeys.has(key) && existing?.key !== key;
      if (!bboxLabelId || !labelsById.has(bboxLabelId) || usedBboxIds.has(bboxLabelId) || duplicateKey) {
        skipped += 1;
        continue;
      }
      usedBboxIds.add(bboxLabelId);
      if (key) usedKeys.add(key);
      accepted.push({ bboxLabelId, key, value: String(match.value ?? '') });
    }
    if (!accepted.length) {
      setMessage(skipped ? `적용 가능한 선택이 없습니다. 중복 key/BBox 또는 유효하지 않은 매핑 ${skipped}건을 확인하세요.` : '적용할 Deep OCR 행을 선택하세요.');
      return;
    }
    const acceptedById = new Map(accepted.map((item) => [item.bboxLabelId, item]));
    setEditedPolicy({
      ...policy,
      labels: (policy.labels || []).map((label) => (acceptedById.has(label.id) ? { ...label, status: 'use' } : label)),
    });
    setCleanroomFields((current) => {
      const byId = new Map(current.map((field) => [field.bboxLabelId, field]));
      for (const item of accepted) {
        const existing = byId.get(item.bboxLabelId);
        byId.set(item.bboxLabelId, {
          bboxLabelId: item.bboxLabelId,
          key: existing?.key || item.key,
          value: existing?.value || item.value,
        });
      }
      return [...byId.values()];
    });
    setSelectedIds(accepted.map((item) => item.bboxLabelId));
    setMessage(`Deep OCR 매핑 ${accepted.length}건을 리뷰에 적용했습니다${skipped ? ` · 중복/오류 ${skipped}건 제외` : ''}. BBox 리뷰 저장 후 cleanroom 주석을 저장하세요.`);
  }

  function updateCleanroomField(bboxLabelId, patch) {
    const previous = cleanroomFields.find((field) => field.bboxLabelId === bboxLabelId);
    setCleanroomFields((current) => current.map((field) => (field.bboxLabelId === bboxLabelId ? { ...field, ...patch } : field)));
    if (previous && Object.prototype.hasOwnProperty.call(patch, 'key') && patch.key !== previous.key) {
      setCleanroomPrivacy((privacy) => {
        const include = new Set(privacy.include_keys || []);
        const exclude = new Set(privacy.exclude_keys || []);
        const mode = include.has(previous.key) ? 'include' : exclude.has(previous.key) ? 'exclude' : 'inherit';
        include.delete(previous.key);
        exclude.delete(previous.key);
        if (patch.key && mode === 'include') include.add(patch.key);
        if (patch.key && mode === 'exclude') exclude.add(patch.key);
        return { include_keys: [...include], exclude_keys: [...exclude] };
      });
    }
  }

  function updateCleanroomPrivacyKey(key, mode) {
    if (!key) return;
    setCleanroomPrivacy((current) => {
      const include = new Set(current.include_keys || []);
      const exclude = new Set(current.exclude_keys || []);
      include.delete(key);
      exclude.delete(key);
      if (mode === 'include') include.add(key);
      if (mode === 'exclude') exclude.add(key);
      return { include_keys: [...include], exclude_keys: [...exclude] };
    });
  }

  async function saveCleanroomLibrary() {
    if (!selectedDocId || !selectedSample || !reviewPath || !cleanroomFields.length) return;
    setBusy('cleanroomLibrarySave');
    setError('');
    try {
      const payload = await apiJson('/api/library-sample/cleanroom/save', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          sourceImage: selectedSample,
          reviewPath,
          fields: cleanroomFields,
          privacy: cleanroomPrivacy,
        }),
      });
      setCleanroomLibrary(payload);
      setCleanroomEditing(false);
      setMessage(`Cleanroom 라이브러리 샘플 주석 저장 완료: ${payload.annotationPath}`);
      await refreshAll({ preserveSelection: true });
      return payload;
    } finally {
      setBusy('');
    }
  }

  function updateAuthoringField(fieldId, patch) {
    if (!authoringBundle) return;
    const hasFakerRule = Object.prototype.hasOwnProperty.call(patch, 'faker_rule');
    setAuthoringBundle((current) => {
      const schema = {
        ...current.schema,
        fields: (current.schema?.fields || []).map((field) => {
          if (field.field_id !== fieldId) return field;
          const next = { ...field, ...patch };
          if (patch.export) {
            next.export = { ...(field.export || {}), ...patch.export };
          }
          if (hasFakerRule) {
            next.generator = patch.faker_rule;
            delete next.faker_rule;
          }
          if (patch.align || patch.valign || patch.overflow || patch.checkbox_style) {
            next.render_policy = {
              ...(field.render_policy || {}),
              ...(patch.align ? { align: patch.align } : {}),
              ...(patch.valign ? { valign: patch.valign } : {}),
              ...(patch.overflow ? { overflow: patch.overflow, fit: patch.overflow === 'shrink' ? 'shrink_to_fit' : 'clip' } : {}),
              ...(patch.checkbox_style ? { checkbox_style: patch.checkbox_style } : {}),
            };
            delete next.align;
            delete next.valign;
            delete next.overflow;
            delete next.checkbox_style;
          }
          return next;
        }),
      };
      const fieldGenerators = { ...(current.faker_profile?.field_generators || {}) };
      if (hasFakerRule) fieldGenerators[fieldId] = patch.faker_rule;
      return { ...current, schema, faker_profile: { ...current.faker_profile, field_generators: fieldGenerators } };
    });
    setAuthoringDirty(true);
    if (authoringResult?.paths?.image || selectedItem?.latestAuthoringPreview) setAuthoringPreviewStale(true);
  }

  function updateAuthoringStyle(fieldId, patch, { shared = false } = {}) {
    updateAuthoringStyles([fieldId], patch, { shared });
  }

  function updateAuthoringStyles(fieldIds, patch, { shared = false } = {}) {
    if (!authoringBundle) return;
    const targetIds = [...new Set((Array.isArray(fieldIds) ? fieldIds : [fieldIds]).filter(Boolean))];
    if (!targetIds.length) return;
    setAuthoringBundle((current) => {
      const fields = [...(current.schema?.fields || [])];
      const styles = current.stylesheet?.style_classes?.length ? [...current.stylesheet.style_classes] : [{ style_class: 'body_default' }];
      for (const fieldId of targetIds) {
        const prepared = prepareAuthoringStyleForField(fields, styles, fieldId, { shared });
        if (!prepared) continue;
        styles[prepared.styleIndex] = { ...styles[prepared.styleIndex], ...patch };
      }
      return {
        ...current,
        schema: { ...current.schema, fields },
        stylesheet: { ...current.stylesheet, style_classes: styles },
      };
    });
    setAuthoringDirty(true);
    if (authoringResult?.paths?.image || selectedItem?.latestAuthoringPreview) setAuthoringPreviewStale(true);
  }

  function prepareAuthoringStyleForField(fields, styles, fieldId, { shared = false } = {}) {
    const fieldIndex = fields.findIndex((field) => field.field_id === fieldId);
    if (fieldIndex < 0) return null;
    const field = fields[fieldIndex];
    let styleClass = field.style_class || 'body_default';
    let styleIndex = styles.findIndex((style) => style.style_class === styleClass);
    const sharedCount = fields.filter((item) => (item.style_class || 'body_default') === styleClass).length;
    if (!shared && (styleIndex < 0 || sharedCount > 1 || styleClass === 'body_default')) {
      const baseStyle = styleIndex >= 0 ? styles[styleIndex] : (styles[0] || { style_class: 'body_default' });
      styleClass = uniqueStyleClassId(fieldId, styles);
      styles.push({ ...baseStyle, style_class: styleClass, source_detection_ids: field.source_detection_id ? [field.source_detection_id] : [] });
      styleIndex = styles.length - 1;
      fields[fieldIndex] = { ...field, style_class: styleClass };
    }
    if (styleIndex < 0) {
      styles.push({ style_class: styleClass });
      styleIndex = styles.length - 1;
    }
    return { fieldIndex, styleIndex, styleClass };
  }

  function nudgeAuthoringStyleOffsets(fieldIds, { dx = 0, dy = 0 } = {}) {
    if (!authoringBundle) return;
    const targetIds = [...new Set((Array.isArray(fieldIds) ? fieldIds : [fieldIds]).filter(Boolean))];
    if (!targetIds.length || (!dx && !dy)) return;
    setAuthoringBundle((current) => {
      const fields = [...(current.schema?.fields || [])];
      const styles = current.stylesheet?.style_classes?.length ? [...current.stylesheet.style_classes] : [{ style_class: 'body_default' }];
      for (const fieldId of targetIds) {
        const prepared = prepareAuthoringStyleForField(fields, styles, fieldId, { shared: false });
        if (!prepared) continue;
        const currentStyle = styles[prepared.styleIndex] || {};
        const nextStyle = { ...currentStyle };
        if (dx) nextStyle.x_shift = clampNumber(Number(currentStyle.x_shift || 0) + dx, -240, 240);
        if (dy) nextStyle.baseline_shift = clampNumber(Number(currentStyle.baseline_shift || 0) + dy, -120, 120);
        styles[prepared.styleIndex] = nextStyle;
      }
      return {
        ...current,
        schema: { ...current.schema, fields },
        stylesheet: { ...current.stylesheet, style_classes: styles },
      };
    });
    setAuthoringDirty(true);
    if (authoringResult?.paths?.image || selectedItem?.latestAuthoringPreview) setAuthoringPreviewStale(true);
    setMessage(`선택 bbox ${targetIds.length}개 위치 보정: x ${dx > 0 ? '+' : ''}${dx}, baseline ${dy > 0 ? '+' : ''}${dy}`);
  }

  function updateAuthoringRenderPolicies(fieldIds, patch) {
    if (!authoringBundle) return;
    const targetIds = new Set((Array.isArray(fieldIds) ? fieldIds : [fieldIds]).filter(Boolean));
    if (!targetIds.size) return;
    setAuthoringBundle((current) => {
      const schema = {
        ...current.schema,
        fields: (current.schema?.fields || []).map((field) => {
          if (!targetIds.has(field.field_id)) return field;
          const checkboxPatch = patch.checkbox_style && isAuthoringCheckboxField(field, current.faker_profile) ? { checkbox_style: patch.checkbox_style } : {};
          const nextPolicy = {
            ...(field.render_policy || {}),
            ...(patch.align ? { align: patch.align } : {}),
            ...(patch.valign ? { valign: patch.valign } : {}),
            ...(patch.overflow ? { overflow: patch.overflow, fit: patch.overflow === 'shrink' ? 'shrink_to_fit' : 'clip' } : {}),
            ...checkboxPatch,
          };
          return { ...field, render_policy: nextPolicy };
        }),
      };
      return { ...current, schema };
    });
    setAuthoringDirty(true);
    if (authoringResult?.paths?.image || selectedItem?.latestAuthoringPreview) setAuthoringPreviewStale(true);
  }

  function updateAuthoringFieldRenderModes(fieldIds, renderMode) {
    if (!authoringBundle || !BBOX_RENDER_MODES.includes(renderMode)) return;
    const targetIds = new Set((Array.isArray(fieldIds) ? fieldIds : [fieldIds]).filter(Boolean));
    if (!targetIds.size) return;
    setAuthoringBundle((current) => ({
      ...current,
      schema: {
        ...current.schema,
        fields: (current.schema?.fields || []).map((field) => (
          targetIds.has(field.field_id) ? { ...field, render_mode: renderMode } : field
        )),
      },
    }));
    setAuthoringDirty(true);
    setAuthoringPreviewStale(true);
    setMessage(`선택 Authoring field ${targetIds.size}개 → ${BBOX_RENDER_MODE_LABELS[renderMode]}`);
  }

  function updateAuthoringQrBox(box, options = {}) {
    if (!authoringBundle || !box) return;
    const imageWidthValue = Number(authoringBundle.schema?.image?.width || 0);
    const imageHeightValue = Number(authoringBundle.schema?.image?.height || 0);
    const imageWidth = Number.isFinite(imageWidthValue) && imageWidthValue > 0 ? Math.round(imageWidthValue) : Number.MAX_SAFE_INTEGER;
    const imageHeight = Number.isFinite(imageHeightValue) && imageHeightValue > 0 ? Math.round(imageHeightValue) : Number.MAX_SAFE_INTEGER;
    const rawWidth = Math.max(24, Math.round(Number(box.width ?? box[2] ?? 180)));
    const rawHeight = Math.max(24, Math.round(Number(box.height ?? box[3] ?? box.width ?? box[2] ?? 180)));
    let side = Math.max(rawWidth, rawHeight);
    if (options.changedIndex === 2) side = rawWidth;
    if (options.changedIndex === 3) side = rawHeight;
    side = Math.max(24, Math.min(side, imageWidth, imageHeight));
    const x = Math.round(Number(box.x ?? box[0] ?? 0));
    const y = Math.round(Number(box.y ?? box[1] ?? 0));
    const normalized = [
      Math.max(0, Math.min(x, Math.max(0, imageWidth - side))),
      Math.max(0, Math.min(y, Math.max(0, imageHeight - side))),
      side,
      side,
    ];
    setAuthoringBundle((current) => ({
      ...current,
      schema: {
        ...current.schema,
        handwriting: {
          ...(current.schema?.handwriting || {}),
          qr_bbox: normalized,
        },
      },
    }));
    setAuthoringDirty(true);
    setAuthoringPreviewStale(true);
    setMessage(`QR bbox 지정: [${normalized.join(', ')}]`);
  }

  async function refreshFonts() {
    const payload = await apiJson('/api/fonts?refresh=1');
    setFontPayload(payload);
    setMessage(`폰트 목록 새로고침 완료: ${(payload.fonts || []).length}개`);
  }

  async function renderAuthoringLivePreview({ silent = true } = {}) {
    if (!selectedDocId || !authoringBundle) return null;
    const seq = authoringPreviewSeq.current + 1;
    authoringPreviewSeq.current = seq;
    if (!silent) setBusy('authoringLivePreview');
    try {
      const payload = await apiJson('/api/authoring/live-preview', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          schema: authoringBundle.schema,
          stylesheet: authoringBundle.stylesheet,
          fakerProfile: authoringBundle.faker_profile,
          seed: 1234,
          renderScale: 2,
          asOfDate: authoringAsOfDate,
          handwritingPreview: selectedIsHandwriting,
          qrBbox: selectedIsHandwriting ? (authoringBundle.schema?.handwriting?.qr_bbox || null) : null,
        }),
      });
      if (seq !== authoringPreviewSeq.current) return null;
      const version = Date.now();
      setAuthoringLivePreview({
        ...payload,
        imageUrl: payload.paths?.image ? fileUrl(payload.paths.image, version) : payload.imageUrl,
      });
      setAuthoringLivePreviewVersion(version);
      if (!silent) setMessage(`Authoring 실시간 렌더 갱신 완료: field ${payload.summary.field_count}개 · 경고 ${payload.summary.warning_count}개`);
      return payload;
    } catch (err) {
      if (seq === authoringPreviewSeq.current) {
        setAuthoringLivePreview((current) => ({ ...(current || {}), error: err.message || String(err) }));
        if (!silent) setError(err.message || String(err));
      }
      return null;
    } finally {
      if (!silent) setBusy('');
    }
  }

  async function renderAuthoringPreview() {
    if (!selectedDocId) return;
    setBusy('authoringRender');
    setError('');
    setMessage(authoringDirty ? 'Authoring 수정본 저장 후 합성 preview를 렌더링 중입니다.' : '합성 preview를 렌더링 중입니다.');
    try {
      if (authoringDirty) await saveAuthoringBundle({ silentBusy: true });
      const resolved = resolveAuthoringPaths();
      const payload = await apiJson('/api/authoring/render-preview', {
        method: 'POST',
        body: JSON.stringify({
          docId: selectedDocId,
          schemaPath: resolved.schema,
          stylesheetPath: resolved.stylesheet,
          fakerProfilePath: resolved.faker_profile,
          asOfDate: authoringAsOfDate,
        }),
      });
      const version = Date.now();
      setAuthoringVersion(version);
      setAuthoringResult((current) => ({
        ...(current || {}),
        ...payload,
        paths: { ...(current?.paths || {}), ...payload.paths },
        imageUrl: payload.paths?.image ? fileUrl(payload.paths.image, version) : payload.imageUrl,
        overlayUrl: payload.paths?.overlay ? fileUrl(payload.paths.overlay, version) : payload.overlayUrl,
      }));
      setCanvasMode('authoring');
      setAuthoringViewMode('preview');
      setAuthoringPreviewStale(false);
      setMessage(`Preview 렌더링 완료: field ${payload.summary.field_count}개 · 경고 ${payload.summary.warning_count}개`);
      await refreshAll();
    } finally {
      setBusy('');
    }
  }

  async function renderAuthoringBatch({ all = false, docIds = null, label = '' } = {}) {
    const requestedDocIds = all ? [...new Set((docIds || []).filter(Boolean))] : [selectedDocId].filter(Boolean);
    if (!requestedDocIds.length) return;
    setBusy(all ? 'authoringBatchGroup' : 'authoringBatch');
    setError('');
    setMessage(all ? `${label || '목표 그룹'} Authoring 완료 문서 ${requestedDocIds.length}종을 각 5장씩 배치 생성 중입니다.` : '선택 문서 합성 샘플 5장을 생성 중입니다.');
    try {
      if (!all && authoringDirty) await saveAuthoringBundle({ silentBusy: true });
      const outDir = all
        ? `outputs/render/batch_authoring_${activeTargetGroup.id || 'target_group'}_20260702`
        : `outputs/render/batch_authoring_${selectedDocId || 'selected'}_20260702`;
      const payload = await apiJson('/api/authoring/render-batch', {
        method: 'POST',
        body: JSON.stringify({
          docIds: requestedDocIds,
          count: 5,
          seed: 20260702,
          outDir,
          renderScale: 2,
          asOfDate: authoringAsOfDate,
        }),
      });
      setAuthoringBatchResult(payload);
      setMessage(`배치 생성 완료: 문서 ${payload.summary.documentCount}종 · 이미지 ${payload.summary.sampleCount}장 · 경고 ${payload.summary.warningCount}개 · ${payload.paths.outDir}`);
      await refreshAll();
    } finally {
      setBusy('');
    }
  }

  const inpaintedPath = selectedIsBlankTemplate ? '' : (cleanupResult?.paths?.inpainted || inpaintResult?.paths?.inpainted || selectedItem?.latestInpainted || '');
  const authoringPreviewPath = authoringResult?.paths?.image || selectedItem?.latestAuthoringPreview || '';
  const authoringOverlayPath = authoringResult?.paths?.overlay || selectedItem?.latestAuthoringOverlay || '';
  const authoringOverlayHref = authoringResult?.overlayUrl || (authoringOverlayPath ? fileUrl(authoringOverlayPath, authoringVersion) : '');
  const batchDocuments = authoringBatchResult?.documents || [];
  const selectedBatchDoc = batchDocuments.find((doc) => doc.docId === selectedDocId) || null;
  const batchSummaryPath = authoringBatchResult?.paths?.summary || selectedItem?.latestAuthoringBatch || '';
  const batchManifestPath = authoringBatchResult?.paths?.manifest || selectedBatchDoc?.manifest || '';
  const batchFirstImagePath = selectedBatchDoc?.firstImage || '';
  const batchSummaryHref = batchSummaryPath ? fileUrl(batchSummaryPath, authoringVersion) : '';
  const batchManifestHref = batchManifestPath ? fileUrl(batchManifestPath, authoringVersion) : '';
  const batchFirstImageHref = batchFirstImagePath ? fileUrl(batchFirstImagePath, authoringVersion) : '';
  const selectedAgentRequest = authoringAgentRequest?.docId === selectedDocId ? authoringAgentRequest : null;
  const selectedAgentRun = authoringAgentRun?.docId === selectedDocId ? authoringAgentRun : null;
  const latestAgentRequestPath = selectedAgentRequest?.paths?.request || selectedItem?.latestAuthoringAgentRequest || '';
  const latestAgentPromptPath = selectedAgentRequest?.paths?.prompt || selectedItem?.latestAuthoringAgentPrompt || '';
  const latestAgentAnchorMapPath = selectedAgentRequest?.request?.generated_sidecars?.anchorMapDraft || selectedItem?.latestAuthoringAgentAnchorMap || '';
  const latestAgentRunPath = selectedAgentRun?.jobPath || selectedItem?.latestAuthoringAgentRun || '';
  const latestAgentRunStatus = selectedAgentRun?.status || (latestAgentRunPath ? 'unknown' : '');
  const latestAgentRunReady = Boolean(
    selectedAgentRun?.validation?.ready
    && selectedAgentRun?.validation?.scope !== 'schema'
    && selectedAgentRun?.executionMode !== 'schema_only',
  );
  const latestAgentRunPolling = Boolean(latestAgentRunPath && !AUTHORING_AGENT_TERMINAL_STATUSES.has(latestAgentRunStatus));
  const latestAgentRunCanCancel = ['queued', 'running', 'cancelling'].includes(latestAgentRunStatus);
  const latestAgentValidation = selectedAgentRun?.validation || {};
  const latestAgentValidationIssueCount = (latestAgentValidation.contractErrors || []).length
    + (latestAgentValidation.missing || []).length
    + (latestAgentValidation.invalidJson || []).length;
  const latestAgentRunNeedsRepair = latestAgentRunStatus === 'needs_repair'
    || (AUTHORING_AGENT_TERMINAL_STATUSES.has(latestAgentRunStatus) && latestAgentValidation.ready === false && latestAgentValidationIssueCount > 0);
  const authoringAgentRetryBusy = ['authoringAgentRun', 'authoringAgentBboxRun', 'authoringAgentCancel'].includes(busy)
    || latestAgentRunCanCancel;
  const selectedAgentModelCapability = authoringAgentCapabilities.models.find((model) => model.id === authoringAgentModel)
    || authoringAgentCapabilities.models[0]
    || DEFAULT_AUTHORING_AGENT_CAPABILITIES.models[0];
  const authoringAgentReasoningOptions = selectedAgentModelCapability.reasoningEfforts?.length
    ? selectedAgentModelCapability.reasoningEfforts
    : ['medium'];
  const latestAgentElapsedSeconds = selectedAgentRun?.elapsedSeconds ?? (
    selectedAgentRun?.startedAt
      ? Math.max(0, (authoringAgentClock - new Date(selectedAgentRun.startedAt).getTime()) / 1000)
      : 0
  );

  useEffect(() => {
    setAuthoringAgentReasoning((current) => (
      authoringAgentReasoningOptions.includes(current)
        ? current
        : selectedAgentModelCapability.defaultReasoningEffort || authoringAgentCapabilities.defaultReasoningEffort || 'medium'
    ));
    if (!selectedAgentModelCapability.supportsFastMode) setAuthoringAgentFastMode(false);
  }, [authoringAgentModel, authoringAgentCapabilities]);

  useEffect(() => {
    const persistedJobPath = selectedItem?.latestAuthoringAgentRun || '';
    if (!persistedJobPath) {
      authoringAgentHydratedJobRef.current = '';
      return;
    }
    if (authoringAgentHydratedJobRef.current === persistedJobPath) return;
    authoringAgentHydratedJobRef.current = persistedJobPath;
    resetAuthoringAgentTerminal(persistedJobPath);
    setAuthoringAgentTerminalOpen(true);
    let cancelled = false;
    async function restorePersistedRun() {
      for (let attempt = 0; attempt < 3; attempt += 1) {
        const payload = await refreshAuthoringAgentRunStatus(persistedJobPath);
        if (cancelled || payload) return;
        await delay(150);
      }
      if (!cancelled) authoringAgentHydratedJobRef.current = '';
    }
    restorePersistedRun().catch((exc) => {
      if (cancelled) return;
      authoringAgentHydratedJobRef.current = '';
      setError(`저장된 Agent 세션 복원 실패: ${exc.message || String(exc)}`);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedDocId, selectedItem?.latestAuthoringAgentRun]);

  useEffect(() => {
    if (!latestAgentRunPolling) return undefined;
    const pollPath = latestAgentRunPath;
    const delayMs = latestAgentRunStatus === 'unknown' ? 500 : 1000;
    const timer = window.setInterval(() => {
      refreshAuthoringAgentRunStatus(pollPath).catch((exc) => setError(exc.message || String(exc)));
    }, delayMs);
    return () => window.clearInterval(timer);
  }, [latestAgentRunPath, latestAgentRunStatus, latestAgentRunPolling]);

  useEffect(() => {
    if (!latestAgentRunPolling) return undefined;
    const timer = window.setInterval(() => setAuthoringAgentClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [latestAgentRunPolling]);

  useEffect(() => {
    if (!authoringAgentTerminalAutoScroll || !authoringAgentTerminalOpen || !authoringAgentTerminalPreRef.current) return;
    authoringAgentTerminalPreRef.current.scrollTop = authoringAgentTerminalPreRef.current.scrollHeight;
  }, [authoringAgentTerminalText, authoringAgentTerminalAutoScroll, authoringAgentTerminalOpen]);

  useEffect(() => {
    function handleGlobalShortcuts(event) {
      if (selectedWorkflowLocked) return;
      const key = event.key?.toLowerCase();
      const modifier = event.metaKey || event.ctrlKey;
      if (modifier && key === 's') {
        event.preventDefault();
        event.stopPropagation();
        if (isBusy) return;
        if (canvasMode === 'authoring' && authoringBundle) run(() => saveAuthoringBundle());
        else if (canvasMode === 'cleanup' && policy && inpaintedPath) run(() => saveCleanupMask());
        else if (policy) run(() => cleanroomEditing ? saveReview({ skipPruneConfirm: true, pruneAuthoring: false }) : saveReview());
        return;
      }
      if (modifier && key === 'z' && !event.shiftKey) {
        if (canvasMode === 'cleanup' && cleanupHistory.length && !isBusy && !isTextEditingTarget(event.target)) {
          event.preventDefault();
          event.stopPropagation();
          undoCleanupMask();
          return;
        }
        if (canvasMode !== 'review' || !policy || !reviewHistory.length || isBusy || isTextEditingTarget(event.target)) return;
        event.preventDefault();
        event.stopPropagation();
        undoReview();
        return;
      }
      const authoringArrowNudge = {
        ArrowLeft: { dx: -1, dy: 0 },
        ArrowRight: { dx: 1, dy: 0 },
        ArrowUp: { dx: 0, dy: -1 },
        ArrowDown: { dx: 0, dy: 1 },
      }[event.key];
      if (authoringArrowNudge && canvasMode === 'authoring' && authoringBundle && selectedAuthoringFieldIds.length && !isBusy && !modifier && !event.altKey && !isTextEditingTarget(event.target)) {
        event.preventDefault();
        event.stopPropagation();
        const step = event.shiftKey ? 10 : 1;
        nudgeAuthoringStyleOffsets(selectedAuthoringFieldIds, { dx: authoringArrowNudge.dx * step, dy: authoringArrowNudge.dy * step });
        return;
      }
      const numericStatusMap = { 1: 'use', 2: 'keep' };
      const numericStatus = numericStatusMap[event.key] || numericStatusMap[event.code === 'Numpad1' ? '1' : event.code === 'Numpad2' ? '2' : ''];
      if (numericStatus && canvasMode === 'review' && policy && selectedIds.length && !isBusy && !isTextEditingTarget(event.target)) {
        event.preventDefault();
        event.stopPropagation();
        setSelectedBboxStatus(numericStatus);
        return;
      }
      if ((event.key === 'Delete' || event.key === 'Backspace') && canvasMode === 'review' && selectedIds.length && !isBusy && !isTextEditingTarget(event.target)) {
        event.preventDefault();
        event.stopPropagation();
        deleteSelectedBboxes();
        return;
      }
      if ((event.key === 'Delete' || event.key === 'Backspace') && canvasMode === 'cleanup' && selectedCleanupId && !isBusy && !isTextEditingTarget(event.target)) {
        event.preventDefault();
        event.stopPropagation();
        deleteSelectedCleanupMask();
      }
    }
    window.addEventListener('keydown', handleGlobalShortcuts, true);
    return () => window.removeEventListener('keydown', handleGlobalShortcuts, true);
  }, [authoringBundle, authoringResult?.paths?.image, bboxEditMode, canvasMode, cleanupHistory, inpaintedPath, isBusy, policy, reviewHistory, selectedAuthoringFieldIds, selectedCleanupId, selectedIds, selectedItem?.latestAuthoringPreview, selectedWorkflowLocked, cleanroomEditing]);

  useEffect(() => {
    if (!selectedDocId || !authoringBundle || selectedWorkflowLocked || cleanroomEditing) return undefined;
    if (authoringBundle?.schema?.generation_path === 'editable-office-template') return undefined;
    const handle = window.setTimeout(() => {
      renderAuthoringLivePreview({ silent: true });
    }, 350);
    return () => window.clearTimeout(handle);
  }, [selectedDocId, authoringBundle, selectedWorkflowLocked, cleanroomEditing]);

  const authoringPaths = resolveAuthoringPaths();
  const authoringAllFields = authoringBundle?.schema?.fields || [];
  const isDocxAuthoringBundle = authoringBundle?.schema?.generation_path === 'editable-office-template';
  const authoringFields = isDocxAuthoringBundle ? authoringAllFields : authoringAllFields.filter(hasRenderableAuthoringBbox);
  const missingAuthoringFields = isDocxAuthoringBundle ? [] : authoringAllFields.filter((field) => !hasRenderableAuthoringBbox(field));
  const selectedAuthoringFields = selectedAuthoringFieldIds.map((id) => authoringFields.find((field) => field.field_id === id)).filter(Boolean);
  const selectedAuthoringField = authoringFields.find((field) => field.field_id === selectedAuthoringFieldId) || selectedAuthoringFields[0] || authoringFields[0] || null;
  const authoringStyles = authoringBundle?.stylesheet?.style_classes || [];
  const selectedAuthoringStyle = styleForField(selectedAuthoringField, authoringStyles);
  const fontOptions = fontPayload.fonts?.length ? fontPayload.fonts : (authoringBundle?.fonts?.items || []);
  const fakerRuleExamples = authoringBundle?.faker_rule_examples || FALLBACK_FAKER_RULE_EXAMPLES;
  const canLoadAuthoring = Boolean(authoringPaths.schema && authoringPaths.stylesheet && authoringPaths.faker_profile);

  useEffect(() => {
    if (!selectedDocId || !canLoadAuthoring || authoringBundle || authoringDirty || selectedWorkflowLocked || cleanroomEditing) return undefined;
    let cancelled = false;
    const handle = window.setTimeout(() => {
      loadAuthoringBundle(authoringPaths, { silentBusy: true })
        .then((payload) => {
          if (!cancelled && payload) setMessage(`Authoring 자동 불러오기 완료: field ${payload.summary?.field_count || 0}개`);
        })
        .catch((exc) => {
          if (!cancelled) setError(exc.message || String(exc));
        });
    }, 50);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [selectedDocId, canLoadAuthoring, authoringPaths.schema, authoringPaths.stylesheet, authoringPaths.faker_profile, authoringBundle, authoringDirty, selectedWorkflowLocked, cleanroomEditing]);
  const showFinalOutputCanvas = Boolean(selectedFinalOutput?.locked && !cleanroomEditing);
  const showInpaintCanvas = Boolean(inpaintedPath && canvasMode === 'inpaint');
  const showCleanupCanvas = Boolean(policy && inpaintedPath && canvasMode === 'cleanup');
  const authoringEditImagePath = authoringBundle?.schema?.source_inpainted || inpaintedPath;
  const authoringLivePreviewPath = authoringLivePreview?.paths?.image || '';
  const authoringCanvasImagePath = authoringLivePreviewPath || authoringEditImagePath;
  const authoringCanvasVersion = authoringLivePreviewPath ? authoringLivePreviewVersion : inpaintVersion;
  const showAuthoringCanvas = Boolean(authoringBundle && authoringCanvasImagePath && canvasMode === 'authoring');
  const canvasTitle = showFinalOutputCanvas ? selectedFinalOutput.label : (showAuthoringCanvas ? 'Authoring 캔버스' : (showCleanupCanvas ? '템플릿 클린업 캔버스' : (showInpaintCanvas ? '인페인팅 결과 캔버스' : (policy ? 'BBox 리뷰 캔버스' : selectedSample ? '샘플 미리보기' : '샘플 없음'))));
  const canvasSubtitle = showFinalOutputCanvas
    ? (selectedFinalOutput.previewPath || selectedFinalOutput.pdfPath || '작업 불가 문서로 지정되어 순차 합성 워크플로우를 사용하지 않습니다.')
    : showAuthoringCanvas
    ? `${authoringLivePreviewPath ? '최종 렌더러 live preview' : '인페인팅 템플릿'} · 선택 ${selectedAuthoringFieldIds.length || 0}개${missingAuthoringFields.length ? ` · bbox 정합성 필요 ${missingAuthoringFields.length}개` : ''}${authoringDirty ? ' · 저장 안 됨' : ''}${authoringLivePreview?.error ? ` · 렌더 오류: ${authoringLivePreview.error}` : ''}`
    : (showCleanupCanvas
      ? `${inpaintedPath} · 브러시 stroke ${cleanupMask?.strokes?.length || 0}개${cleanupDirty ? ' · 저장 안 됨' : ''}`
      : (showInpaintCanvas ? inpaintedPath : (policy ? `${policy.image.width}×${policy.image.height} · ${reviewPath}` : selectedSample || '입고함에서 seed를 적재하거나 웹 수집 필요 문서를 확인하세요.')));

  useEffect(() => {
    const sourceReviewPath = reviewPath || selectedItem?.latestReview || '';
    if (!selectedDocId || !policy || !sourceReviewPath || !selectedItem?.latestInpainted || cleanupDirty || cleanroomEditing) return undefined;
    let cancelled = false;
    const query = new URLSearchParams({ docId: selectedDocId, reviewPath: sourceReviewPath, baseImagePath: inpaintedPath || selectedItem?.latestInpainted || '' });
    apiJson(`/api/cleanup-paint?${query.toString()}`)
      .then((payload) => {
        if (cancelled) return;
        setCleanupMask(payload.paint || emptyCleanupMask(policy.image.width, policy.image.height));
        setCleanupBaseImagePath(payload.baseImagePath || inpaintedPath || selectedItem?.latestInpainted || '');
        setCleanupDirty(false);
        setCleanupHistory([]);
        setSelectedCleanupId('');
        if (payload.paths?.inpainted) {
          const version = Date.now();
          setCleanupVersion(version);
          setCleanupResult({ ...payload, comparisonUrl: payload.paths?.comparison ? fileUrl(payload.paths.comparison, version) : payload.comparisonUrl });
        } else {
          setCleanupResult(null);
          setCleanupVersion(0);
        }
      })
      .catch((exc) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedDocId, reviewPath, selectedItem?.latestReview, selectedItem?.latestInpainted, inpaintedPath, policy?.image?.width, policy?.image?.height, cleanupDirty, cleanroomEditing]);

  return (
    <div className="app workbench-app" onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
      {dropActive && <div className="drop-overlay"><div><b>Seed sample 추가</b><p>PDF, PNG, JPG/JPEG 파일을 놓으면 문서 선택 후 바로 적재합니다.</p></div></div>}
      {uploadOpen && (
        <UploadPopover
          files={uploadFiles}
          warnings={uploadWarnings}
          documents={uploadDocOptions}
          allDocuments={documents}
          selectedDocId={uploadDocId}
          setSelectedDocId={setUploadDocId}
          search={uploadSearch}
          setSearch={setUploadSearch}
          onClose={closeUploadPopover}
          onSubmit={() => run(uploadDroppedFiles)}
          busy={busy === 'upload'}
        />
      )}
      {handwritingScanPopoverOpen && (
        <HandwritingScanPopover
          files={handwritingScanFiles}
          warnings={handwritingScanWarnings}
          setFiles={(files) => openHandwritingScanPopover(files)}
          busy={busy === 'handwritingScanUpload'}
          onClose={closeHandwritingScanPopover}
          onSubmit={() => run(uploadHandwritingScansAndIntake)}
        />
      )}
      {recognitionPopover && (
        <RecognitionPopover
          data={recognitionPopover}
          setChoice={updateRecognitionChoice}
          onClose={() => setRecognitionPopover(null)}
          onApply={(options) => run(() => applyRecognitionChoices(options))}
          onSaveWithoutRecognition={() => run(() => { setRecognitionPopover(null); return saveReview({ skipRecognition: true }); })}
          busy={isBusy}
        />
      )}
      {reviewPrunePopover && (
        <ReviewPrunePopover
          data={reviewPrunePopover}
          busy={isBusy}
          onCancel={() => setReviewPrunePopover(null)}
          onConfirm={() => run(() => {
            const target = reviewPrunePopover.policy;
            setReviewPrunePopover(null);
            return saveReview({ skipRecognition: true, policyOverride: target, skipPruneConfirm: true, pruneAuthoring: true });
          })}
        />
      )}
      {authoringAgentConflictPopover && (
        <AuthoringAgentConflictPopover
          data={authoringAgentConflictPopover}
          resolutions={authoringAgentConflictResolutions}
          focusedId={focusedAuthoringAgentConflictId}
          busy={busy === 'authoringApplyAgentDrafts'}
          onFocus={focusAuthoringAgentConflict}
          onResolve={setAuthoringAgentConflictResolution}
          onUseRecommended={useRecommendedAuthoringAgentConflictResolutions}
          onCancel={closeAuthoringAgentConflictPopover}
          onApply={() => run(() => commitAuthoringAgentDrafts(
            authoringAgentConflictPopover.requestPath,
            authoringAgentConflictPopover,
            authoringAgentConflictResolutions,
          ))}
        />
      )}
      {assessmentPopover && (
        <AssessmentPopover
          popover={assessmentPopover}
          rows={assessmentRowsByDocId.get(assessmentPopover.docId) || assessmentPopover.rows || []}
          summary={assessmentPayload.summary || {}}
          documentTypeOptions={documentTypeOptions}
          feasibilityOptions={feasibilityOptions}
          assessmentExport={assessmentExport}
          assessmentEdits={assessmentEdits}
          busy={busy}
          isBusy={isBusy}
          assessmentValue={assessmentValue}
          setAssessmentEdit={setAssessmentEdit}
          onSave={(row) => run(() => saveAssessmentRow(row))}
          onExport={() => run(exportAssessmentXlsx)}
          onClose={() => setAssessmentPopover(null)}
        />
      )}
      <header className="workbench-top">
        <div className="brand-line">
          <div className="eyebrow">DataFactory Intake Workbench</div>
          <h1>{selectedDoc?.title || '문서 데이터 제작 워크벤치'}</h1>
          {selectedDoc && <span className="doc-id-badge">{selectedDoc.docId}</span>}
        </div>
        <div className="top-context">
          <span className="status-pill importable">자동 적재 {seedScan.summary?.importable || 0}</span>
          <span className="status-pill needsReview">확인 필요 {seedScan.summary?.needsReview || 0}</span>
          <span>워크벤치 미착수 {workPayload.summary?.progressCounts?.not_started || 0}</span>
          <span>진행 {workPayload.summary?.progressCounts?.in_progress || 0}</span>
          <span>완료 {workPayload.summary?.progressCounts?.done || 0}</span>
        </div>
        <div className="runtime-inline">
          <span className={health?.lama?.available ? 'ok' : 'warn'}>LaMa {health?.lama?.available ? '사용 가능' : '미설치'}</span>
          <button onClick={() => run(() => refreshAll())} disabled={isBusy}>새로고침</button>
        </div>
      </header>

      <div className="workbench-body">
        <aside className="queue-panel fixed-panel">
          <section className="panel-block intake-block">
            <div className="block-title-row">
              <h2>Seed 입고함</h2>
              <button className="primary slim" onClick={() => run(importAllImportable)} disabled={!importableFolders.length || isBusy}>
                {busy === 'batchImport' ? '일괄 적재 중...' : `일괄 적재 ${importableFolders.length}`}
              </button>
            </div>
            <div className="summary-grid intake-summary">
              <Metric label="자동" value={seedScan.summary?.importable || 0} />
              <Metric label="확인" value={seedScan.summary?.needsReview || 0} />
              <Metric label="완료" value={seedScan.summary?.alreadyImported || 0} />
              <Metric label="합성" value={needsCollectionItems.length} />
            </div>
            <div className="intake-tabs">
              {INTAKE_TABS.map(([id, label]) => (
                <button key={id} className={intakeTab === id ? 'active' : ''} onClick={() => setIntakeTab(id)}>{label}</button>
              ))}
            </div>
            <div className="intake-list">
              {intakeFolders.length === 0 ? <p className="muted">이 그룹에 표시할 seed 폴더가 없습니다.</p> : intakeFolders.map((folder) => (
                <SeedFolderCard
                  key={folder.folder}
                  folder={folder}
                  documents={documents}
                  manualDocId={manualSeedFolder === folder.folder ? manualDocId : (folder.candidates?.[0]?.docId || selectedDocId)}
                  setManualDocId={(docId) => { setManualSeedFolder(folder.folder); setManualDocId(docId); }}
                  onSelectDoc={selectDocument}
                  onImport={() => run(() => folder.status === 'needsReview' ? saveMappingAndImport(folder) : importSeed(folder.folder, folder.matchedDocId))}
                  onTrash={() => run(() => trashSeedFolder(folder.folder, folder.name))}
                  busy={isBusy}
                />
              ))}
            </div>
          </section>

          <section className="panel-block compact first-priority-block">
            <div className="block-title-row">
              <h2>목표 그룹</h2>
              <span className="priority">{activeTargetGroup.label} · 표시 {targetGroupItems.length}종 / 전체 {targetGroupAllItems.length}종 · scope {(activeTargetGroup.scopeEntries || []).length || targetGroupAllItems.length}건</span>
            </div>
            <p className="muted">좌클릭: 문서 선택 · 우클릭: 생성 가능성 판정. 사용자 정의 목표 그룹은 `workbench/target_groups.json`에 저장됩니다.</p>
            {sampleAvailabilityFilters.length > 0 && <p className="muted mini-help">샘플/합성 필터 적용 중: {sampleAvailabilityFilters.map((id) => SAMPLE_AVAILABILITY_LABELS[id]).join(', ')}. 목표 그룹 목록과 최종 산출물 생성 대상에도 동일하게 적용됩니다.</p>}
            <div className="button-row compact-buttons three-actions">
              <button className="primary" onClick={createTargetGroupDraft} disabled={isBusy}>새 그룹</button>
              <button onClick={() => editTargetGroup(activeTargetGroup)} disabled={!activeTargetGroup.id || isBusy}>{activeTargetGroup.protected ? '복사 편집' : '그룹 수정'}</button>
              <button className="danger" onClick={deleteActiveTargetGroup} disabled={!activeTargetGroup.id || isBusy}>{activeTargetGroup.protected ? '숨김' : '삭제'}</button>
            </div>
            {targetGroups.length > 0 ? (
              <label className="target-group-select">활성 목표 그룹
                <select value={activeTargetGroup.id} onChange={(event) => setActiveTargetGroupId(event.target.value)}>
                  {targetGroups.map((group) => <option key={group.id} value={group.id}>{group.label}</option>)}
                </select>
              </label>
            ) : (
              <p className="muted">표시 중인 목표 그룹이 없습니다. 새 그룹을 만들거나 기본 그룹을 다시 추가하려면 새 그룹으로 필요한 문서를 구성하세요.</p>
            )}
            {targetGroupEditing && (
              <div className="target-group-editor">
                <label>그룹명<input value={targetGroupDraft.label} onChange={(event) => setTargetGroupDraft((current) => ({ ...current, label: event.target.value }))} /></label>
                <label>설명<input value={targetGroupDraft.description} onChange={(event) => setTargetGroupDraft((current) => ({ ...current, description: event.target.value }))} /></label>
                <div className="target-group-add-row">
                  <select value={targetGroupDocId} onChange={(event) => setTargetGroupDocId(event.target.value)}>
                    {documents.map((doc) => <option key={doc.docId} value={doc.docId}>{doc.title} · {doc.docId}</option>)}
                  </select>
                  <button onClick={() => addDocToTargetGroupDraft()} disabled={!targetGroupDocId || isBusy}>추가</button>
                </div>
                <div className="target-group-draft-list">
                  {(targetGroupDraft.scopeEntries || []).map((entry) => (
                    <span key={`${entry.domain}:${entry.docId}`}>{entry.title || entry.docId}<button onClick={() => removeDocFromTargetGroupDraft(entry.docId)} disabled={isBusy}>×</button></span>
                  ))}
                </div>
                <div className="button-row compact-buttons">
                  <button className="primary" onClick={() => run(saveTargetGroupDraft)} disabled={!targetGroupDraft.label.trim() || !targetGroupDraft.scopeEntries.length || isBusy}>
                    {busy === 'targetGroupSave' ? '저장 중...' : '그룹 저장'}
                  </button>
                  <button onClick={() => setTargetGroupEditing(false)} disabled={isBusy}>닫기</button>
                </div>
              </div>
            )}
            <div className="final-export-card">
              <div className="final-export-head">
                <b>최종 산출물 생성</b>
                <span>{finalExportResult?.summary ? `OK ${finalExportResult.summary.okCount} · 오류 ${finalExportResult.summary.errorCount} · 경고 ${finalExportResult.summary.warningCount || 0}` : `${activeTargetGroup.label} · 생성 가능 ${targetGroupFinalExportScopeEntries.length}건`}</span>
              </div>
              <p className="muted mini-help">`outputs/results` · 출력 가능 {targetGroupFinalExportReadyItems.length}종 · 미준비 {targetGroupFinalExportMissingItems.length}종</p>
              <label className="final-export-toggle" title="필기 문서의 authoring 스타일과 faker를 사용해 인쇄체로 생성합니다. QR 코드는 자동 삽입하지 않습니다.">
                <input
                  type="checkbox"
                  checked={finalExportHandwritingAsPrinted}
                  onChange={(event) => setFinalExportHandwritingAsPrinted(event.target.checked)}
                />
                <span>필기 → 인쇄</span>
                <small>임시</small>
              </label>
              <div className="final-export-controls">
                <label>데이터 기준일
                  <input
                    type="date"
                    value={authoringAsOfDate}
                    onChange={(event) => setAuthoringAsOfDate(event.target.value)}
                  />
                </label>
                <label>문서별 생성 매수
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={finalExportCount}
                    onChange={(event) => setFinalExportCount(event.target.value)}
                  />
                </label>
                <button className="primary" onClick={() => run(exportFinalResults)} disabled={!targetGroupFinalExportScopeEntries.length || isBusy}>
                  {busy === 'finalResultsExport' ? '생성 중...' : '최종 산출물 생성'}
                </button>
              </div>
              {targetGroupFinalExportMissingItems.length > 0 && <p className="muted">미준비: {targetGroupFinalExportMissingItems.slice(0, 3).map((item) => item.title).join(', ')}{targetGroupFinalExportMissingItems.length > 3 ? ` 외 ${targetGroupFinalExportMissingItems.length - 3}종` : ''}</p>}
              {finalExportResult?.summary && <p className="muted">생성 파일 {finalExportResult.summary.generatedFileCount || 0}개 · explicit PII 파일 {finalExportResult.summary.piiFileCount || 0}개 · 이미지 규격 경고 {finalExportResult.summary.warningCount || 0}건</p>}
              {finalExportResult?.paths?.manifest && (
                <div className="final-export-links">
                  <a className="result-link compact" href={finalExportResult.urls?.manifest || fileUrl(finalExportResult.paths.manifest)} target="_blank" rel="noreferrer">Manifest XLSX 열기</a>
                  <a className="result-link compact" href={finalExportResult.urls?.summary || fileUrl(finalExportResult.paths.summary)} target="_blank" rel="noreferrer">Run summary JSON</a>
                </div>
              )}
            </div>
            <div className="first-priority-list" aria-label="목표 그룹 문서 목록">
              {targetGroupItems.length === 0 ? <p className="muted">목표 그룹 문서가 없습니다.</p> : targetGroupItems.map((item) => (
                <button
                  key={item.docId}
                  className={`${item.docId === selectedDocId ? 'priority-doc-card active' : 'priority-doc-card'} status-bg-${workItemTone(item)}`}
                  onClick={() => selectDocument(item.docId)}
                  onContextMenu={(event) => openAssessmentPopover(event, item)}
                  title="우클릭: 생성 가능성 판정 편집"
                >
                  <strong>{item.title}</strong>
                  <WorkItemProgress item={item} compact />
                  <span className="priority-doc-meta">
                    <span className={`writing-method ${writingMethodTone(item)}`}>{writingMethodLabel(item)}</span>
                    <span className={workItemIsComplete(item) ? 'next-action complete' : 'next-action'}>{workItemNextAction(item)}</span>
                    <span>{item.statusLabel}</span>
                    {item.needsSynthesis && <span className="need-collect">합성 필요</span>}
                    {item.sampleAvailability === 'internal_ready' && <span className="sample-ready">사내 샘플</span>}
                    {item.sampleAvailability === 'workbench_loaded' && <span className="seed-ready">적재됨</span>}
                    {item.sampleAvailability === 'finalized' && <span className="sample-ready complete">대체 완료</span>}
                    {item.hasPendingSeed && <span className="seed-ready">seed 발견</span>}
                    {(assessmentRowsByDocId.get(item.docId) || []).map((row) => <span key={row.key} className={`assessment-mini ${assessmentTone(row.feasibility)}`}>{row.domain}:{row.feasibilityLabel}</span>)}
                    <span>{item.sampleCount}개</span>
                  </span>
                </button>
              ))}
            </div>
          </section>

          <section className="panel-block compact doc-filter-block">
            <h2>문서 현황판</h2>
            <input placeholder="문서명/ID 검색" value={search} onChange={(event) => setSearch(event.target.value)} />
            <div className="checkbox-filter-block">
              <div className="checkbox-filter-head"><b>도메인</b><small>{domainFilters.length ? `${domainFilters.length}개 선택` : '전체'}</small></div>
              <div className="checkbox-filter-list">
                {(registry?.poDomains || registry?.domains || []).map((domain) => (
                  <label key={domain} className="checkbox-filter-row">
                    <input type="checkbox" checked={domainFilters.includes(domain)} onChange={() => setDomainFilters((current) => toggleArrayValue(current, domain))} />
                    <span>{domain}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="checkbox-filter-block">
              <div className="checkbox-filter-head"><b>진척도</b><small>{statusFilters.length ? statusFilters.map((id) => WORK_STATUS_GROUP_LABELS[id]).join(', ') : '전체'}</small></div>
              <div className="checkbox-filter-list compact">
                {WORK_STATUS_GROUPS.map(([id, label]) => (
                  <label key={id} className="checkbox-filter-row">
                    <input type="checkbox" checked={statusFilters.includes(id)} onChange={() => setStatusFilters((current) => toggleArrayValue(current, id))} />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="checkbox-filter-block">
              <div className="checkbox-filter-head"><b>샘플/합성</b><small>{sampleAvailabilityFilters.length ? sampleAvailabilityFilters.map((id) => SAMPLE_AVAILABILITY_LABELS[id]).join(', ') : '전체'}</small></div>
              <div className="checkbox-filter-list compact">
                {SAMPLE_AVAILABILITY_FILTERS.map(([id, label]) => (
                  <label key={id} className="checkbox-filter-row">
                    <input type="checkbox" checked={sampleAvailabilityFilters.includes(id)} onChange={() => setSampleAvailabilityFilters((current) => toggleArrayValue(current, id))} />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>
            <p className="muted mini-help">도메인은 `DEEP_Agent_문서분류_레지스트리_v2.2.xlsx`의 3번째 시트를 기준으로 분류합니다. 진척도는 seed 상태나 별도 문서가 아니라 workbench 산출물만으로 계산합니다.</p>
            <div className="button-row compact-buttons single-action-row">
              <button className="primary" onClick={createTargetGroupDraftFromFilteredItems} disabled={!filteredItems.length || isBusy}>
                현재 필터 결과로 새 그룹
              </button>
            </div>
          </section>

          <section className="doc-list">
            {filteredItems.map((item) => (
              <button
                key={item.docId}
                className={`${item.docId === selectedDocId ? 'doc-card active' : 'doc-card'} status-bg-${workItemTone(item)}`}
                onClick={() => selectDocument(item.docId)}
                onContextMenu={(event) => openAssessmentPopover(event, item)}
                title="우클릭: 생성 가능성 판정 편집"
              >
                <div><strong>{item.title}</strong><small>{item.docId}</small></div>
                <WorkItemProgress item={item} />
                <div className="doc-card-meta">
                  <span className={`writing-method ${writingMethodTone(item)}`}>{writingMethodLabel(item)}</span>
                  <span className={workItemIsComplete(item) ? 'next-action complete' : 'next-action'}>{workItemNextAction(item)}</span>
                  {item.hasPendingSeed && <span className="seed-ready">seed 발견</span>}
                  {item.needsSynthesis && <span className="need-collect">합성 필요</span>}
                  {item.sampleAvailability === 'internal_ready' && <span className="sample-ready">사내 샘플</span>}
                  {item.sampleAvailability === 'workbench_loaded' && <span className="seed-ready">적재됨</span>}
                  {item.sampleAvailability === 'finalized' && <span className="sample-ready complete">대체 완료</span>}
                  <span>{item.statusLabel}</span>
                  <span>{item.sampleCount}개</span>
                </div>
              </button>
            ))}
          </section>
        </aside>

        <main className="canvas-panel fixed-panel">
          {message && <div className="notice success">{message}</div>}
          {error && <div className="notice error">{error}</div>}
          <section className="selected-context">
            <div>
              <h2>{selectedDoc?.title || '문서를 선택하세요'}</h2>
              <p className="muted">{selectedDoc?.poDomains?.length ? `도메인: ${selectedDoc.poDomains.join(' · ')}` : '도메인 정보 없음'}{(selectedDoc?.workflowDomains || selectedDoc?.domains || []).length ? ` / 업무: ${(selectedDoc.workflowDomains || selectedDoc.domains).join(' · ')}` : ''}</p>
            </div>
            <div className="context-chips">
              {selectedDoc?.issuer && <span>{selectedDoc.issuer}</span>}
              {selectedDoc?.genre && <span>{selectedDoc.genre}</span>}
              {selectedDoc?.structure && <span>{selectedDoc.structure}</span>}
              {selectedDoc?.sensitivity && <span>{selectedDoc.sensitivity}</span>}
            </div>
          </section>

          <section className="canvas-card workbench-canvas-card">
            <div className="canvas-toolbar">
              <div>
                <b>{canvasTitle}</b>
                <p className="muted">{canvasSubtitle}{reviewDirty ? ' · 저장 안 됨' : ''}</p>
              </div>
              <div className="canvas-actions">
                {policy && canvasMode === 'review' && !selectedWorkflowLocked && (
                  <label className={`switch-control ${bboxEditMode === 'edit' ? 'on' : ''}`}>
                    <input
                      type="checkbox"
                      checked={bboxEditMode === 'edit'}
                      disabled={isBusy}
                      onChange={(event) => setBboxEditMode(event.target.checked ? 'edit' : 'select')}
                    />
                    <span className="switch-track" aria-hidden="true"><span /></span>
                    <span className="switch-label">BBox 편집</span>
                  </label>
                )}
                {selectedWorkflowLocked ? (
                  <div className="stage-tabs final-tabs"><button className="active" disabled>최종 산출물</button></div>
                ) : (
                  <div className="stage-tabs">
                    <button className={canvasMode === 'review' ? 'active' : ''} onClick={() => setCanvasMode('review')} disabled={!policy}>BBox 리뷰</button>
                    {!selectedIsBlankTemplate && <button className={canvasMode === 'inpaint' ? 'active' : ''} onClick={() => setCanvasMode('inpaint')} disabled={!inpaintedPath}>인페인팅</button>}
                    {!selectedIsBlankTemplate && <button className={canvasMode === 'cleanup' ? 'active' : ''} onClick={() => setCanvasMode('cleanup')} disabled={!policy || !inpaintedPath}>템플릿 클린업</button>}
                    <button className={canvasMode === 'authoring' ? 'active' : ''} onClick={() => setCanvasMode('authoring')} disabled={!authoringBundle}>Authoring</button>
                  </div>
                )}
                <div className="viewport-buttons">
                  {VIEWPORT_MODES.map(([id, label]) => (
                    <button key={id} className={viewportMode === id ? 'active' : ''} onClick={() => setViewportMode(id)}>{label}</button>
                  ))}
                </div>
              </div>
            </div>
            {showFinalOutputCanvas ? (
              selectedFinalOutput.previewPath || selectedFinalOutput.pdfPath ? (
                <SamplePreview path={selectedFinalOutput.previewPath || selectedFinalOutput.pdfPath} viewportMode={viewportMode} />
              ) : (
                <div className="empty final-empty">
                  <b>최종 샘플이 아직 없습니다.</b>
                  <p>이 문서는 작업 불가로 분류되어 BBox/인페인팅/합성 파이프라인을 사용하지 않습니다. 클린룸 샘플 또는 수집 완료본을 먼저 적재하세요.</p>
                </div>
              )
            ) : showAuthoringCanvas ? (
              <AuthoringCanvas
                imagePath={authoringCanvasImagePath}
                version={authoringCanvasVersion}
                image={authoringBundle.schema?.image}
                fields={authoringFields}
                selectedFieldIds={selectedAuthoringFieldIds}
                setSelectedFieldIds={selectAuthoringFields}
                viewportMode={viewportMode}
                qrBox={selectedIsHandwriting ? authoringQrBox : null}
                qrEditMode={selectedIsHandwriting && authoringQrEditMode}
                onQrBoxChange={updateAuthoringQrBox}
                conflicts={authoringAgentConflictPopover?.conflicts || []}
                conflictResolutions={authoringAgentConflictResolutions}
                focusedConflictId={focusedAuthoringAgentConflictId}
                onConflictSelect={(conflictId) => focusAuthoringAgentConflict(
                  authoringAgentConflictPopover?.conflicts?.find((conflict) => conflict.id === conflictId),
                )}
              />
            ) : showCleanupCanvas ? (
              <CleanupCanvas
                imagePath={inpaintedPath}
                version={cleanupVersion || inpaintVersion}
                image={policy.image}
                mask={cleanupMask}
                selectedId={selectedCleanupId}
                setSelectedId={setSelectedCleanupId}
                tool={cleanupTool}
                color={cleanupMask?.selected_color || [255, 255, 255]}
                radius={cleanupMask?.brush_radius || 10}
                onSampleColor={sampleCleanupColor}
                onAddStroke={addCleanupStroke}
                viewportMode={viewportMode}
              />
            ) : showInpaintCanvas ? (
              <SamplePreview path={inpaintedPath} version={inpaintVersion} viewportMode={viewportMode} />
            ) : policy ? (
              <DocumentCanvas policy={policy} setPolicy={setEditedPolicy} selectedIds={selected} setSelectedIds={setSelectedIds} editMode={bboxEditMode} viewportMode={viewportMode} showRenderMode={false} />
            ) : selectedSample ? (
              <SamplePreview path={selectedSample} viewportMode={viewportMode} />
            ) : <div className="empty">왼쪽 입고함에서 자동 적재하거나, 수집 필요 문서를 확인하세요.</div>}
          </section>
        </main>

        <aside className="action-panel fixed-panel">
          <section className="panel-block">
            <div className="block-title-row">
              <h2>선택 문서 seed</h2>
              <button className="danger slim" onClick={() => run(revertSelectedSeedImport)} disabled={!selectedItem?.sampleCount || isBusy}>적재 되돌리기</button>
            </div>
            <p className="muted">연결된 seed 폴더와 적재 상태입니다. 되돌리기는 샘플/파이프라인 산출물을 보관함으로 이동합니다.</p>
            <button onClick={() => run(() => previewSelectedSeedRevert())} disabled={!selectedItem?.sampleCount || isBusy}>
              {busy === 'seedRevertPreview' ? '미리보기 중...' : '되돌리기 영향 미리보기'}
            </button>
            {selectedItem?.hasEditableOfficeTemplate && (
              <div className="audit-box office-render-box">
                <b>편집 가능한 Office 템플릿</b>
                <span>{selectedItem.officeRender?.backend || 'libreoffice-cli'} · {selectedItem.officeRender?.status || 'external_render_required'}</span>
                <small>DOCX 경로는 LibreOffice+폰트 정규화 고도화 전까지 실험/보류 기능입니다. 외부 GUI 앱 자동화 렌더러는 사용하지 않습니다.</small>
                {selectedItem.latestDocxAnalysis && <small>analysis: {selectedItem.latestDocxAnalysis}</small>}
                {selectedItem.latestDocxRunManifest && <small>latest run: {selectedItem.latestDocxRunManifest}</small>}
                <div className="button-row compact-buttons">
                  <button onClick={() => run(analyzeDocxTemplate)} disabled={isBusy}>
                    {busy === 'docxAnalyze' ? '분석 중...' : 'DOCX 구조 분석'}
                  </button>
                  <button onClick={() => run(draftDocxAuthoring)} disabled={isBusy}>
                    {busy === 'docxDraft' ? '초안 생성 중...' : 'DOCX Schema/Faker 초안'}
                  </button>
                </div>
                <label>DOCX 생성 매수
                  <input type="number" min="1" max="100" value={docxGenerateCount} onChange={(event) => setDocxGenerateCount(event.target.value)} />
                </label>
                <button className="primary" onClick={() => run(generateDocxSamples)} disabled={isBusy}>
                  {busy === 'docxGenerate' ? 'DOCX 값 주입 중...' : 'DOCX 값 주입/선택적 PDF/GT 생성'}
                </button>
                {docxPipelineResult?.summary && <small>최근 결과: {docxPipelineResult.summary.status || 'analysis'} · sample {docxPipelineResult.summary.sampleCount ?? '-'} · warning {docxPipelineResult.summary.warningCount ?? 0}</small>}
              </div>
            )}
            {selectedIsHandwriting && (
              <div className="audit-box handwriting-pipeline-box">
                <b>수기체 데이터 생성</b>
                <span>print pack → 인쇄/작성/스캔 → QR intake → accepted-only export</span>
                <small>수기 문서는 최종 이미지에 텍스트 렌더링을 하지 않습니다. schema/faker/GT만 사전 생성하고 실제 글씨는 작업자 스캔본을 사용합니다.</small>
                <small>최근 print pack: {selectedItem?.latestHandwritingPrintPack || '없음'}</small>
                <small>최근 intake: {selectedItem?.latestHandwritingScanIntake || '없음'} · accepted {selectedItem?.handwritingAcceptedCount || 0} · review {selectedItem?.handwritingReviewRequiredCount || 0}</small>
                <label>Print pack 샘플 수
                  <input type="number" min="1" max="100" value={handwritingPackCount} onChange={(event) => setHandwritingPackCount(event.target.value)} />
                </label>
                <button className="primary" onClick={() => run(createHandwritingPrintPack)} disabled={!selectedItem?.hasAuthoring || isBusy}>
                  {busy === 'handwritingPrintPack' ? '생성 중...' : '수기 Print pack 생성'}
                </button>
                {!selectedItem?.hasAuthoring && <small className="warning-text">먼저 schema/faker authoring을 확정해야 print pack을 만들 수 있습니다.</small>}
                <label>스캔본 폴더 또는 파일 경로
                  <input value={handwritingScanDir} onChange={(event) => setHandwritingScanDir(event.target.value)} placeholder="workbench/documents/.../handwriting_pipeline/scans_inbox" />
                </label>
                <button onClick={() => run(runHandwritingScanIntake)} disabled={!selectedItem?.latestHandwritingPrintPack || !handwritingScanDir.trim() || isBusy}>
                  {busy === 'handwritingScanIntake' ? '매칭 중...' : '스캔 intake / GT 매칭'}
                </button>
                <button onClick={() => openHandwritingScanPopover([])} disabled={isBusy}>
                  scan 문서 처리하기
                </button>
                {handwritingPrintPackResult?.paths?.manifest && <small>생성 manifest: {handwritingPrintPackResult.paths.manifest}</small>}
                {Array.isArray(handwritingPrintPackResult?.manifest?.samples) && handwritingPrintPackResult.manifest.samples.length > 0 && (
                  <small>생성 PDF: {handwritingPrintPackResult.manifest.samples.slice(0, 3).map((sample) => sample.print_pack_pdf).filter(Boolean).join(' · ')}</small>
                )}
                {handwritingScanIntakeResult?.paths?.manifest && <small>intake manifest: {handwritingScanIntakeResult.paths.manifest}</small>}
                {handwritingScanIntakeResult?.summary && (
                  <div className="scan-intake-result">
                    <b>최근 scan 처리 결과</b>
                    <span>accepted {handwritingScanIntakeResult.summary.acceptedCount || 0} · review {handwritingScanIntakeResult.summary.reviewRequiredCount || 0} · scans {handwritingScanIntakeResult.summary.scanCount || 0}</span>
                    <div className="result-link-row">
                      {handwritingScanIntakeResult.urls?.manifest && <a className="result-link compact" href={handwritingScanIntakeResult.urls.manifest} target="_blank" rel="noreferrer">manifest</a>}
                      {!handwritingScanIntakeResult.urls?.manifest && handwritingScanIntakeResult.paths?.manifest && <a className="result-link compact" href={fileUrl(handwritingScanIntakeResult.paths.manifest)} target="_blank" rel="noreferrer">manifest</a>}
                    </div>
                    {(handwritingScanIntakeResult.manifest?.records || []).slice(0, 8).map((record, index) => (
                      <div className={`scan-intake-record ${record.status || 'unknown'}`} key={`${record.raw_scan || record.sample_id || 'scan'}-${index}`}>
                        <span>{record.status || 'unknown'} · {record.doc_id || '-'} · {record.sample_id || `scan_${index}`}</span>
                        {record.reason && <small className="warning-text">{record.reason}</small>}
                        <div className="result-link-row">
                          {record.qr_removed && <a className="result-link compact" href={fileUrl(record.qr_removed)} target="_blank" rel="noreferrer">QR 제거 이미지</a>}
                          {record.matched_gt && <a className="result-link compact" href={fileUrl(record.matched_gt)} target="_blank" rel="noreferrer">GT</a>}
                          {record.matched_bbox && <a className="result-link compact" href={fileUrl(record.matched_bbox)} target="_blank" rel="noreferrer">BBox</a>}
                          {record.review && <a className="result-link compact" href={fileUrl(record.review)} target="_blank" rel="noreferrer">Review</a>}
                        </div>
                      </div>
                    ))}
                    {(handwritingScanIntakeResult.manifest?.records || []).length > 8 && <small>외 {(handwritingScanIntakeResult.manifest.records.length - 8)}건은 manifest에서 확인</small>}
                  </div>
                )}
              </div>
            )}
            {seedRevertPreview?.docId === selectedDocId && (
              <div className="audit-box">
                <b>되돌리기 미리보기</b>
                <span>상태 → {seedRevertPreview.willResetStatusTo} · 보존 {seedRevertPreview.willPreserveArtifacts.length}종</span>
                {(seedRevertPreview.willMove || []).map((item) => <small key={item.path}>{item.path} · {item.fileCount} files</small>)}
                <small>백업 루트: {seedRevertPreview.backupRoot}</small>
              </div>
            )}
            {matchedSeedFolders.length ? matchedSeedFolders.map((folder) => (
              <div className={`seed-card ${folder.status}`} key={folder.folder}>
                <b>{folder.name}</b><span>{folder.statusLabel} · {folder.fileCount}개</span>
                <div className="button-row compact-buttons">
                  <button onClick={() => run(() => importSeed(folder.folder, folder.matchedDocId))} disabled={folder.status === 'alreadyImported' || isBusy}>{folder.status === 'alreadyImported' ? '적재 완료' : '적재'}</button>
                  <button className="danger" onClick={() => run(() => trashSeedFolder(folder.folder, folder.name))} disabled={isBusy}>보관</button>
                </div>
              </div>
            )) : <p className="muted">연결된 seed가 없습니다. 웹에서 샘플을 수집해 `seed_samples/{selectedDoc?.title || '문서명'}/`에 넣으면 입고함에 표시됩니다.</p>}
          </section>

          {selectedItem?.latestCleanroomPdf && (
            <section className="panel-block cleanroom-library-panel">
              <div className="block-title-row">
                <h2>Cleanroom 라이브러리 샘플</h2>
                <span className={`mode-pill ${selectedItem.hasLibrarySampleAnnotation ? 'ready' : 'edit'}`}>
                  {selectedItem.hasLibrarySampleAnnotation ? '주석 완료' : '주석 필요'}
                </span>
              </div>
              <p className="muted">생성된 cleanroom 페이지 중 대표 1장을 선택하고 OCR/BBox 리뷰 후 flat key/value 주석을 저장합니다. 원본 실문서는 선택할 수 없습니다.</p>
              <div className="button-row compact-buttons">
                <button className="primary" onClick={() => run(() => loadCleanroomLibrary({ edit: true }))} disabled={isBusy}>
                  {busy === 'cleanroomLibraryLoad' ? '불러오는 중...' : selectedItem.hasLibrarySampleAnnotation ? '주석 편집' : '대표 페이지 선택/주석'}
                </button>
                {cleanroomEditing && <button onClick={() => setCleanroomEditing(false)} disabled={isBusy}>편집 닫기</button>}
                {selectedItem.latestLibrarySampleAnnotation && <a className="result-link compact" href={fileUrl(selectedItem.latestLibrarySampleAnnotation)} target="_blank" rel="noreferrer">annotation.json</a>}
              </div>
              {cleanroomEditing && cleanroomLibrary?.pages?.length > 0 && (
                <div className="cleanroom-page-grid">
                  {cleanroomLibrary.pages.map((page) => (
                    <button
                      type="button"
                      key={page.path}
                      className={selectedSample === page.path ? 'cleanroom-page active' : 'cleanroom-page'}
                      onClick={() => { setSelectedSample(page.path); setPolicy(null); setReviewPath(''); setCleanroomFields([]); setCleanroomPrivacy({ include_keys: [], exclude_keys: [] }); setCanvasMode('review'); }}
                    >
                      <img src={page.url} alt={page.name} />
                      <span>{page.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </section>
          )}

          {selectedWorkflowLocked && <FinalOutputPanel finalOutput={selectedFinalOutput} selectedItem={selectedItem} />}

          {!selectedWorkflowLocked && <>
          <section className="panel-block">
            <h2>BBox 검출</h2>
            <label>작업 샘플<select value={selectedSample} onChange={(event) => setSelectedSample(event.target.value)}><option value="">샘플 선택</option>{(cleanroomEditing ? (cleanroomLibrary?.pages || []).map((page) => page.path) : (selectedItem?.samples || [])).map((sample) => <option key={sample} value={sample}>{shortPath(sample)}</option>)}</select></label>
            {!cleanroomEditing && <div className="sample-kind-controls">
              <label className={`check-row ${selectedSampleKind === 'blank_template' ? 'on' : ''}`}>
                <input
                  type="checkbox"
                  checked={selectedSampleKind === 'blank_template'}
                  disabled={!selectedDocId || isBusy}
                  onChange={(event) => run(() => updateSelectedSampleKind(event.target.checked ? 'blank_template' : 'filled_sample'))}
                />
                <span>빈 템플릿 샘플</span>
              </label>
              <small>{selectedIsBlankTemplate ? '빈 템플릿은 인페인팅 없이 PaddleOCR 텍스트 bbox를 먼저 리뷰하고, 필요 시 선/그리드 후보를 추가합니다.' : '값이 들어 있는 샘플은 기존처럼 OCR → 리뷰 → 인페인팅 흐름을 사용합니다.'}</small>
              {selectedIsBlankTemplate && (
                <label className={`check-row ${blankTemplateLineDetectEnabled ? 'on' : ''}`}>
                  <input
                    type="checkbox"
                    checked={blankTemplateLineDetectEnabled}
                    disabled={!selectedDocId || isBusy}
                    onChange={(event) => setBlankTemplateLineDetectEnabled(event.target.checked)}
                  />
                  <span>선/그리드 bbox 후보 추가</span>
                </label>
              )}
            </div>}
            <p className="muted">검출 방식: PaddleOCR 정밀 모드({DEFAULT_OCR_PRESET}){selectedIsBlankTemplate && blankTemplateLineDetectEnabled ? ' + opt-in 선/그리드 후보' : ''}</p>
            {!isImagePath(selectedSample) && selectedSample && <p className="warning-text">현재 OCR GUI 실행은 이미지 파일을 대상으로 합니다. PDF는 변환된 JPG/PNG를 선택하세요.</p>}
            <button className="primary" onClick={() => run(runOcrDetect)} disabled={!selectedDocId || !selectedSample || !isImagePath(selectedSample) || isBusy}>{busy === 'detect' ? 'BBox 검출 중...' : selectedIsBlankTemplate && blankTemplateLineDetectEnabled ? 'PaddleOCR + 선/그리드 후보 검출' : 'PaddleOCR 정밀 BBox 검출'}</button>
            {detectionResult && <p className="mini-path">{detectionResult.paths.detections}</p>}
          </section>

          <section className="panel-block compact review-control-panel">
            <div className="block-title-row">
              <h2>리뷰/분류</h2>
              <span className={bboxEditMode === 'edit' ? 'mode-pill edit' : 'mode-pill'}>{bboxEditMode === 'edit' ? '편집 ON' : '선택 모드'}</span>
            </div>
            <div className="status-summary compact"><Metric label="전체" value={stats.total} /><Metric label="사용" value={stats.byStatus.use} tone="use" /><Metric label="미사용" value={stats.byStatus.keep} tone="keep" /><Metric label="무시" value={stats.byStatus.ignore} tone="ignore" /></div>
            <div className="review-hint-line">
              <span>{bboxEditMode === 'edit' ? '드래그 이동/리사이즈 · 빈 영역 신규' : '클릭/범위/다중선택'}</span>
              <span>⌘S 저장 · ⌘Z 취소 · Del 삭제</span>
            </div>
            <div className="selected-box compact">
              {selectedIds.length ? `${selectedIds.length}개 선택` : '선택 없음'}
              {staleLabels.length ? ` · 재확인 ${staleLabels.length}` : ''}
            </div>
            <div className="status-buttons">{STATUS.map((status, index) => <button key={status} className={`status ${status}`} title={`${index + 1}: ${STATUS_DESCRIPTIONS[status]}`} disabled={!policy || selectedIds.length === 0 || isBusy} onClick={() => setSelectedBboxStatus(status)}><b>{index + 1}</b>{STATUS_LABELS[status]}</button>)}</div>
            <button onClick={() => run(() => runCropRecognition({ mode: 'apply' }))} disabled={!policy || isBusy || (!selectedIds.length && !staleLabels.length)}>
              {busy === 'recognizeCrops'
                ? '텍스트 재인식 중...'
                : selectedIds.length
                  ? `선택 ${selectedIds.length}개 텍스트 재인식`
                  : `수정 ${staleLabels.length}개 텍스트 재인식`}
            </button>
            <button className="danger" onClick={deleteSelectedBboxes} disabled={!policy || selectedIds.length === 0 || isBusy}>선택 BBox 삭제</button>
            <div className="button-row compact-buttons">
              <button onClick={() => run(scanReviewLegacyIssues)} disabled={isBusy}>{busy === 'reviewAudit' ? '스캔 중...' : 'ignore 전체 스캔'}</button>
              <button className="danger" onClick={() => run(removeCurrentIgnoreBboxes)} disabled={!policy || stats.byStatus.ignore <= 0 || isBusy}>
                {busy === 'removeIgnore' ? '제거 중...' : `현재 ignore ${stats.byStatus.ignore}개 제거`}
              </button>
            </div>
            {reviewAudit && <p className="mini-path">전체 ignore: {reviewAudit.summary.ignoreCount}개 / {reviewAudit.summary.documentCount}문서</p>}
            {reviewHistory.length > 0 && <button onClick={undoReview} disabled={!policy || isBusy}>실행 취소 (⌘Z)</button>}
            <button onClick={() => run(() => loadReview())} disabled={!selectedItem?.latestReview || isBusy}>기존 리뷰 불러오기</button>
            <button className="primary" onClick={() => run(() => cleanroomEditing ? saveReview({ skipPruneConfirm: true, pruneAuthoring: false }) : saveReview())} disabled={!policy || isBusy}>{busy === 'save' ? '저장 중...' : reviewDirty ? '리뷰 저장 *' : '리뷰 저장'}</button>
          </section>

          {cleanroomEditing ? (
            <section className="panel-block cleanroom-annotation-panel">
              <h2>Flat Schema / GT / PII 주석</h2>
              <p className="muted">리뷰에서 `사용`으로 지정한 bbox마다 flat export key와 GT value를 지정합니다. PII는 공통 정책을 기본으로 하고 문서 예외만 선택합니다.</p>
              {!policy && <p className="warning-text">선택한 대표 페이지에서 BBox 검출을 먼저 실행하세요.</p>}
              {policy && stats.byStatus.use === 0 && <p className="warning-text">최종 값으로 내보낼 bbox를 `사용`으로 지정하세요.</p>}
              <div className="deep-ocr-panel">
                <div className="block-title-row">
                  <h3>DeepAgent OCR key/value 보조</h3>
                  <span className={`mode-pill ${cleanroomLibrary?.deepOcrCredential?.ready ? 'ready' : 'edit'}`}>
                    {cleanroomLibrary?.deepOcrCredential?.ready ? 'API 준비됨' : 'API key 없음'}
                  </span>
                </div>
                <p className="muted">DeepAgent가 key/value를 추출하고 PaddleOCR BBox 텍스트와 정규화 완전일치하는 값만 자동 선택합니다. DeepAgent 응답의 bbox가 없으므로 나머지는 직접 연결해야 합니다.</p>
                {!cleanroomLibrary?.deepOcrCredential?.permissionSafe && (
                  <p className="warning-text">API key 파일 권한이 {cleanroomLibrary.deepOcrCredential.permissionMode || '알 수 없음'}입니다. 로컬 사용자 전용(600)으로 제한하세요.</p>
                )}
                <div className="button-row compact-buttons">
                  <button
                    className="primary"
                    onClick={() => run(() => runDeepOcr())}
                    disabled={!policy || !cleanroomLibrary?.deepOcrCredential?.ready || isBusy}
                  >
                    {busy === 'deepOcr' ? 'Deep OCR 실행 중...' : 'Deep OCR key/value 추출'}
                  </button>
                  <button
                    onClick={() => run(() => runDeepOcr({ forceRefresh: true }))}
                    disabled={!policy || !cleanroomLibrary?.deepOcrCredential?.ready || isBusy}
                    title="동일 이미지 캐시를 무시하고 외부 API를 다시 호출합니다."
                  >외부 API 다시 호출</button>
                </div>
                {deepOcrPreview && (
                  <>
                    <div className="deep-ocr-summary">
                      <b>추출 {deepOcrPreview.summary?.fieldCount || 0}개</b>
                      <span>exact {deepOcrPreview.summary?.exactCount || 0}</span>
                      <span>ambiguous {deepOcrPreview.summary?.ambiguousCount || 0}</span>
                      <span>unmatched {deepOcrPreview.summary?.unmatchedCount || 0}</span>
                      <span>{deepOcrPreview.summary?.cacheHit ? '캐시 사용' : '외부 API 응답'}</span>
                    </div>
                    <div className="deep-ocr-table-wrap">
                      <table className="deep-ocr-table">
                        <thead><tr><th>적용</th><th>Key / Value</th><th>판정</th><th>Paddle BBox</th></tr></thead>
                        <tbody>
                          {(deepOcrPreview.matches || []).map((match) => {
                            const selection = deepOcrSelections[String(match.fieldIndex)] || { enabled: false, bboxLabelId: '' };
                            return (
                              <tr key={match.fieldIndex} className={`deep-ocr-${match.status}`}>
                                <td><input type="checkbox" checked={Boolean(selection.enabled)} onChange={(event) => updateDeepOcrSelection(match.fieldIndex, { enabled: event.target.checked })} /></td>
                                <td>
                                  <b>{match.key || '(key 없음)'}</b>
                                  <span>{match.value || '(빈 값)'}</span>
                                  <small>{match.confidence == null ? 'confidence 없음' : `confidence ${Number(match.confidence).toFixed(3)}`}</small>
                                </td>
                                <td><span className={`match-pill ${match.status}`}>{match.status}</span></td>
                                <td>
                                  <select
                                    value={selection.bboxLabelId || ''}
                                    onChange={(event) => updateDeepOcrSelection(match.fieldIndex, { bboxLabelId: event.target.value, enabled: Boolean(event.target.value) })}
                                  >
                                    <option value="">BBox 직접 선택</option>
                                    {(policy?.labels || []).map((label) => <option key={label.id} value={label.id}>{label.id} · {label.rec_text || label.text || '(텍스트 없음)'}</option>)}
                                  </select>
                                  {(match.candidates || []).length > 0 && <small>후보: {match.candidates.slice(0, 3).map((candidate) => `${candidate.bboxLabelId} ${Math.round(candidate.score * 100)}%`).join(' · ')}</small>}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    <div className="button-row compact-buttons">
                      <button className="primary" onClick={applyDeepOcrSelections} disabled={!Object.values(deepOcrSelections).some((item) => item.enabled && item.bboxLabelId) || isBusy}>선택 매핑을 BBox/주석에 적용</button>
                      {Object.entries(deepOcrPreview.paths || {}).map(([name, path]) => <a key={name} className="result-link compact" href={fileUrl(path)} target="_blank" rel="noreferrer">{name}.json</a>)}
                    </div>
                    <p className="warning-text">적용은 선택한 BBox를 `사용` 상태로 바꾸고 Export key/GT value를 채우지만 자동 저장하지 않습니다. 리뷰 저장 후 주석 저장을 각각 확인하세요.</p>
                  </>
                )}
              </div>
              <div className="cleanroom-field-list">
                {cleanroomFields.map((field, index) => {
                  const privacyMode = (cleanroomPrivacy.include_keys || []).includes(field.key)
                    ? 'include'
                    : (cleanroomPrivacy.exclude_keys || []).includes(field.key) ? 'exclude' : 'inherit';
                  return (
                    <div className="cleanroom-field-row" key={field.bboxLabelId}>
                      <span className="field-index">{index + 1}</span>
                      <label>Export key<input value={field.key} placeholder="예: 성명" onChange={(event) => updateCleanroomField(field.bboxLabelId, { key: event.target.value })} /></label>
                      <label>GT value<input value={field.value} onChange={(event) => updateCleanroomField(field.bboxLabelId, { value: event.target.value })} /></label>
                      <label>PII
                        <select value={privacyMode} disabled={!field.key} onChange={(event) => updateCleanroomPrivacyKey(field.key, event.target.value)}>
                          <option value="inherit">공통 정책</option>
                          <option value="include">강제 포함</option>
                          <option value="exclude">explicit 목록 제외(자동판정 유지)</option>
                        </select>
                      </label>
                      <small>{field.bboxLabelId}</small>
                    </div>
                  );
                })}
              </div>
              <button
                className="primary"
                onClick={() => run(saveCleanroomLibrary)}
                disabled={!policy || !reviewPath || reviewDirty || !cleanroomFields.length || cleanroomFields.some((field) => !field.key.trim()) || isBusy}
              >
                {busy === 'cleanroomLibrarySave' ? '저장 중...' : 'Cleanroom 라이브러리 주석 저장'}
              </button>
              {reviewDirty && <p className="warning-text">BBox 리뷰를 먼저 저장한 뒤 cleanroom 주석을 저장하세요.</p>}
              {cleanroomLibrary?.privacy?.resolvedKeys?.length > 0 && <p className="mini-path">현재 explicit PII: {cleanroomLibrary.privacy.resolvedKeys.join(', ')}</p>}
            </section>
          ) : selectedIsBlankTemplate ? (
            <section className="panel-block">
              <h2>빈 템플릿 흐름</h2>
              <p className="muted">이 샘플은 이미 깨끗한 양식이므로 인페인팅/템플릿 보정을 건너뜁니다. 리뷰에서 값 입력 bbox를 확정한 뒤 Agentic Authoring 추론을 실행하세요.</p>
            </section>
          ) : (
            <section className="panel-block">
              <h2>LaMa 인페인팅</h2>
              <label>LaMa max side<input type="number" min="512" max="4096" step="128" value={lamaMaxSide} onChange={(event) => setLamaMaxSide(Number(event.target.value) || 2400)} /></label>
              <button className="primary" onClick={() => run(runInpaint)} disabled={!policy || stats.byStatus.use === 0 || !canUseLama || isBusy}>{busy === 'inpaint' ? 'LaMa 실행 중...' : 'LaMa 인페인팅 실행'}</button>
              {!canUseLama && <p className="warning-text">LaMa 런타임이 감지되지 않았습니다. .venv-ocr 설치 상태를 확인하세요.</p>}
            </section>
          )}

          {!cleanroomEditing && !selectedIsBlankTemplate && <section className="panel-block compact">
            <h2>템플릿 보정</h2>
            <p className="muted">LaMa 후처리 대신 스포이드로 주변색을 찍고 브러시로 직접 칠합니다.</p>
            <div className="selected-box">
              브러시 {cleanupMask?.strokes?.length || 0}개{selectedCleanupId ? ` · 선택 ${selectedCleanupId}` : ''}{cleanupDirty ? ' · 저장 안 됨' : ''}
            </div>
            <div className="button-row compact-buttons">
              <button className={cleanupTool === 'eyedropper' ? 'active' : ''} onClick={() => { setCanvasMode('cleanup'); setCleanupTool('eyedropper'); }} disabled={!policy || !inpaintedPath || isBusy}>스포이드</button>
              <button className={cleanupTool === 'brush' ? 'active' : ''} onClick={() => { setCanvasMode('cleanup'); setCleanupTool('brush'); }} disabled={!policy || !inpaintedPath || isBusy}>브러시</button>
            </div>
            <div className="cleanup-controls">
              <label>색상
                <input type="color" value={rgbToHex(cleanupMask?.selected_color || [255, 255, 255])} onChange={(event) => updateCleanupPaintSettings({ selected_color: hexToRgb(event.target.value) })} />
              </label>
              <label>크기
                <input type="number" min="1" max="160" value={cleanupMask?.brush_radius || 10} onChange={(event) => updateCleanupPaintSettings({ brush_radius: clampNumber(event.target.value, 1, 160) })} />
              </label>
            </div>
            <div className="button-row compact-buttons">
              <button onClick={() => { setCanvasMode('cleanup'); run(() => loadCleanupMask()); }} disabled={!policy || !inpaintedPath || isBusy}>
                {busy === 'cleanupLoad' ? '불러오는 중...' : '불러오기'}
              </button>
              <button className={cleanupDirty ? 'primary' : ''} onClick={() => run(() => saveCleanupMask())} disabled={!policy || !inpaintedPath || isBusy}>
                {busy === 'cleanupSave' ? '저장 중...' : cleanupDirty ? '저장 *' : '저장'}
              </button>
            </div>
            <div className="button-row compact-buttons">
              <button onClick={deleteSelectedCleanupMask} disabled={!selectedCleanupId || isBusy}>선택 삭제</button>
              <button onClick={undoCleanupMask} disabled={!cleanupHistory.length || isBusy}>실행 취소</button>
            </div>
            <div className="button-row compact-buttons">
              <button onClick={() => run(scanManualCleanupLegacy)} disabled={isBusy}>{busy === 'manualCleanupAudit' ? '스캔 중...' : 'legacy cleanup 스캔'}</button>
              <button className="danger" onClick={() => run(() => promoteManualCleanup(selectedManualCleanupItems[0]))} disabled={!selectedManualCleanupItems.length || isBusy}>
                {busy === 'manualCleanupPromote' ? '승격 중...' : '현재 문서 cleanup 승격'}
              </button>
            </div>
            {manualCleanupAudit && (
              <div className="audit-box">
                <b>manual_cleanup {manualCleanupAudit.summary.legacyCleanupCount}개</b>
                {selectedManualCleanupItems.length ? selectedManualCleanupItems.slice(0, 2).map((item) => <small key={item.cleanupDir}>{item.cleanupDir} → {item.promoteSource || '승격 대상 없음'}</small>) : <small>현재 문서에는 legacy cleanup이 없습니다.</small>}
              </div>
            )}
            {cleanupResult?.paths?.inpainted && <p className="mini-path">{cleanupResult.paths.inpainted}</p>}
          </section>}

          {!cleanroomEditing && <section className="panel-block authoring-control-panel">
            <h2>Authoring 작업</h2>
            <p className="muted">Schema / Style / Faker / Render를 분리해 다룹니다. 기존 파일 3종이 있으면 문서 선택 시 자동으로 불러와 최종 Pillow 렌더러 live preview를 표시합니다.</p>
            <div className="authoring-step-label"><b>0. Agentic Authoring</b><span>선택 문서 전용 draft 생성·보정</span></div>
            <div className="agent-workflow-shell">
              <section className="agent-compose-card">
                <div className="agent-card-head">
                  <div><b>새 draft 생성</b><small>{selectedDocId} 문서만 대상으로 실행</small></div>
                  <span className="agent-scope-badge">문서 격리</span>
                </div>
                <small className={isImagePath(selectedSample) ? 'agent-mode-help' : 'warning-text'}>
                  Agent 시각 원본: {isImagePath(selectedSample) ? `${shortPath(selectedSample)} 1매만 사용` : '작업 샘플에서 JPG/PNG 페이지 1매를 선택하세요.'}
                </small>
                <textarea
                  className="agent-request-input"
                  placeholder="생성 의도나 주의사항을 입력하세요. 예: 하단 체크박스는 이미지 기준으로 날짜·카드종류·동의여부를 구분."
                  value={authoringAgentInstruction}
                  onChange={(event) => setAuthoringAgentInstruction(event.target.value)}
                />
                <div className="agent-primary-options">
                  <label>실행 방식
                    <select value={authoringAgentExecutionMode} onChange={(event) => setAuthoringAgentExecutionMode(event.target.value)}>
                      {(authoringAgentCapabilities.executionModes || DEFAULT_AUTHORING_AGENT_CAPABILITIES.executionModes)
                        .filter((executionMode) => executionMode !== 'targeted_revision')
                        .map((executionMode) => (
                          <option
                            key={executionMode}
                            value={executionMode}
                            disabled={['faker_only', 'validation_repair'].includes(executionMode) && !latestAgentRequestPath}
                          >
                            {AUTHORING_AGENT_EXECUTION_MODE_LABELS[executionMode] || executionMode}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label>모델
                    <select
                      value={authoringAgentModel}
                      onChange={(event) => {
                        const nextModel = authoringAgentCapabilities.models.find((model) => model.id === event.target.value) || selectedAgentModelCapability;
                        setAuthoringAgentModel(nextModel.id);
                        setAuthoringAgentReasoning((current) => (nextModel.reasoningEfforts || []).includes(current) ? current : nextModel.defaultReasoningEffort || 'medium');
                        if (!nextModel.supportsFastMode) setAuthoringAgentFastMode(false);
                      }}
                    >
                      {authoringAgentCapabilities.models.map((model) => <option key={model.id} value={model.id}>{model.label || model.id}</option>)}
                    </select>
                  </label>
                  <label>사고 레벨
                    <select value={authoringAgentReasoning} onChange={(event) => setAuthoringAgentReasoning(event.target.value)}>
                      {authoringAgentReasoningOptions.map((effort) => <option key={effort} value={effort}>{effort}</option>)}
                    </select>
                  </label>
                </div>
                <small className="agent-mode-help">{authoringAgentExecutionMode === 'two_pass' ? 'Schema를 먼저 고정한 뒤 Faker를 생성합니다.' : authoringAgentExecutionMode === 'single_pass' ? '한 세션에서 전체 draft를 빠르게 생성합니다.' : '기존 request에서 선택한 단계만 다시 실행합니다.'}</small>
                <details className="agent-settings-panel">
                  <summary>세부 실행 설정 <span>기준일·pool·fast·시간 제한</span></summary>
                  <div className="agent-options-grid compact">
                    <label>데이터 기준일
                      <input type="date" value={authoringAsOfDate} onChange={(event) => setAuthoringAsOfDate(event.target.value)} />
                    </label>
                    <label>Scalar pool 최소
                      <input type="number" min="1" max="100" value={authoringAgentScalarPoolMinSize} onChange={(event) => setAuthoringAgentScalarPoolMinSize(clampNumber(event.target.value, 1, 100))} />
                    </label>
                    <label>Record pool 최소
                      <input type="number" min="1" max="100" value={authoringAgentRecordPoolMinSize} onChange={(event) => setAuthoringAgentRecordPoolMinSize(clampNumber(event.target.value, 1, 100))} />
                    </label>
                    <label className={`check-row ${authoringAgentFastMode ? 'on' : ''}`} title={selectedAgentModelCapability.supportsFastMode ? '' : '선택한 모델은 fast mode를 지원하지 않습니다.'}>
                      <input type="checkbox" checked={authoringAgentFastMode} disabled={!selectedAgentModelCapability.supportsFastMode} onChange={(event) => setAuthoringAgentFastMode(event.target.checked)} />
                      <span>fast mode</span>
                    </label>
                    <label className={`check-row ${authoringAgentTimeBudgetEnabled ? 'on' : ''}`}>
                      <input type="checkbox" checked={authoringAgentTimeBudgetEnabled} onChange={(event) => setAuthoringAgentTimeBudgetEnabled(event.target.checked)} />
                      <span>시간 제한</span>
                    </label>
                    {authoringAgentTimeBudgetEnabled && <label>최대 실행 시간(분)
                      <input type="number" min="5" max="60" value={authoringAgentTimeBudgetMinutes} onChange={(event) => setAuthoringAgentTimeBudgetMinutes(clampNumber(event.target.value, 5, 60))} />
                    </label>}
                  </div>
                </details>
                <div className="button-row compact-buttons agent-main-actions">
                  <button
                    className="primary"
                    onClick={() => run(() => runAuthoringAgentInference('authoring', authoringAgentExecutionMode))}
                    disabled={!selectedDocId || !isImagePath(selectedSample) || !reviewPath || isBusy || (['faker_only', 'validation_repair'].includes(authoringAgentExecutionMode) && !latestAgentRequestPath)}
                  >
                    {busy === 'authoringAgentRun' ? 'Agent 시작 중...' : `${AUTHORING_AGENT_EXECUTION_MODE_LABELS[authoringAgentExecutionMode] || 'Agent 추론'} 실행`}
                  </button>
                  <button onClick={() => run(() => refreshAuthoringAgentRunStatus())} disabled={!latestAgentRunPath || isBusy}>상태 새로고침</button>
                  <button onClick={() => run(() => createAuthoringAgentRequest('authoring'))} disabled={!selectedDocId || !isImagePath(selectedSample) || !reviewPath || isBusy}>
                    {busy === 'authoringAgentRequest' ? '생성 중...' : '요청 파일만 생성'}
                  </button>
                </div>
              </section>

              {latestAgentRunPath && (
                <section className={`audit-box agent-run-box ${latestAgentRunStatus}`}>
                  <div className="agent-run-summary">
                    <div><b>Agent {latestAgentRunStatus}</b><small>{formatElapsedSeconds(latestAgentElapsedSeconds)}{latestAgentRunPolling ? ' · 자동 갱신 중' : ''}</small></div>
                    {selectedAgentRun?.validation?.summary && <span>draft {selectedAgentRun.validation.summary.present}/{selectedAgentRun.validation.summary.required}</span>}
                  </div>
                  {selectedAgentRun?.passState && <small>pass {selectedAgentRun.passState.current} · 완료 {(selectedAgentRun.passState.completed || []).join(' → ') || '없음'}</small>}
                  {latestAgentRunReady && <small>전체 draft 생성 및 JSON 검증 완료</small>}
                  {selectedAgentRun?.validation?.scope === 'schema' && selectedAgentRun?.validation?.ready && <small>Schema 검증 완료 · Faker 단계 실행 가능</small>}
                  {(selectedAgentRun?.validation?.contractErrors || []).slice(0, 5).map((item, index) => <small className="agent-validation-error" key={`${item.code || 'validation'}-${item.field || index}`}>{item.code || 'validation_error'}{item.field ? ` · ${item.field}` : ''}{item.anchor_id ? ` · ${item.anchor_id}` : ''} — {item.message || '보정 필요'}</small>)}
                  {latestAgentRunNeedsRepair && <small className="agent-repair-hint">검증 오류 {latestAgentValidationIssueCount || selectedAgentRun?.validation?.summary?.contractErrors || 0}건 · 검증 보정을 실행하세요.</small>}
                  {selectedAgentRun?.error && <small>{selectedAgentRun.error}</small>}
                  <details className="agent-run-details">
                    <summary>실행 상세</summary>
                    <small>{latestAgentRunPath}</small>
                    {(selectedAgentRun?.stages || []).map((stage) => <small key={`${stage.stage}-${stage.startedAt}`}>{stage.stage} · {stage.status} · {formatElapsedSeconds(stage.durationSeconds)}{stage.tokensUsed != null ? ` · ${Number(stage.tokensUsed).toLocaleString()} tokens` : ''} · {stage.model}/{stage.reasoningEffort}{stage.fastMode ? '/fast' : ''}</small>)}
                    {selectedAgentRun?.repairSummary?.materializedCount > 0 && <small>누락 use bbox 자동 보강 {selectedAgentRun.repairSummary.materializedCount}건</small>}
                  </details>
                </section>
              )}

              {latestAgentRunNeedsRepair && latestAgentRequestPath && (
                <div className="button-row single-action-row">
                  <button className="primary" onClick={() => run(() => runAuthoringAgentInference('authoring', 'validation_repair'))} disabled={!isImagePath(selectedSample) || !reviewPath || authoringAgentRetryBusy}>검증 보정 실행</button>
                </div>
              )}

              {latestAgentRequestPath && (
                <section className={`agent-revision-card ${latestAgentRunReady ? 'ready' : ''}`}>
                  <div className="agent-card-head">
                    <div><b>요청으로 부분 보정</b><small>현재 {selectedDocId} draft에서 요청한 부분만 최소 수정</small></div>
                    <span className="agent-scope-badge">다른 문서 미변경</span>
                  </div>
                  <textarea
                    className="agent-revision-input"
                    placeholder="예: 성명 필드의 글자 크기만 1px 줄이고, 그 외 필드·faker·bbox는 유지해줘."
                    value={authoringAgentRevisionInstruction}
                    disabled={!latestAgentRunReady || authoringAgentRetryBusy}
                    onChange={(event) => setAuthoringAgentRevisionInstruction(event.target.value)}
                  />
                  <div className="agent-revision-footer">
                    <small>{latestAgentRunReady ? '실행 전 draft는 run 폴더에 자동 백업됩니다. 완료 후 Draft 최종 Authoring 적용을 다시 실행하세요.' : '전체 draft 검증 완료 후 사용할 수 있습니다.'}</small>
                    <button
                      className="primary"
                      onClick={() => run(() => runAuthoringAgentInference('authoring', 'targeted_revision', authoringAgentRevisionInstruction))}
                      disabled={!latestAgentRunReady || !isImagePath(selectedSample) || !reviewPath || !authoringAgentRevisionInstruction.trim() || authoringAgentRetryBusy}
                    >요청 보정 실행</button>
                  </div>
                </section>
              )}

              {latestAgentRunPath && (
                <div className="agent-terminal-box">
                  <div className="agent-terminal-head">
                    <b>Codex CLI 로그</b>
                    <div className="agent-terminal-actions">
                      <label className="check-row">
                        <input type="checkbox" checked={authoringAgentTerminalAutoScroll} onChange={(event) => setAuthoringAgentTerminalAutoScroll(event.target.checked)} />
                        <span>자동 스크롤</span>
                      </label>
                      <button onClick={() => setAuthoringAgentTerminalOpen((current) => !current)}>{authoringAgentTerminalOpen ? '접기' : '열기'}</button>
                    </div>
                  </div>
                  {authoringAgentTerminalOpen && <>
                    <pre ref={authoringAgentTerminalPreRef}>{authoringAgentTerminalText || (latestAgentRunPolling ? '터미널 출력을 기다리는 중...' : '표시할 터미널 출력이 없습니다.')}</pre>
                    <div className="agent-terminal-footer">
                      <small>{Number(authoringAgentTerminalOffsetRef.current).toLocaleString()} bytes</small>
                      <button onClick={() => {
                        setAuthoringAgentTerminalAutoScroll(true);
                        if (authoringAgentTerminalPreRef.current) authoringAgentTerminalPreRef.current.scrollTop = authoringAgentTerminalPreRef.current.scrollHeight;
                      }}>최신 위치</button>
                      {selectedAgentRun?.terminalPath && <a href={fileUrl(selectedAgentRun.terminalPath)} target="_blank" rel="noreferrer">전체 로그</a>}
                    </div>
                  </>}
                </div>
              )}

              <details className="agent-tools-panel">
                <summary>재실행·적용 도구 <span>고급 작업</span></summary>
                {latestAgentRequestPath && (
                  <div className="button-row compact-buttons agent-retry-buttons">
                    <button onClick={() => run(() => runAuthoringAgentInference('authoring', 'schema_only'))} disabled={!isImagePath(selectedSample) || !reviewPath || authoringAgentRetryBusy}>Schema 재실행</button>
                    <button onClick={() => run(() => runAuthoringAgentInference('authoring', 'faker_only'))} disabled={!isImagePath(selectedSample) || !reviewPath || authoringAgentRetryBusy}>Faker 재실행</button>
                    <button onClick={() => run(() => runAuthoringAgentInference('authoring', 'validation_repair'))} disabled={!isImagePath(selectedSample) || !reviewPath || authoringAgentRetryBusy || !latestAgentRunNeedsRepair}>검증 보정</button>
                    {latestAgentRunCanCancel && <button className="danger" onClick={() => run(cancelAuthoringAgentRun)} disabled={isBusy || latestAgentRunStatus === 'cancelling'}>{busy === 'authoringAgentCancel' || latestAgentRunStatus === 'cancelling' ? '취소 처리 중...' : '실행 취소'}</button>}
                  </div>
                )}
                <div className="button-row compact-buttons">
                  <button onClick={() => run(() => runAuthoringAgentInference('bbox_correction', 'single_pass'))} disabled={!selectedDocId || !isImagePath(selectedSample) || !reviewPath || isBusy}>{busy === 'authoringAgentBboxRun' ? '시작 중...' : 'BBox 보정 draft'}</button>
                  <button onClick={() => run(loadAuthoringLibrary)} disabled={isBusy}>Faker 라이브러리</button>
                  <button onClick={() => run(approveAuthoringDraftsToLibrary)} disabled={!latestAgentRequestPath || isBusy}>승인 기록</button>
                  <button className={latestAgentRunReady ? 'primary' : ''} onClick={() => run(applyAuthoringAgentDrafts)} disabled={!latestAgentRunReady || isBusy}>Draft 최종 적용</button>
                </div>
                {latestAgentRequestPath && <details className="agent-paths"><summary>최근 request 경로</summary><p className="mini-path">{latestAgentRequestPath}{latestAgentPromptPath ? ` · prompt: ${latestAgentPromptPath}` : ''}{latestAgentAnchorMapPath ? ` · anchor: ${latestAgentAnchorMapPath}` : ''}</p></details>}
                {authoringLibrary && <p className="mini-path">Library: profile {authoringLibrary.summary.profileTypeCount}종 · pool {authoringLibrary.summary.valuePoolCount}개 · approval {authoringLibrary.summary.approvalCount}건</p>}
                {authoringApprovalResult?.approval && <p className="mini-path">최근 승인: {authoringApprovalResult.approval.path} · missing {authoringApprovalResult.summary.missing}</p>}
              </details>
              <p className="agent-scope-note">Agent는 현재 선택한 페이지 이미지 1매와 해당 review snapshot만 읽고, 선택 문서의 draft request 폴더만 수정합니다. PDF 완본과 다른 페이지는 범위에서 제외됩니다.</p>
            </div>
            <div className="authoring-step-label"><b>1. Schema · Style · Faker</b><span>키/생성 규칙/스타일 편집</span></div>
            <div className="button-row">
              <button onClick={() => run(() => loadAuthoringBundle())} disabled={!canLoadAuthoring || isBusy}>
                {busy === 'authoringLoad' ? '불러오는 중...' : 'Authoring 불러오기'}
              </button>
              <button className={authoringDirty ? 'primary' : ''} onClick={() => run(() => saveAuthoringBundle())} disabled={!authoringBundle || isBusy}>
                {busy === 'authoringSave' ? '저장 중...' : authoringDirty ? 'Authoring 저장 *' : 'Authoring 저장'}
              </button>
              <button onClick={() => run(() => validateAuthoringConsistency({ strictReviewCoverage: true }))} disabled={!authoringBundle || isBusy}>
                {busy === 'authoringValidate' ? '검사 중...' : '정합성 검사'}
              </button>
            </div>
            {authoringBundle?.consistency && (
              <div className={`audit-box ${authoringBundle.consistency.ready ? 'agent-run-box succeeded' : 'agent-run-box failed'}`}>
                <b>Authoring 정합성: {authoringBundle.consistency.ready ? 'OK' : '오류'}</b>
                <small>errors {authoringBundle.consistency.summary?.errorCount || 0} · warnings {authoringBundle.consistency.summary?.warningCount || 0} · fields {authoringBundle.consistency.summary?.fieldCount || 0} · semantic leaves {authoringBundle.consistency.summary?.semanticLeafCount || 0}</small>
                {(authoringBundle.consistency.errors || []).slice(0, 3).map((item, index) => <small key={index}>{item.code}{item.field ? ` · ${item.field}` : ''}{item.semantic_path ? ` · ${item.semantic_path}` : ''}</small>)}
              </div>
            )}
            {authoringLivePreview?.error && <p className="warning-text">Live preview 렌더링 오류: {authoringLivePreview.error}</p>}
            {missingAuthoringFields.length > 0 && (
              <p className="warning-text">Review에서 삭제되었거나 미사용 상태인 bbox에 연결된 Authoring field {missingAuthoringFields.length}개가 숨겨져 있습니다. BBox 리뷰 저장 시 정합성 경고에서 삭제를 확정하세요.</p>
            )}
            {authoringBundle && (
              <AuthoringEditor
                fields={authoringFields}
                selectedField={selectedAuthoringField}
                selectedFields={selectedAuthoringFields}
                selectedFieldIds={selectedAuthoringFieldIds}
                setSelectedFieldIds={selectAuthoringFields}
                fakerRuleExamples={fakerRuleExamples}
                fakerProfile={authoringBundle.faker_profile}
                stylesheet={authoringBundle.stylesheet}
                selectedStyle={selectedAuthoringStyle}
                fontOptions={fontOptions}
                isHandwritingDocument={selectedIsHandwriting}
                privacy={authoringBundle.schema?.privacy || {}}
                privacyPolicy={authoringBundle.librarySamplePrivacy || {}}
                onFieldChange={updateAuthoringField}
                onPrivacyChange={updateDocumentPrivacyKey}
                onRenderModeChange={updateAuthoringFieldRenderModes}
                onStyleChange={updateAuthoringStyles}
                onRenderPolicyChange={updateAuthoringRenderPolicies}
                onRefreshFonts={() => run(refreshFonts)}
                onGotoReview={() => setCanvasMode('review')}
              />
            )}
            {authoringBundle && (
              <details className="raw-json-section">
                <summary>Semantic Schema / Full Schema / Style / Faker raw JSON 편집</summary>
                <p className="muted">사용자 primary schema는 Semantic Schema입니다. Semantic Schema를 수정하면 기존 bbox binding은 leaf 순서와 기존 semantic_path 기준으로 full schema에 자동 연동됩니다. 저장 버튼을 누르기 전까지 파일은 변경되지 않습니다.</p>
                <label>Semantic Schema JSON (Primary)
                  <textarea key={`semantic-${authoringVersion}-${authoringDirty}`} rows="7" defaultValue={JSON.stringify(authoringBundle.schema?.semantic_schema || {}, null, 2)} onBlur={(event) => applySemanticSchemaRawJson(event.target.value)} />
                </label>
                <label>Full Schema JSON (Advanced / bbox binding 포함)
                  <textarea key={`schema-${authoringVersion}-${authoringDirty}`} rows="7" defaultValue={JSON.stringify(authoringBundle.schema, null, 2)} onBlur={(event) => applyAuthoringRawJson('schema', event.target.value)} />
                </label>
                <label>Stylesheet JSON
                  <textarea key={`stylesheet-${authoringVersion}-${authoringDirty}`} rows="7" defaultValue={JSON.stringify(authoringBundle.stylesheet, null, 2)} onBlur={(event) => applyAuthoringRawJson('stylesheet', event.target.value)} />
                </label>
                <label>Faker Profile JSON
                  <textarea key={`faker-${authoringVersion}-${authoringDirty}`} rows="7" defaultValue={JSON.stringify(authoringBundle.faker_profile, null, 2)} onBlur={(event) => applyAuthoringRawJson('faker_profile', event.target.value)} />
                </label>
              </details>
            )}
            <div className="authoring-step-label"><b>2. Render</b><span>live preview와 샘플 생성</span></div>
            {selectedIsHandwriting && authoringBundle && (
              <div className="authoring-edit-section handwriting-authoring-section">
                <div className="section-mini-title"><b>수기 QR bbox</b><span>print pack / scan decode 위치</span></div>
                <div className="button-row compact-buttons">
                  <button className={authoringQrEditMode ? 'active' : ''} onClick={() => setAuthoringQrEditMode((current) => !current)} disabled={isBusy}>
                    {authoringQrEditMode ? 'QR bbox 지정 모드 종료' : 'QR bbox 드래그 지정'}
                  </button>
                  <button onClick={() => run(() => renderAuthoringLivePreview({ silent: false }))} disabled={isBusy}>
                    QR/인쇄체 live preview
                  </button>
                </div>
                <div className="bbox-readonly-grid">
                  {(authoringQrBox || [0, 0, 0, 0]).map((value, index) => (
                    <label key={index}>{['x', 'y', 'w', 'h'][index]}
                      <input type="number" value={value} onChange={(event) => {
                        const next = [...(authoringQrBox || [0, 0, 180, 180])];
                        next[index] = Number(event.target.value) || 0;
                        updateAuthoringQrBox(next, { changedIndex: index });
                      }} />
                    </label>
                  ))}
                </div>
                <p className="muted">QR bbox 지정 모드에서 문서 위를 드래그하면 정사각형 영역으로 저장됩니다. scan intake는 모든 print pack의 QR bbox crop을 순회해 decode합니다.</p>
              </div>
            )}
            <button onClick={() => run(() => renderAuthoringLivePreview({ silent: false }))} disabled={!authoringBundle || isDocxAuthoringBundle || isBusy}>
              {busy === 'authoringLivePreview' ? 'Live preview 갱신 중...' : 'Live preview 새로고침'}
            </button>
            {isDocxAuthoringBundle && <p className="muted">DOCX 템플릿은 이미지 텍스트 렌더 preview 대신 DOCX 값 주입 경로를 사용합니다. PDF 렌더는 LibreOffice 기반 실험 기능이며 외부 GUI 앱 자동화 렌더러는 사용하지 않습니다.</p>}
            {selectedIsHandwriting && <p className="muted">수기 문서 live preview는 최종 제출용 렌더가 아니라, 인쇄체로 처리할 bbox와 QR 위치를 확인하는 용도입니다. 필기체 bbox 값은 답안지에만 출력됩니다.</p>}
            <div className="button-row single-action-row">
              <button onClick={() => run(() => renderAuthoringBatch({ all: false }))} disabled={!canLoadAuthoring || selectedIsHandwriting || isBusy}>
                {busy === 'authoringBatch' ? '5장 생성 중...' : selectedIsHandwriting ? '수기 문서는 렌더 생성 불가' : '선택 문서 5장 생성'}
              </button>
            </div>
            {authoringPaths.schema && <p className="mini-path">{authoringPaths.schema}{authoringDirty ? ' · 수정됨' : ''}</p>}
            {selectedItem?.hasEditableOfficeTemplate && (
              <div className="batch-result-box compact office-render-box">
                <div className="batch-result-head"><b>DOCX 템플릿 렌더 lineage</b><span>{selectedItem.officeRender?.status || 'external_render_required'}</span></div>
                <p className="muted">DOCX 셀 anchor와 faker value set을 source of truth로 삼아 채워진 DOCX와 GT를 추적합니다. PDF/page image는 LibreOffice 기반 선택 산출물이며 bbox 자동화는 보류합니다.</p>
                <div className="result-link-row">
                  {selectedItem.latestDocxAnalysis && <a className="result-link compact" href={fileUrl(selectedItem.latestDocxAnalysis)} target="_blank" rel="noreferrer">Analysis</a>}
                  {selectedItem.latestDocxAnchorMap && <a className="result-link compact" href={fileUrl(selectedItem.latestDocxAnchorMap)} target="_blank" rel="noreferrer">Anchor map</a>}
                  {selectedItem.latestDocxRunManifest && <a className="result-link compact" href={fileUrl(selectedItem.latestDocxRunManifest)} target="_blank" rel="noreferrer">Run manifest</a>}
                  {selectedItem.latestDocxGt && <a className="result-link compact" href={fileUrl(selectedItem.latestDocxGt)} target="_blank" rel="noreferrer">GT dir</a>}
                  {selectedItem.latestDocxBbox && <a className="result-link compact" href={fileUrl(selectedItem.latestDocxBbox)} target="_blank" rel="noreferrer">BBox dir</a>}
                </div>
              </div>
            )}
            {(authoringPreviewPath || authoringOverlayHref || batchSummaryHref || batchFirstImageHref) && (
              <div className="batch-result-box compact">
                <div className="batch-result-head">
                  <b>렌더 결과</b>
                  {authoringBatchResult?.summary && <span>문서 {authoringBatchResult.summary.documentCount} · 이미지 {authoringBatchResult.summary.sampleCount} · 경고 {authoringBatchResult.summary.warningCount}</span>}
                </div>
                <div className="result-link-row">
                  {authoringPreviewPath && <a className="result-link compact" href={fileUrl(authoringPreviewPath, authoringVersion)} target="_blank" rel="noreferrer">Preview</a>}
                  {authoringOverlayHref && <a className="result-link compact" href={authoringOverlayHref} target="_blank" rel="noreferrer">Overlay</a>}
                  {batchSummaryHref && <a className="result-link compact" href={batchSummaryHref} target="_blank" rel="noreferrer">Summary</a>}
                  {batchManifestHref && <a className="result-link compact" href={batchManifestHref} target="_blank" rel="noreferrer">Manifest</a>}
                  {batchFirstImageHref && <a className="result-link compact" href={batchFirstImageHref} target="_blank" rel="noreferrer">첫 샘플</a>}
                </div>
              </div>
            )}
          </section>}
          </>}
        </aside>
      </div>
    </div>
  );
}

function isAuthoringCheckboxField(field, fakerProfile = null) {
  const fieldId = field?.field_id || '';
  const explicitRule = fakerProfile?.field_generators?.[fieldId] || field?.generator || '';
  const explicitType = field?.value_type || '';
  return isCheckboxRule(explicitRule) || isCheckboxRule(explicitType);
}

function isCheckboxRule(value) {
  const normalized = String(value || '').trim().toLowerCase().replaceAll('_', '.').replaceAll('-', '.');
  return normalized === 'bool.checkbox'
    || normalized === 'checkbox'
    || normalized === 'checkbox.bool'
    || normalized === 'boolean'
    || normalized.startsWith('bool.checkbox')
    || normalized.startsWith('checkbox:')
    || normalized.startsWith('boolean:')
    || normalized.startsWith('bool:');
}

function syncSemanticSchemaToAuthoringFields(schema, nextSemanticSchema) {
  const oldLeaves = collectSemanticLeafPaths(schema?.semantic_schema || {});
  const nextLeaves = collectSemanticLeafPaths(nextSemanticSchema || {});
  const nextByKey = new Map(nextLeaves.map((path) => [semanticPathKey(path), path]));
  const oldIndexByKey = new Map(oldLeaves.map((path, index) => [semanticPathKey(path), index]));
  const fields = Array.isArray(schema?.fields) ? schema.fields : [];
  const syncedFields = fields.map((field, index) => {
    const currentPath = fieldSemanticPathParts(field);
    const currentKey = semanticPathKey(currentPath);
    let targetPath = nextByKey.get(currentKey) || null;
    if (!targetPath && oldIndexByKey.has(currentKey)) {
      targetPath = nextLeaves[oldIndexByKey.get(currentKey)] || null;
    }
    if (!targetPath) {
      targetPath = nextLeaves[index] || null;
    }
    if (!targetPath) return null;
    const jsonPath = semanticPathKey(targetPath);
    return {
      ...field,
      label: targetPath[targetPath.length - 1] || field.label,
      semantic_path: targetPath,
      export: {
        ...(field.export || {}),
        json_path: jsonPath,
        csv_column: jsonPath,
      },
    };
  }).filter(Boolean);
  return {
    ...schema,
    semantic_schema: nextSemanticSchema,
    fields: syncedFields,
  };
}

function collectSemanticLeafPaths(value, prefix = []) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const entries = Object.entries(value);
    if (!entries.length) return prefix.length ? [prefix] : [];
    return entries.flatMap(([key, child]) => collectSemanticLeafPaths(child, [...prefix, key]));
  }
  return prefix.length ? [prefix] : [];
}

function fieldSemanticPathParts(field) {
  if (Array.isArray(field?.semantic_path)) {
    return field.semantic_path.map((part) => String(part).trim()).filter(Boolean);
  }
  const raw = field?.semantic_path || field?.key_path || field?.json_path || field?.export?.json_path || field?.key || field?.label || field?.field_id || '';
  return String(raw).split('/').map((part) => part.trim()).filter(Boolean);
}

function semanticPathKey(path) {
  return (Array.isArray(path) ? path : []).map((part) => String(part).trim()).filter(Boolean).join('/');
}

function hasRenderableAuthoringBbox(field) {
  return Array.isArray(field?.bbox) && field.bbox.length === 4 && field.bbox.every((value) => Number.isFinite(Number(value)));
}

function authoringConflictBoxes(conflict) {
  const normalize = (value) => (Array.isArray(value) && value.length === 4 ? value.map((item) => Number(item) || 0) : null);
  const review = normalize(conflict?.review?.bbox);
  const draft = normalize(conflict?.draft?.bbox);
  if (conflict?.type === 'bbox_geometry_changed' && review && draft) {
    return [
      { role: 'review', label: '리뷰', bbox: review },
      { role: 'draft', label: 'Agent', bbox: draft },
    ];
  }
  const bbox = normalize(conflict?.canvasBbox) || review || draft || normalize(conflict?.baseline?.bbox);
  return bbox ? [{ role: 'primary', label: '', bbox }] : [];
}

function AuthoringCanvas({
  imagePath,
  version = 0,
  image,
  fields,
  selectedFieldIds,
  setSelectedFieldIds,
  viewportMode,
  qrBox = null,
  qrEditMode = false,
  onQrBoxChange = null,
  conflicts = [],
  conflictResolutions = {},
  focusedConflictId = '',
  onConflictSelect = null,
}) {
  const width = image?.width || 1200;
  const height = image?.height || 1600;
  const svgRef = useRef(null);
  const [dragBox, setDragBox] = useState(null);
  const selectedSet = useMemo(() => new Set(selectedFieldIds), [selectedFieldIds]);

  function eventPoint(event) {
    const rect = svgRef.current.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(width, ((event.clientX - rect.left) / Math.max(1, rect.width)) * width)),
      y: Math.max(0, Math.min(height, ((event.clientY - rect.top) / Math.max(1, rect.height)) * height)),
    };
  }
  function normalizedDragBox(start, end) {
    const x = Math.min(start.x, end.x);
    const y = Math.min(start.y, end.y);
    const right = Math.max(start.x, end.x);
    const bottom = Math.max(start.y, end.y);
    return { x, y, width: right - x, height: bottom - y, right, bottom };
  }
  function normalizedSquareDragBox(start, end) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const side = Math.min(Math.max(Math.abs(dx), Math.abs(dy)), width, height);
    const rawX = dx < 0 ? start.x - side : start.x;
    const rawY = dy < 0 ? start.y - side : start.y;
    const x = Math.max(0, Math.min(rawX, width - side));
    const y = Math.max(0, Math.min(rawY, height - side));
    return { x, y, width: side, height: side, right: x + side, bottom: y + side };
  }
  function intersects(left, right) {
    return left.x <= right.right && left.right >= right.x && left.y <= right.bottom && left.bottom >= right.y;
  }
  function toggleField(fieldId) {
    const next = new Set(selectedFieldIds);
    if (next.has(fieldId)) next.delete(fieldId);
    else next.add(fieldId);
    setSelectedFieldIds([...next]);
  }
  function handlePointerDown(event) {
    if (!svgRef.current) return;
    if (qrEditMode) {
      const start = eventPoint(event);
      setDragBox({ start, current: start, kind: 'qr' });
      event.currentTarget.setPointerCapture?.(event.pointerId);
      return;
    }
    const conflictNode = event.target.closest?.('[data-authoring-conflict-id]');
    if (conflictNode) {
      const conflictId = conflictNode.getAttribute('data-authoring-conflict-id');
      onConflictSelect?.(conflictId);
      return;
    }
    const fieldNode = event.target.closest?.('[data-authoring-field-id]');
    if (fieldNode) {
      const fieldId = fieldNode.getAttribute('data-authoring-field-id');
      if (event.shiftKey || event.metaKey || event.ctrlKey) toggleField(fieldId);
      else setSelectedFieldIds([fieldId]);
      return;
    }
    const start = eventPoint(event);
    setDragBox({ start, current: start });
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }
  function handlePointerMove(event) {
    if (!dragBox) return;
    setDragBox((current) => current ? { ...current, current: eventPoint(event) } : current);
  }
  function handlePointerUp(event) {
    if (!dragBox) return;
    const box = dragBox.kind === 'qr'
      ? normalizedSquareDragBox(dragBox.start, eventPoint(event))
      : normalizedDragBox(dragBox.start, eventPoint(event));
    if (dragBox.kind === 'qr') {
      if (box.width >= 12 && box.height >= 12 && onQrBoxChange) onQrBoxChange(box);
      setDragBox(null);
      event.currentTarget.releasePointerCapture?.(event.pointerId);
      return;
    }
    const hits = box.width < 3 && box.height < 3
      ? []
      : fields.filter((field) => intersects(bboxOf(field), box)).map((field) => field.field_id);
    if (event.shiftKey || event.metaKey || event.ctrlKey) {
      setSelectedFieldIds([...new Set([...selectedFieldIds, ...hits])]);
    } else {
      setSelectedFieldIds(hits);
    }
    setDragBox(null);
    event.currentTarget.releasePointerCapture?.(event.pointerId);
  }
  const activeDragBox = dragBox
    ? (dragBox.kind === 'qr' ? normalizedSquareDragBox(dragBox.start, dragBox.current) : normalizedDragBox(dragBox.start, dragBox.current))
    : null;
  return (
    <DocumentViewport width={width} height={height} mode={viewportMode}>
      <div className="svg-wrap authoring-canvas">
        <svg
          ref={svgRef}
          className="document-svg"
          viewBox={`0 0 ${width} ${height}`}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={() => setDragBox(null)}
        >
          <image href={imageUrl(imagePath, version)} x="0" y="0" width={width} height={height} preserveAspectRatio="none" />
          {fields.map((field) => {
            const box = bboxOf(field);
            const active = selectedSet.has(field.field_id);
            return (
              <g key={field.field_id} data-authoring-field-id={field.field_id} className="authoring-bbox-group">
                <rect
                  x={box.x}
                  y={box.y}
                  width={box.width}
                  height={box.height}
                  fill={active ? 'rgba(30,102,245,0.13)' : 'rgba(0,200,83,0.08)'}
                  stroke={active ? '#1e66f5' : '#00a846'}
                  strokeWidth={active ? 2.5 : 1.5}
                  vectorEffect="non-scaling-stroke"
                  className="authoring-bbox"
                />
                <title>{`${field.field_id} · ${field.label || ''} · ${field.source_text || ''}`}</title>
              </g>
            );
          })}
          {conflicts.flatMap((conflict) => authoringConflictBoxes(conflict).map((entry) => {
            const [x, y, boxWidth, boxHeight] = entry.bbox;
            const resolved = Boolean(conflictResolutions[conflict.id]);
            const focused = focusedConflictId === conflict.id;
            return (
              <g
                key={`${conflict.id}-${entry.role}`}
                data-authoring-conflict-id={conflict.id}
                className="authoring-conflict-bbox-group"
              >
                <rect
                  x={x}
                  y={y}
                  width={Math.max(1, boxWidth)}
                  height={Math.max(1, boxHeight)}
                  vectorEffect="non-scaling-stroke"
                  className={`authoring-conflict-bbox conflict-${conflict.type} ${entry.role} ${resolved ? 'resolved' : 'unresolved'} ${focused ? 'focused' : ''}`}
                />
                {entry.label && (
                  <text
                    x={x + 3}
                    y={Math.max(12, y - 4)}
                    className={`authoring-conflict-label ${entry.role}`}
                    vectorEffect="non-scaling-stroke"
                    pointerEvents="none"
                  >
                    {entry.label}
                  </text>
                )}
                <title>{`${conflict.message} · ${conflict.bboxLabelId}${resolved ? ` · 선택: ${conflictResolutions[conflict.id]}` : ' · 미해결'}`}</title>
              </g>
            );
          }))}
          {qrBox && Array.isArray(qrBox) && qrBox.length === 4 && (
            <g className="authoring-qr-bbox-group">
              <rect
                x={Number(qrBox[0]) || 0}
                y={Number(qrBox[1]) || 0}
                width={Number(qrBox[2]) || 1}
                height={Number(qrBox[3]) || 1}
                fill="rgba(244, 63, 94, 0.10)"
                stroke="#e11d48"
                strokeWidth={2}
                strokeDasharray="8 4"
                vectorEffect="non-scaling-stroke"
                pointerEvents="none"
              />
              <text x={(Number(qrBox[0]) || 0) + 4} y={(Number(qrBox[1]) || 0) + 14} fill="#e11d48" fontSize="14" fontWeight="800" pointerEvents="none">QR</text>
            </g>
          )}
          {activeDragBox && (
            <rect
              x={activeDragBox.x}
              y={activeDragBox.y}
              width={activeDragBox.width}
              height={activeDragBox.height}
              className="authoring-selection-box"
              vectorEffect="non-scaling-stroke"
            />
          )}
        </svg>
      </div>
    </DocumentViewport>
  );
}

function AuthoringEditor({
  fields,
  selectedField,
  selectedFields,
  selectedFieldIds,
  setSelectedFieldIds,
  fakerRuleExamples,
  fakerProfile,
  selectedStyle,
  fontOptions,
  isHandwritingDocument,
  privacy,
  privacyPolicy,
  onFieldChange,
  onPrivacyChange,
  onRenderModeChange,
  onStyleChange,
  onRenderPolicyChange,
  onRefreshFonts,
  onGotoReview,
}) {
  const renderPolicy = selectedField?.render_policy || {};
  const activeIds = selectedFieldIds.length ? selectedFieldIds : (selectedField ? [selectedField.field_id] : []);
  const isMulti = activeIds.length > 1;
  const currentRule = selectedField ? (fakerProfile?.field_generators?.[selectedField.field_id] || selectedField.generator || selectedField.value_type || 'free_text.short') : '';
  const selectedFontId = fontIdForStyle(selectedStyle, fontOptions);
  const selectedExport = selectedField?.export || {};
  const selectedPrivacyKey = fieldSemanticPathParts(selectedField).at(-1) || '';
  const privacyMode = (privacy?.include_keys || []).includes(selectedPrivacyKey)
    ? 'include'
    : (privacy?.exclude_keys || []).includes(selectedPrivacyKey) ? 'exclude' : 'inherit';
  const privacyDefaultIncluded = (privacyPolicy?.defaultKeys || []).includes(selectedPrivacyKey);
  const privacyResolvedIncluded = privacyMode === 'include' || (privacyMode === 'inherit' && privacyDefaultIncluded);
  const selectedCheckboxFields = selectedFields.filter((field) => isAuthoringCheckboxField(field, fakerProfile));
  const hasCheckboxSelection = selectedCheckboxFields.length > 0;
  const checkboxStyles = [...new Set(selectedCheckboxFields.map((field) => field.render_policy?.checkbox_style || 'v_mark'))];
  const checkboxStyleValue = checkboxStyles.length === 1 ? checkboxStyles[0] : 'mixed';
  const renderModes = [...new Set(selectedFields.map((field) => field.render_mode || 'printed'))];
  const renderModeValue = renderModes.length === 1 ? renderModes[0] : 'mixed';
  function updateStyle(patch, options) {
    if (!activeIds.length) return;
    onStyleChange(activeIds, patch, options);
  }
  function updateRenderPolicy(patch) {
    if (!activeIds.length) return;
    onRenderPolicyChange(activeIds, patch);
  }
  return (
    <div className="authoring-editor">
      <div className="authoring-head">
        <b>Authoring 편집</b>
        <span>{fields.length}개 필드 · 선택 {activeIds.length || 0}개</span>
      </div>
      <p className="muted">{isMulti ? '여러 bbox 선택 중에는 key/schema/faker를 잠그고 style만 일괄 수정합니다.' : '이 단계는 bbox 좌표를 고정한 뒤 schema/faker/style/font만 조정합니다. bbox 위치·크기 수정은 BBox 리뷰 단계에서 수행합니다.'} 방향키로 X Shift/Baseline을 1px씩, Shift+방향키로 10px씩 보정할 수 있습니다.</p>
      <div className="authoring-field-list">
        {fields.map((field, index) => (
          <button
            type="button"
            key={field.field_id}
            className={activeIds.includes(field.field_id) ? 'authoring-field active' : 'authoring-field'}
            onClick={(event) => {
              if (event.shiftKey || event.metaKey || event.ctrlKey) {
                const next = new Set(activeIds);
                if (next.has(field.field_id)) next.delete(field.field_id);
                else next.add(field.field_id);
                setSelectedFieldIds([...next]);
              } else {
                setSelectedFieldIds([field.field_id]);
              }
            }}
          >
            <b>{field.label || `필드 ${index + 1}`}</b>
            <small>{field.source_text || field.field_id}</small>
          </button>
        ))}
      </div>
      {selectedField ? (
        <div className="authoring-form">
          {!isMulti && (
            <>
              <label>표시명
                <input value={selectedField.label || ''} placeholder="예: 성명, 주민등록번호, 주소" onChange={(event) => onFieldChange(selectedField.field_id, { label: event.target.value })} />
              </label>
              <label>Export Key / CSV Column
                <input
                  value={selectedExport.json_path || ''}
                  placeholder="예: customer_name, address"
                  onChange={(event) => onFieldChange(selectedField.field_id, { export: { json_path: event.target.value, csv_column: event.target.value } })}
                />
              </label>
              <label>Faker 규칙 문자열
                <input list="faker-rule-examples" value={currentRule} placeholder="예: person.name_ko, choice:남|여, literal:서울" onChange={(event) => onFieldChange(selectedField.field_id, { faker_rule: event.target.value })} />
                <datalist id="faker-rule-examples">
                  {fakerRuleExamples.map((rule) => <option key={rule} value={rule} />)}
                </datalist>
              </label>
              <label>라이브러리 샘플 PII key
                <select value={privacyMode} disabled={!selectedPrivacyKey} onChange={(event) => onPrivacyChange(selectedPrivacyKey, event.target.value)}>
                  <option value="inherit">공통 정책 사용</option>
                  <option value="include">문서 예외: 강제 포함</option>
                  <option value="exclude">문서 예외: explicit 목록 제외(자동판정 유지)</option>
                </select>
                <small>{selectedPrivacyKey || 'semantic leaf 없음'} · 최종 explicit PII: {privacyResolvedIncluded ? '포함' : '미포함'}{privacyDefaultIncluded ? ' · 공통 정책 대상' : ''}</small>
              </label>
              <div className="rule-help">
                <span>preset: person.name_ko</span>
                <span>date.year/month/day</span>
                <span>choice:남|여</span>
                <span>literal:고정값</span>
                <span>bool.checkbox</span>
                <span>template:{'{{company.name_ko}}'}</span>
                <span>pattern:###-####</span>
              </div>
            </>
          )}
          <div className="authoring-edit-section render-policy-section">
            <div className="section-mini-title"><b>Render Policy</b><span>정렬/초과/체크박스 표현</span></div>
            {isHandwritingDocument && (
              <label>수기 문건 처리 방식
                <select value={renderModeValue} onChange={(event) => onRenderModeChange(activeIds, event.target.value)}>
                  {renderModeValue === 'mixed' && <option value="mixed" disabled>혼합됨</option>}
                  <option value="handwriting">필기체: 답안지에만 출력</option>
                  <option value="printed">인쇄체: 템플릿에 렌더링</option>
                </select>
                <small>이 설정은 authoring field에만 저장되며, review 단계 render_mode는 더 이상 참조하지 않습니다.</small>
              </label>
            )}
            <div className="triple-grid">
            <label>가로
              <select value={renderPolicy.align || 'left'} onChange={(event) => updateRenderPolicy({ align: event.target.value })}>
                <option value="left">left</option>
                <option value="center">center</option>
                <option value="right">right</option>
              </select>
            </label>
            <label>세로
              <select value={renderPolicy.valign || 'middle'} onChange={(event) => updateRenderPolicy({ valign: event.target.value })}>
                <option value="top">top</option>
                <option value="middle">middle</option>
                <option value="bottom">bottom</option>
              </select>
            </label>
            <label>초과
              <select value={renderPolicy.overflow || 'shrink'} onChange={(event) => updateRenderPolicy({ overflow: event.target.value })}>
                <option value="shrink">shrink</option>
                <option value="wrap">wrap</option>
                <option value="clip">clip</option>
                <option value="allow">allow</option>
              </select>
            </label>
          </div>
          {hasCheckboxSelection && (
            <label>체크박스 표현 방식
              <select value={checkboxStyleValue} onChange={(event) => updateRenderPolicy({ checkbox_style: event.target.value })}>
                {checkboxStyleValue === 'mixed' && <option value="mixed" disabled>혼합됨</option>}
                <option value="v_mark">V 표시만 찍기</option>
                <option value="check_mark">✓ 체크 표시 직접 그리기</option>
                <option value="heavy_check_mark">✔ 체크 표시 직접 그리기</option>
                <option value="symbol_box">☑/☐ 박스를 직접 그리기</option>
                <option value="filled_box">채운 사각형</option>
                <option value="dot">점/원 표시</option>
                <option value="ellipse_mark">문구 둘레 타원</option>
              </select>
              {isMulti && <small>선택된 체크박스 bbox {selectedCheckboxFields.length}개에만 일괄 적용됩니다.</small>}
            </label>
          )}
          </div>
          <div className="authoring-edit-section text-style-section">
            <div className="section-mini-title"><b>Text Style</b><span>폰트/크기/색상/위치 보정</span></div>
            <div className="style-subhead">
              <b>텍스트 스타일</b>
              <button type="button" onClick={onRefreshFonts}>폰트 새로고침</button>
            </div>
          <label>폰트
            <select
              value={selectedFontId}
              onChange={(event) => {
                const face = fontOptions.find((font) => font.id === event.target.value);
                if (!face) return;
                updateStyle({
                  font_path: face.path || face.absolutePath,
                  font_index: Number(face.index || 0),
                  font_family: face.family || '',
                  font_weight: face.weight || 'normal',
                  font_style: face.fontStyle || 'normal',
                });
              }}
            >
              <option value="">기본/자동 폰트</option>
              {fontOptions.map((font) => <option key={font.id} value={font.id}>{font.label || `${font.family} ${font.style}`}</option>)}
            </select>
          </label>
          <div className="font-preview-card" style={{ fontFamily: selectedStyle?.font_family || undefined, color: rgbToHex(selectedStyle?.fill), fontSize: `${Math.min(22, Math.max(12, Number(selectedStyle?.font_size || 16)))}px`, fontWeight: selectedStyle?.font_weight || 'normal', fontStyle: selectedStyle?.font_style || 'normal', opacity: selectedStyle?.opacity ?? 1 }}>
            <span>가나다 ABC 123</span>
            <small>{selectedStyle?.font_family || '기본/자동 폰트'} · {selectedStyle?.font_size || 28}px</small>
          </div>
          <div className="triple-grid">
            <label>크기
              <input type="number" min="4" max="240" value={selectedStyle?.font_size || 28} onChange={(event) => updateStyle({ font_size: Number(event.target.value) || 28 })} />
            </label>
            <label>굵기
              <select value={selectedStyle?.font_weight || 'normal'} onChange={(event) => updateStyle({ font_weight: event.target.value })}>
                <option value="normal">normal</option>
                <option value="bold">bold</option>
                <option value="light">light</option>
                <option value="black">black</option>
              </select>
            </label>
            <label>기울임
              <select value={selectedStyle?.font_style || 'normal'} onChange={(event) => updateStyle({ font_style: event.target.value })}>
                <option value="normal">normal</option>
                <option value="italic">italic</option>
              </select>
            </label>
          </div>
          <div className="quad-grid">
            <label>색상
              <input type="color" value={rgbToHex(selectedStyle?.fill)} onChange={(event) => updateStyle({ fill: hexToRgb(event.target.value) })} />
            </label>
            <label>불투명도
              <input type="number" min="0" max="1" step="0.05" value={selectedStyle?.opacity ?? 1} onChange={(event) => updateStyle({ opacity: Number(event.target.value) })} />
            </label>
            <label>줄간격
              <input type="number" min="0.1" max="4" step="0.05" value={selectedStyle?.line_spacing ?? 1} onChange={(event) => updateStyle({ line_spacing: Number(event.target.value) })} />
            </label>
            <label>자간
              <input type="number" min="-20" max="80" step="0.5" value={selectedStyle?.letter_spacing ?? 0} onChange={(event) => updateStyle({ letter_spacing: Number(event.target.value) })} />
            </label>
          </div>
          <div className="quad-grid">
            <label>Baseline
              <input type="number" min="-120" max="120" step="1" value={selectedStyle?.baseline_shift ?? 0} onChange={(event) => updateStyle({ baseline_shift: Number(event.target.value) || 0 })} />
            </label>
            <label>X Shift
              <input type="number" min="-240" max="240" step="1" value={selectedStyle?.x_shift ?? 0} onChange={(event) => updateStyle({ x_shift: Number(event.target.value) || 0 })} />
            </label>
            <label>Style Class
              <input value={selectedField.style_class || 'body_default'} readOnly />
            </label>
            <label>공유 스타일
              <button type="button" onClick={() => updateStyle({}, { shared: true })}>현재 클래스 유지</button>
            </label>
          </div>
          </div>
          <div className="authoring-edit-section field-meta-section">
            <div className="section-mini-title"><b>Field Meta</b><span>BBox 좌표/필수/메모</span></div>
          {!isMulti ? (
            <>
              <div className="bbox-readonly-grid">
                {(selectedField.bbox || [0, 0, 0, 0]).map((value, index) => (
                  <label key={index}>{['x', 'y', 'w', 'h'][index]}
                    <input value={value} readOnly />
                  </label>
                ))}
              </div>
              <div className="bbox-stage-hint">
                <span>BBox 좌표는 읽기 전용입니다.</span>
                <button type="button" onClick={onGotoReview}>BBox 리뷰로 이동</button>
              </div>
              <label className="checkbox-line">
                <input type="checkbox" checked={Boolean(selectedField.required)} onChange={(event) => onFieldChange(selectedField.field_id, { required: event.target.checked })} />
                필수 필드
              </label>
              <label>메모
                <textarea rows="2" value={selectedField.notes || ''} onChange={(event) => onFieldChange(selectedField.field_id, { notes: event.target.value })} />
              </label>
              <p className="mini-path">내부 ID: {selectedField.field_id} · 원본 OCR: {selectedField.source_text || '-'}</p>
            </>
          ) : (
            <div className="bbox-stage-hint">
              <span>{selectedFields.length}개 bbox에 style/render policy만 일괄 적용됩니다.</span>
              <button type="button" onClick={onGotoReview}>BBox 리뷰로 이동</button>
            </div>
          )}
          </div>
        </div>
      ) : <p className="muted">편집할 필드가 없습니다.</p>}
    </div>
  );
}

function HandwritingScanPopover({ files, warnings, setFiles, onClose, onSubmit, busy }) {
  function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    setFiles(event.dataTransfer?.files || []);
  }
  return (
    <div className="upload-backdrop recognition-backdrop" role="dialog" aria-modal="true" onDragOver={(event) => event.preventDefault()} onDrop={handleDrop}>
      <div className="upload-popover recognition-popover">
        <div className="upload-header">
          <div>
            <p className="eyebrow dark">Handwriting Scan Intake</p>
            <h2>scan 문서 처리하기</h2>
            <p className="muted">여러 스캔본이 합쳐진 PDF 또는 이미지들을 여기에 드래그 앤 드롭하세요. 페이지 분할 후 현재 준비된 모든 QR bbox 후보를 crop/decode해 GT와 매칭합니다.</p>
          </div>
          <button onClick={onClose} disabled={busy}>닫기</button>
        </div>
        <div className="scan-drop-zone">
          <b>PDF / PNG / JPG / TIFF / BMP / WEBP 드롭</b>
          <small>기존 seed sample 드래그&드롭과 별도 popover 내부에서만 처리됩니다.</small>
          <input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp" onChange={(event) => setFiles(event.target.files || [])} />
        </div>
        <div className="upload-files">
          {files.map((file) => <span key={`${file.name}-${file.size}`}>{file.name} · {(file.size / 1024 / 1024).toFixed(2)}MB</span>)}
          {warnings.map((warning) => <span className="warn" key={warning}>{warning}</span>)}
          {!files.length && <span>아직 선택된 스캔 파일이 없습니다.</span>}
        </div>
        <div className="upload-footer">
          <p className="muted">decode 엔진: WeChat QR 사용 가능 시 우선, 기존 DataFactory grid marker는 호환 fallback.</p>
          <button className="primary" onClick={onSubmit} disabled={busy || !files.length}>
            {busy ? '처리 중...' : '페이지 분할 / QR decode / GT 매칭'}
          </button>
        </div>
      </div>
    </div>
  );
}

function UploadPopover({ files, warnings, documents, allDocuments, selectedDocId, setSelectedDocId, search, setSearch, onClose, onSubmit, busy }) {
  const selectedDoc = allDocuments.find((doc) => doc.docId === selectedDocId) || null;
  return (
    <div className="upload-backdrop" role="dialog" aria-modal="true">
      <div className="upload-popover">
        <div className="upload-header">
          <div>
            <p className="eyebrow dark">Drag & Drop Seed Intake</p>
            <h2>Seed sample 바로 적재</h2>
            <p className="muted">문서 제목을 검색해 선택하면 seed_samples와 내부 작업 폴더에 동시에 적재합니다.</p>
          </div>
          <button onClick={onClose} disabled={busy}>닫기</button>
        </div>

        <div className="upload-files">
          {files.map((file) => <span key={`${file.name}-${file.size}`}>{file.name} · {(file.size / 1024 / 1024).toFixed(2)}MB</span>)}
          {warnings.map((warning) => <span className="warn" key={warning}>{warning}</span>)}
        </div>

        <label>문서 제목/ID 검색
          <input autoFocus placeholder="예: 주민등록등본, 가족관계증명서, FIN-01" value={search} onChange={(event) => setSearch(event.target.value)} />
        </label>

        <div className="upload-doc-list">
          {documents.map((doc) => (
            <button key={doc.docId} className={doc.docId === selectedDocId ? 'upload-doc active' : 'upload-doc'} onClick={() => setSelectedDocId(doc.docId)}>
              <b>{doc.title}</b>
              <small>{doc.docId}{doc.poDomains?.length ? ` · ${doc.poDomains.join(' · ')}` : ''}</small>
            </button>
          ))}
          {documents.length === 0 && <p className="muted">검색 결과가 없습니다.</p>}
        </div>

        <div className="upload-footer">
          <p className="muted">{selectedDoc ? `저장 위치: seed_samples/${selectedDoc.title}/` : '대상 문서를 선택하세요.'}</p>
          <button className="primary" onClick={onSubmit} disabled={busy || !selectedDocId}>
            {busy ? '적재 중...' : '적재하고 바로 작업'}
          </button>
        </div>
      </div>
    </div>
  );
}

function RecognitionPopover({ data, setChoice, onClose, onApply, onSaveWithoutRecognition, busy }) {
  const candidates = data.candidates || [];
  const saveMode = data.mode === 'save';
  function choiceText(candidate) {
    const choice = data.choices?.[candidate.id] || {};
    const mode = choice.mode || recommendedRecognitionChoice(candidate);
    if (mode === 'crop') return candidate.text || '';
    if (mode === 'manual') return choice.manual || '';
    return candidate.oldText || '';
  }
  return (
    <div className="upload-backdrop recognition-backdrop" role="dialog" aria-modal="true">
      <div className="upload-popover recognition-popover">
        <div className="upload-header">
          <div>
            <p className="eyebrow dark">BBox Crop OCR</p>
            <h2>{saveMode ? '저장 전 텍스트 재확인' : '수정 BBox 텍스트 재인식'}</h2>
            <p className="muted">기존 OCR과 수정 bbox crop OCR을 비교해 실제 label.text로 쓸 값을 선택하세요. 둘 다 틀리면 직접 입력을 사용합니다.</p>
          </div>
          <button onClick={onClose} disabled={busy}>닫기</button>
        </div>

        <div className="recognition-summary">
          <span>대상 {data.summary?.count || candidates.length}개</span>
          <span>인식 {data.summary?.recognized || 0}개</span>
          <span>{data.summary?.preset || 'precise'}</span>
          {data.summary?.elapsed_seconds !== undefined && <span>{Number(data.summary.elapsed_seconds).toFixed(1)}초</span>}
        </div>

        <div className="recognition-list">
          {candidates.map((candidate) => {
            const choice = data.choices?.[candidate.id] || {};
            const mode = choice.mode || recommendedRecognitionChoice(candidate);
            return (
              <div className="recognition-card" key={candidate.id}>
                <div className="recognition-card-head">
                  <div>
                    <b>{candidate.id}</b>
                    <small>crop {candidate.image?.width || '-'}×{candidate.image?.height || '-'} · confidence {confidenceLabel(candidate.confidence)}</small>
                  </div>
                  {candidate.cropPath && <a href={fileUrl(candidate.cropPath)} target="_blank" rel="noreferrer">crop 열기</a>}
                </div>
                {candidate.cropPath && <img className="recognition-crop" src={fileUrl(candidate.cropPath)} alt={`${candidate.id} crop`} />}
                <div className="recognition-choice-grid">
                  <button className={mode === 'old' ? 'active' : ''} onClick={() => setChoice(candidate.id, { mode: 'old' })}>
                    <span>기존 OCR</span>
                    <b>{candidate.oldText || '(비어 있음)'}</b>
                  </button>
                  <button className={mode === 'crop' ? 'active' : ''} onClick={() => setChoice(candidate.id, { mode: 'crop' })}>
                    <span>Crop OCR</span>
                    <b>{candidate.text || '(인식 실패)'}</b>
                  </button>
                </div>
                <label className="manual-label">직접 입력 fallback
                  <input
                    value={choice.manual ?? candidate.oldText ?? candidate.text ?? ''}
                    placeholder="둘 다 틀린 경우 직접 레이블 입력"
                    onChange={(event) => setChoice(candidate.id, { mode: 'manual', manual: event.target.value })}
                    onFocus={() => setChoice(candidate.id, { mode: 'manual' })}
                  />
                </label>
                <p className="recognition-preview">적용값: <b>{choiceText(candidate) || '(빈 텍스트)'}</b></p>
              </div>
            );
          })}
        </div>

        <div className="recognition-footer">
          <button onClick={() => onApply({ saveAfter: saveMode })} disabled={busy}>
            {saveMode ? '추천/선택 적용 후 저장' : '추천/선택 적용'}
          </button>
          <button onClick={() => onApply({ saveAfter: saveMode, forceMode: 'crop' })} disabled={busy}>
            {saveMode ? 'Crop 일괄 채택 후 저장' : 'Crop 결과 일괄 채택'}
          </button>
          {saveMode && <button className="danger" onClick={onSaveWithoutRecognition} disabled={busy}>재인식 없이 그대로 저장</button>}
        </div>
      </div>
    </div>
  );
}

const AUTHORING_CONFLICT_TYPE_LABELS = {
  deleted_in_review_present_in_draft: '리뷰에서 삭제됨',
  agent_added_bbox: 'Agent가 추가함',
  present_in_review_missing_in_draft: 'Agent draft에서 누락',
  added_in_review_missing_in_draft: '리뷰에서 새로 추가됨',
  bbox_geometry_changed: '좌표 변경',
};

function AuthoringAgentConflictPopover({
  data,
  resolutions,
  focusedId,
  busy,
  onFocus,
  onResolve,
  onUseRecommended,
  onCancel,
  onApply,
}) {
  const conflicts = data.conflicts || [];
  const resolvedCount = conflicts.filter((conflict) => Boolean(resolutions[conflict.id])).length;
  const unresolvedCount = conflicts.length - resolvedCount;
  return (
    <aside className="authoring-conflict-popover" role="dialog" aria-modal="false" aria-label="Agent BBox 변경 충돌 확인">
      <div className="authoring-conflict-head">
        <div>
          <p className="eyebrow dark">Authoring 적용 전 확인</p>
          <h2>BBox 변경 충돌 {conflicts.length}건</h2>
          <p className="muted">카드를 누르면 캔버스의 pulse 영역을 확인할 수 있습니다. 다른 문서와 작업은 차단하지 않습니다.</p>
        </div>
        <button onClick={onCancel} disabled={busy} aria-label="충돌 확인 패널 닫기">닫기</button>
      </div>
      <div className="authoring-conflict-summary">
        <span className={unresolvedCount ? 'warn' : 'complete'}>미해결 {unresolvedCount}</span>
        <span>선택 완료 {resolvedCount}</span>
        <button onClick={onUseRecommended} disabled={busy || !unresolvedCount}>추천안 일괄 선택</button>
      </div>
      <div className="authoring-conflict-list">
        {conflicts.map((conflict, index) => {
          const selectedAction = resolutions[conflict.id] || '';
          const reviewBbox = conflict.review?.bbox?.join(', ');
          const draftBbox = conflict.draft?.bbox?.join(', ');
          return (
            <section
              key={conflict.id}
              className={`authoring-conflict-card ${focusedId === conflict.id ? 'focused' : ''} ${selectedAction ? 'resolved' : 'unresolved'}`}
              onClick={() => onFocus(conflict)}
            >
              <div className="authoring-conflict-card-head">
                <div>
                  <span className="authoring-conflict-index">{index + 1}</span>
                  <b>{conflict.label || conflict.bboxLabelId}</b>
                </div>
                <span>{AUTHORING_CONFLICT_TYPE_LABELS[conflict.type] || conflict.type}</span>
              </div>
              <p>{conflict.message}</p>
              <small>
                bbox {conflict.bboxLabelId}
                {conflict.fieldId ? ` · field ${conflict.fieldId}` : ''}
                {conflict.semanticPath ? ` · ${conflict.semanticPath}` : ''}
              </small>
              {(reviewBbox || draftBbox) && (
                <div className="authoring-conflict-coordinates">
                  {reviewBbox && <code>리뷰 [{reviewBbox}]</code>}
                  {draftBbox && <code>Agent [{draftBbox}]</code>}
                </div>
              )}
              <div className="authoring-conflict-actions" onClick={(event) => event.stopPropagation()}>
                {(conflict.actions || []).map((action) => (
                  <button
                    key={action.id}
                    className={selectedAction === action.id ? 'active' : ''}
                    onClick={() => onResolve(conflict.id, action.id)}
                    disabled={busy}
                  >
                    {action.label}
                    {action.id === conflict.recommendedAction && <small>추천</small>}
                  </button>
                ))}
              </div>
            </section>
          );
        })}
      </div>
      <div className="authoring-conflict-footer">
        <p>{unresolvedCount ? `${unresolvedCount}건의 처리 방식을 선택해야 적용할 수 있습니다.` : '모든 충돌의 처리 방식이 선택되었습니다.'}</p>
        <div>
          <button onClick={onCancel} disabled={busy}>취소</button>
          <button className="primary" onClick={onApply} disabled={busy || unresolvedCount > 0}>
            {busy ? '검증 후 적용 중...' : `선택대로 적용 (${resolvedCount})`}
          </button>
        </div>
      </div>
    </aside>
  );
}

function ReviewPrunePopover({ data, busy, onCancel, onConfirm }) {
  const fields = data.fields || [];
  return (
    <div className="upload-backdrop recognition-backdrop" role="dialog" aria-modal="true">
      <div className="upload-popover review-prune-popover">
        <div className="upload-header">
          <div>
            <p className="eyebrow dark">Authoring 정합성 경고</p>
            <h2>사용하지 않거나 삭제된 BBox에 연결된 합성 정보가 있습니다</h2>
            <p className="muted">미사용/기존 무시/삭제 상태로 저장하면 아래 bbox에 연결된 schema/faker/style 정보가 함께 삭제됩니다. 계속 진행할까요?</p>
          </div>
          <button onClick={onCancel} disabled={busy}>아니오</button>
        </div>
        <div className="review-prune-list">
          {fields.map((field) => (
            <div className="review-prune-item" key={`${field.bbox_label_id}-${field.field_id}`}>
              <b>{field.label || field.field_id}</b>
              <small>{field.field_id} · bbox {field.bbox_label_id} · {field.bbox_status === 'deleted' ? '삭제됨' : (STATUS_LABELS[field.bbox_status] || field.bbox_status)}</small>
            </div>
          ))}
        </div>
        <div className="recognition-footer">
          <button onClick={onCancel} disabled={busy}>취소하고 돌아가기</button>
          <button className="danger" onClick={onConfirm} disabled={busy}>
            예, 연결된 Authoring 정보를 삭제하고 저장
          </button>
        </div>
      </div>
    </div>
  );
}

function AssessmentPopover({
  popover,
  rows,
  summary,
  documentTypeOptions,
  feasibilityOptions,
  assessmentExport,
  assessmentEdits,
  busy,
  isBusy,
  assessmentValue,
  setAssessmentEdit,
  onSave,
  onExport,
  onClose,
}) {
  const width = 560;
  const maxX = typeof window === 'undefined' ? popover.x : Math.max(12, window.innerWidth - width - 12);
  const left = Math.min(Math.max(12, popover.x), maxX);
  const top = typeof window === 'undefined' ? popover.y : Math.min(Math.max(12, popover.y), Math.max(12, window.innerHeight - 640));
  return (
    <div className="assessment-context-layer" onMouseDown={onClose} onContextMenu={(event) => event.preventDefault()}>
      <div className="assessment-popover" style={{ left, top, width }} onMouseDown={(event) => event.stopPropagation()}>
        <div className="assessment-popover-head">
          <div>
            <p className="eyebrow dark">First Priority Assessment</p>
            <h2>{popover.title}</h2>
            <p className="muted">문서 속성과 작업 가능 여부를 scope 단위로 판정합니다. 작업 불가는 사유/절충안이 필수입니다.</p>
          </div>
          <button onClick={onClose} disabled={isBusy}>닫기</button>
        </div>

        <div className="assessment-summary">
          <span className="possible">가능 {summary?.byFeasibility?.possible || 0}</span>
          <span className="impossible">불가 {summary?.byFeasibility?.impossible || 0}</span>
          <span className="unknown">미정 {summary?.byFeasibility?.unknown || 0}</span>
        </div>

        <div className="assessment-popover-list">
          {rows.length ? rows.map((row) => {
            const feasibility = assessmentValue(row, 'feasibility') || 'unknown';
            const comment = assessmentValue(row, 'comment') || '';
            const dirty = Boolean(assessmentEdits[row.key]);
            return (
              <div className={`assessment-card ${assessmentTone(feasibility)}`} key={row.key}>
                <div className="assessment-card-head">
                  <b>{row.domain} · {row.title}</b>
                  <span>{row.docId}</span>
                </div>
                <div className="assessment-grid">
                  <label>문서 속성
                    <select value={assessmentValue(row, 'documentType') || 'unknown'} onChange={(event) => setAssessmentEdit(row, { documentType: event.target.value })}>
                      {documentTypeOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
                    </select>
                  </label>
                  <label>작업 가능 여부
                    <select value={feasibility} onChange={(event) => setAssessmentEdit(row, { feasibility: event.target.value })}>
                      {feasibilityOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
                    </select>
                  </label>
                </div>
                <label>코멘트 / 불가 사유 / 절충안
                  <textarea
                    rows="2"
                    value={comment}
                    placeholder={feasibility === 'impossible' ? '작업 불가 사유 또는 가능한 절충안을 반드시 입력' : '선택: 문서 특징, 주의점, 절충안'}
                    onChange={(event) => setAssessmentEdit(row, { comment: event.target.value })}
                  />
                </label>
                {feasibility === 'impossible' && !comment.trim() && <p className="warning-text">작업 불가로 저장하려면 사유/절충안을 입력해야 합니다.</p>}
                <div className="assessment-card-footer">
                  <span>{row.workStatusLabel} · 샘플 {row.sampleCount}개 · BBox {row.hasOcr ? 'Y' : '-'} · 리뷰 {row.hasReview ? 'Y' : '-'}</span>
                  <button className={dirty ? 'primary' : ''} onClick={() => onSave(row)} disabled={isBusy || (feasibility === 'impossible' && !comment.trim())}>
                    {busy === `assessment:${row.key}` ? '저장 중...' : dirty ? '판정 저장 *' : '판정 저장'}
                  </button>
                </div>
              </div>
            );
          }) : <p className="muted">이 문서의 생성 가능성 판정 항목을 불러오지 못했습니다. 새로고침 후 다시 시도하세요.</p>}
        </div>

        <div className="assessment-popover-footer">
          <button className="primary" onClick={onExport} disabled={isBusy || !rows.length}>
            {busy === 'assessmentExport' ? 'XLSX 출력 중...' : '전체 판정표 XLSX 출력'}
          </button>
          {assessmentExport?.path && <a className="result-link compact" href={assessmentExport.url || fileUrl(assessmentExport.path)} target="_blank" rel="noreferrer">최근 판정표 열기</a>}
        </div>
      </div>
    </div>
  );
}

function FinalOutputPanel({ finalOutput, selectedItem }) {
  if (!finalOutput?.locked) return null;
  const hasFinal = Boolean(finalOutput.previewPath || finalOutput.pdfPath || finalOutput.contactSheet);
  const originalCount = selectedItem?.sampleCount || 0;
  return (
    <section className={`panel-block final-output-panel ${finalOutput.kind}`}>
      <h2>최종 산출물 트랙</h2>
      <p className="muted">
        이 문서는 순차 문서합성 워크플로우 대상이 아닙니다. BBox detect/review/inpainting/authoring 대신,
        적재된 클린룸 또는 수집 완료 산출물을 현재 단계의 최종 output으로 사용합니다.
      </p>
      <div className={`final-output-status ${hasFinal ? 'ready' : 'missing'}`}>
        <b>{finalOutput.label}</b>
        <span>{hasFinal ? '사용 가능' : '미적재'}</span>
      </div>
      {finalOutput.kind === 'cleanroom' && (
        <p className="warning-text">실제 샘플 {originalCount}개는 참조/검토용이며, 중앙 캔버스와 최종 output은 클린룸 버전을 우선 표시합니다.</p>
      )}
      {finalOutput.kind === 'collection' && (
        <p className="warning-text">이 유형은 합성 대신 라이선스/개인정보 검토를 마친 실문서 수집본으로 대응합니다.</p>
      )}
      {!hasFinal && (
        <p className="warning-text">작업 불가 문서로 분류되어 합성 파이프라인을 사용할 수 없습니다. 클린룸 샘플 또는 사용 가능한 수집본을 먼저 적재해야 합니다.</p>
      )}
      <div className="final-output-links">
        {finalOutput.previewPath && <a className="result-link" href={fileUrl(finalOutput.previewPath)} target="_blank" rel="noreferrer">미리보기 이미지 열기</a>}
        {finalOutput.pdfPath && <a className="result-link" href={fileUrl(finalOutput.pdfPath)} target="_blank" rel="noreferrer">최종 PDF 열기</a>}
        {finalOutput.contactSheet && finalOutput.contactSheet !== finalOutput.previewPath && <a className="result-link" href={fileUrl(finalOutput.contactSheet)} target="_blank" rel="noreferrer">QA contact sheet 열기</a>}
        {finalOutput.notes && <a className="result-link" href={fileUrl(finalOutput.notes)} target="_blank" rel="noreferrer">검수 노트 열기</a>}
      </div>
      {finalOutput.previewPath && <p className="mini-path">preview: {finalOutput.previewPath}</p>}
      {finalOutput.pdfPath && <p className="mini-path">pdf: {finalOutput.pdfPath}</p>}
    </section>
  );
}

function SeedFolderCard({ folder, documents, manualDocId, setManualDocId, onSelectDoc, onImport, onTrash, busy }) {
  const primaryCandidate = folder.candidates?.[0];
  const effectiveDocId = folder.matchedDocId || manualDocId || primaryCandidate?.docId || '';
  return (
    <div className={`intake-card ${folder.status}`}>
      <div className="intake-card-head">
        <b>{folder.name}</b>
        <span>{folder.fileCount}개</span>
      </div>
      {folder.matchedDocId ? (
        <button className="match-target" onClick={() => onSelectDoc(folder.matchedDocId)}>{folder.matchedTitle} <small>{folder.matchedDocId}</small></button>
      ) : (
        <label>대상 문서<select value={effectiveDocId} onChange={(event) => setManualDocId(event.target.value)}>{documents.map((doc) => <option key={doc.docId} value={doc.docId}>{doc.title} ({doc.docId})</option>)}</select></label>
      )}
      {folder.candidates?.length > 0 && !folder.matchedDocId && <p className="muted">추천: {folder.candidates.slice(0, 2).map((candidate) => `${candidate.title} ${candidate.score}`).join(' · ')}</p>}
      <button className={folder.status === 'importable' ? 'primary' : ''} onClick={onImport} disabled={folder.status === 'alreadyImported' || !effectiveDocId || busy}>{folder.status === 'alreadyImported' ? '이미 적재됨' : folder.status === 'needsReview' ? '매핑 저장 후 적재' : '적재'}</button>
      <button className="danger" onClick={onTrash} disabled={busy}>보관함 이동</button>
    </div>
  );
}

function WorkItemProgress({ item, compact = false }) {
  if (item?.isNonPipeline || COMPLETED_WORK_STATUSES.has(item?.status)) {
    const finalReady = COMPLETED_WORK_STATUSES.has(item.status);
    const label = item.status === 'cleanroom_sample_ready'
      ? '클린룸 완료'
      : item.status === 'collection_done'
        ? '수집 완료'
        : finalReady
          ? '최종 완료'
          : '합성 제외';
    return <div className={compact ? 'final-progress compact' : 'final-progress'}><span className={finalReady ? 'done' : 'pending'}>{label}</span></div>;
  }
  return (
    <div className={compact ? 'work-progress compact' : 'work-progress'} title={workItemNextAction(item)}>
      {WORKFLOW_STAGES.map(([id, label]) => {
        const done = workItemStageState(item, id);
        return (
          <span key={id} className={done ? 'stage-dot done' : 'stage-dot'} aria-label={`${label} ${done ? '완료' : '대기'}`}>
            <i>{compact ? label.slice(0, 1) : label}</i>
          </span>
        );
      })}
    </div>
  );
}

function StatusPill({ item }) {
  if (!item) return <span className="status-pill missing">문서 미선택</span>;
  return <span className={`status-pill ${item.status}`}>{item.statusLabel}</span>;
}
function Metric({ label, value, tone }) {
  return <div className={`metric ${tone || ''}`}><span>{label}</span><b>{value}</b></div>;
}
function useElementSize(ref) {
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    if (!ref.current) return undefined;
    const update = () => setSize({ width: ref.current?.clientWidth || 0, height: ref.current?.clientHeight || 0 });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [ref]);
  return size;
}

function DocumentViewport({ width, height, mode, children }) {
  const ref = useRef(null);
  const size = useElementSize(ref);
  const safeWidth = Math.max(1, width || 1);
  const safeHeight = Math.max(1, height || 1);
  const resolvedMode = mode === 'auto' ? autoViewportMode(safeWidth, safeHeight) : mode;
  const widthScale = size.width ? size.width / safeWidth : 1;
  const fitScale = Math.min(widthScale, size.height ? size.height / safeHeight : widthScale);
  const scale = resolvedMode === 'actual' ? 1 : resolvedMode === 'width' ? widthScale : Math.min(widthScale, fitScale);
  const displayWidth = Math.max(1, Math.round(safeWidth * scale));
  const displayHeight = Math.max(1, Math.round(safeHeight * scale));
  return (
    <div ref={ref} className="document-viewport">
      <div className="viewport-content" style={{ width: displayWidth, height: displayHeight }}>
        {children}
      </div>
    </div>
  );
}

function SamplePreview({ path, version = 0, viewportMode = 'fit' }) {
  const [imageSize, setImageSize] = useState(null);
  if (!isImagePath(path)) {
    return <div className="empty file-preview"><b>{basename(path)}</b><p>PDF/비이미지 파일은 현재 캔버스 미리보기가 제한됩니다.</p><a href={fileUrl(path, version)} target="_blank" rel="noreferrer">파일 열기</a></div>;
  }
  const width = imageSize?.width || 1200;
  const height = imageSize?.height || 1600;
  return (
    <DocumentViewport width={width} height={height} mode={viewportMode}>
      <div className="sample-preview">
        <img src={imageUrl(path, version)} alt={basename(path)} onLoad={(event) => setImageSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} />
      </div>
    </DocumentViewport>
  );
}

function CleanupCanvas({ imagePath, version = 0, image, mask, selectedId, setSelectedId, tool = 'brush', color = [255, 255, 255], radius = 10, onSampleColor, onAddStroke, viewportMode }) {
  const svgRef = useRef(null);
  const sampleCanvasRef = useRef(null);
  const [drawing, setDrawing] = useState(null);
  const width = image?.width || mask?.image?.width || 1200;
  const height = image?.height || mask?.image?.height || 1600;
  const strokes = mask?.strokes || [];

  useEffect(() => {
    if (!imagePath) return undefined;
    let cancelled = false;
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      if (cancelled) return;
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, width, height);
      sampleCanvasRef.current = canvas;
    };
    img.src = imageUrl(imagePath, version);
    return () => { cancelled = true; };
  }, [imagePath, version, width, height]);

  function clientToImage(event) {
    const rect = svgRef.current.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(width - 1, ((event.clientX - rect.left) / rect.width) * width)),
      y: Math.max(0, Math.min(height - 1, ((event.clientY - rect.top) / rect.height) * height)),
    };
  }
  function pointList(points = []) {
    return points.map((point) => `${point.x},${point.y}`).join(' ');
  }
  function strokeColor(stroke) {
    return rgbToHex(stroke.color || [255, 255, 255]);
  }
  function sampleAt(point) {
    const canvas = sampleCanvasRef.current;
    const ctx = canvas?.getContext?.('2d');
    if (!ctx) return;
    const pixel = ctx.getImageData(Math.round(point.x), Math.round(point.y), 1, 1).data;
    onSampleColor?.([pixel[0], pixel[1], pixel[2]]);
  }
  function handlePointerDown(event) {
    if (event.button !== 0) return;
    event.preventDefault();
    const start = clientToImage(event);
    if (tool === 'eyedropper') {
      sampleAt(start);
      return;
    }
    setSelectedId('');
    setDrawing({ points: [start] });
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function handlePointerMove(event) {
    if (!drawing) return;
    const next = clientToImage(event);
    const last = drawing.points[drawing.points.length - 1];
    if (pointDistance(last, next) < 3) return;
    setDrawing({ points: [...drawing.points, next] });
  }
  function handlePointerUp() {
    if (!drawing) return;
    const points = drawing.points.map((point) => ({ x: Math.round(point.x), y: Math.round(point.y) }));
    if (points.length >= 1) onAddStroke(points, { color, radius });
    setDrawing(null);
  }
  function preventContextMenu(event) {
    event.preventDefault();
    event.stopPropagation();
  }
  return (
    <DocumentViewport width={width} height={height} mode={viewportMode}>
      <div className={`svg-wrap cleanup-canvas ${tool}`}>
        <div className="cleanup-help-badge">{tool === 'eyedropper' ? '클릭: 주변색 선택' : '드래그: 브러시 칠하기 · stroke 클릭: 선택 · Delete: 삭제'}</div>
        <svg ref={svgRef} className="document-svg" viewBox={`0 0 ${width} ${height}`} onContextMenu={preventContextMenu} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp}>
          <image href={imageUrl(imagePath, version)} x="0" y="0" width={width} height={height} preserveAspectRatio="none" />
          {strokes.map((stroke, index) => {
            const active = stroke.id === selectedId;
            const points = stroke.points || [];
            const commonProps = {
              stroke: strokeColor(stroke),
              className: active ? 'cleanup-brush selected' : 'cleanup-brush',
              onPointerDown: (event) => {
                if (event.button !== 0) return;
                event.preventDefault();
                event.stopPropagation();
                setSelectedId(stroke.id);
              },
            };
            if (points.length === 1) {
              return (
                <circle key={stroke.id || index} cx={points[0].x} cy={points[0].y} r={stroke.radius || 10} fill={strokeColor(stroke)} {...commonProps}>
                  <title>{stroke.id}</title>
                </circle>
              );
            }
            return (
              <polyline
                key={stroke.id || index}
                points={pointList(points)}
                fill="none"
                strokeWidth={(stroke.radius || 10) * 2}
                strokeLinecap="round"
                strokeLinejoin="round"
                {...commonProps}
              >
                <title>{stroke.id}</title>
              </polyline>
            );
          })}
          {drawing?.points?.length === 1 && (
            <circle cx={drawing.points[0].x} cy={drawing.points[0].y} r={radius} fill={rgbToHex(color)} className="cleanup-drawing" pointerEvents="none" />
          )}
          {drawing?.points?.length > 1 && (
            <polyline points={pointList(drawing.points)} fill="none" stroke={rgbToHex(color)} strokeWidth={radius * 2} strokeLinecap="round" strokeLinejoin="round" className="cleanup-drawing" vectorEffect="non-scaling-stroke" pointerEvents="none" />
          )}
        </svg>
      </div>
    </DocumentViewport>
  );
}

function DocumentCanvas({ policy, setPolicy, selectedIds, setSelectedIds, editMode, viewportMode, showRenderMode = false }) {
  const svgRef = useRef(null);
  const [drag, setDrag] = useState(null);
  const { width, height } = policy.image;
  const editEnabled = editMode === 'edit';
  function clientToImage(event) {
    const rect = svgRef.current.getBoundingClientRect();
    return { x: ((event.clientX - rect.left) / rect.width) * width, y: ((event.clientY - rect.top) / rect.height) * height };
  }
  function toggleId(id, additive) {
    if (!additive) return setSelectedIds([id]);
    setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }
  function selectOnly(event, label) {
    if (event.button !== 0) return;
    const additive = event.shiftKey || event.metaKey || event.ctrlKey;
    toggleId(label.id, additive);
    event.stopPropagation();
  }
  function beginMove(event, label) {
    if (!editEnabled || event.button !== 0) return;
    event.preventDefault();
    const additive = event.shiftKey || event.metaKey || event.ctrlKey;
    if (!selectedIds.has(label.id)) toggleId(label.id, additive);
    const point = clientToImage(event);
    setDrag({ kind: 'move', id: label.id, start: point, original: bboxOf(label), sourcePolicy: policy, moved: false });
    event.currentTarget.setPointerCapture(event.pointerId);
    event.stopPropagation();
  }
  function beginResize(event, label, handle) {
    if (!editEnabled || event.button !== 0) return;
    event.preventDefault();
    const point = clientToImage(event);
    setSelectedIds([label.id]);
    setDrag({ kind: 'resize', id: label.id, handle, start: point, original: bboxOf(label), sourcePolicy: policy, moved: false });
    event.currentTarget.setPointerCapture(event.pointerId);
    event.stopPropagation();
  }
  function handlePointerDown(event) {
    if (event.button === 2) {
      event.preventDefault();
      return;
    }
    if (event.button !== 0) return;
    const point = clientToImage(event);
    setDrag({ kind: editEnabled ? 'draw' : 'select', start: point, end: point });
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function handlePointerMove(event) {
    if (!drag) return;
    const point = clientToImage(event);
    if (drag.kind === 'move') {
      const dx = point.x - drag.start.x;
      const dy = point.y - drag.start.y;
      const nextBox = clampBox({ ...drag.original, x: drag.original.x + dx, y: drag.original.y + dy }, width, height);
      setPolicy(updatePolicyLabelBox(policy, drag.id, nextBox), { remember: false });
      setDrag({ ...drag, moved: drag.moved || Math.abs(dx) > 2 || Math.abs(dy) > 2 });
      return;
    }
    if (drag.kind === 'resize') {
      const nextBox = resizedBox(drag.original, drag.handle, point, width, height);
      setPolicy(updatePolicyLabelBox(policy, drag.id, nextBox), { remember: false });
      setDrag({ ...drag, moved: true });
      return;
    }
    setDrag({ ...drag, end: point });
  }
  function handlePointerUp(event) {
    if (!drag) return;
    if (drag.kind === 'move') {
      if (drag.moved) {
        const end = clientToImage(event);
        const dx = end.x - drag.start.x;
        const dy = end.y - drag.start.y;
        const nextBox = clampBox({ ...drag.original, x: drag.original.x + dx, y: drag.original.y + dy }, width, height);
        const nextPolicy = updatePolicyLabelBox(drag.sourcePolicy, drag.id, nextBox);
        setPolicy(nextPolicy, { remember: true, snapshot: drag.sourcePolicy });
      }
      setDrag(null);
      return;
    }
    if (drag.kind === 'resize') {
      if (drag.moved) {
        const end = clientToImage(event);
        const nextBox = resizedBox(drag.original, drag.handle, end, width, height);
        const nextPolicy = updatePolicyLabelBox(drag.sourcePolicy, drag.id, nextBox);
        setPolicy(nextPolicy, { remember: true, snapshot: drag.sourcePolicy });
      }
      setDrag(null);
      return;
    }
    const end = clientToImage(event);
    const box = boxFromPoints(drag.start, end, width, height);
    if (Math.abs(box.width) < 6 && Math.abs(box.height) < 6) {
      if (drag.kind === 'select') setSelectedIds([]);
    } else if (drag.kind === 'draw') {
      const added = addPolicyLabel(policy, box);
      setPolicy(added.policy);
      setSelectedIds([added.label.id]);
    } else {
      const x2 = box.x + box.width;
      const y2 = box.y + box.height;
      setSelectedIds(policy.labels.filter((label) => { const itemBox = bboxOf(label); return itemBox.cx >= box.x && itemBox.cx <= x2 && itemBox.cy >= box.y && itemBox.cy <= y2; }).map((label) => label.id));
    }
    setDrag(null);
  }
  function preventContextMenu(event) {
    event.preventDefault();
    event.stopPropagation();
  }
  const dragRect = drag && ['select', 'draw'].includes(drag.kind) && drag.end && boxFromPoints(drag.start, drag.end, width, height);
  const selectedOne = selectedIds.size === 1 ? policy.labels.find((label) => selectedIds.has(label.id)) : null;
  return (
    <DocumentViewport width={width} height={height} mode={viewportMode}>
      <div className={editEnabled ? 'svg-wrap edit-mode' : 'svg-wrap'}>
      <svg ref={svgRef} className="document-svg" viewBox={`0 0 ${width} ${height}`} onContextMenu={preventContextMenu} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerUp}>
        <image href={policy.image_url} x="0" y="0" width={width} height={height} preserveAspectRatio="none" />
        {policy.labels.map((label) => {
          const box = bboxOf(label);
          const isSelected = selectedIds.has(label.id);
          return (
            <g key={label.id}>
              <rect
                data-kind="bbox"
                x={box.x}
                y={box.y}
                width={box.width}
                height={box.height}
                fill="transparent"
                stroke={STATUS_COLORS[label.status] || '#888'}
                strokeWidth={isSelected ? 1.5 : 1}
                vectorEffect="non-scaling-stroke"
                className={`${isSelected ? 'bbox selected' : 'bbox'}${editEnabled ? ' editable' : ''}${label.ocr_text_stale ? ' stale' : ''}${showRenderMode ? ` render-${label.render_mode || 'printed'}` : ''}`}
                onPointerDown={(event) => {
                  if (editEnabled) beginMove(event, label);
                  else selectOnly(event, label);
                }}
                onContextMenu={preventContextMenu}
              >
                <title>{`${label.id} · ${STATUS_LABELS[label.status]}${showRenderMode ? ` · ${BBOX_RENDER_MODE_LABELS[label.render_mode || 'printed'] || label.render_mode || '인쇄체'}` : ''} · ${AUTO_TYPE_LABELS[label.auto_type] || label.auto_type}${label.ocr_text_stale ? ' · 텍스트 재확인 필요' : ''} · ${label.text}`}</title>
              </rect>
              {isSelected && <circle cx={box.cx} cy={box.cy} r="2" fill={STATUS_COLORS[label.status] || '#888'} opacity="0.72" vectorEffect="non-scaling-stroke" pointerEvents="none" />}
              {label.ocr_text_stale && <circle cx={Math.max(3, box.x + 4)} cy={Math.max(3, box.y + 4)} r="2.2" fill="#ff9800" vectorEffect="non-scaling-stroke" pointerEvents="none" />}
            </g>
          );
        })}
        {editEnabled && selectedOne && resizeHandles(bboxOf(selectedOne)).map((handle) => (
          <rect key={handle.id} className="resize-handle" x={handle.x - handle.size / 2} y={handle.y - handle.size / 2} width={handle.size} height={handle.size} vectorEffect="non-scaling-stroke" onPointerDown={(event) => beginResize(event, selectedOne, handle.id)} />
        ))}
        {dragRect && <rect x={dragRect.x} y={dragRect.y} width={dragRect.width} height={dragRect.height} fill={drag.kind === 'draw' ? 'rgba(0,200,83,0.12)' : 'rgba(255,193,7,0.14)'} stroke={drag.kind === 'draw' ? '#00c853' : '#ffc107'} strokeWidth="1.2" vectorEffect="non-scaling-stroke" pointerEvents="none" />}
      </svg>
      </div>
    </DocumentViewport>
  );
}

function resizeHandles(box) {
  const size = Math.max(4, Math.min(6, Math.max(box.width, box.height) * 0.025));
  const midX = box.x + box.width / 2;
  const midY = box.y + box.height / 2;
  const right = box.x + box.width;
  const bottom = box.y + box.height;
  return [
    { id: 'nw', x: box.x, y: box.y, size },
    { id: 'n', x: midX, y: box.y, size },
    { id: 'ne', x: right, y: box.y, size },
    { id: 'e', x: right, y: midY, size },
    { id: 'se', x: right, y: bottom, size },
    { id: 's', x: midX, y: bottom, size },
    { id: 'sw', x: box.x, y: bottom, size },
    { id: 'w', x: box.x, y: midY, size },
  ];
}

function resizedBox(original, handle, point, imageWidth, imageHeight) {
  let x1 = original.x;
  let y1 = original.y;
  let x2 = original.right;
  let y2 = original.bottom;
  if (handle.includes('w')) x1 = point.x;
  if (handle.includes('e')) x2 = point.x;
  if (handle.includes('n')) y1 = point.y;
  if (handle.includes('s')) y2 = point.y;
  if (x2 < x1) [x1, x2] = [x2, x1];
  if (y2 < y1) [y1, y2] = [y2, y1];
  return boxFromPoints({ x: x1, y: y1 }, { x: x2, y: y2 }, imageWidth, imageHeight);
}

export default App;
