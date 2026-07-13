# ADM-04 2차 faker/관계 확장

- 1차 고정 입력인 schema_draft.json, anchor_map_draft.json, research_report.json, stylesheet_draft.json은 변경하지 않았습니다.
- 125개 고정 binding 각각에 정확히 하나의 지원 field generator를 배정했습니다.
- 열린 scalar pool은 각 20개, 상관관계 instrument_records는 20개로 구성했습니다.
- 품목·모델·단위·단가·검교정비는 pick_record로 함께 선택하고, 지원되는 금액 행은 단가+검교정비=견적금액, 행 합계=소계, 소계+부가세=합계로 연결했습니다.
- 전체 이미지에서 금액 bbox 안에 통화기호가 포함되고 별도 정적 원 단위가 없음을 확인하여 money.krw 표기를 유지했습니다.
- 부가세 10%는 공식 법령 근거가 있으나 현재 지원 constraint에 곱셈이 없어 정확한 파생식은 uncertainty_report.json에 보류했습니다.

## 승인/적용

UI에서 불확실성 항목과 렌더 결과를 검토한 뒤 draft 세트를 승인하십시오. 최종 schema.json, stylesheet.json, faker_profile.json은 이 작업에서 덮어쓰지 않았습니다.
