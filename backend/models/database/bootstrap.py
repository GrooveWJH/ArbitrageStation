from .analytics_models import AppConfig, AutoTradeConfig, BacktestDataJob, Base, Boolean, Column, DATABASE_URL, EmailConfig, EquitySnapshot, Exchange, Float, ForeignKey, FundingAssignment, FundingCursor, FundingLedger, FundingRate, Index, Integer, MarketSnapshot15m, Numeric, PairUniverseDaily, Path, PnlV2DailyReconcile, Position, RiskRule, SADateTime, SessionLocal, SpotBasisAutoConfig, SpreadPosition, Strategy, String, Text, TradeLog, TypeDecorator, UTC, UTCDateTime, UniqueConstraint, _DEFAULT_DATABASE_URL, _DEFAULT_DB_PATH, _engine_kwargs, _maybe_fix_gbk_utf8_mojibake, _migrate_columns, create_engine, declarative_base, engine, get_db, inspect, os, relationship, sessionmaker, text, utc_now



def _repair_mojibake_seed_data(db):
    changed = False

    for rule in db.query(RiskRule).all():
        old_name = str(rule.name or "")
        old_desc = str(rule.description or "")
        new_name = _maybe_fix_gbk_utf8_mojibake(old_name)
        new_desc = _maybe_fix_gbk_utf8_mojibake(old_desc)
        if old_name != new_name:
            rule.name = new_name
            changed = True
        if old_desc != new_desc:
            rule.description = new_desc
            changed = True

    ex_rows = db.query(Exchange.id, Exchange.display_name, Exchange.name).all()
    ex_name_map = {
        int(ex_id): str((display_name or name or f"EX#{ex_id}"))
        for ex_id, display_name, name in ex_rows
        if int(ex_id or 0) > 0
    }
    for st in db.query(Strategy).filter(Strategy.strategy_type == "spot_hedge").all():
        raw_name = str(st.name or "")
        spot_symbol = str(st.symbol or "").split(":", 1)[0] if st.symbol else ""
        long_name = ex_name_map.get(int(st.long_exchange_id or 0), str(st.long_exchange_id or ""))
        short_name = ex_name_map.get(int(st.short_exchange_id or 0), str(st.short_exchange_id or ""))
        rebuilt_name = f"现货-合约对冲 {spot_symbol} {long_name}->{short_name}".strip()
        should_rebuild = (
            "鐜拌揣" in raw_name
            or "鍚堢害" in raw_name
            or "瀵瑰啿" in raw_name
            or raw_name.startswith("??-????")
        )
        if should_rebuild and raw_name != rebuilt_name:
            st.name = rebuilt_name
            changed = True

    if changed:
        db.flush()


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_columns()
    db = SessionLocal()
    try:
        # Seed default risk rule (80% loss)
        if db.query(RiskRule).count() == 0:
            db.add(RiskRule(
                name="强制止损 80%",
                description="当任意合约仓位亏损达到80%时，立即全平该仓位及其对冲仓位并发送邮件通知",
                rule_type="loss_pct",
                threshold=80.0,
                action="close_position",
                send_email=True,
                is_enabled=True,
            ))
        if db.query(AppConfig).count() == 0:
            db.add(AppConfig())
        if db.query(EmailConfig).count() == 0:
            db.add(EmailConfig())
        if db.query(AutoTradeConfig).count() == 0:
            db.add(AutoTradeConfig())
        if db.query(SpotBasisAutoConfig).count() == 0:
            db.add(SpotBasisAutoConfig())
        _repair_mojibake_seed_data(db)
        db.commit()
    finally:
        db.close()
