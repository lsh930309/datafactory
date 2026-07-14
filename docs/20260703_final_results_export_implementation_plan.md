# 최종 산출물 Export 웹 기능 구현 계획

> **현행 범위 기준**: 아래의 30건 고정 범위 설명은 최초 구현 당시 기록이다. 현재 UI의 export 범위는 XLSX 레지스트리에서 생성한 도메인별 목표 그룹 또는 사용자 정의 그룹이며, 준비 여부는 workbench 산출물로 판단한다.

작성일: 2026-07-03

## 목표

선택한 도메인/사용자 정의 scope의 제출용 최종 산출물을 웹 GUI에서 한 번에 생성한다.

- 작업 가능 문서: 완성된 authoring pipeline으로 `n`개 샘플을 생성한다.
- 작업 불가/비파이프라인 문서: 검수된 cleanroom PDF 1건을 최종 샘플로 출력한다.
- 결과는 `outputs/results/{분야}/{문서ID}_{한국어 문서명}/` 아래에 정리한다.
- FIN-01, RPT-08처럼 금융/제조 양쪽 scope에 포함된 문서는 양쪽 분야 폴더에 모두 복사한다.

## 사전 안전장치

작업 시작 전 다음 위치에 백업을 생성했다.

- 백업 루트: `.bin/backups/final_results_export_20260703_143226/`
- 포함 범위:
  - `workbench/` 전체 APFS clone copy
  - `first_priority_assessments.json` 존재 시 사본
  - 기존 `outputs/results/` 존재 시 사본

구현 원칙:

- 기존 `schema.json`, `stylesheet.json`, `faker_profile.json`, `semantic_schema.json`은 최종 export 과정에서 수정하지 않는다.
- `outputs/results/` 기존 결과가 있으면 삭제하지 않고 export 실행 시점의 백업 폴더로 이동/보존한다.
- 결과 생성 중 문서별 오류가 발생해도 전체 export를 중단하지 않고 manifest에 오류를 기록한다.
- 원본 workbench 데이터는 read-only로 사용하며, 손상이 감지될 경우 백업본을 활용해 복구할 수 있도록 한다.

## 분류 기준

최종 export 분류는 저장된 assessment feasibility보다 실제 생산 가능 상태를 우선한다.

1. `latestAuthoringSchema`, `latestAuthoringStylesheet`, `latestAuthoringFakerProfile`이 모두 존재하면 `pipeline` 모드.
2. authoring bundle이 없고 `latestCleanroomPdf`가 존재하면 `cleanroom` 모드.
3. 둘 다 없으면 `error` 모드로 manifest에 기록한다.

## 산출물 계약

### 작업 가능 문서

각 샘플 번호는 `sample_000`부터 시작한다.

- `sample_000.jpg`: 최종 렌더링 이미지
- `sample_000.json`: GT label JSON
- `sample_000-bbox.json`: 실제 렌더링 bbox JSON

GT JSON 원칙:

- renderer 내부 metadata 제거.
- 한국어 key-value flat dict 중심.
- key는 authoring field label과 semantic schema mapping을 활용해 생성.
- 표/반복행은 `컬럼명[0]`, `컬럼명[1]` 형태를 허용.

BBox JSON 원칙:

- renderer의 actual annotation bbox를 사용.
- `x`, `y`, `width`, `height`를 이미지 크기 기준 0~1 정규화.
- 소수점 아래 4자리까지 반올림.
- field id, 한국어 key, value를 함께 기록.

### 작업 불가/비파이프라인 문서

- `sample_000.pdf`: cleanroom PDF 사본

### Manifest XLSX

- 경로: `outputs/results/final_results_manifest_{timestamp}.xlsx`
- 기존 first priority assessment 표의 구조를 확장한다.
- 포함 컬럼:
  - 분야, 순번, 문서ID, 문서명, 문서 속성, 저장된 작업판정, 최종 출력모드, 생성 샘플 수, 산출물 형식, 출력 폴더, 오류/경고
- MS Excel 복구 경고가 없도록 XML control character 제거와 올바른 workbook relationship/content type을 보장한다.

## 구현 항목

1. `src/datafactory/final_results_export.py` 신규 작성
   - export plan resolve
   - pipeline 문서 렌더링 및 최종 산출물 변환
   - cleanroom PDF 복사
   - manifest JSON/XLSX 작성
   - 기존 results 백업 처리
2. `src/datafactory/web_api.py` API 추가
   - `POST /api/results/final-export`
   - runtime health feature flag 추가
3. `web/src/App.jsx` UI 추가
   - 목표 그룹 패널에 n 입력 및 최종 산출물 생성 버튼
   - 결과 요약/manifest 링크 표시
4. 테스트 추가
   - export plan 분류
   - bbox 정규화
   - GT key sanitizing
   - xlsx 파일 구조 검증

## 검증

- 단위 테스트 실행.
- `count=1` 전체 export 실행.
- `outputs/results` 아래 금융/제조 폴더와 문서별 산출물 존재 확인.
- manifest xlsx zip/xml 구조 검사.
