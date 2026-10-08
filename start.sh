#!/usr/bin/env bash
# Drama Series Agent launcher (Linux / macOS / Git Bash / WSL)
# Origin host: Pixelle-Video-v0.1.15-win64 (streamlit start.bat) -> this repo is the new home.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
WITH_WEB=0
SKIP_INSTALL=0

usage() {
  cat <<'EOF'
Usage: ./start.sh [options]

  --host HOST       API bind host (default: 127.0.0.1)
  --port PORT       API port (default: 8000)
  --with-web        Also start Vite web workbench (web/)
  --skip-install    Do not auto pip/npm install
  -h, --help        Show this help

Env:
  DRAMA_SERIES_ROOT  Set to repo root automatically
  COMFYUI_URL        Default http://127.0.0.1:8188 if unset
  Optional .env next to this script is sourced when present
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --with-web) WITH_WEB=1; shift ;;
    --skip-install) SKIP_INSTALL=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

export DRAMA_SERIES_ROOT="$ROOT"
export COMFYUI_URL="${COMFYUI_URL:-http://127.0.0.1:8188}"

if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "$ROOT/.env"
  set +a
  export DRAMA_SERIES_ROOT="$ROOT"
fi

pick_python() {
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    echo "$ROOT/.venv/bin/python"
  elif [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
    echo "$ROOT/.venv/Scripts/python.exe"
  elif command -v python3 >/dev/null 2>&1; then
    echo "python3"
  else
    echo "python"
  fi
}

PYTHON="$(pick_python)"

if ! command -v "$PYTHON" >/dev/null 2>&1 && [[ ! -x "$PYTHON" ]]; then
  echo "[ERROR] Python not found. Create a venv first:"
  echo "  python -m venv .venv && .venv/bin/pip install -e \".[render,dev]\""
  exit 1
fi

if [[ "$SKIP_INSTALL" -eq 0 ]]; then
  if ! "$PYTHON" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "[Setup] Installing package (editable)..."
    "$PYTHON" -m pip install -e ".[render,dev]"
  fi
fi

WEB_PID=""
cleanup() {
  if [[ -n "$WEB_PID" ]] && kill -0 "$WEB_PID" 2>/dev/null; then
    kill "$WEB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "========================================"
echo "  Drama Series Agent"
echo "========================================"
echo "  Root:  $DRAMA_SERIES_ROOT"
echo "  API:   http://${HOST}:${PORT}"
echo "  Docs:  http://${HOST}:${PORT}/docs"
echo "  Comfy: $COMFYUI_URL"
echo "  Ctrl+C to stop"
echo "========================================"
echo

if [[ "$WITH_WEB" -eq 1 ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "[WARN] npm not found; skipping web"
  else
    if [[ "$SKIP_INSTALL" -eq 0 && ! -d "$ROOT/web/node_modules" ]]; then
      echo "[Setup] npm install in web/..."
      (cd "$ROOT/web" && npm install)
    fi
    echo "[Starting] Vite web workbench..."
    (cd "$ROOT/web" && npm run dev) &
    WEB_PID=$!
  fi
fi

echo "[Starting] FastAPI..."
"$PYTHON" "$ROOT/scripts/run_api.py" --host "$HOST" --port "$PORT"
