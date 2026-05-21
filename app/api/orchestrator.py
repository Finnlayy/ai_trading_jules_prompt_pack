from app.schemas.m8_payload import M8Payload
from app.services.risk_engine import risk_engine_instance
from app.services.ai_kimi import ai_review_instance
from app.services.broker import SimulationBroker
from app.services.journal_logger import journal_logger_instance

# Single broker instance for the MVP
broker_instance = SimulationBroker()

async def process_signal(payload: M8Payload):
    """
    Main orchestration loop integrating AI Review -> Risk Engine -> Simulation Broker -> Journaling.
    Now uses asynchronous calls for the real Kimi Swarm API.
    """

    # 1. AI Context Review (Non-execution, Kimi Swarm via async API)
    ai_review = await ai_review_instance.review_signal(payload)

    # 2. Deterministic Decision
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
    if decision_result["decision"] == "PROCEED_TO_SIMULATION":
        risk_engine_instance.last_trade_bar = risk_engine_instance.current_bar
        risk_engine_instance.trades_today += 1

    return {
        "signal_id": payload.signal_id,
        "final_decision": journal_entry.final_decision,
        "reject_reason": journal_entry.result.get("reject_reason") if journal_entry.result else None
    }
