from . import _part1 as _p1
from . import _part2 as _p2
from . import _part3 as _p3
from . import _part4 as _p4

_PARTS = (_p1, _p2, _p3, _p4,)

def __getattr__(name: str):
    for _mod in _PARTS:
        if hasattr(_mod, name):
            return getattr(_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__() -> list[str]:
    names = set(globals().keys())
    for _mod in _PARTS:
        names.update(k for k in _mod.__dict__.keys() if not k.startswith("__"))
    return sorted(names)

__all__ = sorted({
    k
    for _mod in _PARTS
    for k in _mod.__dict__.keys()
    if not k.startswith("__")
})
