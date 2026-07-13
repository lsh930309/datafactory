# TRD-03 2차 faker/관계 확장 메모

- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았다.
- 35개 고정 binding 각각에 지원 문법의 generator를 정확히 하나씩 배정했다.
- 운송 경로는 `route_records`, 화물·포장·중량·용적은 `cargo_records`에서 같은 레코드로 선택해 상호 모순을 줄였다.
- 전체 이미지 기준으로 `gross_weight`와 `container_weight`는 `KGS`를 값에 포함하고, `measurement_m3`는 머리글의 정적 `M3`와 중복되지 않도록 숫자만 생성한다.
- `container_volume`의 `M3` 포함 여부, 초과가액신고의 공란 지원, 통지처/제출처의 도메인별 값은 승인 전 검토가 필요하다.
- 적용 시 draft 4개(`faker_profile_draft.json`, `value_pool_draft.json`, `uncertainty_report.json`, `application_notes.md`)를 함께 검토하고, 최종 authoring 파일은 UI 승인과 백업 후 반영한다.
