from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.schemas.lifecycle import SignalCandidateRecord
from app.schemas.ai_review import SignalReview
from app.schemas.trading_plan import TradingPlan
from app.services.agentic_reasoning import agentic_reasoning
from app.db.repository import db_session
from app.db.models import AgenticRun
import json

router = APIRouter()

class SignalRequest(BaseModel):
    signal_id: str
    symbol: str
    direction: str
    entry_price: float
    timeframe: str = "1m"

@router.post("/review-signal", response_model=SignalReview)
async def review_signal(req: SignalRequest):
    try:
        # Mocking a SignalCandidateRecord
        class MockSignal:
            signal_id = req.signal_id
            symbol = req.symbol
            direction = req.direction
            entry_price = req.entry_price
            timeframe = req.timeframe

        final_state = await agentic_reasoning.run(MockSignal())
        if final_state.error:
            raise HTTPException(status_code=500, detail=final_state.error)
        return final_state.final_review
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trading-plan", response_model=TradingPlan)
async def create_trading_plan(req: SignalRequest):
    try:
        class MockSignal:
            signal_id = req.signal_id
            symbol = req.symbol
            direction = req.direction
            entry_price = req.entry_price
            timeframe = req.timeframe

        final_state = await agentic_reasoning.run(MockSignal())
        if final_state.error:
            raise HTTPException(status_code=500, detail=final_state.error)
        return final_state.plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    with db_session() as db:
        run = db.query(AgenticRun).filter(AgenticRun.run_id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        return {
            "run_id": run.run_id,
            "status": run.status,
            "symbol": run.symbol,
            "perception_context": json.loads(run.perception_context_json) if run.perception_context_json else None,
            "trading_plan": json.loads(run.trading_plan_json) if run.trading_plan_json else None,
            "risk_result": json.loads(run.risk_result_json) if run.risk_result_json else None,
            "simulator_result": json.loads(run.simulator_result_json) if run.simulator_result_json else None,
            "audit_trace": json.loads(run.audit_trace_json) if run.audit_trace_json else None
        }
