# 여신신청서(APP-01) authoring draft 메모

- `schema_draft.json`, `stylesheet_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`, `anchor_map_draft.json`를 draft로 생성했습니다.
- 계약이 `blank_template`이므로 OCR/static label/keep bbox는 값 target으로 쓰지 않고 `label_anchor_ids` 또는 참고 anchor로만 사용했습니다.
- 필드 target은 `anchor_map_draft.json`에서 `status=use`이고 값 영역으로 확인된 anchor만 사용했습니다.
- 신청개요의 업체명, 대표자, 대출금액, 자금용도 등은 이미지에는 보이지만 현재 review 상태가 `keep`이라 draft schema에는 넣지 않았습니다. 사용하려면 해당 표 셀을 value-region/use로 승인해야 합니다.
- 백만원 단위 표의 금액 칸은 값 위치에 단위가 인쇄되어 있지 않고 표제에만 `(단위 : 백만원)`이 있으므로, faker 값에는 단위를 붙이지 않았습니다.
- 결재/감사 칸은 실제로 서명이나 도장이 필요할 수 있어 현재는 `free_text.short`로만 보수적으로 근사했습니다.

승인/적용 전 확인할 사항:
1. 상단 결재표의 `visual_0002` 빈 칸을 필드로 사용할지 여부.
2. `keep` 상태인 신청개요/업체개요 일부 표 셀을 value target으로 승격할지 여부.
3. 결재/감사 칸에 텍스트 대신 도장/서명 이미지 렌더링이 필요한지 여부.
