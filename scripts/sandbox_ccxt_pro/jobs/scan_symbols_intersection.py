#!/usr/bin/env python3
"""Periodically scan symbol intersection and write JSON file."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.common.io_utils import write_json_file  # noqa: E402
from lib.marketdata.intersection import SUPPORTED_EXCHANGES, build_report  # noqa: E402
from lib.reporting.log import log_error, log_info  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan multi-exchange symbol intersection periodically")
    parser.add_argument(
        "--exchanges",
        nargs="+",
        default=["binance", "okx", "gate", "mexc"],
        choices=SUPPORTED_EXCHANGES,
        help="at least 2 distinct exchanges",
    )
    parser.add_argument("--interval-seconds", type=int, default=600, help="scan interval seconds, default 600")
    parser.add_argument(
        "--output",
        default="scripts/sandbox_ccxt_pro/data/symbols_intersection.json",
        help="output JSON file path",
    )
    parser.add_argument("--once", action="store_true", help="run one scan and exit")
    args = parser.parse_args()

    args.exchanges = list(dict.fromkeys(args.exchanges))
    if len(args.exchanges) < 2:
        parser.error("--exchanges 至少需要 2 个不同交易所")
    if args.interval_seconds <= 0:
        parser.error("--interval-seconds 必须 > 0")
    return args


def write_report(out_path: Path, report: dict) -> None:
    write_json_file(
        out_path,
        {"generated_at": datetime.now().astimezone().isoformat(), "report": report},
    )


def run_once(exchanges: list[str], out_path: Path) -> None:
    log_info(f"开始扫描: exchanges={exchanges}")
    report = build_report(exchanges)
    write_report(out_path, report)
    log_info(f"扫描完成: intersection={report['intersection_count']} output={out_path}")


def sleep_with_progress(seconds: float) -> None:
    total = max(int(seconds), 0)
    if total == 0:
        return
    if not sys.stdout.isatty():
        time.sleep(total)
        return

    width = 28
    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        if elapsed >= total:
            break
        ratio = min(max(elapsed / total, 0.0), 1.0)
        done = int(width * ratio)
        remain = max(total - int(elapsed), 0)
        print(f"\r等待下轮 [{'#' * done}{'-' * (width - done)}] {int(ratio * 100):>3}% 剩余 {remain:>4}s", end="", flush=True)
        time.sleep(1)
    print("\r" + " " * 80, end="\r", flush=True)


def main() -> int:
    args = parse_args()
    out_path = Path(args.output)
    log_info(f"定时任务启动: interval={args.interval_seconds}s exchanges={args.exchanges} output={out_path}")
    try:
        if args.once:
            run_once(args.exchanges, out_path)
            return 0

        while True:
            started_at = datetime.now()
            try:
                run_once(args.exchanges, out_path)
            except Exception as exc:  # noqa: BLE001
                log_error("SCAN_FAIL", f"{type(exc).__name__}: {exc}")

            next_run = started_at + timedelta(seconds=args.interval_seconds)
            log_info(f"下次扫描时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            sleep_with_progress(max((next_run - datetime.now()).total_seconds(), 0))
    except KeyboardInterrupt:
        print()
        log_info("收到终止信号，任务结束")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
