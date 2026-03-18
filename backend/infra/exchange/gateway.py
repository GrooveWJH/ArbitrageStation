"""Exchange gateway entry."""

from core import exchange_manager as _exchange_manager

__all__ = [n for n in dir(_exchange_manager) if not n.startswith("__")]


def __getattr__(name: str):
    return getattr(_exchange_manager, name)
