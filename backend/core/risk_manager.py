"""
Risk Manager 鈥?runs every N seconds.
Evaluates all enabled RiskRules against open strategies/positions.
"""
import logging

from core.time_utils import utc_now
from sqlalchemy.orm import Session
from models.database import SessionLocal, RiskRule, Strategy, Position, Exchange, TradeLog, AppConfig
from core.exchange_manager import close_position, close_spot_position, get_instance
from services.email_service import send_risk_alert

logger = logging.getLogger(__name__)


def _close_strategy(db: Session, strategy: Strategy, rule: RiskRule,
                    trigger_pnl_pct: float):
    """Full close of all positions in a strategy + email."""
    strategy.status = "closing"
    db.commit()

    long_ex = db.query(Exchange).filter(Exchange.id == strategy.long_exchange_id).first()
    short_ex = db.query(Exchange).filter(Exchange.id == strategy.short_exchange_id).first()

    closed_ok = True
    positions = db.query(Position).filter(
        Position.strategy_id == strategy.id,
        Position.status == "open"
    ).all()

    for pos in positions:
        exchange = db.query(Exchange).filter(Exchange.id == pos.exchange_id).first()
        if not exchange:
            continue
        if pos.position_type == "spot":
            result = close_spot_position(exchange, pos.symbol, pos.size)
        else:
            result = close_position(exchange, pos.symbol, pos.side, pos.size)
        pos.status = "closed" if result else "error"
        pos.closed_at = utc_now()
        db.add(TradeLog(
            strategy_id=strategy.id,
            position_id=pos.id,
            action="emergency_close",
            exchange=exchange.name,
            symbol=pos.symbol,
            side="sell" if pos.side == "long" else "buy",
            price=pos.current_price,
            size=pos.size,
            reason=f"风控触发: {rule.name} | 亏损 {trigger_pnl_pct:.2f}%",
        ))
        if not result:
            closed_ok = False

    strategy.status = "closed" if closed_ok else "error"
    strategy.close_reason = f"风控触发: {rule.name}"
    strategy.closed_at = utc_now()
    db.commit()

    if rule.send_email:
        send_risk_alert(
            db=db,
            rule_name=rule.name,
            strategy_id=strategy.id,
            symbol=strategy.symbol,
            exchange_long=long_ex.display_name if long_ex else str(strategy.long_exchange_id),
            exchange_short=short_ex.display_name if short_ex else str(strategy.short_exchange_id),
            pnl_pct=trigger_pnl_pct,
            action_taken="Closed all positions for this strategy (including hedge legs).",
        )

    logger.warning(
        f"[RiskManager] Strategy #{strategy.id} {strategy.symbol} emergency closed. "
        f"Rule: {rule.name}, PnL: {trigger_pnl_pct:.2f}%"
    )


def _calc_strategy_pnl_pct(db: Session, strategy: Strategy) -> float:
    """Calculate combined PnL% for the strategy based on its positions."""
    positions = db.query(Position).filter(
        Position.strategy_id == strategy.id,
        Position.status == "open"
    ).all()
    if not positions:
        return 0.0
    total_pnl = sum(p.unrealized_pnl or 0 for p in positions)
    total_entry_value = sum(p.entry_price * p.size for p in positions if p.entry_price and p.size)
    if total_entry_value == 0:
        return 0.0
    return (total_pnl / total_entry_value) * 100


def _alert_only(db: Session, strategy: Strategy, rule: RiskRule,
                pnl_pct: float, detail: str):
    """Send email alert without closing the strategy."""
    if rule.send_email:
        long_ex = db.query(Exchange).filter(Exchange.id == strategy.long_exchange_id).first()
        short_ex = db.query(Exchange).filter(Exchange.id == strategy.short_exchange_id).first()
        send_risk_alert(
            db=db,
            rule_name=rule.name,
            strategy_id=strategy.id,
            symbol=strategy.symbol,
            exchange_long=long_ex.display_name if long_ex else "",
            exchange_short=short_ex.display_name if short_ex else "",
            pnl_pct=pnl_pct,
            action_taken=f"仅告警，未平仓 | {detail}",
        )
    logger.warning(
        f"[RiskManager] Alert-only #{strategy.id} {strategy.symbol}: {detail}"
    )


def run_risk_checks():
    from core.data_collector import funding_rate_cache

    db: Session = SessionLocal()
    try:
        rules = db.query(RiskRule).filter(RiskRule.is_enabled == True).all()
        if not rules:
            return

        active_strategies = db.query(Strategy).filter(Strategy.status == "active").all()

        for strategy in active_strategies:
            strategy_pnl_pct = _calc_strategy_pnl_pct(db, strategy)

            for rule in rules:
                triggered = False
                detail = ""

                if rule.rule_type == "loss_pct":
                    if strategy_pnl_pct <= -abs(rule.threshold):
                        triggered = True
                        detail = f"亏损 {strategy_pnl_pct:.2f}% 触及 -{rule.threshold}% 限制"

                elif rule.rule_type == "max_position_usd":
                    positions = db.query(Position).filter(
                        Position.strategy_id == strategy.id,
                        Position.status == "open"
                    ).all()
                    for pos in positions:
                        pos_value = (pos.current_price or pos.entry_price or 0) * pos.size
                        if pos_value >= rule.threshold:
                            triggered = True
                            detail = f"单仓位价值 {pos_value:,.0f} USD 超过 {rule.threshold:,.0f} USD 限制"
                            break

                elif rule.rule_type == "max_exposure_usd":
                    positions = db.query(Position).filter(
                        Position.strategy_id == strategy.id,
                        Position.status == "open"
                    ).all()
                    total_exposure = sum(
                        (p.current_price or p.entry_price or 0) * p.size for p in positions
                    )
                    if total_exposure >= rule.threshold:
                        triggered = True
                        detail = f"总敞口 {total_exposure:,.0f} USD 超过 {rule.threshold:,.0f} USD 限制"

                elif rule.rule_type == "min_rate_diff":
                    long_rate = (funding_rate_cache
                                 .get(strategy.long_exchange_id, {})
                                 .get(strategy.symbol, {})
                                 .get("rate", 0)) or 0
                    short_rate = (funding_rate_cache
                                  .get(strategy.short_exchange_id, {})
                                  .get(strategy.symbol, {})
                                  .get("rate", 0)) or 0
                    rate_diff_pct = (short_rate - long_rate) * 100
                    if rate_diff_pct < rule.threshold:
                        triggered = True
                        detail = f"当前费率差 {rate_diff_pct:.4f}% 低于最低阈值 {rule.threshold:.4f}%"

                elif rule.rule_type == "max_leverage":
                    if strategy.initial_margin_usd and strategy.initial_margin_usd > 0:
                        positions = db.query(Position).filter(
                            Position.strategy_id == strategy.id,
                            Position.status == "open"
                        ).all()
                        total_notional = sum(
                            (p.current_price or p.entry_price or 0) * p.size for p in positions
                        )
                        effective_lev = total_notional / strategy.initial_margin_usd
                        if effective_lev >= rule.threshold:
                            triggered = True
                            detail = f"有效杠杆 {effective_lev:.1f}x 超过 {rule.threshold:.1f}x 限制"

                if triggered:
                    if rule.action == "close_position":
                        _close_strategy(db, strategy, rule, strategy_pnl_pct)
                        break  # strategy closing, skip remaining rules
                    elif rule.action == "alert_only":
                        _alert_only(db, strategy, rule, strategy_pnl_pct, detail)

    except Exception as e:
        logger.error(f"run_risk_checks error: {e}")
        db.rollback()
    finally:
        db.close()


