with open("tests/services/test_pionex_direct_broker.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip() == "from app.schemas.journal import DecisionEnum, FinalDecisionEnum" and "import pytest" in "".join(new_lines):
        continue
    new_lines.append(line)

with open("tests/services/test_pionex_direct_broker.py", "w") as f:
    f.writelines(new_lines)
