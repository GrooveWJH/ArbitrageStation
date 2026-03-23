from __future__ import annotations

SUPPORTED_EXCHANGES = ("binance", "gate", "mexc", "okx")


def build_exchange(exchange_id: str):
    try:
        import ccxt
    except ModuleNotFoundError as exc:
        raise SystemExit("缺少依赖 ccxt，请先安装：python3 -m pip install ccxt") from exc

    cls = getattr(ccxt, exchange_id)
    return cls({"enableRateLimit": True})


def normalize_pair(market: dict) -> str | None:
    base = str(market.get("base") or "").strip().upper()
    quote = str(market.get("quote") or "").strip().upper()
    if not base or not quote:
        return None
    return f"{base}/{quote}"


def collect_symbol_sets(exchange_id: str) -> tuple[set[str], set[str]]:
    ex = build_exchange(exchange_id)
    try:
        markets = ex.load_markets()
    finally:
        try:
            ex.close()
        except Exception:
            pass

    spot: set[str] = set()
    futures: set[str] = set()
    for market in markets.values():
        pair = normalize_pair(market)
        if not pair:
            continue
        if bool(market.get("spot")):
            spot.add(pair)
        if bool(market.get("swap")) or bool(market.get("future")):
            futures.add(pair)
    return spot, futures


def build_report(exchanges: list[str]) -> dict:
    per_exchange: dict[str, dict[str, set[str]]] = {}
    eligible_sets: list[set[str]] = []
    for exchange_id in exchanges:
        spot, futures = collect_symbol_sets(exchange_id)
        eligible = spot & futures
        per_exchange[exchange_id] = {"spot": spot, "futures": futures, "eligible": eligible}
        eligible_sets.append(eligible)

    intersection = sorted(set.intersection(*eligible_sets))
    exchange_counts = {
        exchange_id: {
            "spot_count": len(data["spot"]),
            "futures_count": len(data["futures"]),
            "eligible_count": len(data["eligible"]),
        }
        for exchange_id, data in per_exchange.items()
    }
    return {
        "exchanges": exchanges,
        "exchange_counts": exchange_counts,
        "intersection_count": len(intersection),
        "intersection_symbols": intersection,
    }

