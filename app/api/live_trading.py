"""API endpoints for live paper trading monitoring and control."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.schemas.live_trading import (
    EmergencyStopRequest,
    EmergencyStopResponse,
    LiveTradingStatus,
    ManualOrderRequest,
    PerformanceMetricsSchema,
    PerformanceResponse,
    PositionResponse,
)
from app.schemas.m8_payload import M8Payload
from app.api.orchestrator import process_manual_signal
from app.core.config import BROKER_MODE
from app.services.live_fill_tracker import live_fill_tracker
from app.services.performance_calculator import performance_calculator
from app.services.dashboard_sse import dashboard_sse_manager
from app.services.autonomous_loop import autonomous_loop_instance
from app.services.portfolio_circuit_breaker import circuit_breaker_instance
from app.services.journal_logger import journal_logger_instance

router = APIRouter()

LIVE_ACTIVE_MODES = {"paper", "ctrader", "ctrader_direct"}


# In-memory emergency state
_emergency_halt_until: datetime | None = None


def _is_emergency_active() -> bool:
    global _emergency_halt_until
    if _emergency_halt_until is None:
        return False
    if datetime.now(timezone.utc) >= _emergency_halt_until:
        _emergency_halt_until = None
        return False
    return True


def _local_position_response(p) -> PositionResponse:
    return PositionResponse(
        trade_id=p.trade_id,
        symbol=p.symbol,
        direction=p.direction,
        entry_price=p.entry_price,
        current_price=p.current_price,
        size=p.size,
        unrealized_pnl=round(p.unrealized_pnl, 4),
        unrealized_pnl_pct=round(
            (p.unrealized_pnl / (p.entry_price * p.size)) * 100 if p.entry_price * p.size != 0 else 0, 2
        ),
        open_time=p.open_time,
        strategy_id=p.strategy_id,
        stop_price=p.stop_price,
        target_price=p.target_price,
        time_in_trade_minutes=round(p.time_in_trade_minutes, 2),
    )


async def _broker_positions_for_live_mode() -> list[PositionResponse] | None:
    if BROKER_MODE not in {"ctrader", "ctrader_direct"}:
        return None
    try:
        from app.api import orchestrator

        broker = orchestrator.broker_instance
        if getattr(broker, "get_broker_type", lambda: "")() != "ctrader":
            return None
        result = await asyncio.to_thread(broker.get_positions)
        if result.get("error"):
            return None
        return [PositionResponse(**position) for position in result.get("positions", [])]
    except Exception:
        return None


@router.get("/status", response_model=LiveTradingStatus)
async def get_live_status():
    """Return live trading system status."""
    broker_positions = await _broker_positions_for_live_mode()
    if broker_positions is None:
        positions = [_local_position_response(p) for p in live_fill_tracker.get_open_positions()]
    else:
        positions = broker_positions
    total_exposure = sum(p.size * p.current_price for p in positions)
    today_pnl = live_fill_tracker.get_daily_pnl()

    cb = circuit_breaker_instance.check_trade_allowed()
    loop_status = autonomous_loop_instance.get_status()

    return LiveTradingStatus(
        is_active=BROKER_MODE in LIVE_ACTIVE_MODES,
        broker_mode=BROKER_MODE,
        loop_running=loop_status["is_running"],
        open_positions_count=len(positions),
        total_exposure_usdt=round(total_exposure, 2),
        today_pnl=round(today_pnl, 4),
        today_trades=loop_status["loop_stats"]["trades_executed"],
        circuit_breaker_tripped=not cb["trade_allowed"],
        last_trade_at=None,
        uptime_seconds=0.0,
    )


@router.get("/positions")
async def get_open_positions():
    """Return all currently open positions."""
    broker_positions = await _broker_positions_for_live_mode()
    if broker_positions is not None:
        return broker_positions
    return [_local_position_response(p) for p in live_fill_tracker.get_open_positions()]


@router.get("/positions/{trade_id}")
async def get_single_position(trade_id: str):
    """Return a single position by trade ID."""
    p = live_fill_tracker.get_position(trade_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return PositionResponse(
        trade_id=p.trade_id,
        symbol=p.symbol,
        direction=p.direction,
        entry_price=p.entry_price,
        current_price=p.current_price,
        size=p.size,
        unrealized_pnl=round(p.unrealized_pnl, 4),
        unrealized_pnl_pct=round(
            (p.unrealized_pnl / (p.entry_price * p.size)) * 100 if p.entry_price * p.size != 0 else 0, 2
        ),
        open_time=p.open_time,
        strategy_id=p.strategy_id,
        stop_price=p.stop_price,
        target_price=p.target_price,
        time_in_trade_minutes=round(p.time_in_trade_minutes, 2),
    )


@router.post("/positions/{trade_id}/close")
async def close_position(trade_id: str):
    """Manually close an open position."""
    p = live_fill_tracker.get_position(trade_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Position not found")
    live_fill_tracker.record_exit(trade_id, p.current_price)
    return {"success": True, "trade_id": trade_id, "closed_at": datetime.now(timezone.utc).isoformat()}


@router.get("/performance")
async def get_performance(lookback_days: int = 30):
    """Return performance metrics for completed trades."""
    entries = journal_logger_instance.get_entries(limit=1000)
    metrics = performance_calculator.calculate_metrics(entries)
    return PerformanceResponse(
        metrics=PerformanceMetricsSchema(
            total_trades=metrics.total_trades,
            winning_trades=metrics.winning_trades,
            losing_trades=metrics.losing_trades,
            winrate_pct=metrics.winrate_pct,
            profit_factor=metrics.profit_factor,
            expectancy=metrics.expectancy,
            sharpe_ratio=metrics.sharpe_ratio,
            sortino_ratio=metrics.sortino_ratio,
            max_drawdown_pct=metrics.max_drawdown_pct,
            max_drawdown_start_idx=metrics.max_drawdown_start_idx,
            max_drawdown_end_idx=metrics.max_drawdown_end_idx,
            total_pnl=metrics.total_pnl,
            avg_trade_pnl=metrics.avg_trade_pnl,
            avg_winner=metrics.avg_winner,
            avg_loser=metrics.avg_loser,
            largest_winner=metrics.largest_winner,
            largest_loser=metrics.largest_loser,
            avg_holding_time_minutes=metrics.avg_holding_time_minutes,
            calculated_at=metrics.calculated_at,
        ),
        lookback_days=lookback_days,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/equity-curve")
async def get_equity_curve(days: int = 30):
    """Return equity curve data for charting."""
    entries = journal_logger_instance.get_entries(limit=1000)
    curve = performance_calculator.calculate_equity_curve_data(entries)
    return {"curve": curve, "days": days}


@router.get("/trades")
async def get_trades(limit: int = 50, offset: int = 0):
    """Return recent completed trades from the journal."""
    entries = journal_logger_instance.get_entries(limit=limit + offset)
    trades = entries[offset:offset + limit]

    def _fmt_ts(ts: str) -> str:
        """Format ISO timestamp to dd:mm:yy : hh:mm"""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%d:%m:%y : %H:%M")
        except Exception:
            return ts

    return {
        "trades": [
            {
                "trade_id": t.get("trade_id") if isinstance(t, dict) else getattr(t, "trade_id", None),
                "symbol": t.get("symbol") if isinstance(t, dict) else getattr(t, "symbol", None),
                "direction": t.get("direction") if isinstance(t, dict) else getattr(t, "direction", None),
                "decision": (t.get("final_decision") if isinstance(t, dict) else getattr(t, "final_decision", None)),
                "result": t.get("result") if isinstance(t, dict) else getattr(t, "result", None),
                "timestamp": _fmt_ts(t.get("timestamp") if isinstance(t, dict) else getattr(t, "timestamp", "")),
                "execution_mode": (t.get("simulated_fill", {}).get("mode")
                                   if isinstance(t, dict)
                                   else getattr(getattr(t, "simulated_fill", None), "get", lambda k: None)("mode")),
                "entry_price": t.get("entry_price") if isinstance(t, dict) else getattr(t, "entry_price", None),
                "exit_price": (t.get("result", {}).get("exit_price")
                               if isinstance(t, dict)
                               else (getattr(t, "result", {}) or {}).get("exit_price")),
                "pnl": (t.get("result", {}).get("pnl")
                        if isinstance(t, dict)
                        else (getattr(t, "result", {}) or {}).get("pnl")),
            }
            for t in trades
        ],
        "total": len(entries),
        "limit": limit,
        "offset": offset,
    }


@router.get("/stream")
async def live_stream(request: Request):
    """SSE endpoint for real-time trade, position, and metrics updates."""
    client_id = str(uuid.uuid4())

    async def event_generator():
        try:
            async for event_str in dashboard_sse_manager.connect(client_id):
                yield event_str
        finally:
            dashboard_sse_manager.disconnect(client_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/manual/order")
async def manual_order(req: ManualOrderRequest):
    """Direct manual order — bypasses AI review, keeps risk gates."""
    payload = M8Payload(
        signal_id=f"manual-{uuid.uuid4().hex[:12]}",
        symbol=req.symbol.upper(),
        timeframe="1h",
        direction=req.direction,
        intent=req.intent,
        account_mode=req.account_mode,
        timestamp=datetime.now(timezone.utc).isoformat(),
        entry_price=req.entry_price or 0.0,
        stop_price=req.stop_price or 0.0,
        target_price=req.target_price or 0.0,
        confluence_score=50.0,
        crisis_score=10.0,
        mc_dispersion=1.0,
        spread=1.0,
        leverage=req.leverage,
        execution_quantity=req.quantity,
        order_command=req.order_command,
    )
    result = await process_manual_signal(payload)
    return result


@router.post("/emergency-stop", response_model=EmergencyStopResponse)
async def emergency_stop(req: EmergencyStopRequest):
    """Emergency halt all new entries and optionally close open positions."""
    global _emergency_halt_until
    halted_until = datetime.now(timezone.utc) + timedelta(minutes=req.halt_duration_minutes)
    _emergency_halt_until = halted_until

    positions_closed = 0
    if req.close_open_positions:
        for p in live_fill_tracker.get_open_positions():
            live_fill_tracker.record_exit(p.trade_id, p.current_price)
            positions_closed += 1

    autonomous_loop_instance.pause()
    dashboard_sse_manager.broadcast_alert(
        f"🚨 EMERGENCY STOP: {req.reason}", level="critical"
    )

    return EmergencyStopResponse(
        success=True,
        reason=req.reason,
        positions_closed=positions_closed,
        halted_until=halted_until,
    )
