from . import _part1 as _p1
from . import _part2 as _p2
from . import _part3 as _p3
from . import _part4 as _p4
from . import _part5 as _p5
from . import _part6 as _p6
from . import _part7 as _p7
from . import _part8 as _p8
from . import _part9 as _p9
from . import _part10 as _p10
from . import _part11 as _p11
from . import _part12 as _p12
from . import _part13 as _p13
from . import _part14 as _p14
from . import _part15 as _p15

_PARTS = (_p1, _p2, _p3, _p4, _p5, _p6, _p7, _p8, _p9, _p10, _p11, _p12, _p13, _p14, _p15,)

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
