from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ShardLoadState:
    symbol: str
    weight: float
    hz: float
    error_rate: float
    reconnects: int


class ShardPlanner:
    @staticmethod
    def even(symbols: list[str], shard_count: int) -> list[list[str]]:
        if shard_count <= 1 or len(symbols) <= 1:
            return [list(symbols)]
        shard_count = max(1, min(shard_count, len(symbols)))
        out = [[] for _ in range(shard_count)]
        for i, symbol in enumerate(symbols):
            out[i % shard_count].append(symbol)
        return [x for x in out if x]

    @staticmethod
    def weighted(symbols: list[str], shard_count: int, snaps: dict[str, dict]) -> list[list[str]]:
        if shard_count <= 1 or len(symbols) <= 1:
            return [list(symbols)]
        shard_count = max(1, min(shard_count, len(symbols)))
        states: list[ShardLoadState] = []
        for symbol in symbols:
            s = snaps.get(symbol, {})
            hz = float(s.get("hz", 0.0))
            err = float(s.get("error_rate", 0.0))
            rc = int(s.get("reconnects", 0))
            # Weight = throughput + error penalty + reconnect penalty
            weight = hz + (err * 10.0) + (rc * 0.1)
            states.append(ShardLoadState(symbol=symbol, weight=weight, hz=hz, error_rate=err, reconnects=rc))
        states.sort(key=lambda x: x.weight, reverse=True)

        buckets = [[] for _ in range(shard_count)]
        loads = [0.0] * shard_count
        for st in states:
            idx = min(range(shard_count), key=lambda i: loads[i])
            buckets[idx].append(st.symbol)
            loads[idx] += st.weight
        return [x for x in buckets if x]

