#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from datafactory.authoring import render_authoring_preview
from datafactory.workbench import update_manifest_artifact
from datafactory.authoring_backup import backup_authoring_json_before_write

DOC_ID = 'SEC-03'
DOC_TITLE = '투자성향·적합성 설문'
DOC_DIR = ROOT / 'workbench' / 'documents' / '투자성향·적합성_설문__SEC-03'
AUTHORING = DOC_DIR / 'authoring'
PAGE1_DIR = AUTHORING / 'page_001'
PAGE2_DIR = AUTHORING / 'page_002'
OUT_DIR = AUTHORING / 'render_preview'
BATCH_DIR = ROOT / 'outputs' / 'pipeline_ready' / 'SEC-03_투자성향·적합성 설문'
CALIB_DIR = ROOT / 'outputs' / 'style_calibration' / 'SEC-03_투자성향·적합성 설문'
SEMANTIC_SCHEMA = AUTHORING / 'semantic_schema.json'
PROGRESS = ROOT / 'docs/reports/pipeline_ready/20260702_sec03_investment_suitability_pipeline_readiness.md'
ORIGINAL_1 = DOC_DIR / 'samples' / 'original' / '투자성향적합성설문_page_001.jpg'
ORIGINAL_2 = DOC_DIR / 'samples' / 'original' / '투자성향적합성설문_page_002.jpg'
REVIEW_1 = DOC_DIR / 'review' / 'original_투자성향적합성설문_page_001' / 'review.json'
FONT_APPLE = Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')
FONT_FALLBACK = ROOT / 'fonts' / 'malgun.ttf'
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = 'AppleSDGothicNeo' if FONT_APPLE.exists() else 'default_korean'
NOW = datetime.now(timezone.utc).isoformat()
CHECK = '✓'

# Approximate checkbox center positions measured from the 1191x1684 source images.
COMMON_BOXES = {
    'solicitation_wanted': [389, 262, 18, 18],
    'solicitation_not_wanted': [941, 262, 18, 18],
    'new_registration': [389, 299, 18, 18],
    'info_change': [632, 299, 18, 18],
    'same_as_existing': [943, 299, 18, 18],
    'period_lt_6m': [378, 367, 17, 17],
    'period_6m_1y': [526, 367, 17, 17],
    'period_1y_2y': [690, 367, 17, 17],
    'period_2y_3y': [861, 367, 17, 17],
    'period_gt_3y': [1027, 367, 17, 17],
    'product_stable': [378, 400, 17, 17],
    'product_conservative': [378, 427, 17, 17],
    'product_balanced': [378, 453, 17, 17],
    'product_growth': [378, 479, 17, 17],
    'product_aggressive': [378, 504, 17, 17],
    'knowledge_very_low': [378, 531, 17, 17],
    'knowledge_low': [378, 556, 17, 17],
    'knowledge_high': [378, 581, 17, 17],
    'knowledge_very_high': [378, 607, 17, 17],
    'portfolio_lt_10': [378, 636, 17, 17],
    'portfolio_10_20': [624, 636, 17, 17],
    'portfolio_20_30': [378, 661, 17, 17],
    'portfolio_30_40': [624, 661, 17, 17],
    'portfolio_gt_40': [878, 661, 17, 17],
    'loss_principal': [378, 762, 17, 17],
    'loss_10': [568, 762, 17, 17],
    'loss_20': [378, 788, 17, 17],
    'loss_any': [568, 788, 17, 17],
    'type_stable': [378, 819, 17, 17],
    'type_conservative': [378, 843, 17, 17],
    'type_balanced': [378, 916, 17, 17],
    'type_growth': [378, 960, 17, 17],
    'type_aggressive': [378, 1009, 17, 17],
    'derivative_none': [653, 1085, 17, 17],
    'derivative_lt_1y': [739, 1085, 17, 17],
    'derivative_1_3y': [852, 1085, 17, 17],
    'derivative_gt_3y': [989, 1085, 17, 17],
    'agreement_no': [101, 1128, 17, 17],
    'agreement_yes': [224, 1128, 17, 17],
    'existing_info_same': [379, 1390, 18, 18],
}
PAGE1_BOXES = {
    'age_lt_19': [378, 332, 17, 17],
    'age_20_40': [490, 332, 17, 17],
    'age_41_50': [603, 332, 17, 17],
    'age_51_60': [724, 332, 17, 17],
    'age_gt_61': [843, 332, 17, 17],
    'income_stable': [378, 686, 17, 17],
    'income_decrease': [378, 711, 17, 17],
    'income_none': [378, 737, 17, 17],
}
PAGE2_BOXES = {
    'capital_gt_20b': [378, 332, 17, 17],
    'capital_10_20b': [490, 332, 17, 17],
    'capital_5_10b': [690, 332, 17, 17],
    'capital_1_5b': [884, 332, 17, 17],
    'capital_lt_1b': [1058, 332, 17, 17],
    'loss_record_0_1': [378, 686, 17, 17],
    'loss_record_2_3': [378, 711, 17, 17],
    'loss_record_gt_3': [378, 737, 17, 17],
}

TEXT_FIELDS_PAGE1 = {
    'identity_number': [31, 1338, 530, 24],
    'confirmation_date': [625, 1338, 250, 24],
    'customer_name': [887, 1338, 282, 24],
    'reconfirm_date': [625, 1425, 250, 24],
    'reconfirm_name': [887, 1425, 282, 24],
    'proxy_name': [30, 1524, 280, 24],
    'proxy_rrn': [313, 1524, 310, 24],
    'proxy_phone': [626, 1524, 303, 24],
    'proxy_relation': [934, 1524, 230, 24],
    'delegator_name': [651, 1564, 230, 24],
    'receiver_name': [30, 1620, 420, 24],
    'receiver_time': [456, 1620, 382, 24],
    'customer_phone': [844, 1620, 320, 24],
}
TEXT_FIELDS_PAGE2 = {
    'company_reg_no': [31, 1338, 530, 24],
    'confirmation_date': [625, 1338, 250, 24],
    'customer_name': [887, 1338, 282, 24],
    'reconfirm_date': [625, 1425, 250, 24],
    'reconfirm_name': [887, 1425, 282, 24],
    'proxy_name': [30, 1524, 280, 24],
    'proxy_rrn': [313, 1524, 310, 24],
    'proxy_phone': [626, 1524, 303, 24],
    'proxy_relation': [934, 1524, 230, 24],
    'delegator_name': [651, 1564, 230, 24],
    'receiver_name': [30, 1620, 420, 24],
    'receiver_time': [456, 1620, 382, 24],
    'customer_phone': [844, 1620, 320, 24],
}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def field(field_id: str, label: str, bbox: list[int], style_class: str, *, generator: str, value_type: str = 'free_text.short', align: str = 'left', valign: str = 'middle', json_path: str | None = None, notes: str = '') -> dict[str, Any]:
    return {
        'field_id': field_id,
        'label': label,
        'bbox': bbox,
        'bbox_format': 'xywh',
        'source_detection_id': 'manual_sec03_checkbox_form_20260702',
        'source_text': '',
        'value_type': value_type,
        'generator': generator,
        'style_class': style_class,
        'render_policy': {'align': align, 'valign': valign, 'fit': 'shrink_to_fit', 'overflow': 'shrink'},
        'export': {'json_path': json_path or field_id.replace('_', '.'), 'csv_column': field_id},
        'required': False,
        'notes': notes or '2026-07-02 SEC-03 blank checkbox form 기반 수동 bbox/style 보정 필드',
    }


def style_class(style_id: str, size: int, *, align='left', valign='middle', opacity=0.92, color=None, weight='normal') -> dict[str, Any]:
    return {
        'style_class': style_id,
        'font_family': FONT_FAMILY,
        'font_path': FONT,
        'font_size': size,
        'font_weight': weight,
        'fill': color or [18, 18, 18],
        'opacity': opacity,
        'align': align,
        'valign': valign,
        'line_spacing': 1.0,
        'letter_spacing': 0.0,
        'baseline_shift': 0,
        'overflow': 'shrink',
        'confidence': 0.72,
        'source_detection_ids': ['manual_sec03_checkbox_form_20260702'],
    }


def fields_for_page(page: int) -> list[dict[str, Any]]:
    boxes = dict(COMMON_BOXES)
    boxes.update(PAGE1_BOXES if page == 1 else PAGE2_BOXES)
    fields: list[dict[str, Any]] = []
    for key, bbox in boxes.items():
        fields.append(field(f'p{page}_{key}', f'페이지 {page} 체크 {key}', bbox, 'style_check', generator=f'pool_record:sec03_profiles.p{page}_{key}', align='center', json_path=f'page{page}.checkboxes.{key}', notes='선택된 항목은 ■, 미선택 항목은 공란으로 렌더링'))
    text_fields = TEXT_FIELDS_PAGE1 if page == 1 else TEXT_FIELDS_PAGE2
    labels = {
        'identity_number': '실명번호', 'company_reg_no': '사업자등록번호', 'confirmation_date': '확인 날짜', 'customer_name': '고객성명', 'reconfirm_date': '기존정보 동일 확인 날짜', 'reconfirm_name': '기존정보 동일 고객성명',
        'proxy_name': '대리인성명', 'proxy_rrn': '대리인 주민등록번호', 'proxy_phone': '대리인 전화번호', 'proxy_relation': '본인과의 관계', 'delegator_name': '위임자명', 'receiver_name': '유선접수자', 'receiver_time': '유선접수시간', 'customer_phone': '고객전화번호'
    }
    value_types = {'identity_number': 'person.rrn', 'company_reg_no': 'free_text.short', 'confirmation_date': 'date.kr', 'reconfirm_date': 'date.kr', 'customer_phone': 'person.phone_kr', 'proxy_phone': 'person.phone_kr'}
    for key, bbox in text_fields.items():
        style = 'style_date' if 'date' in key else ('style_text_small' if key in {'proxy_rrn','proxy_phone','delegator_name','receiver_time','customer_phone'} else 'style_text')
        fields.append(field(f'p{page}_{key}', labels.get(key, key), bbox, style, generator=f'pool_record:sec03_profiles.p{page}_{key}', value_type=value_types.get(key, 'free_text.short'), json_path=f'page{page}.fields.{key}'))
    return fields


def build_schema(page: int, image_path: Path, schema_path: Path) -> dict[str, Any]:
    return {
        'schema_version': 1,
        'created_at': NOW,
        'updated_at': NOW,
        'doc_id': DOC_ID,
        'title': f'{DOC_TITLE} page {page}',
        'page_index': page,
        'source_review': str(REVIEW_1.resolve()) if page == 1 and REVIEW_1.exists() else '',
        'source_image': str(image_path.resolve()),
        'source_inpainted': str(image_path.resolve()),
        'image': {'width': 1191, 'height': 1684},
        'fields': fields_for_page(page),
        'groups': [
            {'group_id': 'survey_checkboxes', 'type': 'checkbox_survey', 'notes': f'SEC-03 page {page} 선택식 설문 체크박스 묶음'},
            {'group_id': 'signature_and_proxy', 'type': 'signature_section', 'notes': f'SEC-03 page {page} 하단 실명확인/위임장/유선접수 필드'},
        ],
        'authoring_mode': f'sec03_page_{page}_pipeline_ready_20260702',
        'quality_status': 'pipeline_ready_candidate',
    }


def build_stylesheet() -> dict[str, Any]:
    return {
        'schema_version': 1,
        'created_at': NOW,
        'updated_at': NOW,
        'doc_id': DOC_ID,
        'style_classes': [
            style_class('style_check', 14, align='center', opacity=0.92, color=[5, 5, 5]),
            style_class('style_text', 18, opacity=0.88),
            style_class('style_text_small', 15, opacity=0.88),
            style_class('style_date', 17, align='center', opacity=0.88),
        ],
        'notes': '2026-07-02 SEC-03 투자성향·적합성 설문 생산용 스타일. blank form이라 실제 기입값 폰트 추출은 불가능하며, 전체 렌더/overlay 기준으로 Apple SD Gothic Neo 계열의 낮은 농도 텍스트와 작은 선택 표시를 사용함. crop 비교는 사용하지 않음.',
    }


def selected(record: dict[str, str], page: int, keys: list[str], chosen: str) -> None:
    for key in keys:
        record[f'p{page}_{key}'] = CHECK if key == chosen else ''


def selected_many(record: dict[str, str], page: int, keys: list[str], chosen_keys: list[str]) -> None:
    chosen = set(chosen_keys)
    for key in keys:
        record[f'p{page}_{key}'] = CHECK if key in chosen else ''


def fill_common_choices(record: dict[str, str], page: int, rng: random.Random, profile_idx: int, *, corporate: bool) -> None:
    selected(record, page, ['solicitation_wanted','solicitation_not_wanted'], 'solicitation_wanted')
    selected(record, page, ['new_registration','info_change','same_as_existing'], ['new_registration','info_change','same_as_existing'][profile_idx % 3])
    selected(record, page, ['period_lt_6m','period_6m_1y','period_1y_2y','period_2y_3y','period_gt_3y'], ['period_6m_1y','period_1y_2y','period_2y_3y','period_gt_3y'][profile_idx % 4])
    product_choices = ['product_stable','product_conservative','product_balanced','product_growth','product_aggressive']
    selected_many(record, page, product_choices, rng.sample(product_choices, 2 if profile_idx % 3 == 0 else 1))
    selected(record, page, ['knowledge_very_low','knowledge_low','knowledge_high','knowledge_very_high'], ['knowledge_low','knowledge_high','knowledge_very_high'][profile_idx % 3])
    selected(record, page, ['portfolio_lt_10','portfolio_10_20','portfolio_20_30','portfolio_30_40','portfolio_gt_40'], ['portfolio_lt_10','portfolio_10_20','portfolio_20_30','portfolio_gt_40'][profile_idx % 4])
    selected(record, page, ['loss_principal','loss_10','loss_20','loss_any'], ['loss_principal','loss_10','loss_20','loss_any'][profile_idx % 4])
    selected(record, page, ['type_stable','type_conservative','type_balanced','type_growth','type_aggressive'], ['type_stable','type_conservative','type_balanced','type_growth','type_aggressive'][profile_idx % 5])
    selected(record, page, ['derivative_none','derivative_lt_1y','derivative_1_3y','derivative_gt_3y'], ['derivative_none','derivative_lt_1y','derivative_1_3y','derivative_gt_3y'][profile_idx % 4])
    selected(record, page, ['agreement_no','agreement_yes'], 'agreement_yes')
    record[f'p{page}_existing_info_same'] = CHECK if profile_idx % 2 == 0 else ''
    if corporate:
        selected(record, page, ['capital_gt_20b','capital_10_20b','capital_5_10b','capital_1_5b','capital_lt_1b'], ['capital_gt_20b','capital_10_20b','capital_5_10b','capital_1_5b','capital_lt_1b'][profile_idx % 5])
        selected(record, page, ['loss_record_0_1','loss_record_2_3','loss_record_gt_3'], ['loss_record_0_1','loss_record_2_3','loss_record_gt_3'][profile_idx % 3])
    else:
        selected(record, page, ['age_lt_19','age_20_40','age_41_50','age_51_60','age_gt_61'], ['age_20_40','age_41_50','age_51_60','age_gt_61'][profile_idx % 4])
        selected(record, page, ['income_stable','income_decrease','income_none'], ['income_stable','income_decrease','income_none'][profile_idx % 3])


def make_profiles() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    names = ['김민준','이서연','박도윤','최하은','정시우','강서윤','조현우','윤지호']
    companies = ['한빛정밀 주식회사','새론모빌리티 주식회사','대한소재 주식회사','미래식품 주식회사','세종바이오 주식회사','누리패키징 주식회사']
    proxies = ['오지민','한유진','문하린','임서준','권도윤','장민재']
    relations = ['배우자','자녀','임직원','재무담당자','법정대리인']
    profiles: list[dict[str, str]] = []
    all_checkbox_keys = set(COMMON_BOXES) | set(PAGE1_BOXES) | set(PAGE2_BOXES)
    for idx in range(8):
        record: dict[str, str] = {}
        for page in (1, 2):
            for key in all_checkbox_keys:
                record[f'p{page}_{key}'] = ''
        fill_common_choices(record, 1, rng, idx, corporate=False)
        fill_common_choices(record, 2, rng, idx + 1, corporate=True)
        # All generated document dates are fixed before the 2026-07-02 project date.
        date = f'2026                  6                    {2 + idx * 2}'
        reconfirm = f'2026                  6                    {9 + idx * 2}'
        person = names[idx % len(names)]
        company = companies[idx % len(companies)]
        proxy = proxies[idx % len(proxies)]
        phone = f'010-{rng.randint(2000,9999)}-{rng.randint(1000,9999)}'
        proxy_phone = f'010-{rng.randint(2000,9999)}-{rng.randint(1000,9999)}'
        receiver = names[(idx + 3) % len(names)]
        time = f'{9 + idx % 7:02d}:{["10","20","30","40","50"][idx % 5]}'
        record.update({
            'p1_identity_number': f'{rng.randint(700101,991231)}-{rng.randint(1,4)}{rng.randint(100000,999999)}',
            'p1_confirmation_date': date,
            'p1_customer_name': person,
            'p1_reconfirm_date': reconfirm,
            'p1_reconfirm_name': person,
            'p1_proxy_name': proxy,
            'p1_proxy_rrn': f'{rng.randint(700101,991231)}-{rng.randint(1,4)}{rng.randint(100000,999999)}',
            'p1_proxy_phone': proxy_phone,
            'p1_proxy_relation': relations[idx % len(relations)],
            'p1_delegator_name': person,
            'p1_receiver_name': receiver,
            'p1_receiver_time': time,
            'p1_customer_phone': phone,
            'p2_company_reg_no': f'{rng.randint(100,999)}-{rng.randint(10,99)}-{rng.randint(10000,99999)}',
            'p2_confirmation_date': date,
            'p2_customer_name': company,
            'p2_reconfirm_date': reconfirm,
            'p2_reconfirm_name': company,
            'p2_proxy_name': proxy,
            'p2_proxy_rrn': f'{rng.randint(700101,991231)}-{rng.randint(1,4)}{rng.randint(100000,999999)}',
            'p2_proxy_phone': proxy_phone,
            'p2_proxy_relation': relations[(idx + 2) % len(relations)],
            'p2_delegator_name': company,
            'p2_receiver_name': receiver,
            'p2_receiver_time': time,
            'p2_customer_phone': phone,
        })
        profiles.append(record)
    return profiles



def build_semantic_schema(schema_paths: list[Path]) -> dict[str, Any]:
    field_mapping: dict[str, str] = {}
    for path in schema_paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        for item in data.get('fields', []):
            field_mapping[item['field_id']] = item.get('export', {}).get('json_path', item['field_id'])

    common_choices = {
        '투자권유 희망여부': {'희망': '', '불원': ''},
        '작성 구분': {'신규등록': '', '정보변경': '', '기존정보와 동일': ''},
        '투자가능 기간': {'6개월미만': '', '6개월이상~1년미만': '', '1년이상~2년미만': '', '2년이상~3년미만': '', '3년이상': ''},
        '선호 금융투자상품': {
            '안정형상품': '',
            '안정추구형상품': '',
            '위험중립형상품': '',
            '적극투자형상품': '',
            '공격형상품': '',
        },
        '투자지식 수준': {'매우낮음': '', '낮음': '', '높음': '', '매우높음': ''},
        '금융자산 비중': {'10% 미만': '', '10~20%': '', '20~30%': '', '30~40%': '', '40% 이상': ''},
        '손실 감내도': {'원금보전': '', '10% 이내 손실감수': '', '20% 미만 손실감수': '', '고위험 감수': ''},
        '투자성향': {'안정형': '', '안정추구형': '', '위험중립형': '', '적극투자형': '', '공격투자형': ''},
        '파생상품 투자경험 및 기간': {'없음': '', '1년미만': '', '1~3년미만': '', '3년이상': ''},
        '지분증권 투자자 약식확인': {'동의하지 않음': '', '동의함': ''},
        '기존 정보와 동일 확인': '',
    }
    signature_block = {
        '실명확인': {'실명번호 또는 사업자등록번호': '', '확인일자': '', '고객명': ''},
        '기존정보 동일 재확인': {'확인일자': '', '고객명': ''},
        '위임장': {'대리인성명': '', '대리인 식별번호': '', '대리인 전화번호': '', '본인과의 관계': '', '위임자명': ''},
        '유선접수': {'접수자': '', '접수시간': '', '고객전화번호': ''},
    }
    return {
        'schema_version': 1,
        'created_at': NOW,
        'updated_at': NOW,
        'doc_id': DOC_ID,
        'title': DOC_TITLE,
        'purpose': '렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조',
        'semantic_schema': {
            '투자성향·적합성 설문': {
                '개인용 정보 확인서': {
                    '공통 설문': common_choices,
                    '개인 투자자 문항': {
                        '연령대': {'19세이하': '', '20~40세': '', '41~50세': '', '51~60세': '', '61세이상': ''},
                        '수입원': {'현재 수입 안정': '', '향후 감소 또는 불안정': '', '현재 수입 없음': ''},
                    },
                    '확인 및 위임': signature_block,
                },
                '법인용 정보 확인서': {
                    '공통 설문': common_choices,
                    '법인 투자자 문항': {
                        '자본금 규모': {'200억이상': '', '100억이상~200억미만': '', '50억이상~100억미만': '', '10억이상~50억미만': '', '10억미만': ''},
                        '투자손실 기록': {'최근 5년간 1건 이하': '', '최근 5년간 2~3건': '', '최근 5년간 3건 초과': ''},
                    },
                    '확인 및 위임': signature_block,
                },
            }
        },
        'field_mapping': field_mapping,
        'notes': [
            'page_001/page_002 schema는 렌더러 호환을 위해 bbox/style/generator 정보를 유지한다.',
            'semantic_schema.json은 KIE용 key-name 계층만 별도 관리한다.',
            '원본은 blank checkbox form이므로 checkbox key도 수동 bbox와 의미 schema에 명시적으로 포함한다.',
        ],
    }

def build_faker_profile(fields: list[dict[str, Any]]) -> dict[str, Any]:
    gens = {f['field_id']: f['generator'] for f in fields}
    targets = {f['field_id']: f['generator'].split('.', 1)[1] for f in fields if str(f['generator']).startswith('pool_record:sec03_profiles.')}
    for fid, rule in list(gens.items()):
        if str(rule).startswith('pool_record:'):
            gens[fid] = 'literal:'
    return {
        'schema_version': 1,
        'created_at': NOW,
        'updated_at': NOW,
        'doc_id': DOC_ID,
        'locale': 'ko_KR',
        'field_generators': gens,
        'constraints': [{'type': 'pick_record', 'pool': 'sec03_profiles', 'targets': targets}],
        'data_pools': {'sec03_profiles': make_profiles()},
        'notes': 'SEC-03 2페이지 투자성향 설문 faker profile. 동일 seed로 page1/page2를 렌더하여 같은 record를 선택하고, 체크박스는 선택 시 ✓, 미선택 시 공란으로 렌더링함.',
    }


def fit_same_size(a: Image.Image, b: Image.Image) -> tuple[Image.Image, Image.Image]:
    a = a.convert('RGB')
    b = b.convert('RGB')
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.BICUBIC)
    return a, b


def make_full_comparison(page: int, original: Path, rendered: Path) -> Path:
    out_dir = CALIB_DIR / f'page_{page:03d}'
    out_dir.mkdir(parents=True, exist_ok=True)
    orig, rend = fit_same_size(Image.open(original), Image.open(rendered))
    diff = ImageChops.difference(orig, rend)
    diff_amp = diff.point(lambda v: min(255, v * 4))
    blend = Image.blend(orig, rend, 0.5)
    labels = [('original blank', orig), ('render', rend), ('amplified diff', diff_amp), ('50% overlay', blend)]
    scale_w = 420
    thumbs=[]
    for label, im in labels:
        t=im.copy(); t.thumbnail((scale_w, 610)); thumbs.append((label,t))
    font=ImageFont.truetype(str(FONT_FALLBACK),20) if FONT_FALLBACK.exists() else ImageFont.load_default()
    sheet=Image.new('RGB',(scale_w*len(thumbs)+20*(len(thumbs)+1),690),(245,245,242))
    d=ImageDraw.Draw(sheet)
    for i,(label,t) in enumerate(thumbs):
        x=20+i*(scale_w+20); d.text((x,18),label,font=font,fill=(20,20,20)); sheet.paste(t,(x,54)); d.rectangle([x,54,x+t.width,54+t.height],outline=(150,150,150))
    out = out_dir / 'full_comparison.jpg'
    sheet.save(out, quality=92)
    diff.save(out_dir / 'full_diff.png')
    blend.save(out_dir / 'full_overlay_50.png')
    return out


def make_contact_sheet(pairs: list[tuple[Path, Path]]) -> Path:
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    font=ImageFont.truetype(str(FONT_FALLBACK),18) if FONT_FALLBACK.exists() else ImageFont.load_default()
    cell_w, cell_h = 310, 455
    sheet=Image.new('RGB',(len(pairs)*cell_w + 20, cell_h*2 + 64),(246,246,243))
    d=ImageDraw.Draw(sheet)
    for idx,(p1,p2) in enumerate(pairs):
        x=20+idx*cell_w
        d.text((x,16),f'sec03_{idx+1:06d}',font=font,fill=(25,25,25))
        for row,path in enumerate([p1,p2]):
            im=Image.open(path).convert('RGB'); im.thumbnail((cell_w-20, cell_h-45))
            y=48+row*cell_h
            d.text((x,y-22),f'page {row+1}',font=font,fill=(70,70,70))
            sheet.paste(im,(x,y)); d.rectangle([x,y,x+im.width,y+im.height],outline=(155,155,155))
    out=BATCH_DIR / 'contact_sheet.jpg'
    sheet.save(out, quality=92)
    return out


def render_batch(schema1: Path, schema2: Path, stylesheet: Path, faker: Path, *, count: int = 5) -> dict[str, Any]:
    if BATCH_DIR.exists():
        for path in BATCH_DIR.glob('sec03_*'):
            if path.is_file():
                path.unlink()
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    samples=[]
    pairs=[]
    warning_count=0
    field_count=0
    for i in range(1, count+1):
        seed = 20260702 + i - 1
        sid=f'sec03_{i:06d}'
        r1=render_authoring_preview(schema1, stylesheet, faker, out_dir=BATCH_DIR, seed=seed, sample_id=f'{sid}_page_001')
        r2=render_authoring_preview(schema2, stylesheet, faker, out_dir=BATCH_DIR, seed=seed, sample_id=f'{sid}_page_002')
        pairs.append((r1.image, r2.image))
        warning_count += r1.warning_count + r2.warning_count
        field_count = r1.field_count + r2.field_count
        samples.append({
            'sample_id': sid,
            'pages': [
                {'page': 1, 'image': str(r1.image), 'kv': str(r1.kv), 'bbox': str(r1.bbox), 'overlay': str(r1.overlay), 'validation_report': str(r1.validation_report), 'warning_count': r1.warning_count},
                {'page': 2, 'image': str(r2.image), 'kv': str(r2.kv), 'bbox': str(r2.bbox), 'overlay': str(r2.overlay), 'validation_report': str(r2.validation_report), 'warning_count': r2.warning_count},
            ],
        })
    contact = make_contact_sheet(pairs)
    summary={
        'schema_version': 1,
        'created_at': NOW,
        'doc_id': DOC_ID,
        'title': DOC_TITLE,
        'schemas': {'page_001': str(schema1), 'page_002': str(schema2)},
        'stylesheet': str(stylesheet),
        'faker_profile': str(faker),
        'out_dir': str(BATCH_DIR),
        'count': count,
        'page_count': 2,
        'field_count_per_sample': field_count,
        'warning_count': warning_count,
        'contact_sheet': str(contact),
        'samples': samples,
    }
    write_json(BATCH_DIR / 'summary.json', summary)
    return summary


def write_progress(summary: dict[str, Any], comparison1: Path, comparison2: Path) -> None:
    PROGRESS.write_text(f'''# 2026-07-02 SEC-03 투자성향·적합성 설문 파이프라인 준비 작업

## 목표
- `SEC-03 투자성향·적합성 설문`을 이번 순차 처리 대상으로 진행한다.
- 이 문서는 개인용/법인용 2페이지 blank checkbox form이므로, 인페인팅 대상 값이 아니라 체크박스/하단 기입란을 직접 schema화한다.
- 주주명부 방식과 동일하게 문서별 별도 작업 기록을 남기고, crop 비교 없이 전체 렌더/overlay 기준으로 font-family와 스타일을 선택한다.

## 입력 상태
- page 1 원본: `{ORIGINAL_1}`
- page 2 원본: `{ORIGINAL_2}`
- page 1 review: `{REVIEW_1}`
- review에는 `use` bbox가 없으므로 인페인팅은 생략하고 원본 blank form을 `source_inpainted`로 사용했다.

## 구조화 결정
- page 1은 `일반투자자 정보 확인서(개인용)`, page 2는 `일반투자자 정보 확인서(법인용)`으로 분리했다.
- 각 페이지별 렌더링 schema는 별도 파일로 유지하고, KIE용 key-name 계층은 `semantic_schema.json`으로 분리했다.
- batch 생성 시 같은 seed를 사용해 동일 faker record가 선택되도록 했다.
- 체크박스는 선택 시 작은 `✓`, 미선택 시 공란으로 렌더링한다.
- 하단 실명번호/날짜/고객성명/위임장/유선접수 필드는 텍스트 필드로 렌더링한다.
- 원본이 blank form이라 실제 기입값 font를 추출할 수 없으므로, 양식과 가장 충돌이 적은 Apple SD Gothic Neo 계열 저농도 텍스트를 선택했다.

## 산출물
- page 1 schema: `{PAGE1_DIR / 'schema.json'}`
- page 2 schema: `{PAGE2_DIR / 'schema.json'}`
- stylesheet: `{AUTHORING / 'stylesheet.json'}`
- faker_profile: `{AUTHORING / 'faker_profile.json'}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
- batch summary: `{BATCH_DIR / 'summary.json'}`
- batch output dir: `{BATCH_DIR}`
- contact sheet: `{BATCH_DIR / 'contact_sheet.jpg'}`
- page 1 comparison: `{comparison1}`
- page 2 comparison: `{comparison2}`
- preview page 1: `{OUT_DIR / 'preview_page_001.png'}`
- preview page 2: `{OUT_DIR / 'preview_page_002.png'}`

## 검수 결과 및 남은 리스크
- 생성 세트 수: {summary['count']}세트 x {summary['page_count']}페이지
- field 수/page sample 합계: {summary['field_count_per_sample']}
- 렌더 경고 수: {summary['warning_count']}
- 현재 체크박스 위치는 원본 전체 이미지 기준 수동 측정값이다. 추후 사용자가 웹 GUI로 bbox를 더 정밀하게 보정하면 해당 좌표를 schema에 반영하면 된다.
- 선택 표시 `✓`는 실제 수기 체크와 완전히 같지는 않지만, blank form 기반 1-cycle 생산 목적에서는 KIE 선택 영역을 안정적으로 드러내는 방식이다. 실제 수기 체크 샘플이 생기면 표시 glyph/폰트/opacity를 재보정한다.
''', encoding='utf-8')


def main() -> None:
    if not ORIGINAL_1.exists() or not ORIGINAL_2.exists():
        raise FileNotFoundError('SEC-03 source pages are missing')
    AUTHORING.mkdir(parents=True, exist_ok=True)
    if CALIB_DIR.exists():
        shutil.rmtree(CALIB_DIR)
    stylesheet_path = AUTHORING / 'stylesheet.json'
    faker_path = AUTHORING / 'faker_profile.json'
    schema1_path = PAGE1_DIR / 'schema.json'
    schema2_path = PAGE2_DIR / 'schema.json'
    schema1 = build_schema(1, ORIGINAL_1, schema1_path)
    schema2 = build_schema(2, ORIGINAL_2, schema2_path)
    stylesheet = build_stylesheet()
    all_fields = schema1['fields'] + schema2['fields']
    faker = build_faker_profile(all_fields)
    write_json(schema1_path, schema1)
    write_json(schema2_path, schema2)
    # Compatibility copies for current single-preview web UI: page 1 is exposed as the default authoring schema.
    write_json(AUTHORING / 'schema.json', schema1)
    write_json(stylesheet_path, stylesheet)
    write_json(faker_path, faker)
    write_json(SEMANTIC_SCHEMA, build_semantic_schema([schema1_path, schema2_path]))

    p1 = render_authoring_preview(schema1_path, stylesheet_path, faker_path, out_dir=OUT_DIR, seed=20260702, sample_id='preview_page_001')
    p2 = render_authoring_preview(schema2_path, stylesheet_path, faker_path, out_dir=OUT_DIR, seed=20260702, sample_id='preview_page_002')
    summary = render_batch(schema1_path, schema2_path, stylesheet_path, faker_path, count=5)
    comparison1 = make_full_comparison(1, ORIGINAL_1, p1.image)
    comparison2 = make_full_comparison(2, ORIGINAL_2, p2.image)

    update_manifest_artifact(DOC_ID, 'authoring', AUTHORING / 'schema.json')
    update_manifest_artifact(DOC_ID, 'authoring_page_001_schema', schema1_path)
    update_manifest_artifact(DOC_ID, 'authoring_page_002_schema', schema2_path)
    update_manifest_artifact(DOC_ID, 'authoring_stylesheet', stylesheet_path)
    update_manifest_artifact(DOC_ID, 'authoring_faker_profile', faker_path)
    update_manifest_artifact(DOC_ID, 'authoring_semantic_schema', SEMANTIC_SCHEMA)
    update_manifest_artifact(DOC_ID, 'authoring_preview', p1.image)
    update_manifest_artifact(DOC_ID, 'authoring_page_002_preview', p2.image)
    update_manifest_artifact(DOC_ID, 'authoring_overlay', p1.overlay)
    update_manifest_artifact(DOC_ID, 'authoring_batch', BATCH_DIR / 'summary.json')
    update_manifest_artifact(DOC_ID, 'authoring_contact_sheet', BATCH_DIR / 'contact_sheet.jpg')
    update_manifest_artifact(DOC_ID, 'authoring_style_comparison', comparison1)
    update_manifest_artifact(DOC_ID, 'authoring_page_002_style_comparison', comparison2)

    write_progress(summary, comparison1, comparison2)
    print('preview page1', p1.image, 'warnings', p1.warning_count)
    print('preview page2', p2.image, 'warnings', p2.warning_count)
    print('batch', BATCH_DIR / 'summary.json', 'warnings', summary['warning_count'])
    print('contact', BATCH_DIR / 'contact_sheet.jpg')
    print('comparison1', comparison1)
    print('comparison2', comparison2)


if __name__ == '__main__':
    main()
