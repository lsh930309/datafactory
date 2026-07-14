# DataFactory

DataFactory는 실제 문서 이미지(PDF/JPG/PNG 등)를 바탕으로 합성 문서 이미지와 KIE(Key Information Extraction)용 GT를 제작하는 **로컬 GUI 중심 문서 데이터 제작 도구**입니다.

이 저장소는 실행 코드와 함께 레지스트리, bbox review, authoring schema/style/faker 등 복구하기 어려운 구조 데이터를 관리합니다. 반면 실제 원본 문서, 렌더링 결과, 외부 폰트와 비밀키는 개인정보·라이선스·용량 문제로 Git에서 제외합니다.

> 처음 공유받았다면 먼저 알아둘 점: 이 저장소는 “코드와 작업 상태” 저장소입니다. 원본 이미지와 외부 asset까지 포함된 완전한 데이터 패키지가 아니므로, 새 clone에서 현재 작업 화면을 그대로 재현하려면 별도 로컬 데이터 번들이 필요합니다.

## 무엇을 할 수 있나

- 레지스트리에 정의된 문서 유형과 작업 상태 조회
- seed 문서 import 및 문서별 workbench 구성
- PaddleOCR 또는 Deep OCR을 이용한 bbox/text 검출
- GUI 기반 bbox review, 역할 분류, 이동·크기 조정
- LaMa/Telea/수동 브러시를 이용한 템플릿 정리
- schema, stylesheet, faker profile 기반 합성 문서 렌더링
- Codex CLI를 이용한 Agentic Authoring 초안 생성·검증·부분 보정
- 이미지, 순수 semantic GT JSON, 실제 렌더링 bbox JSON 최종 export
- 필기 문서 출력·스캔 intake와 임시 인쇄체 생성

## 저장소 구조

```text
src/datafactory/   Python 백엔드와 OCR·review·authoring·export 로직
web/               React/Vite 웹 GUI
registry/          문서 분류 레지스트리
workbench/         문서별 JSON 작업 상태
scripts/           문서별 cleanroom/authoring 보정 및 운영 스크립트
tests/             회귀 테스트
docs/              설계·운영 문서와 이전 문서 archive
assets/            로컬 생성 asset 자리(.gitkeep만 추적)
fonts/             로컬 외부 폰트 자리(.gitkeep만 추적)
outputs/           생성 결과(미추적)
```

문서 분류의 기준은 `registry/DEEP_Agent_문서분류_레지스트리_v2.2.xlsx`이며, 현재 도메인 분류는 이 파일의 세 번째 시트를 사용합니다. 작업 진척도는 별도 PDF가 아니라 `workbench/`의 실제 상태를 기준으로 계산합니다.

## 새 환경에서 시작하기

### 1. 필수 도구

- Python 3.14
- Node.js와 npm
- macOS에서는 기본 실행 스크립트가 브라우저까지 자동으로 엽니다.
- Agentic Authoring을 사용할 경우 인증된 `codex` CLI가 PATH에 있어야 합니다.

### 2. Python 환경

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,inpaint]'
```

기본 환경은 GUI, Pillow 렌더링, QR 생성과 테스트에 사용합니다. PaddleOCR, PDF 변환, OpenCV contrib, LaMa까지 사용하려면 별도 `.venv-ocr` 또는 `DATAFACTORY_PYTHON`으로 지정한 동등한 환경이 필요합니다.

기존 OCR 환경에 LaMa를 추가할 때는 다음 스크립트를 사용할 수 있습니다.

```bash
./scripts/install_lama_runtime.sh
```

### 3. 웹 의존성

```bash
npm --prefix web ci
```

`start_datafactory_gui.command`는 `web/node_modules/`가 없으면 자동으로 npm 설치를 시도합니다.

### 4. 로컬 폰트

한글 렌더링은 시스템 폰트로 fallback할 수 있지만 기존 스타일과 글자 폭을 정확히 재현하려면 별도 외부 폰트가 필요합니다.

로컬에서 별도로 전달받은 `datafactory_external_fonts_local.zip`이 프로젝트 루트에 있다면 다음처럼 풉니다. ZIP 내부에는 `fonts/...` 상대 경로가 포함되어 있습니다.

```bash
unzip datafactory_external_fonts_local.zip -d .
```

이 ZIP과 압축 해제된 폰트는 라이선스 확인 없이 공개 저장소에 커밋하지 않습니다. ZIP이 없다면 필요한 한글 폰트를 직접 설치하거나 `fonts/` 아래 배치합니다.

### 5. 원본 데이터와 asset

현재 workbench를 그대로 이어가려면 별도로 보관된 다음 데이터가 필요합니다.

- `workbench/documents/**/samples/`: 기존 문서의 직접 실행 원본
- `seed_samples/`: 신규 import 및 일부 cleanroom 스크립트 원본
- `assets/cleanroom_generated/`: cleanroom 로고·도장·서명
- `assets/logo_pool/`, `assets/map_pool/`, `assets/photo_pool/`: 특정 cleanroom 문서용 이미지

이 데이터가 없어도 GUI와 JSON 상태는 열 수 있지만 원본 이미지 표시, OCR, 인페인팅 및 일부 렌더링은 수행할 수 없습니다. 자세한 구분은 [`공개_저장소_로컬_필수_파일_안내.md`](./공개_저장소_로컬_필수_파일_안내.md)를 참고합니다.

### 6. 선택 기능용 비밀키

Deep OCR은 현재 클린룸 샘플 처리에서만 사용하며 다음 로컬 파일을 읽습니다.

```text
.env/deep_agent_api_key
```

```dotenv
API_KEY="발급받은 키"
WEBHOOK_SECRET="발급받은 웹훅 시크릿"
```

이 파일은 절대 Git에 추가하지 않습니다. Deep OCR을 사용하지 않는 일반 GUI·PaddleOCR·authoring 기능에는 필요하지 않습니다. Jira 보조 스크립트의 토큰도 `.env/jira_api_token` 또는 환경변수로만 관리합니다.

## 실행

### macOS 권장 실행

```bash
./start_datafactory_gui.command
```

기본 주소:

- GUI: <http://127.0.0.1:5173>
- API: <http://127.0.0.1:8766>

실행 스크립트는 사용할 Python 환경을 선택하고, 백엔드와 Vite 개발 서버를 시작한 뒤 브라우저를 엽니다. 로그는 `.cache/gui-logs/`에 기록됩니다.

### 수동 실행

터미널 1:

```bash
PYTHONPATH=src ./.venv/bin/python -m datafactory.web_api --host 127.0.0.1 --port 8766
```

터미널 2:

```bash
DATAFACTORY_API_PORT=8766 npm --prefix web run dev -- --host 127.0.0.1 --port 5173
```

## GUI 작업 흐름

1. **문서 선택**: 레지스트리와 workbench 상태를 확인합니다.
2. **샘플 준비**: seed를 import하거나 기존 workbench sample을 선택합니다.
3. **OCR·BBox review**: 검출 결과를 `use`, `keep`, `mask`, `exclude` 등으로 검토합니다.
4. **템플릿 정리**: 필요한 문서는 인페인팅과 수동 cleanup을 수행합니다.
5. **Agentic Authoring**: schema/style/faker/research draft를 생성하고 검증합니다.
6. **부분 보정**: 완료된 draft에 자연어 수정 요청을 넣어 선택 문서만 보정합니다.
7. **최종 적용·미리보기**: 승인된 draft를 authoring 파일에 적용하고 렌더링을 확인합니다.
8. **최종 산출물 생성**: 선택 그룹의 생성 가능 문서를 `outputs/results/`에 export합니다.

Agent 실행 파일은 문서별 `authoring/agent_requests/`와 `authoring/agent_runs/`에 저장됩니다. `job.json`은 추적하지만 터미널 로그, prompt, snapshot은 로컬 전용이므로 다른 환경에서는 과거 세션의 전체 터미널 내용을 복원할 수 없습니다.

## 저장소에 포함되는 것과 제외되는 것

### Git에 포함

- Python/React 코드와 테스트
- 문서 분류 레지스트리
- workbench manifest와 bbox review JSON
- 최종 authoring schema, semantic schema, stylesheet, faker profile
- Agent request/draft와 최소 실행 상태 `job.json`
- 설계·운영 문서

### Git에서 제외

- 실제 원본 샘플과 스캔 이미지
- OCR·인페인팅·cleanup·미리보기 이미지
- `outputs/` 최종·중간 산출물
- 외부 폰트와 cleanroom 이미지 asset
- API 키와 Jira 토큰
- 가상환경, 모델 캐시, npm 의존성
- Agent 터미널 로그와 로컬 백업

제외 대상 중 무엇이 필수이고 무엇이 재생성 가능한지는 [`공개_저장소_로컬_필수_파일_안내.md`](./공개_저장소_로컬_필수_파일_안내.md)에 정리되어 있습니다.

## 최종 산출물 형식

최종 결과는 `outputs/results/` 아래 생성되며 Git에는 포함하지 않습니다.

- `sample_000.jpg`: 합성 이미지
- `sample_000.json`: 순수 semantic GT JSON
- `sample_000-bbox.json`: 실제 렌더링 annotation bbox JSON

핵심 규칙:

- GT에는 `doc_id`, `document_name`, `sample_id`, `labels`, `annotations`, `image`, `bbox_format` 같은 metadata를 넣지 않습니다.
- GT는 semantic schema의 leaf에 생성값만 주입합니다.
- bbox는 실제 렌더링된 값만 `{l,t,r,b}` 형식으로 기록합니다.
- 값이 빈 문자열이라 렌더링되지 않았다면 bbox도 출력하지 않습니다.
- 클린룸 라이브러리 샘플은 별도의 PII/masking key 정책을 함께 검증합니다.

관련 문서:

- `docs/20260703_final_results_export_implementation_plan.md`
- `docs/20260703_pure_semantic_gt_export_plan.md`
- `docs/archive/라이브러리 샘플 데이터 제작 가이드.md`

## 테스트와 기본 점검

```bash
env PYTHONPATH=src ./.venv/bin/python -m pytest
npm --prefix web run build
```

새 환경에서 권장하는 smoke check:

1. `./start_datafactory_gui.command`로 API와 GUI가 모두 시작되는지 확인
2. 레지스트리와 workbench 문서 목록이 표시되는지 확인
3. 샘플 번들이 있다면 한 문서의 원본 이미지와 bbox review가 열리는지 확인
4. 로컬 폰트를 불러온 뒤 authoring preview가 생성되는지 확인
5. 선택 기능을 사용할 때만 OCR/LaMa/DeepAgent/Codex 상태를 확인

## 데이터 손실 및 공개 저장소 안전 원칙

- `authoring/schema.json`, `semantic_schema.json`, `stylesheet.json`, `faker_profile.json`, `review.json`은 핵심 복구 대상입니다.
- 기존 수작업 데이터를 덮어쓰는 작업 전에는 로컬 백업 또는 Git diff를 확인합니다.
- 원본 문서와 스캔에는 개인정보가 있을 수 있으므로 공개 issue, commit, 로그에 첨부하지 않습니다.
- `.env/`, 폰트 ZIP, 원본 데이터 번들, 생성 asset은 강제로 stage하지 않습니다.
- 공개 전환 전 Git 전체 이력에 비밀키·개인정보·재배포 불가 폰트가 포함된 적이 없는지 별도 검사를 수행합니다.

## 저장소 운영 메모

- 기본 브랜치: `main`
- 공개 범위: public
- 작업 상태의 기준: `registry` + `workbench`
- 샘플·산출물·외부 asset: 별도 스토리지 또는 로컬 백업
- Git 커밋 대상: 코드, 작업 정의, 구조 JSON, 테스트, 공개 가능한 문서
