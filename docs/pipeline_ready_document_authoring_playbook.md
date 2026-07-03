# 작업 가능 문서 Pipeline-Ready Authoring 지침

작성일: 2026-07-01  
기준 사례: `ID-03 주주명부`  
목적: [작업 가능] 문서들을 한 번에 한 문서씩, 실제 샘플 기반 합성 데이터 대량 생성이 가능한 상태로 준비한다.

## 1. 기본 원칙

1. **문서는 반드시 한 번에 1종만 진행한다.**
   - 여러 문서를 병렬 처리하지 않는다.
   - 한 문서의 입력 상태 확인 → bbox/schema/faker/style/render → 검증 → 기록을 마친 뒤 다음 문서로 넘어간다.
2. **주주명부 방식처럼 원본 샘플의 시각 정보를 우선한다.**
   - 원본 이미지, review overlay, inpainted template, render preview, 50% overlay를 함께 본다.
   - crop 수치 최적화는 스타일 판단을 왜곡할 수 있으므로 기본 루틴에서 제외한다.
3. **문서별 별도 작업 기록 md를 반드시 남긴다.**
   - 위치: 프로젝트 루트 또는 `docs/manual_authoring/` 중 문서별 맥락에 맞게 택하되, 작업자가 바로 찾을 수 있게 명확히 명명한다.
   - 문서 ID, 문서명, 대표 샘플, 입력 산출물, schema/faker/style 판단 근거, render 결과, 남은 리스크를 기록한다.
4. **font-family는 렌더링 결과물의 시각 정보로 고른다.**
   - 후보: Apple SD Gothic Neo, Malgun Gothic, Gulim, Batang 등 현재 환경에서 렌더링 가능한 폰트.
   - 자동 crop diff가 아니라 전체 문서의 자연스러움, 원본과의 농도/폭/서체 인상, overlay를 근거로 선택한다.
5. **필요한 bbox는 원본에 값이 없어도 문서 구조상 필요하면 추가한다.**
   - 표/그리드/반복행 구조가 있으면 값이 비어 있는 행·열도 생산용 schema에 확장할 수 있다.
   - 단, 확장 근거와 범위를 기록한다.

## 2. 문서 1종 작업 순서

### 2.1 입력 상태 점검

문서별 workbench 디렉터리에서 다음을 확인한다.

- `manifest.json`
- `samples/original/*.{jpg,png,pdf}`
- `review/*/review.json`, `review_overlay.png`
- `inpaint/*/inpainted_lama.png` 또는 cleanup 결과
- 기존 `authoring/schema.json`, `stylesheet.json`, `faker_profile.json`, `render_preview/*`

상태가 부족하면 다음 순서로 보완한다.

1. 샘플만 있음 → bbox detect/review 필요
2. bbox review 완료 → LaMa inpaint 필요
3. inpaint 완료 → authoring 생성 가능
4. authoring 있음 → schema/style/faker 보정 및 batch render

### 2.2 schema 작성/보정

- field_id는 문서 의미가 분명하게 드러나도록 영문 snake_case로 작성한다.
- `label`은 한국어 업무 용어로 작성한다.
- `bbox`는 xywh 픽셀 좌표를 사용한다.
- `render_policy`는 최소한 `align`, `valign`, `overflow`를 포함한다.
- 표/그리드는 `groups`에 row_count, columns, grid 좌표 또는 확장 근거를 남긴다.
- 원본에 값이 적어도 문서가 반복 구조라면 생산 목적상 행/열을 확장한다.

### 2.3 faker_profile 작성/보정

- 가능한 경우 record 단위 pool을 사용해 문서 내 필드 간 일관성을 유지한다.
  - 예: 회사명-주소-대표자, 계좌번호-은행명, 금액 합계, 평가 점수-성향 등.
- 긴 문장/비고/사유는 문서 유형별 문장 템플릿 pool을 만든다.
- 값 생성은 우선 deterministic seed로 재현 가능하게 유지한다.
- 빈 값이 실제 문서에서 자연스러운 경우 빈 값도 pool에 포함할 수 있다.

### 2.4 stylesheet 보정

- 기본 판단 순서:
  1. 원본 전체 이미지의 문서 장르와 인쇄 상태 확인
  2. 후보 font-family로 preview 생성
  3. 원본 / inpainted / render / 50% overlay를 전체 화면에서 비교
  4. font-size, opacity, align, letter_spacing을 조정
- crop 비교/통계는 기본 루틴에서 제외한다.
- 서체가 완전히 같지 않아도 문서 전체에서 튀지 않는 쪽을 우선한다.
- 필요 시 style_class를 역할별로 나눈다.
  - header, table_label, table_value, amount, footer, signature 등.

### 2.5 render 및 QA

- 단일 preview와 overlay 생성.
- 최소 5장 batch 생성.
- batch contact sheet 생성.
- validation warning 0개를 목표로 한다.
- 원본과 비교해 특히 다음을 확인한다.
  - bbox 밖으로 텍스트가 삐져나오지 않는지
  - 빈 행/빈 값이 불필요한 bbox annotation을 만들지 않는지
  - 표/선/도장/배경과 합성 텍스트 농도가 너무 튀지 않는지
  - 문서 내 데이터 관계가 깨지지 않는지

## 3. 문서별 작업 기록 형식

문서별 md에는 최소 다음 항목을 포함한다.

```md
# YYYY-MM-DD DOC-ID 문서명 Pipeline-Ready Authoring 기록

## 목표
## 입력 상태
## 원본 시각 분석
## schema/bbox 결정
## faker_profile 결정
## stylesheet 결정
## 산출물
## 검증 결과
## 남은 리스크 / 다음 보정 포인트
```

## 4. 주주명부에서 고정된 교훈

- 원본에 데이터가 1행만 있어도 표 구조가 명확하면 생산용 bbox/key는 전체 표로 확장한다.
- crop diff 최적화는 때로 전체 문서의 자연스러움을 해친다. 이후 스타일 보정은 전체 이미지와 overlay 중심으로 한다.
- `opacity`, `letter_spacing`은 renderer가 실제로 지원해야 의미가 있으므로 stylesheet 속성과 renderer 동작을 함께 검증한다.
- font-family는 수치가 아니라 최종 렌더링의 시각 인상으로 판단한다.
- 매 반복마다 산출물과 판단 근거를 md에 남겨 다음 문서 작업의 기준점을 만든다.

## 5. 현재 다음 대기열

2026-07-01 현재 우선 대기열은 다음 순서로 처리한다.

1. `RPT-07 내부 심사·결재 문서 [산출물]` — 인페인팅 완료로 기록되어 있어 authoring 착수 우선.
2. `APP-13 계좌개설신청서` — bbox review 완료, 인페인팅부터 필요.
3. `SEC-03 투자성향·적합성 설문` — bbox review 완료, 인페인팅부터 필요.
4. `APP-14 카드발급신청서` — 샘플만 있음, bbox detect부터 필요.

각 문서는 반드시 순차 처리한다.
