"""Domain router for `spot_basis`.

No legacy router forwarding; routes are registered from domain service call points.
"""

from fastapi import APIRouter

from . import service as spot_basis_service

router = APIRouter(prefix="/api/spot-basis", tags=["spot-basis"])
router.add_api_route("/opportunities", spot_basis_service.get_spot_basis_opportunities, methods=["GET"])
router.add_api_route("/refresh-funding-history", spot_basis_service.refresh_spot_basis_funding_history, methods=["POST"])
router.add_api_route("/refresh-funding-history/start", spot_basis_service.start_spot_basis_funding_history_refresh, methods=["POST"])
router.add_api_route(
    "/refresh-funding-history/progress",
    spot_basis_service.get_spot_basis_funding_history_refresh_progress,
    methods=["GET"],
)
router.add_api_route("/auto-decision-preview", spot_basis_service.get_spot_basis_auto_decision_preview, methods=["GET"])
router.add_api_route("/auto-config", spot_basis_service.get_spot_basis_auto_config, methods=["GET"])
router.add_api_route("/auto-config", spot_basis_service.update_spot_basis_auto_config, methods=["PUT"])
router.add_api_route("/drawdown-watermark", spot_basis_service.get_spot_basis_drawdown_watermark, methods=["GET"])
router.add_api_route(
    "/drawdown-watermark/reset",
    spot_basis_service.reset_spot_basis_drawdown_watermark,
    methods=["POST"],
)
router.add_api_route("/auto-status", spot_basis_service.get_spot_basis_auto_status, methods=["GET"])
router.add_api_route("/auto-status", spot_basis_service.update_spot_basis_auto_status, methods=["PUT"])
router.add_api_route("/auto-cycle-last", spot_basis_service.get_spot_basis_auto_cycle_last, methods=["GET"])
router.add_api_route("/auto-cycle-logs", spot_basis_service.get_spot_basis_auto_cycle_logs, methods=["GET"])
router.add_api_route("/auto-cycle-run-once", spot_basis_service.run_spot_basis_auto_cycle_once, methods=["POST"])
router.add_api_route("/reconcile-last", spot_basis_service.get_spot_basis_reconcile_last, methods=["GET"])
router.add_api_route("/reconcile-run-once", spot_basis_service.run_spot_basis_reconcile_once, methods=["POST"])
router.add_api_route("/history", spot_basis_service.get_spot_basis_history, methods=["GET"])

__all__ = ["router"]
