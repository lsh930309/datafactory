# FIN-05 validation repair notes

- 기계 검증에서 누락된 `faker_profile_draft.json`, `value_pool_draft.json`, `application_notes.md`를 요청 디렉터리 안에 생성했습니다.
- `faker_profile_draft.json.field_generators`는 기존 `schema_draft.json.fields`의 field_id 190개를 그대로 사용하며, 렌더러가 지원하는 rule 문법만 배정했습니다.
- `pool:<name>` rule은 새로 만들지 않아 추가 value pool 최소 크기 의무를 발생시키지 않았습니다.
- `det_000023`, `det_000024`는 이미 use/value_region으로 매핑된 앵커였으나 `auto_type`만 `static_label`이라 blank-template 검증에서 탈락했습니다. field/semantic path/evidence를 삭제하지 않고 `anchor_map_draft.json`의 해당 `auto_type`만 `field_value`로 보정했습니다.
- 웹 리서치와 원본 이미지 재확인은 수행하지 않았고, source evidence와 기존 schema/style/anchor 관계는 보존했습니다.
