# v1 Development Notes

## Current v1 slice

The first implementation slice intentionally avoids OCR, LaMa, and complex GUI editing. It proves the core value first:

```text
manual template JSON + seed image
  -> fake field values
  -> Pillow text rendering
  -> rendered bbox calculation
  -> image / KV JSON / bbox JSON / manifest export
```

`seed_samples/` is treated as an input-only folder for real document examples. Generated templates live under `templates/`; generated outputs live under `outputs/`.

## Commands

Inspect an image:

```bash
PYTHONPATH=src ./.venv/bin/python -m datafactory.cli inspect seed_samples/path/to/page.jpg
```

Create a starter template with default placeholder fields:

```bash
PYTHONPATH=src ./.venv/bin/python -m datafactory.cli draft-template \
  seed_samples/path/to/page.jpg \
  --out templates/my_template.json
```

Create a starter template with explicit manual fields:

```bash
PYTHONPATH=src ./.venv/bin/python -m datafactory.cli draft-template \
  seed_samples/path/to/page.jpg \
  --out templates/my_template.json \
  --field person_name:name:320:512:180:36 \
  --field issue_date:date:320:560:180:36
```

Render samples:

```bash
PYTHONPATH=src ./.venv/bin/python -m datafactory.cli render \
  --template templates/my_template.json \
  --count 10 \
  --out outputs/my_run
```

## Output layout

```text
outputs/my_run/
  images/sample_000001.png
  kv/sample_000001.json
  bbox/sample_000001.json
  manifest.jsonl
```

## Template notes

- `bbox` uses pixel `xywh` coordinates.
- `clear_background: true` fills the requested bbox with a nearby sampled background color before rendering text. This is only a v1 approximation, not a replacement for real inpainting.
- `font_path` defaults to a Korean-capable macOS font when available.
- If a value is fixed with `value`, the renderer uses it as-is; otherwise it generates a fake value from `type`.

## Next implementation targets

1. Streamlit preview page that loads a template, renders one preview, and overlays requested/actual bboxes.
2. Simple bbox editing UI or coordinate form controls.
3. OpenCV inpaint adapter for less blocky background clearing.
4. OCR adapter spike, starting with PaddleOCR only after Python 3.14 compatibility is confirmed locally.

## GUI prototype

Run the minimal Streamlit preview app from the repository root:

```bash
PYTHONPATH=src ./.venv/bin/streamlit run app/streamlit_app.py
```

Current GUI capabilities:

- Load an existing template JSON path.
- Render a preview image.
- Overlay requested bboxes and actual rendered bboxes.
- Download preview PNG.
- Run a batch render to an output directory.

The current GUI does not yet support mouse-based bbox drawing. Edit template JSON coordinates directly or generate a starter template with `draft-template`.

## BBox visualization artifacts

Each rendered sample now includes a bbox visualization image:

```text
outputs/my_run/visualizations/sample_000001_bbox.png
```

Color legend:

- Orange: requested template bbox, i.e. where the field was intended to render.
- Blue: actual rendered text bbox, i.e. the GT bbox calculated from the rendered text.
- Black label: `field: value`.

The manifest contains `bbox_image`, and each bbox JSON contains `image.bbox_overlay_path` so downstream review tools can load the visual check image without guessing paths.

## OCR detector evaluation harness

Run a detector and write common JSON plus overlay artifacts:

```bash
PYTHONPATH=src ./.venv/bin/python -m datafactory.cli ocr-eval \
  seed_samples/path/to/page.jpg \
  --engine paddleocr \
  --out outputs/ocr_eval
```

Output layout:

```text
outputs/ocr_eval/<engine>/<doc_id>/
  raw.json
  detections.json
  overlay.png
  summary.json
```

Available engines:

- `paddleocr`: default production detector for OCR quality evaluation. Requires `.venv-ocr` or another compatible OCR environment.
- `projection`: built-in lightweight detector for harness testing only. It is not production OCR.
- `doctr`: optional docTR adapter. Requires `python-doctr` installed in a compatible OCR environment.

Use `projection` to verify that export/overlay/report plumbing works. Use `paddleocr` and `doctr` for real detector quality evaluation.

## Inpainting baseline from OCR detections

Run non-LaMa inpainting from an existing OCR `detections.json`:

```bash
PYTHONPATH=src ./.venv-ocr/bin/python -m datafactory.cli inpaint-detections \
  outputs/ocr_eval/paddleocr/<문서명>/detections.json \
  --out outputs/inpaint_eval/paddleocr_all_bbox \
  --method telea \
  --mask-shape bbox \
  --padding 2 \
  --dilation 1 \
  --radius 3
```

Output layout:

```text
outputs/inpaint_eval/paddleocr_all_bbox/<문서명>/telea/
  mask.png
  mask_overlay.png
  inpainted_telea.png
  comparison_telea.png
  summary.json
```

The current experiment intentionally uses every PaddleOCR bbox. Later GUI workflow should let the user mark detections as `field`, `static`, `ignore`, `stamp_or_seal`, or `table_cell` before mask generation.

## BBox review policy workflow

Create an editable review policy from PaddleOCR detections:

```bash
PYTHONPATH=src ./.venv/bin/python -m datafactory.cli draft-review \
  outputs/ocr_eval/paddleocr/<문서명>/detections.json \
  --out outputs/reviews
```

Output layout:

```text
outputs/reviews/<문서명>/
  review.json
  review_overlay.png
```

Run inpainting only for detections marked `status=use`:

```bash
PYTHONPATH=src ./.venv-ocr/bin/python -m datafactory.cli inpaint-review \
  outputs/reviews/<문서명>/review.json \
  --out outputs/inpaint_eval/paddleocr_reviewed \
  --method telea
```

The Streamlit app now includes an `OCR bbox review` tab. It can create/load a review, show a status-colored overlay, select bboxes on an Altair image canvas by click/drag, apply `use/keep/ignore` to selected bboxes, edit `status` and `auto_type` through `st.data_editor`, save the review, and run use-only inpainting.

## PaddleOCR evaluation environment

PaddleOCR is installed in a separate Python 3.12 environment because the main project venv currently uses Python 3.14.

```bash
/opt/homebrew/bin/python3.12 -m venv .venv-ocr
./.venv-ocr/bin/python -m pip install --upgrade pip
./.venv-ocr/bin/python -m pip install pillow paddleocr paddlepaddle
```

Run PaddleOCR evaluation with a workspace-local PaddleX cache:

```bash
env \
  PADDLE_PDX_CACHE_HOME="$PWD/.cache/paddlex" \
  PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
  PYTHONPATH=src \
  ./.venv-ocr/bin/python -m datafactory.cli ocr-eval \
  "seed_samples/가족관계증명서/11-1.jpg" \
  --engine paddleocr \
  --out outputs/ocr_eval
```

See:

- `docs/reports/ocr/paddleocr_eval_report.md` for the first projection-vs-PaddleOCR comparison.
- `docs/reports/ocr/paddleocr_multi_sample_report.md` for the PaddleOCR-fixed multi-sample bbox test across additional text-containing seed document types.
- `docs/reports/image_processing/inpainting_baseline_report.md` for the first non-LaMa all-bbox OpenCV Telea inpainting result.
- `docs/policy_control_plan.md` for the bbox policy/control design.
- `docs/reports/policy/policy_control_implementation_report.md` for the implemented review policy workflow and reviewed-use inpainting comparison.
- `docs/reports/gui/manual_bbox_review_gui_report.md` for the click/drag manual bbox review GUI update.

## Schema/Stylesheet/Faker authoring next stage

인페인팅 이후 단계의 구조화 계획은 `docs/schema_stylesheet_faker_plan.md`에 기록한다. 다음 개발 단위는 `review.json`의 `use` bbox를 `authoring/schema.json` 초안으로 승격하고, 기본 `stylesheet.json`/`faker_profile.json`을 만든 뒤 preview render를 생성하는 Phase A다.
