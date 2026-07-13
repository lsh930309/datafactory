# MED-04 2차 authoring 메모

- 1차의 `schema_draft.json`, `anchor_map_draft.json`, `stylesheet_draft.json` 구조와 169개 바인딩을 그대로 유지했습니다.
- 모든 바인딩에 정확히 하나의 지원 generator를 부여했고, 금액 열 합계·납부수단 합계·날짜 유효성/순서·기관정보 레코드 일관성·택일 체크박스를 지원 constraint로 추가했습니다.
- `departments`는 24개 scalar, `provider_records`는 20개 완전 합성 record로 구성했습니다. 기관명·주소·전화·대표자·체크섬 사업자번호는 동일 레코드에서 선택됩니다.
- 전체 템플릿에서 날짜의 `년/월/일`은 정적 접미사로 확인되어 생성값에 포함하지 않았고, 금액 칸에는 `원`을 중복 추가하지 않았습니다.
- 환자부담총액/납부할금액/미납금의 차감식과 입원-퇴원·중간의 조건부 선택은 현재 지원 constraint로 정확히 표현할 수 없어 `uncertainty_report.json`에 보류했습니다.
- 적용 전 UI에서 JSON 검증 결과와 보류 항목을 확인한 뒤 draft 일괄 승인하십시오. 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 이 작업에서 덮어쓰지 않았습니다.
