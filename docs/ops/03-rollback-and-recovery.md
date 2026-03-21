# Rollback and Recovery

## 1. When to Roll Back

Execute rollback if any of the following persists after initial remediation:

1. `/api/ready` remains degraded
2. Critical API unavailable
3. WS stream unusable for trading pages
4. Scheduler tasks repeatedly fail and queue keeps growing

## 2. Rollback Procedure

1. Identify last known good commit:
   - `git log --oneline`
2. Deploy that commit to runtime environment.
3. Restart backend and frontend.
4. Validate:
   - `bash scripts/release/smoke-api.sh`
   - `node scripts/release/smoke-ws.mjs`
5. Confirm `status=ok` on `/api/ready`.

## 3. Configuration Recovery

If runtime behavior differs after rollback, verify key configs:

1. `/api/settings/app`
2. `/api/settings/auto-trade-config`
3. `/api/spot-basis/auto-config`
4. `/api/spot-basis/auto-status`

Restore missing settings from last exported snapshot or audited values.

## 4. Database Recovery

If schema/data corruption suspected:

1. Stop services.
2. Backup current DB file.
3. Restore DB backup or rebuild from known-good source.
4. Run post-recovery checks:
   - `bash scripts/release/smoke-api.sh`
   - `node scripts/release/smoke-ws.mjs`

## 5. Recovery Exit Criteria

1. `/api/health` and `/api/ready` stable for 30 minutes
2. No repeated critical errors in backend logs
3. Key pages (Dashboard/Positions/SpotBasisAuto/SpreadMonitor) functional
