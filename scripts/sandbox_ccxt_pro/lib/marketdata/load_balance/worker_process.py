from __future__ import annotations

import asyncio
import signal
import time

from lib.marketdata.load_balance.types import WorkerMetric
from lib.marketdata.load_balance.worker import WorkerConfig, WorkerRuntime


def _classify_loop_exception(exc: BaseException | None, message: str) -> str | None:
    if exc is not None and isinstance(exc, asyncio.CancelledError):
        return None
    text = message if message else ""
    if exc is not None:
        text = f"{type(exc).__name__}: {exc} {text}"
    if "AuthenticationError" in text or "PermissionDenied" in text:
        return "AUTH_FAIL"
    if "BadSymbol" in text or "NotSupported" in text:
        return "SYMBOL_FAIL"
    if "Requests are too frequent" in text or "nonce is behind cache" in text:
        return "RATE_LIMIT"
    if (
        "RequestTimeout" in text
        or "Cannot connect to host" in text
        or "getaddrinfo" in text
        or "Session is closed" in text
        or "Event loop is closed" in text
        or "Connection closed by remote server" in text
    ):
        return "NETWORK"
    if "Task was destroyed but it is pending!" in text:
        return "LOOP"
    if "Unclosed client session" in text or "Unclosed connector" in text:
        return "LOOP"
    if "requires to release all resources with an explicit call to the .close() coroutine" in text:
        return "LOOP"
    if "Future exception was never retrieved" in text and "CancelledError" in text:
        return None
    if not text.strip():
        return None
    return "UNKNOWN"


def _format_exception(exc: BaseException | None, message: str) -> str:
    if exc is None:
        return message
    text = f"{type(exc).__name__}: {exc}"
    return f"{text} {message}".strip()


def run_worker_process(config_dict: dict, metrics_q, stop_event) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    cfg = WorkerConfig(**config_dict)
    runtime = WorkerRuntime(cfg, metrics_q, stop_event)

    def _loop_exception_handler(_, context: dict) -> None:
        msg = str(context.get("message", ""))
        exc = context.get("exception")
        code = _classify_loop_exception(exc, msg)
        if code is None:
            return
        runtime.note_external_error(code)
        now = time.time()
        if now - _loop_exception_handler.last_print_at.get(code, 0.0) >= 2.0:
            _loop_exception_handler.last_print_at[code] = now
            print(f"[worker:{cfg.worker_id}] ASYNC_WARN[{code}]: {_format_exception(exc, msg)}")

    _loop_exception_handler.last_print_at = {}

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
                error_class_counts={"LOOP": 1},
                last_error_code="LOOP",
                terminal_reason="LOOP",
                degrade_stage=0,
                healthy_windows=0,
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
