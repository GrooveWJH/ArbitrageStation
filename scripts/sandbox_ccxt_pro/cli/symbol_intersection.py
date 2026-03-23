#!/usr/bin/env python3
"""Get spot/futures symbol intersection for >=2 supported exchanges."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.common.io_utils import write_json_file  # noqa: E402
from lib.marketdata.intersection import SUPPORTED_EXCHANGES, build_report  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=False)


def print_report(report: dict) -> None:
    for exchange_id in report["exchanges"]:
        counts = report["exchange_counts"][exchange_id]
        print(f"{exchange_id} spot:", counts["spot_count"])
        print(f"{exchange_id} futures:", counts["futures_count"])
        print(f"{exchange_id} eligible(spot&&futures):", counts["eligible_count"])
    print("Intersection:", report["intersection_count"])
    print()
    for symbol in report["intersection_symbols"]:
        print(symbol)


def write_out(path: str, report: dict) -> None:
    out_path = Path(path)
    if out_path.suffix.lower() == ".json":
        write_json_file(out_path, report)
        return

    lines: list[str] = []
    for exchange_id in report["exchanges"]:
        counts = report["exchange_counts"][exchange_id]
        lines.extend(
            [
                f"{exchange_id} spot: {counts['spot_count']}",
                f"{exchange_id} futures: {counts['futures_count']}",
                f"{exchange_id} eligible(spot&&futures): {counts['eligible_count']}",
            ]
        )
    lines.extend([f"Intersection: {report['intersection_count']}", "", *report["intersection_symbols"]])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@app.command()
def run(
    exchanges: Annotated[
        list[str],
        typer.Option(
            "--exchanges",
            help="at least 2 distinct exchanges, e.g. --exchanges binance --exchanges okx",
        ),
    ] = ["binance", "okx"],
    json_output: Annotated[bool, typer.Option("--json", help="print JSON")] = False,
    out: Annotated[str, typer.Option(help="optional output file path (.json or .txt)")] = "",
) -> None:
    deduped = list(dict.fromkeys(x.strip().lower() for x in exchanges if x.strip()))
    unsupported = sorted([x for x in deduped if x not in SUPPORTED_EXCHANGES])
    if unsupported:
        joined = ", ".join(unsupported)
        raise typer.BadParameter(f"unsupported exchanges: {joined}", param_hint="--exchanges")
    if len(deduped) < 2:
        raise typer.BadParameter("至少需要 2 个不同交易所", param_hint="--exchanges")

    report = build_report(deduped)
    if json_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)

    if out:
        write_out(out, report)


if __name__ == "__main__":
    app()
