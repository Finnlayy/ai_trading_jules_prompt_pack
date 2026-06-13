import asyncio
from app.api.backtest_runner import _generate_backtest_chart_sync

def test_chart_gen():
    outcomes = [
        {"pnl": 100},
        {"pnl": -50},
        {"pnl": 200},
        {"pnl": -100},
    ]

    b64 = _generate_backtest_chart_sync(outcomes)
    assert b64.startswith("iVBORw0KGgo")
    print("Success: Chart generated successfully!")

test_chart_gen()
