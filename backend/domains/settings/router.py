"""Settings domain routes."""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from db.models import AppConfig, AutoTradeConfig, EmailConfig, RiskRule

router = APIRouter(prefix="/api/settings", tags=["settings"])


class RiskRuleCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    rule_type: str
    threshold: float
    action: str
    send_email: bool = True
    is_enabled: bool = True


class RiskRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    threshold: Optional[float] = None
    action: Optional[str] = None
    send_email: Optional[bool] = None
    is_enabled: Optional[bool] = None


class EmailConfigUpdate(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: Optional[str] = None
    to_emails: Optional[str] = None
    is_enabled: Optional[bool] = None


class AppConfigUpdate(BaseModel):
    auto_trade_enabled: Optional[bool] = None
    data_refresh_interval: Optional[int] = None
    risk_check_interval: Optional[int] = None


class AutoTradeConfigUpdate(BaseModel):
    enable_cross_exchange: Optional[bool] = None
    enable_spot_hedge: Optional[bool] = None
    cross_exchange_allow_ids: Optional[List[int]] = None
    spot_hedge_allow_ids: Optional[List[int]] = None
    entry_minutes_before_funding: Optional[int] = None
    min_rate_diff_pct: Optional[float] = None
    min_spot_rate_pct: Optional[float] = None
    min_annualized_pct: Optional[float] = None
    max_entry_spread_pct: Optional[float] = None
    min_entry_basis_pct: Optional[float] = None
    exit_spread_threshold_pct: Optional[float] = None
    max_hold_minutes: Optional[float] = None
    min_cross_volume_usd: Optional[float] = None
    min_spot_volume_usd: Optional[float] = None
    position_size_mode: Optional[str] = None
    fixed_size_usd: Optional[float] = None
    max_position_usd: Optional[float] = None
    max_open_strategies: Optional[int] = None
    funding_max_positions: Optional[int] = None
    leverage: Optional[float] = None
    volume_cap_pct: Optional[float] = None
    fee_rate_pct: Optional[float] = None
    pre_settle_exit_threshold_pct: Optional[float] = None
    spread_gain_exit_threshold_pct: Optional[float] = None
    switch_min_improvement_pct: Optional[float] = None
    max_hold_cycles: Optional[int] = None
    max_margin_utilization_pct: Optional[float] = None
    spread_arb_enabled: Optional[bool] = None
    spread_use_hedge_mode: Optional[bool] = None
    spread_entry_z: Optional[float] = None
    spread_exit_z: Optional[float] = None
    spread_stop_z: Optional[float] = None
    spread_stop_z_delta: Optional[float] = None
    spread_tp_z_delta: Optional[float] = None
    spread_position_pct: Optional[float] = None
    spread_max_positions: Optional[int] = None
    spread_order_type: Optional[str] = None
    spread_pre_settle_mins: Optional[int] = None
    spread_min_volume_usd: Optional[float] = None
    spread_cooldown_mins: Optional[int] = None


@router.get("/risk-rules")
def list_risk_rules(db: Session = Depends(get_db)):
    rules = db.query(RiskRule).order_by(RiskRule.id).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "rule_type": r.rule_type,
            "threshold": r.threshold,
            "action": r.action,
            "send_email": r.send_email,
            "is_enabled": r.is_enabled,
            "created_at": r.created_at,
        }
        for r in rules
    ]


@router.post("/risk-rules")
def create_risk_rule(body: RiskRuleCreate, db: Session = Depends(get_db)):
    rule = RiskRule(**body.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"success": True, "id": rule.id}


@router.put("/risk-rules/{rule_id}")
def update_risk_rule(rule_id: int, body: RiskRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(RiskRule).filter(RiskRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    db.commit()
    return {"success": True}


@router.delete("/risk-rules/{rule_id}")
def delete_risk_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(RiskRule).filter(RiskRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"success": True}


@router.get("/email")
def get_email_config(db: Session = Depends(get_db)):
    cfg = db.query(EmailConfig).first()
    if not cfg:
        return {}
    return {
        "smtp_host": cfg.smtp_host,
        "smtp_port": cfg.smtp_port,
        "smtp_user": cfg.smtp_user,
        "from_email": cfg.from_email,
        "to_emails": cfg.to_emails,
        "is_enabled": cfg.is_enabled,
    }


@router.put("/email")
def update_email_config(body: EmailConfigUpdate, db: Session = Depends(get_db)):
    cfg = db.query(EmailConfig).first()
    if not cfg:
        cfg = EmailConfig()
        db.add(cfg)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(cfg, field, value)
    db.commit()
    return {"success": True}


@router.post("/email/test")
def test_email(db: Session = Depends(get_db)):
    from services.email_service import send_email

    ok = send_email(db, "套利工具 - 邮件测试", "<h2>邮件配置测试成功！</h2><p>您的邮件通知已正常工作。</p>")
    return {"success": ok, "message": "邮件发送成功" if ok else "发送失败，请检查SMTP配置"}


@router.get("/app")
def get_app_config(db: Session = Depends(get_db)):
    cfg = db.query(AppConfig).first()
    if not cfg:
        return {}
    return {
        "auto_trade_enabled": cfg.auto_trade_enabled,
        "data_refresh_interval": cfg.data_refresh_interval,
        "risk_check_interval": cfg.risk_check_interval,
    }


@router.put("/app")
def update_app_config(body: AppConfigUpdate, db: Session = Depends(get_db)):
    from main import reschedule_jobs

    cfg = db.query(AppConfig).first()
    if not cfg:
        cfg = AppConfig()
        db.add(cfg)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(cfg, field, value)
    db.commit()
    reschedule_jobs(data_interval=body.data_refresh_interval, risk_interval=body.risk_check_interval)
    return {"success": True}


@router.get("/auto-trade-config")
def get_auto_trade_config(db: Session = Depends(get_db)):
    cfg = db.query(AutoTradeConfig).first()
    if not cfg:
        cfg = AutoTradeConfig()
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return {
        "enable_cross_exchange": cfg.enable_cross_exchange,
        "enable_spot_hedge": cfg.enable_spot_hedge,
        "cross_exchange_allow_ids": json.loads(cfg.cross_exchange_allow_ids or "[]"),
        "spot_hedge_allow_ids": json.loads(cfg.spot_hedge_allow_ids or "[]"),
        "entry_minutes_before_funding": cfg.entry_minutes_before_funding,
        "min_rate_diff_pct": cfg.min_rate_diff_pct,
        "min_spot_rate_pct": cfg.min_spot_rate_pct,
        "min_annualized_pct": cfg.min_annualized_pct,
        "max_entry_spread_pct": cfg.max_entry_spread_pct,
        "min_entry_basis_pct": cfg.min_entry_basis_pct,
        "exit_spread_threshold_pct": cfg.exit_spread_threshold_pct,
        "max_hold_minutes": cfg.max_hold_minutes,
        "min_cross_volume_usd": cfg.min_cross_volume_usd,
        "min_spot_volume_usd": cfg.min_spot_volume_usd,
        "position_size_mode": cfg.position_size_mode,
        "fixed_size_usd": cfg.fixed_size_usd,
        "max_position_usd": cfg.max_position_usd,
        "max_open_strategies": cfg.max_open_strategies,
        "funding_max_positions": cfg.funding_max_positions,
        "leverage": cfg.leverage,
        "volume_cap_pct": cfg.volume_cap_pct,
        "fee_rate_pct": cfg.fee_rate_pct,
        "pre_settle_exit_threshold_pct": cfg.pre_settle_exit_threshold_pct,
        "spread_gain_exit_threshold_pct": cfg.spread_gain_exit_threshold_pct,
        "switch_min_improvement_pct": cfg.switch_min_improvement_pct,
        "max_hold_cycles": cfg.max_hold_cycles,
        "max_margin_utilization_pct": cfg.max_margin_utilization_pct,
        "spread_arb_enabled": cfg.spread_arb_enabled,
        "spread_use_hedge_mode": cfg.spread_use_hedge_mode,
        "spread_entry_z": cfg.spread_entry_z,
        "spread_exit_z": cfg.spread_exit_z,
        "spread_stop_z": cfg.spread_stop_z,
        "spread_stop_z_delta": cfg.spread_stop_z_delta,
        "spread_tp_z_delta": cfg.spread_tp_z_delta,
        "spread_position_pct": cfg.spread_position_pct,
        "spread_max_positions": cfg.spread_max_positions,
        "spread_order_type": cfg.spread_order_type,
        "spread_pre_settle_mins": cfg.spread_pre_settle_mins,
        "spread_min_volume_usd": cfg.spread_min_volume_usd,
        "spread_cooldown_mins": cfg.spread_cooldown_mins,
    }


@router.put("/auto-trade-config")
def update_auto_trade_config(body: AutoTradeConfigUpdate, db: Session = Depends(get_db)):
    cfg = db.query(AutoTradeConfig).first()
    if not cfg:
        cfg = AutoTradeConfig()
        db.add(cfg)
    data = body.model_dump(exclude_none=True)
    for key, val in data.items():
        if key in ("cross_exchange_allow_ids", "spot_hedge_allow_ids"):
            setattr(cfg, key, json.dumps(val))
        else:
            setattr(cfg, key, val)
    db.commit()
    return {"success": True}


__all__ = ["router"]
