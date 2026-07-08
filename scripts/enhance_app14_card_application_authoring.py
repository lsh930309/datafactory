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

DOC_ID='APP-14'
DOC_TITLE='카드발급신청서'
DOC_DIR=ROOT/'workbench'/'documents'/'카드발급신청서__APP-14'
AUTHORING=DOC_DIR/'authoring'
OUT_DIR=AUTHORING/'render_preview'
BATCH_DIR=ROOT/'outputs'/'pipeline_ready'/'APP-14_카드발급신청서'
CALIB_DIR=ROOT/'outputs'/'style_calibration'/'APP-14_카드발급신청서'
SEMANTIC_SCHEMA=AUTHORING/'semantic_schema.json'
PROGRESS=ROOT/'docs/reports/pipeline_ready/20260702_app14_card_application_pipeline_readiness.md'
PAGES={i:DOC_DIR/'samples'/'original'/f'카드발급신청서_page_{i:03d}.jpg' for i in range(1,5)}
FONT_APPLE=Path('/System/Library/Fonts/AppleSDGothicNeo.ttc')
FONT_FALLBACK=ROOT/'fonts'/'malgun.ttf'
FONT=str(FONT_APPLE if FONT_APPLE.exists() else FONT_FALLBACK)
FONT_FAMILY='AppleSDGothicNeo' if FONT_APPLE.exists() else 'default_korean'
NOW=datetime.now(timezone.utc).isoformat()
CHECK='✓'

P1_CHECKS={
 'id_resident':[235,314,18,18],'id_gov':[349,314,18,18],'id_foreign':[457,314,18,18],'id_welfare':[590,314,18,18],'id_driver':[349,356,18,18],'id_passport':[456,356,18,18],
 'privacy1_agree':[864,650,22,22],'privacy1_disagree':[1009,650,22,22],'privacy2_agree':[864,686,22,22],'privacy2_disagree':[1009,686,22,22],
 'privacy3_agree':[864,782,22,22],'privacy3_disagree':[1009,782,22,22],'privacy4_agree':[864,817,22,22],'privacy4_disagree':[1009,817,22,22],
 'privacy5_agree':[864,900,22,22],'privacy5_disagree':[1009,900,22,22],'privacy6_agree':[864,935,22,22],'privacy6_disagree':[1009,935,22,22],
 'optional1_agree':[864,1144,22,22],'optional1_disagree':[1009,1144,22,22],'optional2_agree':[864,1180,22,22],'optional2_disagree':[1009,1180,22,22],'optional3_agree':[864,1215,22,22],'optional3_disagree':[1009,1215,22,22],
 'channel_phone':[475,1260,22,22],'channel_sms':[557,1260,22,22],'channel_paper':[676,1260,22,22],'channel_email':[762,1260,22,22],'channel_all':[864,1260,22,22],'channel_disagree':[1009,1260,22,22],
 'third_party1_agree':[864,1404,22,22],'third_party1_disagree':[1009,1404,22,22],'third_party2_agree':[864,1439,22,22],'third_party2_disagree':[1009,1439,22,22],'third_party3_agree':[864,1488,22,22],'third_party3_disagree':[1009,1488,22,22],
}
P1_TEXTS={
 'receipt_year':[270,458,50,26],'receipt_month':[405,458,50,26],'receipt_day':[525,458,50,26],'applicant_name':[518,496,175,26],
 'issuer_date':[763,315,145,24],'issuer_agency':[932,315,170,24],'tracking_number':[724,357,220,24],'dispatch_date':[724,397,170,24],'delivery_barcode':[724,456,220,24],
 'required_consent_year':[300,968,48,26],'required_consent_month':[452,968,48,26],'required_consent_day':[572,968,48,26],'required_consent_name':[790,968,270,26],
 'optional_consent_year':[300,1531,48,26],'optional_consent_month':[452,1531,48,26],'optional_consent_day':[572,1531,48,26],'optional_consent_name':[790,1531,270,26],
}
P4_CHECKS={'service_agree':[864,1367,22,22],'service_disagree':[1010,1367,22,22]}
P4_TEXTS={'issue_date_serial':[108,122,300,42],'delivery_barcode':[508,122,420,42],'service_year':[300,1512,48,28],'service_month':[452,1512,48,28],'service_day':[572,1512,48,28],'service_name':[790,1512,260,28]}

# Apple SD Gothic Neo의 check glyph는 textbbox top offset 때문에 중앙 정렬 시 하단으로 내려가 보인다.
# APP-14의 checkbox는 실제 기입값 위치가 중요하므로 문서 전용으로 요청 bbox를 위로 미세 보정한다.
for _checks in (P1_CHECKS, P4_CHECKS):
    for _bbox in _checks.values():
        _bbox[1] -= 7
        _bbox[3] += 2


def write_json(path:Path,data:dict[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    backup_authoring_json_before_write(path, next_payload=data, reason=Path(__file__).name + ".write_json")
def field(fid,label,bbox,style,gen,*,align='left',value_type='free_text.short'):
    return {'field_id':fid,'label':label,'bbox':bbox,'bbox_format':'xywh','source_detection_id':'manual_app14_blank_form_20260702','source_text':'','value_type':value_type,'generator':gen,'style_class':style,'render_policy':{'align':align,'valign':'middle','fit':'shrink_to_fit','overflow':'shrink'},'export':{'json_path':fid.replace('_','.'),'csv_column':fid},'required':False,'notes':'APP-14 blank form 수동 bbox/style 필드'}

def style(style_id,size,*,align='left',opacity=.9,color=None):
    return {'style_class':style_id,'font_family':FONT_FAMILY,'font_path':FONT,'font_size':size,'font_weight':'normal','fill':color or [18,18,18],'opacity':opacity,'align':align,'valign':'middle','line_spacing':1.0,'letter_spacing':0.0,'baseline_shift':0,'overflow':'shrink','confidence':0.72,'source_detection_ids':['manual_app14_blank_form_20260702']}

def schema(page:int)->dict[str,Any]:
    checks=P1_CHECKS if page==1 else P4_CHECKS
    texts=P1_TEXTS if page==1 else P4_TEXTS
    fields=[]
    for k,b in checks.items(): fields.append(field(f'p{page}_{k}',f'page{page} check {k}',b,'style_check',f'pool_record:app14_profiles.p{page}_{k}',align='center',value_type='bool.checkbox'))
    for k,b in texts.items():
        is_date_part = 'date' in k or k in {'receipt_year','receipt_month','receipt_day'} or k.endswith(('_year','_month','_day'))
        st='style_date' if is_date_part else ('style_text_small' if 'barcode' in k or 'tracking' in k else 'style_text')
        fields.append(field(f'p{page}_{k}',f'page{page} {k}',b,st,f'pool_record:app14_profiles.p{page}_{k}',align='center' if is_date_part else 'left'))
    return {'schema_version':1,'created_at':NOW,'updated_at':NOW,'doc_id':DOC_ID,'title':f'{DOC_TITLE} page {page}','page_index':page,'source_image':str(PAGES[page].resolve()),'source_inpainted':str(PAGES[page].resolve()),'image':{'width':1191,'height':1684},'fields':fields,'groups':[{'group_id':'card_application_values','type':'blank_form_fields','notes':f'APP-14 page {page} 수동 체크/기입 필드'}],'authoring_mode':f'app14_page_{page}_pipeline_ready_20260702','quality_status':'pipeline_ready_candidate'}

def stylesheet()->dict[str,Any]:
    return {'schema_version':1,'created_at':NOW,'updated_at':NOW,'doc_id':DOC_ID,'style_classes':[style('style_check',14,align='center',opacity=.88,color=[5,5,5]),style('style_text',18,opacity=.88),style('style_text_small',16,opacity=.88),style('style_date',17,align='center',opacity=.88)],'notes':'APP-14 카드발급신청서 생산용 스타일. 원본은 blank form이므로 전체 렌더/overlay 기준 Apple SD Gothic Neo 저농도 텍스트와 작은 체크 표시를 사용함. crop 비교 미사용.'}

def mark(record,page,groups,chosen):
    for key in groups: record[f'p{page}_{key}']=CHECK if key==chosen else ''

def make_profiles():
    rng=random.Random(20260702); names=['김민준','이서연','박도윤','최하은','정시우','강서윤']; agencies=['서울강남','부산서면','대전둔산','광주상무','인천송도']; profiles=[]
    all_keys=list(P1_CHECKS)+list(P4_CHECKS)+list(P1_TEXTS)+list(P4_TEXTS)
    for i,name in enumerate(names):
        r={f'p1_{k}':'' for k in list(P1_CHECKS)+list(P1_TEXTS)}; r.update({f'p4_{k}':'' for k in list(P4_CHECKS)+list(P4_TEXTS)})
        mark(r,1,['id_resident','id_gov','id_foreign','id_welfare','id_driver','id_passport'],['id_resident','id_driver','id_passport'][i%3])
        for base in ['privacy1','privacy2','privacy3','privacy4','privacy5','privacy6']:
            mark(r,1,[f'{base}_agree',f'{base}_disagree'],f'{base}_agree')
        for base in ['optional1','optional2','optional3','third_party1','third_party2','third_party3']:
            mark(r,1,[f'{base}_agree',f'{base}_disagree'],f'{base}_agree' if i%3 else f'{base}_disagree')
        channel_groups=['channel_phone','channel_sms','channel_paper','channel_email','channel_all','channel_disagree']
        for key in channel_groups: r[f'p1_{key}']=''
        for key in (['channel_all'] if i%2 else ['channel_phone','channel_sms','channel_email']): r[f'p1_{key}']=CHECK
        mark(r,4,['service_agree','service_disagree'],'service_agree')
        # Project 기준일(2026-07-02) 이후 미래일이 나오지 않도록 2026-06 범위로 고정한다.
        month=6; day=2+i*4; dispatch=f'2026-{month:02d}-{day:02d}'
        r.update({
            'p1_receipt_year':'26','p1_receipt_month':str(month),'p1_receipt_day':str(day),'p1_applicant_name':name,
            'p1_issuer_date':dispatch,'p1_issuer_agency':agencies[i%len(agencies)],'p1_tracking_number':f'{rng.randint(100000,999999)}-{rng.randint(10,99)}','p1_dispatch_date':dispatch,'p1_delivery_barcode':f'BC{rng.randint(10000000,99999999)}',
            'p1_required_consent_year':'26','p1_required_consent_month':str(month),'p1_required_consent_day':str(day),'p1_required_consent_name':name,
            'p1_optional_consent_year':'26','p1_optional_consent_month':str(month),'p1_optional_consent_day':str(day+1),'p1_optional_consent_name':name,
            'p4_issue_date_serial':f'{dispatch} / {rng.randint(100000,999999)}','p4_delivery_barcode':f'HN-{rng.randint(1000000000,9999999999)}','p4_service_year':'26','p4_service_month':str(month),'p4_service_day':str(day+2),'p4_service_name':name,
        })
        profiles.append(r)
    return profiles

def faker_profile(fields):
    gens={f['field_id']:('bool.checkbox' if str(f.get('style_class'))=='style_check' else 'literal:') for f in fields}
    targets={f['field_id']:f['generator'].split('.',1)[1] for f in fields}
    return {'schema_version':1,'created_at':NOW,'updated_at':NOW,'doc_id':DOC_ID,'locale':'ko_KR','field_generators':gens,'constraints':[{'type':'pick_record','pool':'app14_profiles','targets':targets}],'data_pools':{'app14_profiles':make_profiles()},'notes':'APP-14 4페이지 카드발급신청서 faker profile. page1/page4는 같은 record로 체크/기입값을 렌더링하고 page2/page3은 안내 원문을 보존함.'}


def semantic_schema(schema_paths:list[Path])->dict[str,Any]:
    field_mapping:dict[str,str]={}
    for path in schema_paths:
        data=json.loads(path.read_text(encoding='utf-8'))
        for item in data.get('fields',[]):
            field_mapping[item['field_id']]=item.get('export',{}).get('json_path',item['field_id'])
    return {
        'schema_version':1,
        'created_at':NOW,
        'updated_at':NOW,
        'doc_id':DOC_ID,
        'title':DOC_TITLE,
        'purpose':'렌더링 bbox/style 속성을 제외한 KIE/라벨링 관점의 의미 구조',
        'semantic_schema':{
            '카드발급신청서':{
                '발급신청확인서 및 인수증':{
                    '카드인수':{
                        '교부자 기재':{'신분증 종류':{'주민등록증':'','공무원증':'','외국인등록증':'','장애인등록증':'','운전면허증':'','여권':''},'발급일자':'','발급기관':'','주민번호':'','추적번호':'','발송일자':'','배송사 바코드':''},
                        '회원 기재':{'수령일자':{'년':'','월':'','일':''},'신청인 성명':''},
                    },
                    '필수 동의':{
                        '고유식별정보 수집 이용':'','고유식별정보 처리':'','개인신용정보 제3자 제공':'','제3자 고유식별정보 처리':'','개인신용정보 조회':'','신용정보 고유식별정보 처리':'',
                        '동의일자':{'년':'','월':'','일':''},'성명':''
                    },
                    '선택 동의':{
                        '개인신용정보 수집 이용':'','마케팅 고유식별정보 처리':'','이용권유 방법':{'전화':'','문자메시지':'','서면':'','이메일':'','전부동의':'','동의하지않음':''},
                        '개인신용정보 제공':'','출입국 관리 제공':'','부정사용 방지 제공':'',
                        '동의일자':{'년':'','월':'','일':''},'성명':''
                    },
                    '제3자 제공 동의':{'제공 동의 1':'','제공 동의 2':'','제공 동의 3':''},
                },
                '상품서비스 제공 동의':{
                    '발송정보':{'발송일자 및 일련번호':'','배송사 바코드':''},
                    '필수 제공 동의':'',
                    '동의일자':{'년':'','월':'','일':''},
                    '성명':'',
                },
            }
        },
        'field_mapping':field_mapping,
        'notes':['page_001/page_004 schema는 렌더러 호환을 위해 bbox/style/generator 정보를 유지한다.','semantic_schema.json은 KIE용 key-name 계층만 별도 관리한다.','page_002/page_003은 현재 정적 약관/안내문 페이지로 보존한다.'],
    }

def render_pair(schema1,schema4,style_path,faker_path,count=5):
    if BATCH_DIR.exists(): shutil.rmtree(BATCH_DIR)
    BATCH_DIR.mkdir(parents=True)
    samples=[]; pairs=[]; warnings=0; field_count=0
    for i in range(1,count+1):
        sid=f'app14_{i:06d}'; seed=20260702+i-1
        r1=render_authoring_preview(schema1,style_path,faker_path,out_dir=BATCH_DIR,seed=seed,sample_id=f'{sid}_page_001')
        # Static terms pages are preserved as-is for this blank-form pipeline stage.
        p2=BATCH_DIR/f'{sid}_page_002.png'; p3=BATCH_DIR/f'{sid}_page_003.png'
        Image.open(PAGES[2]).save(p2); Image.open(PAGES[3]).save(p3)
        r4=render_authoring_preview(schema4,style_path,faker_path,out_dir=BATCH_DIR,seed=seed,sample_id=f'{sid}_page_004')
        warnings+=r1.warning_count+r4.warning_count; field_count=r1.field_count+r4.field_count; pairs.append([r1.image,p2,p3,r4.image])
        samples.append({'sample_id':sid,'pages':[{'page':1,'image':str(r1.image),'kv':str(r1.kv),'bbox':str(r1.bbox),'overlay':str(r1.overlay),'validation_report':str(r1.validation_report),'warning_count':r1.warning_count},{'page':2,'image':str(p2),'static_preserved':True},{'page':3,'image':str(p3),'static_preserved':True},{'page':4,'image':str(r4.image),'kv':str(r4.kv),'bbox':str(r4.bbox),'overlay':str(r4.overlay),'validation_report':str(r4.validation_report),'warning_count':r4.warning_count}]})
    contact=make_contact_sheet(pairs)
    summary={'schema_version':1,'created_at':NOW,'doc_id':DOC_ID,'title':DOC_TITLE,'schemas':{'page_001':str(schema1),'page_004':str(schema4)},'stylesheet':str(style_path),'faker_profile':str(faker_path),'out_dir':str(BATCH_DIR),'count':count,'page_count':4,'field_count_per_sample':field_count,'warning_count':warnings,'contact_sheet':str(contact),'samples':samples}
    write_json(BATCH_DIR/'summary.json',summary); return summary

def make_contact_sheet(groups):
    font=ImageFont.truetype(str(FONT_FALLBACK),16) if FONT_FALLBACK.exists() else ImageFont.load_default(); cell_w,cell_h=250,355
    sheet=Image.new('RGB',(len(groups)*cell_w+20,cell_h*4+64),(246,246,243)); d=ImageDraw.Draw(sheet)
    for i,paths in enumerate(groups):
        x=20+i*cell_w; d.text((x,14),f'app14_{i+1:06d}',font=font,fill=(25,25,25))
        for row,path in enumerate(paths):
            im=Image.open(path).convert('RGB'); im.thumbnail((cell_w-20,cell_h-35)); y=44+row*cell_h; d.text((x,y-18),f'page {row+1}',font=font,fill=(70,70,70)); sheet.paste(im,(x,y)); d.rectangle([x,y,x+im.width,y+im.height],outline=(155,155,155))
    out=BATCH_DIR/'contact_sheet.jpg'; sheet.save(out,quality=92); return out

def compare(page,original,rendered):
    out_dir=CALIB_DIR/f'page_{page:03d}'; out_dir.mkdir(parents=True,exist_ok=True)
    orig=Image.open(original).convert('RGB'); rend=Image.open(rendered).convert('RGB').resize(orig.size)
    diff=ImageChops.difference(orig,rend); blend=Image.blend(orig,rend,.5); diff_amp=diff.point(lambda v:min(255,v*4))
    labels=[('original blank',orig),('render',rend),('amplified diff',diff_amp),('50% overlay',blend)]
    scale_w=420; font=ImageFont.truetype(str(FONT_FALLBACK),20) if FONT_FALLBACK.exists() else ImageFont.load_default(); thumbs=[]
    for label,im in labels:
        t=im.copy(); t.thumbnail((scale_w,610)); thumbs.append((label,t))
    sheet=Image.new('RGB',(scale_w*4+100,690),(245,245,242)); d=ImageDraw.Draw(sheet)
    for i,(label,t) in enumerate(thumbs):
        x=20+i*(scale_w+20); d.text((x,18),label,font=font,fill=(20,20,20)); sheet.paste(t,(x,54)); d.rectangle([x,54,x+t.width,54+t.height],outline=(150,150,150))
    out=out_dir/'full_comparison.jpg'; sheet.save(out,quality=92); diff.save(out_dir/'full_diff.png'); blend.save(out_dir/'full_overlay_50.png'); return out

def write_progress(summary,c1,c4):
    PROGRESS.write_text(f'''# 2026-07-02 APP-14 카드발급신청서 파이프라인 준비 작업

## 목표
- `APP-14 카드발급신청서`를 SEC-03 다음 순차 처리 대상으로 진행한다.
- 현재 샘플은 4페이지 blank form이며 OCR/review/inpaint 산출물이 없다.
- page 1과 page 4는 체크/날짜/성명/배송정보 기입란을 생산용 field로 정의하고, page 2~3은 약관/안내문 성격의 정적 페이지로 보존한다.

## 입력 상태
- page 1~4 원본: `{DOC_DIR / 'samples' / 'original'}`
- 기존 OCR/review/inpaint: 없음
- blank form이므로 인페인팅은 생략하고 원본을 `source_inpainted`로 사용했다.

## 구조화 결정
- page 1: 카드 인수, 필수/선택 동의, 이용권유 방법, 제3자 제공 동의, 날짜/성명 필드.
- page 4: 발송일자/일련번호, 배송사 바코드, 상품서비스 제공 동의, 날짜/성명 필드.
- page 2~3: 데이터 주입 대상이 거의 없는 안내문 페이지로 판단해 원문 보존.
- KIE용 key-name 계층은 `semantic_schema.json`으로 분리했다.
- 모든 생성 날짜는 2026-06 범위로 제한하여 프로젝트 기준일 이후 미래일을 제거했다.
- font-family는 blank form 특성상 실제 기입값이 없으므로 전체 렌더 기준 Apple SD Gothic Neo 저농도 스타일로 선택했다.
- crop 비교는 사용하지 않았다.

## 산출물
- page 1 schema: `{AUTHORING / 'page_001' / 'schema.json'}`
- page 4 schema: `{AUTHORING / 'page_004' / 'schema.json'}`
- stylesheet: `{AUTHORING / 'stylesheet.json'}`
- faker_profile: `{AUTHORING / 'faker_profile.json'}`
- semantic_schema: `{SEMANTIC_SCHEMA}`
- batch summary: `{BATCH_DIR / 'summary.json'}`
- contact sheet: `{BATCH_DIR / 'contact_sheet.jpg'}`
- page 1 comparison: `{c1}`
- page 4 comparison: `{c4}`
- preview page 1: `{OUT_DIR / 'preview_page_001.png'}`
- preview page 4: `{OUT_DIR / 'preview_page_004.png'}`

## 검수 결과 및 남은 리스크
- 생성 세트 수: {summary['count']}세트 x {summary['page_count']}페이지
- field 수/page sample 합계: {summary['field_count_per_sample']}
- 렌더 경고 수: {summary['warning_count']}
- page 2~3은 정적 보존 처리했다. 향후 약관 내 개별 체크/서명란이 있는 변형 양식이 들어오면 별도 page schema를 추가해야 한다.
- 좌표는 원본 blank form 기준 수동 측정값이며, 실제 업무 적용 전 웹 GUI에서 bbox 미세 조정 가능성을 열어 둔다.
''',encoding='utf-8')

def main():
    for p in PAGES.values():
        if not p.exists(): raise FileNotFoundError(p)
    AUTHORING.mkdir(parents=True,exist_ok=True)
    if CALIB_DIR.exists(): shutil.rmtree(CALIB_DIR)
    s1=schema(1); s4=schema(4); st=stylesheet(); fk=faker_profile(s1['fields']+s4['fields'])
    p1=AUTHORING/'page_001'/'schema.json'; p4=AUTHORING/'page_004'/'schema.json'; sp=AUTHORING/'stylesheet.json'; fp=AUTHORING/'faker_profile.json'
    write_json(p1,s1); write_json(p4,s4); write_json(AUTHORING/'schema.json',s1); write_json(sp,st); write_json(fp,fk); write_json(SEMANTIC_SCHEMA,semantic_schema([p1,p4]))
    r1=render_authoring_preview(p1,sp,fp,out_dir=OUT_DIR,seed=20260702,sample_id='preview_page_001')
    r4=render_authoring_preview(p4,sp,fp,out_dir=OUT_DIR,seed=20260702,sample_id='preview_page_004')
    summary=render_pair(p1,p4,sp,fp,count=5)
    c1=compare(1,PAGES[1],r1.image); c4=compare(4,PAGES[4],r4.image)
    update_manifest_artifact(DOC_ID,'authoring',AUTHORING/'schema.json'); update_manifest_artifact(DOC_ID,'authoring_page_001_schema',p1); update_manifest_artifact(DOC_ID,'authoring_page_004_schema',p4); update_manifest_artifact(DOC_ID,'authoring_stylesheet',sp); update_manifest_artifact(DOC_ID,'authoring_faker_profile',fp); update_manifest_artifact(DOC_ID,'authoring_semantic_schema',SEMANTIC_SCHEMA); update_manifest_artifact(DOC_ID,'authoring_preview',r1.image); update_manifest_artifact(DOC_ID,'authoring_page_004_preview',r4.image); update_manifest_artifact(DOC_ID,'authoring_overlay',r1.overlay); update_manifest_artifact(DOC_ID,'authoring_batch',BATCH_DIR/'summary.json'); update_manifest_artifact(DOC_ID,'authoring_contact_sheet',BATCH_DIR/'contact_sheet.jpg'); update_manifest_artifact(DOC_ID,'authoring_style_comparison',c1); update_manifest_artifact(DOC_ID,'authoring_page_004_style_comparison',c4)
    write_progress(summary,c1,c4)
    print('preview page1',r1.image,'warnings',r1.warning_count); print('preview page4',r4.image,'warnings',r4.warning_count); print('batch',BATCH_DIR/'summary.json','warnings',summary['warning_count']); print('contact',BATCH_DIR/'contact_sheet.jpg'); print('comparison1',c1); print('comparison4',c4)
if __name__=='__main__': main()
