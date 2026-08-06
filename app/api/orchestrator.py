import asyncio
import inspect
from datetime import datetime, timezone

from app.schemas.m8_payload import M8Payload
from app.services.risk_engine import risk_engine_instance
from app.services.ai_factory import ai_review_instance
from app.services.broker_factory import BrokerFactory
from app.services.journal_logger import journal_logger_instance
from app.services.regime_engine import regime_engine_instance
from app.services.confidence_registry import confidence_registry
from app.services.signal_generator import BybitDataFeed
from app.schemas.journal import DecisionEnum, FinalDecisionEnum
from app.schemas.ai_review import SignalReview
from app.core.config import AI_FAILURE_POLICY, BROKER_MODE, PAPER_TRADING_RELAX_RISK


def _build_broker():
    """Build broker via factory for clean single-mode selection."""
    return BrokerFactory.create(mode=BROKER_MODE, journal_path=journal_logger_instance.filepath)


# Single broker instance for the MVP
broker_instance = _build_broker()


def _get_broker():
    return broker_instance


def reset_broker():
    global broker_instance
    broker_instance = _build_broker()
    return broker_instance


def _is_ai_provider_unavailable(ai_review) -> bool:
    risk_flags = [str(flag).upper() for flag in (ai_review.risk_flags or [])]
    return any("UNAVAILABLE" in flag for flag in risk_flags)


def _is_live_capable_broker(broker) -> bool:
    if hasattr(broker, "is_live_capable"):
        try:
            return bool(broker.is_live_capable())
        except Exception:
            return False
    # Legacy fallback for older broker classes
    if BROKER_MODE in {"pionex_relay", "relay", "pionex"} and hasattr(broker, "is_ready"):
        try:
            return bool(broker.is_ready())
        except Exception:
            return False
    return False


def _should_execute_broker_in_thread(broker) -> bool:
    broker_type = getattr(broker, "get_broker_type", lambda: "")()
    return broker_type == "ctrader"




def _check_emergency_halt(payload):
    from app.api.live_trading import _is_emergency_active
    from app.schemas.journal import FinalDecisionEnum
    if _is_emergency_active():
        return {
            "signal_id": payload.signal_id,
            "trade_id": f"emergency-{payload.signal_id}",
            "final_decision": FinalDecisionEnum.REJECTED,
            "ai_decision": None,
            "ai_trace": None,
            "regime": None,
            "reject_reason": "EMERGENCY_HALT",
            "broker_result": None,
            "simulated_fill": None,
            "execution_mode": "simulation",
        }
    return None

async def _execute_trade_with_broker(payload, decision_result, ai_decision):
    execute_kwargs = {
        "payload": payload,
        "decision": decision_result["decision"],
        "reject_reason": decision_result["reject_reason"],
        "ai_decision": ai_decision,
    }
    if _should_execute_broker_in_thread(broker_instance):
        journal_entry = await asyncio.to_thread(broker_instance.execute_trade, **execute_kwargs)
    else:
        journal_entry = broker_instance.execute_trade(**execute_kwargs)
    return journal_entry

def _record_trade_fill(payload, decision_result, journal_entry):
    from app.schemas.journal import DecisionEnum
    if decision_result["decision"] == DecisionEnum.PROCEED_TO_SIMULATION and journal_entry.simulated_fill:
        fill = journal_entry.simulated_fill
        size = 0.0
        if "size_base" in fill:
             size = fill.get("size_base", 0.0)
        elif journal_entry.result and journal_entry.result.get("ledger_delta") and "size_base" in journal_entry.result.get("ledger_delta"):
             size = journal_entry.result["ledger_delta"].get("size_base", 0.0)
        elif journal_entry.result and "size_base" in journal_entry.result:
             size = journal_entry.result.get("size_base", 0.0)
        else:
             size = fill.get("size", 0.0)

        if payload.intent == "ENTRY":
            from app.services.live_fill_tracker import live_fill_tracker, FillData
            from datetime import datetime, timezone
            live_fill_tracker.record_fill(
                journal_entry.trade_id,
                FillData(
                    entry_price=fill.get("fill_price", payload.entry_price),
                    fill_time=datetime.now(timezone.utc),
                    size=size,
                    side=payload.direction,
                    fees=fill.get("fees", 0.0),
                    slippage=fill.get("slippage", 0.0),
                ),
            )
        else:
             pass

        from app.services.dashboard_sse import dashboard_sse_manager
        dashboard_sse_manager.broadcast_trade_update({
            "trade_id": journal_entry.trade_id,
            "symbol": payload.symbol,
            "direction": payload.direction,
            "entry_price": payload.entry_price,
            "status": "filled",
        })

def _update_risk_engine_post_trade(decision_result):
    from app.schemas.journal import DecisionEnum
    if decision_result["decision"] == DecisionEnum.PROCEED_TO_SIMULATION:
        risk_engine_instance.last_trade_bar = risk_engine_instance.current_bar
        risk_engine_instance.trades_today += 1

def _get_execution_mode():
    execution_mode = "simulation"
    if broker_instance.get_broker_type() == "pionex_direct":
        execution_mode = "live" if getattr(broker_instance, "is_live_capable", lambda: False)() else "dry_run"
    elif broker_instance.get_broker_type() == "pionex_relay":
         execution_mode = "dry_run"
    return execution_mode

def _build_final_response(payload, journal_entry, ai_decision, ai_trace, regime_result, execution_mode):
    return {
        "signal_id": payload.signal_id,
        "trade_id": journal_entry.trade_id,
        "final_decision": journal_entry.final_decision,
        "ai_decision": ai_decision,
        "ai_trace": ai_trace,
        "regime": regime_result,
        "reject_reason": journal_entry.result.get("reject_reason") if journal_entry.result else None,
        "broker_result": journal_entry.result,
        "simulated_fill": journal_entry.simulated_fill,
        "execution_mode": execution_mode,
    }

async def _check_regime(payload: M8Payload) -> dict:
    """
    Check market regime before trading.
    Returns {trade_allowed, regime, reason}.
    If data fetch fails, allows trade (fail-open) with a warning.
    """
    try:
        # Run sync data fetch in thread pool to avoid blocking async loop
        bars = await asyncio.to_thread(
            BybitDataFeed.fetch,
            payload.symbol,
            bars=50,
            timeframe=payload.timeframe,
        )
        if not bars or len(bars) < 30:
            return {"trade_allowed": True, "regime": "UNKNOWN", "reason": "Insufficient bars for regime check"}

        closes = [bar.c for bar in bars]
        result = regime_engine_instance.should_trade(closes)
        return result
    except Exception as e:
        # Fail open — log warning but don't block trade
        return {"trade_allowed": True, "regime": "UNKNOWN", "reason": f"Regime check failed: {e}"}





async def process_signal(payload: M8Payload):
    """
    Main orchestration loop integrating AI Review -> Risk Engine -> Broker -> Journaling.
    Now uses BrokerFactory for clean broker selection.
    """

    # Emergency Halt Gate — must be checked before any execution
    halt_result = _check_emergency_halt(payload)
    if halt_result:
        return halt_result

    # 0. Regime Check (lightweight gate before expensive AI review)
    regime_result = await _check_regime(payload)

    # 1. AI Context Review (Non-execution, Kimi Swarm via async API)
    ai_review_result = ai_review_instance.review_signal(payload)
    ai_review = await ai_review_result if inspect.isawaitable(ai_review_result) else ai_review_result

    # Inject regime info into AI audit trace
    if ai_review.audit_trace is not None:
        ai_review.audit_trace["regime"] = regime_result

    # 2. Deterministic Decision
    if (
        AI_FAILURE_POLICY == "reject_live"
        and _is_ai_provider_unavailable(ai_review)
        and _is_live_capable_broker(broker_instance)
        and payload.intent != "CLOSE"
    ):
        decision_result = {
            "decision": DecisionEnum.REJECT,
            "reject_reason": "AI_PROVIDER_UNAVAILABLE_LIVE_BLOCK",
        }
    else:
        decision_result = risk_engine_instance.evaluate(payload, ai_review)

    # Override if regime blocks trading (only for ENTRY, not CLOSE)
    is_paper_mode = BROKER_MODE in {"simulation", "sim", "paper", "kraken_paper", "krakenpaper"}
    should_relax = is_paper_mode and PAPER_TRADING_RELAX_RISK
    if payload.intent != "CLOSE" and not regime_result.get("trade_allowed", True) and not should_relax:
        decision_result = {
            "decision": DecisionEnum.REJECT,
            "reject_reason": f"REGIME_HALT: {regime_result.get('reason', 'Market regime unsuitable')}",
        }

    # 3. Execution via selected Broker
    journal_entry = await _execute_trade_with_broker(payload, decision_result, ai_review.decision)

    # 4. Live Fill Tracking
    from app.services.live_fill_tracker import live_fill_tracker
    live_fill_tracker.record_intent(
        trade_id=journal_entry.trade_id,
        symbol=payload.symbol,
        direction=payload.direction,
        entry_price=payload.entry_price,
        stop_price=payload.stop_price,
        target_price=payload.target_price,
        decision=decision_result["decision"],
        strategy_id=payload.strategy_id,
        ai_trace=ai_review.audit_trace,
    )
    
    # 5. Journaling
    # ⚡ Bolt Optimization: Offload synchronous I/O to worker thread pool
    # Impact: Prevents blocking the async event loop, reducing execution latency significantly under load.
    await asyncio.to_thread(journal_logger_instance.log, journal_entry)

    # 6. Record fill if trade executed
    # We only record an entry fill for ENTRY intents. (For CLOSE intents, this should be handled separately).
    # ⚡ Bolt Optimization: Offload synchronous DB commit to worker thread
    await asyncio.to_thread(_record_trade_fill, payload, decision_result, journal_entry)

    # Update Risk Engine state if trade executed
    _update_risk_engine_post_trade(decision_result)

    # Dispatch learning feedback for rejected trades (simulated outcome)
    if decision_result["decision"] == DecisionEnum.REJECT and payload.intent == "ENTRY":
        asyncio.create_task(_dispatch_learning_feedback(payload, ai_review))
        # Also queue for delayed shadow evaluation when future bars are available
        from app.services.shadow_queue import shadow_queue
        try:
            shadow_queue.add(payload, ai_review)
        except Exception:
            pass

    execution_mode = _get_execution_mode()

    return _build_final_response(
        payload, journal_entry, ai_review.decision, ai_review.audit_trace, regime_result, execution_mode
    )


async def _dispatch_learning_feedback(payload: M8Payload, ai_review: SignalReview):
    """Simulate trade outcome for rejected signals and dispatch learning feedback to scouts."""
    if not ai_review.audit_trace:
        return
    scout_decisions = ai_review.audit_trace.get("scouts", {})
    if not scout_decisions:
        return
    try:
        from app.services.shadow_paper_engine import ShadowPaperEngine
        bars = await asyncio.to_thread(
            BybitDataFeed.fetch,
            payload.symbol,
            bars=200,
            timeframe=payload.timeframe,
        )
        if not bars or len(bars) < 20:
            return
        signal_ts = datetime.fromisoformat(payload.timestamp.replace('Z', '+00:00')).timestamp() * 1000
        entry_idx = min(range(len(bars)), key=lambda i: abs(bars[i].ts - signal_ts))
        # Need at least one future bar to simulate
        if entry_idx >= len(bars) - 1:
            return
        engine = ShadowPaperEngine()
        outcome = engine.simulate_trade(payload, bars, entry_idx, max_holding_bars=20)
        for scout_name, scout_report in scout_decisions.items():
            scout_approved = isinstance(scout_report, dict) and scout_report.get("decision") == DecisionEnum.PROCEED_TO_SIMULATION.value
            if not scout_approved and isinstance(scout_report, str):
                scout_approved = "PROCEED" in scout_report.upper() or "APPROVE" in scout_report.upper()
            was_correct = (scout_approved and outcome.win) or (not scout_approved and not outcome.win)
            confidence_registry.mark_scout_outcome(
                symbol=payload.symbol,
                scout_names=[scout_name],
                was_correct=was_correct,
            )
    except Exception:
        pass


async def process_manual_signal(payload: M8Payload):
    """
    Manual order bypass — skips AI review but keeps deterministic risk gates.
    Used for operator-initiated direct orders via the UI.
    """

    # Emergency Halt Gate — must be checked before any execution
    halt_result = _check_emergency_halt(payload)
    if halt_result:
        return halt_result

    # 0. Regime Check
    regime_result = await _check_regime(payload)

    # 1. Dummy AI Review (bypass)
    ai_review = SignalReview(
        schema_version="1.0",
        signal_id=payload.signal_id,
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
        confidence=1.0,
        reason_codes=["MANUAL_BYPASS"],
        risk_flags=[],
        requires_human_review=False,
        audit_trace={"manual": True, "source": "ui_direct"},
    )

    # 2. Deterministic Decision (Risk Engine still active for safety)
    decision_result = risk_engine_instance.evaluate(payload, ai_review)

    # Override if regime blocks trading (only for ENTRY, not CLOSE)
    is_paper_mode = BROKER_MODE in {"simulation", "sim", "paper", "kraken_paper", "krakenpaper"}
    should_relax = is_paper_mode and PAPER_TRADING_RELAX_RISK
    if payload.intent != "CLOSE" and not regime_result.get("trade_allowed", True) and not should_relax:
        decision_result = {
            "decision": DecisionEnum.REJECT,
            "reject_reason": f"REGIME_HALT: {regime_result.get('reason', 'Market regime unsuitable')}",
        }

    # 3. Execution via selected Broker
    journal_entry = await _execute_trade_with_broker(payload, decision_result, ai_review.decision)

    # 4. Live Fill Tracking
    from app.services.live_fill_tracker import live_fill_tracker
    live_fill_tracker.record_intent(
        trade_id=journal_entry.trade_id,
        symbol=payload.symbol,
        direction=payload.direction,
        entry_price=payload.entry_price,
        stop_price=payload.stop_price,
        target_price=payload.target_price,
        decision=decision_result["decision"],
        strategy_id=payload.strategy_id,
        ai_trace=ai_review.audit_trace,
    )

    # 5. Journaling
    # ⚡ Bolt Optimization: Offload synchronous I/O to worker thread pool
    # Impact: Prevents blocking the async event loop, reducing execution latency significantly under load.
    await asyncio.to_thread(journal_logger_instance.log, journal_entry)

    # 6. Record fill if trade executed
    # ⚡ Bolt Optimization: Offload synchronous DB commit to worker thread
    await asyncio.to_thread(_record_trade_fill, payload, decision_result, journal_entry)

    # Update Risk Engine state if trade executed
    _update_risk_engine_post_trade(decision_result)

    execution_mode = _get_execution_mode()

    return _build_final_response(
        payload, journal_entry, ai_review.decision, ai_review.audit_trace, regime_result, execution_mode
    )

