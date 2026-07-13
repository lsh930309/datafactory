# 적용 메모

- 1차 패스의 `schema_draft.json`, `anchor_map_draft.json`, `research_report.json`, `stylesheet_draft.json`은 고정 입력으로 보존했습니다.
- `faker_profile_draft.json`에는 57개 고정 바인딩 각각에 정확히 하나의 지원 generator를 지정하고, 12개 상관 레코드를 `pick_record`로 연결했습니다.
- 발행회사/연락처와 송하인, 대표 품명과 두 포장행은 `copy`로 일치시켰고, 출항일 미래 방지와 순중량≤총중량 관계를 지원 constraint로 추가했습니다.
- 전체 이미지에서 중량·용적 수치와 단위가 별도 위치이므로 수치 생성값에는 단위를 포함하지 않습니다.
- 용적 단위는 열 제목상 `CBM`이지만 원본 단위 앵커 OCR이 `KGS`라 `choice:CBM|M3`로 제안하고 검토필요 상태를 유지했습니다.
- UI에서는 `uncertainty_report.json`의 용적 단위 결정을 우선 확인한 뒤 draft 묶음을 승인·적용하면 됩니다. 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`은 이 작업에서 덮어쓰지 않았습니다.
