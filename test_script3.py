import ast

code = """
class Test:
    def _handle_reject(self, payload, symbol, reason, ai_decision, trade_id, simulated_fill=None):
        simulated_fill = simulated_fill or {}
        self.notifier.send_reject(symbol, reason, trade_id, payload.intent)
        return self._build_entry(
            payload=payload,
            decision="PROCEED_TO_SIMULATION",
            reject_reason=reason,
            ai_decision=ai_decision,
            final_decision="REJECTED",
            simulated_fill=simulated_fill,
            result={"status": "REJECTED", "reject_reason": reason},
        )
"""

tree = ast.parse(code)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == '_handle_reject':
        print(f"Function {node.name} has {len(node.body)} statements in its body.")
