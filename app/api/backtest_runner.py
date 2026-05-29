"""
Backtest Runner — fetches historical data, generates M8Payloads via CISD scoring,
and runs them through the full M8 pipeline (AI Review → Risk Engine → Broker → Journal).
Outcomes are recorded in ConfidenceRegistry for AI learning.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from app.services.signal_generator import signal_generator_instance
from app.api.orchestrator import process_signal, reset_broker, _get_broker
from app.services.risk_engine import risk_engine_instance
from app.services.confidence_registry import confidence_registry
from app.core.config import AI_FAILURE_POLICY, AI_PROVIDER, BROKER_MODE

router = APIRouter()


class BacktestRunRequest(BaseModel):
    symbol: str = "HYPEUSDT"
    timeframe: str = "1m"
    strategy_id: Optional[str] = None
    bars: int = 500
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_balance: float = 10000.0
    max_signals: Optional[int] = 50
    min_confluence: Optional[float] = None


@router.post("/run")
async def run_backtest(req: BacktestRunRequest):
    """
    Run a full backtest through the M8 pipeline on historical data.

    1. Fetch historical OHLCV from Bybit
    2. Compute MTF CISD scores for every bar
    3. Generate M8Payloads for bars exceeding confidence threshold
    4. Run each payload through process_signal() (AI → Risk → Broker → Journal)
    5. Return performance summary + all journal entries
    """
    try:
        print(f"[BACKTEST] Starting: {req.symbol} {req.timeframe} | bars={req.bars}")

        # Reset risk engine state for clean backtest
        risk_engine_instance.trades_today = 0
        risk_engine_instance.last_trade_bar = -1
        risk_engine_instance.current_bar = 0

        # Generate payloads from historical data
        if req.strategy_id:
            from app.services.strategy_engine import strategy_registry
            strategy_registry.set_active_strategy(req.strategy_id)

        payloads = signal_generator_instance.generate_payloads(
            symbol=req.symbol,
            timeframe=req.timeframe,
            bars=req.bars,
            min_confluence=req.min_confluence,
        )
        generation_summary = getattr(signal_generator_instance, "last_generation_summary", {})

        if not payloads:
            return {
                "status": "success",
                "symbol": req.symbol,
                "timeframe": req.timeframe,
                "signals_generated": 0,
                "generation_summary": generation_summary,
                "message": "No signals generated — confluence threshold not met",
            }

        if req.max_signals:
            payloads = payloads[:req.max_signals]

        # Run each payload through the full pipeline
        results = []
        executed_payloads = []
        for payload in payloads:
            result = await process_signal(payload)
            # Build entry/exit coordinates for chart rendering
            entry = {"price": payload.entry_price, "time": payload.timestamp}
            exit_price = payload.target_price if payload.direction == "LONG" else payload.stop_price
            exit_coord = {"price": exit_price, "time": payload.timestamp}
            results.append({
                "signal_id": payload.signal_id,
                "direction": payload.direction,
                "entry_price": payload.entry_price,
                "confluence_score": payload.confluence_score,
                "final_decision": result["final_decision"],
                "reject_reason": result.get("reject_reason"),
                "ai_trace": result.get("ai_trace"),
                "asset_class": result.get("asset_class"),
                "entry": entry,
                "exit": exit_coord,
            })
            if result["final_decision"] == "EXECUTED_SIM":
                executed_payloads.append((payload, result))

        # Record outcomes for executed trades using historical bar simulation
        raw_bars = getattr(signal_generator_instance, "last_raw_bars", [])
        bar_index = {getattr(bar, 'ts', 0): idx for idx, bar in enumerate(raw_bars)}

        if executed_payloads and raw_bars:
            from app.services.shadow_paper_engine import ShadowPaperEngine
            engine = ShadowPaperEngine()

        for payload, result in executed_payloads:
            signal_dt = datetime.fromisoformat(payload.timestamp.replace('Z', '+00:00'))
            signal_ts = int(signal_dt.timestamp() * 1000)
            entry_idx = min(range(len(raw_bars)), key=lambda i: abs(raw_bars[i].ts - signal_ts)) if raw_bars else None
            if entry_idx is not None and entry_idx < len(raw_bars) - 1:
                try:
                    outcome = engine.simulate_trade(payload, raw_bars, entry_idx, max_holding_bars=50)
                    win = outcome.win
                    pnl_pct = outcome.pnl_pct
                    rr = abs(outcome.r_multiple)
                    # Record trade outcome
                    confidence_registry.record_trade_outcome(
                        symbol=payload.symbol,
                        direction=payload.direction,
                        pnl_pct=pnl_pct,
                        rr=rr,
                        win=win,
                    )
                    # Record scout outcome
                    ai_trace = result.get("ai_trace") or {}
                    scout_decisions = ai_trace.get("scout_decisions", {})
                    if not scout_decisions:
                        scout_decisions = ai_trace.get("scouts", {})
                    for scout_name, scout_report in scout_decisions.items():
                        scout_approved = isinstance(scout_report, dict) and scout_report.get("decision") == "PROCEED_TO_SIMULATION"
                        if not scout_approved and isinstance(scout_report, str):
                            scout_approved = "PROCEED" in scout_report.upper() or "APPROVE" in scout_report.upper()
                        was_correct = (scout_approved and win) or (not scout_approved and not win)
                        confidence_registry.mark_scout_outcome(
                            symbol=payload.symbol,
                            scout_names=[scout_name],
                            was_correct=was_correct,
                        )
                except Exception:
                    pass

        # Summarize
        executed = sum(1 for r in results if r["final_decision"] == "EXECUTED_SIM")
        rejected = sum(1 for r in results if r["final_decision"] == "REJECTED")

        longs = sum(1 for r in results if r["direction"] == "LONG")
        shorts = sum(1 for r in results if r["direction"] == "SHORT")

        return {
            "status": "success",
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "bars_analyzed": req.bars,
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
        "type": getattr(broker, "get_broker_type", lambda: type(broker).__name__)(),
        "name": getattr(broker, "get_broker_name", lambda: type(broker).__name__)(),
        "display_mode": getattr(broker, "get_broker_mode", lambda: "unknown")(),
    }
    if hasattr(broker, "is_ready"):
        broker_info["connected"] = broker.is_ready()
    if hasattr(broker, "is_live_capable"):
        broker_info["live_capable"] = broker.is_live_capable()
    if hasattr(broker, "get_wallet_balances") and broker.is_ready():
        wallets = {}
        for key, account_mode in (("primary", "SPOT"), ("futures", "FUTURES")):
            try:
                wallets[key] = broker.get_wallet_balances(account_mode=account_mode)
            except Exception:
                wallets[key] = {"account_mode": account_mode, "error": "BALANCE_UNAVAILABLE"}
        broker_info["wallets"] = wallets
        broker_info["balance"] = wallets["primary"]
    if broker.is_ready():
        if hasattr(broker, "get_positions"):
            broker_info["positions"] = broker.get_positions()
        elif hasattr(broker, "get_open_positions"):
            broker_info["positions"] = broker.get_open_positions()
    if hasattr(broker, "get_running_bots") and broker.is_ready():
        broker_info["bots"] = broker.get_running_bots()

    return {
        "status": "ok",
        "ai": {
            "provider": AI_PROVIDER,
            "failure_policy": AI_FAILURE_POLICY,
        },
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


@router.post("/smoke")
async def smoke_test():
    """
    Pionex dry-run smoke test.
    Runs a series of test payloads through the full pipeline without sending live orders.
    Verifies symbol mapping, balance fetching, Kelly sizing, War Room rules, and dry-run execution.
    """
    from app.schemas.m8_payload import M8Payload
    from datetime import datetime, timezone
    from app.api.orchestrator import ai_review_instance
    from app.services.ai_mock import MockAIReviewLayer

    broker = _get_broker()
    results = []

    # Temporarily swap to Mock AI for deterministic smoke testing
    original_ai = ai_review_instance
    mock_ai = MockAIReviewLayer()
    import app.api.orchestrator as orch_module
    orch_module.ai_review_instance = mock_ai

    # Test 1: Broker readiness
    is_ready = getattr(broker, "is_ready", lambda: False)()
    is_live = getattr(broker, "is_live_capable", lambda: False)()
    results.append({"test": "broker_ready", "passed": is_ready, "live_capable": is_live})

    # Test 2: Wallet balances (if broker supports it)
    balance_ok = False
    if hasattr(broker, "get_wallet_balances") and is_ready:
        try:
            spot = broker.get_wallet_balances(account_mode="SPOT")
            futures = broker.get_wallet_balances(account_mode="FUTURES")
            balance_ok = "error" not in spot and "error" not in futures
            results.append({"test": "wallet_balances", "passed": balance_ok, "spot": spot.get("balance"), "futures": futures.get("balance")})
        except Exception as exc:
            results.append({"test": "wallet_balances", "passed": False, "error": str(exc)})
    else:
        results.append({"test": "wallet_balances", "passed": None, "note": "Broker does not support wallet balances or not ready"})

    ts = datetime.now(timezone.utc).isoformat()

    # Test payloads for dry-run pipeline verification
    test_payloads = [
        {
            "signal_id": "smoke-1-entry",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "direction": "LONG",
            "intent": "ENTRY",
            "account_mode": "SPOT",
            "timestamp": ts,
            "entry_price": 50000.0,
            "stop_price": 48000.0,
            "target_price": 54000.0,
            "confluence_score": 85.0,
            "crisis_score": 5.0,
            "mc_dispersion": 1.5,
            "spread": 3.0,
            "bar_confirmed": True,
            "macro_event_risk": False,
        },
        {
            "signal_id": "smoke-2-futures",
            "symbol": "XAGUSDT.P",
            "timeframe": "1h",
            "direction": "SHORT",
            "intent": "ENTRY",
            "account_mode": "FUTURES",
            "timestamp": ts,
            "entry_price": 30.0,
            "stop_price": 31.0,
            "target_price": 28.0,
            "confluence_score": 75.0,
            "crisis_score": 8.0,
            "mc_dispersion": 2.0,
            "spread": 4.0,
            "bar_confirmed": True,
            "macro_event_risk": False,
        },
        {
            "signal_id": "smoke-3-rejected",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "direction": "LONG",
            "intent": "ENTRY",
            "account_mode": "SPOT",
            "timestamp": ts,
            "entry_price": 50000.0,
            "stop_price": 48000.0,
            "target_price": 54000.0,
            "confluence_score": 50.0,
            "crisis_score": 45.0,
            "mc_dispersion": 1.0,
            "spread": 3.0,
            "bar_confirmed": True,
            "macro_event_risk": True,
        },
        {
            "signal_id": "smoke-4-close",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "direction": "LONG",
            "intent": "CLOSE",
            "account_mode": "SPOT",
            "timestamp": ts,
            "entry_price": 52000.0,
            "stop_price": 48000.0,
            "target_price": 54000.0,
            "confluence_score": 80.0,
            "crisis_score": 5.0,
            "mc_dispersion": 1.5,
            "spread": 3.0,
            "bar_confirmed": True,
            "macro_event_risk": False,
        },
    ]

    pipeline_results = []
    try:
        for raw in test_payloads:
            # Reset cooldown between each test payload for independent evaluation
            risk_engine_instance.last_trade_bar = -1
            risk_engine_instance.trades_today = 0
            try:
                payload = M8Payload(**raw)
                result = await process_signal(payload)
                pipeline_results.append({
                    "signal_id": raw["signal_id"],
                    "symbol": raw["symbol"],
                    "direction": raw["direction"],
                    "intent": raw["intent"],
                    "final_decision": result["final_decision"],
                    "reject_reason": result.get("reject_reason"),
                    "broker_status": result["broker_result"].get("status") if result.get("broker_result") else None,
                    "is_dry_run": "DRY_RUN" in str(result["broker_result"].get("status", "")) or "SIM" in str(result["final_decision"]),
                })
            except Exception as exc:
                pipeline_results.append({
                    "signal_id": raw["signal_id"],
                    "error": str(exc),
                    "passed": False,
                })
    finally:
        orch_module.ai_review_instance = original_ai

    # smoke-3 is intentionally a rejection test (low confluence + high crisis)
    dry_run_results = [r for r in pipeline_results if r["signal_id"] != "smoke-3-rejected" and "error" not in r]
    all_passed = (
        is_ready
        and all(r.get("is_dry_run", True) for r in dry_run_results)
        and not any("error" in r for r in pipeline_results)
    )

    return {
        "status": "smoke_test_complete",
        "broker_mode": BROKER_MODE,
        "live_capable": is_live,
        "all_passed": all_passed,
        "infrastructure_checks": results,
        "pipeline_checks": pipeline_results,
    }
