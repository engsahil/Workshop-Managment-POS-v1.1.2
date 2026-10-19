#!/usr/bin/env bash
# Auto Workshop Management POS v1.2.2 — Linux / macOS launcher
# Default: 127.0.0.1:8000 (auto-selects next free port if 8000 is occupied)
set -e
cd "$(dirname "$0")/backend"
PY="${PYTHON:-python3}"
if [ -x "../.venv/bin/python" ]; then
  PY="../.venv/bin/python"
elif [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
fi
if [ -n "${1:-}" ]; then
  export AWP_PORT="$1"
fi
if ! "$PY" -c "import fastapi, sqlalchemy, pydantic, argon2, jwt, uvicorn, multipart, tzdata" >/dev/null 2>&1; then
  echo "Installing dependencies from requirements.txt..."
  "$PY" -m pip install -q -r ../requirements.txt
fi
export AWP_PORT="${AWP_PORT:-${PORT:-8000}}"
export AWP_HOST="${AWP_HOST:-${HOST:-127.0.0.1}}"
export PORT="$AWP_PORT"
export HOST="$AWP_HOST"
exec "$PY" run.py "$AWP_PORT"
