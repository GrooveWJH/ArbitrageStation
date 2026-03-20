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
    echo "[backend-gate] python3/python not found"
    exit 127
  fi
fi

if ! command -v ruff >/dev/null 2>&1; then
  echo "[backend-gate] ruff not found in PATH"
  echo "[backend-gate] run: ${PYTHON_BIN} -m pip install ruff"
  exit 127
fi

if ! "${PYTHON_BIN}" -c "import fastapi, sqlalchemy, ccxt" >/dev/null 2>&1; then
  echo "[backend-gate] missing backend dependencies for ${PYTHON_BIN}"
  echo "[backend-gate] run: ${PYTHON_BIN} -m pip install -r backend/requirements.txt"
  exit 2
fi

echo "[backend-gate] 1/10 line-limit"
"${PYTHON_BIN}" backend/tools/check_line_limit.py \
  --root backend \
  --max-lines 400 \
  --exceptions-file backend/tools/line_limit_exceptions.txt

echo "[backend-gate] 2/10 no-loader"
"${PYTHON_BIN}" backend/tools/check_no_loader.py --root backend

echo "[backend-gate] 3/10 no-split-aggregator"
"${PYTHON_BIN}" backend/tools/check_no_split_aggregator.py --root backend

echo "[backend-gate] 4/10 no-chain-imports"
"${PYTHON_BIN}" backend/tools/check_no_chain_imports.py \
  --root backend \
  --exceptions-file backend/tools/chain_import_exceptions.txt

echo "[backend-gate] 5/10 domain-infra-boundary"
"${PYTHON_BIN}" backend/tools/check_domain_infra_imports.py --root backend

echo "[backend-gate] 6/10 layer-boundaries"
"${PYTHON_BIN}" backend/tools/check_layer_boundaries.py --root backend

echo "[backend-gate] 7/10 no-legacy-api-imports"
"${PYTHON_BIN}" backend/tools/check_no_legacy_api_imports.py --root backend

echo "[backend-gate] 8/10 ruff"
ruff check backend --config backend/ruff.toml

echo "[backend-gate] 9/10 compile"
"${PYTHON_BIN}" -m compileall -q backend

echo "[backend-gate] 10/10 unittest"
"${PYTHON_BIN}" -m unittest discover -s backend/tests -p "test_*.py" -v
