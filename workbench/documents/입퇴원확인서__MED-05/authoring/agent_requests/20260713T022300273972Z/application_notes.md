# MED-05 2차 authoring 초안

- 1차의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았다.
- 27개 고정 binding에 각각 하나의 지원 generator를 지정했다.
- 병명-질병분류기호 3쌍과 발병일-입원일-퇴원일-복합 표시값은 `pick_record`로 연결했다.
- 입원일 이전 발병, 퇴원일 이전 입원, 퇴원일 이전 발급, 기준일 이후 발급을 막는 날짜 constraint와 주민등록번호-만 나이 관계를 추가했다.
- record pool 2개와 scalar pool 2개를 각각 20개로 확장했다.
- 전체 서식 이미지에서 확인한 정적 `만( )세`, `년/월/일`, `제/호`는 생성값에서 제외했다.

## 승인 전 확인

1. `입원·퇴원구분`을 `입원|퇴원` 단일 선택으로 사용할지 확인한다.
2. 복합 표시값 `입원 YYYY-MM-DD / 퇴원 YYYY-MM-DD` 형식을 확인한다.
3. renderer의 `person.rrn`이 뒷자리를 마스킹하는지 확인한다.

승인 시 네 개 2차 산출물(`faker_profile_draft.json`, `value_pool_draft.json`, `uncertainty_report.json`, `application_notes.md`)만 적용 대상으로 사용한다. 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 이 작업에서 덮어쓰지 않았다.
