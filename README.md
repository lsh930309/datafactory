# DataFactory

DataFactory는 실제 문서 이미지(PDF/JPG/PNG 등)를 기반으로 합성 문서 이미지와 KIE(Key Information Extraction)용 GT 레이블을 제작하기 위한 GUI 중심 도구입니다.

이 저장소는 **코드, 설정, 레지스트리, workbench JSON 상태, bbox/schema/faker/style 정보**처럼 손상 시 복구가 어려운 핵심 정보를 보호하기 위한 저장소입니다. 실제 원본 샘플 이미지, 인페인팅 이미지, 생성 결과물, 캐시, 외부 폰트 바이너리는 용량과 라이선스/개인정보 리스크 때문에 커밋하지 않습니다.

## 목표

- 실문서 샘플을 문서 유형별 workbench에 적재
- OCR/Paddle 기반 bbox 검출
- GUI에서 bbox review/edit/classification 수행
- LaMa 기반 인페인팅 및 수동 cleanup 지원
- authoring 단계에서 schema/faker/style/bbox를 조합해 합성 문서 렌더링
- 최종적으로 1차 목표 문서 범위에 대해 이미지, GT JSON, bbox JSON, manifest를 생성

## 현재 저장소에 포함되는 것

- `src/datafactory/`: Python 백엔드, OCR/정책/인페인팅/export/authoring 로직
- `web/`: React 기반 웹 GUI
- `app/`: 이전 Streamlit 진입점(호환/참조용)
- `scripts/`: 문서별 cleanroom/authoring 보정 스크립트
- `tests/`: 회귀 테스트
- `registry/`: 문서 분류/1차 범위 레지스트리 자료
- `workbench/`: 문서별 JSON 상태
  - `manifest.json`
  - `authoring/schema.json`
  - `authoring/semantic_schema.json`
  - `authoring/stylesheet.json`
  - `authoring/faker_profile.json`
  - `review/**/review.json`
- `docs/`: 현재 운영에 필요한 핵심 계획/지침 문서

## 저장소에서 제외되는 것

- `seed_samples/`: 실제 원본 문서 샘플
- `outputs/`: 최종/중간 산출물
- `workbench/**/samples/`: workbench 내부 원본/cleanroom 샘플 파일
- `workbench/**/inpaint/`, `workbench/**/cleanup/`: 인페인팅/cleanup 이미지
- `assets/`: 이미지 생성/지도/로고/사진 등 바이너리 asset
- `fonts/`: 외부 폰트 파일
- `.bin/`, `.cache/`, `.venv*`, `web/node_modules/`: 로컬 캐시·백업·의존성

> 따라서 새 환경에서 완전한 렌더링을 재현하려면 별도 보관된 `seed_samples/`, 필요한 workbench 이미지, 외부 폰트, LaMa/Paddle 런타임 캐시를 다시 준비해야 합니다. 이 저장소는 우선 “작업 정의와 복구 가능한 구조 데이터”를 보호하는 데 초점을 둡니다.

## 빠른 시작

### 1. Python 환경

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,inpaint]'
```

OCR/Paddle, LaMa 등 고급 런타임은 로컬 환경에 따라 별도로 설치해야 합니다. 기존 작업 환경에서는 `.venv-ocr`, `.cache/paddlex`, `.cache/torch` 등을 로컬 캐시로 사용했습니다.

### 2. 웹 GUI 실행

```bash
./start_datafactory_gui.command
```

기본 흐름은 다음 단계로 구성됩니다.

1. 문서 선택/상태 확인
2. bbox detect
3. bbox review/edit/classification
4. inpainting / cleanup
5. authoring(schema/faker/style)
6. render / final export

### 3. 테스트

```bash
env PYTHONPATH=src ./.venv/bin/python -m pytest
```

현재 기준 전체 회귀 테스트는 `84 passed` 상태입니다.

## 최종 산출물 export 정책

최종 결과는 `outputs/results/` 아래 생성되지만 Git에는 포함하지 않습니다.

작업 가능 문서는 다음 형식을 생성합니다.

- `sample_000.jpg`: 합성 이미지
- `sample_000.json`: GT label JSON
- `sample_000-bbox.json`: 실제 렌더링 annotation bbox JSON

GT/BBox 정책:

- metadata(`doc_id`, `document_name`, `sample_id`, `labels`, `annotations`, `image`, `bbox_format` 등)를 넣지 않습니다.
- GT는 순수 semantic schema에 value만 주입합니다.
- bbox는 실제 렌더링된 annotation만 `{l,t,r,b}` 형식으로 기록합니다.
- value가 빈 문자열이라 실제 렌더링이 없다면 bbox도 출력하지 않습니다.

관련 문서:

- `docs/20260703_final_results_export_implementation_plan.md`
- `docs/20260703_pure_semantic_gt_export_plan.md`

## 1차 목표 범위

1차 목표는 금융/제조 30건 기준에서 중복 2건을 제외한 unique 28종입니다. 작업 방식은 크게 세 가지입니다.

1. **pipeline 문서**: GUI bbox/inpaint/authoring/render 파이프라인으로 대량 생성
2. **cleanroom 문서**: Pillow 직접 드로잉 기반 대표 샘플 제작
3. **수집 문서**: 라이선스/개인정보 리스크가 낮은 실제 공개 문서 수집 대응

범위 정의는 `src/datafactory/registry.py::FIRST_PRIORITY_SCOPE_ENTRIES`와 `docs/objectives/20260702_manual_authoring_objective.md`를 기준으로 합니다.

## 데이터 손실 방지 원칙

- authoring/schema/stylesheet/faker/review JSON은 핵심 복구 대상입니다.
- schema 초안 재생성처럼 기존 수작업 데이터를 덮어쓸 수 있는 기능은 매우 주의해서 사용해야 합니다.
- 주요 변경 전에는 `.bin/backups/`에 로컬 백업을 생성하는 정책을 유지합니다.
- GitHub에는 백업 디렉터리 자체는 올리지 않지만, 복구 가능한 최신 JSON 상태는 커밋합니다.

## 저장소 운영 메모

- 기본 브랜치: `main`
- 공개 범위: private
- 샘플/산출물은 별도 스토리지 또는 로컬 백업으로 관리
- Git 커밋 대상은 “작업 정의, 코드, JSON 상태, 테스트” 중심
