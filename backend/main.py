import asyncio
import logging
import os
import sys
from datetime import timedelta, timezone

# Ensure backend directory is importable
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from infra.market.gateway import get_market_read_status, verify_market_read_ready

from db import SessionLocal, init_db
from db.models import AppConfig, Exchange
from error_handlers import register_exception_handlers
from readiness import readiness_snapshot
from domains.exchanges.service import default_is_unified_account
from domains.exchanges.router import router as exchanges_router
from domains.dashboard.router import router as dashboard_router
from domains.trading.router import router as trading_router
from domains.settings.router import router as settings_router
from domains.analytics.router import router as analytics_router
from domains.spread_monitor.router import router as spread_monitor_router
from domains.spread_arb.router import router as spread_arb_router
from domains.spot_basis.router import router as spot_basis_router
from domains.spot_basis_data.router import router as spot_basis_data_router
from domains.pnl_v2.router import router as pnl_v2_router
from domains.websocket.router import (
    router as ws_router,
    start_broadcast_loop,
    start_price_broadcast_loop,
)
from domains.runtime.service import (
    collect_equity_snapshot,
    collect_funding_rates,
    refresh_spread_stats,
    resync_time_differences,
    run_daily_pnl_v2_reconcile_job,
    run_funding_ingest_cycle,
    run_risk_checks,
    run_spot_basis_auto_open_cycle,
    run_spot_basis_reconcile_cycle,
    run_spread_arb,
    schedule_collect_recent_snapshots,
    schedule_daily_universe_freeze,
    setup_all_hedge_modes,
    sync_market_opportunity_inputs,
    sync_market_volume_cache,
    start_okx_private_ws_supervisor,
    stop_okx_private_ws_supervisor,
    update_position_prices,
    update_spread_position_prices,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "data", "app.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)
EQUITY_SNAPSHOT_INTERVAL_SECS = 20
FUNDING_SYNC_INTERVAL_SECS = 5
VOLUME_SYNC_INTERVAL_SECS = 60
OPPORTUNITY_SYNC_INTERVAL_SECS = 1
POSITION_PRICE_SYNC_INTERVAL_SECS = 2
DEFAULT_PUBLIC_EXCHANGES = ("binance", "okx", "gate", "mexc")

app = FastAPI(title="Arbitrage Tool API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(exchanges_router)
app.include_router(dashboard_router)
app.include_router(trading_router)
app.include_router(settings_router)
app.include_router(analytics_router)
app.include_router(spread_monitor_router)
app.include_router(spread_arb_router)
app.include_router(spot_basis_router)
app.include_router(spot_basis_data_router)
app.include_router(pnl_v2_router)
app.include_router(ws_router)
register_exception_handlers(app, logger)

# Freeze scheduler timezone to UTC+8 so cron jobs are deterministic across hosts.
UTC8 = timezone(timedelta(hours=8))
scheduler = BackgroundScheduler(timezone=UTC8)


def reschedule_jobs(data_interval: int = None, risk_interval: int = None):
    if data_interval is not None:
        safe_data_interval = max(1, int(data_interval))
        scheduler.reschedule_job("update_prices", trigger="interval", seconds=safe_data_interval)
    if risk_interval is not None:
        safe_risk_interval = max(3, int(risk_interval))
        scheduler.reschedule_job("risk_checks", trigger="interval", seconds=safe_risk_interval)


def _get_app_config():
    db = SessionLocal()
    try:
        return db.query(AppConfig).first()
    finally:
        db.close()


def _ensure_public_read_exchanges() -> None:
    db = SessionLocal()
    try:
        existing = {
            str(ex.name or "").lower().strip(): ex
            for ex in db.query(Exchange).all()
            if ex.name
        }
        changed = False
        for name in DEFAULT_PUBLIC_EXCHANGES:
            if name in existing:
                continue
            db.add(
                Exchange(
                    name=name,
                    display_name=name.upper(),
                    api_key="",
                    api_secret="",
                    passphrase="",
                    is_active=True,
                    is_testnet=False,
                    is_unified_account=default_is_unified_account(name),
                )
            )
            changed = True
        if changed:
            db.commit()
            logger.info("Seeded default public exchanges for market-read: %s", ",".join(DEFAULT_PUBLIC_EXCHANGES))
    finally:
        db.close()


@app.on_event("startup")
async def startup():
    os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
    init_db()
    _ensure_public_read_exchanges()
    logger.info("Database initialized")
    verify_market_read_ready()
    logger.info("Market read source ready: %s", get_market_read_status().get("base_url"))

    cfg = _get_app_config()
    risk_interval = max(3, int(cfg.risk_check_interval if cfg else 10))

    scheduler.add_job(collect_funding_rates, "interval", seconds=FUNDING_SYNC_INTERVAL_SECS,
                      id="collect_rates", replace_existing=True)
    scheduler.add_job(sync_market_volume_cache, "interval", seconds=VOLUME_SYNC_INTERVAL_SECS,
                      id="collect_volume", replace_existing=True)
    scheduler.add_job(sync_market_opportunity_inputs, "interval", seconds=OPPORTUNITY_SYNC_INTERVAL_SECS,
                      id="collect_opportunity_inputs", replace_existing=True)
    scheduler.add_job(update_position_prices, "interval", seconds=POSITION_PRICE_SYNC_INTERVAL_SECS,
                      id="update_prices", replace_existing=True)
    scheduler.add_job(run_risk_checks, "interval", seconds=risk_interval,
                      id="risk_checks", replace_existing=True)
    # Run spread-arb cycle at a safer cadence to avoid DB pool starvation.
    scheduler.add_job(run_spread_arb, "interval", seconds=5,
                      id="spread_arb", replace_existing=True)
    scheduler.add_job(update_spread_position_prices, "interval", seconds=10,
                      id="spread_prices", replace_existing=True)
    scheduler.add_job(resync_time_differences, "interval", minutes=5,
                      id="resync_time", replace_existing=True)
    scheduler.add_job(refresh_spread_stats, "interval", minutes=15,
                      id="spread_stats", replace_existing=True)
    scheduler.add_job(collect_equity_snapshot, "interval", seconds=EQUITY_SNAPSHOT_INTERVAL_SECS,
                      id="equity_snapshot", replace_existing=True)
    scheduler.add_job(run_funding_ingest_cycle, "interval", minutes=5,
                      id="funding_ingest", replace_existing=True)
    scheduler.add_job(
        run_daily_pnl_v2_reconcile_job,
        "cron",
        hour=0,
        minute=10,
        id="pnl_v2_daily_reconcile",
        replace_existing=True,
    )
    scheduler.add_job(run_spot_basis_auto_open_cycle, "interval", seconds=5,
                      id="spot_basis_auto_open", replace_existing=True)
    scheduler.add_job(
        run_spot_basis_reconcile_cycle,
        "interval",
        seconds=30,
        id="spot_basis_reconcile",
        replace_existing=True,
    )
    scheduler.add_job(
        schedule_collect_recent_snapshots,
        "interval",
        minutes=15,
        kwargs={
            "top_n": 40,
            "min_perp_volume": 0.0,
            "min_spot_volume": 0.0,
            "lookback_buckets": 8,
        },
        id="spot_basis_data_collect",
        replace_existing=True,
    )
    scheduler.add_job(
        schedule_daily_universe_freeze,
        "cron",
        hour=0,
        minute=5,
        kwargs={
            "top_n": 120,
            "min_perp_volume": 0.0,
            "min_spot_volume": 0.0,
        },
        id="spot_basis_universe_daily",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started (funding: %ss, volume: %ss, opp: %ss, pos: %ss, risk: %ss, equity_snapshot: %ss)",
        FUNDING_SYNC_INTERVAL_SECS,
        VOLUME_SYNC_INTERVAL_SECS,
        OPPORTUNITY_SYNC_INTERVAL_SECS,
        POSITION_PRICE_SYNC_INTERVAL_SECS,
        risk_interval,
        EQUITY_SNAPSHOT_INTERVAL_SECS,
    )

    # Enable hedge mode on all exchanges at startup
    asyncio.get_event_loop().run_in_executor(None, setup_all_hedge_modes)

    # Initial data pull
    asyncio.get_event_loop().run_in_executor(None, collect_funding_rates)
    asyncio.get_event_loop().run_in_executor(None, sync_market_volume_cache)
    asyncio.get_event_loop().run_in_executor(None, sync_market_opportunity_inputs)
    asyncio.get_event_loop().run_in_executor(None, refresh_spread_stats)
    asyncio.get_event_loop().run_in_executor(None, collect_equity_snapshot)

    # WebSocket broadcast loop (rates + opportunities every 5s)
    asyncio.create_task(start_broadcast_loop(interval=5))
    # Price diff broadcast loop (every 1s)
    asyncio.create_task(start_price_broadcast_loop())
    # Exchange private stream: OKX account/positions/orders.
    start_okx_private_ws_supervisor()


@app.on_event("shutdown")
async def shutdown():
    await stop_okx_private_ws_supervisor()
    scheduler.shutdown(wait=False)


@app.get("/api/health")
def health():
    return {"status": "ok", "market_read": get_market_read_status()}


@app.get("/api/ready")
def ready():
    payload, code = readiness_snapshot(
        session_factory=SessionLocal,
        scheduler=scheduler,
        market_status_getter=get_market_read_status,
    )
    return JSONResponse(status_code=code, content=payload)
