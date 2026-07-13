# CRD-02 Pass 2 적용 메모

- Pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았다.
- 15개 고정 binding 각각에 렌더러 지원 generator를 정확히 하나씩 지정했다.
- 12개 완전 합성 record pool로 기업명, 대표자, 등록번호, 주소, 세 날짜, 등급, 등급 설명을 함께 선택하도록 구성했다.
- 전체 템플릿에서 값 위치에 별도 단위가 없음을 확인해 faker 값에 중복 단위를 넣지 않았다. 날짜 표기는 원본처럼 `YYYY년 MM월 DD일`을 사용한다.
- 사업자등록번호는 checksum을 만족하도록 만들었고, 모든 날짜는 작업일 `2026-07-13` 이후가 되지 않도록 제한했다.
- 단일 문자열 날짜 사이의 선후관계는 지원 constraint로 직접 표현할 수 없어 record pool에서 `결산일 <= 평가일 <= 유효기한`을 보장했다.
- 적용 전 UI에서 `faker_profile_draft.json`, `value_pool_draft.json`, `uncertainty_report.json`을 함께 승인하고, 최종 `faker_profile.json` 교체는 별도 백업 후 수행한다.
