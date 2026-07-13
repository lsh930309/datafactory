# COL-03 pass 2 적용 메모

- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았습니다.
- 57개 고정 바인딩마다 정확히 하나의 지원 `field_generators` 규칙을 배정했습니다.
- 열린 scalar pool은 각 20개, 관계형 record pool은 각 20개로 확장했습니다.
- 소재지·건축물 개요·건축물현황 4개 행·발급기관은 `pick_record`로 묶고, 날짜 상한과 핵심 면적 대소관계를 지원 constraint로 추가했습니다.
- 전체 템플릿에서 값 칸에 정적으로 보이는 `㎡`, `%`, `m`, `동` 단위는 faker 값에 중복하지 않았습니다.
- 시간 유효성, 식별번호 체크섬, 건폐율/용적률 나눗셈 산식, 2쪽 이후 완결성은 현재 renderer 계약으로 안전하게 표현할 수 없어 `uncertainty_report.json`에 남겼습니다.

적용 전 UI에서 `faker_profile_draft.json`, `value_pool_draft.json`, `uncertainty_report.json`을 함께 검토한 뒤 승인하십시오. 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 이 pass에서 덮어쓰지 않았습니다.
