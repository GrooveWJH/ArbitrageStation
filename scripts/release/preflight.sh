#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

WITH_SMOKE="0"
if [[ "${RELEASE_WITH_SMOKE:-0}" == "1" ]]; then
  WITH_SMOKE="1"
fi
if [[ "${1:-}" == "--with-smoke" ]]; then
  WITH_SMOKE="1"
fi

echo "[release-preflight] 1/3 backend quality gate"
bash scripts/quality-gate-backend.sh

echo "[release-preflight] 2/3 frontend quality gate"
bash scripts/quality-gate-frontend.sh

if [[ "${WITH_SMOKE}" == "1" ]]; then
  echo "[release-preflight] 3/3 runtime smoke checks"
  bash scripts/release/smoke-api.sh
  node scripts/release/smoke-ws.mjs
else
  echo "[release-preflight] 3/3 runtime smoke checks skipped (pass --with-smoke to enable)"
fi

echo "[release-preflight] all checks passed"
