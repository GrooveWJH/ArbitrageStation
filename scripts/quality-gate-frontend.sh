#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "[frontend-gate] python3/python not found"
    exit 127
  fi
fi

echo "[frontend-gate] 1/5 line-limit-hard(<=440)"
"${PYTHON_BIN}" backend/tools/check_line_limit.py \
  --root frontend/src \
  --extensions js,jsx,ts,tsx \
  --max-lines 440 \
  --exceptions-file frontend/tools/line_limit_exceptions.txt

echo "[frontend-gate] 2/5 line-limit-target(<=320)"
"${PYTHON_BIN}" backend/tools/check_line_limit.py \
  --root frontend/src \
  --extensions js,jsx,ts,tsx \
  --max-lines 320 \
  --exceptions-file frontend/tools/line_limit_exceptions.txt

echo "[frontend-gate] 3/5 biome-lint"
pnpm --dir frontend lint

echo "[frontend-gate] 4/5 frontend-test"
pnpm --dir frontend test

echo "[frontend-gate] 5/5 build-smoke"
GENERATE_SOURCEMAP=false pnpm --dir frontend build
