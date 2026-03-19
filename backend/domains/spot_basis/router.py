"""Domain router for `spot_basis`.

No legacy router forwarding; routes are registered from domain service call points.
"""

from fastapi import APIRouter

from .service import (
    get_spot_basis_auto_config,
    get_spot_basis_auto_cycle_last,
    get_spot_basis_auto_cycle_logs,
    get_spot_basis_auto_decision_preview,
    get_spot_basis_auto_status,
    get_spot_basis_drawdown_watermark,
    get_spot_basis_funding_history_refresh_progress,
    get_spot_basis_history,
    get_spot_basis_opportunities,
    get_spot_basis_reconcile_last,
    refresh_spot_basis_funding_history,
    reset_spot_basis_drawdown_watermark,
    run_spot_basis_auto_cycle_once,
    run_spot_basis_reconcile_once,
    start_spot_basis_funding_history_refresh,
    update_spot_basis_auto_config,
    update_spot_basis_auto_status,
)

router = APIRouter(prefix="/api/spot-basis", tags=["spot-basis"])
router.add_api_route("/opportunities", get_spot_basis_opportunities, methods=["GET"])
router.add_api_route("/refresh-funding-history", refresh_spot_basis_funding_history, methods=["POST"])
router.add_api_route("/refresh-funding-history/start", start_spot_basis_funding_history_refresh, methods=["POST"])
router.add_api_route("/refresh-funding-history/progress", get_spot_basis_funding_history_refresh_progress, methods=["GET"])
router.add_api_route("/auto-decision-preview", get_spot_basis_auto_decision_preview, methods=["GET"])
router.add_api_route("/auto-config", get_spot_basis_auto_config, methods=["GET"])
router.add_api_route("/auto-config", update_spot_basis_auto_config, methods=["PUT"])
router.add_api_route("/drawdown-watermark", get_spot_basis_drawdown_watermark, methods=["GET"])
router.add_api_route("/drawdown-watermark/reset", reset_spot_basis_drawdown_watermark, methods=["POST"])
router.add_api_route("/auto-status", get_spot_basis_auto_status, methods=["GET"])
router.add_api_route("/auto-status", update_spot_basis_auto_status, methods=["PUT"])
router.add_api_route("/auto-cycle-last", get_spot_basis_auto_cycle_last, methods=["GET"])
router.add_api_route("/auto-cycle-logs", get_spot_basis_auto_cycle_logs, methods=["GET"])
router.add_api_route("/auto-cycle-run-once", run_spot_basis_auto_cycle_once, methods=["POST"])
router.add_api_route("/reconcile-last", get_spot_basis_reconcile_last, methods=["GET"])
router.add_api_route("/reconcile-run-once", run_spot_basis_reconcile_once, methods=["POST"])
router.add_api_route("/history", get_spot_basis_history, methods=["GET"])

__all__ = ["router"]
