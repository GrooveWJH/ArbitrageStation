# Data Rebuild and Import Guide

This guide covers the M4 requirement: database can be rebuilt, while key business data can be imported back.

## 1. Target Key Tables

1. Funding cashflow and allocation:
   - `funding_ledger`
   - `funding_assignments`
2. Strategy and execution snapshots:
   - `strategies`
   - `positions`
   - `trade_logs`
   - `equity_snapshots`
3. Critical runtime configs:
   - `app_config`
   - `auto_trade_config`
   - `spot_basis_auto_config`
   - `risk_rules`
   - `email_config`
4. Optional market replay data:
   - `market_snapshots_15m`
   - `pair_universe_daily`

## 2. Export Before Rebuild

Assume DB path is `data/arbitrage.db` (adjust for your environment).

```bash
mkdir -p data/backups
DB_PATH="data/arbitrage.db"
TS="$(date +%Y%m%d_%H%M%S)"

sqlite3 "${DB_PATH}" ".mode csv" ".headers on" "SELECT * FROM funding_ledger;" > "data/backups/${TS}_funding_ledger.csv"
sqlite3 "${DB_PATH}" ".mode csv" ".headers on" "SELECT * FROM funding_assignments;" > "data/backups/${TS}_funding_assignments.csv"
sqlite3 "${DB_PATH}" ".mode csv" ".headers on" "SELECT * FROM strategies;" > "data/backups/${TS}_strategies.csv"
sqlite3 "${DB_PATH}" ".mode csv" ".headers on" "SELECT * FROM positions;" > "data/backups/${TS}_positions.csv"
sqlite3 "${DB_PATH}" ".mode csv" ".headers on" "SELECT * FROM trade_logs;" > "data/backups/${TS}_trade_logs.csv"
sqlite3 "${DB_PATH}" ".mode csv" ".headers on" "SELECT * FROM equity_snapshots;" > "data/backups/${TS}_equity_snapshots.csv"
sqlite3 "${DB_PATH}" ".mode csv" ".headers on" "SELECT * FROM app_config;" > "data/backups/${TS}_app_config.csv"
sqlite3 "${DB_PATH}" ".mode csv" ".headers on" "SELECT * FROM auto_trade_config;" > "data/backups/${TS}_auto_trade_config.csv"
sqlite3 "${DB_PATH}" ".mode csv" ".headers on" "SELECT * FROM spot_basis_auto_config;" > "data/backups/${TS}_spot_basis_auto_config.csv"
sqlite3 "${DB_PATH}" ".mode csv" ".headers on" "SELECT * FROM risk_rules;" > "data/backups/${TS}_risk_rules.csv"
sqlite3 "${DB_PATH}" ".mode csv" ".headers on" "SELECT * FROM email_config;" > "data/backups/${TS}_email_config.csv"
```

## 3. Rebuild Database

1. Stop backend service.
2. Backup old DB file:
   - `cp data/arbitrage.db data/arbitrage.db.bak.${TS}`
3. Remove old DB:
   - `rm -f data/arbitrage.db`
4. Start backend once to auto-create schema:
   - `python3 -m uvicorn main:app --host 0.0.0.0 --port 8000`

## 4. Import Critical Data

Use sqlite import in the same column order as exports:

```bash
DB_PATH="data/arbitrage.db"

sqlite3 "${DB_PATH}" ".mode csv" ".import --skip 1 data/backups/<ts>_app_config.csv app_config"
sqlite3 "${DB_PATH}" ".mode csv" ".import --skip 1 data/backups/<ts>_auto_trade_config.csv auto_trade_config"
sqlite3 "${DB_PATH}" ".mode csv" ".import --skip 1 data/backups/<ts>_spot_basis_auto_config.csv spot_basis_auto_config"
sqlite3 "${DB_PATH}" ".mode csv" ".import --skip 1 data/backups/<ts>_risk_rules.csv risk_rules"
sqlite3 "${DB_PATH}" ".mode csv" ".import --skip 1 data/backups/<ts>_email_config.csv email_config"

sqlite3 "${DB_PATH}" ".mode csv" ".import --skip 1 data/backups/<ts>_strategies.csv strategies"
sqlite3 "${DB_PATH}" ".mode csv" ".import --skip 1 data/backups/<ts>_positions.csv positions"
sqlite3 "${DB_PATH}" ".mode csv" ".import --skip 1 data/backups/<ts>_trade_logs.csv trade_logs"
sqlite3 "${DB_PATH}" ".mode csv" ".import --skip 1 data/backups/<ts>_equity_snapshots.csv equity_snapshots"
sqlite3 "${DB_PATH}" ".mode csv" ".import --skip 1 data/backups/<ts>_funding_ledger.csv funding_ledger"
sqlite3 "${DB_PATH}" ".mode csv" ".import --skip 1 data/backups/<ts>_funding_assignments.csv funding_assignments"
```

## 5. Spot Basis Market Data Import (Optional)

For replay/backtest datasets, use existing API imports:

1. `POST /api/spot-basis-data/import-snapshots`
2. `POST /api/spot-basis-data/import-funding`

Or use SpotBasisBacktest page upload path fields.

## 6. Post-Import Verification

1. `bash scripts/release/smoke-api.sh`
2. `node scripts/release/smoke-ws.mjs`
3. Confirm:
   - `/api/ready` is `ok`
   - key config endpoints return expected values
   - funding and strategy pages render without 500 errors
