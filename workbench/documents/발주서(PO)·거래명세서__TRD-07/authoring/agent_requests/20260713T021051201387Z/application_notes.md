# TRD-07 2차 faker/관계 확장 메모

- 1차의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았다.
- 46개 고정 `field_id`마다 renderer 지원 문법의 generator를 정확히 하나씩 배정했다.
- 수신처와 발신처는 각각 12개 합성 레코드 pool, 품목은 20개 검산 레코드 pool로 묶었다. 품목별 `금액=수량×단가`는 레코드에서 보장하고 공급가 합계는 `sum` constraint로 계산한다.
- 결재일은 좁은 원본 셀에 맞춰 `MM/DD`를 유지하고, 20개 레코드에서 `작성일<=검토일<=승인일`을 보장한다.
- 전체 이미지 기준으로 `EA`는 별도 정적 열이므로 수량 값에 넣지 않았고, 금액 셀에는 `원` 접미사를 넣지 않았다. 발송지의 `발송지:`는 값 영역과 함께 지워지는 prefix라 생성 레코드에 포함했다.
- UI 승인 시 네 개 2차 산출물(`faker_profile_draft.json`, `value_pool_draft.json`, `uncertainty_report.json`, `application_notes.md`)을 함께 검토한 뒤 적용한다. 최종 authoring 파일은 이 작업에서 덮어쓰지 않았다.
