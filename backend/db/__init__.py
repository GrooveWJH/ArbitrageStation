"""Boundary-safe DB package."""

from .bootstrap import init_db
from .engine import Base, SessionLocal, engine, get_db
from . import models as _models
from .types import UTC, UTCDateTime

AppConfig = _models.AppConfig
AutoTradeConfig = _models.AutoTradeConfig
BacktestDataJob = _models.BacktestDataJob
EmailConfig = _models.EmailConfig
EquitySnapshot = _models.EquitySnapshot
Exchange = _models.Exchange
FundingAssignment = _models.FundingAssignment
FundingCursor = _models.FundingCursor
FundingLedger = _models.FundingLedger
FundingRate = _models.FundingRate
MarketSnapshot15m = _models.MarketSnapshot15m
PairUniverseDaily = _models.PairUniverseDaily
PnlV2DailyReconcile = _models.PnlV2DailyReconcile
Position = _models.Position
RiskRule = _models.RiskRule
SpotBasisAutoConfig = _models.SpotBasisAutoConfig
SpreadPosition = _models.SpreadPosition
Strategy = _models.Strategy
TradeLog = _models.TradeLog

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
    "UTC",
    "UTCDateTime",
    "AppConfig",
    "AutoTradeConfig",
    "BacktestDataJob",
    "EmailConfig",
    "EquitySnapshot",
    "Exchange",
    "FundingAssignment",
    "FundingCursor",
    "FundingLedger",
    "FundingRate",
    "MarketSnapshot15m",
    "PairUniverseDaily",
    "PnlV2DailyReconcile",
    "Position",
    "RiskRule",
    "SpotBasisAutoConfig",
    "SpreadPosition",
    "Strategy",
    "TradeLog",
]
