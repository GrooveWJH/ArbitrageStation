from __future__ import annotations

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS l0_raw (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_exchange_ms INTEGER,
  ts_recv_ms INTEGER NOT NULL,
  exchange TEXT NOT NULL,
  market TEXT NOT NULL,
  symbol TEXT NOT NULL,
  bid1 REAL NOT NULL,
  ask1 REAL NOT NULL,
  mid REAL NOT NULL,
  spread_bps REAL NOT NULL,
  payload_bytes INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_l0_key_ts ON l0_raw(exchange, market, symbol, ts_recv_ms);
CREATE INDEX IF NOT EXISTS idx_l0_ts ON l0_raw(ts_recv_ms);

CREATE TABLE IF NOT EXISTS l1_1s (
  bucket_ms INTEGER NOT NULL,
  exchange TEXT NOT NULL,
  market TEXT NOT NULL,
  symbol TEXT NOT NULL,
  open_mid REAL NOT NULL,
  high_mid REAL NOT NULL,
  low_mid REAL NOT NULL,
  close_mid REAL NOT NULL,
  avg_spread_bps REAL NOT NULL,
  samples INTEGER NOT NULL,
  bytes_sum INTEGER NOT NULL,
  PRIMARY KEY(bucket_ms, exchange, market, symbol)
);
CREATE INDEX IF NOT EXISTS idx_l1_key_ts ON l1_1s(exchange, market, symbol, bucket_ms);

CREATE TABLE IF NOT EXISTS l2_10s (
  bucket_ms INTEGER NOT NULL,
  exchange TEXT NOT NULL,
  market TEXT NOT NULL,
  symbol TEXT NOT NULL,
  open_mid REAL NOT NULL,
  high_mid REAL NOT NULL,
  low_mid REAL NOT NULL,
  close_mid REAL NOT NULL,
  avg_spread_bps REAL NOT NULL,
  samples INTEGER NOT NULL,
  bytes_sum INTEGER NOT NULL,
  PRIMARY KEY(bucket_ms, exchange, market, symbol)
);
CREATE INDEX IF NOT EXISTS idx_l2_key_ts ON l2_10s(exchange, market, symbol, bucket_ms);

CREATE TABLE IF NOT EXISTS l3_60s (
  bucket_ms INTEGER NOT NULL,
  exchange TEXT NOT NULL,
  market TEXT NOT NULL,
  symbol TEXT NOT NULL,
  open_mid REAL NOT NULL,
  high_mid REAL NOT NULL,
  low_mid REAL NOT NULL,
  close_mid REAL NOT NULL,
  avg_spread_bps REAL NOT NULL,
  samples INTEGER NOT NULL,
  bytes_sum INTEGER NOT NULL,
  PRIMARY KEY(bucket_ms, exchange, market, symbol)
);
CREATE INDEX IF NOT EXISTS idx_l3_key_ts ON l3_60s(exchange, market, symbol, bucket_ms);

CREATE TABLE IF NOT EXISTS latest_quote (
  exchange TEXT NOT NULL,
  market TEXT NOT NULL,
  symbol TEXT NOT NULL,
  ts_exchange_ms INTEGER,
  ts_recv_ms INTEGER NOT NULL,
  bid1 REAL NOT NULL,
  ask1 REAL NOT NULL,
  mid REAL NOT NULL,
  spread_bps REAL NOT NULL,
  payload_bytes INTEGER NOT NULL,
  PRIMARY KEY(exchange, market, symbol)
);

CREATE TABLE IF NOT EXISTS latest_funding (
  exchange TEXT NOT NULL,
  symbol TEXT NOT NULL,
  funding_rate REAL NOT NULL,
  next_funding_ts_ms INTEGER,
  updated_at_ms INTEGER NOT NULL,
  PRIMARY KEY(exchange, symbol)
);
CREATE INDEX IF NOT EXISTS idx_latest_funding_updated ON latest_funding(updated_at_ms);

CREATE TABLE IF NOT EXISTS latest_volume (
  exchange TEXT NOT NULL,
  market TEXT NOT NULL,
  symbol TEXT NOT NULL,
  volume_24h_quote REAL NOT NULL,
  updated_at_ms INTEGER NOT NULL,
  PRIMARY KEY(exchange, market, symbol)
);
CREATE INDEX IF NOT EXISTS idx_latest_volume_updated ON latest_volume(updated_at_ms);

CREATE TABLE IF NOT EXISTS stream_health (
  worker_id TEXT PRIMARY KEY,
  exchange TEXT NOT NULL,
  market TEXT NOT NULL,
  status TEXT NOT NULL,
  hz_p50 REAL NOT NULL,
  hz_p95 REAL NOT NULL,
  bw_mbps REAL NOT NULL,
  total_events INTEGER NOT NULL,
  total_errors INTEGER NOT NULL,
  total_reconnects INTEGER NOT NULL,
  symbol_count_total INTEGER NOT NULL,
  symbol_count_with_data INTEGER NOT NULL,
  symbol_count_no_data INTEGER NOT NULL,
  no_data_symbols TEXT NOT NULL,
  error_class_counts TEXT NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS compaction_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_ms INTEGER NOT NULL,
  action TEXT NOT NULL,
  detail TEXT NOT NULL
);
"""
