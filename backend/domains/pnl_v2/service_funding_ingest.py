"""Funding-ingest service for pnl-v2."""

from domains.pnl_v2 import integrations as pnl_v2_integrations

run_funding_ingest = pnl_v2_integrations.run_funding_ingest

__all__ = ["run_funding_ingest"]
