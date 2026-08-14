import re

filepath = 'app/services/pionex_direct_broker.py'

with open(filepath, 'r') as f:
    content = f.read()

# Locate the beginning of _close_position
start_match = re.search(r'    def _close_position\(self, payload: M8Payload, symbol: str, account_mode: str, ai_decision: AIDecisionEnum\) -> TradeJournalEntry:\n', content)
start_idx = start_match.end()

# The next method is _send_live_close
end_match = re.search(r'\n    def _send_live_close\(', content[start_idx:])
end_idx = start_idx + end_match.start()

new_method_body = """        trade_id = f"pionex-direct-{payload.signal_id}"
        position = self.ledger.get(symbol=symbol, account_mode=account_mode)
        if not position:
            return self._build_reject_close_entry(payload, symbol, "NO_OPEN_POSITION", ai_decision, trade_id)

        close_size = payload.execution_quantity if payload.execution_quantity and payload.execution_quantity > 0 else None
        close_info = self.ledger.apply_close(symbol=symbol, account_mode=account_mode, close_size_base=close_size)
        closed_size_base = float(close_info["closed_size_base"])
        entry_price = float(close_info["entry_price"])
        risk_amount = float(close_info["risk_amount"])
        direction = str(close_info["direction"])

        if closed_size_base <= 0:
            return self._build_reject_close_entry(payload, symbol, "ZERO_CLOSE_SIZE", ai_decision, trade_id)

        realized_pnl, close_side = self._calculate_close_pnl_and_side(direction, entry_price, payload.entry_price, closed_size_base)

        live_mode = self.config.live_trading_enabled and self.client is not None
        client_order_id = self._client_order_id(payload, symbol, account_mode, close_side)
        simulated_fill: dict[str, Any] = {
            "mode": "PIONEX_DIRECT",
            "live_mode": live_mode,
            "symbol": symbol,
            "account_mode": account_mode,
            "close_side": close_side,
            "closed_size_base": closed_size_base,
            "entry_price": entry_price,
            "close_price": payload.entry_price,
            "client_order_id": client_order_id,
        }

        result: dict[str, Any] = {
            "status": "CLOSED_DRY_RUN",
            "reject_reason": None,
            "realized_pnl_quote": realized_pnl,
            "risk_amount": risk_amount,
            "ledger_delta": {
                "action": "CLOSE",
                "symbol": symbol,
                "account_mode": account_mode,
                "closed_size_base": closed_size_base,
                "client_order_id": client_order_id,
            },
        }

        self._record_trade_metrics(symbol, direction, realized_pnl, risk_amount)

        if live_mode and self.client:
            rollback_err = self._execute_live_close_or_rollback(
                payload, symbol, account_mode, close_side, closed_size_base,
                client_order_id, direction, entry_price, risk_amount,
                simulated_fill, ai_decision, result
            )
            if rollback_err:
                return rollback_err

        self.notifier.send_execution(
            symbol=symbol,
            account_mode=account_mode,
            intent=payload.intent,
            side=close_side,
            size=closed_size_base,
            price=payload.entry_price,
            trade_id=trade_id,
        )
        return self._build_entry(
            payload=payload,
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            reject_reason=None,
            ai_decision=ai_decision,
            final_decision=FinalDecisionEnum.EXECUTED_SIM,
            simulated_fill=simulated_fill,
            result=result,
        )"""

content = content[:start_idx] + new_method_body + content[end_idx:]

with open(filepath, 'w') as f:
    f.write(content)
