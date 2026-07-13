# Pass 2 생성 메모

+- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았습니다.
+- 37개 고정 binding 각각에 renderer 지원 generator를 정확히 1개씩 배정했습니다.
+- 당사자/연락처/주소/날짜는 12개 합성 record pool, 품목 3개 행은 20개 합성 product record pool을 사용합니다.
+- 품목 record는 품명, 수량과 단위, HS 번호, 특혜 원산지 기준, 원산지 국가를 함께 선택합니다.
+- 전체 이미지에서 `Quantity & Unit` 셀에 단위가 값과 함께 들어가므로 `pcs`, `units`, `sets`, `m`를 faker 값에 포함했습니다. 다른 품목 열에는 정적 단위 suffix가 없습니다.
+- 포괄기간은 0~365일 순서를 보장하고 모든 날짜는 2026-07-13 이후가 되지 않도록 제한했습니다.

## 검토 및 적용

1. `uncertainty_report.json`의 HS/원산지 기준 법적 검증 범위와 서명 이미지 필요 여부를 확인합니다.
2. UI에서 draft 4종을 함께 검토한 뒤 승인합니다.
3. 승인 전에는 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`에 적용하지 않습니다.
