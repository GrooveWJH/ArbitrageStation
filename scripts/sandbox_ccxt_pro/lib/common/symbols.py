from __future__ import annotations

import json
from pathlib import Path

from lib.common.io_utils import read_json_file
from lib.marketdata.intersection import SUPPORTED_EXCHANGES


def _norm_symbol_list(values: list[str]) -> list[str]:
    out = [str(s).strip().upper() for s in values if str(s).strip()]
    return list(dict.fromkeys(out))


def _norm_exchanges(values: list[str]) -> list[str]:
    out = [str(x).strip().lower() for x in values if str(x).strip()]
    return list(dict.fromkeys(out))


def _validate_schema_v3(payload: dict) -> None:
    version = payload.get("schema_version")
    if version != 3:
        raise ValueError(f"unsupported symbols schema_version: {version}, require 3")
    groups = payload.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("invalid symbols file: groups must be non-empty list")
    mode = str(payload.get("mode", "")).strip().lower()
    if mode not in {"single_group", "grouped"}:
        raise ValueError("invalid symbols file: mode must be single_group/grouped")
    if mode == "single_group" and len(groups) != 1:
        raise ValueError("invalid symbols file: single_group mode requires exactly 1 group")


def _exchange_symbol_map_from_groups(groups: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for idx, group in enumerate(groups):
        if not isinstance(group, dict):
            raise ValueError("invalid symbols file: group must be object")
        gid = str(group.get("id") or f"g{idx + 1}")
        exchanges_raw = group.get("exchanges")
        symbols_raw = group.get("symbols")
        if not isinstance(exchanges_raw, list) or not isinstance(symbols_raw, list):
            raise ValueError(f"invalid symbols file: group[{gid}] missing exchanges/symbols")
        exchanges = _norm_exchanges(exchanges_raw)
        symbols = _norm_symbol_list(symbols_raw)
        if len(exchanges) < 2:
            raise ValueError(f"invalid symbols file: group[{gid}] requires >=2 exchanges")
        if not symbols:
            raise ValueError(f"invalid symbols file: group[{gid}] symbols empty")
        unsupported = [ex for ex in exchanges if ex not in SUPPORTED_EXCHANGES]
        if unsupported:
            raise ValueError(f"invalid symbols file: group[{gid}] unsupported exchanges: {', '.join(unsupported)}")
        for ex in exchanges:
            if ex in out:
                raise ValueError(f"invalid symbols file: exchange appears in multiple groups: {ex}")
            out[ex] = symbols
    if not out:
        raise ValueError("invalid symbols file: empty exchange-symbol mapping")
    return out


def load_symbols_for_service(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"symbols file not found: {path}")
    try:
        payload = read_json_file(path)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid symbols file (not JSON): {path}. "
            "请重新生成: .venv/bin/python scripts/sandbox_ccxt_pro/cli/symbol_intersection.py --all --json --out "
            "scripts/sandbox_ccxt_pro/data/symbols_intersection.json"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid symbols file: root must be object")
    _validate_schema_v3(payload)
    groups = payload["groups"]
    return _exchange_symbol_map_from_groups(groups)


def load_intersection_symbols(path: Path) -> list[str]:
    symbols_by_exchange = load_symbols_for_service(path)
    merged: list[str] = []
    for symbols in symbols_by_exchange.values():
        merged.extend(symbols)
    out = _norm_symbol_list(merged)
    if not out:
        raise ValueError("intersection_symbols is empty")
    return out
