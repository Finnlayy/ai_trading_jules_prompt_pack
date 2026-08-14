import ast
from typing import Any

code = """
class Test:
    def _record_trade_metrics(self, symbol: str, direction: str, realized_pnl: float, risk_amount: float) -> None:
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

    def _build_reject_close_entry(
        self,
        payload: Any,
        symbol: str,
        reason: str,
        ai_decision: Any,
        trade_id: str,
    ) -> Any:
        self.notifier.send_reject(symbol, reason, trade_id, payload.intent)
        return self._build_entry(
            payload=payload,
            decision="PROCEED_TO_SIMULATION",
            reject_reason=reason,
            ai_decision=ai_decision,
            final_decision="REJECTED",
            simulated_fill={},
            result={"status": "REJECTED", "reject_reason": reason},
        )

    def _calculate_close_pnl_and_side(self, direction: str, entry_price: float, close_price: float, size: float) -> tuple[float, str]:
        if direction == "LONG":
            return (close_price - entry_price) * size, "SELL"
        return (entry_price - close_price) * size, "BUY"

    def _close_position(self, payload: Any, symbol: str, account_mode: str, ai_decision: Any) -> Any:
        trade_id = f"pionex-direct-{payload.signal_id}"
        if not self.ledger.get(symbol=symbol, account_mode=account_mode):
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
        simulated_fill = {
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
            try:
                result["order"] = self._send_live_close(
                    symbol=symbol,
                    account_mode=account_mode,
                    close_side=close_side,
                    size_base=closed_size_base,
                    client_order_id=client_order_id,
                )
                result["status"] = "CLOSED_LIVE"
            except Exception as exc:
                self.ledger.apply_entry(
                    symbol=symbol,
                    account_mode=account_mode,
                    direction=direction,
                    size_base=closed_size_base,
                    client_order_id=client_order_id,
                    entry_price=entry_price,
                    risk_amount=risk_amount,
                )
                self.notifier.send_error("CLOSE", str(exc))
                return self._build_entry(
                    payload=payload,
                    decision="PROCEED_TO_SIMULATION",
                    reject_reason=str(exc),
                    ai_decision=ai_decision,
                    final_decision="REJECTED",
                    simulated_fill=simulated_fill,
                    result={"status": "API_ERROR", "reject_reason": str(exc)},
                )

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
            decision="PROCEED_TO_SIMULATION",
            reject_reason=None,
            ai_decision=ai_decision,
            final_decision="EXECUTED_SIM",
            simulated_fill=simulated_fill,
            result=result,
        )
"""

tree = ast.parse(code)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == '_close_position':
        print(f"Function {node.name} has {len(node.body)} statements in its body.")
