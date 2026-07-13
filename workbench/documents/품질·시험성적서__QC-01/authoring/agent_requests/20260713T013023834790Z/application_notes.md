# QC-01 2차 authoring 초안

고정된 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않고 faker와 관계 산출물만 확장했습니다.

- 60개 binding 모두에 지원 문법의 `field_generators`를 정확히 하나씩 지정했습니다.
- 치수는 전체 원본 이미지에서 값 뒤의 `mm`가 실제 값 표기의 일부임을 확인해 단위를 포함한 풀을 사용했고, 규격별 범위와 `내경 < 외경 < 길이` 관계를 제약으로 추가했습니다.
- `채취일 <= 접수일 <= 발행일 <= 2026-07-13`, 책임기술인·시험검사자의 성명/서명 일치, 두 시험군 담당자 일치를 지원 제약으로 반영했습니다.
- 열린 scalar pool은 최소 20개를 충족합니다. 실제 개인·기업·연락처·자격번호는 포함하지 않았습니다.
- 날짜 출력 구두점, 국가중요시설 조건부 시설명, 제품 규격과 표 열의 조건부 연동, 2페이지 완결성은 현재 렌더러/요청 범위로 확정할 수 없어 `uncertainty_report.json`에 남겼습니다.

적용 전 UI에서 불확실성 항목을 검토한 뒤 draft 묶음을 승인하십시오. 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 이 작업에서 덮어쓰지 않았습니다.
