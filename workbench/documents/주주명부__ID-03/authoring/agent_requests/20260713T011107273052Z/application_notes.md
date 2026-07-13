# ID-03 주주명부 pass 2 적용 메모

- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았습니다.
- 20개 고정 binding 모두에 renderer 지원 문법의 generator를 정확히 하나씩 지정했습니다.
- 12개 합성 record를 추가해 세 주주의 이름 분할, 주식종류, 소유주식수, 총주식수, 기준일, 증명일, 법인·주소·대표이사를 한 세트로 생성합니다. 각 record에서 세 소유주식수의 합은 총주식수와 일치합니다.
- 전체 원본 이미지의 값 bbox에 포함된 `년`, `월/일 현재`, `주`, `원` 표기를 faker 값에도 유지했습니다.
- 실제 개인정보나 실제 기업·주소 데이터는 사용하지 않았습니다.

검토 시에는 `uncertainty_report.json`의 두 줄 주주명, 분할 주소, 주식수 합계 DSL 제한을 확인하십시오. 승인 후 UI의 draft 적용 절차로 반영하며, 이 pass에서는 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`을 덮어쓰지 않았습니다.
