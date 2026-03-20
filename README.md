# ArbitrageStation

ArbitrageStation is a crypto arbitrage system focused on safety-first operations:
risk control, execution reliability, and reconciliation stability.

## Runtime Baseline

- Python: `3.11+` (project baseline is `3.11`)
- Node.js: `20+`
- Package manager (frontend): `pnpm@10`

## Quick Start

### Backend

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend start
```

### Windows One-Click (local dev)

```bat
start.bat
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

1. `biome` lint
2. production build smoke

## CI Workflows

- Backend: `.github/workflows/backend-ci.yml`
- Frontend: `.github/workflows/frontend-ci.yml`

Both workflows call the same gate scripts under `scripts/` to keep local and CI behavior aligned.
