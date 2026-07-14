# FIN-05 validation repair notes

- 기계 검증에서 누락된 `faker_profile_draft.json`, `value_pool_draft.json`, `application_notes.md`를 요청 디렉터리 안에 생성했습니다.
- `faker_profile_draft.json.field_generators`는 기존 `schema_draft.json.fields`의 field_id 190개를 그대로 사용하며, 렌더러가 지원하는 rule 문법만 배정했습니다.
- `pool:<name>` rule은 새로 만들지 않아 추가 value pool 최소 크기 의무를 발생시키지 않았습니다.
- `det_000023`, `det_000024`는 이미 use/value_region으로 매핑된 앵커였으나 `auto_type`만 `static_label`이라 blank-template 검증에서 탈락했습니다. field/semantic path/evidence를 삭제하지 않고 `anchor_map_draft.json`의 해당 `auto_type`만 `field_value`로 보정했습니다.
- 웹 리서치와 원본 이미지 재확인은 수행하지 않았고, source evidence와 기존 schema/style/anchor 관계는 보존했습니다.

## Targeted revision

- 원본 1쪽 표를 다시 대조하여 `발행자 보고용`을 체크박스 선택지로, 소득자 식별번호·종사업장 일련번호를 실제 입력값 유형으로 바로잡았습니다.
- 금액 표의 잘못된 체크박스/자유문자열 규칙을 `money.krw`로 통일하고, 행 합계가 원천 열의 합과 일치하도록 `sum` 제약을 추가했습니다.
- 근무처명·사업자등록번호·기간의 합계 열은 실제 합산 대상이 아니므로 binding과 anchor coverage는 유지하되 `render:false`와 빈 literal 규칙으로 공란 처리했습니다.

## Employment-state simulation revision

- 현재 고용이력·세액 레코드는 종전근무지, 선택적 비과세·감면 항목, 기납부세액을 함께 선택합니다. 유효하지 않은 표 칸은 빈 문자열로 두고, 보이지 않는 공제·세액공제 입력값은 임의로 추가하지 않습니다.

## Residency, nationality, and richer scenario revision

- `거주지국/거주지국코드`, `국적/국적코드`는 12개 `residency_nationality_records`에서 한 번에 선택합니다. 국가명과 ISO 3166-1 숫자 코드를 같은 레코드에 두고, 거주자/비거주자 및 내국인/외국인 체크도 함께 설정해 서로 모순되지 않게 했습니다.
- 기존의 8자리 임의 코드 패턴은 3자리 국가 코드 기본값으로 교체했습니다. 서로 다른 거주지국과 국적을 가질 수 있는 합성 사례도 포함하되, 국내 국적자는 대한민국/410으로 일치시킵니다.
- 고용이력 레코드는 표 합계와 세액 관계를 같은 레코드 안에서 유지하면서도, 모든 칸을 채우지 않는 다양한 근로소득 상태를 표현합니다.

## User-requested employment and blank-cell revision

- `employment_history_tax_records` 12개 합성 레코드로 기본 시나리오를 교체했습니다. 종전근무지 수는 0개·1개·2개가 모두 확률적으로 선택되며, 2개인 경우 `종(전) 1`은 항상 더 오래된 종료일, `종(전) 2`는 그 다음 종료일의 근무지입니다.
- 비과세 및 감면소득명세의 국외근로·야간근로수당·보육수당·출산지원금·연구보조비는 매 레코드에서 최소 2개 항목에 유효 금액을 배정합니다. 미발생 항목과 다른 유효값 없는 표 칸은 `0` 대신 빈 문자열로 렌더링합니다.
- canonical bbox review와 재대조하여 삭제된 `visual_0067`, `visual_0074`, `visual_0237`은 제거하고, review에 `use`로 남아 있는 농어촌특별세 bbox(`manual_1783992911760`)는 복원했습니다. 해당 값이 없을 때는 `0` 대신 공란을 출력합니다.
- 문서 하단 `징수(보고)의무자 서명 또는 인` bbox는 징수의무자 대표자 성명을 재사용하도록 연결해 유효한 합성 값을 항상 주입합니다.
