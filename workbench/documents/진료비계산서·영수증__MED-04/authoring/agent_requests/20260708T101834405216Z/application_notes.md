# 적용 메모

- `schema_draft.json`, `stylesheet_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`, `anchor_map_draft.json` 초안을 생성했습니다.
- 현재 샘플은 빈 서식이므로 OCR 텍스트는 정적 라벨 근거로만 사용했고, schema field의 `anchor_id`는 리뷰에서 `use`로 잡힌 값 영역만 사용했습니다.
- 전체 템플릿 이미지 기준으로 값 위치에 `원` 같은 정적 단위가 인쇄되어 있지 않아 금액 faker 값은 `money.krw`만 지정했습니다.
- 사업자등록번호, 상호, 전화번호, 사업장소재지는 라벨은 보이지만 확정 값 anchor가 없어 draft schema에는 넣지 않고 uncertainty에 남겼습니다.
- 적용 전 UI에서 날짜 파트 위치와 `unmapped_use_anchors`를 확인한 뒤 최종 `schema.json` 등으로 승격하면 됩니다.
