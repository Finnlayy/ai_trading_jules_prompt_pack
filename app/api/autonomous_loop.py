"""API endpoints for the Autonomous Trading Loop."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.autonomous_loop import (
    LoopControlRequest,
    LoopStatusResponse,
    WatchlistItemSchema,
    HealthSnapshotSchema,
    StrategyRotationLogSchema,
    LoopStatsResponse,
)
from app.services.autonomous_loop import autonomous_loop_instance
from app.services.watchlist_manager import WatchlistItem, watchlist_manager
from app.services.strategy_engine import strategy_registry

router = APIRouter()


@router.get("/status", response_model=LoopStatusResponse)
async def get_loop_status():
    """Return current status of the autonomous trading loop."""
    status = autonomous_loop_instance.get_status()
    health = status.get("health", {})
    return LoopStatusResponse(
        is_running=status["is_running"],
        active_symbols=status["active_symbols"],
        poll_interval_seconds=status["poll_interval_seconds"],
        loop_stats=status["loop_stats"],
        health=HealthSnapshotSchema(
            status=health.get("status", "unknown"),
            cycles_completed=health.get("cycles_completed", 0),
            signals_generated=health.get("signals_generated", 0),
            trades_executed=health.get("trades_executed", 0),
            errors_last_5min=health.get("errors_last_5min", 0),
            avg_cycle_time_ms=health.get("avg_cycle_time_ms", 0.0),
            next_poll=health.get("next_poll"),
            timestamp=health.get("timestamp"),
        ),
        current_strategy_id=status["current_strategy_id"],
    )


@router.post("/control")
async def control_loop(req: LoopControlRequest):
    """Start, stop, pause, or resume the autonomous loop."""
    try:
        if req.action == "start":
            autonomous_loop_instance.start()
        elif req.action == "stop":
            autonomous_loop_instance.stop()
        elif req.action == "pause":
            autonomous_loop_instance.pause()
        elif req.action == "resume":
            autonomous_loop_instance.resume()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")
    except RuntimeError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"success": True, "action": req.action, "status": autonomous_loop_instance.get_status()}


@router.get("/watchlist")
async def get_watchlist():
    """Return all watchlist items."""
    items = watchlist_manager.list_all()
    return {
        "items": [
            {
                "symbol": item.symbol,
                "timeframes": item.timeframes,
                "active": item.active,
                "strategy_id": item.strategy_id,
                "min_confluence": item.min_confluence,
                "max_position_size_usdt": item.max_position_size_usdt,
                "added_at": item.added_at,
            }
            for item in items
        ],
        "count": len(items),
    }


@router.post("/watchlist")
async def add_to_watchlist(req: WatchlistItemSchema):
    """Add a symbol to the watchlist."""
    item = WatchlistItem(
        symbol=req.symbol.upper(),
        timeframes=req.timeframes,
        active=req.active,
        strategy_id=req.strategy_id,
        min_confluence=req.min_confluence,
        max_position_size_usdt=req.max_position_size_usdt,
    )
    watchlist_manager.add(item)
    return {"success": True, "symbol": item.symbol}


@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    """Remove a symbol from the watchlist."""
    watchlist_manager.remove(symbol)
    return {"success": True, "symbol": symbol.upper()}


@router.patch("/watchlist/{symbol}")
async def update_watchlist_item(symbol: str, req: WatchlistItemSchema):
    """Update properties of a watchlist item."""
    updated = watchlist_manager.update(
        symbol,
        timeframes=req.timeframes,
        active=req.active,
        strategy_id=req.strategy_id,
        min_confluence=req.min_confluence,
        max_position_size_usdt=req.max_position_size_usdt,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not in watchlist")
    return {"success": True, "symbol": symbol.upper()}


@router.get("/stats")
async def get_loop_stats():
    """Return detailed loop statistics."""
    stats = autonomous_loop_instance._health.stats
    return LoopStatsResponse(
        cycles_completed=stats.cycles_completed,
        signals_generated=stats.signals_generated,
        trades_executed=stats.trades_executed,
        errors_last_5min=stats.errors_last_5min,
        error_history=stats.error_history,
        avg_cycle_time_ms=autonomous_loop_instance._health.get_avg_cycle_time_ms(),
    )


@router.get("/rotation-log")
async def get_rotation_log():
    """Return recent strategy rotation events."""
    logs = autonomous_loop_instance.get_rotation_log()
    return {"logs": logs, "count": len(logs)}
