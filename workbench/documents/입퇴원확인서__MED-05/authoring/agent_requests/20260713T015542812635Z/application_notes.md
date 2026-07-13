# MED-05 2차 authoring 초안

기존 semantic schema, field ID, 의미 경로, 가시 앵커, style/research 초안은 유지했다. 검증 복구 단계에서 숨김 primary 날짜 필드 2개에 기존 입·퇴원연월일 bbox에서 파생한 비렌더 전용 앵커를 각각 연결해, 가시 composite 필드와의 앵커 중복만 해소했다.

- 27개 binding 각각에 renderer 지원 generator를 정확히 1개씩 지정했다.
- 병명과 질병분류기호는 20개 합성 record pool에서 같은 행 단위로 선택한다.
- 발병일·입원일·퇴원일·복합 표시문구는 20개 입퇴원 record에서 함께 선택한다.
- 발급일은 유효한 연월일이며 퇴원일보다 빠르지 않고 기준일 `2026-07-13`을 넘지 않도록 제한했다.
- 주민등록번호와 만 나이는 `age_from_rrn`으로 연결했다.
- 전체 이미지에서 확인한 정적 `만( )세`, `년/월/일`, `제/호`는 생성값에 중복하지 않는다.

승인 전에는 `uncertainty_report.json`의 세 항목을 확인해야 한다. 특히 `person.rrn`의 뒤 6자리 마스킹, 단일 bbox 복합 입퇴원 기간 렌더링, `입원·퇴원구분` 값 표기 관행을 검토한다.

적용 시 이 요청 디렉터리의 draft 파일을 함께 검토한 뒤 UI 승인·백업 절차를 거쳐야 하며, 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 이 단계에서 덮어쓰지 않는다.
