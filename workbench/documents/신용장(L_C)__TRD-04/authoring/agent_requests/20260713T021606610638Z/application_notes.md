# TRD-04 신용장(L/C) pass 2 적용 메모

- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았습니다.
- 37개 고정 binding 각각에 지원 문법의 `field_generators`를 하나씩 배치했습니다.
- 은행, 무역 당사자, 통화·금액, 계약 참조, 물품·HS·항구를 12개 이상의 record pool과 `pick_record`로 연결했습니다.
- 발행일 → 최종선적일 → 만기일 순서와 기준일(2026-07-13) 상한을 지원 날짜 제약으로 추가했습니다.
- 전체 원본 이미지에서 통화코드/금액 및 통화명/영문금액이 분리된 bbox임을 확인하여 값에 단위를 중복하지 않았습니다.

## 승인 전 확인

1. 렌더러가 `DD MON YYYY` pool 값을 `date_order`와 `date_not_after`에서 파싱하는지 통합 테스트합니다.
2. 40A 선택 범위와 drawee 은행 소재지 동기화 정책을 `uncertainty_report.json` 기준으로 결정합니다.
3. 승인 후에만 draft를 최종 `faker_profile.json` 등에 적용하고, 기존 최종 파일은 백업합니다.
