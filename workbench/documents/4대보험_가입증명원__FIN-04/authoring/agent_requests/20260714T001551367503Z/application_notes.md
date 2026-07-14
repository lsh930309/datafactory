# FIN-04 패스 2 적용 메모

- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 변경하지 않았습니다.
- `faker_profile_draft.json`에 고정된 33개 binding별 generator를 정확히 하나씩 작성했습니다.
- 12개 합성 `fin04_profiles` record를 추가하고, 상단 복합 문구·발급정보·가입자정보·보험별 날짜를 `pick_record`로 함께 선택하도록 했습니다.
- 가입자 성명과 네 보험 행 성명, 사업장관리번호·사업장명칭 반복값은 `copy` 관계로 일치시켰습니다.
- 원본의 인명, 주민등록번호, 사업장명, 관리번호, 문서번호는 value pool에 재사용하지 않았습니다.
- 전체 템플릿 기준으로 KST는 정적 suffix라 생성 값에서 제외했고, 신고접수일 괄호는 값 bbox에 포함되어 생성 값에도 유지했습니다.

## 남은 검토

- 진본 스탬프 시각과 발급일시의 공식 관계는 확인되지 않아 같은 날짜의 근접 시각으로만 구성했습니다.
- 산재보험 자진신고 사업장의 자격취득일 조건부 공란은 지원 constraint 문법이 없어 현재 filled sample 시나리오에서는 날짜를 생성합니다.
- registry의 개인정보 미포함 표기와 실제 샘플의 주민등록번호·성명 존재가 충돌하므로 별도 registry 품질 검토가 필요합니다.

## 승인·적용

UI에서 draft 4종(`faker_profile_draft.json`, `value_pool_draft.json`, `uncertainty_report.json`, `application_notes.md`)과 고정 입력 4종을 함께 검토한 뒤 승인하십시오. 승인 전에는 final `schema.json`, `stylesheet.json`, `faker_profile.json`에 복사하거나 덮어쓰지 마십시오.
