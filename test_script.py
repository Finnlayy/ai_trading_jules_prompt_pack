import ast

def get_function_complexity(filename):
    with open(filename, 'r') as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_close_position':
            return node

node = get_function_complexity('app/services/pionex_direct_broker.py')
print(f"Function {node.name} has {len(node.body)} statements in its body.")
