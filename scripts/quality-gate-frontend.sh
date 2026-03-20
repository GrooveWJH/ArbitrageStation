#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "[frontend-gate] 1/2 biome-lint"
pnpm --dir frontend lint

echo "[frontend-gate] 2/2 build-smoke"
pnpm --dir frontend build
