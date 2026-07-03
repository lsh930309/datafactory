# 합성 문서 이미지 생성 GUI 도구 러프 구상안

## 1. 프로젝트 목표

이 프로젝트의 목표는 실문서 이미지와 PDF를 seed로 받아, KIE(Key Information Extraction)·OCR 학습에 사용할 수 있는 합성 문서 이미지와 정답 데이터를 대량 생성하도록 돕는 GUI 기반 도구를 만드는 것이다.

초기 목표는 모든 과정을 완전 자동화하는 단일 모델을 만드는 것이 아니다. `docs/start_idea.md`에서 정리한 것처럼, 현재 실무적으로 가장 안정적인 방향은 여러 오픈소스 도구와 Python 기반 정밀 렌더링을 조합한 하이브리드 파이프라인이다. 따라서 v1은 다음을 목표로 한다.

- 실문서 seed를 불러와 텍스트 영역을 자동 탐지한다.
- OCR 결과와 bbox를 GUI에서 검수·수정할 수 있게 한다.
- 원본 텍스트 영역을 지운 빈 템플릿 이미지를 만든다.
- 각 bbox를 의미 있는 필드와 연결하고, 필드별 fake value 생성 규칙을 정의한다.
- fake value를 원래 문서 스타일에 최대한 맞춰 다시 렌더링한다.
- 합성 이미지와 함께 KV JSON, bbox JSON, manifest를 내보낸다.
- 최종적으로 수십~수천 장 단위의 변형 문서를 반복 생성할 수 있게 한다.

## 2. 기본 방향

### 2.1 단일 SOTA 모델보다 하이브리드 워크플로우 우선

문서 텍스트 편집(Document Text Editing)이나 Scene Text Editing 계열 모델은 시각적으로 자연스러운 결과를 만들 수 있지만, 금융·공문서처럼 작은 숫자, 표선, 정밀한 좌표, 정확한 GT가 중요한 문서에서는 결과물이 뭉개지거나 hallucination이 생길 수 있다.

따라서 초기 구현은 다음 조합을 우선 고려한다.

```text
Seed PDF/JPG/PNG
  -> 페이지 이미지화 / 해상도 정규화
  -> OCR 또는 text detection으로 bbox 추출
  -> bbox GUI 검수 및 필드 매핑
  -> 인페인팅으로 빈 템플릿 생성
  -> Faker/룰 기반 fake KV 생성
  -> Pillow/OpenCV 기반 정밀 텍스트 렌더링
  -> bbox/GT 재계산
  -> Augraphy 등으로 스캔/팩스/촬영 노이즈 증강
  -> 이미지 + JSON + manifest export
```

### 2.2 GUI는 자동화와 수동 검수의 중간 지점

실문서의 layout, 표선, 도장, 워터마크, 흐린 스캔 품질은 문서마다 다르기 때문에, v1부터 완전 자동화를 전제로 하면 실패 비용이 커진다. GUI는 다음 역할을 한다.

- OCR이 찾은 bbox를 사람이 빠르게 확인한다.
- 잘못 잡힌 bbox를 수정하거나 삭제한다.
- 여러 bbox를 하나의 필드로 묶거나, 하나의 bbox를 별도 필드로 분리한다.
- 필드명, 타입, 생성 규칙을 문서별 템플릿으로 저장한다.
- 합성 preview를 보며 렌더링 위치, 폰트 크기, 색상, 정렬을 보정한다.
- 충분히 검수된 템플릿에서 대량 생성 job을 실행한다.

## 3. 주요 사용자 흐름

### 3.1 Seed 등록

1. 사용자가 PDF/JPG/PNG 파일을 업로드한다.
2. PDF는 페이지별 이미지로 변환한다.
3. 각 페이지의 원본 크기, 렌더링 DPI, 좌표계 정보를 저장한다.
4. GUI에서 페이지 썸네일과 확대 이미지를 보여준다.

### 3.2 OCR 및 bbox 후보 생성

1. PaddleOCR, CRAFT, docTR 등 후보 엔진으로 텍스트 영역을 탐지한다.
2. 탐지 결과를 `TextRegion`으로 저장한다.
3. GUI에서 원본 이미지 위에 bbox overlay를 표시한다.
4. 사용자는 bbox를 이동, 크기 조정, 삭제, 병합, 분리할 수 있다.

### 3.3 필드 스키마 작성

1. 사용자가 bbox를 선택해 필드명을 지정한다.
2. 각 필드에 타입을 지정한다.
   - 예: 이름, 주민번호, 사업자번호, 날짜, 금액, 주소, 은행명, 계좌번호, 자유 텍스트
3. 필드별 fake value 생성 규칙을 지정한다.
   - Faker 기반 생성
   - 사용자 지정 후보 목록
   - 정규식/포맷 기반 생성
   - Python rule/plugin 기반 생성
4. 필드 스키마와 bbox 매핑을 문서 템플릿으로 저장한다.

### 3.4 템플릿 생성

1. 선택된 텍스트 bbox를 마스크로 변환한다.
2. 마스크를 확장/블러 처리해 글자 가장자리 잔상을 줄인다.
3. LaMa 또는 대체 인페인팅 엔진으로 텍스트 제거 이미지를 만든다.
4. 인페인팅 결과를 GUI에서 원본과 비교한다.
5. 필요하면 특정 영역만 다시 마스킹하거나 수동 제외한다.

### 3.5 합성 렌더링

1. 필드 스키마에 따라 fake KV를 생성한다.
2. 원본 OCR 영역 주변에서 글자 색상, 배경색, 줄 높이, 정렬 후보를 추정한다.
3. 한국어 문서에 자주 쓰이는 폰트 preset을 사용한다.
   - 맑은 고딕
   - 굴림
   - 돋움
   - Noto Sans CJK / 본고딕
   - 기타 사용자 등록 폰트
4. Pillow/OpenCV로 템플릿 이미지 위에 값을 렌더링한다.
5. 실제 렌더링된 텍스트의 bbox를 계산해 GT로 저장한다.
6. preview에서 원본 스타일과 위치를 비교해 보정할 수 있게 한다.

### 3.6 대량 생성 및 export

1. 사용자가 생성 개수, random seed, 증강 옵션을 설정한다.
2. 각 샘플마다 fake KV를 새로 생성한다.
3. 렌더링 결과에 선택적으로 노이즈를 적용한다.
   - 스캔 노이즈
   - 압축 artifacts
   - blur
   - 회전/기울기
   - 밝기/대비 변화
   - 팩스/복사본 질감
   - 모바일 촬영 shadow
4. 결과물을 저장한다.
   - 합성 이미지
   - KV JSON
   - bbox JSON
   - manifest JSONL/CSV
   - template provenance

## 4. 초기 내부 개념 모델

v1 구현 시 내부 모델은 다음 개념을 기준으로 잡는다.

### 4.1 `DocumentSeed`

원본 문서와 페이지 이미지 정보를 나타낸다.

- 원본 파일 경로
- 파일 타입: PDF/JPG/PNG 등
- 페이지 번호
- 렌더링 DPI 또는 scale
- 이미지 width/height
- 원본 좌표계와 화면 좌표계 변환 정보

### 4.2 `TextRegion`

OCR 또는 detection 결과로 나온 텍스트 영역이다.

- region id
- page id
- bbox 좌표
- polygon 좌표 후보
- OCR text
- confidence
- detection source
- 사용자가 수정했는지 여부

### 4.3 `FieldSpec`

합성 데이터 생성에 사용할 의미 필드다.

- field id
- field name
- field type
- 연결된 bbox 또는 region id
- value generation rule
- text style preset
- alignment / overflow policy
- 출력 GT 포함 여부

### 4.4 `TemplateSpec`

하나의 seed 문서를 재사용 가능한 합성 템플릿으로 정의한다.

- seed reference
- page references
- selected text regions
- field specs
- inpainted template image paths
- render defaults
- augmentation defaults

### 4.5 `RenderJob`

대량 생성 실행 단위다.

- template id
- output directory
- sample count
- random seed
- enabled fields
- augmentation profile
- export formats

### 4.6 `SyntheticSample`

생성된 한 건의 결과물이다.

- image path
- kv JSON path 또는 payload
- bbox JSON path 또는 payload
- source template id
- render job id
- random seed
- generation timestamp

## 5. 출력 포맷 초안

초기에는 복잡한 학습 포맷을 바로 맞추기보다 단순하고 추적 가능한 JSON을 먼저 사용한다.

### 5.1 KV JSON 예시

```json
{
  "sample_id": "sample_000001",
  "template_id": "template_invoice_a",
  "fields": {
    "customer_name": "홍길동",
    "amount": "123,400",
    "issue_date": "2026-06-26"
  }
}
```

### 5.2 bbox JSON 예시

```json
{
  "sample_id": "sample_000001",
  "image": {
    "path": "images/sample_000001.png",
    "width": 2480,
    "height": 3508
  },
  "annotations": [
    {
      "field": "customer_name",
      "text": "홍길동",
      "bbox": [320, 512, 128, 34],
      "bbox_format": "xywh"
    }
  ]
}
```

### 5.3 manifest JSONL 예시

```json
{"sample_id":"sample_000001","image":"images/sample_000001.png","kv":"kv/sample_000001.json","bbox":"bbox/sample_000001.json","template_id":"template_invoice_a"}
```

추후 필요에 따라 COCO, LayoutLM, Donut, PaddleOCR, 자체 KIE 포맷 export를 별도 adapter로 추가한다.

## 6. 기술 후보

### 6.1 OCR / Text Detection

- PaddleOCR: 한국어 OCR 및 bbox 추출 후보로 우선 검토
- CRAFT: text detection 중심 후보
- docTR: OCR pipeline 후보
- Tesseract: 설치 간단한 fallback 후보

### 6.2 Inpainting

- LaMa: 문서 배경 보존을 위한 우선 후보
- OpenCV inpaint: 가벼운 fallback
- diffusion 기반 모델: 품질 spike 후 선택

### 6.3 Rendering

- Pillow: 텍스트 렌더링, bbox 계산, 폰트 처리
- OpenCV: 이미지 합성, 좌표/마스크 처리
- HarfBuzz/RAQM 계열: 한국어/복합 텍스트 렌더링 품질이 필요할 때 검토

### 6.4 Fake Data

- Faker: 기본 fake value 생성
- custom provider: 한국 금융/공문서 도메인 값 생성
- rule plugin: 프로젝트별 필드 생성 규칙 확장

### 6.5 Augmentation

- Augraphy: 스캔/복사/팩스 스타일 증강
- OpenCV/Pillow: 기본 blur, brightness, rotation, compression

### 6.6 GUI

초기 후보는 다음과 같다.

- Streamlit
  - 장점: 빠른 MVP, Python pipeline과 결합 쉬움
  - 단점: 정교한 bbox 편집 UX는 한계가 있을 수 있음
- PySide / Qt
  - 장점: 데스크톱 bbox 편집 UX 구현에 강함
  - 단점: 개발량 증가
- Tauri + Web frontend + Python backend
  - 장점: 장기적으로 제품형 GUI에 적합
  - 단점: 초기 세팅과 통신 구조가 무거움

v1은 빠른 실험을 위해 Streamlit 또는 간단한 web UI로 시작하고, bbox 편집 UX가 병목이 되면 PySide/Tauri로 전환하는 방향을 기본값으로 둔다.

## 7. MVP 범위

MVP는 다음까지를 성공 기준으로 한다.

1. 단일 seed 문서 또는 단일 PDF page를 불러온다.
2. OCR/text detection 결과를 bbox overlay로 표시한다.
3. bbox를 최소한 삭제/선택/필드 연결할 수 있다.
4. 필드별 fake value 생성 규칙을 지정한다.
5. 텍스트 제거 템플릿을 생성한다.
6. 합성 preview 1건을 생성한다.
7. 사용자가 지정한 개수만큼 이미지와 JSON을 export한다.

MVP에서 제외할 수 있는 것:

- 완전 자동 스키마 추론
- 모든 문서 포맷에 대한 완벽한 layout 이해
- 고품질 diffusion 기반 스타일 보존 텍스트 생성
- 복잡한 multi-page template dependency
- 클라우드/멀티유저 협업 기능

## 8. 단계별 빌드업 제안

### Phase 0. 프로젝트 골격과 샘플 데이터 준비

- Python package 구조를 만든다.
- `samples/`에 공개 가능하거나 더미로 만든 문서 이미지를 둔다.
- PDF 이미지화, 이미지 로딩, 좌표계 유틸리티를 만든다.
- JSON schema 초안을 정의한다.

### Phase 1. OCR/bbox 검수 워크벤치

- seed 이미지를 GUI에 표시한다.
- OCR 결과 bbox를 overlay한다.
- bbox 선택, 삭제, 필드명 연결을 저장한다.
- 저장된 template spec을 다시 로드한다.

### Phase 2. 템플릿화와 렌더링 preview

- 선택 bbox를 마스크로 변환한다.
- OpenCV inpaint fallback부터 구현한다.
- LaMa 연동은 optional backend로 둔다.
- Pillow 기반 텍스트 렌더링과 bbox 재계산을 구현한다.
- preview에서 원본/템플릿/합성 이미지를 비교한다.

### Phase 3. 대량 생성과 export

- RenderJob 단위로 N개 샘플을 생성한다.
- KV JSON, bbox JSON, manifest를 저장한다.
- random seed와 provenance를 기록한다.
- 기본 augmentation profile을 추가한다.

### Phase 4. 품질 개선

- OCR bbox 병합/분리 UX를 개선한다.
- 필드 타입별 fake provider를 늘린다.
- 스타일 추정: 색상, 폰트 크기, 정렬, line spacing을 자동화한다.
- export adapter를 늘린다.

### Phase 5. 고급 자동화 spike

- DocRevive, TextFlow, RS-STE, AnyText 등 공개 모델의 실제 사용 가능성, 라이선스, 한국어 품질을 검증한다.
- 정밀 GT가 필요한 필드는 Python 렌더링을 유지하고, 시각적 자연스러움이 중요한 필드만 diffusion 기반 편집을 선택적으로 적용하는 hybrid mode를 검토한다.

## 9. 주요 리스크와 대응

### 9.1 OCR 품질 리스크

스캔 품질이 낮거나 표선이 복잡한 문서는 OCR bbox가 부정확할 수 있다.

대응:

- GUI에서 수동 수정 가능하게 한다.
- OCR engine을 plugin화해 교체 가능하게 한다.
- confidence가 낮은 bbox를 별도 표시한다.

### 9.2 인페인팅 품질 리스크

텍스트 제거 후 표선, 배경 패턴, 도장 주변이 깨질 수 있다.

대응:

- OpenCV fallback과 LaMa backend를 분리한다.
- bbox mask expansion 값을 조절 가능하게 한다.
- 원본/템플릿 diff preview를 제공한다.

### 9.3 렌더링 자연스러움 리스크

Python 렌더링은 정확한 GT를 만들 수 있지만 원본 문서의 폰트/안티앨리어싱과 완전히 같지 않을 수 있다.

대응:

- 스타일 preset을 템플릿별로 저장한다.
- 색상과 폰트 크기를 원본 영역에서 추정한다.
- 필요한 경우 렌더링 후 blur/noise를 약하게 적용한다.

### 9.4 개인정보/민감정보 리스크

실문서 seed에 개인정보가 포함될 수 있다.

대응:

- 원본 문서와 합성 출력의 저장 위치를 명확히 분리한다.
- provenance에 원본 경로를 기록하되 외부 export 시 제거 옵션을 둔다.
- 테스트용 공개 샘플과 실제 민감 문서를 혼용하지 않는다.

### 9.5 의존성 설치 리스크

OCR, LaMa, diffusion 모델은 설치가 무겁거나 OS/GPU 영향을 받을 수 있다.

대응:

- core pipeline은 optional dependency 없이 동작하게 한다.
- 무거운 backend는 extras 또는 adapter로 둔다.
- 설치되지 않은 단계는 비활성화하고 명확한 안내를 표시한다.

## 10. 당장 만들 첫 문서/파일 후보

이 문서 다음 단계에서 만들 후보는 다음과 같다.

- `pyproject.toml`: Python project metadata와 기본 의존성
- `src/datafactory/`: core package
- `src/datafactory/models.py`: 내부 데이터 모델
- `src/datafactory/io.py`: 이미지/PDF 로딩 및 저장
- `src/datafactory/render.py`: Pillow 렌더링과 bbox 계산
- `src/datafactory/export.py`: KV/bbox/manifest export
- `app/`: GUI prototype
- `samples/`: 더미 seed 문서
- `tests/`: 모델/렌더/export 단위 테스트

## 11. 초기 완료 기준

첫 번째 작동 가능한 milestone은 다음 조건을 만족하면 된다.

- seed 이미지 1장을 GUI 또는 CLI로 불러올 수 있다.
- 사람이 정의한 2~3개 필드에 대해 fake value를 생성할 수 있다.
- 템플릿 이미지 위에 해당 값을 렌더링할 수 있다.
- 렌더링된 값의 bbox가 JSON으로 저장된다.
- 이미지, KV JSON, bbox JSON, manifest가 한 output directory에 생성된다.
- 같은 template에서 10개 이상의 샘플을 반복 생성할 수 있다.

이 milestone을 달성한 뒤 OCR 자동화, 인페인팅 품질, GUI 편집 UX를 단계적으로 붙인다.
