# SEC-01 pass 2 적용 메모

- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았다.
- 10개 고정 field에 renderer 지원 문법의 generator를 하나씩 지정했다.
- 펀드 표지의 상호의존 값 7개는 20개 합성 record pool과 `pick_record`로 묶었다. 합성 운용사 URL은 실재 오인을 막기 위해 `example.invalid`를 사용한다.
- 작성기준일은 효력발생일보다 늦지 않고, 두 날짜 모두 2026-07-13 이후가 되지 않도록 지원 constraint를 적용했다.
- 모집총액 anchor는 전체 이미지상 `[모집(매출) 총액 : …좌]` 전체를 포함하므로 단위를 중복하지 않고 완성된 복합 문자열을 생성한다.
- `uncertainty_report.json`의 복합 모집총액, 운용사 URL, 위험등급 명칭 이슈를 검토한 뒤 UI에서 승인·적용한다. 숫자 모집총액에 별도 범위 제약이 필요하면 다음 schema pass에서 숫자 전용 bbox 분리가 필요하다.
- 이번 산출물은 67페이지 PDF 중 현재 표지 1페이지만 대상으로 하며 final authoring 파일은 덮어쓰지 않았다.
