# 적용 메모

- `filled_sample` 기준으로 전체 선하증권 이미지를 확인하고, 보이는 값 위치를 `schema_draft.json`의 semantic schema와 binding으로 연결했습니다.
- 기존 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 건드리지 않았고 요청 디렉터리 안의 draft 산출물만 작성했습니다.
- 자동 리뷰에서 `keep`으로 남아 있었지만 전체 이미지상 명확한 값인 `FOB`, `FREIGHT COLLECT`, `MUMBAI`, 수령지/인도지, 총 포장수 문자 값은 `anchor_map_draft.json`에서 value target으로 승격했습니다.
- 문서명에는 AWB가 포함되어 있으나 입력 이미지는 `BILL OF LADING` 양식이므로 AWB 전용 항공 필드는 추가하지 않았습니다.
- 비어 있는 송하인 상세주소, 통지처, 봉인번호, 용적 영역은 manual bbox 근거로 보수적인 generator를 제안했고 `uncertainty_report.json`에 승인 필요 항목으로 남겼습니다.
- 발행일의 `17-MAY-23` 같은 영문 월 약어 날짜는 현재 지원 generator 문법으로 직접 표현하기 어려워 synthetic pool로 근사했습니다.
