# APP-14 pass 2 적용 메모

pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았다. 이번 pass에서는 현재 53개 binding에 정확히 대응하는 `field_generators`를 작성하고, 신분증-발급기관, 동의/비동의, 이용권유 채널, 분리 날짜, 성명 일치 관계를 지원 constraint 문법으로 확장했다.

전체 템플릿에서 날짜 칸 앞의 `20`과 `년/월/일`이 정적 인쇄물임을 확인했으므로 faker 값에는 해당 prefix·단위를 넣지 않는다. 신분증 발급기관 풀은 실제 기관정보가 아닌 합성 명칭만 사용한다.

적용 전에는 `uncertainty_report.json`의 세 항목을 확인한다. 특히 `p1_dispatch_date`는 날짜와 일련번호가 한 bbox에 있어 내부 날짜 순서를 검증할 수 없고, `p1_delivery_barcode`는 숫자 문자열 생성만 보장한다. 이 두 항목의 렌더 방식이 현재 renderer 기대와 맞는지 UI 미리보기로 승인해야 한다.

승인 시 네 pass 2 산출물을 함께 적용하고, 기존 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 백업 후 별도 적용 절차로 갱신한다. 이 요청 디렉터리의 draft 파일 자체는 최종 파일을 덮어쓰지 않는다.
