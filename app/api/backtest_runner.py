"""
Backtest Runner — fetches historical data, generates M8Payloads via CISD scoring,
and runs them through the full M8 pipeline (AI Review → Risk Engine → Broker → Journal).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import List, Optional

from app.services.signal_generator import signal_generator_instance
from app.api.orchestrator import process_signal, reset_broker, _get_broker
from app.services.risk_engine import risk_engine_instance
from app.core.config import BROKER_MODE

router = APIRouter()


@router.post("/run")
async def run_backtest(
    symbol: str = "HYPEUSDT",
    timeframe: str = "1m",
    bars: int = 500,
    max_signals: Optional[int] = 50,
    min_confluence: Optional[float] = None,
):
    """
    Run a full backtest through the M8 pipeline on historical data.

    1. Fetch historical OHLCV from Bybit
    2. Compute MTF CISD scores for every bar
    3. Generate M8Payloads for bars exceeding confidence threshold
    4. Run each payload through process_signal() (AI → Risk → Broker → Journal)
    5. Return performance summary + all journal entries
    """
    try:
        print(f"[BACKTEST] Starting: {symbol} {timeframe} | bars={bars}")

        # Reset risk engine state for clean backtest
        risk_engine_instance.trades_today = 0
        risk_engine_instance.last_trade_bar = -1
        risk_engine_instance.current_bar = 0

        # Generate payloads from historical data
        payloads = signal_generator_instance.generate_payloads(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            min_confluence=min_confluence,
        )
        generation_summary = getattr(signal_generator_instance, "last_generation_summary", {})

        if not payloads:
            return {
                "status": "success",
                "symbol": symbol,
                "timeframe": timeframe,
                "signals_generated": 0,
                "generation_summary": generation_summary,
                "message": "No signals generated — confluence threshold not met",
            }

        if max_signals:
            payloads = payloads[:max_signals]

        # Run each payload through the full pipeline
        results = []
        for payload in payloads:
            result = await process_signal(payload)
            results.append({
                "signal_id": payload.signal_id,
                "direction": payload.direction,
                "entry_price": payload.entry_price,
                "confluence_score": payload.confluence_score,
                "final_decision": result["final_decision"],
                "reject_reason": result.get("reject_reason"),
                "asset_class": result.get("asset_class"),
            })

        # Summarize
        executed = sum(1 for r in results if r["final_decision"] == "EXECUTED_SIM")
        rejected = sum(1 for r in results if r["final_decision"] == "REJECTED")

        longs = sum(1 for r in results if r["direction"] == "LONG")
        shorts = sum(1 for r in results if r["direction"] == "SHORT")

        return {
            "status": "success",
            "symbol": symbol,
            "timeframe": timeframe,
            "bars_analyzed": bars,
            "signals_generated": len(payloads),
            "executed": executed,
            "rejected": rejected,
            "longs": longs,
            "shorts": shorts,
            "generation_summary": generation_summary,
            "results": results,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
async def backtest_status():
    """Quick status of the backtest runner."""
    broker = _get_broker()
    broker_info = {
        "mode": BROKER_MODE,
        "type": type(broker).__name__,
    }
    if hasattr(broker, "is_ready"):
        broker_info["connected"] = broker.is_ready()
    if hasattr(broker, "is_live_capable"):
        broker_info["live_capable"] = broker.is_live_capable()
    if hasattr(broker, "get_balance") and broker.is_ready():
        try:
            balance = broker.get_balance()
            broker_info["balance"] = balance
        except Exception:
            broker_info["balance"] = "error"

    return {
        "status": "ok",
        "broker": broker_info,
        "risk_engine_state": {
            "trades_today": risk_engine_instance.trades_today,
            "current_bar": risk_engine_instance.current_bar,
            "last_trade_bar": risk_engine_instance.last_trade_bar,
        }
    }


@router.post("/reset")
async def reset_backtest():
    """Reset risk engine and broker state for a clean run."""
    risk_engine_instance.trades_today = 0
    risk_engine_instance.last_trade_bar = -1
    risk_engine_instance.current_bar = 0
    reset_broker()
    return {"status": "reset", "message": "Risk engine and broker state cleared"}
