# CRD-01 2차 authoring 초안 적용 메모

- 1차의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았다.
- 53개 고정 binding 모두에 renderer 지원 문법의 `field_generators`를 정확히 하나씩 배정했다.
- 개설·발급 2개 행과 대출 8개 행은 `pick_record`로 상품/기관 조합을 묶었다. record pool은 각각 최소 12개를 충족한다.
- 대출 금액 pool은 24개이며, 전체 이미지에 `(단위: 천원)`이 정적으로 인쇄되어 있어 생성 값에는 단위를 넣지 않았다.
- 등록사유발생일자는 `date_not_after`로 기준일 `2026-07-13` 이후가 되지 않게 했다.
- 발급일시는 기준일을 따르는 `date.kr`과 유효 시각 pool을 결합했고, 주민등록번호는 유효 생년월일·세기/성별 숫자 뒤를 마스킹한 20개 pool로 구성했다.

적용 전에는 UI에서 `faker_profile_draft.json`의 합성 기관명과 상품 조합, 주민등록번호 마스킹 정책을 검토한다. 승인 후 draft를 최종 authoring 파일에 반영하며, 이 요청 디렉터리의 초안은 원본 최종 파일을 덮어쓰지 않는다.
