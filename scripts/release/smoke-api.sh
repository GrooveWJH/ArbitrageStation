#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
TIMEOUT_SECS="${TIMEOUT_SECS:-15}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "[smoke-api] python interpreter not found"
    exit 127
  fi
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[smoke-api] curl not found"
  exit 127
fi

TMP_FILES=()
cleanup() {
  for f in "${TMP_FILES[@]:-}"; do
    rm -f "${f}" || true
  done
}
trap cleanup EXIT

request_json() {
  local path="$1"
  local expect_code="$2"
  local body
  body="$(mktemp)"
  TMP_FILES+=("${body}")

  local code
  if ! code="$(curl -sS -m "${TIMEOUT_SECS}" -o "${body}" -w "%{http_code}" "${API_BASE}${path}")"; then
    echo "[smoke-api] request failed: ${path}"
    exit 1
  fi

  if [[ "${code}" != "${expect_code}" ]]; then
    echo "[smoke-api] unexpected status for ${path}: got=${code}, expected=${expect_code}"
    echo "[smoke-api] response:"
    cat "${body}"
    exit 1
  fi
  echo "${body}"
}

assert_status_field() {
  local body_path="$1"
  local expected="$2"
  local path="$3"
  "${PYTHON_BIN}" - "${body_path}" "${expected}" "${path}" <<'PY'
import json
import sys

body_path, expected, path = sys.argv[1], sys.argv[2], sys.argv[3]
with open(body_path, "r", encoding="utf-8") as f:
    payload = json.load(f)

actual = str(payload.get("status"))
if actual != expected:
    print(f"[smoke-api] invalid status for {path}: got={actual!r}, expected={expected!r}")
    print(payload)
    raise SystemExit(1)
PY
}

echo "[smoke-api] base=${API_BASE}"

body_health="$(request_json "/api/health" "200")"
assert_status_field "${body_health}" "ok" "/api/health"
echo "[smoke-api] ok /api/health"

body_ready="$(request_json "/api/ready" "200")"
assert_status_field "${body_ready}" "ok" "/api/ready"
echo "[smoke-api] ok /api/ready"

for path in \
  "/api/exchanges/" \
  "/api/settings/app" \
  "/api/settings/risk-rules" \
  "/api/pnl/v2/summary?days=1" \
  "/api/spot-basis/auto-status"
do
  request_json "${path}" "200" >/dev/null
  echo "[smoke-api] ok ${path}"
done

echo "[smoke-api] all API smoke checks passed"
