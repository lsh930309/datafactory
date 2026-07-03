#!/usr/bin/env bash
set -u

# macOS one-click entrypoint for the React-based DataFactory GUI.
# Double-click this .command file, or run it from a terminal:
#   ./start_datafactory_gui.command

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR" || exit 1

API_HOST="${DATAFACTORY_API_HOST:-127.0.0.1}"
API_PORT="${DATAFACTORY_API_PORT:-8766}"
WEB_HOST="${DATAFACTORY_WEB_HOST:-127.0.0.1}"
WEB_PORT="${DATAFACTORY_WEB_PORT:-5173}"
DEFAULT_API_PORT="8766"
REQUESTED_API_PORT="$API_PORT"
REQUESTED_WEB_PORT="$WEB_PORT"
LOG_DIR="$ROOT_DIR/.cache/gui-logs"
API_LOG="$LOG_DIR/api.log"
WEB_LOG="$LOG_DIR/web.log"
URL="http://$WEB_HOST:$WEB_PORT"

API_PID=""
WEB_PID=""
CLEANED_UP="0"

mkdir -p "$LOG_DIR" "$ROOT_DIR/.cache/npm-react" "$ROOT_DIR/.cache/torch"
export TORCH_HOME="${TORCH_HOME:-$ROOT_DIR/.cache/torch}"

terminate_pid() {
  local label="$1"
  local pid="$2"
  if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
    return
  fi
  echo "Stopping $label (pid=$pid)..."
  kill -TERM "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ! kill -0 "$pid" 2>/dev/null; then
      wait "$pid" 2>/dev/null || true
      return
    fi
    sleep 0.2
  done
  echo "$label did not stop after TERM; forcing shutdown."
  kill -KILL "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
}

cleanup() {
  if [[ "$CLEANED_UP" == "1" ]]; then
    return
  fi
  CLEANED_UP="1"
  trap - INT TERM EXIT
  echo
  echo "Stopping DataFactory GUI..."
  terminate_pid "React dev server" "$WEB_PID"
  terminate_pid "Backend API" "$API_PID"
  echo "Stopped. You can close this window."
}

stop_and_exit() {
  cleanup
  exit 0
}

trap stop_and_exit INT TERM
trap cleanup EXIT

fail() {
  echo
  echo "ERROR: $1"
  echo "API log: $API_LOG"
  echo "Web log: $WEB_LOG"
  echo
  echo "Press Enter to close this window."
  read -r _
  exit 1
}

http_ready() {
  local url="$1"
  curl -fsS "$url" >/dev/null 2>&1
}

python_can_import() {
  local python_bin="$1"
  local module_name="$2"
  [[ -x "$python_bin" ]] || return 1
  "$python_bin" - "$module_name" <<'PY' >/dev/null 2>&1
import importlib
import sys
importlib.import_module(sys.argv[1])
PY
}

select_python() {
  if [[ -n "${DATAFACTORY_PYTHON:-}" ]]; then
    echo "$DATAFACTORY_PYTHON"
    return
  fi
  local ocr_python="$ROOT_DIR/.venv-ocr/bin/python"
  local default_python="$ROOT_DIR/.venv/bin/python"
  if python_can_import "$ocr_python" "cv2" && python_can_import "$ocr_python" "PIL"; then
    echo "$ocr_python"
    return
  fi
  echo "$default_python"
}

api_has_opencv() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import json
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=2) as response:
    payload = json.loads(response.read().decode("utf-8"))
if not payload.get("opencv", {}).get("available"):
    raise SystemExit(1)
PY
}

api_has_lama() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import json
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=2) as response:
    payload = json.loads(response.read().decode("utf-8"))
if not payload.get("lama", {}).get("available"):
    raise SystemExit(1)
PY
}

api_has_lama_resize() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import json
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=2) as response:
    payload = json.loads(response.read().decode("utf-8"))
if not payload.get("features", {}).get("lama_resize"):
    raise SystemExit(1)
PY
}

api_has_staged_gui() {
  local url="$1"
  "$PYTHON_BIN" - "$url" <<'PY' >/dev/null 2>&1
import json
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=2) as response:
    payload = json.loads(response.read().decode("utf-8"))
features = payload.get("features", {})
required = [
    "seed_images",
    "ocr_detect_endpoint",
    "staged_gui",
    "registry",
    "seed_scan",
    "seed_import",
    "seed_import_batch",
    "seed_mapping",
    "work_items",
    "workbench",
    "font_registry",
]
if not all(features.get(name) for name in required):
    raise SystemExit(1)
PY
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local pid="${3:-}"
  local log_file="${4:-}"
  local attempt
  for attempt in $(seq 1 80); do
    if http_ready "$url"; then
      echo "$name is ready: $url"
      return 0
    fi
    if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
      echo "$name process exited before becoming ready."
      [[ -n "$log_file" && -f "$log_file" ]] && tail -80 "$log_file"
      return 1
    fi
    sleep 0.25
  done
  echo "$name did not become ready in time."
  [[ -n "$log_file" && -f "$log_file" ]] && tail -80 "$log_file"
  return 1
}

port_available() {
  local host="$1"
  local port="$2"
  "$PYTHON_BIN" - "$host" "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind((host, port))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
PY
}

find_available_port() {
  local host="$1"
  local start_port="$2"
  local label="$3"
  local port
  for port in $(seq "$start_port" $((start_port + 80))); do
    if port_available "$host" "$port"; then
      echo "$port"
      return 0
    fi
  done
  echo "Could not find an available $label port near $start_port." >&2
  return 1
}

stop_port_listeners() {
  local label="$1"
  local port="$2"
  local pids=""
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | sort -u || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi
  echo "Stopping existing $label listener(s) on fixed port $port..."
  local pid
  while IFS= read -r pid; do
    [[ -n "$pid" ]] && terminate_pid "$label listener" "$pid"
  done <<< "$pids"
}

open_url() {
  local url="$1"
  if ! command -v open >/dev/null 2>&1; then
    echo "Open this URL manually: $url"
    return 0
  fi
  if open "$url" >/dev/null 2>&1; then
    return 0
  fi
  if open -a "Safari" "$url" >/dev/null 2>&1; then
    return 0
  fi
  if open -a "Google Chrome" "$url" >/dev/null 2>&1; then
    return 0
  fi
  echo "Could not auto-open a browser in this environment."
  echo "Open this URL manually: $url"
}

echo "========================================"
echo "DataFactory React GUI launcher"
echo "Workspace: $ROOT_DIR"
echo "API:       http://$API_HOST:$API_PORT"
echo "Web:       $URL"
echo "========================================"
echo

PYTHON_BIN="$(select_python)"
PYTHON_HAS_LAMA="0"

if [[ ! -x "$PYTHON_BIN" ]]; then
  fail "Python virtualenv not found or not executable: $PYTHON_BIN"
fi

echo "Python:    $PYTHON_BIN"
if python_can_import "$PYTHON_BIN" "cv2"; then
  echo "OpenCV:    available (Telea/NS inpainting enabled)"
else
  echo "OpenCV:    not available (only fill inpainting will work)"
fi
if python_can_import "$PYTHON_BIN" "simple_lama_inpainting" && python_can_import "$PYTHON_BIN" "torch"; then
  PYTHON_HAS_LAMA="1"
  echo "LaMa:      available (LaMa inpainting enabled; model downloads on first use if not cached)"
else
  echo "LaMa:      not available (run ./scripts/install_lama_runtime.sh to enable)"
fi

if ! command -v npm >/dev/null 2>&1; then
  fail "npm is not installed or not on PATH. Install Node.js/npm first."
fi

if [[ ! -d "$ROOT_DIR/web/node_modules" ]]; then
  echo "Installing React/Vite dependencies..."
  NPM_CONFIG_CACHE="$ROOT_DIR/.cache/npm-react" npm --prefix "$ROOT_DIR/web" install || fail "npm install failed"
else
  echo "React/Vite dependencies already installed."
fi

echo
echo "Starting backend API..."
stop_port_listeners "Backend API" "$API_PORT"
if ! port_available "$API_HOST" "$API_PORT"; then
  fail "Fixed backend API port is still occupied after cleanup: $API_HOST:$API_PORT"
fi
: >"$API_LOG"
PYTHONPATH="$ROOT_DIR/src" "$PYTHON_BIN" -m datafactory.web_api --host "$API_HOST" --port "$API_PORT" >"$API_LOG" 2>&1 &
API_PID="$!"
wait_for_url "Backend API" "http://$API_HOST:$API_PORT/api/assets" "$API_PID" "$API_LOG" || fail "Backend API failed to start"

echo
echo "Starting React dev server..."
URL="http://$WEB_HOST:$WEB_PORT"
stop_port_listeners "React dev server" "$WEB_PORT"
if ! port_available "$WEB_HOST" "$WEB_PORT"; then
  fail "Fixed React dev server port is still occupied after cleanup: $WEB_HOST:$WEB_PORT"
fi
: >"$WEB_LOG"
DATAFACTORY_API_HOST="$API_HOST" DATAFACTORY_API_PORT="$API_PORT" NPM_CONFIG_CACHE="$ROOT_DIR/.cache/npm-react" npm --prefix "$ROOT_DIR/web" run dev -- --host "$WEB_HOST" --port "$WEB_PORT" >"$WEB_LOG" 2>&1 &
WEB_PID="$!"
wait_for_url "React dev server" "$URL" "$WEB_PID" "$WEB_LOG" || fail "React dev server failed to start"

echo
echo "Final ports:"
echo "- API: http://$API_HOST:$API_PORT"
echo "- Web: $URL"
echo "- Policy: fixed ports only; existing listeners on these ports are stopped before restart."
echo
echo "Opening browser: $URL"
open_url "$URL"

echo
echo "Ready."
echo "- Keep this Terminal window open while using the GUI."
echo "- Press Ctrl+C here to stop servers started by this launcher."
echo "- Logs:"
echo "  API: $API_LOG"
echo "  Web: $WEB_LOG"
echo

while true; do
  sleep 1
done
