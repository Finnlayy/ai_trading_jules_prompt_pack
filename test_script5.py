import ast

code = """
class Test:
    def _execute_live_close(
        self,
        payload,
        symbol: str,
        account_mode: str,
        close_side: str,
        closed_size_base: float,
        client_order_id: str,
        direction: str,
        entry_price: float,
        risk_amount: float,
        simulated_fill: dict,
        ai_decision,
        result: dict,
    ) -> Optional[Any]:
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
"""

tree = ast.parse(code)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == '_execute_live_close':
        print(f"Function {node.name} has {len(node.body)} statements in its body.")
