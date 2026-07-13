# TRD-05 pass 2 적용 메모

- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `stylesheet_draft.json` 구조와 71개 field binding은 유지했다.
- `faker_profile_draft.json`에 71개 field generator를 정확히 하나씩 정의하고, 열린 scalar pool은 각 20개, 상관 record pool은 60개로 구성했다.
- 신고 주체·국가/항구·품목·가격·날짜가 한 레코드에서 함께 선택되도록 `pick_record`를 사용했으며, 중복 표시값은 `copy`, 날짜는 `date_order`/`date_not_before`/`date_not_after`로 보강했다.
- 사업자등록번호는 checksum을 보장하는 `business_reg_no`가 최종 생성하도록 record pool 대상에서 제외했다.
- 원본 전체 이미지 기준으로 `(KG)`, `(CT)`, `(SET)/(EA)`는 값에 포함하고, 열 제목의 USD는 값에 중복하지 않았다.
- 승인 전에는 코드 전체 집합, 환율 의미, 금액 복합 산술 한계를 `uncertainty_report.json`에서 확인한다. UI 승인 후에만 최종 authoring 파일로 적용한다.
