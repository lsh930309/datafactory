# Authoring 자동 백업 정책

## 목적
GUI 또는 문서별 보정 스크립트가 기존 수동 authoring 작업을 덮어써도 즉시 복구할 수 있도록, 모든 문서의 핵심 authoring JSON을 쓰기 직전에 자동 백업한다.

## 보호 대상
다음 파일명은 경로에 `authoring/`이 포함되어 있고 `render_preview/`, `backups/` 하위가 아닐 때 보호된다.

- `schema.json`
- `stylesheet.json`
- `faker_profile.json`
- `semantic_schema.json`

## 백업 위치
원본 파일과 같은 authoring 폴더 아래에 timestamp 디렉터리를 생성한다.

```text
workbench/documents/<문서명__ID>/authoring/backups/<YYYYMMDDTHHMMSSffffffZ>/<파일명>
workbench/documents/<문서명__ID>/authoring/backups/<YYYYMMDDTHHMMSSffffffZ>/manifest.json
```

`manifest.json`에는 원본 경로, 백업 경로, 백업 사유, 파일 크기, SHA-256이 기록된다.

## 적용 경로
- backend authoring 저장/초안/마이그레이션 계열: `src/datafactory/authoring.py`의 공통 `_write_json()`
- 문서별 authoring 보정 스크립트: `scripts/enhance_*_authoring.py`, `scripts/calibrate_*_style.py`, `scripts/build_manual_authoring_20260702.py`의 `write_json()`

## 원칙
- 새 파일 생성은 백업하지 않는다.
- 기존 파일과 완전히 같은 내용으로 쓰는 경우는 백업하지 않는다.
- preview/batch/render 산출물은 백업하지 않는다.
- 기존 수동 style을 보존해야 하는 작업은 `stylesheet.json`을 직접 재산출하지 말고, 누락 field/style만 병합해야 한다.
