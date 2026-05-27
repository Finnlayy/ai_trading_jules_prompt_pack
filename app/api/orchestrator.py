import asyncio
import inspect
from datetime import datetime, timezone

from app.schemas.m8_payload import M8Payload
from app.services.risk_engine import risk_engine_instance
from app.services.ai_kimi import ai_review_instance
from app.services.broker_factory import BrokerFactory
from app.services.journal_logger import journal_logger_instance
from app.services.regime_engine import regime_engine_instance
from app.services.signal_generator import BybitDataFeed
from app.schemas.journal import DecisionEnum
from app.core.config import AI_FAILURE_POLICY, BROKER_MODE


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

        closes = [bar.close for bar in bars]
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
    if payload.intent != "CLOSE" and not regime_result.get("trade_allowed", True):
        decision_result = {
            "decision": DecisionEnum.REJECT,
            "reject_reason": f"REGIME_HALT: {regime_result.get('reason', 'Market regime unsuitable')}",
        }

    # 3. Execution via selected Broker
    execute_kwargs = {
        "payload": payload,
        "decision": decision_result["decision"],
        "reject_reason": decision_result["reject_reason"],
        "ai_decision": ai_review.decision,
    }
    if _should_execute_broker_in_thread(broker_instance):
        journal_entry = await asyncio.to_thread(broker_instance.execute_trade, **execute_kwargs)
    else:
        journal_entry = broker_instance.execute_trade(**execute_kwargs)

    # 4. Live Fill Tracking
    from app.services.live_fill_tracker import live_fill_tracker, FillData
    from app.services.dashboard_sse import dashboard_sse_manager

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
    
    # 4. Journaling
    await journal_logger_instance.log(journal_entry)
    

    # 5. Journaling
    journal_logger_instance.log(journal_entry)

    # 6. Record fill if trade executed
    if decision_result["decision"] == DecisionEnum.PROCEED_TO_SIMULATION and journal_entry.simulated_fill:
        fill = journal_entry.simulated_fill
        live_fill_tracker.record_fill(
            journal_entry.trade_id,
            FillData(
                entry_price=fill.get("fill_price", payload.entry_price),
                fill_time=datetime.now(timezone.utc),
                size=fill.get("size", 0.0),
                side=payload.direction,
                fees=fill.get("fees", 0.0),
                slippage=fill.get("slippage", 0.0),
            ),
        )
        dashboard_sse_manager.broadcast_trade_update({
            "trade_id": journal_entry.trade_id,
            "symbol": payload.symbol,
            "direction": payload.direction,
            "entry_price": payload.entry_price,
            "status": "filled",
        })

    # Update Risk Engine state if trade executed
    if decision_result["decision"] == DecisionEnum.PROCEED_TO_SIMULATION:
        risk_engine_instance.last_trade_bar = risk_engine_instance.current_bar
        risk_engine_instance.trades_today += 1

    return {
        "signal_id": payload.signal_id,
        "trade_id": journal_entry.trade_id,
        "final_decision": journal_entry.final_decision,
        "ai_decision": ai_review.decision,
        "ai_trace": ai_review.audit_trace,
        "regime": regime_result,
        "reject_reason": journal_entry.result.get("reject_reason") if journal_entry.result else None,
        "broker_result": journal_entry.result,
        "simulated_fill": journal_entry.simulated_fill,
    }
