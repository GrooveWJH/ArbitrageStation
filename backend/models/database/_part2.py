from ._part1 import Base, Boolean, Column, DATABASE_URL, Exchange, Float, ForeignKey, FundingAssignment, FundingCursor, FundingLedger, FundingRate, Index, Integer, Numeric, Path, Position, SADateTime, SessionLocal, Strategy, String, Text, TradeLog, TypeDecorator, UTC, UTCDateTime, UniqueConstraint, _DEFAULT_DATABASE_URL, _DEFAULT_DB_PATH, _engine_kwargs, create_engine, declarative_base, engine, get_db, inspect, os, relationship, sessionmaker, text, utc_now



class PnlV2DailyReconcile(Base):
    """Daily reconciliation result for v2 rollout observation."""
    __tablename__ = "pnl_v2_daily_reconcile"
    __table_args__ = (
        UniqueConstraint("trade_date_cn", name="uq_pnl_v2_daily_reconcile_date"),
        Index("ix_pnl_v2_daily_reconcile_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trade_date_cn = Column(String(10), nullable=False, default="")  # UTC+8 date: YYYY-MM-DD
    window_start_utc = Column(UTCDateTime, nullable=False)
    window_end_utc = Column(UTCDateTime, nullable=False)
    as_of = Column(UTCDateTime, nullable=False)
    strategy_total_pnl_usdt = Column(Float, default=0.0)
    summary_total_pnl_usdt = Column(Float, default=0.0)
    abs_diff = Column(Float, default=0.0)
    pct_diff = Column(Float, default=0.0)
    passed = Column(Boolean, default=True)
    tolerance_abs = Column(Float, default=5.0)
    tolerance_pct = Column(Float, default=0.001)
    strategy_count = Column(Integer, default=0)
    missing_strategy_count = Column(Integer, default=0)
    note = Column(String(200), default="")
    created_at = Column(UTCDateTime, default=utc_now)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now)


class RiskRule(Base):
    """User-defined risk rules 鈥?each row is one independent rule."""
    __tablename__ = "risk_rules"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    rule_type = Column(String(50))      # loss_pct / max_position_usd / max_exposure_usd / min_rate_diff / max_leverage
    threshold = Column(Float)           # the numeric trigger value
    action = Column(String(50))         # close_position / alert_only
    send_email = Column(Boolean, default=True)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(UTCDateTime, default=utc_now)


class EmailConfig(Base):
    __tablename__ = "email_config"
    id = Column(Integer, primary_key=True, default=1)
    smtp_host = Column(String(200), default="smtp.gmail.com")
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String(200), default="")
    smtp_password = Column(String(500), default="")
    from_email = Column(String(200), default="")
    to_emails = Column(String(1000), default="")    # comma-separated
    is_enabled = Column(Boolean, default=False)


class SpreadPosition(Base):
    """A price-spread arbitrage position: short high-price exchange, long low-price exchange."""
    __tablename__ = "spread_positions"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False)
    high_exchange_id = Column(Integer, ForeignKey("exchanges.id"))   # short leg
    low_exchange_id  = Column(Integer, ForeignKey("exchanges.id"))   # long leg

    # Entry snapshot
    entry_spread_pct  = Column(Float)     # spread % when entered
    entry_z_score     = Column(Float)     # z-score when entered
    position_size_usd = Column(Float)     # notional per leg in USD
    order_type        = Column(String(10), default="market")  # market / limit

    # Actual filled quantities (base currency, e.g. BTC)
    short_size_base   = Column(Float, default=0)
    long_size_base    = Column(Float, default=0)
    short_order_id    = Column(String(200), default="")
    long_order_id     = Column(String(200), default="")

    # Entry prices
    short_entry_price = Column(Float, default=0)
    long_entry_price  = Column(Float, default=0)

    # Exit targets (set at open time)
    take_profit_z     = Column(Float, nullable=True)   # entry_z - tp_delta; TP when z falls here

    # Live prices (updated periodically)
    short_current_price = Column(Float, default=0)
    long_current_price  = Column(Float, default=0)
    unrealized_pnl_usd  = Column(Float, default=0)

    # Result
    realized_pnl_usd = Column(Float, default=0)
    status           = Column(String(20), default="open")  # open / closing / closed / error
    close_reason     = Column(String(300), default="")
    short_closed     = Column(Boolean, default=False)   # True = short leg confirmed closed
    long_closed      = Column(Boolean, default=False)   # True = long leg confirmed closed
    created_at       = Column(UTCDateTime, default=utc_now)
    closed_at        = Column(UTCDateTime, nullable=True)


class EquitySnapshot(Base):
    """Periodic snapshot of total account equity across all exchanges."""
    __tablename__ = "equity_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(UTCDateTime, default=utc_now, index=True)
    total_usdt = Column(Float)          # sum across all exchanges
    per_exchange = Column(Text, default="{}")  # JSON: {exchange_name: usdt_balance}


class AppConfig(Base):
    """Global application settings."""
    __tablename__ = "app_config"
    id = Column(Integer, primary_key=True, default=1)
    auto_trade_enabled = Column(Boolean, default=False)
    data_refresh_interval = Column(Integer, default=30)     # seconds
    risk_check_interval = Column(Integer, default=10)       # seconds


class AutoTradeConfig(Base):
    """Configuration for the automatic trading engine."""
    __tablename__ = "auto_trade_config"
    id = Column(Integer, primary_key=True, default=1)

    # Strategy type toggles
    enable_cross_exchange = Column(Boolean, default=True)
    enable_spot_hedge = Column(Boolean, default=True)

    # Exchange filters (JSON arrays of exchange IDs; empty = no restriction)
    cross_exchange_allow_ids = Column(Text, default="[]")
    spot_hedge_allow_ids = Column(Text, default="[]")

    # Entry conditions
    entry_minutes_before_funding = Column(Integer, default=10)
    min_rate_diff_pct = Column(Float, default=0.05)    # cross: min rate diff %
    min_spot_rate_pct = Column(Float, default=0.05)    # spot hedge: min perp rate %
    min_annualized_pct = Column(Float, default=20.0)   # minimum annualized return to enter
    max_entry_spread_pct = Column(Float, default=-0.1) # cross: max allowed negative spread
    min_entry_basis_pct = Column(Float, default=0.0)   # spot hedge: min perp premium % over spot

    # Exit conditions
    exit_spread_threshold_pct = Column(Float, default=0.05)  # exit when |spread| <= this
    max_hold_minutes = Column(Float, default=60.0)            # safety exit N min after funding

    # Volume filters
    min_cross_volume_usd = Column(Float, default=0.0)   # min 24h futures vol for cross-exchange
    min_spot_volume_usd = Column(Float, default=0.0)    # min 24h futures vol for spot hedge

    # Position sizing
    position_size_mode = Column(String(20), default="fixed")  # fixed / dynamic
    fixed_size_usd = Column(Float, default=100.0)
    max_position_usd = Column(Float, default=1000.0)
    max_open_strategies = Column(Integer, default=5)
    funding_max_positions = Column(Integer, default=5)  # funding-arb only cap
    leverage = Column(Float, default=1.0)
    volume_cap_pct = Column(Float, default=0.1)  # dynamic: % of 24h volume as max size

    # 鈹€鈹€ Spread arbitrage settings 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    spread_arb_enabled    = Column(Boolean, default=False)
    spread_use_hedge_mode = Column(Boolean, default=True)   # False = skip opps conflicting with funding arb direction
    spread_entry_z        = Column(Float, default=1.5)   # enter when z >= this
    spread_exit_z         = Column(Float, default=0.5)   # exit when z <= this (mean reversion)
    spread_stop_z         = Column(Float, default=3.0)   # legacy absolute stop (fallback if no entry_z stored)
    spread_stop_z_delta   = Column(Float, default=1.5)   # dynamic stop = entry_z + delta
    spread_position_pct   = Column(Float, default=10.0)  # % of available balance per leg
    spread_max_positions  = Column(Integer, default=3)   # max concurrent spread positions
    spread_order_type     = Column(String(10), default="market")  # market / limit
    spread_pre_settle_mins  = Column(Integer, default=10)   # exit N min before funding settlement
    spread_min_volume_usd   = Column(Float, default=0.0)    # min 24h volume on BOTH legs to enter
    spread_cooldown_mins    = Column(Integer, default=30)   # cooldown after stop-loss before re-entry
    spread_tp_z_delta       = Column(Float, default=3.0)    # floating TP = entry_z - this delta

    # Exit logic
    fee_rate_pct = Column(Float, default=0.04)                    # fallback taker fee % per order
    pre_settle_exit_threshold_pct = Column(Float, default=0.05)   # pre-settlement stop-loss threshold %
    spread_gain_exit_threshold_pct = Column(Float, default=0.05)  # extra buffer above close fees for spread exit %
    switch_min_improvement_pct = Column(Float, default=20.0)      # min annualized improvement to justify switch %
    max_hold_cycles = Column(Integer, default=3)                  # max settlement cycles before decay check
    max_margin_utilization_pct = Column(Float, default=80.0)      # max % of total futures balance to use as margin


class SpotBasisAutoConfig(Base):
    """Configuration for the new automatic spot-perp funding arbitrage engine."""
    __tablename__ = "spot_basis_auto_config"
    id = Column(Integer, primary_key=True, default=1)

    is_enabled = Column(Boolean, default=False)
    dry_run = Column(Boolean, default=True)
    refresh_interval_secs = Column(Integer, default=10)

    # Decision thresholds
    enter_score_threshold = Column(Float, default=15.0)
    switch_min_advantage = Column(Float, default=5.0)
    switch_confirm_rounds = Column(Integer, default=3)
    entry_conf_min = Column(Float, default=0.55)
    hold_conf_min = Column(Float, default=0.45)

    # Capital utilization
    max_total_utilization_pct = Column(Float, default=75.0)
    target_utilization_pct = Column(Float, default=60.0)
    max_open_pairs = Column(Integer, default=5)
    min_pair_notional_usd = Column(Float, default=300.0)
    max_pair_notional_usd = Column(Float, default=3000.0)
    reserve_cash_pct = Column(Float, default=15.0)  # legacy, no longer used by v2 allocator
    reserve_floor_pct = Column(Float, default=2.0)
    fee_buffer_pct = Column(Float, default=0.5)
    slippage_buffer_pct = Column(Float, default=0.5)
    margin_buffer_pct = Column(Float, default=1.0)
    max_exchange_utilization_pct = Column(Float, default=35.0)
    max_symbol_utilization_pct = Column(Float, default=10.0)
    min_capacity_pct = Column(Float, default=12.0)
    max_impact_pct = Column(Float, default=0.30)
    rebalance_min_relative_adv_pct = Column(Float, default=5.0)
    rebalance_min_absolute_adv_usd_day = Column(Float, default=0.50)
    execution_retry_max_rounds = Column(Integer, default=2)
    execution_retry_backoff_secs = Column(Integer, default=8)

    # Execution / safety
    # Hard rule: spot-perp strategy runs with no unhedged exposure.
    max_unhedged_notional_pct_nav = Column(Float, default=0.0)
    max_unhedged_seconds = Column(Integer, default=0)
    delta_epsilon_abs_usd = Column(Float, default=5.0)
    delta_epsilon_nav_pct = Column(Float, default=0.01)
    repair_timeout_secs = Column(Integer, default=20)
    repair_retry_rounds = Column(Integer, default=2)
    circuit_breaker_on_repair_fail = Column(Boolean, default=True)
    data_stale_threshold_seconds = Column(Integer, default=20)
    api_fail_circuit_count = Column(Integer, default=5)
    basis_shock_exit_z = Column(Float, default=4.0)

    # Portfolio risk
    portfolio_dd_soft_pct = Column(Float, default=-2.0)
    portfolio_dd_hard_pct = Column(Float, default=-4.0)
    drawdown_peak_nav_usdt = Column(Float, default=0.0)
    drawdown_peak_reset_at = Column(UTCDateTime, nullable=True)

    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now)
