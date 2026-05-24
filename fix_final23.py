with open("tests/services/test_pionex_direct_broker.py", "r") as f:
    text = f.read()

text = "from app.schemas.journal import DecisionEnum, FinalDecisionEnum\n" + text

with open("tests/services/test_pionex_direct_broker.py", "w") as f:
    f.write(text)
