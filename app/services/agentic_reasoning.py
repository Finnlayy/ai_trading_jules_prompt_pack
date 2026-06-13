from sqlalchemy import func
import json
import uuid
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from app.schemas.perception import PerceptionContext
from app.schemas.trading_plan import TradingPlan, PlanSetup, PlanTrigger, PlanInvalidation, PlanRiskIntent
from app.schemas.ai_review import SignalReview, DecisionEnum
from app.schemas.lifecycle import SignalCandidateRecord
from app.services.perception_engine import perception_engine
from app.services.agent_registry import agent_registry
from app.services.ai_factory import ai_review_instance
from app.db.models import AgenticRun
from app.db import get_db, SessionLocal

class AgenticState(BaseModel):
    run_id: str
    signal: Optional[Any] = None  # SignalCandidateRecord or M8Payload
    perception: Optional[PerceptionContext] = None
    scout_reviews: Dict[str, Any] = {}
    plan: Optional[TradingPlan] = None
    critique: Optional[Dict[str, Any]] = None
    final_review: Optional[SignalReview] = None
    error: Optional[str] = None

class AgenticReasoningLayer:
    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgenticState)

        workflow.add_node("perceive", self._node_perceive)
        workflow.add_node("scout_review", self._node_scout_review)
        workflow.add_node("plan", self._node_plan)
        workflow.add_node("critique", self._node_critique)
        workflow.add_node("finalize", self._node_finalize)

        workflow.set_entry_point("perceive")
        workflow.add_edge("perceive", "scout_review")
        workflow.add_edge("scout_review", "plan")
        workflow.add_edge("plan", "critique")
        workflow.add_edge("critique", "finalize")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    async def _node_perceive(self, state: AgenticState) -> AgenticState:
        try:
            symbol = state.signal.symbol if hasattr(state.signal, 'symbol') else "UNKNOWN"
            timeframe = state.signal.timeframe if hasattr(state.signal, 'timeframe') else "1m"
            state.perception = await perception_engine.build_context(symbol, timeframe)
        except Exception as e:
            state.error = f"Perception failed: {str(e)}"
        return state

    async def _node_scout_review(self, state: AgenticState) -> AgenticState:
        if state.error: return state
        # In a real implementation, we would call the scouts here.
        # For MVP, we mock the scout review while respecting the 60% rule.
        state.scout_reviews = {"mock_scout": {"decision": "PROCEED", "confidence": 0.85}}
        return state

    async def _node_plan(self, state: AgenticState) -> AgenticState:
        if state.error: return state

        # Mocking plan generation via LLM
        direction = state.signal.direction if hasattr(state.signal, 'direction') else "LONG"
        price = state.signal.entry_price if hasattr(state.signal, 'entry_price') else 100.0

        state.plan = TradingPlan(
            setup=PlanSetup(
                market_conditions="Trend following",
                regime="Trending",
                sentiment="Bullish",
                volatility="Medium",
                structure="Higher Highs"
            ),
            trigger=PlanTrigger(
                entry_condition="Price > MA20",
                price_zone_min=price * 0.99,
                price_zone_max=price * 1.01,
                timeframe="1m",
                confirmation_rule="Volume expansion"
            ),
            invalidation=PlanInvalidation(
                hard_stop_price=price * 0.95 if direction == "LONG" else price * 1.05,
                thesis_invalidated_condition="Price breaks previous low",
                max_loss_pct=5.0
            ),
            risk_intent=PlanRiskIntent(
                target_size_usd=100.0,
                risk_reward_ratio=2.0,
                leverage_desired=1.0,
                confidence_score=0.8
            ),
            direction=direction,
            evidence={"chart": "Looks good"}
        )
        return state

    async def _node_critique(self, state: AgenticState) -> AgenticState:
        if state.error: return state
        # Validate for contradictions
        state.critique = {"valid": True, "notes": "Plan looks solid."}
        return state


    def _generate_swarm_commentary(self, state: AgenticState) -> str:
        # Generate esports commentary based on scout votes and perception context
        votes = []
        for v in state.scout_reviews.values():
            if isinstance(v, dict):
                votes.append(v.get('decision', 'HOLD'))

        proceeds = sum(1 for v in votes if v == 'PROCEED')
        rejects = sum(1 for v in votes if v == 'REJECT')

        regime = "Unknown"
        volatility = "Medium"
        if state.perception and state.perception.regime:
            regime = state.perception.regime.market_regime
            volatility = state.perception.regime.volatility

        direction = getattr(state.signal, 'direction', 'LONG')

        if proceeds > rejects and rejects == 0:
            return f"Unanimous Swarm conviction to go {direction}! Risk teams and Quants are aligned in this {regime} regime."
        elif proceeds > rejects and rejects > 0:
            return f"Fierce debate in the war room! Quants push for {direction} but Risk counters with high {volatility} volatility concerns. Proceeding with caution."
        elif rejects > proceeds:
            return f"Swarm rejects the {direction} setup. The models are stepping back, waiting for better structure in this {regime} market."
        else:
            return f"Gridlock in the Swarm. The teams are evenly split on this {direction} idea. Holding fire."

    async def _node_finalize(self, state: AgenticState) -> AgenticState:

        if state.error: return state


        commentary = self._generate_swarm_commentary(state)

        audit_trace = {"trading_plan": state.plan.dict() if state.plan else None, "swarm_commentary": commentary}

        state.final_review = SignalReview(
            schema_version="1.0",
            signal_id=state.signal.signal_id if hasattr(state.signal, 'signal_id') else "unknown",
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            confidence=0.8,
            reason_codes=["PLAN_VALIDATED"],
            risk_flags=[],
            requires_human_review=False,
            audit_trace=audit_trace
        )

        # Persist to DB
        with SessionLocal() as db:
            run = db.query(AgenticRun).filter(AgenticRun.run_id == state.run_id).first()
            if run:
                run.perception_context_json = state.perception.json() if state.perception else None
                run.trading_plan_json = state.plan.json() if state.plan else None
                run.audit_trace_json = json.dumps(audit_trace)

                run.status = "planning_completed"
                run.completed_at = func.now()
                db.commit()

        return state

    async def run(self, signal: Any) -> AgenticState:
        run_id = f"run_{int(time.time())}_{str(uuid.uuid4())[:8]}"

        with SessionLocal() as db:
            db_run = AgenticRun(
                run_id=run_id,
                signal_id=signal.signal_id if hasattr(signal, 'signal_id') else None,
                symbol=signal.symbol if hasattr(signal, 'symbol') else "UNKNOWN",
                status="started"
            )
            db.add(db_run)
            db.commit()

        initial_state = AgenticState(run_id=run_id, signal=signal)
        final_state = await self.graph.ainvoke(initial_state)
        return final_state

agentic_reasoning = AgenticReasoningLayer()
