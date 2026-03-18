from ._part2 import AppConfig, AutoTradeConfig, Base, Boolean, Column, DATABASE_URL, EmailConfig, EquitySnapshot, Exchange, Float, ForeignKey, FundingAssignment, FundingCursor, FundingLedger, FundingRate, Index, Integer, Numeric, Path, PnlV2DailyReconcile, Position, RiskRule, SADateTime, SessionLocal, SpotBasisAutoConfig, SpreadPosition, Strategy, String, Text, TradeLog, TypeDecorator, UTC, UTCDateTime, UniqueConstraint, _DEFAULT_DATABASE_URL, _DEFAULT_DB_PATH, _engine_kwargs, create_engine, declarative_base, engine, get_db, inspect, os, relationship, sessionmaker, text, utc_now



class MarketSnapshot15m(Base):
    """15m bucketed market snapshots for spot/perp backtesting replay."""
    __tablename__ = "market_snapshots_15m"
    __table_args__ = (
        UniqueConstraint(
            "exchange_id",
            "symbol",
            "market_type",
            "bucket_ts",
            name="uq_market_snapshots_15m_key",
        ),
        Index("ix_market_snapshots_15m_bucket", "bucket_ts"),
        Index("ix_market_snapshots_15m_symbol_bucket", "symbol", "bucket_ts"),
    )

    id = Column(Integer, primary_key=True, index=True)
    exchange_id = Column(Integer, ForeignKey("exchanges.id"), nullable=False)
    symbol = Column(String(64), nullable=False)
    market_type = Column(String(10), nullable=False)  # perp | spot
    bucket_ts = Column(UTCDateTime, nullable=False)

    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    open_interest = Column(Float, nullable=True)
    bid_price = Column(Float, nullable=True)
    ask_price = Column(Float, nullable=True)

    source_ts = Column(UTCDateTime, default=utc_now)
    created_at = Column(UTCDateTime, default=utc_now)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now)


class PairUniverseDaily(Base):
    """Daily frozen pair universe to reduce survivorship bias in backtests."""
    __tablename__ = "pair_universe_daily"
    __table_args__ = (
        UniqueConstraint(
            "trade_date",
            "symbol",
            "perp_exchange_id",
            "spot_exchange_id",
            name="uq_pair_universe_daily_key",
        ),
        Index("ix_pair_universe_daily_trade_date", "trade_date"),
        Index("ix_pair_universe_daily_symbol_date", "symbol", "trade_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trade_date = Column(String(10), nullable=False)  # UTC date: YYYY-MM-DD
    symbol = Column(String(64), nullable=False)      # perp symbol
    spot_symbol = Column(String(64), nullable=False)
    perp_exchange_id = Column(Integer, ForeignKey("exchanges.id"), nullable=False)
    spot_exchange_id = Column(Integer, ForeignKey("exchanges.id"), nullable=False)
    perp_exchange_name = Column(String(50), default="")
    spot_exchange_name = Column(String(50), default="")
    funding_rate_pct = Column(Float, default=0.0)
    basis_pct = Column(Float, default=0.0)
    perp_volume_24h = Column(Float, default=0.0)
    spot_volume_24h = Column(Float, default=0.0)
    liquidity_score = Column(Float, default=0.0)
    rank_score = Column(Float, default=0.0)
    source = Column(String(30), default="live_scan")
    created_at = Column(UTCDateTime, default=utc_now)


class BacktestDataJob(Base):
    """Async backfill/export job metadata for replay data pipeline."""
    __tablename__ = "backtest_data_jobs"
    __table_args__ = (
        Index("ix_backtest_data_jobs_status_created", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(30), nullable=False)  # backfill | export
    status = Column(String(20), default="pending")  # pending/running/succeeded/failed
    progress = Column(Float, default=0.0)
    params_json = Column(Text, default="{}")
    result_path = Column(Text, default="")
    result_format = Column(String(10), default="")
    result_rows = Column(Integer, default=0)
    result_json = Column(Text, default="{}")
    message = Column(String(200), default="")
    error = Column(Text, default="")
    created_at = Column(UTCDateTime, default=utc_now)
    started_at = Column(UTCDateTime, nullable=True)
    finished_at = Column(UTCDateTime, nullable=True)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now)


def _migrate_columns():
    """Add any missing columns to existing tables (SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS)."""
    migrations = {
        "exchanges": [
            ("is_unified_account", "INTEGER"),
        ],
        "strategies": [
            ("funding_pnl_usd", "REAL DEFAULT 0.0"),
            ("entry_e24_net_pct", "REAL DEFAULT 0.0"),
            ("entry_open_fee_pct", "REAL DEFAULT 0.0"),
            ("entry_spot_base_qty", "REAL DEFAULT 0.0"),
            ("entry_perp_base_qty", "REAL DEFAULT 0.0"),
            ("entry_delta_base_qty", "REAL DEFAULT 0.0"),
            ("hedge_qty_mode", "TEXT DEFAULT 'base_equal'"),
        ],
        "spread_positions": [
            ("short_closed",   "INTEGER DEFAULT 0"),
            ("long_closed",    "INTEGER DEFAULT 0"),
            ("take_profit_z",  "REAL"),
        ],
        "auto_trade_config": [
            ("min_cross_volume_usd", "REAL DEFAULT 0.0"),
            ("min_spot_volume_usd",  "REAL DEFAULT 0.0"),
            ("fee_rate_pct",                    "REAL DEFAULT 0.04"),
            ("pre_settle_exit_threshold_pct",   "REAL DEFAULT 0.05"),
            ("spread_gain_exit_threshold_pct",  "REAL DEFAULT 0.05"),
            ("switch_min_improvement_pct",      "REAL DEFAULT 20.0"),
            ("max_hold_cycles",                 "INTEGER DEFAULT 3"),
            ("max_margin_utilization_pct",      "REAL DEFAULT 80.0"),
            ("spread_arb_enabled",    "INTEGER DEFAULT 0"),
            ("spread_entry_z",        "REAL DEFAULT 1.5"),
            ("spread_exit_z",         "REAL DEFAULT 0.5"),
            ("spread_stop_z",         "REAL DEFAULT 3.0"),
            ("spread_stop_z_delta",   "REAL DEFAULT 1.5"),
            ("spread_position_pct",   "REAL DEFAULT 10.0"),
            ("spread_max_positions",  "INTEGER DEFAULT 3"),
            ("spread_order_type",     "TEXT DEFAULT 'market'"),
            ("spread_pre_settle_mins", "INTEGER DEFAULT 10"),
            ("spread_min_volume_usd",  "REAL DEFAULT 0.0"),
            ("spread_cooldown_mins",   "INTEGER DEFAULT 30"),
            ("spread_tp_z_delta",      "REAL DEFAULT 3.0"),
            ("funding_max_positions",  "INTEGER DEFAULT 5"),
            ("spread_use_hedge_mode",  "INTEGER DEFAULT 1"),
        ],
        "spot_basis_auto_config": [
            ("target_utilization_pct", "REAL DEFAULT 60.0"),
            ("max_open_pairs", "INTEGER DEFAULT 5"),
            ("min_pair_notional_usd", "REAL DEFAULT 300.0"),
            ("max_pair_notional_usd", "REAL DEFAULT 3000.0"),
            ("reserve_floor_pct", "REAL DEFAULT 2.0"),
            ("fee_buffer_pct", "REAL DEFAULT 0.5"),
            ("slippage_buffer_pct", "REAL DEFAULT 0.5"),
            ("margin_buffer_pct", "REAL DEFAULT 1.0"),
            ("min_capacity_pct", "REAL DEFAULT 12.0"),
            ("max_impact_pct", "REAL DEFAULT 0.30"),
            ("rebalance_min_relative_adv_pct", "REAL DEFAULT 5.0"),
            ("rebalance_min_absolute_adv_usd_day", "REAL DEFAULT 0.50"),
            ("execution_retry_max_rounds", "INTEGER DEFAULT 2"),
            ("execution_retry_backoff_secs", "INTEGER DEFAULT 8"),
            ("delta_epsilon_abs_usd", "REAL DEFAULT 5.0"),
            ("delta_epsilon_nav_pct", "REAL DEFAULT 0.01"),
            ("repair_timeout_secs", "INTEGER DEFAULT 20"),
            ("repair_retry_rounds", "INTEGER DEFAULT 2"),
            ("circuit_breaker_on_repair_fail", "INTEGER DEFAULT 1"),
            ("drawdown_peak_nav_usdt", "REAL DEFAULT 0.0"),
            ("drawdown_peak_reset_at", "TIMESTAMP"),
        ],
    }
    insp = inspect(engine)
    with engine.connect() as conn:
        for table, cols in migrations.items():
            try:
                existing = {c["name"] for c in insp.get_columns(table)}
            except Exception:
                continue
            for col_name, col_def in cols:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"))
        # Funding stability queries filter by exchange_id + symbol + timestamp on a
        # multi-million-row table; keep indexes guaranteed on existing databases.
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_funding_rates_exchange_symbol_ts "
                "ON funding_rates(exchange_id, symbol, timestamp)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_funding_rates_timestamp "
                "ON funding_rates(timestamp)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_funding_ledger_exchange_symbol_time "
                "ON funding_ledger(exchange_id, symbol, funding_time)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_funding_ledger_ingested_at "
                "ON funding_ledger(ingested_at)"
            )
        )
        # Upgrade dedupe index to source-agnostic key. Safe for repeated startup.
        try:
            idx_names = {ix["name"] for ix in insp.get_indexes("funding_ledger")}
        except Exception:
            idx_names = set()
        if "uq_funding_ledger_fallback_v2" not in idx_names:
            conn.execute(
                text(
                    "DELETE FROM funding_ledger WHERE id NOT IN ("
                    "SELECT MIN(id) FROM funding_ledger "
                    "GROUP BY exchange_id, account_key, symbol, funding_time, side, amount_norm)"
                )
            )
            conn.execute(text("DROP INDEX IF EXISTS uq_funding_ledger_fallback"))
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_funding_ledger_fallback_v2 "
                    "ON funding_ledger(exchange_id, account_key, symbol, funding_time, side, amount_norm)"
                )
            )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_funding_assignments_strategy "
                "ON funding_assignments(strategy_id)"
            )
        )
        conn.commit()


def _maybe_fix_gbk_utf8_mojibake(value: str) -> str:
    text = str(value or "")
    if not text:
        return text
    markers = (
        "鐜拌揣",
        "鍚堢害",
        "瀵瑰啿",
        "寮哄埗姝㈡崯",
        "椋庢帶",
        "浜忔崯",
        "鍗曚粨浣",
        "鎬绘暈",
        "褰撳墠璐圭巼",
    )
    if not any(m in text for m in markers):
        return text
    try:
        fixed = text.encode("gbk").decode("utf-8")
    except Exception:
        return text
    return fixed or text
