import ast

code = """
class Test:
    def _calculate_close_pnl_and_side(self, direction: str, entry_price: float, close_price: float, size: float) -> tuple[float, str]:
        if direction == "LONG":
            return (close_price - entry_price) * size, "SELL"
        return (entry_price - close_price) * size, "BUY"
"""

tree = ast.parse(code)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == '_calculate_close_pnl_and_side':
        print(f"Function {node.name} has {len(node.body)} statements in its body.")
