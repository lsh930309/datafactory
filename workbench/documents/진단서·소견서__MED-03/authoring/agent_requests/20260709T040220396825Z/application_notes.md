# 진단서·소견서(MED-03) authoring draft

- `blank_template` 기준으로 전체 템플릿 이미지를 우선 확인하고, `status=use`인 37개 값 영역을 모두 schema field에 매핑했습니다.
- OCR/keep 박스는 정적 라벨 근거로만 사용했고, schema field의 `anchor_id`에는 사용하지 않았습니다.
- `년/월/일`, `일부터`, 전화번호 괄호, `면허번호 제/호`는 템플릿에 이미 인쇄된 정적 문구라 faker 값에서 제외했습니다.
- 병명과 질병분류기호는 합성 diagnosis record pool과 `pick_record` constraint로 같은 레코드에서 선택되도록 했습니다.

## 검토 필요

- 부 질병·부상 병명/질병분류기호를 항상 채울지 또는 일부 샘플에서 공란 허용할지 결정이 필요합니다.
- 주민등록번호는 합성 rule만 사용했지만, 최종 렌더링에서 마스킹 정책을 적용할지 검토해야 합니다.
- 의사/치과의사/한의사 체크박스는 현재 정확히 하나만 선택되도록 모델링했습니다.

## 적용 방법

UI에서 `schema_draft.json`, `stylesheet_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`, `anchor_map_draft.json`을 함께 검토한 뒤 최종 authoring 파일로 승인 적용하면 됩니다.
