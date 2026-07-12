# 수술기록지 MED-08 draft 생성 메모

요청 디렉터리 안에 `schema_draft.json`, `stylesheet_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`, `anchor_map_draft.json`을 생성/갱신했습니다.

전체 템플릿 이미지를 우선 근거로 사용했고, blank template 계약에 따라 OCR/keep 라벨은 `label_anchor_ids`로만 연결했습니다. schema field의 `anchor_id`는 review에서 `use`로 확정된 manual value-region anchor만 사용했습니다.

수술코드/수술명/수량/주수술/부수술은 요청대로 우선 3행만 작성했습니다. 재료처치는 재료/수량이 각각 큰 단일 bbox라서 export용 5행 hidden field와 실제 표시용 composite render field를 함께 두었습니다.

남은 확인 사항은 `uncertainty_report.json`에 정리했습니다. 특히 가산항목 값 목록, 나이 단위 포함 여부, 실제 수술코드 체계, 전신마취제 조건부 체크 관계는 적용 전 승인 또는 bbox/schema 조정이 필요합니다.

## 2026-07-09 특수 bbox 분할 보정

재료처치 영역의 `manual_1783577183603`(재료) 및 `manual_1783577225121`(수량)은 점선/가상 그리드 구조라 현재 OpenCV line detection으로 행 분리가 안정적으로 되지 않았습니다. 전역 blank-template 계약을 바꾸지 않고, 이번 MED-08 드래프트에서만 부모 bbox를 `split_source_region`으로 보존하고 5개 행별 value-region anchor를 추가했습니다.

- 재료: `manual_1783577183603_row01` ~ `manual_1783577183603_row05`
- 수량: `manual_1783577225121_row01` ~ `manual_1783577225121_row05`
- 기존 export용 hidden row + render-only composite 구조는 제거했고, 각 semantic row field가 고유 anchor를 직접 렌더/GT 대상으로 사용합니다.

## 2026-07-09 faker 품질 보강

- 주수술/부수술은 템플릿상 체크박스 컬럼이므로 체크박스 렌더링을 유지하되, `primary_secondary_group` constraint로 정확히 한 수술 행만 주수술이 되도록 변경했습니다.
- `재료처치 > 재료`는 수술 소모품/드레싱/배액관/봉합사/복강경 재료 등으로 pool을 확장했습니다.
- `마취재료`와 `주사처방`은 빈 free-text fallback 대신 전용 pool을 사용합니다.
- `마취시간`은 `마취료` 영역의 duration으로 해석하고 `20분`~`3시간` 범위의 소요시간 pool로 생성합니다.

