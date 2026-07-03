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

DOC_ID = 'APP-13'
DOC_TITLE = '계좌개설신청서'
DOC_DIR = ROOT / 'workbench' / 'documents' / '계좌개설신청서__APP-13'
AUTHORING = DOC_DIR / 'authoring'
SCHEMA_PATH = AUTHORING / 'schema.json'
STYLE_PATH = AUTHORING / 'stylesheet.json'
FAKER_PATH = AUTHORING / 'faker_profile.json'
OUT_DIR = AUTHORING / 'render_preview'
BATCH_DIR = ROOT / 'outputs' / 'pipeline_ready' / 'APP-13_계좌개설신청서'
CALIB_DIR = ROOT / 'outputs' / 'style_calibration' / 'APP-13_계좌개설신청서'
SEMANTIC_SCHEMA = AUTHORING / 'semantic_schema.json'
PROGRESS = ROOT / 'docs/reports/pipeline_ready/20260702_app13_account_opening_pipeline_readiness.md'
ORIGINAL = DOC_DIR / 'samples' / 'original' / '계좌개설신청서_page_001.jpg'
REVIEW = DOC_DIR / 'review' / 'original_계좌개설신청서_page_001' / 'review.json'
INPAINTED = DOC_DIR / 'inpaint' / 'original' / 'lama' / 'inpainted_lama.png'
INPAINT_SUMMARY = DOC_DIR / 'inpaint' / 'original' / 'lama' / 'summary.json'
INPAINT_COMPARISON = DOC_DIR / 'inpaint' / 'original' / 'lama' / 'comparison_lama.png'
FONT_APPLE = Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')
FONT_FALLBACK = ROOT / 'fonts' / 'malgun.ttf'
FONT = str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY = 'AppleSDGothicNeo' if FONT_APPLE.exists() else 'default_korean'
NOW = datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def field(field_id: str, label: str, bbox: list[int], style_class: str, *, generator: str, value_type: str = 'free_text.short', align: str = 'left', valign: str = 'middle', json_path: str | None = None, notes: str = '') -> dict:
    return {
        'field_id': field_id,
        'label': label,
        'bbox': bbox,
        'bbox_format': 'xywh',
        'source_detection_id': 'manual_app13_blank_form_20260702',
        'source_text': '',
        'value_type': value_type,
        'generator': generator,
        'style_class': style_class,
        'render_policy': {'align': align, 'valign': valign, 'fit': 'shrink_to_fit', 'overflow': 'shrink'},
        'export': {'json_path': json_path or field_id.replace('_', '.'), 'csv_column': field_id},
        'required': True,
        'notes': notes or '2026-07-02 APP-13 blank form 기반 수동 bbox/style 보정 필드',
    }


def style_class(style_class_id: str, size: int, *, align: str = 'left', valign: str = 'middle', opacity: float = 0.90, weight: str = 'normal', color: list[int] | None = None) -> dict:
    return {
        'style_class': style_class_id,
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
        'confidence': 0.70,
        'source_detection_ids': ['manual_app13_blank_form_20260702'],
    }


def make_profiles() -> list[dict[str, str]]:
    rng = random.Random(20260702)
    companies = [
        ('주식회사 한빛테크놀로지', '서울특별시 강남구 테헤란로 152, 18층', '서울특별시 강남구 테헤란로 152, 18층', '김민준', '박서연'),
        ('새론모빌리티 주식회사', '경기도 성남시 분당구 판교역로 235', '경기도 성남시 분당구 대왕판교로 660', '이도윤', '최하은'),
        ('대한소재 주식회사', '부산광역시 해운대구 센텀중앙로 79', '부산광역시 해운대구 센텀중앙로 79', '정우진', '강서윤'),
        ('미래식품 주식회사', '대전광역시 유성구 테크노중앙로 50', '충청남도 천안시 서북구 직산읍 공단로 21', '조현우', '오지민'),
        ('세종바이오 주식회사', '서울특별시 마포구 월드컵북로 396', '인천광역시 연수구 송도과학로 32', '윤지호', '한유진'),
        ('누리패키징 주식회사', '광주광역시 북구 첨단과기로 123', '광주광역시 북구 첨단벤처로 108', '임서준', '문하린'),
    ]
    account_types = ['보통예금 / KRW', '기업자유예금 / KRW', '외화보통예금 / USD', '정기예금 / KRW']
    profiles: list[dict[str, str]] = []
    for i, (company, legal_addr, biz_addr, rep, attorney) in enumerate(companies):
        date = f'2026-06-{2 + i * 4:02d}'
        existing = f'{rng.randint(100,999)}-{rng.randint(100000,999999)}-{rng.randint(10,99)}'
        rrn = f'{rng.randint(720101,991231)}-{rng.randint(1,4)}{rng.randint(100000,999999)}'
        phone = f'010-{rng.randint(2000,9999)}-{rng.randint(1000,9999)}'
        profiles.append({
            'date': date,
            'company_name': company,
            'existing_account_number': existing,
            'account_name': company,
            'account_type_currency': account_types[i % len(account_types)],
            'legal_address': legal_addr,
            'business_address': biz_addr,
            'signatories': f'{rep} 대표이사, {attorney} 재무담당',
            'attorney_identity': f'{attorney} / {rrn}',
            'attorney_address': biz_addr,
            'attorney_phone': phone,
            'behalf_company': company,
            'authorised_signatory': f'{rep} 대표이사',
        })
    return profiles


def build_schema() -> dict:
    fields = [
        field('application_date', '작성일', [148, 221, 210, 34], 'style_value', generator='pool_record:app13_account_profiles.date', value_type='date.kr', json_path='application.date'),
        field('company_name_inline', '회사이름 본문', [230, 351, 536, 39], 'style_value', generator='pool_record:app13_account_profiles.company_name', value_type='company.name_ko', json_path='company.name'),
        field('existing_account_number', '기존 계좌번호', [230, 390, 275, 38], 'style_value', generator='pool_record:app13_account_profiles.existing_account_number', json_path='account.existing.number'),
        field('account_name', 'Account Name 회사이름', [352, 552, 465, 40], 'style_value', generator='pool_record:app13_account_profiles.account_name', value_type='company.name_ko', json_path='account.name'),
        field('account_type_currency', '계좌 종류 및 통화', [528, 608, 420, 40], 'style_value', generator='pool_record:app13_account_profiles.account_type_currency', json_path='account.type_currency'),
        field('legal_address', '법적 주소', [360, 664, 660, 42], 'style_value_small', generator='pool_record:app13_account_profiles.legal_address', value_type='address.ko', json_path='company.legal_address'),
        field('business_address', '사업장 주소', [415, 720, 630, 42], 'style_value_small', generator='pool_record:app13_account_profiles.business_address', value_type='address.ko', json_path='company.business_address'),
        field('signatories', '수권서명자', [320, 776, 650, 42], 'style_value_small', generator='pool_record:app13_account_profiles.signatories', json_path='signatories.names'),
        field('attorney_identity', '대리인 성명 및 주민등록번호', [490, 1095, 430, 38], 'style_value', generator='pool_record:app13_account_profiles.attorney_identity', json_path='attorney.identity'),
        field('attorney_address', '대리인 주소', [225, 1141, 690, 34], 'style_value_small', generator='pool_record:app13_account_profiles.attorney_address', value_type='address.ko', json_path='attorney.address'),
        field('attorney_phone', '대리인 연락처', [160, 1172, 300, 34], 'style_value', generator='pool_record:app13_account_profiles.attorney_phone', value_type='person.phone_kr', json_path='attorney.phone'),
        field('behalf_company', 'For and on behalf of 회사이름', [390, 1210, 515, 40], 'style_value', generator='pool_record:app13_account_profiles.behalf_company', value_type='company.name_ko', json_path='company.behalf_name'),
        field('authorised_signatory', '명판 및 법인인감 서명자', [720, 1362, 320, 40], 'style_signature', generator='pool_record:app13_account_profiles.authorised_signatory', json_path='signatories.authorised_signatory', align='center'),
    ]
    return {
        'schema_version': 1,
        'created_at': NOW,
        'updated_at': NOW,
        'doc_id': DOC_ID,
        'title': DOC_TITLE,
        'source_review': str(REVIEW.resolve()),
        'source_image': str(ORIGINAL.resolve()),
        'source_inpainted': str((INPAINTED if INPAINTED.exists() else ORIGINAL).resolve()),
        'image': {'width': 1191, 'height': 1684},
        'fields': fields,
        'groups': [
            {'group_id': 'company_account', 'type': 'section', 'columns': ['company_name', 'account_number', 'account_type_currency'], 'notes': '상단 회사/계좌 정보'},
            {'group_id': 'attorney', 'type': 'section', 'columns': ['attorney_identity', 'attorney_address', 'attorney_phone'], 'notes': '대리인 정보'},
        ],
        'authoring_mode': 'app13_pipeline_ready_20260702',
        'quality_status': 'pipeline_ready_candidate',
    }


def build_stylesheet() -> dict:
    return {
        'schema_version': 1,
        'created_at': NOW,
        'updated_at': NOW,
        'doc_id': DOC_ID,
        'source_image': str(ORIGINAL.resolve()),
        'style_classes': [
            style_class('style_value', 20, opacity=0.88),
            style_class('style_value_small', 18, opacity=0.88),
            style_class('style_signature', 20, align='center', opacity=0.86),
        ],
        'notes': '2026-07-02 APP-13 추가계좌 개설 신청서 생산용 스타일. 원본이 미기입 blank form이라 실제 값 폰트 직접 추출은 불가능하며, 정적 양식과 가장 충돌이 적은 Apple SD Gothic Neo 계열의 낮은 농도 출력값을 선택함. crop 비교는 사용하지 않음.',
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
            '계좌개설신청서': {
                '신청정보': {
                    '작성일': '',
                    '기존 계좌번호': '',
                    '추가 계좌명': '',
                    '계좌 종류 및 통화': '',
                },
                '회사정보': {
                    '회사명': '',
                    '법적 주소': '',
                    '사업장 주소': '',
                },
                '수권서명자': [
                    {'성명': '', '직책': ''}
                ],
                '대리인': {
                    '성명 및 주민등록번호': '',
                    '주소': '',
                    '연락처': '',
                },
                '위임회사': {
                    '회사명': '',
                    '명판 및 법인인감 서명자': '',
                },
            }
        },
        'field_mapping': field_mapping,
        'notes': [
            'schema.json은 renderer 호환을 위해 bbox/style/generator/render_policy를 유지한다.',
            'semantic_schema.json은 KIE용 key-name 계층만 별도 관리한다.',
            'blank form 기반이므로 정적 조항/은행명/수신처는 template 배경으로 보존하고 값 주입 필드만 field_mapping에 포함한다.',
        ],
    }


def build_faker_profile(fields: list[dict]) -> dict:
    gens = {f['field_id']: f['generator'] for f in fields}
    targets = {f['field_id']: f['generator'].split('.', 1)[1] for f in fields if str(f['generator']).startswith('pool_record:app13_account_profiles.')}
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
        'constraints': [{'type': 'pick_record', 'pool': 'app13_account_profiles', 'targets': targets}],
        'data_pools': {'app13_account_profiles': make_profiles()},
        'notes': 'APP-13 계좌개설신청서 faker profile. 회사명/주소/대리인/계좌 정보를 하나의 record에서 선택해 정합성을 유지함.',
    }


def fit_same_size(a: Image.Image, b: Image.Image) -> tuple[Image.Image, Image.Image]:
    a = a.convert('RGB')
    b = b.convert('RGB')
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.BICUBIC)
    return a, b


def make_full_comparison(rendered_path: Path) -> None:
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    orig, rend = fit_same_size(Image.open(ORIGINAL), Image.open(rendered_path))
    inp = Image.open(INPAINTED if INPAINTED.exists() else ORIGINAL).convert('RGB').resize(orig.size, Image.Resampling.BICUBIC)
    diff = ImageChops.difference(orig, rend)
    diff_amp = diff.point(lambda v: min(255, v * 3))
    blend = Image.blend(orig, rend, 0.5)
    labels = [('original blank', orig), ('template', inp), ('render', rend), ('amplified diff', diff_amp), ('50% overlay', blend)]
    scale_w = 430
    thumbs=[]
    for label, im in labels:
        t=im.copy(); t.thumbnail((scale_w, 610)); thumbs.append((label,t))
    font=ImageFont.truetype(str(FONT_FALLBACK),20) if FONT_FALLBACK.exists() else ImageFont.load_default()
    sheet=Image.new('RGB',(scale_w*len(thumbs)+20*(len(thumbs)+1),690),(245,245,242))
    d=ImageDraw.Draw(sheet)
    for i,(label,t) in enumerate(thumbs):
        x=20+i*(scale_w+20)
        d.text((x,18),label,font=font,fill=(20,20,20))
        sheet.paste(t,(x,54)); d.rectangle([x,54,x+t.width,54+t.height],outline=(150,150,150))
    sheet.save(CALIB_DIR / 'full_comparison.jpg', quality=92)
    diff.save(CALIB_DIR / 'full_diff.png')
    blend.save(CALIB_DIR / 'full_overlay_50.png')


def make_contact_sheet(sample_paths: list[Path]) -> Path:
    thumbs=[]
    for path in sample_paths:
        im=Image.open(path).convert('RGB'); im.thumbnail((330,470)); thumbs.append((path.stem, im.copy()))
    font=ImageFont.truetype(str(FONT_FALLBACK),18) if FONT_FALLBACK.exists() else ImageFont.load_default()
    sheet=Image.new('RGB',(5*350+20,540),(246,246,243)); d=ImageDraw.Draw(sheet)
    for i,(label,im) in enumerate(thumbs):
        x=20+i*350; y=24
        d.text((x,y),label,font=font,fill=(25,25,25)); sheet.paste(im,(x,y+34)); d.rectangle([x,y+34,x+im.width,y+34+im.height],outline=(155,155,155))
    out=BATCH_DIR / 'contact_sheet.jpg'; out.parent.mkdir(parents=True, exist_ok=True); sheet.save(out, quality=92); return out


def write_progress(preview, batch, contact: Path) -> None:
    PROGRESS.write_text(f'''# 2026-07-02 APP-13 계좌개설신청서 파이프라인 준비 작업

## 목표
- `APP-13 계좌개설신청서`를 주주명부/RPT-07 다음 순차 처리 대상으로 진행한다.
- 현재 샘플은 값이 기입되지 않은 blank form이므로, bbox review의 `use` 영역이 없고 인페인팅은 원본 보존 템플릿으로 처리한다.
- 빈 입력란 위치를 원본 시각 정보 기준으로 직접 bbox/schema/faker/style로 정의한다.

## 입력 상태
- 원본 이미지: `{ORIGINAL}`
- bbox review: `{REVIEW}`
- LaMa 인페인팅 결과: `{INPAINTED}`
- 인페인팅 summary: `{INPAINT_SUMMARY}`
- review에는 치환 대상 use bbox가 없어 mask_ratio 0 템플릿을 사용한다.

## 구조화 결정
- 정적 Citi 추가계좌 개설 신청서 양식에 값만 주입한다.
- 주요 필드는 작성일, 회사명, 기존 계좌번호, 계좌명, 계좌 종류/통화, 법적 주소, 사업장 주소, 수권서명자, 대리인 정보, 회사 대표 기입란, 명판/법인인감 서명자다.
- 원본이 blank form이므로 값 font-family는 실제 기입값 추출이 불가능하다. 정적 양식과 시각적으로 충돌이 적은 Apple SD Gothic Neo 계열을 낮은 opacity로 적용했다.
- crop 비교 루틴은 사용하지 않고 전체 문서 렌더/overlay로만 확인했다.

## 산출물
- schema: `{SCHEMA_PATH}`
- stylesheet: `{STYLE_PATH}`
- faker_profile: `{FAKER_PATH}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
- preview: `{preview.image}`
- preview overlay: `{preview.overlay}`
- preview validation: `{preview.validation_report}`
- batch summary: `{batch.summary}`
- batch output dir: `{BATCH_DIR}`
- contact sheet: `{contact}`
- full comparison: `{CALIB_DIR / 'full_comparison.jpg'}`
- 50% overlay: `{CALIB_DIR / 'full_overlay_50.png'}`

## 검수 결과 및 남은 리스크
- field 수: {batch.field_count}
- 렌더 경고 수: {batch.warning_count}
- blank form 특성상 인페인팅 품질 리스크는 낮다.
- 원본의 실제 수기 기입 스타일이 없으므로 font-family/weight는 추후 실제 작성본 샘플이 확보되면 재보정해야 한다.
- 현재는 1페이지 양식만 처리한다. 다중 페이지 계좌개설 패키지가 들어오면 subtype 또는 page template 분리가 필요하다.
''', encoding='utf-8')


def main() -> None:
    if not ORIGINAL.exists():
        raise FileNotFoundError(ORIGINAL)
    AUTHORING.mkdir(parents=True, exist_ok=True)
    if CALIB_DIR.exists():
        shutil.rmtree(CALIB_DIR)
    schema = build_schema()
    stylesheet = build_stylesheet()
    faker = build_faker_profile(schema['fields'])
    write_json(SCHEMA_PATH, schema)
    write_json(STYLE_PATH, stylesheet)
    write_json(FAKER_PATH, faker)
    write_json(SEMANTIC_SCHEMA, build_semantic_schema(schema))
    preview = render_authoring_preview(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=OUT_DIR, seed=20260702)
    batch = render_authoring_batch(SCHEMA_PATH, STYLE_PATH, FAKER_PATH, out_dir=BATCH_DIR, count=5, seed=20260702, sample_prefix='app13', clean=True)
    contact = make_contact_sheet([sample.image for sample in batch.samples])
    make_full_comparison(preview.image)
    if INPAINT_COMPARISON.exists():
        update_manifest_artifact(DOC_ID, 'inpaint', INPAINT_COMPARISON)
    if INPAINTED.exists():
        update_manifest_artifact(DOC_ID, 'inpainted', INPAINTED)
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
