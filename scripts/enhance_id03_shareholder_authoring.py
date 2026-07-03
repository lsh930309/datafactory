#!/usr/bin/env python3
from __future__ import annotations

import json
import random
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / 'src'))

from datafactory.authoring import render_authoring_batch, render_authoring_preview
from datafactory.workbench import update_manifest_artifact
from datafactory.authoring_backup import backup_authoring_json_before_write

DOC_DIR = ROOT / 'workbench' / 'documents' / '주주명부__ID-03'
AUTHORING = DOC_DIR / 'authoring'
SCHEMA_PATH = AUTHORING / 'schema.json'
STYLE_PATH = AUTHORING / 'stylesheet.json'
FAKER_PATH = AUTHORING / 'faker_profile.json'
OUT_DIR = AUTHORING / 'render_preview'
BATCH_DIR = ROOT / 'outputs' / 'pipeline_ready' / 'ID-03_주주명부'
PROGRESS = ROOT / 'docs/reports/pipeline_ready/20260702_id03_shareholder_pipeline_readiness.md'
SEMANTIC_SCHEMA_PATH = AUTHORING / 'semantic_schema.json'
FONT_REG = '/System/Library/Fonts/AppleSDGothicNeo.ttc'
FONT_BOLD = str(ROOT / 'fonts' / 'malgunbd.ttf')
if not Path(FONT_REG).exists():
    FONT_REG = str(ROOT / 'fonts' / 'malgun.ttf')

NOW = datetime.now(timezone.utc).isoformat()

# Grid measured from source image line candidates.  The source contains one filled
# shareholder row, but the production template must support the whole blank table.
TABLE_X = [143, 293, 430, 568, 706, 843, 996]
TABLE_Y = [386, 443, 500, 557, 614, 671, 728, 785, 842, 899, 956]
COLS = ['name', 'share_count', 'attendance_shares', 'approval_shares', 'notarization_shares', 'note']
COL_LABELS = {
    'name': '주주명',
    'share_count': '소유주식수',
    'attendance_shares': '회의출석',
    'approval_shares': '의결찬성',
    'notarization_shares': '인증촉탁',
    'note': '비고',
}
ALIGN = {
    'name': 'center',
    'share_count': 'right',
    'attendance_shares': 'right',
    'approval_shares': 'right',
    'notarization_shares': 'right',
    'note': 'center',
}
STYLE = {
    'name': ('style_table_name', 23, 'normal'),
    'share_count': ('style_table_number', 20, 'normal'),
    'attendance_shares': ('style_table_number', 20, 'normal'),
    'approval_shares': ('style_table_number', 20, 'normal'),
    'notarization_shares': ('style_table_number', 20, 'normal'),
    'note': ('style_table_note', 16, 'normal'),
}

COMPANIES = [
    ('주식회사 엔식품', '경기도 하남시 대성로 69번길 48'),
    ('새론패션 주식회사', '강원특별자치도 원주시 혁신로 19'),
    ('한빛정밀 주식회사', '서울특별시 강남구 테헤란로 152'),
    ('대한소재 주식회사', '서울특별시 중구 세종대로 110'),
    ('미래모빌리티 주식회사', '서울특별시 마포구 월드컵북로 396'),
    ('세종바이오 주식회사', '경기도 성남시 분당구 판교역로 235'),
    ('아라전자 주식회사', '부산광역시 해운대구 센텀중앙로 79'),
    ('태성기계 주식회사', '대구광역시 달서구 성서공단로 11'),
    ('누리패키징 주식회사', '대전광역시 유성구 테크노중앙로 50'),
    ('동원테크놀로지 주식회사', '광주광역시 북구 첨단과기로 123'),
]
FIRST_NAMES = ['김민준','이서준','박도윤','최예준','정시우','강하준','조주원','윤지호','장지후','임준우','한서연','오서윤','서지우','신서현','권민서','김하은','이하윤','박윤서','최지유','정지민','강도현','조현우','윤서진','장유준','임건우']
DATES = ['2023년 5월 8일','2023년 12월 29일','2024년 3월 8일','2024년 6월 21일','2024년 9월 30일','2025년 1월 15일','2025년 4월 11일','2025년 8월 7일','2025년 12월 18일','2026년 2월 5일']
PAR_VALUES = [100, 500, 1000, 5000]
NOTES = ['', '', '', '', '대표주주', '공동보유', '임원', '창업주', '']


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data: dict) -> None:
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def semantic_schema(fields: list[dict]) -> dict:
    """Meaning-first schema separated from bbox/style renderer metadata."""

    field_paths = {
        item['field_id']: item.get('export', {}).get('json_path', item['field_id'])
        for item in fields
    }
    return {
        'schema_version': 1,
        'doc_id': 'ID-03',
        'title': '주주명부',
        'updated_at': NOW,
        'purpose': 'KIE label/value 구조 정의. bbox/style/render_policy는 schema.json 및 stylesheet.json에서 관리한다.',
        'schema': {
            '주주명부': {
                '기준일': '',
                '기준일_접미어': '',
                '주주': [
                    {
                        '순번': '',
                        '주주명': '',
                        '소유주식수': '',
                        '회의출석주식수': '',
                        '의결찬성주식수': '',
                        '인증촉탁주식수': '',
                        '비고': '',
                    }
                ],
                '합계': {
                    '총주식수': '',
                    '출석주식수': '',
                    '의결찬성주식수': '',
                    '인증촉탁주식수': '',
                    '1주당_금액': '',
                    '자본금': '',
                },
                '증명문구': '위 주주명부는 본사에 비치된 주주명부와 대조하여 틀림이 없음을 증명합니다.',
                '작성일': '',
                '회사': {
                    '회사명': '',
                    '소재지': '',
                    '대표이사': '',
                },
            }
        },
        'field_mapping': field_paths,
        'notes': [
            '원본은 1개 주주 행만 값이 있으나, 생산용 KIE를 위해 9개 주주 행 전체를 반복 구조로 정의한다.',
            'renderer 호환 schema.json에는 field_id/bbox/style_class/render_policy가 유지된다.',
            '이 파일은 사람이 읽는 의미 schema 및 라벨 구조의 기준이다.',
        ],
    }


def fmt_num(n: int) -> str:
    return f'{n:,}'


def field(field_id: str, label: str, bbox: list[int], style_class: str, *, generator: str, value_type='free_text.short', align='center', json_path: str | None = None, notes='') -> dict:
    return {
        'field_id': field_id,
        'label': label,
        'bbox': bbox,
        'bbox_format': 'xywh',
        'source_detection_id': 'manual_grid_20260702',
        'source_text': '',
        'value_type': value_type,
        'generator': generator,
        'style_class': style_class,
        'render_policy': {'align': align, 'valign': 'middle', 'fit': 'shrink_to_fit', 'overflow': 'shrink'},
        'export': {'json_path': json_path or field_id.replace('_', '.'), 'csv_column': field_id},
        'required': True,
        'notes': notes or '2026-07-02 ID-03 고품질 생산 템플릿: 원본 빈 표 구조를 grid 기준으로 확장한 수동 bbox',
    }


def cell_bbox(row: int, col: int, pad_x=8, pad_y=8) -> list[int]:
    x1, x2 = TABLE_X[col], TABLE_X[col + 1]
    y1, y2 = TABLE_Y[row], TABLE_Y[row + 1]
    return [x1 + pad_x, y1 + pad_y, (x2 - x1) - pad_x * 2, (y2 - y1) - pad_y * 2]


def display_date(value: str) -> str:
    """Match the source document's visually spaced Korean date notation."""

    return value.replace('년 ', '년  ').replace('월 ', '월  ')


def spaced_name(value: str) -> str:
    return ' '.join(value) if value and ' ' not in value else value


def style_class(style_class: str, size: int, *, align='center', weight='normal', opacity=0.88, letter_spacing=0.0, baseline_shift=0) -> dict:
    font_path = FONT_BOLD if weight == 'bold' else FONT_REG
    return {
        'style_class': style_class,
        'font_family': 'AppleSDGothicNeo' if Path(FONT_REG).name == 'AppleSDGothicNeo.ttc' else 'default_korean',
        'font_path': font_path,
        'font_size': size,
        'font_weight': weight,
        'fill': [32, 34, 34],
        'opacity': opacity,
        'align': align,
        'valign': 'middle',
        'line_spacing': 1.0,
        'letter_spacing': letter_spacing,
        'baseline_shift': baseline_shift,
        'overflow': 'shrink',
        'confidence': 0.86,
        'source_detection_ids': ['manual_grid_20260702'],
    }


def make_profiles() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    profiles=[]
    for i, (company, address) in enumerate(COMPANIES):
        raw_date = DATES[i % len(DATES)]
        date = display_date(raw_date)
        par = PAR_VALUES[i % len(PAR_VALUES)]
        row_count = 1 + (i % 5)  # 1..5 filled shareholders; remaining rows intentionally blank.
        names = rng.sample(FIRST_NAMES, row_count)
        # Generate balanced share counts with clean commercial-document style numbers.
        base_units = [rng.choice([10, 20, 25, 30, 40, 50, 75, 100]) for _ in range(row_count)]
        total_units = sum(base_units)
        scale = rng.choice([100, 200, 500, 1000])
        shares = [u * scale for u in base_units]
        total = sum(shares)
        attendance = sum(shares[: max(1, row_count - (i % 2))])
        approval = attendance if i % 3 != 0 else max(shares[0], attendance - shares[-1])
        notarization = approval if i % 4 != 0 else shares[0]
        record={
            'list_date': date,
            'list_date_suffix': '현재',
            'issue_date': date,
            'company_name': company,
            'company_address': address,
            'representative_name': spaced_name(names[0]),
            'total_issued_shares': f'{fmt_num(total)}주',
            'attendance_total': f'{fmt_num(attendance)}주' if attendance else '',
            'approval_total': f'{fmt_num(approval)}주' if approval else '',
            'notarization_total': f'{fmt_num(notarization)}주' if notarization else '',
            'par_value': f'{fmt_num(par)}원',
            'capital_amount': f'{fmt_num(total * par)}원',
        }
        for r in range(1, 10):
            if r <= row_count:
                s = shares[r - 1]
                attends = s if r <= max(1, row_count - (i % 2)) else 0
                approves = attends if not (i % 3 == 0 and r == row_count) else 0
                notarizes = approves if not (i % 4 == 0 and r > 1) else 0
                record.update({
                    f'shareholder_{r}_name': names[r - 1],
                    f'shareholder_{r}_share_count': fmt_num(s),
                    f'shareholder_{r}_attendance_shares': fmt_num(attends) if attends else '',
                    f'shareholder_{r}_approval_shares': fmt_num(approves) if approves else '',
                    f'shareholder_{r}_notarization_shares': fmt_num(notarizes) if notarizes else '',
                    f'shareholder_{r}_note': NOTES[(i + r) % len(NOTES)],
                })
            else:
                for c in COLS:
                    record[f'shareholder_{r}_{c}'] = ''
        profiles.append(record)
    return profiles


def main() -> None:
    schema = load_json(SCHEMA_PATH)
    stylesheet = load_json(STYLE_PATH)
    faker = load_json(FAKER_PATH)

    fields=[]
    # Header date: source date + suffix are separate so the suffix can stay visually aligned.
    fields.append(field('shareholder_list_date', '주주명부 기준일', [765, 292, 166, 33], 'style_header_date', generator='pool_record:id03_registry_profiles.list_date', value_type='date.kr', align='center', json_path='shareholder.list.date'))
    fields.append(field('shareholder_list_date_suffix', '기준일 접미어', [935, 292, 53, 33], 'style_header_suffix', generator='pool_record:id03_registry_profiles.list_date_suffix', align='center', json_path='shareholder.list.date.suffix'))

    for r in range(1, 10):
        for c_idx, col in enumerate(COLS):
            style_id, _size, _weight = STYLE[col]
            fields.append(field(
                f'shareholder_{r}_{col}',
                f'주주 {r} {COL_LABELS[col]}',
                cell_bbox(r - 1, c_idx, pad_x=9 if col == 'name' else 8, pad_y=8),
                style_id,
                generator=f'pool_record:id03_registry_profiles.shareholder_{r}_{col}',
                align=ALIGN[col],
                json_path=f'shareholders.{r}.{col}',
                notes='원본에는 일부 행만 값이 있으나, 생산용 KIE 템플릿을 위해 주주 표 전체 행/열을 bbox로 확장함.',
            ))

    fields.extend([
        field('total_issued_shares', '총주식수', [157, 1028, 150, 38], 'style_summary_number', generator='pool_record:id03_registry_profiles.total_issued_shares', align='center', json_path='totals.issued_shares'),
        field('attendance_total', '출석주식수', [326, 1028, 150, 38], 'style_summary_number', generator='pool_record:id03_registry_profiles.attendance_total', align='center', json_path='totals.attendance_shares'),
        field('approval_total', '의결찬성주식수', [493, 1028, 150, 38], 'style_summary_number', generator='pool_record:id03_registry_profiles.approval_total', align='center', json_path='totals.approval_shares'),
        field('notarization_total', '인증촉탁주식수', [665, 1028, 150, 38], 'style_summary_number', generator='pool_record:id03_registry_profiles.notarization_total', align='center', json_path='totals.notarization_shares'),
        field('par_value', '1주당 금액', [832, 1028, 150, 38], 'style_summary_number', generator='pool_record:id03_registry_profiles.par_value', align='center', json_path='totals.par_value'),
        field('issue_date', '작성일', [768, 1158, 196, 38], 'style_footer_date', generator='pool_record:id03_registry_profiles.issue_date', value_type='date.kr', align='center', json_path='issue.date'),
        field('company_name', '회사명', [637, 1214, 300, 37], 'style_footer_company', generator='pool_record:id03_registry_profiles.company_name', align='left', json_path='company.name'),
        field('company_address', '소재지', [637, 1268, 390, 38], 'style_footer_address', generator='pool_record:id03_registry_profiles.company_address', align='left', json_path='company.address'),
        field('representative_name', '대표이사', [637, 1322, 140, 38], 'style_footer_rep', generator='pool_record:id03_registry_profiles.representative_name', align='left', json_path='representative.name'),
    ])

    schema.update({
        'updated_at': NOW,
        'fields': fields,
        'groups': [
            {
                'group_id': 'shareholder_rows',
                'type': 'table',
                'row_count': 9,
                'columns': COLS,
                'grid': {'x': TABLE_X, 'y': TABLE_Y},
                'notes': '원본 빈 표를 생산 가능 KIE 데이터로 확장한 주주 행 그룹',
            }
        ],
        'authoring_mode': 'id03_pipeline_ready_20260702',
        'quality_status': 'pipeline_ready_candidate',
    })

    style_classes = [
        style_class('style_header_date', 22, align='center', opacity=0.86, baseline_shift=-2),
        style_class('style_header_suffix', 20, align='center', opacity=0.88, baseline_shift=-2),
        style_class('style_table_name', 23, align='center', opacity=0.88, letter_spacing=2.2, baseline_shift=-2),
        style_class('style_table_number', 21, align='right', opacity=0.88, baseline_shift=-3),
        style_class('style_table_note', 16, align='center', opacity=0.86),
        style_class('style_summary_number', 22, align='center', opacity=0.86, baseline_shift=-7),
        style_class('style_footer_date', 24, align='center', opacity=0.86),
        style_class('style_footer_company', 23, align='left', opacity=0.88),
        style_class('style_footer_address', 22, align='left', opacity=0.88),
        style_class('style_footer_rep', 23, align='left', opacity=0.88, letter_spacing=1.5),
    ]
    stylesheet.update({
        'updated_at': NOW,
        'style_classes': style_classes,
        'notes': '2026-07-02 ID-03 고품질 보정. 표 grid 기준 bbox 확장, Apple SD Gothic Neo로 회귀하고 crop 수치 비교 없이 전체 이미지/overlay 기준으로 font-size/opacity/정렬을 조정.',
    })

    profiles = make_profiles()
    field_generators = {f['field_id']: f['generator'] for f in fields}
    targets = {f['field_id']: f['generator'].split('.', 1)[1] for f in fields if f['generator'].startswith('pool_record:id03_registry_profiles.')}
    # The existing authoring engine does not natively generate pool_record; use pick_record constraint after placeholder generation.
    for fid in list(field_generators):
        if field_generators[fid].startswith('pool_record:'):
            field_generators[fid] = 'literal:'
    faker.update({
        'updated_at': NOW,
        'field_generators': field_generators,
        'constraints': [{'type': 'pick_record', 'pool': 'id03_registry_profiles', 'targets': targets}],
        'data_pools': {'id03_registry_profiles': profiles},
        'notes': '2026-07-02 ID-03 생산용 faker profile. 1~5명 주주를 선택하고 나머지 표 행은 빈 값으로 유지하되 모든 bbox/key는 고정 제공.',
    })

    write_json(SCHEMA_PATH, schema)
    write_json(STYLE_PATH, stylesheet)
    write_json(FAKER_PATH, faker)
    write_json(SEMANTIC_SCHEMA_PATH, semantic_schema(fields))

    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix='id03', clean=True)
    update_manifest_artifact('ID-03', 'authoring', SCHEMA_PATH)
    update_manifest_artifact('ID-03', 'authoring_stylesheet', STYLE_PATH)
    update_manifest_artifact('ID-03', 'authoring_faker_profile', FAKER_PATH)
    update_manifest_artifact('ID-03', 'authoring_preview', preview.image)
    update_manifest_artifact('ID-03', 'authoring_overlay', preview.overlay)
    update_manifest_artifact('ID-03', 'authoring_batch', batch.summary)

    PROGRESS.write_text(f'''# 2026-07-02 ID-03 주주명부 파이프라인 완성 작업

## 목표
- `ID-03 주주명부`를 첫 번째 완전 생산 가능 문서로 만든다.
- 원본 샘플은 1명 주주만 기입되어 있으나, 문서 포맷은 9행 표 구조이므로 빈 행/열까지 bbox와 key를 확장한다.
- 최종 목표는 원본과 거의 같은 시각 품질로 무한 배치 생성 가능한 상태다.

## 이번 반영
- 상단 기준일 + `현재` 접미어 bbox 유지/보정.
- 주주 표 9행 x 6열 전체를 명시 field로 확장.
  - 열: 주주명, 소유주식수, 회의출석, 의결찬성, 인증촉탁, 비고.
  - 원본에 값이 없는 행도 KIE 가능성을 위해 고정 key/bbox 제공.
- 하단 합계 영역에 출석/찬성/인증촉탁 합계 bbox 추가.
- 회사명/소재지/대표이사/작성일 bbox 폭과 정렬 보정.
- faker profile은 하나의 registry record를 선택하여 회사/주주/합계가 서로 맞도록 구성.
- style은 `font-family`, `font-size`, `font-weight`, `text-align`을 bbox별 style_class에 명시.
- 원본/렌더 전체 비교와 50% overlay 비교를 통해 스타일을 재보정.
  - 렌더러에 stylesheet의 `opacity`, `letter_spacing` 반영 기능을 추가.
  - font-family를 최초 후보였던 Apple SD Gothic Neo로 회귀.
  - crop 비교/수치 최적화는 제외하고, 전체 문서의 스캔 농도와 overlay 기준으로 font-size/opacity/대표자명 자간을 재보정.
  - 작성일/기준일/대표자명은 원본과 같은 표시 공백을 갖도록 faker 값을 조정.

## 산출물
- schema: `{SCHEMA_PATH}`
- stylesheet: `{STYLE_PATH}`
- faker_profile: `{FAKER_PATH}`
- semantic_schema: `{SEMANTIC_SCHEMA_PATH}`
- preview: `{preview.image}`
- overlay: `{preview.overlay}`
- validation: `{preview.validation_report}`
- batch summary: `{batch.summary}`
- batch out_dir: `{BATCH_DIR}`
- contact sheet: `{BATCH_DIR / 'contact_sheet.jpg'}`
- style calibration full comparison: `{ROOT / 'outputs' / 'style_calibration' / 'ID-03_주주명부' / 'full_comparison.jpg'}`
- style calibration overlay: `{ROOT / 'outputs' / 'style_calibration' / 'ID-03_주주명부' / 'full_overlay_50.png'}`

## 자체 검수 포인트
- 표 내부 텍스트는 grid 중심/우측 정렬을 유지한다.
- 1~5명 주주 케이스를 생성하고 남은 행은 공란으로 둔다.
- 총주식수/출석주식수/의결찬성주식수/인증촉탁주식수/1주당 금액은 같은 record에서 주입되어 관계가 유지된다.
- crop 비교는 이후 보정 루틴에서 제외한다.
- 현재 후보는 전체 문서 축소/확대와 50% overlay 기준으로 원본 스캔 농도와 가장 무난하게 맞는 Apple SD Gothic Neo 계열 스타일이다.
''', encoding='utf-8')

    print('preview', preview.image)
    print('overlay', preview.overlay)
    print('warnings', preview.warning_count)
    print('batch', batch.summary, 'samples', batch.sample_count, 'warnings', batch.warning_count)


if __name__ == '__main__':
    main()
