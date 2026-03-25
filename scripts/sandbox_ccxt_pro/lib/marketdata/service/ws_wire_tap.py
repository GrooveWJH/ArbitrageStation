from __future__ import annotations

import importlib
from typing import Callable

from lib.reporting.log import log_error


class WsWireTap:
    _patched = False
    _orig_handle_message = None
    _listeners: dict[int, Callable[[str, int], None]] = {}
    _next_listener_id = 1

    def __init__(self, on_frame: Callable[[str, int], None]):
        self._on_frame = on_frame
        self._listener_id: int | None = None
        self.enabled = False
        self.source = "disabled"

    @classmethod
    def _extract_frame_bytes(cls, message) -> int:
        data = getattr(message, "data", None)
        if data is None:
            return 0
        if isinstance(data, bytes):
            return len(data)
        if isinstance(data, str):
            return len(data.encode("utf-8"))
        return 0

    @classmethod
    def _worker_key_from_client(cls, client) -> str:
        cached = getattr(client, "_codex_worker_key", "")
        if cached:
            return str(cached)

        callback = getattr(client, "on_message_callback", None)
        exchange = getattr(callback, "__self__", None)
        ex_id = str(getattr(exchange, "id", "") or "")
        market = ""
        options = getattr(exchange, "options", {}) if exchange is not None else {}
        if isinstance(options, dict):
            default_type = str(options.get("defaultType", "") or "").lower()
            if default_type in {"future", "futures", "swap"}:
                market = "swap"
            elif default_type == "spot":
                market = "spot"

        if not market:
            url = str(getattr(client, "url", "") or "").lower()
            if any(x in url for x in ("futures", "swap", "perp", "contract")):
                market = "swap"
            elif url:
                market = "spot"

        if ex_id and market:
            key = f"{ex_id}:{market}"
            try:
                setattr(client, "_codex_worker_key", key)
            except Exception:
                pass
            return key
        return ""

    @classmethod
    def _install_patch(cls) -> bool:
        if cls._patched:
            return True
        try:
            ws_client_mod = importlib.import_module("ccxt.async_support.base.ws.client")
        except Exception as exc:  # noqa: BLE001
            log_error("WIRE_TAP", f"patch disabled: import failed: {type(exc).__name__}: {exc}")
            return False

        client_cls = getattr(ws_client_mod, "Client", None)
        if client_cls is None or not hasattr(client_cls, "handle_message"):
            log_error("WIRE_TAP", "patch disabled: Client.handle_message not found")
            return False

        orig = getattr(client_cls, "handle_message")
        if not callable(orig):
            log_error("WIRE_TAP", "patch disabled: handle_message not callable")
            return False

        def patched_handle_message(client, message):
            try:
                frame_bytes = cls._extract_frame_bytes(message)
                if frame_bytes > 0:
                    worker_id = cls._worker_key_from_client(client)
                    if worker_id:
                        for cb in tuple(cls._listeners.values()):
                            cb(worker_id, frame_bytes)
            except Exception:
                # Never break ccxt message flow because of telemetry
                pass
            return orig(client, message)

        cls._orig_handle_message = orig
        setattr(client_cls, "handle_message", patched_handle_message)
        cls._patched = True
        return True

    @classmethod
    def _uninstall_patch_if_idle(cls) -> None:
        if not cls._patched or cls._listeners:
            return
        try:
            ws_client_mod = importlib.import_module("ccxt.async_support.base.ws.client")

            client_cls = getattr(ws_client_mod, "Client", None)
            if client_cls is not None and cls._orig_handle_message is not None:
                setattr(client_cls, "handle_message", cls._orig_handle_message)
        except Exception:
            pass
        finally:
            cls._patched = False
            cls._orig_handle_message = None

    def start(self) -> bool:
        if self._listener_id is not None:
            self.enabled = True
            return True
        ok = self._install_patch()
        if not ok:
            self.enabled = False
            self.source = "disabled"
            return False
        listener_id = WsWireTap._next_listener_id
        WsWireTap._next_listener_id += 1
        WsWireTap._listeners[listener_id] = self._on_frame
        self._listener_id = listener_id
        self.enabled = True
        self.source = "ccxt_ws_message_data"
        return True

    def stop(self) -> None:
        if self._listener_id is None:
            self.enabled = False
            return
        WsWireTap._listeners.pop(self._listener_id, None)
        self._listener_id = None
        self.enabled = False
        WsWireTap._uninstall_patch_if_idle()
