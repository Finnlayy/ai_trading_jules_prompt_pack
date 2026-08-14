import os

filepath = 'app/services/pionex_direct_broker.py'

with open(filepath, 'r') as f:
    content = f.read()

helpers = """    def _build_reject_close_entry(
        self,
        payload: M8Payload,
        symbol: str,
        reason: str,
        ai_decision: AIDecisionEnum,
        trade_id: str,
        simulated_fill: Optional[dict[str, Any]] = None,
    ) -> TradeJournalEntry:
        self.notifier.send_reject(symbol, reason, trade_id, payload.intent)
        return self._build_entry(
            payload=payload,
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            reject_reason=reason,
            ai_decision=ai_decision,
            final_decision=FinalDecisionEnum.REJECTED,
            simulated_fill=simulated_fill or {},
            result={"status": "REJECTED", "reject_reason": reason},
        )

    def _calculate_close_pnl_and_side(
        self,
        direction: str,
        entry_price: float,
        close_price: float,
        size: float,
    ) -> tuple[float, str]:
        if direction == "LONG":
            return (close_price - entry_price) * size, "SELL"
        return (entry_price - close_price) * size, "BUY"

    def _record_trade_metrics(
        self,
        symbol: str,
        direction: str,
        realized_pnl: float,
        risk_amount: float,
    ) -> None:
        if risk_amount and risk_amount > 0:
            rr_achieved = abs(realized_pnl / risk_amount)
            pnl_pct = (realized_pnl / risk_amount) * 100.0
        else:
            rr_achieved = 0.0
            pnl_pct = 0.0
        from app.services.confidence_registry import confidence_registry
        from app.services.portfolio_circuit_breaker import circuit_breaker_instance
        confidence_registry.record_trade_outcome(
            symbol=symbol,
            direction=direction,
            pnl_pct=pnl_pct,
            rr=rr_achieved,
            win=realized_pnl > 0,
        )
        circuit_breaker_instance.record_trade_pnl(realized_pnl)

    def _execute_live_close_or_rollback(
        self,
        payload: M8Payload,
        symbol: str,
        account_mode: str,
        close_side: str,
        closed_size_base: float,
        client_order_id: str,
        direction: str,
        entry_price: float,
        risk_amount: float,
        simulated_fill: dict[str, Any],
        ai_decision: AIDecisionEnum,
        result: dict[str, Any],
    ) -> Optional[TradeJournalEntry]:
        try:
            order = self._send_live_close(
                symbol=symbol,
                account_mode=account_mode,
                close_side=close_side,
                size_base=closed_size_base,
                client_order_id=client_order_id,
            )
            result["status"] = "CLOSED_LIVE"
            result["order"] = order
            return None
        except PionexAPIError as exc:
            # Rollback local ledger close when live close fails.
            self.ledger.apply_entry(
                symbol=symbol,
                account_mode=account_mode,
                direction=direction,
                size_base=closed_size_base,
                client_order_id=client_order_id,
                entry_price=entry_price,
                risk_amount=risk_amount,
            )
            self.notifier.send_error("CLOSE", exc.message)
            return self._build_entry(
                payload=payload,
                decision=DecisionEnum.PROCEED_TO_SIMULATION,
                reject_reason=exc.message,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill=simulated_fill,
                result={"status": "API_ERROR", "reject_reason": exc.message},
            )

    def _close_position(self, payload: M8Payload, symbol: str, account_mode: str, ai_decision: AIDecisionEnum) -> TradeJournalEntry:"""

content = content.replace("    def _close_position(self, payload: M8Payload, symbol: str, account_mode: str, ai_decision: AIDecisionEnum) -> TradeJournalEntry:", helpers)

with open(filepath, 'w') as f:
    f.write(content)
