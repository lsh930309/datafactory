# 전자세금계산서 pass 2 적용 메모

- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았습니다.
- 64개 고정 바인딩 각각에 지원 문법의 `field_generators`를 정확히 1개씩 배정했습니다.
- 공급자·공급받는자 레코드는 각각 12개, 품목 레코드는 20개, 작성일/품목일 세트는 12개로 확장했습니다. 모든 회사·연락처·사업자번호는 합성값이며 이메일은 `.example` 도메인을 사용합니다.
- 공급자/공급받는자 묶음, 품목 행 계산값, 작성일과 품목 월·일, 공급가액·세액·총액 합계를 renderer 지원 constraint로 연결했습니다.
- 전체 원본 이미지에서 금액 값 위치에 `원`이 인쇄되어 있지 않으므로 금액 generator는 단위를 붙이지 않습니다.
- 현재는 결제수단을 `현금 = 합계금액`, 나머지 0으로 제한합니다. 수정사유 조건부 표시, 복수 결제수단 임의 분할, 영세율/면세·반올림은 지원 grammar 한계로 `uncertainty_report.json`에 보류했습니다.

적용 전에는 UI에서 값 풀과 두 정책(수정사유 사용, 현금 전액 결제)을 검토한 뒤 draft 묶음을 승인하십시오. 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 이 작업에서 덮어쓰지 않았습니다.
