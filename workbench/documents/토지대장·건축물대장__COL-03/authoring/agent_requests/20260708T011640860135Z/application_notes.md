# COL-03 authoring draft notes

- 요청 패키지 기준으로 `schema_draft.json`, `stylesheet_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`, `anchor_map_draft.json`를 생성했습니다.
- `contract.sample_kind`는 `filled_sample`이므로 리뷰에서 `use`로 확정된 값 영역과 수동 value_region을 schema target으로 사용했습니다.
- 기존 final authoring 파일(`schema.json`, `stylesheet.json`, `faker_profile.json`)은 수정하지 않았습니다.
- 현재 입력 샘플은 건축물대장 1쪽입니다. 토지대장 전용 항목은 현재 샘플 anchor가 없어 schema에 추가하지 않았습니다.
- 면적/거리/부속건축물의 빈 수동 영역은 generator를 지원 grammar(`template`, `choice`)로만 근사했으며, 정밀 단위와 자리수는 `uncertainty_report.json`에서 승인 확인 대상으로 남겼습니다.
- 적용 전 UI에서 `status_row_1_floor`의 OCR(`z1층`), 담당자/부서명 표기, 마스킹 등록번호 자리수를 확인하는 것이 좋습니다.
