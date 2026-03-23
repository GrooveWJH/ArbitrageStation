from __future__ import annotations

from pathlib import Path

from lib.common.io_utils import read_json_file


def load_intersection_symbols(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"symbols file not found: {path}")

    payload = read_json_file(path)
    data = payload.get("report") if isinstance(payload, dict) and isinstance(payload.get("report"), dict) else payload
    symbols = data.get("intersection_symbols") if isinstance(data, dict) else None

    if not isinstance(symbols, list):
        raise ValueError("invalid symbols file: missing intersection_symbols list")

    out = [str(s).strip().upper() for s in symbols if str(s).strip()]
    if not out:
        raise ValueError("intersection_symbols is empty")
    return out

