# RPT-07 2차 authoring 적용 메모

- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았다.
- 26개 고정 binding마다 renderer 지원 문법의 generator를 정확히 하나씩 배정했다.
- 열린 scalar pool은 각 20개, 상관관계 `expense_records`는 12개로 구성했다. 값은 모두 테스트용 합성 데이터다.
- `pick_record`로 기안자·결재자·일자·금액·용도·첨부 문구를 한 레코드에서 선택하며, `copy`, `date_order`, `date_not_after`, `numeric_compare`, `sum`으로 핵심 관계를 추가 검증한다.
- 전체 템플릿 이미지 확인 결과 금액 셀에 정적 `원`이 없고 복합 문구 bbox는 접두·접미 문구까지 포함한다. 세부 판단은 `uncertainty_report.json`에 남겼다.

적용 전에는 문서번호/계좌번호 형식과 복합 문자열 필드의 분리 여부를 검토한다. 승인 후 draft 파일을 최종 authoring 파일로 승격하되, 기존 `schema.json`, `stylesheet.json`, `faker_profile.json`은 별도 백업 후 교체한다.
