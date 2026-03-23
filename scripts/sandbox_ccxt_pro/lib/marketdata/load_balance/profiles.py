from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExchangePerfProfile:
    batch_size: int
    batch_delay_ms: int
    max_shards: int
    max_reconnect_backoff: float


PROFILES: dict[str, dict[str, ExchangePerfProfile]] = {
    "balanced": {
        "binance": ExchangePerfProfile(batch_size=12, batch_delay_ms=500, max_shards=12, max_reconnect_backoff=20.0),
        "okx": ExchangePerfProfile(batch_size=12, batch_delay_ms=500, max_shards=12, max_reconnect_backoff=20.0),
        "gate": ExchangePerfProfile(batch_size=6, batch_delay_ms=1200, max_shards=16, max_reconnect_backoff=30.0),
        "mexc": ExchangePerfProfile(batch_size=5, batch_delay_ms=1500, max_shards=18, max_reconnect_backoff=30.0),
    },
    "conservative": {
        "binance": ExchangePerfProfile(batch_size=8, batch_delay_ms=900, max_shards=16, max_reconnect_backoff=30.0),
        "okx": ExchangePerfProfile(batch_size=8, batch_delay_ms=900, max_shards=16, max_reconnect_backoff=30.0),
        "gate": ExchangePerfProfile(batch_size=4, batch_delay_ms=1800, max_shards=24, max_reconnect_backoff=35.0),
        "mexc": ExchangePerfProfile(batch_size=4, batch_delay_ms=2000, max_shards=24, max_reconnect_backoff=35.0),
    },
    "aggressive": {
        "binance": ExchangePerfProfile(batch_size=20, batch_delay_ms=250, max_shards=10, max_reconnect_backoff=15.0),
        "okx": ExchangePerfProfile(batch_size=20, batch_delay_ms=250, max_shards=10, max_reconnect_backoff=15.0),
        "gate": ExchangePerfProfile(batch_size=8, batch_delay_ms=900, max_shards=14, max_reconnect_backoff=25.0),
        "mexc": ExchangePerfProfile(batch_size=7, batch_delay_ms=1000, max_shards=14, max_reconnect_backoff=25.0),
    },
}


def resolve_exchange_profile(profile: str, exchange: str) -> ExchangePerfProfile:
    return PROFILES.get(profile, PROFILES["balanced"]).get(exchange, PROFILES["balanced"]["binance"])

