"""
Repository layer — CRUD operations for all SQLAlchemy models.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Trade, Position, PerformanceSnapshot, StrategyRotation, NewsImpact


# ---------------------------------------------------------------------------
# Trade Repository
# ---------------------------------------------------------------------------

class TradeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> Trade:
        trade = Trade(**kwargs)
        self.db.add(trade)
        self.db.commit()
        self.db.refresh(trade)
        return trade

    def get_by_trade_id(self, trade_id: str) -> Trade | None:
        return self.db.query(Trade).filter(Trade.trade_id == trade_id).first()

    def get_by_symbol(self, symbol: str, limit: int = 100) -> List[Trade]:
        return (
            self.db.query(Trade)
            .filter(Trade.symbol == symbol.upper())
            .order_by(Trade.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_by_strategy(self, strategy_id: str, limit: int = 100) -> List[Trade]:
        return (
            self.db.query(Trade)
            .filter(Trade.strategy_id == strategy_id)
            .order_by(Trade.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_recent(self, days: int = 30, limit: int = 1000) -> List[Trade]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return (
            self.db.query(Trade)
            .filter(Trade.created_at >= since)
            .order_by(Trade.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_performance_summary(self, symbol: str | None = None, days: int = 30) -> dict:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        query = self.db.query(Trade).filter(Trade.created_at >= since)
        if symbol:
            query = query.filter(Trade.symbol == symbol.upper())

        trades = query.all()
        total = len(trades)
        if total == 0:
            return {"total_trades": 0}

        winners = [t for t in trades if t.pnl is not None and t.pnl > 0]
        losers = [t for t in trades if t.pnl is not None and t.pnl < 0]
        total_pnl = sum(t.pnl for t in trades if t.pnl is not None)

        return {
            "total_trades": total,
            "winning_trades": len(winners),
            "losing_trades": len(losers),
            "winrate_pct": round(len(winners) / total * 100, 2) if total > 0 else 0.0,
            "total_pnl": round(total_pnl, 4),
            "avg_pnl": round(total_pnl / total, 4) if total > 0 else 0.0,
            "symbol": symbol,
            "days": days,
        }

    def get_winrate_by_symbol_and_timeframe(self, symbol: str, timeframe: str, days: int = 30) -> dict:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        trades = (
            self.db.query(Trade)
            .filter(Trade.symbol == symbol.upper())
            .filter(Trade.timeframe == timeframe)
            .filter(Trade.created_at >= since)
            .all()
        )
        total = len(trades)
        if total == 0:
            return {"symbol": symbol, "timeframe": timeframe, "winrate_pct": 0.0, "total_trades": 0}
        winners = sum(1 for t in trades if t.pnl is not None and t.pnl > 0)
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "winrate_pct": round(winners / total * 100, 2),
            "total_trades": total,
        }


# ---------------------------------------------------------------------------
# Position Repository
# ---------------------------------------------------------------------------

class PositionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> Position:
        pos = Position(**kwargs)
        self.db.add(pos)
        self.db.commit()
        self.db.refresh(pos)
        return pos

    def get_open(self) -> List[Position]:
        return self.db.query(Position).filter(Position.is_open == True).all()

    def get_by_trade_id(self, trade_id: str) -> Position | None:
        return self.db.query(Position).filter(Position.trade_id == trade_id).first()

    def get_by_symbol(self, symbol: str) -> List[Position]:
        return (
            self.db.query(Position)
            .filter(Position.symbol == symbol.upper())
            .all()
        )

    def update_price(self, trade_id: str, current_price: float, unrealized_pnl: float) -> None:
        pos = self.get_by_trade_id(trade_id)
        if pos:
            pos.current_price = current_price
            pos.unrealized_pnl = unrealized_pnl
            self.db.commit()

    def close(self, trade_id: str, exit_price: float, realized_pnl: float) -> None:
        pos = self.get_by_trade_id(trade_id)
        if pos:
            pos.is_open = False
            pos.current_price = exit_price
            pos.realized_pnl = realized_pnl
            pos.closed_at = datetime.now(timezone.utc)
            self.db.commit()


# ---------------------------------------------------------------------------
# Performance Repository
# ---------------------------------------------------------------------------

class PerformanceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_snapshot(self, **kwargs) -> PerformanceSnapshot:
        snap = PerformanceSnapshot(**kwargs)
        self.db.add(snap)
        self.db.commit()
        self.db.refresh(snap)
        return snap

    def get_latest(self) -> PerformanceSnapshot | None:
        return (
            self.db.query(PerformanceSnapshot)
            .order_by(PerformanceSnapshot.captured_at.desc())
            .first()
        )

    def get_history(self, limit: int = 100) -> List[PerformanceSnapshot]:
        return (
            self.db.query(PerformanceSnapshot)
            .order_by(PerformanceSnapshot.captured_at.desc())
            .limit(limit)
            .all()
        )


# ---------------------------------------------------------------------------
# Strategy Rotation Repository
# ---------------------------------------------------------------------------

class StrategyRotationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> StrategyRotation:
        rot = StrategyRotation(**kwargs)
        self.db.add(rot)
        self.db.commit()
        self.db.refresh(rot)
        return rot

    def get_recent(self, limit: int = 50) -> List[StrategyRotation]:
        return (
            self.db.query(StrategyRotation)
            .order_by(StrategyRotation.created_at.desc())
            .limit(limit)
            .all()
        )


# ---------------------------------------------------------------------------
# News Impact Repository
# ---------------------------------------------------------------------------

class NewsImpactRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> NewsImpact:
        item = NewsImpact(**kwargs)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_by_symbol(self, symbol: str, limit: int = 50) -> List[NewsImpact]:
        return (
            self.db.query(NewsImpact)
            .filter(NewsImpact.symbol == symbol.upper())
            .order_by(NewsImpact.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_recent(self, limit: int = 100) -> List[NewsImpact]:
        return (
            self.db.query(NewsImpact)
            .order_by(NewsImpact.created_at.desc())
            .limit(limit)
            .all()
        )
