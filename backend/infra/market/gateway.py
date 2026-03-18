"""Market data gateway entry."""

from core import data_collector as _data_collector

__all__ = [n for n in dir(_data_collector) if not n.startswith("__")]


def __getattr__(name: str):
    return getattr(_data_collector, name)
