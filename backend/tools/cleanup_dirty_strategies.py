from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.database import FundingAssignment, Position, SessionLocal, Strategy, TradeLog


@dataclass
class DirtyStrategyCandidate:
    strategy_id: int
    close_reason: str
    created_at: datetime | None
    position_count: int
    trade_log_count: int
    funding_assignment_count: int


def _find_candidates(*, open_failed_only: bool) -> list[DirtyStrategyCandidate]:
    db = SessionLocal()
    try:
        out: list[DirtyStrategyCandidate] = []
        q = db.query(Strategy).filter(Strategy.status == "error").order_by(Strategy.id.asc())
        for s in q.all():
            reason = str(s.close_reason or "")
            if open_failed_only and "open failed" not in reason.lower():
                continue
            trade_log_count = int(db.query(TradeLog).filter(TradeLog.strategy_id == s.id).count())
            if trade_log_count > 0:
                continue
            funding_assignment_count = int(
                db.query(FundingAssignment).filter(FundingAssignment.strategy_id == s.id).count()
            )
            if funding_assignment_count > 0:
                continue
            position_count = int(db.query(Position).filter(Position.strategy_id == s.id).count())
            out.append(
                DirtyStrategyCandidate(
                    strategy_id=int(s.id),
                    close_reason=reason,
                    created_at=s.created_at,
                    position_count=position_count,
                    trade_log_count=trade_log_count,
                    funding_assignment_count=funding_assignment_count,
                )
            )
        return out
    finally:
        db.close()


def _apply_cleanup(strategy_ids: list[int]) -> dict:
    db = SessionLocal()
    try:
        if not strategy_ids:
            return {
                "deleted_positions": 0,
                "deleted_trade_logs": 0,
                "deleted_funding_assignments": 0,
                "deleted_strategies": 0,
            }

        deleted_funding_assignments = int(
            db.query(FundingAssignment)
            .filter(FundingAssignment.strategy_id.in_(strategy_ids))
            .delete(synchronize_session=False)
        )
        deleted_trade_logs = int(
            db.query(TradeLog)
            .filter(TradeLog.strategy_id.in_(strategy_ids))
            .delete(synchronize_session=False)
        )
        deleted_positions = int(
            db.query(Position)
            .filter(Position.strategy_id.in_(strategy_ids))
            .delete(synchronize_session=False)
        )
        deleted_strategies = int(
            db.query(Strategy)
            .filter(Strategy.id.in_(strategy_ids))
            .delete(synchronize_session=False)
        )
        db.commit()
        return {
            "deleted_positions": deleted_positions,
            "deleted_trade_logs": deleted_trade_logs,
            "deleted_funding_assignments": deleted_funding_assignments,
            "deleted_strategies": deleted_strategies,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Clean dirty strategy rows: status=error with no trade logs and no funding assignments. "
            "Default dry-run."
        )
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Apply deletion. Without this flag, only print candidates.",
    )
    p.add_argument(
        "--open-failed-only",
        action="store_true",
        help="Restrict to rows whose close_reason contains 'open failed'.",
    )
    args = p.parse_args()

    candidates = _find_candidates(open_failed_only=bool(args.open_failed_only))
    ids = [x.strategy_id for x in candidates]
    now = datetime.now(timezone.utc).isoformat()
    print(f"[{now}] dirty_strategy_candidates={len(candidates)}")
    if candidates:
        print("sample_strategy_ids=", ids[:30])
        reasons = {}
        for one in candidates:
            key = one.close_reason.strip() or "<empty>"
            reasons[key] = int(reasons.get(key, 0)) + 1
        print("top_reasons=", sorted(reasons.items(), key=lambda x: (-x[1], x[0]))[:10])

    if not args.apply:
        print("dry_run=True (use --apply to delete)")
        return

    result = _apply_cleanup(ids)
    print("apply=True")
    print(result)


if __name__ == "__main__":
    main()
