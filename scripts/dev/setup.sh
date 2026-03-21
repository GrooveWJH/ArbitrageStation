#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PNPM_VERSION="${PNPM_VERSION:-10.11.0}"
UV_INSTALL_HINT="Install uv first: https://docs.astral.sh/uv/getting-started/installation/"

log() {
  echo "[dev-setup] $*"
}

fail() {
  echo "[dev-setup] ERROR: $*" >&2
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
  command -v pnpm >/dev/null 2>&1 || fail "pnpm not found. Install pnpm 10+ or enable corepack."
}

command -v node >/dev/null 2>&1 || fail "node not found. Install Node.js 20+."
command -v uv >/dev/null 2>&1 || fail "uv not found. ${UV_INSTALL_HINT}"
ensure_pnpm

log "root=${ROOT_DIR}"
log "uv=$(uv --version)"
log "node=$(node --version)"
log "pnpm=$(pnpm --version)"

if [[ ! -d "${ROOT_DIR}/.venv" ]]; then
  log "creating virtualenv at .venv"
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    uv venv --python "${PYTHON_BIN}" "${ROOT_DIR}/.venv"
  else
    uv venv "${ROOT_DIR}/.venv"
  fi
fi

VENV_PY="${ROOT_DIR}/.venv/bin/python"
[[ -x "${VENV_PY}" ]] || fail "virtualenv python not found at ${VENV_PY}"

log "installing backend dependencies"
uv pip install --python "${VENV_PY}" -r "${ROOT_DIR}/backend/requirements.txt"

log "installing frontend dependencies"
pnpm --dir "${ROOT_DIR}/frontend" install --frozen-lockfile

log "setup complete"
log "next: bash scripts/dev/start.sh"
