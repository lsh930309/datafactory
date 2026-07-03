# Pure Semantic Schema / GT / BBox Export 정비 지침

작성일: 2026-07-03

## 목표

1차 목표 중 pipeline 방식으로 생성되는 문서의 `semantic_schema.json`, 최종 GT JSON, 최종 BBox JSON에서 모든 metadata를 제거한다.

- 문서명 wrapper도 metadata로 간주하여 제거한다.
- GT는 metadata 없는 semantic schema를 복제한 뒤 leaf value만 주입한다.
- BBox는 GT와 동일한 key 구조를 복제한 뒤 leaf에 `{l,t,r,b}`만 주입한다.
- 문서 식별 정보는 폴더명과 manifest XLSX에서만 관리한다.

## 사전 백업

작업 시작 전 다음 백업을 생성한다.

- `workbench/`
- `outputs/results/`
- 백업 위치: `.bin/backups/pure_semantic_gt_export_{timestamp}/`

## Semantic Schema 규칙

`workbench/documents/*/authoring/semantic_schema.json`은 다음만 포함한다.

- 실제 KIE key 구조
- leaf는 빈 문자열 `""`

다음은 금지한다.

- `schema_version`
- `doc_id`
- `title`
- `created_at`
- `updated_at`
- `purpose`
- `notes`
- `field_mapping`
- 최상위 문서명 wrapper

## GT 규칙

`sample_000.json`은 semantic schema와 같은 구조만 가진다.

- metadata 없음
- 문서명 wrapper 없음
- leaf value만 샘플별 생성값으로 치환

## BBox 규칙

`sample_000-bbox.json`은 GT와 같은 key tree만 가진다.

- metadata 없음
- 문서명 wrapper 없음
- leaf는 `{l,t,r,b}` 네 좌표만 포함
- `field`, `key`, `value`, `image`, `annotations`, `bbox_format`, `precision` 등 금지

## Key Name 규칙

- 실제 문서 이미지/렌더 결과의 의미를 기준으로 사람이 읽는 한국어 key를 사용한다.
- 템플릿에 이미 인쇄된 static text는 key에 포함하지 않는다.
- 영문/혼합 label은 한국어 의미 key로 치환한다.
  - 예: `Account Name 회사이름` → `회사이름`
  - 예: `For and on behalf of 회사이름` → `회사이름`
- 반복/table은 `항목명[0]`, `항목명[1]` 형태를 허용한다.

## 구현 절차

1. 20종 pipeline authoring schema의 field label을 한국어 key로 정규화한다.
2. 각 field의 `export.json_path`를 정규화된 semantic key path와 일치시킨다.
3. 각 문서의 `semantic_schema.json`을 metadata 없는 순수 key tree로 재작성한다.
4. `final_results_export.py`에서 GT/BBox 생성 방식을 semantic schema clone 기반으로 변경한다.
5. 테스트로 metadata 금지, GT/BBox tree 일치, BBox leaf 좌표 형식을 검증한다.
6. `outputs/results`를 재생성한다.
