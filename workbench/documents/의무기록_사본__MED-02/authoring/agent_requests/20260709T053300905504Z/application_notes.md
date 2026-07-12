# 의무기록 사본 MED-02 작성 초안 메모

생성 파일: `schema_draft.json`, `stylesheet_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`, `anchor_map_draft.json`.

전체 템플릿 이미지(`inpainted_lama.png`)를 기준으로 값 위치를 확인했고, `filled_sample` 계약에 따라 `status=use` 앵커만 schema binding의 `anchor_id`로 사용했습니다. 라벨과 단위 텍스트는 `label_anchor_ids`와 `anchor_map_draft.json`의 static 역할로 분리했습니다.

진단코드/진단명/진료과/주호소/검사명은 지원되는 `pick_record` 제약으로 같은 합성 레코드에서 맞춰지도록 했습니다. 치료내용은 요청대로 1, 2, 3번 라인을 각각 별도 bbox에 매핑했습니다.

검토 필요: 발급기관명은 값 target 앵커가 없어 binding하지 않았습니다. 기록작성일과 진료일자의 동일성, 검사 참고치 칸의 다양한 값 허용 여부, 단일 `date.kr` 필드를 `date_order` 제약에 쓸 수 있는지는 적용 전에 확인이 필요합니다.
