"""
Cross-Exchange Funding Rate Arbitrage:
  - Long perpetual on exchange A (lower rate)
  - Short perpetual on exchange B (higher rate)
  - Collect rate differential every 8h
"""
import logging

from core.time_utils import utc_now
from sqlalchemy.orm import Session
from models.database import Exchange, Strategy, Position, TradeLog
from core.exchange_manager import fetch_ticker, place_order, place_hedge_order, close_position, close_hedge_position
from services.email_service import send_email
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class CrossExchangeStrategy(BaseStrategy):

    def open(self, symbol: str, long_exchange_id: int, short_exchange_id: int,
             size_usd: float, leverage: float = 1.0) -> dict:
        long_ex = self.db.query(Exchange).filter(Exchange.id == long_exchange_id).first()
        short_ex = self.db.query(Exchange).filter(Exchange.id == short_exchange_id).first()
        if not long_ex or not short_ex:
            return {"success": False, "error": "Exchange not found"}

        # Get current price from long exchange
        ticker = fetch_ticker(long_ex, symbol)
        if not ticker:
            return {"success": False, "error": f"Cannot fetch ticker for {symbol}"}

        price = ticker.get("last") or ticker.get("close")
        if not price:
            return {"success": False, "error": "Invalid ticker price"}

        contract_size = (size_usd * leverage) / price

        # Create strategy record
        strategy = Strategy(
            name=f"跨所套利 {symbol} {long_ex.display_name}<->{short_ex.display_name}",
            strategy_type="cross_exchange",
            symbol=symbol,
            long_exchange_id=long_exchange_id,
            short_exchange_id=short_exchange_id,
            initial_margin_usd=size_usd,
            status="active",
        )
        self.db.add(strategy)
        self.db.flush()

        errors = []

        # Place long order (hedge mode: positionSide=LONG required for dual-side accounts)
        long_order = place_hedge_order(long_ex, symbol, "buy", contract_size, user_leverage=int(leverage))
        long_fill_price = (long_order.get("average") or price) if long_order else price
        long_pos = Position(
            strategy_id=strategy.id,
            exchange_id=long_exchange_id,
            symbol=symbol,
            side="long",
            position_type="swap",
            size=contract_size,
            entry_price=long_fill_price,
            current_price=long_fill_price,
            status="open" if long_order else "error",
        )
        self.db.add(long_pos)
        if not long_order:
            errors.append("long order failed")
        else:
            self.db.add(TradeLog(
                strategy_id=strategy.id,
                action="open",
                exchange=long_ex.name,
                symbol=symbol,
                side="buy",
                price=long_fill_price,
                size=contract_size,
                reason="cross_exchange open long",
            ))

        # Place short order (hedge mode: positionSide=SHORT required for dual-side accounts)
        short_order = place_hedge_order(short_ex, symbol, "sell", contract_size, user_leverage=int(leverage))
        short_fill_price = (short_order.get("average") or price) if short_order else price
        short_pos = Position(
            strategy_id=strategy.id,
            exchange_id=short_exchange_id,
            symbol=symbol,
            side="short",
            position_type="swap",
            size=contract_size,
            entry_price=short_fill_price,
            current_price=short_fill_price,
            status="open" if short_order else "error",
        )
        self.db.add(short_pos)
        if not short_order:
            errors.append("short order failed")
        else:
            self.db.add(TradeLog(
                strategy_id=strategy.id,
                action="open",
                exchange=short_ex.name,
                symbol=symbol,
                side="sell",
                price=short_fill_price,
                size=contract_size,
                reason="cross_exchange open short",
            ))

        if errors:
            strategy.status = "error"
            # Mark the failed leg's position as error so it doesn't pollute PnL stats
            if not long_order:
                long_pos.status = "error"
            if not short_order:
                short_pos.status = "error"
            self.db.commit()
            # Emergency unwind: close whichever leg succeeded to avoid naked exposure
            if long_order and not short_order:
                logger.warning(f"[CrossExchange] Short leg failed, emergency closing long on {long_ex.name}")
                unwind = close_hedge_position(long_ex, symbol, "long", contract_size)
                if unwind:
                    unwind_price = unwind.get("average") or unwind.get("price") or long_fill_price
                    long_pos.status = "closed"
                    long_pos.closed_at = utc_now()
                    self.db.add(TradeLog(
                        strategy_id=strategy.id,
                        action="emergency_close",
                        exchange=long_ex.name,
                        symbol=symbol,
                        side="sell",
                        price=unwind_price,
                        size=contract_size,
                        reason="emergency unwind: short leg failed",
                    ))
                else:
                    logger.error(
                        f"[CrossExchange] EMERGENCY UNWIND FAILED: long on {long_ex.name} {symbol} "
                        f"still open 鈥?MANUAL INTERVENTION REQUIRED"
                    )
            elif short_order and not long_order:
                logger.warning(f"[CrossExchange] Long leg failed, emergency closing short on {short_ex.name}")
                unwind = close_hedge_position(short_ex, symbol, "short", contract_size)
                if unwind:
                    unwind_price = unwind.get("average") or unwind.get("price") or short_fill_price
                    short_pos.status = "closed"
                    short_pos.closed_at = utc_now()
                    self.db.add(TradeLog(
                        strategy_id=strategy.id,
                        action="emergency_close",
                        exchange=short_ex.name,
                        symbol=symbol,
                        side="buy",
                        price=unwind_price,
                        size=contract_size,
                        reason="emergency unwind: long leg failed",
                    ))
                else:
                    logger.error(
                        f"[CrossExchange] EMERGENCY UNWIND FAILED: short on {short_ex.name} {symbol} "
                        f"still open 鈥?MANUAL INTERVENTION REQUIRED"
                    )
            strategy.close_reason = f"open failed: {errors}"
            strategy.closed_at = utc_now()
            self.db.commit()

        return {
            "success": not errors,
            "strategy_id": strategy.id,
            "errors": errors,
            "long_exchange": long_ex.name,
            "short_exchange": short_ex.name,
            "symbol": symbol,
            "size_contracts": contract_size,
            "entry_price": price,
        }

    def close(self, strategy_id: int, reason: str = "manual") -> dict:
        strategy = self.db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            return {"success": False, "error": "Strategy not found"}

        strategy.status = "closing"
        self.db.commit()

        positions = self.db.query(Position).filter(
            Position.strategy_id == strategy_id,
            Position.status == "open"
        ).all()

        errors = []
        for pos in positions:
            exchange = self.db.query(Exchange).filter(Exchange.id == pos.exchange_id).first()
            result = close_hedge_position(exchange, pos.symbol, pos.side, pos.size)
            fill_price = (result.get("average") or result.get("price") or pos.current_price) if result else pos.current_price
            if result:
                pos.status = "closed"
                pos.closed_at = utc_now()
                self.db.add(TradeLog(
                    strategy_id=strategy_id,
                    position_id=pos.id,
                    action="close",
                    exchange=exchange.name,
                    symbol=pos.symbol,
                    side="sell" if pos.side == "long" else "buy",
                    price=fill_price,
                    size=pos.size,
                    reason=reason,
                ))
            else:
                # Keep status="open" so risk manager continues monitoring
                errors.append(f"{exchange.name} close failed")
                logger.error(
                    f"[CrossExchange] Close failed for strategy#{strategy_id} "
                    f"{pos.symbol} {pos.side} on {exchange.name} (pos#{pos.id}) 鈥?position left OPEN"
                )
                try:
                    send_email(
                        db=self.db,
                        subject=f"[Alert] Close failed - {pos.symbol} {pos.side} on {exchange.name}",
                        body=(
                            f"Strategy #{strategy_id} failed to close on {exchange.name}.\n"
                            f"Symbol: {pos.symbol}\n"
                            f"Side: {pos.side}\n"
                            f"Size: {pos.size}\n"
                            f"Reason: {reason}\n\n"
                            "Position remains OPEN. Please inspect and close manually."
                        ),
                    )
                except Exception as mail_err:
                    logger.warning(f"[CrossExchange] Failed to send alert email: {mail_err}")
        strategy.status = "closed" if not errors else "error"
        strategy.close_reason = reason
        strategy.closed_at = utc_now()
        self.db.commit()
        return {"success": not errors, "errors": errors}


