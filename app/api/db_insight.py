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
    symbol: str | None = Query(default=None, pattern=r"^[A-Za-z0-9_\-\.]+$"),
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
    symbol: str = Query(..., pattern=r"^[A-Za-z0-9_\-\.]+$"),
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
    symbol: str = Query(..., pattern=r"^[A-Za-z0-9_\-\.]+$"),
    timeframe: str = Query(default="1h"),
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Winrate for a specific symbol + timeframe combination."""
    repo = TradeRepository(db)
    return repo.get_winrate_by_symbol_and_timeframe(symbol, timeframe, days)


@router.get("/positions")
def get_db_positions(
    symbol: str | None = Query(default=None, pattern=r"^[A-Za-z0-9_\-\.]+$"),
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
    symbol: str | None = Query(default=None, pattern=r"^[A-Za-z0-9_\-\.]+$"),
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


@router.get("/second-brain")
def get_second_brain():
    """Fetch compiled Project Wiki & Second Brain content."""
    from app.services.wiki_service import SECOND_BRAIN_FILE, update_second_brain
    
    # Refresh stats on access
    try:
        update_second_brain()
    except Exception:
        pass

    if not SECOND_BRAIN_FILE.exists():
        content = "# Project Wiki & Second Brain\n\nNo compiled entry found yet. Perform some trades or run training drills to populate memory."
    else:
        try:
            content = SECOND_BRAIN_FILE.read_text(encoding="utf-8")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not read second brain file: {exc}")

    # Build the list of documents dynamically
    from pathlib import Path
    from datetime import datetime, timezone
    docs = []
    try:
        for p in sorted(Path(".").glob("*.md")):
            if p.is_file():
                stat = p.stat()
                modified_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                docs.append({
                    "name": p.name,
                    "size_bytes": stat.st_size,
                    "modified": modified_time
                })
    except Exception:
        pass

    return {
        "content": content,
        "docs": docs
    }


@router.get("/second-brain/doc/{filename}")
def get_second_brain_doc(filename: str):
    """Fetch raw text content of a specified project document file from root."""
    from pathlib import Path

    if not filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Invalid filename parameter")

    base_dir = Path(".").resolve()
    try:
        doc_path = (base_dir / filename).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid filename parameter")

    if doc_path.parent != base_dir:
        raise HTTPException(status_code=400, detail="Invalid filename parameter")
    
    if not doc_path.exists() or not doc_path.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
        
    try:
        content = doc_path.read_text(encoding="utf-8")
        return {"filename": filename, "content": content}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read document file: {exc}")


@router.post("/second-brain/compress")
async def trigger_second_brain_compression():
    """Trigger the BrainCompressor to scan, format, and summarize all chats and plans."""
    from app.services.brain_compressor import BrainCompressor
    try:
        compressor = BrainCompressor()
        index_path = await compressor.run_sync_and_compile()
        return {
            "status": "success",
            "message": "Second brain compression and summarization completed successfully.",
            "index_file": str(index_path)
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error running compression: {exc}")


@router.get("/second-brain/summaries")
def get_second_brain_summaries():
    """Fetch compiled consolidated summaries index content."""
    from pathlib import Path
    summaries_file = Path("wiki/second_brain_summaries.md")
    if not summaries_file.exists():
        raise HTTPException(status_code=404, detail="Summaries index not compiled yet. Call POST /api/db/second-brain/compress first.")
        
    try:
        content = summaries_file.read_text(encoding="utf-8")
        return {
            "filename": "second_brain_summaries.md",
            "content": content
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read summaries file: {exc}")

