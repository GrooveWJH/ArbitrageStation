from __future__ import annotations

import asyncio

from lib.marketdata.config import build_arg_parser
from lib.marketdata.core.runner import run


def main() -> int:
    args = build_arg_parser().parse_args()
    return asyncio.run(run(args))
