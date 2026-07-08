# Agentic Authoring Request: 토지대장·건축물대장 (COL-03)

## 목표
문서 이미지/OCR/BBox review와 실제 문서 리서치 근거를 사용해 authoring 초안을 A-to-Z로 생성한다.
산출물은 즉시 적용하지 않는 draft이며, UI에서 사용자 승인/수정/백업 후 확정한다.

## 사용자 지시
(추가 지시 없음)

## 입력 문서 컨텍스트
- 제목: 토지대장·건축물대장
- 문서 ID: COL-03
- PO 도메인: 금융, 공공, 건설
- 업무 도메인: 건설·부동산, 공공·행정 (B2G), 금융 - 은행 (여신·신용·외환)

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
- KIE 관점의 key-value hierarchy만 작성한다.
- 모든 value는 빈 문자열로 둔다.
- key는 실제 문서에 보이는 라벨, 표제, placeholder, 주변 텍스트, 편집 가능한 anchor 기반 한국어 자연어를 우선한다.
- 문서에 보이지 않는 추상 키, 업무 추론만으로 만든 키, downstream 편의용 임의 구조체를 만들지 않는다.
- 웹 리서치로 발견한 일반 항목이라도 대응 anchor가 없으면 schema_draft에 자동 추가하지 않는다.

## Faker profile 규칙
- schema key의 의미가 충분히 명확하고 문서 anchor 또는 리서치 근거와 연결될 때만 faker rule을 제안한다.
- 문서 필드의 의미와 실제 작성 관행을 근거로 타입, 형식, 값 범위, 선택지, 단위, 날짜/금액/식별번호 규칙을 제안하되, 반드시 현재 DataFactory 렌더러가 지원하는 rule 문법만 사용한다.
- faker_profile_draft.json에는 렌더러가 직접 읽는 `field_generators` 객체를 반드시 포함하고, key는 schema_draft.fields[].field_id, value는 지원 rule 문자열이어야 한다.
- 지원 rule 문법: literal:<고정 더미 문자열>, choice:<값1>|<값2>|<값3>, pool:<data_pools 이름>, same_as:<다른 field_id>, pattern:<# 숫자, A 대문자, a 소문자, * 영문대문자/숫자 패턴>, template:<문자열과 {{지원 rule}} 조합>, person.name_ko, person.phone_kr, person.rrn, date.kr, money.krw, company.name_ko, address.ko, free_text.short, checkbox.bool.
- `date_between:`, `time|format:`, `decimal_range:`, `identifier.*`, `area.*`, `land_use.*`, `building.*`, `text.short`, `count_triplet`, `lot_number`, `page_count_label`처럼 현재 렌더러가 모르는 custom rule/type 이름은 field_generators 값으로 쓰지 않는다.
- 지원 문법만으로 정밀 형식을 표현하기 어렵다면 `pattern:`, `choice:`, `pool:`, `template:` 중 하나로 근사하고, 근사 사유와 원래 의도는 field_rules 또는 uncertainty_report에 기록한다.
- 의미가 불확실한 key는 literal:, choice:, pool: 등을 임의 생성하지 말고 보류 사유를 기록한다.
- 실제 개인정보, 실제 기업정보, 실제 계좌/식별번호처럼 오인 가능한 값은 만들지 않는다.
- 합성 더미 값 규칙 또는 승인된 value pool 참조만 사용한다.
- faker_profile_draft의 각 rule은 관련 schema key, anchor, research_report 근거 ID를 추적 가능하게 남긴다. 추적용 상세 목록은 선택적으로 `field_rules`에 중복 기록할 수 있지만, 최종 적용 기준은 `field_generators`이다.

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
- `money.krw`
- `company.name_ko`
- `address.ko`
- `free_text.short`
- `checkbox.bool`

금지 예시: `date_between:-365d:+0d|format:%Y/%m/%d`, `time|format:%H:%M:%S`, `decimal_range:10..99`, `identifier.document_confirmation`, `area.square_meter`, `land_use.zoning`, `building.structure`, `text.short`, `count_triplet`, `lot_number`, `page_count_label`.

## DOCX/빈 템플릿 anchor 규칙
- PDF/JPG는 visible text, OCR, bbox 위치, 주변 텍스트를 anchor 근거로 삼는다.
- DOCX는 visible text, content control, form field, table cell, bookmark, placeholder 등 편집 가능한 anchor를 근거로 삼는다.
- 숨은 메타데이터나 파일명만으로 schema key 또는 faker rule을 만들지 않는다.
- DOCX 경로에서는 원본 템플릿, 채워진 DOCX, 렌더링 PDF, 페이지 이미지, bbox/label/GT lineage가 manifest에 남아야 한다.
- sample_kind가 blank_template이면 OCR/static label/keep bbox는 라벨 근거(label_anchor_ids)로만 쓰고 schema field의 anchor_id로 쓰지 않는다.
- sample_kind가 blank_template이면 schema field의 anchor_id는 반드시 리뷰에서 use로 확정된 값 입력 후보, 체크박스, 표 셀, manual bbox, visual_line_detect bbox 중 하나여야 한다.
- sample_kind가 blank_template이고 값 삽입 영역을 찾을 수 없으면 field를 만들지 말고 uncertainty_report에 남긴다.

## 적용/검수 정책
- 렌더러는 authoring 데이터를 임의 보정하지 않고 schema/style/faker/render_policy를 그대로 따른다.
- Agent 산출물은 바로 적용하지 않고 draft로 저장한다.
- 기존 authoring 파일을 덮어쓰기 전 사용자 승인과 백업 경로가 필요하다.
- UI 확정 전에는 schema_draft, faker_profile_draft, value_pool_draft, research_report, uncertainty_report를 함께 검토 가능해야 한다.

## 입력 파일
- sample: workbench/documents/토지대장·건축물대장__COL-03/samples/original/건축물대장.pdf
- latestReview: workbench/documents/토지대장·건축물대장__COL-03/review/original_건축물대장_page_001/review.json
- latestInpainted: workbench/documents/토지대장·건축물대장__COL-03/inpaint/original_건축물대장_page_001/lama/inpainted_lama.png
