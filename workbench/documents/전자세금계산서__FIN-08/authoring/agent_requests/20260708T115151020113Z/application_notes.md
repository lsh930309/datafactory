# 전자세금계산서 FIN-08 authoring draft

생성 파일: `schema_draft.json`, `stylesheet_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`, `anchor_map_draft.json`.

전체 템플릿 이미지와 review의 `use` anchor를 기준으로 공급자, 공급받는자, 작성일자, 공급가액, 세액, 품목 명세, 결제 금액 칸을 모두 draft schema에 연결했습니다. 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 덮어쓰지 않았습니다.

불확실한 부분은 승인번호 세부 형식, 종사업장번호 공란 처리, 공급받는자 이메일 2줄의 역할, 수정사유 값, 2~4행 빈 품목 생성 여부, 결제수단 금액 분배입니다. 이 항목은 `uncertainty_report.json`에서 검토 후 승인/수정하면 됩니다.

faker generator는 현재 지원 문법만 사용했습니다. 금액 칸 주변에 별도 정적 단위가 보이지 않아 금액 값에는 `원` suffix를 넣지 않았습니다.
