"""Domain router for `pnl_v2`.

No runtime-router forwarding; routes are registered explicitly from domain services.
"""

from fastapi import APIRouter

from .service_detail import get_strategy_pnl_detail_v2
from .service_export import get_pnl_export_v2
from .service_funding_ingest import run_funding_ingest
from .service_reconcile import get_reconcile_latest_v2, run_reconcile_once_v2
from .service_strategies import get_strategy_pnl_v2
from .service_summary import get_pnl_summary_v2

router = APIRouter(prefix="/api/pnl/v2", tags=["pnl-v2"])
router.add_api_route("/summary", get_pnl_summary_v2, methods=["GET"])
router.add_api_route("/strategies", get_strategy_pnl_v2, methods=["GET"])
router.add_api_route("/strategies/{strategy_id}", get_strategy_pnl_detail_v2, methods=["GET"])
router.add_api_route("/export", get_pnl_export_v2, methods=["GET"])
router.add_api_route("/funding/ingest", run_funding_ingest, methods=["POST"])
router.add_api_route("/reconcile/run-once", run_reconcile_once_v2, methods=["POST"])
router.add_api_route("/reconcile/latest", get_reconcile_latest_v2, methods=["GET"])

__all__ = ["router"]
