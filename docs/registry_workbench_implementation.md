# 레지스트리 중심 문서 제작 워크벤치 구현 기록

## 목적
`seed_samples/문서제목/`에 모아 둔 실제 원본문서를 레지스트리의 문서 계층과 연결해, 작업자가 샘플 확보 현황을 먼저 파악하고 `입고함 → 일괄 적재 → PaddleOCR BBox → 리뷰/분류 → LaMa 인페인팅`으로 이어지게 한다.

## 적용 구조

- 원본 보관: `seed_samples/<사람이 알아볼 수 있는 문서 제목>/...`
  - 사용자가 직접 넣거나 웹앱 드래그&드랍으로 추가한 실제 문서 원본만 둔다.
  - 웹앱 드롭 적재 시에도 문서 제목 폴더명을 사용해 사람이 알아볼 수 있게 보관한다.
  - PDF는 원본을 보관하고, 드롭 적재/단일 적재/일괄 적재 시 아직 렌더링된 페이지가 없으면 전체 페이지를 `*_page_001.jpg` 형식으로 자동 렌더링해 즉시 작업 샘플로 쓴다.
- 작업 보관: `workbench/documents/<문서제목_slug>__<문서ID>/`
  - `samples/original/`: seed 원본을 복제 적재한 작업 샘플
  - `ocr/`: PaddleOCR 검출 산출물
  - `review/`: BBox 리뷰 정책
  - `inpaint/`: LaMa 결과
  - `manifest.json`: 문서별 작업 상태와 산출물 포인터
- 수동 매핑 보관: `workbench/seed_mappings.json`
  - 미매칭 seed 폴더를 한 번 문서에 연결하면 다음 스캔부터 자동 후보로 사용한다.
- seed 보관함: `workbench/.trash/seed_samples/`
  - GUI에서 더 이상 쓰지 않을 seed 원본 폴더를 삭제하지 않고 timestamp가 붙은 폴더로 이동한다.
  - 작업 폴더(`workbench/documents/...`)와 기존 산출물은 건드리지 않는다.

## UI 원칙

- 첫 화면은 문서 상세보다 `Seed 입고함`을 먼저 보여준다.
- 입고함은 `자동 적재 가능`, `확인 필요`, `이미 적재됨`으로 나뉜다.
- 기본 적재 방식은 반자동 일괄 적재다. 고신뢰 매칭은 작업자가 한 번에 승인해 적재한다.
- 문서 현황판에는 `seed 발견/미적재`, `웹 수집 필요`, `샘플 적재됨`, `BBox 완료`, `리뷰 완료`, `LaMa 완료`를 표시한다.
- 문서 ID보다 문서 제목을 먼저 표시하고, ID는 보조 badge로 노출한다.
- 레지스트리의 산업도메인/업무 연결은 물리 폴더를 중복하지 않고 UI에서 가상 계층처럼 보여준다.
- 브라우저 어디에나 `pdf/png/jpg/jpeg`를 드롭하면 문서 검색 popover에서 대상 문서를 고르고 바로 적재한다.
- 중앙 캔버스는 폭 슬라이더 없이 컨테이너 폭에 맞춰 자동 리사이즈한다.
- 중앙 캔버스는 `전체 맞춤 / 폭 맞춤 / 100%` 표시 모드를 제공해 세로 문서와 가로로 긴 문서 모두 최초 리뷰 시 잘리지 않게 본다.
- BBox 리뷰 캔버스는 선택/상태 변경뿐 아니라 단일 bbox 이동, 리사이즈, 수동 추가, 삭제를 지원한다.
- LaMa 완료 후 메인 캔버스는 인페인팅 결과 이미지로 전환하고, 4분할 비교 결과는 별도 열기 버튼으로 유지한다.

## 현재 구현된 API

- `GET /api/registry`: 엑셀 레지스트리 로딩 결과
- `GET /api/seed/scan`: seed 폴더를 `importable / needsReview / alreadyImported`로 분류
- `POST /api/seed/import`: 단일 seed 폴더 적재 및 선택적 수동 매핑 저장
- `POST /api/seed/import-batch`: 자동 적재 가능 seed 폴더 일괄 적재
- `POST /api/seed/mapping`: seed 폴더명과 문서 ID의 수동 매핑 저장
- `POST /api/seed/upload`: 드롭된 파일을 문서 제목 seed 폴더에 저장하고 즉시 workbench로 import
- `POST /api/seed/trash`: `seed_samples/` 하위 원본 폴더를 `workbench/.trash/seed_samples/`로 이동
- `GET /api/work-items`: 문서별 작업 상태 목록
- 기존 OCR/review/inpaint API는 `docId`를 받으면 workbench 하위 산출물 경로를 기본값으로 사용한다.
- `POST /api/ocr/detect`는 PaddleOCR `preset`을 받는다.
  - `fast`: 빠른 검출
  - `balanced`: 기존 기본값
  - `precise`: 고해상도/낮은 threshold 기반 정밀 검출

## 현재 구현된 UX 흐름

1. 작업자가 `seed_samples/`에 실제 문서 폴더를 넣거나, 웹앱에 파일을 드롭한다.
   - 웹앱 드롭 시 문서 제목/ID를 검색해 선택하면 `seed_samples/<문서제목>/` 저장과 내부 import를 동시에 수행한다.
   - PDF가 포함된 경우 적재 시점에 JPG 페이지가 없으면 자동으로 렌더링된다.
2. 웹앱의 `Seed 입고함`이 자동 적재 가능/확인 필요/이미 적재됨을 보여준다.
3. 자동 적재 가능 항목은 `일괄 적재`로 한 번에 workbench로 복제한다.
4. 확인 필요 항목은 문서명을 검색해 한 번 매핑하고, 매핑 저장 후 적재한다.
5. 문서 현황판에서 `웹 수집 필요` 문서를 보고 추가 샘플을 구해온다.
6. 샘플이 적재된 문서는 PaddleOCR BBox 프리셋 검출, 리뷰/분류/좌표편집, LaMa 인페인팅 작업을 이어간다.
7. 더 이상 쓰지 않을 seed 원본 폴더는 입고함/선택 문서 seed 카드의 `보관함 이동` 버튼으로 안전하게 숨긴다.

## 검증

- Python 테스트: `env PYTHONPATH=src ./.venv/bin/python -m pytest -q`
- React 빌드: `npm run build` in `web/`
- API smoke: `/api/health`, `/api/seed/scan`, `/api/work-items`

## 다음 단계: authoring 산출물

`BBox 완료 → 리뷰 완료 → LaMa 완료` 다음 단계는 `authoring/` 하위의 `schema.json`, `stylesheet.json`, `faker_profile.json`을 작성해 인페인팅된 템플릿 위에 합성 값을 렌더링하는 것이다. 상세 계획은 `docs/schema_stylesheet_faker_plan.md`를 따른다.
