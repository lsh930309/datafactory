# 수동 마스크 기반 템플릿 클린업 구현 계획

## 목표
LaMa 인페인팅이 완료된 템플릿에 남는 얼룩, 글자 잔흔, 경계 흔적을 작업자가 자유형 올가미 마스크로 지정하고, 해당 영역까지 포함해 LaMa를 다시 실행해 더 깨끗한 합성 템플릿을 만든다.

## 기본 정책
- 기본 방식은 **후처리 클린업**으로 고정한다.
- 작업자는 기존 인페인팅 결과 위에서 잔흔 영역을 표시하고, 실제 클린업도 현재 인페인팅 템플릿 이미지에 수동 cleanup mask만 적용해 수행한다.
- 기존 `lama` 인페인팅 산출물은 삭제하지 않고 `manual_cleanup` 산출물을 별도 보존한다.
- 이후 Authoring 초안/Preview/배치 생성은 cleanup 산출물이 있으면 cleanup된 `inpainted_lama.png`를 우선 사용한다.

## 저장 구조
문서별 기존 inpaint 폴더 하위에 다음 구조를 사용한다.

```text
workbench/documents/<문서폴더>/inpaint/<sample_key>/manual_cleanup/
  mask.json              # 자유형 마스크 벡터 데이터
  manual_mask.png        # 수동 마스크 raster
  mask_overlay.png       # 현재 템플릿 위 수동 mask overlay
  inpainted_lama.png     # cleanup 완료 템플릿
  comparison_lama.png    # 4-in-1 비교 이미지
  summary.json           # 실행 요약
```

## GUI 흐름
1. BBox 리뷰 후 LaMa 인페인팅을 실행한다.
2. 중앙 캔버스의 `템플릿 클린업` 탭으로 이동한다.
3. 인페인팅 결과 위에서 자유형 올가미를 드래그해 잔흔 영역을 추가한다.
4. 필요 시 마스크를 클릭해 선택하고 Delete로 삭제하거나 Cmd/Ctrl+Z로 되돌린다.
5. Cmd/Ctrl+S 또는 `마스크 저장`으로 수동 마스크를 저장한다.
6. `LaMa 클린업 재실행`을 누르면 현재 인페인팅 템플릿에 수동 마스크만 적용해 LaMa가 후처리처럼 실행된다.
7. 완료 후 캔버스는 cleanup된 템플릿으로 즉시 갱신되고, 기존 4-in-1 비교 이미지는 새 창으로 열 수 있다.

## 단축키
- `Cmd/Ctrl+S`: 현재 모드 저장. 클린업 탭에서는 수동 마스크 저장.
- `Cmd/Ctrl+Z`: 클린업 탭에서는 마지막 마스크 편집 실행 취소.
- `Delete/Backspace`: 선택된 수동 마스크 삭제.

## 검증 기준
- 수동 polygon/path가 현재 템플릿 이미지와 동일 크기의 binary mask로 rasterize된다.
- 클린업 실행은 기존 bbox mask를 다시 포함하지 않고 수동 mask만 사용한다.
- cleanup 산출물이 존재하면 workbench의 `latestInpainted`가 cleanup 결과를 우선 반환한다.
- React build와 pytest가 통과한다.
