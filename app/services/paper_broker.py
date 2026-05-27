"""
PaperBroker — executes trades on Bybit TESTNET only.
Never connects to live Bybit. Falls back to SimulationBroker if no API keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from app.schemas.m8_payload import M8Payload
from app.schemas.journal import TradeJournalEntry, DirectionEnum, DecisionEnum, FinalDecisionEnum
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.services.bybit_api import BybitAPIClient, BybitCredentials, BybitAPIError


@dataclass
class PaperBrokerConfig:
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    testnet: bool = True
    default_qty: str = "0.01"  # Minimum order size for HYPEUSDT
    category: str = "linear"


class PaperBroker:
    """
    Paper trading broker that executes on Bybit Testnet.
    Logs all trades to journal just like SimulationBroker.
    """

    def __init__(self, config: Optional[PaperBrokerConfig] = None):
        self.config = config or self._config_from_env()
        self.client: Optional[BybitAPIClient] = None
        self.journal: List[TradeJournalEntry] = []
        self._connected = False

        if self.config.api_key and self.config.api_secret:
            try:
                creds = BybitCredentials(
                    api_key=self.config.api_key,
                    api_secret=self.config.api_secret,
                    testnet=self.config.testnet,
                )
                self.client = BybitAPIClient(creds)
                self._connected = True
            except BybitAPIError as e:
                print(f"[PAPER BROKER] Connection failed: {e}")
                self._connected = False
        else:
            print("[PAPER BROKER] No API keys configured — running in DRY-RUN mode")

    @staticmethod
    def _config_from_env() -> PaperBrokerConfig:
        """Load config from environment variables."""
        return PaperBrokerConfig(
            api_key=os.getenv("BYBIT_TESTNET_API_KEY") or None,
            api_secret=os.getenv("BYBIT_TESTNET_API_SECRET") or None,
            testnet=True,
        )

    def is_ready(self) -> bool:
        return self._connected

    def is_live_capable(self) -> bool:
        return self._connected

    def get_broker_name(self) -> str:
        return "PaperBroker"

    def get_broker_type(self) -> str:
        return "paper"

    def get_broker_mode(self) -> str:
        return "paper" if self._connected else "simulation"

    def get_positions(self) -> Dict[str, Any]:
        return {"positions": [], "broker": "paper"}

    def get_wallet_balances(self, account_mode: str = "SPOT") -> Dict[str, Any]:
        return {"balances": [], "broker": "paper"}

    def execute_trade(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str] = None,
        ai_decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION,
    ) -> TradeJournalEntry:
        """
        Execute or simulate a trade.
        If connected to Testnet → place real order.
        If no keys → dry-run (log only, no real order).
        """
        simulated_fill: Dict[str, Any] = {}
        result: Optional[Dict[str, Any]] = None
        final_decision = FinalDecisionEnum.SKIPPED
        order_response: Optional[Dict] = None

        if payload.direction == "LONG":
            risk = payload.entry_price - payload.stop_price
            reward = payload.target_price - payload.entry_price
            bybit_side = "Buy"
        else:
            risk = payload.stop_price - payload.entry_price
            reward = payload.entry_price - payload.target_price
            bybit_side = "Sell"

        rr_ratio = reward / risk if risk > 0 else 0.0

        if decision == DecisionEnum.PROCEED_TO_SIMULATION:
            final_decision = FinalDecisionEnum.EXECUTED_SIM

            if self._connected and self.client:
                # Place REAL order on Bybit Testnet
                try:
                    order_response = self.client.place_order(
                        symbol=payload.symbol,
                        side=bybit_side,
                        order_type="Market",
                        qty=self.config.default_qty,
                        stop_loss=str(payload.stop_price),
                        take_profit=str(payload.target_price),
                        category=self.config.category,
                    )
                    simulated_fill = {
                        "fill_price": payload.entry_price,
                        "fee": 0.0,
                        "slippage": 0.0,
                        "bybit_order_id": order_response.get("orderId", "unknown"),
                        "bybit_response": order_response,
                    }
                    result = {"status": "OPEN_TESTNET", "reject_reason": None}
                except BybitAPIError as e:
                    # Order failed — log as rejected with API error
                    final_decision = FinalDecisionEnum.REJECTED
                    simulated_fill = {}
                    result = {"status": "API_ERROR", "reject_reason": str(e)}
            else:
                # DRY-RUN mode: no real order
                simulated_fill = {
                    "fill_price": payload.entry_price,
                    "fee": 0.0,
                    "slippage": 0.0,
                    "mode": "DRY_RUN",
                }
                result = {"status": "OPEN_DRY_RUN", "reject_reason": None}
        else:
            final_decision = FinalDecisionEnum.REJECTED
            result = {"status": "REJECTED", "reject_reason": reject_reason}

        entry = TradeJournalEntry(
            trade_id=f"paper-{payload.signal_id}",
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
            result=result,
        )

        self.journal.append(entry)
        return entry

    def get_positions(self, symbol: str) -> Dict[str, Any]:
        """Query current position on Testnet."""
        if not self._connected or not self.client:
            return {"error": "Not connected to Testnet"}
        try:
            return self.client.get_position(symbol)
        except BybitAPIError as e:
            return {"error": str(e)}

    def get_balance(self) -> Dict[str, Any]:
        """Query wallet balance on Testnet."""
        if not self._connected or not self.client:
            return {"error": "Not connected to Testnet"}
        try:
            return self.client.get_wallet_balance()
        except BybitAPIError as e:
            return {"error": str(e)}

    def check_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Check status of a specific order."""
        if not self._connected or not self.client:
            return {"error": "Not connected to Testnet"}
        try:
            orders = self.client.get_open_orders(symbol)
            # Find specific order
            for order in orders.get("list", []):
                if order.get("orderId") == order_id:
                    return order
            return {"status": "not_found", "order_id": order_id}
        except BybitAPIError as e:
            return {"error": str(e)}
