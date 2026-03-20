from . import base
from .base import Depends, Query, Session, get_db, router

def get_spot_basis_opportunities(
    symbol: str = Query("", description="Partial symbol filter"),
    min_rate: float = Query(0.01, description="Min positive funding rate % on perp exchange"),
    min_perp_volume: float = Query(0, description="Min perp 24h volume"),
    min_spot_volume: float = Query(0, description="Min spot 24h volume"),
    min_basis_pct: float = Query(0.0, description="Min positive basis % (perp - spot) / spot"),
    perp_exchange_ids: str = Query("", description="Comma separated perp exchange IDs"),
    spot_exchange_ids: str = Query("", description="Comma separated spot exchange IDs"),
    require_cross_exchange: bool = Query(False, description="Force spot exchange != perp exchange"),
    action_mode: str = Query("open", description="open | switch"),
    sort_by: str = Query("score_strict", description="score_strict | annualized | basis_abs | basis_pct | score"),
    limit: int = Query(200, ge=1, le=1000),
    refresh_history: bool = Query(False, description="Best-effort refresh funding history from exchange before scan"),
    refresh_days: int = Query(base._FUNDING_STABILITY_WINDOW_DAYS, ge=1, le=base._FUNDING_HISTORY_REFRESH_MAX_DAYS),
    refresh_limit: int = Query(40, ge=1, le=base._FUNDING_HISTORY_REFRESH_MAX_LEGS),
    refresh_ttl_secs: int = Query(base._FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, ge=0, le=86400),
    refresh_force: bool = Query(False, description="Ignore refresh TTL and force refresh"),
    db: Session = Depends(get_db),
):
    from .scanner import _scan_spot_basis_opportunities

    return _scan_spot_basis_opportunities(
        db=db,
        symbol=symbol,
        min_rate=min_rate,
        min_perp_volume=min_perp_volume,
        min_spot_volume=min_spot_volume,
        min_basis_pct=min_basis_pct,
        perp_exchange_ids=perp_exchange_ids,
        spot_exchange_ids=spot_exchange_ids,
        require_cross_exchange=require_cross_exchange,
        action_mode=action_mode,
        sort_by=sort_by,
        limit=limit,
        refresh_history=refresh_history,
        refresh_days=refresh_days,
        refresh_limit=refresh_limit,
        refresh_ttl_secs=refresh_ttl_secs,
        refresh_force=refresh_force,
    )


@router.post("/refresh-funding-history")
def refresh_spot_basis_funding_history(
    symbol: str = Query("", description="Partial symbol filter"),
    perp_exchange_ids: str = Query("", description="Comma separated perp exchange IDs"),
    refresh_days: int = Query(base._FUNDING_STABILITY_WINDOW_DAYS, ge=1, le=base._FUNDING_HISTORY_REFRESH_MAX_DAYS),
    refresh_limit: int = Query(40, ge=1, le=base._FUNDING_HISTORY_REFRESH_MAX_LEGS),
    refresh_ttl_secs: int = Query(base._FUNDING_HISTORY_REFRESH_DEFAULT_TTL_SECS, ge=0, le=86400),
    refresh_force: bool = Query(False, description="Ignore refresh TTL and force refresh"),
    db: Session = Depends(get_db),
):
    from .funding_history_io import _build_funding_refresh_targets, _build_perp_symbol_entries
    from .funding_history_refresh import _refresh_funding_history_targets

    ex_map = base.get_cached_exchange_map()
    ex_obj_map = {e.id: e for e in db.query(base.Exchange).all()}
    symbol_like = symbol.upper().strip()
    perp_allow_ids = base._parse_ids(perp_exchange_ids)

    by_symbol = _build_perp_symbol_entries(symbol_like=symbol_like, ex_map=ex_map)
    symbol_items = list(by_symbol.items())
    targets = _build_funding_refresh_targets(
        symbol_items=symbol_items,
        max_legs=max(1, int(refresh_limit or 1)),
    )
    if perp_allow_ids:
        targets = [t for t in targets if int(t.get("exchange_id") or 0) in perp_allow_ids]

    refresh_meta = _refresh_funding_history_targets(
        db=db,
        exchange_obj_map=ex_obj_map,
        targets=targets,
        history_days=max(1, int(refresh_days or base._FUNDING_STABILITY_WINDOW_DAYS)),
        refresh_ttl_secs=max(0, int(refresh_ttl_secs or 0)),
        force=bool(refresh_force),
    )
    return {
        "ok": True,
        "symbol_candidates": len(symbol_items),
        "target_legs": len(targets),
        "refresh_meta": refresh_meta,
    }


@router.post("/refresh-funding-history/start")
def start_spot_basis_funding_history_refresh(
    symbol: str = Query("", description="Partial symbol filter"),
    perp_exchange_ids: str = Query("", description="Comma separated perp exchange IDs"),
    refresh_days: int = Query(base._FUNDING_STABILITY_WINDOW_DAYS, ge=1, le=base._FUNDING_HISTORY_REFRESH_MAX_DAYS),
    refresh_limit: int = Query(base._FUNDING_HISTORY_REFRESH_MAX_LEGS, ge=1, le=base._FUNDING_HISTORY_REFRESH_MAX_LEGS),
    refresh_ttl_secs: int = Query(0, ge=0, le=86400),
    refresh_force: bool = Query(True, description="Ignore refresh TTL and force refresh"),
):
    from .funding_history_refresh import _start_funding_history_refresh_job

    symbol_like = symbol.upper().strip()
    perp_allow_ids = base._parse_ids(perp_exchange_ids)
    return _start_funding_history_refresh_job(
        symbol_like=symbol_like,
        perp_allow_ids=perp_allow_ids,
        refresh_days=refresh_days,
        refresh_limit=refresh_limit,
        refresh_ttl_secs=refresh_ttl_secs,
        refresh_force=refresh_force,
    )


@router.get("/refresh-funding-history/progress")
def get_spot_basis_funding_history_refresh_progress():
    from .funding_history_refresh import _funding_refresh_job_snapshot

    snap = _funding_refresh_job_snapshot()
    req = max(1, int(snap.get("requested_legs") or 1))
    done = max(0, int(snap.get("processed_legs") or 0))
    snap["progress_pct"] = round(min(100.0, (done / req) * 100.0), 2)
    return {"ok": True, "job": snap}
