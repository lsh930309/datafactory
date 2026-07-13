# FIN-01 2차 authoring 초안

- 1차의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았다.
- 고정된 20개 binding마다 renderer 지원 문법의 generator를 정확히 하나씩 지정했다.
- 회사정보, 사업연도/신고/발급일, 세무서 정보를 각각 12개 record pool로 묶어 서로 맞는 값이 함께 선택되게 했다.
- 개인/법인 체크박스는 `exclusive_choice`로 정확히 하나만 선택되게 했다.
- 전체 템플릿 이미지에서 사업연도 종료일 앞의 `~`가 정적 인쇄임을 확인해 faker 값에서는 제외했다.
- JSON 계약 및 anchor/binding/generator/pool/constraint 검증을 통과한 뒤 UI에서 draft 묶음을 검토·승인해 적용한다. 최종 authoring 파일은 이 단계에서 덮어쓰지 않는다.

남은 검토 사항은 `uncertainty_report.json`에 기록했다.
