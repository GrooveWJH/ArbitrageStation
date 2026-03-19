"""AI analyst domain routes."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai-analyst", tags=["ai-analyst"])

LOGS_DIR = Path(r"C:\Claudeworkplace\ai-trader\logs")
ARBITRAGE_DB = Path(__file__).resolve().parents[2] / "data" / "arbitrage.db"

ALLOWED_FIELDS = {
    "min_annualized_pct",
    "entry_minutes_before_funding",
    "max_entry_spread_pct",
    "spread_gain_exit_threshold_pct",
    "pre_settle_exit_threshold_pct",
    "switch_min_improvement_pct",
    "max_hold_cycles",
    "fixed_size_usd",
    "max_position_usd",
    "spread_entry_z",
    "spread_exit_z",
    "spread_stop_z_delta",
    "spread_position_pct",
    "spread_cooldown_mins",
    "min_rate_diff_pct",
    "funding_max_positions",
    "min_cross_volume_usd",
    "min_spot_volume_usd",
}


def _list_analysis_files() -> list[Path]:
    if not LOGS_DIR.exists():
        return []
    return sorted(LOGS_DIR.glob("analysis_*.json"), reverse=True)


def _read_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _file_summary(path: Path, data: dict) -> dict:
    return {
        "filename": path.name,
        "timestamp": data.get("timestamp"),
        "strategies_analyzed": data.get("strategies_analyzed", 0),
        "has_adjustments": bool(data.get("adjustments")),
        "applied": data.get("applied", False),
        "reasoning": data.get("reasoning", ""),
    }


def _get_current_config() -> dict:
    if not ARBITRAGE_DB.exists():
        return {}
    try:
        conn = sqlite3.connect(str(ARBITRAGE_DB))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM auto_trade_config LIMIT 1").fetchone()
        conn.close()
        if not row:
            return {}
        return {f: row[f] for f in ALLOWED_FIELDS if f in row.keys()}
    except Exception:
        return {}


def _update_file(filename: str, patch: dict):
    target = LOGS_DIR / filename
    if not target.exists():
        return
    data = _read_file(target)
    data.update(patch)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


@router.get("/latest")
def get_latest():
    files = _list_analysis_files()
    if not files:
        return {"data": None}
    latest_file = files[0]
    data = _read_file(latest_file)
    return {
        "data": {
            "filename": latest_file.name,
            "timestamp": data.get("timestamp"),
            "strategies_analyzed": data.get("strategies_analyzed", 0),
            "response": data.get("response", ""),
            "adjustments": data.get("adjustments", {}),
            "reasoning": data.get("reasoning", ""),
            "applied": data.get("applied", False),
            "applied_fields": data.get("applied_fields", []),
            "rejected_fields": data.get("rejected_fields", []),
            "current_config": _get_current_config(),
            "total_history": len(files),
        }
    }


@router.get("/history")
def get_history(limit: int = 20):
    files = _list_analysis_files()[:limit]
    return {"data": [_file_summary(f, _read_file(f)) for f in files]}


class ApplyRequest(BaseModel):
    adjustments: Dict[str, Any]
    filename: Optional[str] = None


class RejectRequest(BaseModel):
    field: str
    filename: Optional[str] = None


@router.post("/apply")
def apply_adjustments(req: ApplyRequest):
    safe = {k: v for k, v in req.adjustments.items() if k in ALLOWED_FIELDS}
    if not safe:
        raise HTTPException(status_code=400, detail="没有合法的参数字段可应用")
    if not ARBITRAGE_DB.exists():
        raise HTTPException(status_code=503, detail="arbitrage-tool 数据库不存在")
    try:
        conn = sqlite3.connect(str(ARBITRAGE_DB))
        sets = ", ".join(f"{k} = ?" for k in safe)
        conn.execute(f"UPDATE auto_trade_config SET {sets}", list(safe.values()))
        conn.commit()
        conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if req.filename:
        data = _read_file(LOGS_DIR / req.filename) if (LOGS_DIR / req.filename).exists() else {}
        applied = set(data.get("applied_fields", []))
        applied.update(safe.keys())
        all_keys = set(data.get("adjustments", {}).keys())
        rejected = set(data.get("rejected_fields", []))
        _update_file(
            req.filename,
            {"applied_fields": list(applied), "applied": (applied | rejected) >= all_keys},
        )

    return {"success": True, "applied_fields": safe}


@router.post("/reject")
def reject_adjustment(req: RejectRequest):
    if req.field not in ALLOWED_FIELDS:
        raise HTTPException(status_code=400, detail="不支持的参数字段")
    if req.filename:
        data = _read_file(LOGS_DIR / req.filename) if (LOGS_DIR / req.filename).exists() else {}
        rejected = set(data.get("rejected_fields", []))
        rejected.add(req.field)
        all_keys = set(data.get("adjustments", {}).keys())
        applied = set(data.get("applied_fields", []))
        _update_file(
            req.filename,
            {"rejected_fields": list(rejected), "applied": (applied | rejected) >= all_keys},
        )
    return {"success": True, "rejected_field": req.field}


__all__ = ["router"]
