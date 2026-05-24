from app.schemas.m8_payload import M8Payload
from app.schemas.journal import TradeJournalEntry, DirectionEnum, DecisionEnum, FinalDecisionEnum
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from typing import Dict, Optional
from datetime import datetime, timezone

class SimulationBroker:
    def __init__(self, fee_bps: float = 5.0, slippage_bps: float = 2.0):
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.journal: list[TradeJournalEntry] = []

    def is_live_capable(self) -> bool:
        return False

    def is_ready(self) -> bool:
        return True

    def get_broker_name(self) -> str:
        return "SimulationBroker"

    def get_broker_type(self) -> str:
        return "simulation"

    def get_broker_mode(self) -> str:
        return "simulation"

    def get_positions(self) -> dict:
        return {"positions": [], "broker": "simulation"}

    def get_wallet_balances(self, account_mode: str = "SPOT") -> dict:
        return {"balances": [], "broker": "simulation"}

    def execute_trade(self, 
                      payload: M8Payload, 
                      decision: DecisionEnum, 
                      reject_reason: Optional[str] = None,
                      ai_decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION) -> TradeJournalEntry:
        """
        Simulates execution. Applies mock fills if proceeded, otherwise logs rejection.
        """
        
        simulated_fill = {}
        result = None
        final_decision = FinalDecisionEnum.SKIPPED

        if payload.direction == "LONG":
            risk = payload.entry_price - payload.stop_price
            reward = payload.target_price - payload.entry_price
        else:
            risk = payload.stop_price - payload.entry_price
            reward = payload.entry_price - payload.target_price

        # Avoid div by zero in mock
        rr_ratio = reward / risk if risk > 0 else 0.0

        if decision == DecisionEnum.PROCEED_TO_SIMULATION:
            final_decision = FinalDecisionEnum.EXECUTED_SIM
            
            # Apply static slippage to entry
            entry_price_with_slippage = payload.entry_price * (1 + self.slippage_bps / 10000.0) if payload.direction == "LONG" else payload.entry_price * (1 - self.slippage_bps / 10000.0)
            
            # Simulated fee
            fee = entry_price_with_slippage * (self.fee_bps / 10000.0)
            
            simulated_fill = {
                "fill_price": entry_price_with_slippage,
                "fee": fee,
                "slippage": abs(entry_price_with_slippage - payload.entry_price)
            }
            
            # For MVP, mock result as open (unrealized). Real backtest would scan future bars.
            result = {"status": "OPEN", "reject_reason": None}
        else:
            final_decision = FinalDecisionEnum.REJECTED
            result = {"status": "REJECTED", "reject_reason": reject_reason}

        entry = TradeJournalEntry(
            trade_id=f"sim-{payload.signal_id}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            direction=DirectionEnum(payload.direction),
            entry_price=payload.entry_price,
            stop_price=payload.stop_price,
            target_price=payload.target_price,
            risk_reward=rr_ratio,
            m8_score=payload.confluence_score,
            ai_decision=DecisionEnum(ai_decision.value),
            final_decision=final_decision,
            simulated_fill=simulated_fill,
            result=result
        )

        self.journal.append(entry)
        return entry
