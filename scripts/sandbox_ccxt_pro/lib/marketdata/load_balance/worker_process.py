from __future__ import annotations

import asyncio
import signal

from lib.marketdata.load_balance.types import WorkerMetric
from lib.marketdata.load_balance.worker import WorkerConfig, WorkerRuntime


def _is_benign_async_exception(exc: BaseException | None, message: str) -> bool:
    if "Unclosed client session" in message or "Unclosed connector" in message:
        return True
    if "Task was destroyed but it is pending!" in message:
        return True
    if "requires to release all resources with an explicit call to the .close() coroutine" in message:
        return True
    if exc is None:
        return False
    if isinstance(exc, asyncio.CancelledError):
        return True
    text = f"{type(exc).__name__}: {exc}"
    if "RequestTimeout" in text or "Cannot connect to host" in text:
        return True
    if "Event loop is closed" in text or "Session is closed" in text:
        return True
    if isinstance(exc, AttributeError) and "getaddrinfo" in text:
        return True
    if isinstance(exc, KeyError) and "api.gateio.ws" in text:
        return True
    if "Future exception was never retrieved" in message and "CancelledError" in text:
        return True
    return False


def run_worker_process(config_dict: dict, metrics_q, stop_event) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    cfg = WorkerConfig(**config_dict)
    runtime = WorkerRuntime(cfg, metrics_q, stop_event)

    def _loop_exception_handler(_, context: dict) -> None:
        msg = str(context.get("message", ""))
        exc = context.get("exception")
        if _is_benign_async_exception(exc, msg):
            return
        if exc is None:
            print(f"[worker:{cfg.worker_id}] ASYNC_WARN: {msg}")
            return
        print(f"[worker:{cfg.worker_id}] ASYNC_WARN: {type(exc).__name__}: {exc}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(_loop_exception_handler)
    try:
        loop.run_until_complete(runtime.run())
    except Exception as exc:  # noqa: BLE001
        metrics_q.put(
            WorkerMetric(
                worker_id=cfg.worker_id,
                exchange=cfg.exchange,
                market=cfg.market,
                status="error",
                degraded=True,
                window_sec=cfg.window_sec,
                shard_count=max(1, cfg.shard_count),
                order_book_limit=max(1, cfg.order_book_limit),
                batch_delay_ms=max(0, cfg.batch_delay_ms or 0),
                total_events=0,
                total_errors=1,
                total_bytes=0,
                total_reconnects=0,
                hz_p50=0.0,
                hz_p95=0.0,
                bw_mbps=0.0,
                symbols={},
                decision=None,
                fatal_errors=1,
            ).to_dict()
        )
        print(f"[worker:{cfg.worker_id}] FATAL: {type(exc).__name__}: {exc}")
    finally:
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
