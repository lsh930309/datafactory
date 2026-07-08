# 여신거래약정서 APP-02 authoring draft

요청 패키지의 `filled_sample` 기준으로 1페이지 review `use` 앵커 14개를 모두 schema field에 매핑했습니다. 라벨/문맥 bbox는 `label_anchor_ids`와 `anchor_map_draft.json`의 keep/static evidence로만 보존했습니다.

생성된 초안은 약정일, 여신과목, 여신한도액, 여신자명/주소, 금융기관명 포함 약정 체결 문구, 거래기간 만료일, 이율, 연체배상금률, 이자 지급일을 포함합니다. 긴 문장 bbox는 사용자 지시대로 `****` 위치만 합성 금융기관명으로 치환하는 `template:` generator로 작성했습니다.

불확실한 부분은 `uncertainty_report.json`에 남겼습니다. 특히 여신과목, 금액 범위, 이율/연체배상금률 범위는 업무 승인용 pool 초안이며, 원본 PDF 2페이지의 서명란/추가 값은 이번 request의 reviewed use anchor가 없어 스키마에 추가하지 않았습니다.

적용 전에는 UI에서 `schema_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`을 함께 검토하고 승인하면 됩니다. 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 덮어쓰지 않았습니다.
