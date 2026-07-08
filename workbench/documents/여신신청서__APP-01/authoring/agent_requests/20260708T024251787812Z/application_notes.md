# 여신신청서 APP-01 authoring draft notes

- 생성 시각: 2026-07-08T02:48:14.562197+00:00
- `blank_template` 계약에 맞춰 OCR/keep bbox는 정적 라벨 근거로만 사용했고, schema binding의 `anchor_id`는 `use` 값 영역만 사용했습니다.
- 전체 템플릿 이미지를 우선 확인해 상단 결재표, 신청구분 체크박스, 신청개요, 업체개요, 채권보전 표의 빈 셀을 값 입력 후보로 매핑했습니다.
- 상단 2행 5열 결재표는 요청 지시대로 윗줄 빈칸을 `직책명`, 아랫줄을 한국인 이름 기반 `서명` 값으로 처리했습니다.
- 표 밖에 인쇄된 `(단위 : 백만원)`은 정적 단위로 보고 금액 faker 값에는 별도 단위 문자를 넣지 않았습니다.
- 불확실 항목은 `uncertainty_report.json`에 남겼습니다. 특히 `visual_0055`는 매출액/당기순이익 영역 분할 검토가 필요합니다.
- 이 파일들은 draft이며 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 덮어쓰지 않았습니다.
