# 입퇴원확인서 MED-05 authoring draft

전체 템플릿 이미지를 기준으로 `schema_draft.json`, `stylesheet_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`, `anchor_map_draft.json`을 생성했습니다.

핵심 결정:
- `blank_template` 계약에 따라 OCR 라벨/keep bbox는 `label_anchor_ids`로만 사용했습니다.
- 실제 값 바인딩은 `status=use`, `role=value_region`인 앵커만 사용했습니다.
- `질병분류기호` 좌측 빈 header는 병명 열 헤더 후보로 보아 `병명` 적용을 권장하되, 값 필드로 매핑하지 않았습니다.
- 병명 표는 요청대로 최대 3개의 `병명 + 질병분류기호` 세트로 구성했습니다.
- 병명/질병분류기호 3개 세트는 `data_pools.diagnosis_records`와 `pick_record` constraint를 사용해 같은 진단 레코드에서 함께 선택되도록 소급 보정했습니다.
- `만( )세`, `년/월/일`, `면허번호 제/호`는 정적 문구가 이미 템플릿에 있으므로 faker 값에는 단위를 넣지 않았습니다.

검토 필요:
- 빈 header `visual_0012`를 실제 authoring 적용 시 `병명` 정적 텍스트로 채울지 승인해야 합니다.
- `입원·퇴원연월일`은 현재 큰 단일 bbox라서 기간 문자열로 생성합니다. 입원일/퇴원일을 별도 검증하려면 bbox를 추가 분할해야 합니다.
- 공식 별지 원문을 추가 확보하면 header 문구와 의사소견 라벨을 더 강하게 확정할 수 있습니다.
