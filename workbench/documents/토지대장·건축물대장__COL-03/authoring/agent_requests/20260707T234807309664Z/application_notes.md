# 적용 메모 - COL-03 토지대장·건축물대장

- 요청 패키지 기준 `sample_kind`는 `filled_sample`이며, 참조 샘플은 `일반건축물대장(갑)` page 1 OCR/review anchor입니다.
- `schema_draft.json`은 review/manual에서 `use`로 확인된 page 1 value anchor만 field target으로 사용했습니다. 값은 모두 빈 문자열입니다.
- `faker_profile_draft.json`은 실제 샘플의 회사명, 주소, 주민/법인등록번호, 문서확인번호를 재사용하지 않고 합성 규칙 또는 안전한 value pool만 참조합니다.
- `anchor_map_draft.json`은 기존 request sidecar를 보존하면서 label/static/header/footer와 schema value target을 구분했습니다.
- page 2/3은 샘플 이미지로 확인했지만 요청에 포함된 최신 OCR/review anchor가 page 1만 가리키므로 schema에는 추가하지 않고 uncertainty에 남겼습니다.
- `토지대장` 전용 항목은 웹/레지스트리 맥락상 관련 문서 유형이지만, 현재 보이는 샘플 anchor가 건축물대장이므로 자동 추가하지 않았습니다.

## 승인 전 확인 필요

1. page 2/3도 authoring 대상이면 해당 페이지의 OCR/review/anchor map을 먼저 생성한 뒤 draft를 확장하세요.
2. 상단 우측 `det_000005` 값은 의미가 불명확해 제외했습니다. 인쇄/QR/양식 코드로 사용할지 확인이 필요합니다.
3. `det_000078`은 OCR이 `z1층`으로 읽었지만 시각적으로 `지1층`에 가까워 보입니다. UI에서 anchor text를 정정할지 검토하세요.
4. `det_000040`은 OCR 단위가 apostrophe처럼 잡혔지만 양식상 `m²`로 보입니다. 렌더 검수 시 단위 표시를 확인하세요.

생성 시각: 2026-07-08T08:53:05+09:00
