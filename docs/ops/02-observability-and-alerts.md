# Observability and Alerts

## 1. Minimum Operational Signals

## API

- `/api/health` availability
- `/api/ready` availability and status
- Core endpoint p95 latency:
  - `/api/dashboard/*`
  - `/api/pnl/v2/*`
  - `/api/spot-basis/*`

## WebSocket

- Connection success rate
- Reconnect frequency
- Event envelope validity (`type/version/ts/payload`)

## Scheduler/Jobs

- Scheduler running status (`/api/ready`)
- Job count and IDs (`/api/ready`)
- Task backlog growth trend
- Retry rate trend (watch for retry storms)

## 2. Alert Triggers (Recommended)

1. **Critical**
   - `/api/health` unavailable for 1 minute
   - `/api/ready` degraded for 1 minute
2. **High**
   - WS reconnect loops > 5 times in 5 minutes
   - Repeated task failures for same job class in 5-minute window
3. **Medium**
   - Core API p95 latency > 2x baseline for 10 minutes
   - Log error volume sustained above normal baseline

## 3. Manual Checks During Incident

1. `curl -sS http://127.0.0.1:8000/api/ready`
2. `bash scripts/release/smoke-api.sh`
3. `node scripts/release/smoke-ws.mjs`
4. Inspect `backend/data/app.log` for repeated stack traces.

## 4. Escalation Rule

- If critical alerts persist for more than 10 minutes after first remediation action, execute rollback plan in `03-rollback-and-recovery.md`.
