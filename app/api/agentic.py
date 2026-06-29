from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.schemas.lifecycle import SignalCandidateRecord
from app.schemas.ai_review import SignalReview
from app.schemas.trading_plan import TradingPlan
from app.services.agentic_reasoning import agentic_reasoning
from app.db import get_db, SessionLocal
from app.db.models import AgenticRun
import json
import asyncio

from app.schemas.perception import SwarmStateResponse, ScoutVoteState
from app.db.models import AgentReviewEvent
import time

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
    # ⚡ Bolt Optimization: Offloaded synchronous DB I/O and JSON parsing to a threadpool to prevent blocking the async event loop.
    def _fetch_run():
        with SessionLocal() as db:
            run = db.query(AgenticRun).filter(AgenticRun.run_id == run_id).first()
            if not run:
                return None

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

    result = await asyncio.to_thread(_fetch_run)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/swarm-state/{run_id}", response_model=SwarmStateResponse)
async def get_swarm_state(run_id: str):
    # ⚡ Bolt Optimization: Offloaded synchronous DB I/O and JSON parsing to a threadpool to prevent blocking the async event loop.
    def _fetch_swarm():
        with SessionLocal() as db:
            run = db.query(AgenticRun).filter(AgenticRun.run_id == run_id).first()
            if not run:
                return None

            events = db.query(AgentReviewEvent).filter(AgentReviewEvent.candidate_id == run_id).all()
            votes = []
            for e in events:
                reasons = []
                if e.reasons_json:
                    try:
                        reasons = json.loads(e.reasons_json)
                    except Exception:
                        pass
                votes.append(ScoutVoteState(
                    scout_name=e.scout_name,
                    vote=e.decision,
                    confidence=e.confidence,
                    reason_codes=reasons,
                    model=e.model or "unknown"
                ))

            audit = {}
            if run.audit_trace_json:
                try:
                    audit = json.loads(run.audit_trace_json)
                except Exception:
                    pass

            commentary = audit.get("swarm_commentary", "")

            return SwarmStateResponse(
                run_id=run.run_id,
                symbol=run.symbol or "UNKNOWN",
                direction="LONG", # Placeholder, would be pulled from run/candidate
                consensus_score=0.5, # Placeholder
                votes=votes,
                commentary=commentary,
                timestamp=int(time.time())
            )

    result = await asyncio.to_thread(_fetch_swarm)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result

@router.get("/runs/latest/swarm", response_model=SwarmStateResponse)
async def get_latest_swarm_state():
    # ⚡ Bolt Optimization: Offloaded synchronous DB I/O and JSON parsing to a threadpool to prevent blocking the async event loop.
    def _fetch_latest():
        with SessionLocal() as db:
            run = db.query(AgenticRun).order_by(AgenticRun.id.desc()).first()
            return run.run_id if run else None

    run_id = await asyncio.to_thread(_fetch_latest)
    if not run_id:
        raise HTTPException(status_code=404, detail="No runs found")

    return await get_swarm_state(run_id)
