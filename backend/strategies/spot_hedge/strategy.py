from __future__ import annotations

import logging

from core.time_utils import utc_now
from models.database import Position, Strategy, TradeLog
from strategies.base import BaseStrategy

from .base import SpotHedgeBase
from .close_ops import SpotHedgeCloseMixin
from .open_ops import SpotHedgeOpenMixin

logger = logging.getLogger(__name__)


class SpotHedgeStrategy(SpotHedgeBase, SpotHedgeOpenMixin, SpotHedgeCloseMixin, BaseStrategy):
    def _handle_open_error(
        self,
        strategy: Strategy,
        errors: list[str],
        spot_ex,
        perp_ex,
        spot_order,
        perp_order,
        spot_pos: Position,
        perp_pos: Position,
        spot_symbol: str,
        symbol: str,
        spot_size: float,
        perp_size: float,
        spot_fill: float,
        perp_fill: float,
    ) -> None:
        from strategies import spot_hedge as spot_gateway

        strategy.status = "error"
        unwind_failures: list[str] = []
        self.db.flush()
        if not spot_order:
            spot_pos.status = "error"
        if not perp_order:
            perp_pos.status = "error"
        self.db.commit()

        if spot_order and not perp_order:
            logger.warning("[SpotHedge] Perp leg failed, emergency selling spot on %s", spot_ex.name)
            unwind = spot_gateway.close_spot_position(spot_ex, spot_symbol, spot_size)
            unwind_price = (unwind.get("average") or unwind.get("price") or spot_fill) if unwind else spot_fill
            if unwind:
                spot_pos.status = "closed"
                spot_pos.closed_at = utc_now()
                self.db.add(
                    TradeLog(
                        strategy_id=strategy.id,
                        action="emergency_close",
                        exchange=spot_ex.name,
                        symbol=spot_symbol,
                        side="sell",
                        price=unwind_price,
                        size=spot_size,
                        reason="emergency unwind: perp leg failed",
                    )
                )
            else:
                unwind_failures.append("spot emergency unwind failed")
                spot_pos.status = "open"
                spot_pos.closed_at = None
        elif perp_order and not spot_order:
            logger.warning("[SpotHedge] Spot leg failed, emergency closing perp on %s", perp_ex.name)
            unwind = spot_gateway.close_hedge_position(perp_ex, symbol, "short", perp_size)
            unwind_price = (unwind.get("average") or unwind.get("price") or perp_fill) if unwind else perp_fill
            if unwind:
                perp_pos.status = "closed"
                perp_pos.closed_at = utc_now()
                self.db.add(
                    TradeLog(
                        strategy_id=strategy.id,
                        action="emergency_close",
                        exchange=perp_ex.name,
                        symbol=symbol,
                        side="buy",
                        price=unwind_price,
                        size=perp_size,
                        reason="emergency unwind: spot leg failed",
                    )
                )
            else:
                unwind_failures.append("perp emergency unwind failed")
                perp_pos.status = "open"
                perp_pos.closed_at = None

        remaining_open = self._remaining_open_positions(strategy.id)
        strategy.close_reason = f"open failed: {errors}"
        if unwind_failures:
            strategy.close_reason += f"; unwind failed: {unwind_failures}"
        if remaining_open > 0:
            strategy.status = "active"
            strategy.closed_at = None
        else:
            strategy.status = "closed"
            strategy.closed_at = utc_now()
        self.db.commit()
