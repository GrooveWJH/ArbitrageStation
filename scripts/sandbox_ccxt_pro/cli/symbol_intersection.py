#!/usr/bin/env python3
"""Build intersection symbols JSON (schema v3, flattened groups)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.common.io_utils import write_json_file  # noqa: E402
from lib.marketdata.intersection import SUPPORTED_EXCHANGES, collect_symbol_sets  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=False)


def _normalize_exchanges(values: list[str]) -> list[str]:
    return list(dict.fromkeys(x.strip().lower() for x in values if x.strip()))


def _validate_exchanges(exchanges: list[str], *, hint: str) -> None:
    unsupported = sorted([x for x in exchanges if x not in SUPPORTED_EXCHANGES])
    if unsupported:
        raise typer.BadParameter(f"unsupported exchanges: {', '.join(unsupported)}", param_hint=hint)
    if len(exchanges) < 2:
        raise typer.BadParameter("至少需要 2 个不同交易所", param_hint=hint)


def _intersection_symbols(exchanges: list[str], cache: dict[str, tuple[set[str], set[str]]]) -> list[str]:
    eligible_sets: list[set[str]] = []
    for exchange_id in exchanges:
        if exchange_id not in cache:
            cache[exchange_id] = collect_symbol_sets(exchange_id)
        spot, futures = cache[exchange_id]
        eligible_sets.append(spot & futures)
    return sorted(set.intersection(*eligible_sets))


def _parse_pair_expr(expr: str) -> list[str]:
    normalized = expr.replace("&&", ",").replace("+", ",").replace("，", ",").replace(" ", ",")
    return _normalize_exchanges([x for x in normalized.split(",") if x.strip()])


def _single_group_id(exchanges: list[str]) -> str:
    if set(exchanges) == set(SUPPORTED_EXCHANGES):
        return "all_4"
    return "group_1"


def _group_id_for_pair(idx: int, exchanges: list[str]) -> str:
    return f"pair_{idx + 1}_{'_'.join(exchanges)}"


def _build_schema_v3_doc(mode: str, groups: list[dict], inputs: dict[str, list[str]]) -> dict:
    return {
        "schema_version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "groups": groups,
        "meta": {
            "intersection_rule": "group symbols = intersection(spot and futures) across group exchanges",
            "group_count": len(groups),
            "symbol_counts": {group["id"]: len(group["symbols"]) for group in groups},
            "inputs": inputs,
        },
    }


def _validate_no_cross_group_duplicate_exchanges(groups: list[list[str]]) -> None:
    seen: set[str] = set()
    for exchanges in groups:
        for ex in exchanges:
            if ex in seen:
                raise typer.BadParameter(f"同一交易所出现在多个 group: {ex}", param_hint="--pair")
            seen.add(ex)


def _write_out(path: str, payload: dict) -> None:
    out_path = Path(path)
    if out_path.suffix.lower() == ".json":
        write_json_file(out_path, payload)
        return
    lines = [f"schema_version: {payload.get('schema_version')}", f"mode: {payload.get('mode')}", ""]
    for group in payload.get("groups", []):
        gid = group.get("id", "-")
        exchanges = ", ".join(group.get("exchanges", []))
        symbols = group.get("symbols", [])
        lines.append(f"=== group: {gid} ===")
        lines.append(f"- exchanges: {exchanges}")
        lines.append(f"- symbols: {len(symbols)}")
        lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


@app.command()
def run(
    all_exchanges: Annotated[bool, typer.Option("--all", help="use all supported exchanges")] = False,
    exchanges: Annotated[
        list[str],
        typer.Option("--exchanges", help="exchange list; supports repeated style or first value after --exchanges"),
    ] = ["binance", "okx"],
    pairs: Annotated[
        list[str],
        typer.Option("--pair", help="group pair, e.g. --pair 'binance&&okx' --pair 'gate&&mexc'"),
    ] = [],
    extra_exchanges: Annotated[list[str], typer.Argument(help="extra exchanges for compact syntax")] = [],
    json_output: Annotated[bool, typer.Option("--json", help="print JSON")] = False,
    out: Annotated[str, typer.Option(help="optional output file path (.json/.txt)")] = "",
) -> None:
    merged = [*exchanges, *extra_exchanges]
    if all_exchanges:
        merged = list(SUPPORTED_EXCHANGES)
    base_exchanges = _normalize_exchanges(merged)
    _validate_exchanges(base_exchanges, hint="--exchanges")

    cache: dict[str, tuple[set[str], set[str]]] = {}
    try:
        groups: list[dict] = []
        inputs: dict[str, list[str]] = {}
        if pairs:
            pair_defs = [_parse_pair_expr(expr) for expr in pairs]
            _validate_no_cross_group_duplicate_exchanges(pair_defs)
            for group in pair_defs:
                _validate_exchanges(group, hint="--pair")
            for idx, group_exchanges in enumerate(pair_defs):
                symbols = _intersection_symbols(group_exchanges, cache)
                gid = _group_id_for_pair(idx, group_exchanges)
                groups.append({"id": gid, "exchanges": group_exchanges, "symbols": symbols})
                inputs[gid] = group_exchanges
            mode = "grouped"
        else:
            symbols = _intersection_symbols(base_exchanges, cache)
            gid = _single_group_id(base_exchanges)
            groups.append({"id": gid, "exchanges": base_exchanges, "symbols": symbols})
            inputs[gid] = base_exchanges
            mode = "single_group"
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"获取交集失败: {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(1)

    payload = _build_schema_v3_doc(mode=mode, groups=groups, inputs=inputs)

    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"schema_version: {payload['schema_version']}")
        print(f"mode: {payload['mode']}")
        print("groups:")
        for group in payload["groups"]:
            print(
                f"  - {group['id']}: exchanges={len(group['exchanges'])}, "
                f"symbols={len(group['symbols'])}"
            )

    if out:
        _write_out(out, payload)


if __name__ == "__main__":
    app()
