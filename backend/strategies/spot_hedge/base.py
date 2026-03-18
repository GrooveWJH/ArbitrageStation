from __future__ import annotations

from models.database import Position


class SpotHedgeBase:
    def _remaining_open_positions(self, strategy_id: int) -> int:
        return int(
            self.db.query(Position)
            .filter(
                Position.strategy_id == strategy_id,
                Position.status == "open",
            )
            .count()
        )
