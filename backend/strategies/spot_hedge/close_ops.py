from __future__ import annotations

import logging

from core.time_utils import utc_now
from models.database import Exchange, Position, Strategy, TradeLog
from services.email_service import send_email

logger = logging.getLogger(__name__)


class SpotHedgeCloseMixin:
    def close(self, strategy_id: int, reason: str = "manual") -> dict:
        from strategies import spot_hedge as spot_gateway

        strategy = self.db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            return {"success": False, "error": "Strategy not found"}

        strategy.status = "closing"
        self.db.commit()
        positions = (
            self.db.query(Position)
            .filter(
                Position.strategy_id == strategy_id,
                Position.status == "open",
            )
            .all()
        )

        errors = []
        for pos in positions:
            exchange = self.db.query(Exchange).filter(Exchange.id == pos.exchange_id).first()
            if not exchange:
                errors.append(f"exchange#{pos.exchange_id} missing")
                continue

            if pos.position_type == "spot":
                result = spot_gateway.close_spot_position(exchange, pos.symbol, pos.size)
            else:
                result = spot_gateway.close_hedge_position(exchange, pos.symbol, pos.side, pos.size)
            fill_price = (result.get("average") or result.get("price") or pos.current_price) if result else pos.current_price

            if result:
                pos.status = "closed"
                pos.closed_at = utc_now()
                self.db.add(
                    TradeLog(
                        strategy_id=strategy_id,
                        position_id=pos.id,
                        action="close",
                        exchange=exchange.name,
                        symbol=pos.symbol,
                        side="sell" if pos.side == "long" else "buy",
                        price=fill_price,
                        size=pos.size,
                        reason=reason,
                    )
                )
                continue

            errors.append(f"{exchange.name} close failed")
            logger.error(
                "[SpotHedge] Close failed for strategy#%s %s %s on %s (pos#%s); position left OPEN",
                strategy_id,
                pos.symbol,
                pos.side,
                exchange.name,
                pos.id,
            )
            self._try_send_close_alert(strategy_id=strategy_id, pos=pos, exchange_name=exchange.name, reason=reason)

        remaining_open = self._remaining_open_positions(strategy_id)
        if remaining_open > 0:
            strategy.status = "active"
            strategy.close_reason = f"{reason}; close_failed={errors}" if errors else reason
            strategy.closed_at = None
        else:
            strategy.status = "closed"
            strategy.close_reason = f"{reason}; close_errors={errors}" if errors else reason
            strategy.closed_at = utc_now()
        self.db.commit()

        return {
            "success": (remaining_open == 0 and not errors),
            "errors": errors,
            "remaining_open_positions": int(remaining_open),
            "strategy_status": strategy.status,
        }

    def _try_send_close_alert(self, strategy_id: int, pos: Position, exchange_name: str, reason: str) -> None:
        try:
            send_email(
                db=self.db,
                subject=f"[Alert] Close failed - {pos.symbol} {pos.side} on {exchange_name}",
                body=(
                    f"Strategy #{strategy_id} failed to close on {exchange_name}.\n"
                    f"Symbol: {pos.symbol}\n"
                    f"Side: {pos.side}\n"
                    f"Size: {pos.size}\n"
                    f"Reason: {reason}\n\n"
                    "Position remains OPEN. Please inspect and close manually."
                ),
            )
        except Exception as mail_err:
            logger.warning("[SpotHedge] Failed to send alert email: %s", mail_err)
