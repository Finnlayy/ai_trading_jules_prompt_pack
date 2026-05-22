from app.schemas.m8_payload import M8Payload
from app.services.risk_engine import risk_engine_instance
from app.services.ai_kimi import ai_review_instance
from app.services.broker import SimulationBroker
from app.services.paper_broker import PaperBroker
from app.services.pionex_relay_broker import PionexRelayBroker
from app.services.pionex_direct_broker import PionexDirectBroker
from app.services.journal_logger import journal_logger_instance
from app.schemas.journal import DecisionEnum
from app.core.config import AI_FAILURE_POLICY, BROKER_MODE

def _build_broker():
    if BROKER_MODE == "pionex_direct":
        return PionexDirectBroker()
    if BROKER_MODE in {"pionex_direct", "direct", "pionex_api"}:
        return PionexDirectBroker(journal_path=journal_logger_instance.filepath)
    if BROKER_MODE in {"pionex_relay", "pionex", "relay"}:
        return PionexRelayBroker()
    if BROKER_MODE == "paper":
        return PaperBroker()
    return SimulationBroker()


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
    if BROKER_MODE in {"pionex_relay", "relay", "pionex"} and hasattr(broker, "is_ready"):
        try:
            return bool(broker.is_ready())
        except Exception:
            return False
    return False

async def process_signal(payload: M8Payload):
    """
    Main orchestration loop integrating AI Review -> Risk Engine -> Simulation Broker -> Journaling.
    Now uses asynchronous calls for the real Kimi Swarm API.
    """
    
    # 1. AI Context Review (Non-execution, Kimi Swarm via async API)
    ai_review = await ai_review_instance.review_signal(payload)
    
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
    
    # 3. Execution via Simulation Broker
    journal_entry = broker_instance.execute_trade(
        payload=payload,
        decision=decision_result["decision"],
        reject_reason=decision_result["reject_reason"],
        ai_decision=ai_review.decision
    )
    
    # 4. Journaling
    journal_logger_instance.log(journal_entry)
    
    # Update Risk Engine state if trade executed
    if decision_result["decision"] == DecisionEnum.PROCEED_TO_SIMULATION:
        risk_engine_instance.last_trade_bar = risk_engine_instance.current_bar
        risk_engine_instance.trades_today += 1
        
    return {
        "signal_id": payload.signal_id,
        "final_decision": journal_entry.final_decision,
        "reject_reason": journal_entry.result.get("reject_reason") if journal_entry.result else None
    }
