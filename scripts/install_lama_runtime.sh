#!/usr/bin/env bash
set -euo pipefail

# Install the optional LaMa runtime into the OCR/runtime virtualenv without
# downgrading PaddleOCR/OpenCV/Pillow/Numpy packages that are already working.
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${DATAFACTORY_PYTHON:-$ROOT_DIR/.venv-ocr/bin/python}"
mkdir -p "$ROOT_DIR/.cache/torch"
export TORCH_HOME="${TORCH_HOME:-$ROOT_DIR/.cache/torch}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python runtime not found: $PYTHON_BIN" >&2
  echo "Set DATAFACTORY_PYTHON or create .venv-ocr first." >&2
  exit 1
fi

echo "Python: $PYTHON_BIN"
"$PYTHON_BIN" -V

echo
if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import torch, torchvision, simple_lama_inpainting
PY
then
  echo "LaMa runtime is already installed."
else
  echo "Installing torch/torchvision..."
  "$PYTHON_BIN" -m pip install torch torchvision

  echo
  echo "Installing simple-lama-inpainting without dependency resolution..."
  echo "Reason: its pinned Pillow/Numpy constraints can downgrade the PaddleOCR runtime."
  "$PYTHON_BIN" -m pip install --no-deps simple-lama-inpainting==0.1.2 fire==0.5.0 termcolor
fi

echo
"$PYTHON_BIN" - <<'PY'
import simple_lama_inpainting
import torch
print("simple_lama_inpainting: ok")
print("torch:", torch.__version__)
if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    print("device: mps")
elif torch.cuda.is_available():
    print("device: cuda")
else:
    print("device: cpu")
print("Note: LaMa model weights download on first inpaint if not already cached.")
PY
