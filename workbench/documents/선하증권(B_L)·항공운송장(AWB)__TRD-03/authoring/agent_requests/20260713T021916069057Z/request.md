# Agentic Authoring Request: 선하증권(B/L)·항공운송장(AWB) (TRD-03)

## 목표
문서 이미지/OCR/BBox review와 실제 문서 리서치 근거를 사용해 authoring 초안을 A-to-Z로 생성한다.
산출물은 즉시 적용하지 않는 draft이며, UI에서 사용자 승인/수정/백업 후 확정한다.

## 사용자 지시
이번 작업은 인쇄체 authoring 품질 재구축이다.
1. 전체 원본/인페인트 이미지와 use bbox를 source of truth로 삼아 실제 문서 KIE 구조를 반영한 계층형 primary semantic_schema를 만든다. 메타데이터는 넣지 않는다.
2. 모든 use bbox를 빠짐없이 binding한다. 의미가 불명확하면 생략하지 말고 검토필요 leaf로 연결한다.
3. 기존 stylesheet의 검증된 폰트/정렬/크기는 가능한 한 보존하고, 이번 작업의 중심을 schema와 faker 품질에 둔다.
4. 열린 scalar pool은 20개 이상, 상관관계 record pool은 12개 이상으로 만들고, 작은 폐쇄형 선택지는 pool_policies에 근거를 명시한다.
5. 날짜는 작업일 이후가 될 수 없고 현실의 선후관계를 지켜야 한다. 사업자등록번호는 checksum이 맞아야 하며 주민등록번호는 유효 생년월일과 뒷자리 마스킹을 사용한다.
6. 금리/비율/금액/합계/연령/체크박스/기관-질병-코드 등 서로 의존하는 값은 지원 constraint로 명시한다. 독립 생성으로 현실에서 불가능한 조합이 나오지 않게 한다.
7. 값 위치에 정적 단위가 인쇄되어 있으면 faker 값에 단위를 중복하지 않는다.
8. FIN-01과 QC-01의 다중 페이지 완결성은 이번 차수에서 확장하지 않는다. 현재 페이지의 KIE와 값 품질만 개선하고 uncertainty_report에 페이지 제한을 명시한다.

## 입력 문서 컨텍스트
- 제목: 선하증권(B/L)·항공운송장(AWB)
- 문서 ID: TRD-03
- PO 도메인: 무역
- 업무 도메인: 무역·물류

## 필수 산출물
- `schema_draft.json`
- `stylesheet_draft.json`
- `faker_profile_draft.json`
- `value_pool_draft.json`
- `research_report.json`
- `uncertainty_report.json`
- `anchor_map_draft.json`
- `application_notes.md`

## 웹 리서치 필수 규칙
- schema/faker 초안 생성 전에 실제 문서명과 유사 명칭을 웹 검색한다.
- 공식/원문/공공기관/법령/제도 설명/실제 샘플 양식을 우선 출처로 사용한다.
- research_report에는 검색일, 검색어, 출처 URL, 출처 유형, 요약, 필드별 반영 근거를 기록한다.
- 리서치는 문서에 보이는 anchor의 의미 해석과 faker profile 정밀화를 위한 보조 근거일 뿐, 템플릿에 없는 필드를 자동 추가하는 근거가 아니다.
- 출처 간 내용이 다르거나 실제 템플릿 anchor와 연결되지 않으면 faker rule을 확정하지 않고 uncertainty_report에 남긴다.

## Schema 규칙
- `schema_draft.json`은 constrained full authoring draft이다. Agent가 의미 판단과 bbox mapping을 함께 수행하되, 시스템이 deterministic하게 분할할 수 있는 JSON만 작성한다.
- `schema_draft.json.semantic_schema`는 사용자와 GT가 보는 primary schema이다. 메타데이터 없이 KIE 관점의 key-value hierarchy만 작성하고 모든 leaf value는 빈 문자열로 둔다.
- `schema_draft.json.fields` 또는 `schema_draft.json.field_bindings`는 semantic_schema leaf와 bbox anchor를 연결하기 위한 binding layer로만 사용한다.
- 각 binding은 `field_id`, 한국어 `key` 또는 `label`, `semantic_path`, `anchor_id`, 빈 `value`, 선택적 `label_anchor_ids`, `value_type`, `faker_rule`/`generator`, `style_class`, `unit_policy`, `research_evidence_ids`, `visual_evidence`를 포함한다.
- 각 binding의 `semantic_path`는 반드시 `semantic_schema`의 leaf path와 정확히 일치해야 한다. 단, 화면 렌더링만을 위한 복합 표시 필드는 `export:{include:false}`를 명시하고 semantic_schema leaf 매핑에서 제외할 수 있다.
- 각 binding의 `anchor_id`는 anchor_map_draft에 존재해야 하며, 값 target인 `use` anchor여야 한다. 라벨 bbox는 `label_anchor_ids`에만 둔다.
- key는 실제 문서에 보이는 라벨, 표제, placeholder, 주변 텍스트, 편집 가능한 anchor 기반 한국어 자연어를 우선한다.
- 문서에 보이지 않는 추상 키, 업무 추론만으로 만든 키, downstream 편의용 임의 구조체를 만들지 않는다.
- 웹 리서치로 발견한 일반 항목이라도 대응 anchor가 없으면 schema_draft에 자동 추가하지 않는다.
- `use` anchor는 절대 생략하지 않는다. 의미가 불확실해도 반드시 `검토필요/<anchor_id 또는 보이는 label>` primary leaf와 binding field를 만들고 `review_required:true`, 낮은 confidence, uncertainty_report 항목을 남긴다.
- `unmapped_use_anchors`는 성공 산출물에서 금지한다. 모든 use anchor coverage는 100%여야 한다.
- 예: primary semantic schema에는 `입원일`, `퇴원일`을 분리 저장하되 문서에는 `입원: yyyy-mm-dd, 퇴원: yyyy-mm-dd` 한 줄로 찍어야 한다면, 분리 leaf field는 `render_policy:{render:false}`로 두고 복합 표시 field는 같은 anchor에 `export:{include:false}`로 둔다.

## 시각 근거 우선 규칙
- 전체 템플릿 이미지가 최상위 source of truth이다. 웹 리서치, 문서명, 라벨 텍스트, 관행보다 실제 전체 문서 이미지에서 보이는 레이아웃/라벨/값 위치 관계가 우선한다.
- agent_requests의 visual_evidence_manifest.json은 전체 템플릿 이미지 경로와 bbox 위치 인덱스이다. 먼저 전체 이미지를 보고 문맥을 판단하고, crops/*.png는 작은 글자나 경계가 애매할 때만 확대 보조 자료로 확인한다.
- 값 위치 바로 옆/안에 정적 단위나 prefix/suffix가 실제로 인쇄되어 있는지는 전체 이미지의 문맥에서 판단하고, 필요한 경우 해당 crop으로 확대 확인한다.
- 라벨에만 단위 의미가 있고 값 위치에는 별도 정적 단위가 없으면, 그 단위가 자연스러운 값 표기의 일부인지 판단해 포함할 수 있다. 예: 호수/가구수/세대수 값은 `0호/0가구/0세대`처럼 생성한다.
- 전체 이미지에서 보이는 시각 근거와 OCR/리서치가 충돌하면 전체 이미지 근거를 따르고, 결정 근거를 faker_profile_draft.json.field_rules 또는 uncertainty_report.json에 기록한다.

## Faker profile 규칙
- schema key의 의미가 충분히 명확하고 문서 anchor 또는 리서치 근거와 연결될 때만 faker rule을 제안한다.
- 문서 필드의 의미와 실제 작성 관행을 근거로 타입, 형식, 값 범위, 선택지, 단위, 날짜/금액/식별번호 규칙을 제안하되, 반드시 현재 DataFactory 렌더러가 지원하는 rule 문법만 사용한다.
- 날짜와 연령 관계는 요청의 고정 기준일 `2026-07-13`을 기준으로 설계한다. 미래 날짜를 만들지 말고 실행 시각에 따라 결과가 달라지는 암묵적 today를 전제로 하지 않는다.
- 서로 독립적으로 생성하면 문서 유효성이 깨지는 field들은 `faker_profile_draft.json.constraints`에 명시적으로 모델링한다. 예: 체크박스 택1, 시작/종료일 순서, 행/열 합계, 본인부담금/공단부담금/총액 관계.
- 지원 constraint 타입은 `pick_record`, `copy`, `exclusive_choice`, `primary_secondary_group`, `date_group`, `date_order`, `date_not_before`, `date_not_after`, `sum`, `numeric_range`, `numeric_compare`, `age_from_rrn`뿐이다. 지원하지 않는 수식 DSL이나 자연어 constraint는 쓰지 말고 uncertainty_report에 보류한다.
- 연/월/일이 각각 다른 bbox로 분리된 날짜 placeholder에는 `date.year`, `date.month`, `date.day`를 우선 사용한다. 날짜의 월/일/연도에 `pattern:##` 또는 `pattern:####`를 쓰지 않는다.
- 문서 이미지/템플릿의 값 입력 위치 바로 옆/안에 `㎡`, `m²`, `m2`, `%`, `m`, `원`, `명`, `건`, `동`, `층` 같은 단위가 이미 정적 텍스트로 남아 있으면 faker 값에는 그 단위를 포함하지 않는다.
- `호/가구/세대`처럼 라벨에만 단위 의미가 있고 값 위치에 별도 정적 단위가 없는 복합 값은 단위를 포함해 생성한다. 단위 포함/제외 근거를 field_rules 또는 uncertainty_report에 기록한다.
- faker_profile_draft.json에는 렌더러가 직접 읽는 `field_generators` 객체를 반드시 포함하고, key는 schema_draft.fields[].field_id, value는 지원 rule 문자열이어야 한다.
- 지원 rule 문법: literal:<고정 더미 문자열>, choice:<값1>|<값2>|<값3>, pool:<data_pools 이름>, same_as:<다른 field_id>, pattern:<# 숫자, A 대문자, a 소문자, * 영문대문자/숫자 패턴>, template:<문자열과 {{지원 rule}} 조합>, person.name_ko, person.phone_kr, person.rrn, date.kr, date.year, date.month, date.day, money.krw, business_reg_no, company.name_ko, medical.institution_ko, address.ko, free_text.short, checkbox.bool.
- `pool:<name>`을 쓰는 경우 faker_profile_draft.json의 `data_pools.<name>`에 반드시 실제 scalar 합성 값 배열을 함께 정의한다. 열린 scalar pool은 최소 20개, `pick_record`용 상관관계 record pool은 최소 12개의 다양하고 현실적인 값을 포함해야 하며, data_pools에 없는 pool 이름은 절대 쓰지 않는다.
- 법령/서식상 선택지가 고정된 작은 폐쇄형 pool만 `pool_policies.<name>={closed_set:true, exception_kind:'legal_or_form_closed_set', evidence:'...'}`와 근거를 명시해 최소 크기 예외로 인정한다. 단순히 자료를 충분히 만들지 못한 pool이나 현실의 개방형 record pool에는 이 예외를 사용하지 않는다.
- `date_between:`, `time|format:`, `decimal_range:`, `identifier.*`, `area.*`, `land_use.*`, `building.*`, `text.short`, `count_triplet`, `lot_number`, `page_count_label`처럼 현재 렌더러가 모르는 custom rule/type 이름은 field_generators 값으로 쓰지 않는다.
- 지원 문법만으로 정밀 형식을 표현하기 어렵다면 `pattern:`, `choice:`, `pool:`, `template:` 중 하나로 근사하고, 근사 사유와 원래 의도는 field_rules 또는 uncertainty_report에 기록한다.
- 의미가 불확실한 key는 literal:, choice:, pool: 등을 임의 생성하지 말고 보류 사유를 기록한다.
- 실제 개인정보, 실제 기업정보, 실제 계좌/식별번호처럼 오인 가능한 값은 만들지 않는다.
- 합성 더미 값 규칙 또는 승인된 value pool 참조만 사용한다.
- faker_profile_draft의 각 rule은 관련 schema key, anchor, research_report 근거 ID를 추적 가능하게 남긴다. 추적용 상세 목록은 선택적으로 `field_rules`에 중복 기록할 수 있지만, 최종 적용 기준은 `field_generators`이다.
- constraints의 각 항목도 관련 schema key, anchor, research_report 근거 ID를 `note`, `evidence_ids`, `field_rules` 중 하나에 추적 가능하게 남긴다.

## 지원 Faker relationship constraint 문법
- `pick_record`은 field 간 값 짝을 같은 레코드에서 뽑아야 할 때만 사용한다. 형식은 반드시 `{type:'pick_record', pool:'record_pool_name', targets:{field_id:'record_key', other_field_id:'other_record_key'}}`이다.
- `pick_record`의 `targets`는 반드시 `schema_draft.fields[].field_id -> data_pools.<pool>[] 객체의 key` 방향이다. `{record_key: field_id}` 방향으로 쓰지 않는다.
- `pick_record`의 레코드 목록은 constraint 내부 `records`에 넣지 않는다. 반드시 `faker_profile_draft.json.data_pools.<pool>`에 object 배열로 둔다. 예: `data_pools.diagnosis_records=[{name:'급성 기관지염', code:'J20.9'}]`.
- `pick_record`로 연결되는 field라도 `field_generators`에는 렌더러가 지원하는 안전한 기본 rule을 둔다. 다만 최종 값은 constraint가 같은 record에서 덮어쓴다.
- `copy`는 `{type:'copy', source:'source_field_id', target:'target_field_id'}`로 작성한다. source/target은 모두 schema binding field_id여야 한다.
- `exclusive_choice`는 `{type:'exclusive_choice', targets:[field_id...]}`로 작성하며 동일 그룹 체크박스 중 정확히 하나만 선택되어야 할 때 사용한다.
- `primary_secondary_group`은 수술 행별 주수술/부수술 체크박스에만 사용한다. 형식은 `{type:'primary_secondary_group', rows:[{primary:'수술1_주수술', secondary:'수술1_부수술'}, ...]}`이며 정확히 한 행만 주수술=true, 나머지는 부수술=true가 된다.
- `date_group`은 `{type:'date_group', year:'field_id', month:'field_id', day:'field_id', min_year:2020, max_year:2027}`로 작성해 분리된 연/월/일 bbox가 항상 유효한 한 날짜가 되게 한다. 템플릿에 `20` 같은 세기 prefix가 이미 인쇄되어 연도 bbox가 뒤 2자리만 받는 경우에만 `year_format:'yy'`를 추가한다.
- `date_order`는 `{type:'date_order', start:{year,month,day}, end:{year,month,day}, min_days:0, max_days:60}` 또는 start/end가 각각 단일 `date.kr` field_id인 형태로 작성해 종료일이 시작일보다 빠르지 않게 한다.
- `date_not_before`는 `{type:'date_not_before', source:'source_date_field_id', target:{year:'field_id', month:'field_id', day:'field_id'}, min_days:0, max_days:90}`로 작성해 target 날짜가 source 날짜보다 과거가 되지 않게 한다. source/target은 단일 date.kr field 또는 year/month/day group을 사용할 수 있다.
- `date_not_after`는 `{type:'date_not_after', target:'date_field_id', max:'as_of_date'}`로 작성해 target 날짜가 작업일보다 미래가 되지 않게 한다. target은 단일 date.kr field 또는 year/month/day group을 사용할 수 있고, max는 `as_of_date` 또는 다른 날짜 field/group이다.
- `sum`은 `{type:'sum', sources:[field_id...], target:'field_id', format:'money.krw'}`로 작성해 합계/소계/총액 bbox가 구성 항목의 합과 일치하게 한다.
- `numeric_range`는 `{type:'numeric_range', target:'field_id', min:0, max:20, decimals:2, suffix:'%'}`로 작성해 금리, 비율, 수량, 금액 등의 현실 범위를 제한한다.
- `numeric_compare`는 `{type:'numeric_compare', left:'equity_field_id', operator:'<=', right:'assets_field_id'}`로 작성해 두 숫자 field 사이의 대소 관계를 보장한다. operator는 `<`, `<=`, `>`, `>=`만 허용한다.
- `age_from_rrn`은 `{type:'age_from_rrn', rrn:'rrn_field_id', age:'age_field_id', issue:{year:'field_id', month:'field_id', day:'field_id'}}`로 작성해 발급일 기준 만 나이를 주민등록번호와 일치시킨다.
- 지원하지 않는 관계, 단일 문자열 내부의 복잡한 날짜 순서, 조건부 선택/복합 수식은 자연어 constraint로 쓰지 말고 uncertainty_report에 보류 사유와 필요한 bbox/schema 조정을 기록한다.

## 지원 Faker rule 문법
faker_profile_draft.json.field_generators 값은 아래 형식만 사용한다.
- `literal:<고정 더미 문자열>`
- `choice:<값1>|<값2>|<값3>`
- `pool:<data_pools 이름>`
- `same_as:<다른 field_id>`
- `pattern:<# 숫자, A 대문자, a 소문자, * 영문대문자/숫자 패턴>`
- `template:<문자열과 {{지원 rule}} 조합>`
- `person.name_ko`
- `person.phone_kr`
- `person.rrn`
- `date.kr`
- `date.year`
- `date.month`
- `date.day`
- `money.krw`
- `business_reg_no`
- `company.name_ko`
- `medical.institution_ko`
- `address.ko`
- `free_text.short`
- `checkbox.bool`

금지 예시: `date_between:-365d:+0d|format:%Y/%m/%d`, `time|format:%H:%M:%S`, `decimal_range:10..99`, `identifier.document_confirmation`, `area.square_meter`, `land_use.zoning`, `building.structure`, `text.short`, `count_triplet`, `lot_number`, `page_count_label`.

## DOCX/빈 템플릿 anchor 규칙
- PDF/JPG는 visible text, OCR, bbox 위치, 주변 텍스트를 anchor 근거로 삼는다.
- DOCX는 visible text, content control, form field, table cell, bookmark, placeholder 등 편집 가능한 anchor를 근거로 삼는다.
- DOCX 경로에서는 docx_template_analysis.json과 docx_anchor_map.json의 value_cell anchor를 schema field anchor_id/docx_anchor_id로 사용한다.
- DOCX 경로의 stylesheet는 이미지 렌더링용이 아니라 lineage 호환용이다. 실제 값 삽입은 원본 DOCX 셀 서식을 유지한 채 DOCX XML에 값을 주입한다.
- DOCX 경로의 GT는 PDF OCR 결과가 아니라 faker value set을 source of truth로 한다. 다만 현재 DOCX 경로는 LibreOffice 폰트 재현 품질 문제가 해결되기 전까지 실험/보류 기능이다.
- 숨은 메타데이터나 파일명만으로 schema key 또는 faker rule을 만들지 않는다.
- DOCX 경로에서는 원본 템플릿, 채워진 DOCX, 선택적 LibreOffice 렌더링 결과, GT lineage가 manifest에 남아야 한다. 외부 GUI 앱 자동화 렌더러는 사용하지 않는다.
- sample_kind가 blank_template이면 OCR/static label/keep bbox는 라벨 근거(label_anchor_ids)로만 쓰고 schema field의 anchor_id로 쓰지 않는다.
- sample_kind가 blank_template이면 schema field의 anchor_id는 반드시 리뷰에서 use로 확정된 값 입력 후보, 체크박스, 표 셀, manual bbox, visual_line_detect bbox 중 하나여야 한다.
- sample_kind가 blank_template이고 값 삽입 영역을 찾을 수 없으면 field를 만들지 말고 uncertainty_report에 남긴다.

## 적용/검수 정책
- 렌더러는 authoring 데이터를 임의 보정하지 않고 schema/style/faker/render_policy를 그대로 따른다.
- Agent 산출물은 바로 적용하지 않고 draft로 저장한다.
- 기존 authoring 파일을 덮어쓰기 전 사용자 승인과 백업 경로가 필요하다.
- UI 확정 전에는 schema_draft, faker_profile_draft, value_pool_draft, research_report, uncertainty_report를 함께 검토 가능해야 한다.

## 입력 파일
- sample: workbench/documents/선하증권(B_L)·항공운송장(AWB)__TRD-03/samples/original/선하증권.pdf
- latestReview: workbench/documents/선하증권(B_L)·항공운송장(AWB)__TRD-03/review/original_선하증권_page_001/review.json
- latestInpainted: workbench/documents/선하증권(B_L)·항공운송장(AWB)__TRD-03/inpaint/original_선하증권_page_001/lama/inpainted_lama.png
- visualEvidenceManifest: workbench/documents/선하증권(B_L)·항공운송장(AWB)__TRD-03/authoring/agent_requests/20260713T021916069057Z/visual_evidence_manifest.json
