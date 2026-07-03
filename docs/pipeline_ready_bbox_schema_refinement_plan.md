# Pipeline-ready 20종 bbox/schema 2차 보정 계획

작성일: 2026-07-02

## 목표

1차 목표 범위 중 `pipeline-ready` 방식으로 생산 가능한 20종 문서에 대해, 문서별로 한 종씩 다음 항목을 시각 근거 중심으로 재검수·보정한다.

- 원본/인페인팅 템플릿/합성본/contact/multiply overlay/diff를 비교하여 bbox 위치·크기·정렬을 보정한다.
- Paddle OCR 또는 기존 수동 authoring으로 누락되기 쉬운 checkbox, 빈 form 입력칸, 표 내부 반복행/열을 실제 value 주입 가능 bbox로 보강한다.
- 텍스트가 비정상적으로 크거나 작게 렌더링되는 문제를 우선 bbox 여유 조정으로 해결하고, 필요 시 render policy를 부여한다.
  - `shrink`: bbox 안에 반드시 맞춤
  - `clip`: bbox 밖 렌더링 절단
  - `allow`: 실제 문서처럼 bbox 밖으로 자연스럽게 이어지는 짧은 텍스트 허용
  - `wrap`: 주소/문장형 값 자동 줄바꿈
- schema는 문서의 key_name 구조를 표현하는 의미 계층으로 정비하고, 렌더링용 좌표/스타일 정보는 기존 authoring schema/stylesheet와 분리 가능한 보조 JSON으로 관리한다.
- 각 문서별로 개별 보고서를 남기고, 루트 전체 진행표를 지속 업데이트한다.

## 대상 범위

이번 phase의 대상은 1차 목표 중 pipeline-ready로 분류된 20종이다. 기존 outputs에 존재하더라도 범위 외 문서는 제외한다.

| 순서 | 문서ID | 공식 문서명 | 상태 |
|---:|---|---|---|
| 1 | ID-03 | 주주명부 | 진행 예정 |
| 2 | FIN-01 | 재무제표(재무상태표·손익계산서) | 진행 예정 |
| 3 | RPT-01 | 사업계획서·자금사용계획서 | 진행 예정 |
| 4 | CRD-01 | 신용정보조회서(NICE·KCB) | 진행 예정 |
| 5 | CRD-02 | 기업신용등급평가서 | 진행 예정 |
| 6 | COL-05 | 공시지가확인원 | 진행 예정 |
| 7 | ID-11 | 실소유자 확인서(AML) | 진행 예정 |
| 8 | APP-13 | 계좌개설신청서 | 진행 예정 |
| 9 | RPT-07 | 내부 심사·결재 문서 [산출물] | 진행 예정 |
| 10 | SEC-03 | 투자성향·적합성 설문 | 진행 예정 |
| 11 | SEC-01 | 투자설명서·증권신고서 | 진행 예정 |
| 12 | APP-14 | 카드발급신청서 | 진행 예정 |
| 13 | TRD-07 | 발주서(PO)·거래명세서 | 진행 예정 |
| 14 | ADM-04 | 산출내역서·견적서 | 진행 예정 |
| 15 | QC-02 | 입고·검수 보고서 | 진행 예정 |
| 16 | QC-01 | 품질·시험성적서 | 진행 예정 |
| 17 | TRD-05 | 수출입신고필증 | 진행 예정 |
| 18 | TRD-01 | 상업송장(Commercial Invoice) | 진행 예정 |
| 19 | TRD-06 | 원산지증명서(C/O) | 진행 예정 |
| 20 | TRD-02 | 포장명세서(Packing List) | 진행 예정 |

## 문서별 작업 순서

1. 현재 authoring bundle 확인
   - `schema.json`, `stylesheet.json`, `faker_profile.json`, 렌더 preview, validation report 확인
2. 시각 증거 생성/확인
   - 원본 또는 인페인팅 템플릿
   - 현재 synthetic render
   - contact sheet
   - 50% overlay/multiply/diff
3. bbox 보정
   - 표/grid 문서는 행·열 경계 기준으로 bbox를 정렬한다.
   - 실제 출력 bbox는 renderer가 반환하므로 템플릿 bbox는 시각적으로 자연스럽게 약간 넓게 둔다.
4. render option 보정
   - 긴 주소/문장: `wrap` 우선
   - 원문처럼 칸 밖으로 이어지는 짧은 값: `allow`
   - 금액/숫자/정형 ID: `shrink`
   - 반드시 칸 밖을 잘라야 하는 항목: `clip`
5. schema 의미 구조 보강
   - 기존 renderer 호환 `schema.json`은 유지한다.
   - 의미 계층은 `semantic_schema.json` 및 필요 시 `field_mapping.json`으로 분리한다.
6. 샘플 재생성 및 검증
   - preview/batch render
   - validation warning 0건 또는 사유 기록
   - 시각 비교 결과와 잔여 리스크 기록

## 산출물

- 진행표: `docs/reports/progress/20260702_pipeline_ready_bbox_schema_refinement_progress.md`
- 문서별 보고서: `docs/reports/bbox_schema_refinement/{doc_id}_{slug}.md`
- 문서별 의미 schema: `workbench/documents/{문서명}__{doc_id}/authoring/semantic_schema.json`
- 필요 시 보정된 `schema.json`, `stylesheet.json`, `faker_profile.json`
- 보정 후 synthetic sample 및 QA 이미지: `outputs/pipeline_ready/{doc_id}_{문서명}/` 및 `outputs/style_calibration/{doc_id}_{문서명}/`
