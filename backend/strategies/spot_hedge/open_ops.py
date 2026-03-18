from __future__ import annotations

import logging

from core.time_utils import utc_now
from models.database import Exchange, Position, Strategy, TradeLog

logger = logging.getLogger(__name__)


class SpotHedgeOpenMixin:
    def open(
        self,
        symbol: str,
        long_exchange_id: int,
        short_exchange_id: int,
        size_usd: float,
        leverage: float = 1.0,
        entry_e24_net_pct: float | None = None,
        entry_open_fee_pct: float | None = None,
        hedge_base_ratio: float = 1.0,
    ) -> dict:
        from strategies import spot_hedge as spot_gateway

        spot_ex = self.db.query(Exchange).filter(Exchange.id == long_exchange_id).first()
        perp_ex = self.db.query(Exchange).filter(Exchange.id == short_exchange_id).first()
        if not spot_ex or not perp_ex:
            return {"success": False, "error": "Exchange not found"}

        spot_symbol = symbol.split(":")[0] if ":" in symbol else symbol
        ticker = spot_gateway.fetch_spot_ticker(spot_ex, spot_symbol)
        if not ticker:
            return {"success": False, "error": f"Cannot fetch spot ticker for {spot_symbol}"}

        perp_ticker = spot_gateway.fetch_ticker(perp_ex, symbol)
        if not perp_ticker:
            return {"success": False, "error": f"Cannot fetch perp ticker for {symbol}"}

        spot_price = ticker.get("last") or ticker.get("close")
        perp_price = perp_ticker.get("last") or perp_ticker.get("close")
        if not spot_price or not perp_price:
            return {"success": False, "error": "Invalid spot/perp ticker price"}

        spot_size = size_usd / spot_price
        perp_size = spot_size * max(0.0, float(hedge_base_ratio or 1.0))
        leverage_int = max(1, int(float(leverage or 1)))

        strategy = Strategy(
            name=f"现货-合约对冲 {spot_symbol} {(spot_ex.display_name or spot_ex.name)}->{(perp_ex.display_name or perp_ex.name)}",
            strategy_type="spot_hedge",
            symbol=symbol,
            long_exchange_id=long_exchange_id,
            short_exchange_id=short_exchange_id,
            initial_margin_usd=size_usd,
            entry_e24_net_pct=float(entry_e24_net_pct or 0.0),
            entry_open_fee_pct=max(0.0, float(entry_open_fee_pct or 0.0)),
            entry_spot_base_qty=max(0.0, float(spot_size)),
            entry_perp_base_qty=max(0.0, float(perp_size)),
            entry_delta_base_qty=round(max(0.0, float(spot_size)) - max(0.0, float(perp_size)), 12),
            hedge_qty_mode="base_equal",
            status="active",
        )
        self.db.add(strategy)
        self.db.flush()

        errors: list[str] = []
        perp_order = spot_gateway.place_hedge_order(
            perp_ex,
            symbol,
            "sell",
            perp_size,
            user_leverage=leverage_int,
        )
        perp_fill = (perp_order.get("average") or perp_price) if perp_order else perp_price
        perp_pos = Position(
            strategy_id=strategy.id,
            exchange_id=short_exchange_id,
            symbol=symbol,
            side="short",
            position_type="swap",
            size=perp_size,
            entry_price=perp_fill,
            current_price=perp_fill,
            status="open" if perp_order else "error",
        )
        self.db.add(perp_pos)
        if not perp_order:
            errors.append("perp short failed")
        else:
            self.db.add(
                TradeLog(
                    strategy_id=strategy.id,
                    action="open",
                    exchange=perp_ex.name,
                    symbol=symbol,
                    side="sell",
                    price=perp_fill,
                    size=perp_size,
                    reason="spot_hedge open perp short",
                )
            )

        spot_order = spot_gateway.place_spot_order(spot_ex, spot_symbol, "buy", spot_size) if perp_order else None
        spot_fill = (spot_order.get("average") or spot_price) if spot_order else spot_price
        spot_pos = Position(
            strategy_id=strategy.id,
            exchange_id=long_exchange_id,
            symbol=spot_symbol,
            side="long",
            position_type="spot",
            size=spot_size,
            entry_price=spot_fill,
            current_price=spot_fill,
            status="open" if spot_order else "error",
        )
        self.db.add(spot_pos)
        if perp_order and not spot_order:
            errors.append("spot buy failed")
        elif spot_order:
            self.db.add(
                TradeLog(
                    strategy_id=strategy.id,
                    action="open",
                    exchange=spot_ex.name,
                    symbol=spot_symbol,
                    side="buy",
                    price=spot_fill,
                    size=spot_size,
                    reason="spot_hedge open spot",
                )
            )

        if errors:
            self._handle_open_error(
                strategy=strategy,
                errors=errors,
                spot_ex=spot_ex,
                perp_ex=perp_ex,
                spot_order=spot_order,
                perp_order=perp_order,
                spot_pos=spot_pos,
                perp_pos=perp_pos,
                spot_symbol=spot_symbol,
                symbol=symbol,
                spot_size=spot_size,
                perp_size=perp_size,
                spot_fill=spot_fill,
                perp_fill=perp_fill,
            )
        else:
            strategy.status = "active"
            strategy.close_reason = ""
            strategy.closed_at = None
            self.db.commit()

        return {
            "success": not errors,
            "strategy_id": strategy.id,
            "errors": errors,
            "spot_exchange": spot_ex.name,
            "perp_exchange": perp_ex.name,
            "symbol": symbol,
            "spot_size": spot_size,
            "perp_size": perp_size,
            "entry_price": perp_price,
        }
