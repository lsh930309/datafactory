#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from datafactory.authoring import render_authoring_batch, render_authoring_preview
from datafactory.workbench import update_manifest_artifact
from datafactory.authoring_backup import backup_authoring_json_before_write

DOC_ID = 'RPT-07'
DOC_TITLE = '내부 심사·결재 문서 [산출물]'
DOC_DIR = ROOT / 'workbench' / 'documents' / '내부_심사·결재_문서_[산출물]__RPT-07'
AUTHORING = DOC_DIR / 'authoring'
SCHEMA_PATH = AUTHORING / 'schema.json'
STYLE_PATH = AUTHORING / 'stylesheet.json'
FAKER_PATH = AUTHORING / 'faker_profile.json'
OUT_DIR = AUTHORING / 'render_preview'
BATCH_DIR = ROOT / 'outputs' / 'pipeline_ready' / 'RPT-07_내부 심사·결재 문서 [산출물]'
CALIB_DIR = ROOT / 'outputs' / 'style_calibration' / 'RPT-07_내부 심사·결재 문서 [산출물]'
SEMANTIC_SCHEMA = AUTHORING / 'semantic_schema.json'
PROGRESS = ROOT / 'docs/reports/pipeline_ready/20260702_rpt07_internal_approval_pipeline_readiness.md'
ORIGINAL = DOC_DIR / 'samples' / 'original' / '06월개인경비_page_001.jpg'
INPAINTED = DOC_DIR / 'inpaint' / 'original_06월개인경비_page_001' / 'manual_cleanup' / 'inpainted_lama.png'
REVIEW = DOC_DIR / 'review' / 'original_06월개인경비_page_001' / 'review.json'
FONT_APPLE = Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')
FONT_FALLBACK = ROOT / 'fonts' / 'malgun.ttf'
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = 'AppleSDGothicNeo' if FONT_APPLE.exists() else 'default_korean'
NOW = datetime.now(timezone.utc).isoformat()

# Table grid measured from the source image.  The input has one expense row, but
# authoring keeps the table fields explicit so later rows can be added without a
# schema redesign.
TABLE_X = [75, 205, 335, 463, 593, 723, 853, 982, 1113]
TABLE_Y = [1147, 1170, 1243, 1268]
TABLE_COLS = [
    ('expense_date', '사용일자', 'date.kr', 'style_table_date', 'center'),
    ('vendor', '사용처', 'free_text.short', 'style_table_multiline', 'center'),
    ('receipt_type', '영수증 종류', 'free_text.short', 'style_table_center', 'center'),
    ('receipt_amount', '영수증 금액', 'money.krw', 'style_table_money', 'right'),
    ('claim_amount', '신청 청구금액', 'money.krw', 'style_table_money', 'right'),
    ('purpose', '사용용도', 'free_text.short', 'style_table_multiline', 'center'),
    ('detail_purpose', '상세 사용용도', 'free_text.short', 'style_table_multiline', 'center'),
    ('project', '프로젝트', 'free_text.short', 'style_table_multiline', 'center'),
]


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def field(field_id: str, label: str, bbox: list[int], style_class: str, *, generator: str, value_type: str = 'free_text.short', align: str = 'left', valign: str = 'middle', json_path: str | None = None, notes: str = '', source_detection_id: str = 'manual_rpt07_20260702') -> dict:
    return {
        'field_id': field_id,
        'label': label,
        'bbox': bbox,
        'bbox_format': 'xywh',
        'source_detection_id': source_detection_id,
        'source_text': '',
        'value_type': value_type,
        'generator': generator,
        'style_class': style_class,
        'render_policy': {'align': align, 'valign': valign, 'fit': 'shrink_to_fit', 'overflow': 'shrink'},
        'export': {'json_path': json_path or field_id.replace('_', '.'), 'csv_column': field_id},
        'required': True,
        'notes': notes or '2026-07-02 RPT-07 생산용 수동 bbox/style 보정 필드',
    }


def style_class(style_class_id: str, size: int, *, align: str = 'left', valign: str = 'middle', weight: str = 'normal', opacity: float = 0.96, color: list[int] | None = None, letter_spacing: float = 0.0) -> dict:
    return {
        'style_class': style_class_id,
        'font_family': FONT_FAMILY,
        'font_path': FONT,
        'font_size': size,
        'font_weight': weight,
        'fill': color or [24, 24, 24],
        'opacity': opacity,
        'align': align,
        'valign': valign,
        'line_spacing': 1.0,
        'letter_spacing': letter_spacing,
        'baseline_shift': 0,
        'overflow': 'shrink',
        'confidence': 0.78,
        'source_detection_ids': ['manual_rpt07_20260702'],
    }


def table_cell_bbox(col_idx: int, *, pad_x: int = 7, pad_y: int = 5) -> list[int]:
    x1, x2 = TABLE_X[col_idx], TABLE_X[col_idx + 1]
    y1, y2 = TABLE_Y[1], TABLE_Y[2]
    return [x1 + pad_x, y1 + pad_y, (x2 - x1) - pad_x * 2, (y2 - y1) - pad_y * 2]


def total_cell_bbox(col_idx: int, *, pad_x: int = 7, pad_y: int = 3) -> list[int]:
    x1, x2 = TABLE_X[col_idx], TABLE_X[col_idx + 1]
    y1, y2 = TABLE_Y[2], TABLE_Y[3]
    return [x1 + pad_x, y1 + pad_y, (x2 - x1) - pad_x * 2, (y2 - y1) - pad_y * 2]


def fmt_num(value: int) -> str:
    return f'{value:,}'


def make_profiles() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    people = [
        ('Randy', '이승훈', 'AI솔루션개발팀 - AI엔지니어링 파트', '팀원', 'CFO', 'Kevin 남해솔'),
        ('Mina', '정하윤', '데이터플랫폼팀 - 분석자동화 파트', '팀원', '팀장', 'Chris 박지훈'),
        ('Leo', '김도현', '클라우드운영팀 - 인프라 파트', '매니저', 'CFO', 'Jayden 최민석'),
        ('Grace', '박서연', '서비스기획팀 - B2B솔루션 파트', '책임', '본부장', 'Olivia 한유진'),
        ('Evan', '최준영', '보안개발팀 - 컴플라이언스 파트', '팀원', '팀장', 'Dylan 정우성'),
        ('Jin', '장민재', '사업개발팀 - 파트너십 파트', '팀원', 'CFO', 'Noah 강태윤'),
        ('Irene', '오하린', '품질관리팀 - QA자동화 파트', '선임', '팀장', 'Sophie 윤서아'),
        ('Sean', '문지호', 'AI솔루션개발팀 - 프로덕트 파트', '팀원', 'CTO', 'Ethan 권도윤'),
    ]
    purposes = [
        ('소프트웨어 구독료', 'AI 코딩 에이전트\n구독료(ChatGPT Pro)', '개인카드', 159000, 100000, '소프트웨어\n구독료', '회사 내부\n프로젝트', '회사 내부\n프로젝트', 'Receipt-2417-3864-5631.pdf'),
        ('업무용 클라우드 사용료', '테스트 서버\n월간 사용료', '개인카드', 88000, 88000, '클라우드\n사용료', '개발환경\n검증', 'AI PoC\n프로젝트', 'Receipt-5921-7720-1406.pdf'),
        ('고객 미팅 교통비', '외부 고객사\n방문 택시비', '카드영수증', 46200, 46200, '교통비', '고객사 방문\n및 회의', '영업지원\n프로젝트', 'Taxi-20260614-0918.pdf'),
        ('컨퍼런스 참가비', '산업 컨퍼런스\n온라인 등록비', '개인카드', 220000, 150000, '교육훈련비', '업무 관련\n세미나 참가', '기술리서치\n프로젝트', 'Conf-REG-20260621.pdf'),
        ('자료 구입비', '리서치 보고서\n단건 구매', '개인카드', 77000, 77000, '도서자료비', '시장 분석\n자료 구입', '전략기획\n프로젝트', 'Market-Report-8891.pdf'),
    ]
    weekdays = ['월', '화', '수', '목', '금']
    profiles: list[dict[str, str]] = []
    for i, person in enumerate(people):
        alias, ko_name, department, submitter_role, approver_role, approver = person
        purpose = purposes[i % len(purposes)]
        purpose_line, vendor, receipt_type, receipt_amount, claim_amount, category, detail, project, attach_name = purpose
        day = 6 + (i * 3) % 22
        date_iso = f'2026-06-{day:02d}'
        req_date = f'2026-06-{30 - (i % 4):02d}({weekdays[(i + 1) % len(weekdays)]})'
        approval_date = f'2026/06/{30 - (i % 4):02d}'
        full_name = f'{alias} {ko_name}'
        title_name = f'{ko_name}({alias})'
        amount_line = f'1. 품의 금액: 총 1건, {fmt_num(claim_amount)}원'
        reason = (
            f'사내 규정상 업무 수행에 필요한 {purpose_line} 사용 내역을 아래와 같이 품의합니다.\n'
            f'{date_iso} 사용분은 {department.split(" - ")[0]} 업무와 직접 관련된 비용이며, 증빙자료를 첨부하였습니다.\n'
            '개인경비 사용내역을 아래와 같이 품의합니다.'
        )
        profiles.append({
            'requester_name': full_name,
            'department': department,
            'request_date': req_date,
            'document_number': '',
            'submitter_role': submitter_role,
            'approver_role': approver_role,
            'submitter_name': full_name,
            'approver_name': approver,
            'approval_date': approval_date,
            'expense_title': f'{title_name} 6월 개인경비 지출결의',
            'account_number': f'{rng.randint(100,999)}-{rng.randint(100,999)}-{rng.randint(100000,999999)}',
            'special_note': reason,
            'amount_line': amount_line,
            'purpose_line': f'2. 개인경비 사용용도: {purpose_line}',
            'expense_date': date_iso,
            'vendor': vendor,
            'receipt_type': receipt_type,
            'receipt_amount': fmt_num(receipt_amount),
            'claim_amount': fmt_num(claim_amount),
            'purpose': category,
            'detail_purpose': detail,
            'project': project,
            'total_label': '합계(총 1건)',
            'total_claim_amount': f'{fmt_num(claim_amount)}원',
            'attachment_summary': f'첨부파일 1개 ({rng.choice([42.7, 58.3, 64.4, 71.2, 86.5]):.1f}KB)',
            'attachment_filename': f'{attach_name} ({rng.choice([42.7, 58.3, 64.4, 71.2, 86.5]):.1f}KB) AI요약',
        })
    return profiles



ORIGINAL_SOURCE_RECORD = {
    'requester_name': 'Randy 이승훈',
    'department': 'AI솔루션개발팀 - AI엔지니어링 파트',
    'request_date': '2026-06-30(화)',
    'document_number': '',
    'submitter_role': '팀원',
    'approver_role': 'CFO',
    'submitter_name': 'Randy 이승훈',
    'approver_name': 'Kevin 남해솔',
    'approval_date': '2026/06/30',
    'expense_title': '이승훈(Randy) 6월 개인경비 지출결의',
    'account_number': '110-560-052435',
    'special_note': '사내 규정상 반드시 @koreadeep.com 계정으로 가입 및 이용하도록 규정되어 있는 것을 확인하였으나, 6월 결제일(2026-06-06) 당시에는 사내 메일 계\n정을 지급받지 못한 상황이었기에 개인 계정(lsh930309@gmail.com)으로 결제를 진행하게 되었습니다.\n익월(2026년 7월)부터는 2026-06-29(월) 부로 지급받은 사내 이메일 계정으로 신규 가입하여 결제 및 사용할 예정입니다.\n개인경비 사용내역을 아래와 같이 품의합니다.',
    'amount_line': '1. 품의 금액: 총 1건, 100,000원',
    'purpose_line': '2. 개인경비 사용용도: 소프트웨어 구독료',
    'expense_date': '2026-06-06',
    'vendor': 'AI 코딩 에이전트\n구독료(ChatGPT Pro)',
    'receipt_type': '개인카드',
    'receipt_amount': '159,000',
    'claim_amount': '100,000',
    'purpose': '소프트웨어\n구독료',
    'detail_purpose': '회사 내부\n프로젝트',
    'project': '회사 내부\n프로젝트',
    'total_label': '합계(총 1건)',
    'total_claim_amount': '100,000원',
    'attachment_summary': '첨부파일 1개 (64.4KB)',
    'attachment_filename': 'Receipt-2417-3864-5631.pdf (64.4KB) AI요약',
}

def build_schema() -> dict:
    fields: list[dict] = []
    add = fields.append
    add(field('requester_name', '기안자', [198, 194, 220, 32], 'style_body', generator='pool_record:rpt07_expense_profiles.requester_name', value_type='person.name_ko', json_path='approval.requester.name'))
    add(field('department', '소속', [198, 231, 300, 32], 'style_body_small', generator='pool_record:rpt07_expense_profiles.department', json_path='approval.requester.department'))
    add(field('request_date', '기안일', [198, 269, 135, 32], 'style_body', generator='pool_record:rpt07_expense_profiles.request_date', value_type='date.kr', json_path='approval.request.date'))
    add(field('document_number', '문서번호', [198, 305, 220, 31], 'style_body', generator='pool_record:rpt07_expense_profiles.document_number', json_path='approval.document_number', notes='원본 양식의 문서번호 칸은 공란이므로 faker record도 기본 공란 유지'))
    add(field('submitter_role', '신청 결재 역할', [875, 191, 95, 34], 'style_approval_role', generator='pool_record:rpt07_expense_profiles.submitter_role', json_path='approval.line.submitter.role', align='center'))
    add(field('approver_role', '승인 결재 역할', [1010, 191, 100, 34], 'style_approval_role', generator='pool_record:rpt07_expense_profiles.approver_role', json_path='approval.line.approver.role', align='center'))
    add(field('submitter_name', '신청자', [872, 251, 100, 46], 'style_approval_name', generator='pool_record:rpt07_expense_profiles.submitter_name', json_path='approval.line.submitter.name', align='center'))
    add(field('approver_name', '승인자', [1015, 252, 95, 46], 'style_approval_name', generator='pool_record:rpt07_expense_profiles.approver_name', json_path='approval.line.approver.name', align='center'))
    add(field('approval_date', '결재일', [880, 327, 86, 27], 'style_approval_date', generator='pool_record:rpt07_expense_profiles.approval_date', value_type='date.kr', json_path='approval.line.submitter.date', align='center'))
    add(field('expense_title', '제목', [240, 461, 470, 34], 'style_title_value', generator='pool_record:rpt07_expense_profiles.expense_title', json_path='expense.title'))
    add(field('account_number', '계좌번호', [240, 510, 190, 34], 'style_body', generator='pool_record:rpt07_expense_profiles.account_number', json_path='payment.account_number'))
    add(field('special_note', '특이사항', [74, 904, 1035, 67], 'style_special_note', generator='pool_record:rpt07_expense_profiles.special_note', json_path='expense.special_note', valign='top'))
    add(field('amount_line', '품의 금액', [72, 1042, 300, 31], 'style_line_item', generator='pool_record:rpt07_expense_profiles.amount_line', json_path='expense.amount_summary'))
    add(field('purpose_line', '개인경비 사용용도', [72, 1072, 420, 31], 'style_line_item', generator='pool_record:rpt07_expense_profiles.purpose_line', json_path='expense.purpose_summary'))
    for idx, (suffix, label, value_type, style, align) in enumerate(TABLE_COLS):
        add(field(f'expense_1_{suffix}', f'상세내역 1행 {label}', table_cell_bbox(idx), style, generator=f'pool_record:rpt07_expense_profiles.{suffix}', value_type=value_type, align=align, json_path=f'expense.rows.1.{suffix}', source_detection_id='manual_table_grid_20260702'))
    add(field('total_label', '합계 라벨', total_cell_bbox(0), 'style_total_label', generator='pool_record:rpt07_expense_profiles.total_label', align='center', json_path='expense.total.label', source_detection_id='manual_table_grid_20260702'))
    add(field('total_claim_amount', '합계 청구금액', total_cell_bbox(4), 'style_total_money', generator='pool_record:rpt07_expense_profiles.total_claim_amount', value_type='money.krw', align='right', json_path='expense.total.claim_amount', source_detection_id='manual_table_grid_20260702'))
    add(field('attachment_summary', '첨부파일 요약', [83, 1299, 240, 31], 'style_attachment_summary', generator='pool_record:rpt07_expense_profiles.attachment_summary', json_path='attachments.summary'))
    add(field('attachment_filename', '첨부파일명', [80, 1344, 390, 34], 'style_attachment_file', generator='pool_record:rpt07_expense_profiles.attachment_filename', json_path='attachments.files.1.name'))
    return {
        'schema_version': 1,
        'created_at': NOW,
        'updated_at': NOW,
        'doc_id': DOC_ID,
        'title': DOC_TITLE,
        'source_review': str(REVIEW.resolve()),
        'source_image': str(ORIGINAL.resolve()),
        'source_inpainted': str(INPAINTED.resolve()),
        'image': {'width': 1191, 'height': 1684},
        'fields': fields,
        'groups': [
            {
                'group_id': 'expense_rows',
                'type': 'table',
                'row_count': 1,
                'columns': [col[0] for col in TABLE_COLS],
                'grid': {'x': TABLE_X, 'y': TABLE_Y},
                'notes': '원본 개인경비 지출결의서의 상세 내역 표를 1행 생산용 table group으로 구조화함.',
            },
            {
                'group_id': 'approval_line',
                'type': 'approval_boxes',
                'columns': ['submitter', 'approver'],
                'notes': '상단 우측 신청/승인 결재 박스 필드 묶음.',
            },
        ],
        'authoring_mode': 'rpt07_pipeline_ready_20260702',
        'quality_status': 'pipeline_ready_candidate',
    }


def build_stylesheet() -> dict:
    classes = [
        style_class('style_body', 19, opacity=0.97),
        style_class('style_body_small', 16, opacity=0.97),
        style_class('style_approval_role', 19, align='center', opacity=0.97),
        style_class('style_approval_name', 20, align='center', weight='bold', opacity=0.98),
        style_class('style_approval_date', 18, align='center', opacity=0.97),
        style_class('style_title_value', 18, opacity=0.98, weight='bold'),
        style_class('style_special_note', 17, valign='top', opacity=0.96),
        style_class('style_line_item', 18, opacity=0.98),
        style_class('style_table_date', 18, align='center', opacity=0.97),
        style_class('style_table_center', 18, align='center', opacity=0.97),
        style_class('style_table_money', 18, align='right', opacity=0.97),
        style_class('style_table_multiline', 17, align='center', opacity=0.97),
        style_class('style_total_label', 17, align='center', weight='bold', opacity=0.98),
        style_class('style_total_money', 18, align='right', weight='bold', opacity=0.98),
        style_class('style_attachment_summary', 20, opacity=0.97, weight='bold'),
        style_class('style_attachment_file', 18, opacity=0.92, color=[45, 45, 45]),
    ]
    return {
        'schema_version': 1,
        'created_at': NOW,
        'updated_at': NOW,
        'doc_id': DOC_ID,
        'source_image': str(ORIGINAL.resolve()),
        'style_classes': classes,
        'notes': '2026-07-02 RPT-07 내부 심사·결재 문서 생산용 1차 스타일. 원본/렌더 전체 비교와 overlay 기준으로 Apple SD Gothic Neo 계열을 선택하고 bbox별 크기/정렬을 보정함. crop 비교 루틴은 사용하지 않음.',
    }


def build_semantic_schema(schema: dict) -> dict:
    field_mapping = {field['field_id']: field['export']['json_path'] for field in schema.get('fields', [])}
    return {
        'schema_version': 1,
        'created_at': NOW,
        'updated_at': NOW,
        'doc_id': DOC_ID,
        'title': DOC_TITLE,
        'purpose': '렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조',
        'semantic_schema': {
            '내부 심사·결재 문서': {
                '기안자 정보': {
                    '기안자': '',
                    '소속': '',
                    '기안일': '',
                    '문서번호': '',
                },
                '결재선': {
                    '신청': {'역할': '', '성명': '', '결재일': ''},
                    '승인': {'역할': '', '성명': ''},
                },
                '지출결의': {
                    '제목': '',
                    '계좌번호': '',
                    '특이사항': '',
                    '품의 금액': '',
                    '개인경비 사용용도': '',
                },
                '상세 내역': [
                    {
                        '사용일자': '',
                        '사용처': '',
                        '영수증 종류': '',
                        '영수증 금액': '',
                        '신청 청구금액': '',
                        '사용용도': '',
                        '상세 사용용도': '',
                        '프로젝트': '',
                    }
                ],
                '합계': {'라벨': '', '신청 청구금액': ''},
                '첨부파일': {'요약': '', '파일명': ''},
            }
        },
        'field_mapping': field_mapping,
        'notes': [
            'schema.json은 renderer 호환을 위해 bbox/style/generator/render_policy를 유지한다.',
            'semantic_schema.json은 KIE용 key-name 계층만 별도 관리한다.',
            '현재 synthetic profile은 개인경비 지출결의서 subtype의 1행 상세내역을 기준으로 한다.',
        ],
    }


def build_faker_profile(fields: list[dict]) -> dict:
    profiles = make_profiles()
    field_generators = {f['field_id']: f['generator'] for f in fields}
    targets = {f['field_id']: f['generator'].split('.', 1)[1] for f in fields if str(f['generator']).startswith('pool_record:rpt07_expense_profiles.')}
    for field_id, rule in list(field_generators.items()):
        if str(rule).startswith('pool_record:'):
            field_generators[field_id] = 'literal:'
    return {
        'schema_version': 1,
        'created_at': NOW,
        'updated_at': NOW,
        'doc_id': DOC_ID,
        'locale': 'ko_KR',
        'field_generators': field_generators,
        'constraints': [{'type': 'pick_record', 'pool': 'rpt07_expense_profiles', 'targets': targets}],
        'data_pools': {'rpt07_expense_profiles': profiles},
        'notes': 'RPT-07 개인경비 지출결의서용 faker profile. 기안자/부서/결재자/금액/첨부파일을 하나의 record에서 선택해 문서 내 정합성을 유지함.',
    }


def fit_same_size(a: Image.Image, b: Image.Image) -> tuple[Image.Image, Image.Image]:
    a = a.convert('RGB')
    b = b.convert('RGB')
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.BICUBIC)
    return a, b



def render_original_value_calibration() -> Path:
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    faker = json.loads(FAKER_PATH.read_text(encoding='utf-8'))
    faker['data_pools'] = {'rpt07_expense_profiles': [ORIGINAL_SOURCE_RECORD]}
    faker['notes'] = 'RPT-07 원본값 기반 style calibration profile. crop 비교 없이 전체 문서와 overlay 비교에만 사용.'
    path = CALIB_DIR / 'calibration_faker_profile.json'
    write_json(path, faker)
    result = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, path, out_dir=CALIB_DIR / 'render', seed=1, sample_id='calibration_original_values')
    return result.image

def make_full_comparison(rendered_path: Path) -> None:
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    orig, rend = fit_same_size(Image.open(ORIGINAL), Image.open(rendered_path))
    inp = Image.open(INPAINTED).convert('RGB').resize(orig.size, Image.Resampling.BICUBIC)
    diff = ImageChops.difference(orig, rend)
    diff_amp = diff.point(lambda v: min(255, v * 3))
    blend = Image.blend(orig, rend, 0.5)
    labels = [('original', orig), ('inpainted', inp), ('render', rend), ('amplified diff', diff_amp), ('50% overlay', blend)]
    scale_w = 430
    thumbs = []
    for label, im in labels:
        t = im.copy()
        t.thumbnail((scale_w, 610))
        thumbs.append((label, t))
    font = ImageFont.truetype(str(FONT_FALLBACK), 20) if FONT_FALLBACK.exists() else ImageFont.load_default()
    sheet = Image.new('RGB', (scale_w * len(thumbs) + 20 * (len(thumbs) + 1), 690), (245, 245, 242))
    draw = ImageDraw.Draw(sheet)
    for i, (label, t) in enumerate(thumbs):
        x = 20 + i * (scale_w + 20)
        draw.text((x, 18), label, font=font, fill=(20, 20, 20))
        sheet.paste(t, (x, 54))
        draw.rectangle([x, 54, x + t.width, 54 + t.height], outline=(150, 150, 150))
    sheet.save(CALIB_DIR / 'full_comparison.jpg', quality=92)
    diff.save(CALIB_DIR / 'full_diff.png')
    blend.save(CALIB_DIR / 'full_overlay_50.png')


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    thumbs = []
    for path in sample_paths:
        im = Image.open(path).convert('RGB')
        im.thumbnail((330, 470))
        thumbs.append((path.stem, im.copy()))
    font = ImageFont.truetype(str(FONT_FALLBACK), 18) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cols = 5
    w = cols * 350 + 20
    h = 540
    sheet = Image.new('RGB', (w, h), (246, 246, 243))
    draw = ImageDraw.Draw(sheet)
    for idx, (label, im) in enumerate(thumbs):
        x = 20 + idx * 350
        y = 24
        draw.text((x, y), label, font=font, fill=(25, 25, 25))
        sheet.paste(im, (x, y + 34))
        draw.rectangle([x, y + 34, x + im.width, y + 34 + im.height], outline=(155, 155, 155))
    out = BATCH_DIR / 'contact_sheet.jpg'
    sheet.save(out, quality=92)
    return out


def write_progress(preview, batch, contact_sheet: Path) -> None:
    PROGRESS.write_text(f'''# 2026-07-02 RPT-07 내부 심사·결재 문서 파이프라인 준비 작업

## 목표
- `RPT-07 내부 심사·결재 문서 [산출물]`를 주주명부 이후 두 번째 순차 처리 대상으로 삼는다.
- 현재 확보된 샘플 `개인경비 지출결의서`를 기준으로 bbox/schema/faker/style/render를 생산 가능한 수준으로 구성한다.
- 모든 문서 병렬 처리는 하지 않고, 본 문서 1건에 대해서만 현 단계의 작업 내역과 결과를 기록한다.

## 입력 상태
- 원본 이미지: `{ORIGINAL}`
- 인페인팅 템플릿: `{INPAINTED}`
- bbox review: `{REVIEW}`
- 수동 cleanup이 적용된 LaMa 템플릿을 base image로 사용했다.

## 시각 분석 및 구조화 결정
- 문서는 1페이지짜리 개인경비 지출결의서이며, 크게 `기안자 정보`, `신청/승인 결재 박스`, `제목/계좌번호`, `특이사항`, `상세 내역 표`, `첨부파일`로 구성된다.
- 원본에는 상세 내역 표 1행만 값이 있으므로, v1 생산용 schema도 우선 1행 table group으로 정의한다.
- 원본의 정적 안내문/표 헤더/회색 합계 행은 인페인팅 템플릿에 남겨두고, 실제 치환 값만 field로 둔다.
- 본문 `특이사항`은 장문 필드로 유지하되 faker 값에 줄바꿈을 명시하여 bbox 안에 들어가게 했다.
- font-family는 렌더링 결과물 시각 비교 기준으로 Apple SD Gothic Neo 계열을 1차 선택했다.
- crop 비교 루틴은 사용하지 않고, 전체 문서 비교와 50% overlay 기준으로만 보정했다.

## schema/faker/style 반영
- schema: `{SCHEMA_PATH}`
- stylesheet: `{STYLE_PATH}`
- faker_profile: `{FAKER_PATH}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
- field 수: {batch.field_count}
- 생성 record는 기안자/부서/결재자/금액/첨부파일명이 서로 맞도록 하나의 pool record에서 선택된다.

## 산출물
- preview: `{preview.image}`
- preview overlay: `{preview.overlay}`
- preview validation: `{preview.validation_report}`
- batch summary: `{batch.summary}`
- batch output dir: `{BATCH_DIR}`
- contact sheet: `{contact_sheet}`
- original-value calibration render: `{CALIB_DIR / 'render' / 'calibration_original_values.png'}`
- full comparison: `{CALIB_DIR / 'full_comparison.jpg'}`
- 50% overlay: `{CALIB_DIR / 'full_overlay_50.png'}`

## 검수 결과 및 남은 리스크
- 렌더 경고 수: {batch.warning_count}
- 현재 1차 결과는 원본 개인경비 지출결의서의 구조와 대부분 일치한다.
- 다만 원본 샘플이 한 종류뿐이므로, 향후 다른 내부 결재 양식이 추가되면 RPT-07 하위 템플릿을 문서 subtype별로 나누는 것이 안전하다.
- 상세 내역 표는 현재 1행 생산을 기준으로 했다. 복수 행 비용 정산을 지원하려면 하단 표 높이/행 추가가 필요하다.
''', encoding='utf-8')


def main() -> None:
    if not ORIGINAL.exists():
        raise FileNotFoundError(ORIGINAL)
    if not INPAINTED.exists():
        raise FileNotFoundError(INPAINTED)
    AUTHORING.mkdir(parents=True, exist_ok=True)
    if CALIB_DIR.exists():
        shutil.rmtree(CALIB_DIR)
    schema = build_schema()
    stylesheet = build_stylesheet()
    faker_profile = build_faker_profile(schema['fields'])
    write_json(SCHEMA_PATH, schema)
    write_json(STYLE_PATH, stylesheet)
    write_json(FAKER_PATH, faker_profile)
    write_json(SEMANTIC_SCHEMA, build_semantic_schema(schema))

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix='rpt07', clean=True)
    contact = make_contact_sheet([sample.image for sample in batch.samples])
    calibration_image = render_original_value_calibration()
    make_full_comparison(calibration_image)

    update_manifest_artifact(DOC_ID, 'authoring', SCHEMA_PATH)
    update_manifest_artifact(DOC_ID, 'authoring_stylesheet', STYLE_PATH)
    update_manifest_artifact(DOC_ID, 'authoring_faker_profile', FAKER_PATH)
    update_manifest_artifact(DOC_ID, 'authoring_semantic_schema', SEMANTIC_SCHEMA)
    update_manifest_artifact(DOC_ID, 'authoring_preview', preview.image)
    update_manifest_artifact(DOC_ID, 'authoring_overlay', preview.overlay)
    update_manifest_artifact(DOC_ID, 'authoring_batch', batch.summary)
    update_manifest_artifact(DOC_ID, 'authoring_contact_sheet', contact)
    update_manifest_artifact(DOC_ID, 'authoring_style_comparison', CALIB_DIR / 'full_comparison.jpg')

    write_progress(preview, batch, contact)
    print('preview', preview.image)
    print('overlay', preview.overlay)
    print('warnings', preview.warning_count)
    print('batch', batch.summary, 'samples', batch.sample_count, 'warnings', batch.warning_count)
    print('contact', contact)
    print('comparison', CALIB_DIR / 'full_comparison.jpg')


if __name__ == '__main__':
    main()
