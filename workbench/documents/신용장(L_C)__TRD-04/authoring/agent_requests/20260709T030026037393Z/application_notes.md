# 신용장(L/C) TRD-04 authoring draft

요청 패키지와 원본 전체 이미지를 기준으로 `schema_draft.json`, `stylesheet_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`, `anchor_map_draft.json`을 생성했습니다.

- `sample_kind`가 `filled_sample`이므로 review에서 `use`로 확정된 bbox를 값 target으로 사용했습니다.
- 하단 `GLOBAL FIRST BANK` use anchor는 서명/푸터 인쇄 영역으로 판단해 schema에는 매핑하지 않고 `unmapped_use_anchors`와 uncertainty에 남겼습니다.
- 46A/71B/46D 조항은 현재 review에서 `keep` 정적 텍스트라 편집 필드로 만들지 않았습니다. 필요하면 UI에서 long-text value bbox를 수동 추가한 뒤 재승인하는 편이 안전합니다.
- faker는 renderer 지원 문법만 사용했습니다. 영문 날짜, USD 금액, 영문 금액 문구는 정밀 formatter가 없어 `pool:`/`template:` 기반 근사로 작성했습니다.

승인 전 확인할 부분은 amount words 동기화, 영문 날짜 포맷 지원 여부, 문서 요구사항/비용/추가조건 조항을 편집 가능한 필드로 확장할지 여부입니다.
