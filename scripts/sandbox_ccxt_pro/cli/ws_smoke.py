#!/usr/bin/env python3
"""Typer entrypoint for sandbox CCXT Pro smoke app."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.marketdata.main import main as legacy_main  # noqa: E402

app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(ctx: typer.Context) -> None:
    """Run WS smoke app and forward all extra args to legacy parser."""
    argv_backup = list(sys.argv)
    try:
        sys.argv = [argv_backup[0], *ctx.args]
        raise typer.Exit(legacy_main())
    finally:
        sys.argv = argv_backup


if __name__ == "__main__":
    app()
