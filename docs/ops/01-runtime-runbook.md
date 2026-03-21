# Runtime Runbook

## 1. Local Start

## Unified scripts (Linux/macOS)

```bash
bash scripts/dev/setup.sh
bash scripts/dev/start.sh
```

Prerequisite: install `uv` first if missing:
- https://docs.astral.sh/uv/getting-started/installation/

## Windows (PowerShell)

```powershell
pwsh -File scripts/dev/setup.ps1
pwsh -File scripts/dev/start.ps1
```

## Manual start (optional)

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend start
```

## 2. Runtime Health Commands

```bash
curl -sS http://127.0.0.1:8000/api/health
curl -sS http://127.0.0.1:8000/api/ready
bash scripts/release/smoke-api.sh
node scripts/release/smoke-ws.mjs
python3 scripts/release/cleanup-ai-artifacts.py
```

## 3. Frontend WS Runtime Config

Frontend WS endpoint priority:

1. `REACT_APP_WS_URL`
2. `REACT_APP_WS_HOST` + `REACT_APP_WS_PORT` + `REACT_APP_WS_PATH`
3. Auto-detect from browser location (`localhost` defaults to backend port `8000`)

Examples:

```bash
# Full explicit URL
REACT_APP_WS_URL=wss://api.example.com/ws

# Split host/port/path
REACT_APP_WS_HOST=127.0.0.1
REACT_APP_WS_PORT=8000
REACT_APP_WS_PATH=/ws
```

## 4. Common Failure Playbook

## Symptom: `/api/ready` returns `503`

1. Check response `checks.database` and `checks.scheduler`.
2. If database failed:
   - Verify `DATABASE_URL`
   - Verify data directory permission
3. If scheduler failed or `running=false`:
   - Restart backend process
   - Re-check `/api/ready`

## Symptom: Frontend loads but data stale

1. Verify backend is reachable:
   - `bash scripts/release/smoke-api.sh`
2. Verify WS stream:
   - `node scripts/release/smoke-ws.mjs`
3. Inspect backend logs for repeated fetch or retry errors.

## Symptom: WS reconnect loop in browser

1. Confirm backend `/ws` is reachable on port `8000`.
2. Confirm reverse proxy/network allows WS upgrade.
3. Confirm smoke script receives valid envelope.
4. Verify frontend WS env vars are not pointing to stale host/port.

## 5. Log Locations

- Backend application log:
  - `backend/data/app.log`
- Frontend runtime issues:
  - Browser console
