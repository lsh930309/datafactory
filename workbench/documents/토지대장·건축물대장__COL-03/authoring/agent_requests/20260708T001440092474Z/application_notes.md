# 적용 메모 - COL-03 토지대장·건축물대장

생성 시각: 2026-07-08T09:19:11+09:00

## 생성 내용
- 요청 패키지, OCR detections, bbox review, 기존 authoring schema/stylesheet/faker profile, 요청 anchor_map_draft를 읽어 새 draft 8종을 생성했습니다.
- `contract.sample_kind`는 `filled_sample`이므로 review에서 `use`로 남은 값 anchor를 schema field target으로 사용했습니다.
- 기존 faker profile의 unsupported rule 이름은 모두 지원 grammar(`pattern:`, `choice:`, `pool:`, `template:`, `date.kr`, `address.ko`, `company.name_ko`, `person.phone_kr`)로 치환했습니다.

## 남은 불확실성
- `det_000040`의 면적 단위 OCR이 `m'`로 깨져 있어 UI에서 실제 `m²` 여부 확인이 필요합니다.
- `det_000078`은 `z1층`으로 OCR되었으나 실제로는 `지1층`일 가능성이 큽니다.
- 상단 `JXA06`과 하단 용지 규격은 review상 use이지만 명확한 업무 필드 라벨이 없어 schema_draft에는 넣지 않았습니다.
- 토지대장 전용 항목은 현재 보이는 샘플이 건축물대장 1쪽 중심이라 anchor가 확인된 항목만 반영했습니다.

## 승인/적용 시 확인
- UI에서 `schema_draft.json`, `faker_profile_draft.json`, `value_pool_draft.json`, `uncertainty_report.json`을 함께 확인하세요.
- 확정 전에는 기존 `schema.json`, `stylesheet.json`, `faker_profile.json`을 덮어쓰지 않았습니다.
