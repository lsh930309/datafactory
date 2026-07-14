# 2026-07-02 1차 납기: 수동 Authoring 1-cycle 작업 목표

> **폐기된 과거 범위 문서**: 이 문서의 고정 1차 범위와 진행률 정의는 더 이상 사용하지 않는다. 현재 분류 원천은 `registry/DEEP_Agent_문서분류_레지스트리_v2.2.xlsx`이며, 도메인은 3번째 시트 `2.업무분류`, 진척도는 `workbench/documents/` 상태만을 기준으로 한다.

작성일: 2026-06-29  
범위 정정일: 2026-06-30  
대상 프로젝트: DataFactory  
납기 목표: 2026-07-02까지 **웹 GUI의 1차 목표 문서 범위**(금융 20건 + 제조 10건 = scope entry 30건, 중복 2건 제거 후 unique 28종)에 대해 합성 가능/불가능을 판정하고, 가능한 문서부터 최소 1-cycle을 완성한다.

> **범위 정정 원칙(중요)**  
> 이 문서의 대상 범위는 더 이상 “이 문서가 처음 작성된 시점에 인페인팅이 완료되어 있던 문서”가 아니다.  
> 아래 고정 범위는 당시 기록 보존용이며 현재 코드나 운영 판단에는 사용하지 않는다.
> 인페인팅 완료 여부는 **작업 가능 상태/우선순위**일 뿐, 목표 범위를 결정하지 않는다.

## 1. 배경과 의사결정

기획팀 논의 결과, 7월 2일까지의 1차 목표는 완전 자동화 워크플로우 완성이 아니라 **가능한 문서에 대해 최소 합성 1-cycle을 우선 완성**하는 것으로 정한다.

현재 DataFactory는 다음 단계까지 실사용 가능한 흐름을 갖췄다.

```text
seed sample 적재
  -> PaddleOCR bbox 검출
  -> bbox review/classification/edit
  -> LaMa inpainting
  -> authoring draft / preview render 기반
```

다만 `schema`, `faker_profile`, `key name` 자동 생성은 아직 초안 품질이 낮고, 현재 일정에서는 모델 기반 자동화 고도화보다 **1차 목표 28종을 기준으로 문서별 가능/불가능을 판정한 뒤, 가능한 문서는 직접 시각 검수하여 schema + faker_profile을 완성**하는 편이 더 업무 우선도에 맞다.

따라서 이번 작업은 “가내수공업 방식”을 공식 작업 방식으로 인정하고, 문서별 1회성 수동 authoring을 통해 최소 GT 생성 cycle을 확보하는 데 집중한다. 특히 faker profile은 기존 템플릿이 없더라도 문서 의미에 맞는 `literal:`, `choice:`, `pattern:`, `template:`, `pool:`, `same_as:` 규칙과 `constraints`를 직접 창작해 정의한다. 필요한 경우 외부 공개 자료를 웹에서 수집해 간단한 data pool을 만들고, 해당 pool에서 랜덤 선택하는 방식까지 이번 작업 범위에 포함한다.

## 2. 1차 목표 정의

### 2.1 대상 범위: scope entry 30건 / unique 28종

- 기준 소스(폐기): 당시 수기 고정 범위
- 현재 기준: `registry/DEEP_Agent_문서분류_레지스트리_v2.2.xlsx`와 `workbench/documents/`
- scope entry: 금융 20건 + 제조 10건 = 30건
- 중복 문서: `FIN-01`, `RPT-08` 2건이 금융/제조 양쪽에 중복 등장
- 실제 unique 대상: **28종**
- 비대상 문서(`ID-01 사업자등록증` 등)는 기존 산출물이 있더라도 이번 목표 완료율에 포함하지 않는다.

#### 2.1.1 원본 scope entry 30건

| # | 분야 | doc_id | 문서명 | 비고 |
| ---: | --- | --- | --- | --- |
| 1 | 금융 | ID-03 | 주주명부 |  |
| 2 | 금융 | FIN-01 | 재무제표(재무상태표·손익계산서) | 중복 |
| 3 | 금융 | RPT-01 | 사업계획서·자금사용계획서 |  |
| 4 | 금융 | ADM-01 | 회의록(이사회·주총) |  |
| 5 | 금융 | CRD-01 | 신용정보조회서(NICE·KCB) |  |
| 6 | 금융 | CRD-02 | 기업신용등급평가서 |  |
| 7 | 금융 | RPT-02 | 여신 심사의견서 [산출물] |  |
| 8 | 금융 | COL-02 | 감정평가서 |  |
| 9 | 금융 | COL-05 | 공시지가확인원 |  |
| 10 | 금융 | ID-11 | 실소유자 확인서(AML) |  |
| 11 | 금융 | APP-13 | 계좌개설신청서 |  |
| 12 | 금융 | RPT-08 | 컴플라이언스 점검보고서 [산출물] | 중복 |
| 13 | 금융 | RPT-07 | 내부 심사·결재 문서 [산출물] |  |
| 14 | 금융 | SEC-03 | 투자성향·적합성 설문 |  |
| 15 | 금융 | APP-12 | 약관·상품설명서 |  |
| 16 | 금융 | SEC-01 | 투자설명서·증권신고서 |  |
| 17 | 금융 | FIN-11 | 감사보고서·결산보고서 |  |
| 18 | 금융 | LGL-02 | 판결문·결정문 |  |
| 19 | 금융 | RPT-06 | 타당성·시장조사 보고서 |  |
| 20 | 금융 | APP-14 | 카드발급신청서 |  |
| 21 | 제조 | TRD-07 | 발주서(PO)·거래명세서 |  |
| 22 | 제조 | ADM-04 | 산출내역서·견적서 |  |
| 23 | 제조 | QC-02 | 입고·검수 보고서 |  |
| 24 | 제조 | QC-01 | 품질·시험성적서 |  |
| 25 | 제조 | RPT-08 | 컴플라이언스 점검보고서 [산출물] | 중복 |
| 26 | 제조 | FIN-01 | 재무제표(재무상태표·손익계산서) | 중복 |
| 27 | 제조 | TRD-05 | 수출입신고필증 |  |
| 28 | 제조 | TRD-01 | 상업송장(Commercial Invoice) |  |
| 29 | 제조 | TRD-06 | 원산지증명서(C/O) |  |
| 30 | 제조 | TRD-02 | 포장명세서(Packing List) |  |

#### 2.1.2 작업 관리용 unique 대상 28종

| # | 분야 | doc_id | 문서명 |
| ---: | --- | --- | --- |
| 1 | 금융 | ID-03 | 주주명부 |
| 2 | 금융·제조 | FIN-01 | 재무제표(재무상태표·손익계산서) |
| 3 | 금융 | RPT-01 | 사업계획서·자금사용계획서 |
| 4 | 금융 | ADM-01 | 회의록(이사회·주총) |
| 5 | 금융 | CRD-01 | 신용정보조회서(NICE·KCB) |
| 6 | 금융 | CRD-02 | 기업신용등급평가서 |
| 7 | 금융 | RPT-02 | 여신 심사의견서 [산출물] |
| 8 | 금융 | COL-02 | 감정평가서 |
| 9 | 금융 | COL-05 | 공시지가확인원 |
| 10 | 금융 | ID-11 | 실소유자 확인서(AML) |
| 11 | 금융 | APP-13 | 계좌개설신청서 |
| 12 | 금융·제조 | RPT-08 | 컴플라이언스 점검보고서 [산출물] |
| 13 | 금융 | RPT-07 | 내부 심사·결재 문서 [산출물] |
| 14 | 금융 | SEC-03 | 투자성향·적합성 설문 |
| 15 | 금융 | APP-12 | 약관·상품설명서 |
| 16 | 금융 | SEC-01 | 투자설명서·증권신고서 |
| 17 | 금융 | FIN-11 | 감사보고서·결산보고서 |
| 18 | 금융 | LGL-02 | 판결문·결정문 |
| 19 | 금융 | RPT-06 | 타당성·시장조사 보고서 |
| 20 | 금융 | APP-14 | 카드발급신청서 |
| 21 | 제조 | TRD-07 | 발주서(PO)·거래명세서 |
| 22 | 제조 | ADM-04 | 산출내역서·견적서 |
| 23 | 제조 | QC-02 | 입고·검수 보고서 |
| 24 | 제조 | QC-01 | 품질·시험성적서 |
| 25 | 제조 | TRD-05 | 수출입신고필증 |
| 26 | 제조 | TRD-01 | 상업송장(Commercial Invoice) |
| 27 | 제조 | TRD-06 | 원산지증명서(C/O) |
| 28 | 제조 | TRD-02 | 포장명세서(Packing List) |

### 2.2 현재 로컬 workbench 스냅샷

집계일: 2026-06-30  
집계 기준: `workbench/documents/*/manifest.json`, `review/*/review.json`, `inpaint/*/lama/inpainted_lama.png`, `authoring/render_preview/preview_*.png`

| 상태 | 수량 | 의미 |
| --- | ---: | --- |
| `preview_done` | 13 | 범위 정정 후 유효 대상이며 수동 schema/faker/profile + preview 완료 |
| `ready_for_authoring` | 0 | review + LaMa 완료, 다음 수동 authoring 가능 |
| `blocked_no_inpaint` | 2 | review는 있으나 LaMa 인페인팅 필요 |
| `blocked_no_review` | 6 | 샘플/워크벤치가 있으나 bbox review부터 필요 |
| `blocked_no_sample` | 7 | 현재 workbench 샘플 없음 |

### 2.3 이번 납기의 완료 정의

문서 1종의 최소 1-cycle 완료 기준은 다음과 같다.

1. 해당 문서가 2.1의 28종 unique 대상에 포함된다.
2. 샘플 원본, review overlay, inpainted image, bbox review json을 확인한다.
3. 실제 치환 대상 bbox 각각에 대해 의미 있는 schema field를 정의한다.
4. 사람이 알아볼 수 있는 `field_id`, `label`, `export.json_path`, `export.csv_column`을 부여한다.
5. 각 field에 대해 즉시 렌더링 가능한 `faker_profile.field_generators` 규칙을 부여한다.
6. 문서 내부 정합성이 필요한 경우 `data_pools`와 `constraints`로 같은 record에서 값이 나오도록 연결한다.
7. 기존 기본 stylesheet 또는 현재 renderer가 읽을 수 있는 최소 stylesheet를 유지한다.
8. preview render를 1회 이상 생성한다.
9. preview image, kv json, bbox json, overlay, validation report가 생성된다.
10. 결과가 완벽하지 않더라도 “해당 문서 유형의 최소 합성 샘플 1건”으로 설명 가능해야 한다.
11. 스타일시트 중 `font-size`, `font-family`, `font-weight` 3가지를 제외한 문서 합성 필요 정보가 모두 구축되어 있어야 한다.

이번 단계에서 사용자가 직접 마무리할 stylesheet 항목은 `font-size`, `font-family`, `font-weight` 3가지로 제한한다. 그 외 schema field 정의, key naming, faker rule, value template, data pool, export key, bbox 매핑 등 문서 합성에 필요한 정보는 작업자가 직접 구축하는 것을 최종 목표로 한다.

## 3. 합성 불가능/불가능에 가까운 문서 판정 기준

다음 중 하나에 해당하면 이번 1차 납기에서는 “합성 보류/불가 후보”로 분류한다.

1. **샘플 문서 확보 불가**
   - 공개/내부 경로에서 실제 양식 또는 충분히 유사한 샘플 이미지를 구할 수 없음.
   - 샘플이 있어도 텍스트가 대부분 지워져 bbox/schema 추론 근거가 없음.

2. **단순 템플릿 + value set 주입으로 정의하기 어려움**
   - 수십 페이지 단위 문서처럼 한 장 템플릿으로 대표하기 어려움.
   - 페이지마다 layout과 의미 구조가 크게 달라 1-cycle 정의가 과도하게 커짐.
   - 반복 행/가변 페이지/긴 서술 문단이 핵심이며 현재 renderer의 고정 bbox 주입 방식으로 표현하기 어려움.

3. **시각적 품질 또는 GT 신뢰도 리스크가 지나치게 큼**
   - OCR/bbox/inpainting 결과가 너무 불안정해 수동 schema를 작성해도 preview가 문서처럼 보이지 않음.
   - 문서 구조상 어떤 bbox가 어떤 의미인지 사람이 봐도 확정하기 어려움.

불가/보류 문서는 단순 제외하지 않고, 반드시 다음 정보를 기록한다.

```text
문서명 / doc_id
보류 사유
샘플 확보 여부
현재 산출물 상태
향후 재시도 조건
```

## 4. 수동 Authoring 작업 방식

### 4.1 입력 산출물

문서별로 다음 파일을 함께 본다.

```text
workbench/documents/<문서폴더>/samples/original/*
workbench/documents/<문서폴더>/review/*/review.json
workbench/documents/<문서폴더>/review/*/review_overlay.png
workbench/documents/<문서폴더>/inpaint/*/lama/inpainted_lama.png
workbench/documents/<문서폴더>/inpaint/*/lama/comparison_lama.png
```

작업자는 원본/overlay/inpaint 결과를 시각적으로 대조하면서 `review.json`의 `status=use` bbox를 field 후보로 삼는다. bbox가 잘못되었거나 schema 작성에 부적합하면 해당 사실을 기록하고, 필요 시 GUI에서 bbox review를 먼저 수정한다.

### 4.2 작성 대상

이번 작업에서 직접 작성/수정할 핵심 파일은 다음 두 개다.

```text
workbench/documents/<문서폴더>/authoring/schema.json
workbench/documents/<문서폴더>/authoring/faker_profile.json
```

필요 시 faker profile용 보조 data pool도 문서별 또는 공용 리소스로 추가할 수 있다. 예를 들어 국내 상장기업명, 업종명, 은행명, 지역명, 관공서명, 주소 구성요소처럼 공개 자료 기반 값 목록이 필요하면 웹에서 출처를 확인해 간단한 dataset으로 만들고 faker rule이 이를 참조하도록 설계한다.

`stylesheet.json`은 이번 납기에서는 기본값 또는 기존 자동 생성값을 유지한다. 최종적으로 사용자가 직접 보정할 항목은 `font-size`, `font-family`, `font-weight` 3가지다. 단, preview가 전혀 판독 불가능할 정도로 정렬/overflow가 깨지는 경우에 한해 render_policy 또는 최소 stylesheet 속성을 수정할 수 있다.

### 4.3 schema 작성 원칙

- `field_id`는 사람이 읽을 수 있는 snake_case 영문 key를 쓴다.
- `label`은 한국어 업무 표시명을 쓴다.
- `source_text`는 원 OCR 또는 원문 값을 보존한다.
- `bbox`, `source_detection_id`, `source_image`, `source_inpainted`는 실제 산출물 기준으로 유지한다.
- `export.json_path`와 `export.csv_column`은 label이 아니라 의미 중심 key로 정리한다.
- 같은 문서 안에서 중복 의미가 있으면 역할을 key에 반영한다.
- 28종 범위 밖 문서에 작성된 산출물은 실험/참고 산출물로만 보고, 1차 목표 진행률에는 반영하지 않는다.

### 4.4 faker_profile 작성 원칙

- 현재 renderer가 즉시 처리 가능한 rule string을 우선 사용한다.
- 기본 rule 예시:
  - `person.name_ko`
  - `person.rrn`
  - `person.phone_kr`
  - `date.kr`
  - `money.krw`
  - `company.name_ko`
  - `address.ko`
  - `free_text.short`
  - `choice:남|여`
  - `literal:고정값`
  - `pattern:###-####-####`
  - `template:{company.name_ko}는 {date.kr}에 설립됨`
  - `pool:pool_name`
  - `same_as:other_field_id`
- 현재 faker 엔진이 표현하기 어려운 값은 우선 `literal:` 또는 `template:`로 1-cycle을 성립시킨다.
- 기존 템플릿이 없으면 작업자가 문서 의미에 맞는 문장/값 템플릿을 직접 창작한다.
- 선택형 값이나 실제 기관/기업/업종/지역 명단이 필요한 경우, 공개 웹 자료에서 간단한 data pool을 구축하고 `pool:` 또는 `constraints`로 연결한다. 외부 자료를 사용한 경우 출처와 수집일을 작업 로그에 남긴다.
- 문서 내부 정합성은 가능한 범위에서 `pick_record`, `copy`, `same_as`로 보장한다.
- 최종 목표는 `font-size`, `font-family`, `font-weight`를 제외하고 preview/render/export/GT 생성에 필요한 모든 의미 정보와 값 생성 정보를 완성하는 것이다.

## 5. 현재 28종 진행표

| doc_id | 문서명 | 분야 | 상태 | sample | review | inpaint | schema/faker | preview | fields | warnings | 판정/메모 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- |
| ID-03 | 주주명부 | 금융 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 10 | 0 | 범위 정정 후 유효 대상. 수동 schema/faker/profile + preview 완료. |
| FIN-01 | 재무제표(재무상태표·손익계산서) | 금융·제조 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 20 | 0 | 범위 정정 후 유효 대상. 수동 schema/faker/profile + preview 완료. |
| RPT-01 | 사업계획서·자금사용계획서 | 금융 | blocked_no_sample | 없음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 현재 workbench 샘플 없음. 샘플 수집/적재 필요. |
| ADM-01 | 회의록(이사회·주총) | 금융 | blocked_no_review | 있음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 샘플/워크벤치 있음. bbox review부터 필요. |
| CRD-01 | 신용정보조회서(NICE·KCB) | 금융 | blocked_no_sample | 없음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 현재 workbench 샘플 없음. 샘플 수집/적재 필요. |
| CRD-02 | 기업신용등급평가서 | 금융 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 14 | 0 | 범위 정정 후 유효 대상. 수동 schema/faker/profile + preview 완료. |
| RPT-02 | 여신 심사의견서 [산출물] | 금융 | blocked_no_sample | 없음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 현재 workbench 샘플 없음. 샘플 수집/적재 필요. |
| COL-02 | 감정평가서 | 금융 | blocked_no_review | 있음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 샘플/워크벤치 있음. bbox review부터 필요. |
| COL-05 | 공시지가확인원 | 금융 | blocked_no_sample | 없음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 현재 workbench 샘플 없음. 샘플 수집/적재 필요. |
| ID-11 | 실소유자 확인서(AML) | 금융 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 27 | 0 | 범위 정정 후 유효 대상. 수동 schema/faker/profile + preview 완료. |
| APP-13 | 계좌개설신청서 | 금융 | blocked_no_inpaint | 있음 | 있음 | 없음 | 미작성 | 미생성 | - | - | bbox review 있음. LaMa 인페인팅 후 authoring 가능. |
| RPT-08 | 컴플라이언스 점검보고서 [산출물] | 금융·제조 | blocked_no_review | 있음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 샘플/워크벤치 있음. bbox review부터 필요. |
| RPT-07 | 내부 심사·결재 문서 [산출물] | 금융 | blocked_no_sample | 없음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 현재 workbench 샘플 없음. 샘플 수집/적재 필요. |
| SEC-03 | 투자성향·적합성 설문 | 금융 | blocked_no_inpaint | 있음 | 있음 | 없음 | 미작성 | 미생성 | - | - | bbox review 있음. LaMa 인페인팅 후 authoring 가능. |
| APP-12 | 약관·상품설명서 | 금융 | blocked_no_sample | 없음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 현재 workbench 샘플 없음. 샘플 수집/적재 필요. |
| SEC-01 | 투자설명서·증권신고서 | 금융 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 10 | 0 | page 1 대표 cycle 완료. 전체 67쪽 합성은 다중 페이지/산문형 보류 후보. |
| FIN-11 | 감사보고서·결산보고서 | 금융 | blocked_no_review | 있음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 샘플/워크벤치 있음. bbox review부터 필요. |
| LGL-02 | 판결문·결정문 | 금융 | blocked_no_review | 있음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 샘플/워크벤치 있음. bbox review부터 필요. |
| RPT-06 | 타당성·시장조사 보고서 | 금융 | blocked_no_sample | 없음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 현재 workbench 샘플 없음. 샘플 수집/적재 필요. |
| APP-14 | 카드발급신청서 | 금융 | blocked_no_review | 있음 | 없음 | 없음 | 미작성 | 미생성 | - | - | 샘플/워크벤치 있음. bbox review부터 필요. |
| TRD-07 | 발주서(PO)·거래명세서 | 제조 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 45 | 0 | 발주서 1쪽 1-cycle 완료. PO/거래처/품목/금액/합계 정합성 profile 적용. |
| ADM-04 | 산출내역서·견적서 | 제조 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 120 | 0 | 견적서 1쪽 1-cycle 완료. 12개 품목/소계/VAT/합계 정합성 profile 적용. |
| QC-02 | 입고·검수 보고서 | 제조 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 72 | 0 | 빈 양식 기반 수동 bbox 72개 1-cycle 완료. 입고수량/품질/불량격리 정합성 profile 적용. |
| QC-01 | 품질·시험성적서 | 제조 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 60 | 0 | 품질검사 성적서 1쪽 1-cycle 완료. 접수/채취/발행일 및 치수시험 결과 정합성 profile 적용. |
| TRD-05 | 수출입신고필증 | 제조 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 64 | 0 | 수출신고필증 1쪽 1-cycle 완료. 신고번호/일자/품목/금액/중량/수리일자 정합성 profile 적용. |
| TRD-01 | 상업송장(Commercial Invoice) | 제조 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 28 | 0 | 상업송장 1쪽 1-cycle 완료. 송장번호/일자/L/C/거래조건/품목 수량·단가·금액 정합성 profile 적용. |
| TRD-06 | 원산지증명서(C/O) | 제조 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 37 | 0 | 한미 FTA C/O 1쪽 1-cycle 완료. 수출자/생산자/수입자/blanket period/품목·HS·원산지 기준 정합성 profile 적용. |
| TRD-02 | 포장명세서(Packing List) | 제조 | preview_done | 있음 | 있음 | 있음 | 작성 | 생성 | 57 | 0 | 포장명세서 1쪽 1-cycle 완료. 포장수/품목수량/순중량/총중량/CBM 합계 정합성 profile 적용. |

## 6. 최종 산출 범위와 사용자 잔여 작업

이번 수동 authoring 작업이 완료된 문서는 다음 정보가 모두 준비되어 있어야 한다.

- bbox와 schema field의 의미 매핑
- 사람이 읽을 수 있는 `field_id`, `label`, `json_path`, `csv_column`
- 각 field의 faker rule 또는 직접 창작한 value template
- 필요한 경우 공개 자료 기반 data pool과 그 참조 규칙
- preview render에 필요한 base image, bbox, render policy, export 구조
- KV JSON과 bbox GT가 의미 있는 key로 생성되는 상태

사용자가 후속으로 직접 보정할 항목은 stylesheet의 다음 3가지로 한정한다.

1. `font-size`
2. `font-family`
3. `font-weight`

## 7. 작업 우선순위

1. 2.1의 28종 unique 대상만 작업 범위로 삼는다.
2. 이 중 `ready_for_authoring` 문서부터 수동 schema/faker를 작성한다.
3. `blocked_no_inpaint`는 LaMa 인페인팅을 먼저 완료한 뒤 authoring한다.
4. `blocked_no_review`는 bbox 검출/review부터 수행한다.
5. `blocked_no_sample`은 샘플 수집 또는 불가 사유 기록을 우선한다.
6. 산문/보고서형, 수십 페이지 문서, 자유서술 중심 문서는 합성 가능/불가능 판정을 먼저 기록하고 가능한 절충안을 명시한다.
7. `ID-01 사업자등록증`처럼 이미 산출물이 있는 비대상 문서는 별도 참고 산출물로 보존하되 이번 1차 목표 완료율에서 제외한다.

## 8. 진행 기록 방식

수동 작업 중 각 문서의 상태는 별도 진행표 또는 작업 로그에 다음 형식으로 기록한다.

| doc_id | 문서명 | 상태 | 샘플 | review | inpaint | schema/faker | preview | 판정/메모 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FIN-01 | 재무제표 | preview_done | 있음 | 있음 | 있음 | 작성됨 | 생성됨 | 범위 정정 후 유효 대상 |

상태값은 다음 중 하나를 사용한다.

- `ready_for_authoring`: 28종 대상이며 inpaint까지 완료되어 schema/faker 작성 가능
- `authoring_done`: schema/faker 작성 완료
- `preview_done`: preview render 완료
- `blocked_no_sample`: 28종 대상이나 샘플 없음
- `blocked_no_review`: 샘플/워크벤치가 있으나 bbox review 없음
- `blocked_no_inpaint`: review는 있으나 LaMa inpainting 없음
- `blocked_too_complex`: 다페이지/복잡 구조로 1차 보류
- `blocked_quality`: OCR/bbox/inpaint 품질 문제로 보류
- `out_of_scope`: 28종 밖 문서. 기존 산출물 보존 가능하나 목표 완료율 제외

## 9. 이번 문서의 역할

진행 상황의 공식 기록 파일은 사용자 요청에 따라 프로젝트 루트에 새로 만든 `20260702_first_priority_authoring_progress.md`로 둔다. `docs/reports/archive/20260702_manual_authoring_progress_corrected.md`와 `.bin/20260702_manual_authoring_progress.md`는 동일 범위를 반영하는 보조/이전 호환 파일로만 취급한다.

이 문서는 7월 2일 1차 납기 전까지의 작업 판단 기준과 완료 기준을 고정하는 루트 목표 문서다. 이후 실제 문서별 schema/faker 작성은 이 기준에 따라 진행하며, 자동화 고도화 계획은 별도 후속 phase로 미룬다.
