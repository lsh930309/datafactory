# Workspace Cleanup Plan

작성일: 2026-07-03

## 목표

중간 실험, 테스트, 임시 렌더링, 캐시성 부산물을 정리하여 현재 워크스페이스에서 실제 작업/최종 산출물만 빠르게 식별 가능하게 만든다.

## 보존 대상

- `workbench/`: 현재 문서 작업 원본, bbox, inpaint, authoring 상태
- `seed_samples/`: 실제 seed sample 보관소
- `registry/`: 공식 문서 분류/범위 자료
- `docs/`: 계획서, 지침서, 보고서
- `scripts/`: cleanroom/pipeline 보정 및 관리 스크립트
- `src/`, `tests/`, `web/`, `app/`: 코드
- `fonts/`, `assets/`: 렌더링에 필요한 폰트/이미지 자산
- `outputs/results/`: 현재 최종 산출물
- `.bin/backups/`: 수동 작업 손실 방지용 백업
- `.cache/`, `.venv`, `.venv-ocr`, `.playwright-browsers`, `web/node_modules`: 실행 재현에 필요한 런타임/모델/브라우저/의존성 캐시

## 정리 대상

삭제하지 않고 `.bin/trash/workspace_cleanup_{timestamp}/` 아래로 이동한다.

- `.bin/final_results_work/`: 최종 결과 생성 중간 작업 디렉터리
- `.bin/batch_authoring_20260702/`, `.bin/manual_authoring_review/`, `.bin/pipeline_ready/`, `.bin/style_calibration/`, `.bin/obsolete_style_calibration/`, `.bin/non_kie_samples/`: 이전 실험/중간 산출물
- `.bin/trash_*`: 과거 휴지통 디렉터리들을 `.bin/trash/legacy_trash_dirs/`로 집약
- `outputs/cleanroom_trials/`, `outputs/render/`, `outputs/pipeline_ready/`, `outputs/style_calibration/`, `outputs/first_priority_assessment/`: 최종 `outputs/results/`로 대체된 중간 산출물
- `outputs/results.zip`: 현재 `outputs/results/` 재생성 이후 stale 가능성이 있는 압축본
- `tmp/`: 검증/실험 임시 파일
- `.playwright-cli/`, `.pytest_cache/`, `__pycache__/`, `.DS_Store`: 실행/테스트 캐시성 파일

## 완료 기준

- 핵심 보존 디렉터리가 유지된다.
- 정리된 항목은 `.bin/trash/workspace_cleanup_{timestamp}/manifest.json`으로 추적 가능하다.
- 전체 테스트가 통과한다.
