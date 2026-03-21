# ArbitrageStation Release Checklist (M4)

## 1. Pre-Release Gate (Required)

1. Ensure baseline environment:
   - Python `3.11+`
   - Node `20+`
   - pnpm `10+`
2. Clean up AI analyst artifacts (one-time when decommissioning AI analyst):
   - `python3 scripts/release/cleanup-ai-artifacts.py`
   - optional override: `AI_ANALYST_LOG_DIR=/path/to/logs python3 scripts/release/cleanup-ai-artifacts.py`
3. Run unified quality gate:
   - `bash scripts/release/preflight.sh`
4. If target runtime is available, run smoke checks:
   - `bash scripts/release/preflight.sh --with-smoke`

## 2. Runtime Sanity (Required)

1. Health endpoint:
   - `GET /api/health` returns `{"status":"ok"}`
2. Readiness endpoint:
   - `GET /api/ready` returns HTTP `200` and `status=ok`
   - Database check is `ok=true`
   - Scheduler check is `ok=true`, `running=true`, `job_count>0`
3. WebSocket sanity:
   - `node scripts/release/smoke-ws.mjs`
   - Envelope contains `type/version/ts/payload` (legacy `data` kept for compatibility)

## 3. Go/No-Go Rules

## Go

- Backend quality gate passed
- Frontend quality gate passed
- `/api/health` and `/api/ready` both healthy
- WS smoke passed
- No critical alert in logs during 15-minute observation window

## No-Go

- Any quality gate failure
- `/api/ready` degraded (`503`) or scheduler not running
- WS cannot establish or envelope invalid
- Retry storm / task backlog growth during observation window

## 4. Post-Release Verification (Required)

1. Re-run smoke:
   - `bash scripts/release/smoke-api.sh`
   - `node scripts/release/smoke-ws.mjs`
2. Spot-check key pages:
   - Dashboard
   - Positions
   - SpotBasisAuto
   - SpreadMonitor
3. Confirm no repeated exceptions in backend `data/app.log` within first 30 minutes.
