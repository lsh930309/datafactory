# 전자세금계산서 FIN-08 authoring 초안

생성한 파일: `schema_draft.json`, `stylesheet_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `research_report.json`, `uncertainty_report.json`, `anchor_map_draft.json`.

전체 원본 이미지와 inpainted 템플릿을 기준으로 공급자, 공급받는자, 승인번호, 작성일자/공급가액/세액, 품목 4행, 결제 금액 영역을 매핑했습니다. `filled_sample`이므로 리뷰에서 `use`인 OCR 값 bbox와 manual/visual value bbox를 field target으로 사용했고, 라벨 bbox는 `label_anchor_ids`와 개선된 `anchor_map_draft.json`의 `keep` anchor로만 추적했습니다.

금액 칸 주변에는 값 위치에 `원` 정적 단위가 보이지 않아 faker 값에는 별도 단위 suffix를 넣지 않았습니다. 세액 10% 계산, 빈 품목 행 처리, 승인번호 정확 자리수, 종사업장번호 공란 허용 여부는 `uncertainty_report.json`에 보류했습니다.

적용 전 UI에서 schema binding, faker generator, sum constraint를 함께 검토한 뒤 승인하면 됩니다. 기존 final `schema.json`, `stylesheet.json`, `faker_profile.json`은 수정하지 않았습니다.
