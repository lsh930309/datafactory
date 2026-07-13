# 적용 메모

+- 1차 pass의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았습니다.
+- 77개 고정 field_id 각각에 지원 문법 generator를 정확히 하나씩 배정했습니다.
+- 20개 합성 레코드의 `pick_record`로 신청인 헤더와 동일 필지 10개 연도 행을 함께 선택합니다. 가격 값에는 템플릿에 정적으로 인쇄된 `원/㎡`를 넣지 않습니다.
+- 접수일은 `2026-07-13` 이후가 되지 않도록 `date_not_after`를 적용했습니다. 공시일과 가격 기준연도는 레코드 안에서 일치시켰습니다.
+- 법인명/사업자등록번호 조건부 분기와 2페이지는 현재 schema·anchor 범위에서 지원하지 않고 uncertainty에 남겼습니다.

승인 시 네 개 pass-2 산출물을 함께 적용하고, 최종 파일 덮어쓰기는 UI 백업/승인 절차 이후 수행해야 합니다.
