from __future__ import annotations

import json


def estimate_payload_bytes(payload: object) -> int:
    try:
        return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except Exception:
        return len(str(payload).encode("utf-8"))

