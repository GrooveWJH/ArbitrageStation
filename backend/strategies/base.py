from abc import ABC, abstractmethod
from sqlalchemy.orm import Session


class BaseStrategy(ABC):
    def __init__(self, db: Session):
        self.db = db

    @abstractmethod
    def open(self, symbol: str, long_exchange_id: int, short_exchange_id: int,
              size_usd: float, leverage: float = 1.0) -> dict:
        """Open positions for this strategy. Returns result dict."""

    @abstractmethod
    def close(self, strategy_id: int, reason: str = "manual") -> dict:
        """Close all positions for an existing strategy."""
