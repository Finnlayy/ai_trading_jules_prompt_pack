"""REST endpoints for SQL database insights and analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.repository import (
    TradeRepository,
    PositionRepository,
    PerformanceRepository,
    StrategyRotationRepository,
    NewsImpactRepository,
)
from app.db.models import Trade, Position

router = APIRouter()


@router.get("/trades")
def get_trades(
    symbol: str | None = Query(default=None),
    strategy_id: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Query trades with optional filters."""
    repo = TradeRepository(db)
    if symbol:
        trades = repo.get_by_symbol(symbol, limit=limit)
    elif strategy_id:
        trades = repo.get_by_strategy(strategy_id, limit=limit)
    else:
        trades = repo.get_recent(days=days, limit=limit)

    return {
        "trades": [
            {
                "trade_id": t.trade_id,
                "symbol": t.symbol,
                "direction": t.direction,
                "strategy_id": t.strategy_id,
                "timeframe": t.timeframe,
                "entry_price": t.entry_price,
                "final_decision": t.final_decision,
                "pnl": t.pnl,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in trades
        ],
        "count": len(trades),
    }


@router.get("/performance/symbol")
def get_symbol_performance(
    symbol: str = Query(...),
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Aggregated performance metrics for a single symbol."""
    repo = TradeRepository(db)
    summary = repo.get_performance_summary(symbol=symbol, days=days)
    return summary


@router.get("/performance/strategy")
def get_strategy_performance(
    strategy_id: str = Query(...),
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Aggregated performance metrics for a strategy."""
    repo = TradeRepository(db)
    summary = repo.get_performance_summary(symbol=None, days=days)
    # Filter by strategy in-memory for simplicity
    trades = repo.get_by_strategy(strategy_id, limit=1000)
    total = len(trades)
    if total == 0:
        return {"strategy_id": strategy_id, "total_trades": 0}
    winners = [t for t in trades if t.pnl is not None and t.pnl > 0]
    losers = [t for t in trades if t.pnl is not None and t.pnl < 0]
    total_pnl = sum(t.pnl for t in trades if t.pnl is not None)
    return {
        "strategy_id": strategy_id,
        "total_trades": total,
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "winrate_pct": round(len(winners) / total * 100, 2),
        "total_pnl": round(total_pnl, 4),
        "avg_pnl": round(total_pnl / total, 4),
    }


@router.get("/winrate")
def get_winrate(
    symbol: str = Query(...),
    timeframe: str = Query(default="1h"),
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Winrate for a specific symbol + timeframe combination."""
    repo = TradeRepository(db)
    return repo.get_winrate_by_symbol_and_timeframe(symbol, timeframe, days)


@router.get("/positions")
def get_db_positions(
    symbol: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Query positions from the database."""
    repo = PositionRepository(db)
    if symbol:
        positions = repo.get_by_symbol(symbol)
    else:
        positions = repo.get_open()

    return {
        "positions": [
            {
                "trade_id": p.trade_id,
                "symbol": p.symbol,
                "direction": p.direction,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "size": p.size,
                "unrealized_pnl": p.unrealized_pnl,
                "realized_pnl": p.realized_pnl,
                "is_open": p.is_open,
                "opened_at": p.opened_at.isoformat() if p.opened_at else None,
                "closed_at": p.closed_at.isoformat() if p.closed_at else None,
            }
            for p in positions
        ],
        "count": len(positions),
    }


@router.get("/rotations")
def get_rotations(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Recent strategy rotation events."""
    repo = StrategyRotationRepository(db)
    rotations = repo.get_recent(limit=limit)
    return {
        "rotations": [
            {
                "symbol": r.symbol,
                "old_strategy": r.old_strategy,
                "new_strategy": r.new_strategy,
                "regime": r.regime,
                "reason": r.reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rotations
        ],
        "count": len(rotations),
    }


@router.get("/news")
def get_db_news(
    symbol: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Scored news items stored in the database."""
    repo = NewsImpactRepository(db)
    if symbol:
        items = repo.get_by_symbol(symbol, limit=limit)
    else:
        items = repo.get_recent(limit=limit)

    return {
        "items": [
            {
                "symbol": n.symbol,
                "source": n.source,
                "title": n.title,
                "sentiment_polarity": n.sentiment_polarity,
                "urgency": n.urgency,
                "relevance": n.relevance,
                "composite_score": n.composite_score,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in items
        ],
        "count": len(items),
    }
