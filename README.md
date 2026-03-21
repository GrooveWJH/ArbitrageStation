# ArbitrageStation

ArbitrageStation is a crypto arbitrage system focused on safety-first operations:
risk control, execution reliability, and reconciliation stability.

## Runtime Baseline

- Python: `3.11+` (project baseline is `3.11`)
- Node.js: `20+`
- Package manager (frontend): `pnpm@10`
- Virtualenv tool: `uv` (required by `scripts/dev/setup.*`)

## Quick Start

### Unified Setup

```bash
bash scripts/dev/setup.sh
```

If `uv` is missing, install it first:
- https://docs.astral.sh/uv/getting-started/installation/

### Unified Start

```bash
bash scripts/dev/start.sh
```

### Windows (PowerShell)

```powershell
pwsh -File scripts/dev/setup.ps1
pwsh -File scripts/dev/start.ps1
```

### Manual Start (optional)

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend start
```

## Quality Gates

Run the same gates used by CI.

### Backend gate

```bash
bash scripts/quality-gate-backend.sh
```

Gate order:

1. structure gates (line limit / loader / split-aggregator / chain imports)
2. boundary gates (domain-infra / layer boundaries / legacy imports)
3. `ruff`
4. compile check
5. unit tests

### Frontend gate

```bash
bash scripts/quality-gate-frontend.sh
```

Gate order:

1. line-limit hard gate (`<=440`, with temporary whitelist)
2. line-limit target gate (`<=320`, whitelist only for approved oversized pages)
3. `biome` lint
4. frontend tests (`pnpm --dir frontend test`)
5. production build smoke
   - gate script uses `GENERATE_SOURCEMAP=false` to reduce third-party sourcemap noise

Run frontend local regression tests:

```bash
pnpm --dir frontend test
```

## Release Preflight

Run release checks with unified commands:

```bash
bash scripts/release/preflight.sh
```

Run with runtime smoke checks (requires backend running at `http://127.0.0.1:8000`):

```bash
bash scripts/release/preflight.sh --with-smoke
```

## Ops Runbooks

- [Release checklist](docs/ops/00-release-checklist.md)
- [Runtime runbook](docs/ops/01-runtime-runbook.md)
- [Observability and alerts](docs/ops/02-observability-and-alerts.md)
- [Rollback and recovery](docs/ops/03-rollback-and-recovery.md)
- [Data rebuild and import](docs/ops/04-data-rebuild-and-import.md)

## CI Workflows

- Backend: `.github/workflows/backend-ci.yml`
- Frontend: `.github/workflows/frontend-ci.yml`

Both workflows call the same gate scripts under `scripts/` to keep local and CI behavior aligned.
