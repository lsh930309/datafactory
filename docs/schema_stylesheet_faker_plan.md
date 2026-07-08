# Schema · Stylesheet · Faker-Format 고도화 계획

작성일: 2026-06-29

## 0. 현재 위치와 다음 병목

현재 DataFactory는 다음 단계까지 실사용 가능한 흐름을 갖췄다.

```text
실문서 seed 적재
  -> PaddleOCR precise bbox 검출
  -> bbox review/classification/edit
  -> use bbox 기반 LaMa inpainting
  -> 빈 템플릿 이미지 확보
```

즉, 지금까지는 완성된 실제 문서 이미지에서 치환할 영역을 골라 “구멍을 뚫고 배경을 복원하는” 단계였다. 다음 단계는 그 빈 영역에 어떤 값을, 어떤 스키마 키로, 어떤 스타일로 렌더링할지 정하는 것이다.

핵심 병목은 3개다.

1. **schema**: 문서 bbox와 데이터 key/value/label export 구조의 매핑.
2. **stylesheet**: 원본 문서와 비슷한 폰트, 크기, 색, 정렬, 줄간격, 자간, 패딩, overflow 정책 추정.
3. **faker-format**: LLM 서빙 없이도 문서별 값 집합을 만들고, 문서 내부 key 간 유효성을 유지하는 생성 규칙.

v1의 현실적 목표는 완전 자동화가 아니라 **자동 초안 + GUI 승인/수정 + deterministic render/export**다. GT 정확도가 중요하므로 확산 모델 기반 text editing은 기본 렌더러가 아니라 장기 실험 후보로 둔다.

---

## 1. 조사 요약과 적용 판단

### 1.1 Schema / KIE 쪽 참고점

- **LayoutLMv3**는 텍스트와 이미지 패치의 정렬을 학습하는 Document AI 모델이며, form/receipt/document QA/layout analysis 등 문서 이해 task에서 강점을 보인다. 우리에게는 “text bbox + layout + semantic key”를 함께 관리해야 한다는 구조적 근거가 된다.
- **DocILE**은 business document의 Key Information Localization and Extraction(KILE)과 Line Item Recognition(LIR)을 분리해 다룬다. 특히 55개 클래스, line item, zero/few-shot layout을 고려한다는 점이 법인등기부등본/증명서류처럼 다양한 문서군에 중요하다.
- **SROIE**는 receipt OCR/KIE의 고전적 벤치마크로, OCR text와 key-value extraction을 분리해 평가하는 흐름을 참고할 수 있다.
- **PaddleOCR 3.0**은 PP-OCRv5, PP-StructureV3, PP-ChatOCRv4를 통해 OCR, hierarchical parsing, key information extraction을 다룬다. 현재 DataFactory가 이미 PaddleOCR을 쓰고 있으므로 장기적으로 layout/KIE 초안 생성 후보로 가장 자연스럽다.

적용 판단:

- v1 schema는 딥러닝 KIE 모델을 바로 학습하지 않는다.
- 대신 `review.json`의 bbox를 사람이 승인한 field candidate로 승격하고, 이 구조가 나중에 LayoutLM/Paddle KIE 학습 데이터로도 변환 가능하도록 둔다.

### 1.2 Document synthesis 쪽 참고점

- **Donut/SynthDoG**는 OCR-free document understanding을 위해 synthetic document generator를 함께 제안했다. 핵심 시사점은 합성 문서도 “문서 구조와 GT를 먼저 알고 있는 생성”이 중요하다는 점이다.
- **DocSynth** 계열 연구도 layout, text, visual realism을 함께 고려한 synthetic document 생성의 필요성을 보여준다.
- **DocLayNet/PubLayNet/DocBank**는 layout annotation이 문서 도메인 일반화에 중요함을 보여준다.

적용 판단:

- DataFactory는 “이미지부터 생성”하지 않고, 실제 seed 이미지에서 인페인팅된 template을 만들고 그 위에 deterministic renderer로 값을 얹는다.
- 따라서 layout 자체는 실제 문서에서 가져오되, field schema와 generated value GT는 우리가 완전히 통제하는 방향이 적합하다.

### 1.3 Stylesheet 추출 쪽 참고점

- **DeepFont**는 이미지에서 font를 식별하는 대표 연구지만, 실제 문서 이미지의 작은 한글/숫자/스캔 노이즈에 곧바로 안정 적용하기는 어렵다.
- AnyText/TextDiffuser 같은 diffusion 기반 text editing은 배경과 자연스러운 합성에는 강하지만, KIE 학습용 GT에서는 글자 정확도/작은 폰트/숫자/표선 위 렌더링 안정성이 리스크다.

적용 판단:

- v1 stylesheet는 ML 모델이 아니라 **픽셀 통계 + 후보 폰트 fitting + GUI 보정**으로 간다.
- 완전 자동 스타일 복원이 아니라, “대부분 맞는 초안”을 만들고 작업자가 빠르게 보정한다.

### 1.4 Faker-format / Constraint 쪽 참고점

- Faker `ko_KR` provider는 이름, 주소, 우편번호 등 한국어 기반 기본 생성에 쓸 수 있다.
- Faker만으로는 주민등록번호-생년월일, 회사명-대표자-주소, 발급일-만료일, 금액 합계 같은 cross-field consistency를 보장하지 못한다.
- SDV의 Constraint-Augmented Generation(CAG) 개념처럼 생성값을 constraint에 맞게 변환/검증/거절하는 계층이 필요하다.
- Pydantic validator는 schema/model 단위 검증을 구현하기 좋은 후보지만, 런타임 의존성 추가는 구현 단계에서 별도 판단한다.

적용 판단:

- v1은 `faker provider + document context + constraints + retry/repair` 구조를 쓴다.
- 긴 문장은 LLM 없이 `clause template + slot filling + weighted variants`로 시작한다.

---

## 2. 목표 산출물 구조

문서별 workbench 산출물을 다음처럼 확장한다.

```text
workbench/documents/<문서제목_slug>__<문서ID>/
  samples/original/...
  ocr/...
  review/...
  inpaint/...
  authoring/
    schema.json
    stylesheet.json
    faker_profile.json
    render_preview/
      preview_000001.png
      preview_000001.kv.json
      preview_000001.bbox.json
      preview_000001.overlay.png
  manifest.json
```

세 파일의 역할은 명확히 분리한다.

| 파일 | 목적 | 사람이 자주 만지는가 |
| --- | --- | --- |
| `schema.json` | bbox와 key/value/export 구조 매핑 | 자주 |
| `stylesheet.json` | 텍스트 렌더링 스타일 후보/확정값 | 초기에 자주 |
| `faker_profile.json` | 값 생성 규칙, context, constraints | 문서 유형별로 가끔 |

---

## 3. Schema 설계 초안

### 3.1 최소 구조

`review.json`의 `status=use` bbox를 schema field candidate로 승격한다.

```json
{
  "schema_version": 1,
  "doc_id": "registry-doc-id",
  "title": "가족관계증명서",
  "source_review": "workbench/.../review.json",
  "source_inpainted": "workbench/.../inpaint/.../inpainted_lama.png",
  "fields": [
    {
      "field_id": "person_name",
      "label": "성명",
      "bbox": [320, 512, 180, 36],
      "bbox_format": "xywh",
      "source_detection_id": "det_000123",
      "source_text": "홍길동",
      "value_type": "person.name_ko",
      "generator": "context.person.primary.name",
      "style_class": "body_10pt_black_left",
      "render_policy": {
        "align": "left",
        "valign": "middle",
        "fit": "shrink_to_fit",
        "overflow": "clip"
      },
      "export": {
        "json_path": "person.name",
        "csv_column": "person_name"
      },
      "required": true,
      "notes": ""
    }
  ],
  "groups": []
}
```

### 3.2 field_id 원칙

- 사람이 알아볼 수 있는 snake_case를 사용한다.
- 같은 문서 안에서 중복되지 않는다.
- 레이블명 그대로가 아니라 데이터 의미를 적는다.
  - 좋음: `applicant_name`, `issue_date`, `company_registration_number`
  - 나쁨: `field_001`, `성명1`

### 3.3 groups

반복 표/라인아이템은 v1에서 완전 자동화하지 않는다. 대신 수동 정의 가능한 group만 둔다.

```json
{
  "group_id": "shareholder_rows",
  "kind": "repeating_rows",
  "row_count": 5,
  "fields": ["shareholder_name", "share_count", "share_ratio"]
}
```

v1에서는 group을 렌더링 힌트/관리 단위로만 사용하고, 동적 행 추가/삭제는 v2로 미룬다.

---

## 4. Stylesheet 설계 초안

### 4.1 목표

원본 문서의 특정 bbox에 있던 텍스트 스타일을 다음 속성으로 근사한다.

```json
{
  "schema_version": 1,
  "doc_id": "registry-doc-id",
  "source_image": "...original.jpg",
  "style_classes": [
    {
      "style_class": "body_10pt_black_left",
      "font_family": "Apple SD Gothic Neo",
      "font_path": "/System/Library/Fonts/...",
      "font_size": 28,
      "fill": [34, 34, 34],
      "opacity": 1.0,
      "align": "left",
      "valign": "middle",
      "line_spacing": 1.15,
      "letter_spacing": 0,
      "baseline_shift": 0,
      "confidence": 0.72,
      "source_detection_ids": ["det_000123", "det_000124"]
    }
  ]
}
```

### 4.2 자동 추출 후보 알고리즘

1. **foreground color 추정**
   - 원본 bbox 내부에서 배경보다 어두운 픽셀을 foreground 후보로 잡는다.
   - median/trimmed mean RGB를 계산한다.
   - 너무 밝거나 bbox가 빈 경우 기본값 `[32, 32, 32]`을 쓴다.
2. **font size 추정**
   - OCR text와 bbox 높이/폭을 기준으로 후보 크기 범위를 잡는다.
   - 후보 폰트별 `ImageDraw.textbbox()` 결과가 원래 bbox에 가장 잘 맞는 크기를 고른다.
3. **font family 후보 선택**
   - v1 후보: Apple SD Gothic Neo, NanumGothic, Noto Sans CJK KR, Arial Unicode류.
   - 문서별로 후보 ranking을 저장하고, GUI에서 확정 가능하게 한다.
4. **정렬 추정**
   - bbox와 주변 라벨/표선을 기준으로 left/center/right를 추정하되, v1은 기본 left로 둔다.
   - 숫자/금액 필드는 right 후보를 더 높게 둔다.
5. **style clustering**
   - 비슷한 font_size/color/height의 field를 같은 `style_class`로 묶는다.
   - field마다 style을 직접 저장하지 않고 `style_class`를 참조하게 해 수정 비용을 줄인다.

### 4.3 GUI 보정 UX

- field 선택 시 style preview를 보여준다.
- 후보 폰트/크기/color/align을 바꾸면 canvas에 즉시 렌더링한다.
- “이 스타일을 같은 class 전체에 적용” 버튼을 둔다.
- 자동 confidence가 낮은 style class를 우선 검수 목록 상단에 노출한다.

---

## 5. Faker-format 설계 초안

### 5.1 생성 계층

값 생성은 field 단위 난수 호출이 아니라 문서 context 생성 후 field가 context를 참조하는 방식으로 한다.

```json
{
  "schema_version": 1,
  "doc_id": "registry-doc-id",
  "locale": "ko_KR",
  "contexts": {
    "person.primary": {
      "provider": "person_kr",
      "fields": ["name", "rrn", "birth_date", "address", "phone"]
    },
    "company.primary": {
      "provider": "company_kr",
      "fields": ["name", "registration_number", "corporate_number", "representative", "address"]
    }
  },
  "field_generators": {
    "person_name": "context.person.primary.name",
    "rrn": "context.person.primary.rrn",
    "issue_date": "date.issue_after_birth"
  },
  "constraints": [
    {
      "type": "rrn_matches_birth_date",
      "rrn": "rrn",
      "birth_date": "birth_date"
    },
    {
      "type": "date_order",
      "before": "issue_date",
      "after": "expiry_date"
    }
  ]
}
```

### 5.2 기본 provider 분류

| value_type | v1 전략 |
| --- | --- |
| `person.name_ko` | Faker ko_KR + 성/이름 후보 사전 보강 |
| `person.rrn` | 자체 생성기. 생년월일/성별/검증자리 정책 포함 |
| `person.phone_kr` | Faker/자체 mobile pattern |
| `address.ko` | Faker ko_KR road/land address 기반, 필요 시 행정구역 사전 보강 |
| `company.name_ko` | 업종/법인 suffix 후보 사전 기반 자체 생성기 |
| `company.registration_number` | 사업자등록번호 형식 + checksum 옵션 |
| `company.corporate_number` | 법인등록번호 형식 + checksum 옵션 |
| `money.krw` | 범위/천단위/한글금액 변환 옵션 |
| `date.kr` | format, min/max, relative rule |
| `legal_clause` | clause template + slot filling |
| `free_text.short` | template fragments |
| `free_text.long` | paragraph grammar |

### 5.3 긴 문장 생성 전략

법인등기부등본/계약서/증명서 문장처럼 긴 텍스트는 다음처럼 처리한다.

1. **문장 family 정의**
   - 예: `registration.purpose_change`, `executive.appointment`, `address.transfer`
2. **clause template 작성**
   - 예: `본 회사는 {date} 주주총회의 결의에 의하여 {purpose}을/를 사업목적에 추가한다.`
3. **slot generator 연결**
   - `{date}`는 context date, `{purpose}`는 업종/사업목적 사전.
4. **길이/줄바꿈 fitting**
   - bbox 폭에 맞춰 word wrap하고, line count가 넘으면 다른 template 또는 축약형으로 retry.
5. **문서 내부 consistency 유지**
   - 같은 회사명/대표자/주소/날짜는 context에서 재사용.

### 5.4 Constraint 실행 방식

생성기는 다음 순서를 따른다.

```text
context seed 생성
  -> field value materialize
  -> constraints validate
  -> 실패 시 repair 가능한 rule repair
  -> repair 불가 시 retry
  -> 최종 values + validation report 저장
```

v1 acceptance:

- 실패한 constraint를 숨기지 않는다.
- preview/export 산출물에 `validation_report.json`을 남긴다.
- hard failure가 있으면 batch export를 중단하거나 해당 sample을 reject한다.

---

## 6. Rendering / Export 계획

### 6.1 렌더 입력

```text
inpainted_lama.png
schema.json
stylesheet.json
faker_profile.json
random_seed
```

### 6.2 렌더 출력

```text
render_preview/
  sample_000001.png
  sample_000001.kv.json
  sample_000001.bbox.json
  sample_000001.overlay.png
  sample_000001.validation_report.json
```

### 6.3 bbox GT 정책

- GT bbox는 원래 schema bbox가 아니라 **실제로 렌더링된 텍스트 bbox**를 기준으로 저장한다.
- `requested_bbox`도 함께 저장해 style/fit 실패를 검수할 수 있게 한다.
- overflow가 발생한 field는 `validation_report`에 기록한다.

### 6.4 CSV/JSON label export

초기에는 JSON을 canonical로 둔다.

```json
{
  "sample_id": "sample_000001",
  "doc_id": "registry-doc-id",
  "values": {
    "person": {
      "name": "김민준",
      "rrn": "900101-1******"
    }
  },
  "flat_values": {
    "person_name": "김민준",
    "rrn": "900101-1******"
  }
}
```

CSV는 `flat_values` 기반으로 부가 export한다.

---

## 7. 웹 GUI 흐름

현재 GUI 단계 뒤에 다음 authoring 단계를 추가한다.

```text
BBox 검출
  -> Review & classification
  -> LaMa inpainting
  -> Schema 매핑
  -> Style 보정
  -> Faker/value preview
  -> Render/export
```

### 7.1 Schema 매핑 화면

- `use` bbox 목록을 field candidate로 표시.
- bbox 선택 시 `field_id`, `label`, `value_type`, `export path`를 입력/수정.
- OCR source_text를 참고로 보여준다.
- 자주 쓰는 value_type preset을 버튼/검색으로 제공.

### 7.2 Style 보정 화면

- 선택 field에 generated sample value를 임시 렌더링.
- font/size/color/align을 즉시 preview.
- 같은 style_class에 일괄 적용.
- low confidence style 우선 검수.

### 7.3 Faker/value preview 화면

- `Generate values` 버튼으로 values JSON preview.
- constraint pass/fail 표시.
- 긴 문장 field는 여러 후보를 보여주고 하나를 선택 가능.

### 7.4 Render/export 화면

- 단일 preview render.
- bbox overlay render.
- batch count 지정 후 export.
- 실패 sample/rejected sample 수 표시.

---

## 8. 구현 로드맵

### Phase A. 문서/스키마 authoring 기반

목표: 수동으로라도 schema/stylesheet/faker_profile을 만들고 preview render 가능.

- `authoring/` 산출물 경로 추가.
- `review.json -> schema draft` 변환.
- 최소 `stylesheet.json` 생성: 기본 font/color/align.
- 최소 `faker_profile.json` 생성: Faker ko_KR + basic provider.
- CLI preview render 1장 생성.

성공 기준:

- 한 문서에서 `use` bbox 3~5개를 field로 매핑해 preview image/kv/bbox가 생성된다.

### Phase B. 스타일 추출 초안

목표: 원본 스타일과 유사한 초안 자동 생성.

- foreground color 추정.
- 후보 폰트/크기 fitting.
- style_class clustering.
- GUI style preview/수정.

성공 기준:

- 작업자가 font size/color를 매번 직접 입력하지 않아도 대부분의 필드가 원본과 큰 차이 없이 렌더링된다.

### Phase C. constraint-aware faker

목표: 문서 내부 데이터 유효성 유지.

- document context 생성기.
- 주민등록번호/전화/주소/회사/금액/날짜 provider.
- constraint validate/retry/repair.
- validation report export.

성공 기준:

- 생년월일-주민번호, 날짜 순서, 금액 합계 같은 기본 rule이 깨진 sample은 export되지 않는다.

### Phase D. 긴 문장/반복 영역

목표: 법인등기부등본류의 장문 필드와 표/반복행 처리.

- clause template registry.
- slot filling + weighted variants.
- bbox fitting retry.
- repeating group 수동 정의.

성공 기준:

- 긴 문장 field가 bbox 안에서 줄바꿈/축약/retry를 통해 안정적으로 들어간다.

### Phase E. 고급 자동화 후보

목표: 필요한 경우만 ML/LLM 후보를 보조 도구로 평가.

- PaddleOCR PP-Structure/PP-ChatOCR 기반 field label 후보 추출 실험.
- diffusion text editing 후보는 GT 정확성 비교 실험으로만 유지.
- 충분한 수동 schema가 쌓이면 문서 유형별 schema suggestion 모델 검토.

---

## 9. 리스크와 대응

| 리스크 | 대응 |
| --- | --- |
| 스타일 자동 추출이 부정확함 | style_class preview + 빠른 수동 보정 우선 |
| 폰트가 원본과 완전히 다름 | 후보 폰트 목록과 문서별 기본 폰트 override 저장 |
| 긴 문장이 bbox를 넘침 | template variant retry, shrink_to_fit, wrap, reject 정책 |
| Faker 값이 현실성이 낮음 | 도메인 사전/provider를 프로젝트 내에 누적 |
| cross-field consistency 붕괴 | context-first 생성 + constraint validation |
| schema 작성 공수가 큼 | OCR source_text, label 후보, registry title을 활용한 자동 초안 |
| diffusion text editing이 GT를 훼손 | 기본 경로에서 제외하고 실험 후보로만 유지 |

---

## 10. 참고 자료

- LayoutLMv3: https://arxiv.org/abs/2204.08387
- Donut / SynthDoG: https://arxiv.org/abs/2111.15664
- DocILE: https://arxiv.org/abs/2302.05658
- SROIE: https://arxiv.org/abs/2103.10213
- PaddleOCR 3.0 Technical Report: https://arxiv.org/abs/2507.05595
- DocLayNet: https://arxiv.org/abs/2206.01062
- DeepFont: https://arxiv.org/abs/1507.03196
- AnyText: https://arxiv.org/abs/2311.03054
- TextDiffuser: https://arxiv.org/abs/2305.10855
- Faker ko_KR provider docs: https://faker.readthedocs.io/en/master/locales/ko_KR.html
- Faker standard providers: https://faker.readthedocs.io/en/master/providers.html
- SDV Constraint-Augmented Generation: https://docs.sdv.dev/sdv/concepts/constraint-augmented-generation-cag
- Pydantic validators: https://docs.pydantic.dev/latest/concepts/validators/

---

## 11. 다음 구현 제안

바로 다음 개발 단위는 **Phase A: schema authoring 기반**이 적합하다.

최소 구현 단위:

1. `review.json`의 `use` bbox에서 `authoring/schema.json` 초안 생성.
2. 기본 `stylesheet.json`과 `faker_profile.json` 생성.
3. CLI/API에서 단일 preview render를 생성.
4. GUI에 “Schema 초안 생성 → field_id/value_type 수정 → preview render” 화면을 붙인다.

이 단위가 완성되면, 현재의 인페인팅 결과물이 처음으로 “값을 주입해서 GT와 함께 합성 이미지로 출력 가능한 템플릿”이 된다.

### 2026-07-08 구현 메모: 제한형 relational constraints

Agent authoring 산출물의 `faker_profile.json`은 기존 `field_generators` 문법을 그대로 유지하되, field 간 데이터 정합성은 `constraints` 배열로 별도 표현한다. 현재 렌더러가 실제 적용하고 draft validator가 허용하는 constraint 타입은 아래 6개로 제한한다.

- `pick_record`: object record pool에서 한 레코드를 뽑아 여러 field에 일관 반영한다.
- `copy`: 한 field 값을 다른 field로 복사한다.
- `exclusive_choice`: 동일 그룹 체크박스 중 정확히 하나만 선택한다.
- `date_group`: 분리된 `year/month/day` bbox가 하나의 유효 날짜를 이루게 한다.
- `date_order`: 시작일/종료일처럼 두 날짜 그룹의 선후 관계를 보장한다.
- `sum`: 소계/합계/총액 field가 source field들의 합과 일치하게 한다.

MED-04 `진료비계산서·영수증`처럼 금액 행/열 합계, 본인부담/공단부담/총액, 진료기간 시작/종료일, 문서구분 체크박스 상호배타가 중요한 양식은 agent가 faker profile 작성 시 위 constraint를 반드시 검토해야 한다. 지원하지 않는 자연어 수식이나 임의 DSL은 사용하지 않고 `uncertainty_report.json`에 보류 사유를 남긴다.
