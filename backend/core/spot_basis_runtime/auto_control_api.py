from typing import Optional

from .auto_decision_api import get_spot_basis_auto_decision_preview
from .base import (
    Depends,
    DrawdownWatermarkResetRequest,
    HTTPException,
    Query,
    Session,
    SpotBasisAutoConfigUpdate,
    SpotBasisAutoStatusUpdate,
    _to_float,
    get_db,
    router,
    utc_now,
)

def get_spot_basis_auto_config(db: Session = Depends(get_db)):
    from .scoring_config import _get_or_create_auto_cfg
    from .fee_symbols import _dump_auto_cfg

    cfg = _get_or_create_auto_cfg(db)
    return _dump_auto_cfg(cfg)
def update_spot_basis_auto_config(body: SpotBasisAutoConfigUpdate, db: Session = Depends(get_db)):
    from .history_logic import _clamp
    from .scoring_config import _get_or_create_auto_cfg
    from .fee_symbols import _dump_auto_cfg

    cfg = _get_or_create_auto_cfg(db)
    data = body.model_dump(exclude_none=True)

    int_fields = {
        "refresh_interval_secs",
        "switch_confirm_rounds",
        "max_open_pairs",
        "execution_retry_max_rounds",
        "execution_retry_backoff_secs",
        "repair_timeout_secs",
        "repair_retry_rounds",
        "data_stale_threshold_seconds",
        "api_fail_circuit_count",
    }
    bool_fields = {"is_enabled", "dry_run", "circuit_breaker_on_repair_fail"}

    for key, val in data.items():
        if key in int_fields:
            int_val = int(val)
            if key == "execution_retry_max_rounds":
                int_val = max(0, int_val)
            elif key == "execution_retry_backoff_secs":
                int_val = max(1, int_val)
            elif key == "repair_timeout_secs":
                int_val = max(1, int_val)
            elif key == "repair_retry_rounds":
                int_val = max(1, int_val)
            setattr(cfg, key, int_val)
        elif key in bool_fields:
            setattr(cfg, key, bool(val))
        else:
            f = float(val)
            if key in {"max_total_utilization_pct", "target_utilization_pct"}:
                f = _clamp(f, 1.0, 100.0)
            elif key == "max_symbol_utilization_pct":
                f = _clamp(f, 0.0, 100.0)
            elif key in {"min_pair_notional_usd", "max_pair_notional_usd"}:
                f = max(1.0, f)
            elif key in {"reserve_floor_pct", "fee_buffer_pct", "slippage_buffer_pct", "margin_buffer_pct"}:
                f = _clamp(f, 0.0, 30.0)
            elif key in {"entry_conf_min", "hold_conf_min", "delta_epsilon_nav_pct"}:
                f = _clamp(f, 0.0, 100.0 if key == "delta_epsilon_nav_pct" else 1.0)
            elif key == "delta_epsilon_abs_usd":
                f = max(0.0, f)
            setattr(cfg, key, f)

    cfg.min_pair_notional_usd = max(1.0, _to_float(getattr(cfg, "min_pair_notional_usd", 300.0), 300.0))
    cfg.max_pair_notional_usd = max(
        cfg.min_pair_notional_usd,
        _to_float(getattr(cfg, "max_pair_notional_usd", 3000.0), 3000.0),
    )

    # Force no-unhedged policy regardless of payload.
    cfg.max_unhedged_notional_pct_nav = 0.0
    cfg.max_unhedged_seconds = 0

    db.commit()
    db.refresh(cfg)
    return {"success": True, "config": _dump_auto_cfg(cfg)}


@router.get("/drawdown-watermark")
def get_spot_basis_drawdown_watermark(db: Session = Depends(get_db)):
    from .scoring_config import _get_or_create_auto_cfg
    from .fee_symbols import _dump_drawdown_watermark

    cfg = _get_or_create_auto_cfg(db)
    return {"success": True, **_dump_drawdown_watermark(cfg, db)}


@router.post("/drawdown-watermark/reset")
def reset_spot_basis_drawdown_watermark(
    body: Optional[DrawdownWatermarkResetRequest] = None,
    db: Session = Depends(get_db),
):
    from .scoring_config import _get_or_create_auto_cfg
    from .fee_symbols import _dump_drawdown_watermark, _latest_equity_nav_usdt

    cfg = _get_or_create_auto_cfg(db)
    current_nav, _ = _latest_equity_nav_usdt(db)
    req = body or DrawdownWatermarkResetRequest()
    target_peak_nav = max(0.0, _to_float(getattr(req, "peak_nav_usdt", 0.0), 0.0))
    if target_peak_nav <= 0:
        target_peak_nav = current_nav
    if target_peak_nav <= 0:
        raise HTTPException(400, "current NAV unavailable, pass peak_nav_usdt explicitly")
    cfg.drawdown_peak_nav_usdt = round(target_peak_nav, 6)
    cfg.drawdown_peak_reset_at = utc_now()
    db.commit()
    db.refresh(cfg)
    return {
        "success": True,
        "message": "drawdown watermark reset",
        **_dump_drawdown_watermark(cfg, db),
    }


@router.get("/auto-status")
def get_spot_basis_auto_status(db: Session = Depends(get_db)):
    from .scoring_config import _get_or_create_auto_cfg

    cfg = _get_or_create_auto_cfg(db)
    return {
        "enabled": bool(cfg.is_enabled),
        "dry_run": bool(cfg.dry_run),
        "refresh_interval_secs": int(cfg.refresh_interval_secs or 10),
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.put("/auto-status")
def update_spot_basis_auto_status(body: SpotBasisAutoStatusUpdate, db: Session = Depends(get_db)):
    from .scoring_config import _get_or_create_auto_cfg

    cfg = _get_or_create_auto_cfg(db)
    cfg.is_enabled = bool(body.enabled)
    if body.dry_run is not None:
        cfg.dry_run = bool(body.dry_run)
    db.commit()
    db.refresh(cfg)
    return {
        "success": True,
        "enabled": bool(cfg.is_enabled),
        "dry_run": bool(cfg.dry_run),
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.get("/auto-cycle-last")
def get_spot_basis_auto_cycle_last():
    from core.spot_basis_auto_engine import get_last_spot_basis_auto_cycle_summary
    return get_last_spot_basis_auto_cycle_summary()


@router.get("/auto-cycle-logs")
def get_spot_basis_auto_cycle_logs(limit: int = Query(120, ge=1, le=500)):
    from core.spot_basis_auto_engine import get_spot_basis_auto_cycle_logs
    items = get_spot_basis_auto_cycle_logs(limit=limit)
    return {"items": items, "total": len(items)}


@router.post("/auto-cycle-run-once")
def run_spot_basis_auto_cycle_once():
    from core.spot_basis_auto_engine import run_spot_basis_auto_open_cycle
    return run_spot_basis_auto_open_cycle(force=True)


@router.get("/reconcile-last")
def get_spot_basis_reconcile_last():
    from core.spot_basis_reconciler import get_last_spot_basis_reconcile_summary
    return get_last_spot_basis_reconcile_summary()


@router.post("/reconcile-run-once")
def run_spot_basis_reconcile_once():
    from core.spot_basis_reconciler import run_spot_basis_reconcile_cycle
    return run_spot_basis_reconcile_cycle(force=True)
