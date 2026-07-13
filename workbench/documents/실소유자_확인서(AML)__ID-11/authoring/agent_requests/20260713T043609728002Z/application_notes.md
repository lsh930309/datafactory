# ID-11 2차 authoring draft 적용 메모

- 1차 고정 입력인 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았습니다.
- 현재 32개 고정 binding마다 정확히 하나의 지원 generator를 지정했습니다.
- 합성 scalar pool은 모두 최소 20개, 관계형 `id11_scenarios` record pool은 12개입니다.
- 생략/25%/최대 지분/과반 선임/사실상 지배/대표자 경로는 정확히 하나만 선택되며, 같은 record에서 작성인·실제소유자·지분율을 함께 가져옵니다.
- 전체 이미지에서 지분율 값 오른쪽의 `%`와 성명 오른쪽의 `(인)`이 정적 텍스트임을 확인해 생성값에서는 제외했습니다.
- 비대면 양식의 외국인 개설 불가 안내에 따라 국적은 합성 시나리오에서 `대한민국`으로 제한했습니다.
- 원본 PDF 2·3페이지에는 현재 use bbox가 없으므로 해당 페이지 및 구형 p2/p3/p4 faker 항목은 포함하지 않았습니다.

## 승인·적용 순서

1. `faker_profile_draft.json`의 12개 시나리오와 빈 행 정책을 검토합니다.
2. `uncertainty_report.json`의 렌더러 constraint 적용 순서 주의를 확인합니다.
3. UI 승인 후에만 기존 최종 `faker_profile.json`을 백업하고 draft를 적용합니다. 이 작업에서는 최종 파일을 덮어쓰지 않았습니다.
