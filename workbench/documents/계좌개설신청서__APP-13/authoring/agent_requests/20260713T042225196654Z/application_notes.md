# APP-13 2차 authoring 초안

- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았습니다.
- 고정 binding 17개 모두에 지원 문법의 generator를 하나씩 지정했습니다.
- 12개 합성 법인 신청 record pool과 `pick_record`를 추가해 회사, 계좌, 주소, 대리인, 수권서명 값이 한 신청 단위로 맞도록 구성했습니다.
- 반복 회사명은 `copy`, 작성일은 기준일 `2026-07-13`을 넘지 않도록 `date_not_after`를 적용했습니다.
- 전체 템플릿 이미지 기준으로 값 위치에 정적 단위·접두·접미가 없어 faker 값에 별도 단위를 가감하지 않았습니다.

## 승인 전 확인

1. `Account Type & Currency`의 실제 운영 상품명·허용 통화 범위를 확인합니다.
2. `Signatories`를 이름·직책 목록으로 렌더하는 방식을 승인합니다.
3. 하단 `Authorised Signatory`를 텍스트로 유지할지 명판·법인인감 이미지 자산으로 전환할지 결정합니다.
4. 합성 주민등록번호·계좌번호는 내부 테스트에만 사용하고 외부 노출 시 마스킹 정책을 적용합니다.

승인 시 draft 8종을 한 묶음으로 적용하되, 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 기존 백업 후 UI 적용 절차에서만 갱신합니다.
