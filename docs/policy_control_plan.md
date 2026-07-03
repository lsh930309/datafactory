# BBox 정책 컨트롤 및 관리 고도화 구현 계획

Date: 2026-06-26

## 1. 문제 정의

PaddleOCR detector 자체는 현재 기본 가중치만으로도 실문서 bbox baseline으로 충분히 강하다. 하지만 `모든 bbox를 일괄 mask/inpaint` 하는 정책은 문서 구조를 크게 훼손한다.

현재 OpenCV Telea all-bbox 실험에서 확인한 주요 문제는 다음과 같다.

- 정적 라벨, 제목, 안내문까지 삭제됨
- 표 선과 겹치는 작은 숫자 bbox가 선을 끊음
- 긴 문단 영역이 넓게 흐려짐
- 도장/워터마크/QR 주변이 일부만 손상됨
- 실제로 교체할 값과 보존할 문서 양식 요소가 구분되지 않음

따라서 다음 병목은 인페인팅 모델 교체가 아니라 **bbox 사용 정책**이다.

## 2. 목표

v1.1의 목표는 완전 자동 분류기가 아니라, 사람이 빠르게 보정할 수 있는 반자동 정책 컨트롤 레이어를 만드는 것이다.

핵심 원칙:

1. 시스템이 먼저 bbox별 기본 상태를 추정한다.
2. GUI는 색상 overlay와 표 편집을 통해 빠르게 수정하게 한다.
3. 인페인팅은 `use`로 선택된 bbox만 대상으로 한다.
4. 정책 결과는 JSON으로 저장해 재사용/학습 데이터로 누적한다.
5. 처음부터 세부 유형 입력을 강제하지 않는다. `use / keep / ignore`가 v1의 핵심이다.

## 3. 상태 모델

### 3.1 Review status

| Status | 의미 | 인페인팅 대상 |
| --- | --- | --- |
| `use` | 제거 후 새 값으로 재생성할 후보 | yes |
| `keep` | 원본 문서의 정적 요소로 보존 | no |
| `ignore` | detector noise 또는 별도 처리 대상 | no |

### 3.2 Auto type

자동 분류/후처리를 위해 optional type을 둔다. 사람은 필요할 때만 수정한다.

| Auto type | 예시 | 기본 status |
| --- | --- | --- |
| `field_value` | 날짜, 금액, 전화번호, 주소 일부, 식별번호 | `use` |
| `static_label` | 성명, 생년월일, 발급일, 제목 라벨 | `keep` |
| `table_cell` | 표 안의 작은 숫자/짧은 값 | `use` 또는 문서별 정책 |
| `long_paragraph` | 약관/안내문/하단 고지 | `keep` |
| `header_footer` | 상단/하단 발급 정보, 페이지 정보 | `keep` |
| `stamp_or_seal` | 빨간 도장/인장 영역 | `ignore` |
| `watermark` | 흐린 배경 보안문양 | `ignore` |
| `unknown` | 확신 부족 | `keep` |

## 4. 자동 pre-labeling v1 규칙

초기 구현은 ML이 아니라 explainable heuristic으로 둔다.

사용 feature:

- bbox 상대 좌표: `x/y/w/h` normalized
- bbox 면적/비율
- OCR text 길이와 문자 패턴
- confidence
- 빨간 픽셀 비율: 도장/인장 후보
- 빈 text/zero confidence
- 긴 줄/문단 여부
- 숫자/날짜/전화번호/금액/식별번호 패턴
- 공공문서 라벨 키워드

기본 방향:

- 빨간색 비율이 높으면 `stamp_or_seal -> ignore`
- 빈 text 또는 confidence 0 근처면 `unknown -> ignore`
- 문서 상단 제목/하단 안내문은 `header_footer/long_paragraph -> keep`
- 날짜/금액/전화번호/식별번호 패턴은 `field_value -> use`
- 라벨 키워드 중심 짧은 한글은 `static_label -> keep`
- 작고 반복적인 숫자 셀은 `table_cell -> use`로 시작하되, 추후 문서별 rule에서 조정
- 확신이 낮은 것은 삭제보다 보존이 안전하므로 `keep`

## 5. 저장 포맷

`review.json`:

```json
{
  "schema_version": 1,
  "source_detections": "outputs/ocr_eval/paddleocr/.../detections.json",
  "source_image": "seed_samples/.../page.jpg",
  "image": {"width": 2480, "height": 3509},
  "labels": [
    {
      "id": "det_0001",
      "text": "2026.06.26",
      "confidence": 0.98,
      "bbox": [100, 200, 150, 30],
      "polygon": [[100,200], [250,200], [250,230], [100,230]],
      "status": "use",
      "auto_type": "field_value",
      "reason": "date-like text",
      "locked": false,
      "notes": ""
    }
  ]
}
```

## 6. GUI v1

Streamlit v1에서는 외부 canvas dependency 없이 다음을 우선 구현한다.

- detections path 입력
- 자동 review 생성
- status별 색상 overlay 표시
  - `use`: 초록
  - `keep`: 파랑/회색
  - `ignore`: 빨강
- bbox table 편집
  - `status` selectbox
  - `auto_type` selectbox
  - notes 입력
- bulk controls
  - confidence threshold 아래 ignore
  - 선택/필터 결과는 후속 단계에서 mouse drag UI로 확장
- 저장 버튼
- 저장된 review의 `use` bbox만 인페인팅 실행

마우스 클릭/드래그 기반 canvas는 후속 v1.2로 분리한다. 지금은 core policy model과 저장/적용 루프를 먼저 고정한다.

## 7. CLI v1

추가 명령:

```bash
# 자동 pre-label review 생성
PYTHONPATH=src ./.venv/bin/python -m datafactory.cli draft-review \
  outputs/ocr_eval/paddleocr/<문서명>/detections.json \
  --out outputs/reviews

# review.json에서 status=use인 bbox만 인페인팅
PYTHONPATH=src ./.venv-ocr/bin/python -m datafactory.cli inpaint-review \
  outputs/reviews/<문서명>/review.json \
  --out outputs/inpaint_eval/paddleocr_reviewed \
  --method telea
```

## 8. 구현 순서

1. `review.json` 생성/로드/저장 모델 추가
2. heuristic pre-labeler 추가
3. status별 overlay renderer 추가
4. `draft-review` CLI 추가
5. `inpaint-review` CLI 추가
6. Streamlit review tab 추가
7. 테스트 추가
8. 기존 all-bbox 인페인팅 보고서와 v1 문서 갱신

## 9. 성공 기준

- 기존 `detections.json`에서 `review.json`을 생성할 수 있다.
- GUI/CLI 양쪽에서 review를 저장하고 재사용할 수 있다.
- `inpaint-review`는 `status=use`인 bbox만 mask로 만든다.
- all-bbox 대비 mask ratio가 줄어드는지 summary로 확인할 수 있다.
- 테스트가 `review 생성 -> 일부 bbox만 인페인팅 -> keep bbox 보존`을 검증한다.
