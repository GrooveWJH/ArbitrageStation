"""Exchange profile helpers shared by API and background jobs."""

from __future__ import annotations


DEFAULT_UNIFIED_ACCOUNT_EXCHANGES = {
    "okx",
    "bybit",
    "bitget",
    "kucoin",
    "gate",
    "gateio",
    "woo",
    "woofipro",
}


def default_is_unified_account(exchange_name: str) -> bool:
    return (exchange_name or "").lower() in DEFAULT_UNIFIED_ACCOUNT_EXCHANGES


def resolve_is_unified_account(exchange_obj) -> bool:
    """Resolve unified-account mode with explicit DB override first."""
    if exchange_obj is None:
        return False
    override = getattr(exchange_obj, "is_unified_account", None)
    if override is not None:
        return bool(override)
    return default_is_unified_account(getattr(exchange_obj, "name", ""))

