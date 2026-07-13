# QC-02 2차 authoring 적용 메모

- 1차 고정 입력인 schema_draft.json, anchor_map_draft.json, research_report.json, stylesheet_draft.json은 변경하지 않았습니다.
- 72개 고정 binding마다 renderer 지원 generator를 정확히 1개씩 구성했습니다.
- 발주일과 입고일은 분리 연·월·일 date_group, 발주일 ≤ 입고일, 최대 60일, 2026-07-13 이후 금지 관계를 적용했습니다. 인페인트 전체 이미지에서 `20`은 제거되어 4자리 연도를 생성하고, 정적 `년`, `월`, `일`은 값에 중복하지 않습니다.
- 8개 품목 행은 품명·규격·기타 검사내용을 24개 합성 record pool에서 함께 선택하고, 수량은 정적 단위 없이 1~999 정수로 제한했습니다.
- 품질 판정에 따른 조치·비고 조건 분기는 현재 지원 제약에 없어 uncertainty_report.json에 승인 필요 항목으로 남겼습니다.
- UI 승인 시 네 개 2차 파일을 함께 검토한 뒤 최종 faker_profile.json 적용 여부를 결정하십시오.
