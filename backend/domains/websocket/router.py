"""Domain router compatibility shim for `websocket`."""
from api.websocket import router, start_broadcast_loop, start_price_broadcast_loop

__all__ = ['router', 'start_broadcast_loop', 'start_price_broadcast_loop']
