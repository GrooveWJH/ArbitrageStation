import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.database import SessionLocal, Position, Strategy


OPEN_STRATEGY_STATUSES = {"active"}


def _to_dict_position(p: Position) -> dict:
    return {
        "position_id": p.id,
        "strategy_id": p.strategy_id,
        "symbol": p.symbol,
        "side": p.side,
        "position_type": p.position_type,
        "size": p.size,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def build_report() -> dict:
    db = SessionLocal()
    try:
        strategies = db.query(Strategy).all()
        positions = db.query(Position).all()
        strategy_map = {s.id: s for s in strategies}

        open_positions = [p for p in positions if p.status == "open"]
        active_strategies = [s for s in strategies if s.status in OPEN_STRATEGY_STATUSES]

        mismatched_open_positions = []
        orphan_open_positions = []

        for p in open_positions:
            if not p.strategy_id:
                orphan_open_positions.append(_to_dict_position(p))
                continue
            s = strategy_map.get(p.strategy_id)
            if not s:
                orphan_open_positions.append(_to_dict_position(p))
                continue
            if s.status not in OPEN_STRATEGY_STATUSES:
                item = _to_dict_position(p)
                item["strategy_status"] = s.status
                item["strategy_name"] = s.name
                item["strategy_close_reason"] = s.close_reason
                mismatched_open_positions.append(item)

        active_without_open_positions = []
        for s in active_strategies:
            has_open = any(p.status == "open" and p.strategy_id == s.id for p in positions)
            if not has_open:
                active_without_open_positions.append(
                    {
                        "strategy_id": s.id,
                        "name": s.name,
                        "symbol": s.symbol,
                        "status": s.status,
                    }
                )

        strategy_status_counts = Counter(s.status for s in strategies)
        position_status_counts = Counter(p.status for p in positions)
        top_error_reasons = Counter(
            (s.close_reason or "").strip()
            for s in strategies
            if s.status == "error"
        ).most_common(15)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "strategies_total": len(strategies),
                "positions_total": len(positions),
                "open_positions_total": len(open_positions),
                "active_strategies_total": len(active_strategies),
                "mismatched_open_positions": len(mismatched_open_positions),
                "orphan_open_positions": len(orphan_open_positions),
                "active_without_open_positions": len(active_without_open_positions),
            },
            "strategy_status_counts": dict(strategy_status_counts),
            "position_status_counts": dict(position_status_counts),
            "top_error_reasons": [{"reason": r, "count": n} for r, n in top_error_reasons],
            "mismatched_open_positions": mismatched_open_positions,
            "orphan_open_positions": orphan_open_positions,
            "active_without_open_positions": active_without_open_positions,
        }
    finally:
        db.close()


def apply_activate_strategies(report: dict) -> dict:
    db = SessionLocal()
    touched = 0
    ids_to_activate = sorted(
        {
            item["strategy_id"]
            for item in report["mismatched_open_positions"]
            if item.get("strategy_id")
        }
    )
    try:
        for sid in ids_to_activate:
            s = db.query(Strategy).filter(Strategy.id == sid).first()
            if not s:
                continue
            if s.status not in OPEN_STRATEGY_STATUSES:
                s.status = "active"
                if s.closed_at is not None:
                    s.closed_at = None
                touched += 1
        db.commit()
        return {"mode": "activate_strategies", "updated_strategies": touched}
    finally:
        db.close()


def apply_mark_positions_error(report: dict) -> dict:
    db = SessionLocal()
    touched = 0
    target_ids = {
        item["position_id"] for item in report["mismatched_open_positions"]
    } | {item["position_id"] for item in report["orphan_open_positions"]}
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for pid in sorted(target_ids):
            p = db.query(Position).filter(Position.id == pid).first()
            if not p:
                continue
            if p.status == "open":
                p.status = "error"
                p.closed_at = now
                touched += 1
        db.commit()
        return {"mode": "mark_positions_error", "updated_positions": touched}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit strategy/position status consistency.")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write JSON report.",
    )
    parser.add_argument(
        "--apply",
        choices=["activate_strategies", "mark_positions_error"],
        default=None,
        help="Optional repair action. If omitted, dry-run only.",
    )
    args = parser.parse_args()

    report = build_report()
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(json.dumps(
        {
            "strategy_status_counts": report["strategy_status_counts"],
            "position_status_counts": report["position_status_counts"],
            "top_error_reasons": report["top_error_reasons"][:5],
        },
        ensure_ascii=False,
        indent=2,
    ))

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report_written={out}")

    if args.apply:
        if args.apply == "activate_strategies":
            result = apply_activate_strategies(report)
        else:
            result = apply_mark_positions_error(report)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
