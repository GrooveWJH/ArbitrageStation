from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, Text, Index, UniqueConstraint, Numeric, text, inspect
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.types import TypeDecorator, DateTime as SADateTime
import os
from pathlib import Path
from core.time_utils import UTC, utc_now

_DEFAULT_DB_PATH = (Path(__file__).resolve().parents[1] / "data" / "arbitrage.db").resolve()
_DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_DEFAULT_DATABASE_URL = f"sqlite:///{_DEFAULT_DB_PATH.as_posix()}"

DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL)

_engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
    # Raise pool capacity to avoid scheduler bursts exhausting connections.
    "pool_size": 30,
    "max_overflow": 60,
    # Fail fast instead of blocking request thread for 30s on pool starvation.
    "pool_timeout": 5,
}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {
        "check_same_thread": False,
        "timeout": 30,
    }

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UTCDateTime(TypeDecorator):
    """Store datetimes as UTC-naive in DB and expose as timezone-aware UTC in Python."""

    impl = SADateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Exchange(Base):
    __tablename__ = "exchanges"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)          # ccxt id, e.g. "binance"
    display_name = Column(String(100))
    api_key = Column(String(500), default="")
    api_secret = Column(String(500), default="")
    passphrase = Column(String(200), default="")                    # for OKX, etc.
    is_active = Column(Boolean, default=True)
    is_testnet = Column(Boolean, default=False)
    # None means "use exchange default profile"; True/False is explicit override.
    is_unified_account = Column(Boolean, nullable=True)
    created_at = Column(UTCDateTime, default=utc_now)


class Strategy(Base):
    """A running arbitrage strategy instance (links two positions)."""
    __tablename__ = "strategies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    strategy_type = Column(String(50))          # cross_exchange / spot_hedge
    symbol = Column(String(50))
    long_exchange_id = Column(Integer, ForeignKey("exchanges.id"))
    short_exchange_id = Column(Integer, ForeignKey("exchanges.id"))
    initial_margin_usd = Column(Float, default=0)
    status = Column(String(20), default="active")   # active / closed / closing
    close_reason = Column(String(200), default="")
    funding_pnl_usd = Column(Float, default=0)   # accumulated funding fees earned during holding
    entry_e24_net_pct = Column(Float, default=0)   # entry-time E24 net expectation (pct/day)
    entry_open_fee_pct = Column(Float, default=0)  # entry-time one-side total fee pct (spot+perp)
    entry_spot_base_qty = Column(Float, default=0)  # entry-time spot base quantity
    entry_perp_base_qty = Column(Float, default=0)  # entry-time perp base quantity (base-equivalent)
    entry_delta_base_qty = Column(Float, default=0)  # entry-time spot-perp base delta
    hedge_qty_mode = Column(String(20), default="base_equal")  # base_equal | notional_equal
    created_at = Column(UTCDateTime, default=utc_now)
    closed_at = Column(UTCDateTime, nullable=True)

    positions = relationship("Position", back_populates="strategy")


class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    exchange_id = Column(Integer, ForeignKey("exchanges.id"))
    symbol = Column(String(50))
    side = Column(String(10))           # long / short
    position_type = Column(String(20))  # spot / futures / swap
    size = Column(Float)
    entry_price = Column(Float)
    current_price = Column(Float, default=0)
    unrealized_pnl = Column(Float, default=0)
    unrealized_pnl_pct = Column(Float, default=0)
    status = Column(String(20), default="open")     # open / closed / closing
    created_at = Column(UTCDateTime, default=utc_now)
    closed_at = Column(UTCDateTime, nullable=True)

    strategy = relationship("Strategy", back_populates="positions")


class FundingRate(Base):
    __tablename__ = "funding_rates"
    __table_args__ = (
        Index("ix_funding_rates_exchange_symbol_ts", "exchange_id", "symbol", "timestamp"),
        Index("ix_funding_rates_timestamp", "timestamp"),
    )
    id = Column(Integer, primary_key=True, index=True)
    exchange_id = Column(Integer, ForeignKey("exchanges.id"))
    symbol = Column(String(50))
    rate = Column(Float)
    next_funding_time = Column(UTCDateTime, nullable=True)
    open_interest = Column(Float, nullable=True)
    volume_24h = Column(Float, nullable=True)
    timestamp = Column(UTCDateTime, default=utc_now)


class TradeLog(Base):
    __tablename__ = "trade_logs"
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    action = Column(String(30))         # open / close / emergency_close
    exchange = Column(String(50))
    symbol = Column(String(50))
    side = Column(String(10))
    price = Column(Float)
    size = Column(Float)
    reason = Column(String(500), default="")
    timestamp = Column(UTCDateTime, default=utc_now)


class FundingLedger(Base):
    """Normalized funding-fee events with strong idempotency key."""
    __tablename__ = "funding_ledger"
    __table_args__ = (
        UniqueConstraint("normalized_hash", name="uq_funding_ledger_hash"),
        UniqueConstraint(
            "exchange_id",
            "account_key",
            "symbol",
            "funding_time",
            "side",
            "amount_norm",
            name="uq_funding_ledger_fallback",
        ),
        Index("ix_funding_ledger_exchange_symbol_time", "exchange_id", "symbol", "funding_time"),
        Index("ix_funding_ledger_funding_time", "funding_time"),
        Index("ix_funding_ledger_ingested_at", "ingested_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    exchange_id = Column(Integer, ForeignKey("exchanges.id"), nullable=False, index=True)
    account_key = Column(String(128), nullable=False, default="")
    symbol = Column(String(64), nullable=False, default="")
    side = Column(String(16), nullable=False, default="unknown")
    funding_time = Column(UTCDateTime, nullable=False)  # stored in UTC
    amount_usdt = Column(Numeric(28, 12), nullable=False, default=0)
    amount_norm = Column(String(64), nullable=False, default="0.000000000000")
    source = Column(String(32), nullable=False, default="unknown")
    source_ref = Column(String(255), nullable=False, default="")
    normalized_hash = Column(String(64), nullable=False, default="")
    raw_payload = Column(Text, default="{}")
    ingested_at = Column(UTCDateTime, default=utc_now, nullable=False)


class FundingCursor(Base):
    """Incremental cursor per exchange/account/symbol for funding ingestion."""
    __tablename__ = "funding_cursor"
    __table_args__ = (
        UniqueConstraint(
            "exchange_id",
            "account_key",
            "symbol",
            "cursor_type",
            name="uq_funding_cursor_key",
        ),
        Index("ix_funding_cursor_updated_at", "updated_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    exchange_id = Column(Integer, ForeignKey("exchanges.id"), nullable=False, index=True)
    account_key = Column(String(128), nullable=False, default="")
    symbol = Column(String(64), nullable=False, default="*")
    cursor_type = Column(String(20), nullable=False, default="time_ms")
    cursor_value = Column(String(255), nullable=False, default="0")
    last_success_at = Column(UTCDateTime, nullable=True)
    last_error = Column(String(500), default="")
    retry_count = Column(Integer, default=0)
    created_at = Column(UTCDateTime, default=utc_now)
    updated_at = Column(UTCDateTime, default=utc_now, onupdate=utc_now)


class FundingAssignment(Base):
    """Funding event -> strategy allocation rows."""
    __tablename__ = "funding_assignments"
    __table_args__ = (
        UniqueConstraint(
            "ledger_id",
            "strategy_id",
            "position_id",
            name="uq_funding_assignment_key",
        ),
        Index("ix_funding_assignments_strategy", "strategy_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    ledger_id = Column(Integer, ForeignKey("funding_ledger.id"), nullable=False, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True, index=True)
    assigned_amount_usdt = Column(Numeric(28, 12), nullable=False, default=0)
    assigned_ratio = Column(Float, nullable=False, default=0)
    rule_version = Column(String(16), nullable=False, default="v1")
    assigned_at = Column(UTCDateTime, default=utc_now, nullable=False)
