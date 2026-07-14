# DeepAgent\-API 명세

# DeepAgent-API 명세

📄 본 문서는 **현행 SaaS 본류(DeepAgent-API)** API 명세입니다. Deep Hub(fork) UIUX 고도화 트랙의 신규 명세는 → DEEP Agent UIUX 고도화 명세 참조 (JUNGLETFT-1638).

DeepAgent-API의 주요 외부 호출 API를 공통, OCR, Parser, SaaS 과금, Webhook 기준으로 정리한다.

| 분류 | Base path | 주요 용도 |
| --- | --- | --- |
| NH BMT 반영 범위 | - | 농협 BMT 문서/Slack 논의 기반으로 본류 반영 대상과 제외 항목을 추적 |
| 공통 | `/api/v1/auth`, `/api/v1/files`, `/api/v1/converter` | 인증, 파일 업로드, 문서 변환 |
| OCR | `/api/v1/ocr`, `/api/v2/ocr` | 템플릿 OCR, 워크스페이스 OCR, OCR Direct (v2 동기/비동기), SchemaDocument |
| Parser | `/api/v1/parser`, `/api/v2/parser` | 파일 파싱 및 언어 자동 감지 기반 Parser v2 호출 |
| 결제 / 플랜 / 크레딧 | `/api/v1/plans`, `/api/v1/payments`, `/api/v1/credit` | 구독, 결제 트랜잭션, 크레딧 조회 |
| Webhook | `/api/v1/webhook`, `/api/v1/converter/webhook` | Paddle/Polaris 외부 이벤트 수신 + OCR Direct Async 작업 완료 송신 콜백 |
| API key | `/api/v2/api-key` | 발급된 API key 조회 |

## 문서 트리

```
DeepAgent-API 명세
├─ NH BMT 반영 범위
├─ 공통
│  ├─ 인증
│  └─ 파일 및 변환
├─ OCR
│  ├─ SchemaDocument
│  ├─ 템플릿 OCR
│  ├─ 워크스페이스 OCR
│  └─ OCR Direct (v2)
├─ Parser
├─ 결제 / 플랜 / 크레딧
├─ Webhook
└─ API key
```

## 문서 히스토리

| 일시 | 구분 | 변경 내용 | 참고 |
| --- | --- | --- | --- |
| 2026-06-01 | 초안 | `DeepAgent-API 명세` 루트와 공통, OCR, Parser, 결제/플랜/크레딧, Webhook 하위 문서 구조를 생성했다. | 현행 DeepAgent-API 라우터/스키마 기준 |
| 2026-06-01 | 구조 보강 | OCR 하위에 SchemaDocument 문서를 추가하고, OCR 결과 공통 스키마를 분리했다. | [SchemaDocument API](https://koreadeep.atlassian.net/wiki/spaces/KDL/pages/244089083) |
| 2026-06-01 | BMT 참고 | NH BMT 반영 범위 문서를 추가해 BMT에서 본류로 가져올 후보와 제외할 항목을 추적하도록 했다. | BMT api, NH API FE - BE |
| 2026-06-01 | 정책 결정 반영 | SaaS 본류는 동시 로그인 허용을 유지한다는 Slack 논의를 반영했다. BMT 단일 세션/heartbeat 정책은 본류 반영 대상에서 제외하고 BMT 전용 차이점으로 분리했다. | [Slack thread](https://koreadeep.slack.com/archives/C09RTSKSNNA/p1780281635347759) |
| 2026-06-04 | SchemaDocument 명세 갱신 | SchemaDocument 문서를 최신 `SchemaDocument API 명세 및 사용법 안내` 내용으로 동기화했다. | 원본 업데이트 문서, [SchemaDocument](https://koreadeep.atlassian.net/wiki/x/JwGLDg) |
| 2026-06-15 | 결제 명세 보강 | 결제 / 플랜 / 크레딧 문서에 `GET /payments/me/transaction`의 비활성 구독 처리(`400` 반환, 기존 미처리 `500` 수정)를 명시했다. | [Slack thread](https://koreadeep.slack.com/archives/C09RTSKSNNA/p1781488524082979), JUNGLETFT-1554 |
| 2026-06-19 | 트리 동기화 | 문서 트리와 분류 표를 실제 child 페이지/코드 마운팅 기준으로 동기화했다. OCR 하위에 OCR Direct (v2), 최상위에 API key 를 트리에 추가하고, OCR base path 에 `/api/v2/ocr` 를 보강(`src/api/v2/v2_router.py`)했다. API key 행 링크를 정리했다. | dev 코드/페이지 트리 기준 |
| 2026-06-29 | 비동기 OCR Direct 추가 | OCR Direct (v2) 페이지에 비동기 모드(`POST /api/v2/ocr/direct/async`, `GET /api/v2/ocr/direct/jobs/{job_id}`, webhook payload + HMAC 서명 + 5회 exp backoff 재시도) 절을 추가하고 v1.1 로 올렸다. Webhook 페이지에 송신 webhook(`ocr_direct.completed`/`ocr_direct.failed`) 절을 추가했다. 페이지를 수신/송신 두 절로 재구성하고, Polaris webhook 의 HMAC 서명 적용을 반영했다. | JUNGLETFT-1380 (Done) 의사결정 옵션 D / JUNGLETFT-1711 / GitHub PR [DEEP-API-Docs#7](https://github.com/KDL-Solution/DEEP-API-Docs/pull/7) |

## 공통 사항

- 기본 API prefix는 `/api`이다.
- 사용자 API는 대부분 인증 쿠키의 `access_token`을 사용한다.
- SSE 엔드포인트는 `text/event-stream` 응답을 반환한다.
- 파일 기반 기능은 보통 `파일 및 변환` 문서의 업로드 흐름을 먼저 따른다.

## 기준

2026-06-01 기준 `DeepAgent-API` 라우터와 스키마를 기준으로 작성했다. NH BMT 문서 기반의 추가 반영 후보는 NH BMT 반영 범위에서 별도로 추적한다.
