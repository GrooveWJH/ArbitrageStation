"""Summary service for pnl-v2."""

from domains.pnl_v2 import integrations as pnl_v2_integrations

get_pnl_summary_v2 = pnl_v2_integrations.get_pnl_summary_v2

__all__ = ["get_pnl_summary_v2"]
