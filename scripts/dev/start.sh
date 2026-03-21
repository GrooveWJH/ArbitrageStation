#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PNPM_VERSION="${PNPM_VERSION:-10.11.0}"
FRONTEND_GENERATE_SOURCEMAP="${FRONTEND_GENERATE_SOURCEMAP:-false}"
BACKEND_PID=""
FRONTEND_PID=""

log() {
  echo "[dev-start] $*"
}

fail() {
  echo "[dev-start] ERROR: $*" >&2
  exit 1
}

ensure_pnpm() {
  if command -v pnpm >/dev/null 2>&1; then
    return
  fi
  if command -v corepack >/dev/null 2>&1; then
    log "pnpm not found, trying corepack..."
    corepack enable >/dev/null 2>&1 || true
    corepack prepare "pnpm@${PNPM_VERSION}" --activate >/dev/null 2>&1 || true
  fi
  command -v pnpm >/dev/null 2>&1 || fail "pnpm not found. Run setup first."
}

cleanup() {
  trap - EXIT INT TERM
  for pid in "${BACKEND_PID}" "${FRONTEND_PID}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
      kill "${pid}" >/dev/null 2>&1 || true
    fi
  done
  if [[ -n "${BACKEND_PID}" ]]; then
    wait "${BACKEND_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID}" ]]; then
    wait "${FRONTEND_PID}" >/dev/null 2>&1 || true
  fi
}

monitor_processes() {
  while true; do
    if ! kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
      wait "${BACKEND_PID}" || true
      log "backend exited"
      return 1
    fi
    if ! kill -0 "${FRONTEND_PID}" >/dev/null 2>&1; then
      wait "${FRONTEND_PID}" || true
      log "frontend exited"
      return 1
    fi
    sleep 1
  done
}

trap cleanup EXIT INT TERM

[[ -x "${ROOT_DIR}/.venv/bin/python" ]] || fail "missing .venv. Run: bash scripts/dev/setup.sh"
[[ -d "${ROOT_DIR}/frontend/node_modules" ]] || fail "missing frontend/node_modules. Run: bash scripts/dev/setup.sh"

command -v node >/dev/null 2>&1 || fail "node not found. Run setup first."
ensure_pnpm

VENV_PY="${ROOT_DIR}/.venv/bin/python"
if ! "${VENV_PY}" -c "import fastapi, sqlalchemy, ccxt" >/dev/null 2>&1; then
  fail "backend dependencies missing in .venv. Run: bash scripts/dev/setup.sh"
fi

log "starting backend http://127.0.0.1:8000"
(
  cd "${ROOT_DIR}/backend"
  exec "${VENV_PY}" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
) &
BACKEND_PID="$!"

log "starting frontend http://127.0.0.1:3000"
(
  cd "${ROOT_DIR}"
  export GENERATE_SOURCEMAP="${FRONTEND_GENERATE_SOURCEMAP}"
  exec pnpm --dir frontend start
) &
FRONTEND_PID="$!"

log "backend_pid=${BACKEND_PID} frontend_pid=${FRONTEND_PID}"
log "frontend GENERATE_SOURCEMAP=${FRONTEND_GENERATE_SOURCEMAP}"
log "press Ctrl+C to stop both services"

monitor_processes
