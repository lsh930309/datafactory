# TRD-01 pass 2 적용 메모

+- pass 1의 `schema_draft.json`, `anchor_map_draft.json`, `stylesheet_draft.json`은 변경하지 않았습니다.
+- `faker_profile_draft.json`에는 28개 binding 각각 정확히 하나의 renderer 지원 generator를 두고, 20개 합성 invoice record를 `pick_record`로 연결했습니다.
+- 각 record에서 송장일 < L/C일 < 출발일, 수량 × 단가 = 금액, 수하인 국가·도착항·화인 목적지, 송하인·서명자를 일치시켰습니다. 모든 날짜는 기준일 2026-07-13 이후가 아닙니다.
+- 전체 원본 이미지에서 `PC`, `/PC`, `US$`가 값 영역에 포함됨을 확인해 생성값에 유지했습니다.
+- 실제 기업·개인·계좌·식별번호는 사용하지 않았습니다.

## 검토 및 적용

1. `uncertainty_report.json`의 복합 문자열 필드 제한을 검토합니다.
2. UI에서 draft 네 파일과 고정 pass 1 산출물을 함께 승인합니다.
3. 승인 전에는 최종 `schema.json`, `stylesheet.json`, `faker_profile.json`을 덮어쓰지 않습니다.
