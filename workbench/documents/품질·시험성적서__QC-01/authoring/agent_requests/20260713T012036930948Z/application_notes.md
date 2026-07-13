# QC-01 2차 authoring 적용 메모

- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 고정 입력으로 보존했습니다.
- 60개 고정 binding 각각에 renderer 지원 문법의 `field_generators`를 정확히 하나씩 지정했습니다.
- 열린 scalar pool 4종은 각 20개, 상관관계 `pick_record` pool은 12개 합성 레코드로 구성했습니다.
- 채취일·접수일·발행일은 같은 레코드에서 현실 순서로 선택되고 작업일 이후가 되지 않도록 제한했습니다. 담당자 서명은 지원되는 서명 생성기가 없어 대응 성명을 복사합니다.
- 원본 전체 이미지에서 치수 값 bbox 안에 `mm`가 함께 보이므로 치수 faker 값에도 `mm`를 포함했습니다.
- 적용 전에는 텍스트 서명 fallback, 제품별 치수 허용공차, 2페이지 후속 확장 여부를 검토하십시오. 승인 후 UI의 draft 적용 절차로 반영하며 최종 파일은 이 작업에서 덮어쓰지 않았습니다.
