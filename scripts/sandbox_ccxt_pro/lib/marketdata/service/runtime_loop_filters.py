from __future__ import annotations


def is_ws_keepalive_timeout(message: str, text: str) -> bool:
    msg = message or ""
    body = (text or "").lower()
    if "Future exception was never retrieved" not in msg:
        return False
    return (
        ("ping-pong keepalive missing" in body or "connection timeout" in body)
        and ("ws.okx.com" in body or "wss://" in body)
    )


def is_gate_subscription_race(exc: BaseException | None, message: str) -> bool:
    if not isinstance(exc, KeyError):
        return False
    return "orderbook:" in str(exc) and ("Client.receive_loop" in message or "Exception in callback" in message)


def is_gate_internal_future_error(message: str, text: str) -> bool:
    return "Future exception was never retrieved" in message and "api.gateio.ws/ws/v4" in text


def is_ws_close_1006_future(message: str, text: str) -> bool:
    return "Future exception was never retrieved" in message and "closing code 1006" in text.lower()


def is_future_cancelled(message: str, text: str) -> bool:
    return "Future exception was never retrieved" in message and "CancelledError" in text


def is_gate_cache_index_error(message: str, exc: BaseException | None) -> bool:
    if "Future exception was never retrieved" not in message:
        return False
    if not isinstance(exc, IndexError):
        return False
    if "list index out of range" not in str(exc).lower():
        return False
    tb = exc.__traceback__
    while tb is not None:
        filename = (tb.tb_frame.f_code.co_filename or "").replace("\\", "/").lower()
        if filename.endswith("/ccxt/pro/gate.py") or "/ccxt/pro/gate.py" in filename:
            return True
        tb = tb.tb_next
    return False
