# 약제비 계산서·영수증 authoring draft

- `schema_draft.json`, `stylesheet_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`, `anchor_map_draft.json` 초안을 생성했습니다.
- 빈 템플릿이므로 OCR 라벨/정적 문구는 `label_anchor_ids` 근거로만 두고, 실제 값 필드의 `anchor_id`는 review에서 `use`로 확정된 value-region bbox만 사용했습니다.
- 금액 표는 항목별 금액, 열 합계, ⑤ 약제비 총액, ⑥ 환자부담 총액, 납부수단 합계를 지원되는 `sum` constraint로 모델링했습니다.
- 사용자 지시대로 `현금영수증(` 오른쪽 괄호 안 bbox는 `cash_receipt_issued` 체크박스로 처리했습니다.
- 남은 검토 사항은 투약일수 단위 포함 여부, 환자부담총액과 납부합계의 동시 일치 강제 방식, 일부 식별번호/승인번호 자리수입니다.
- 확정 적용 전 UI에서 draft 7개 JSON과 이 notes 파일을 함께 검토한 뒤 기존 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`으로 승격하세요.
