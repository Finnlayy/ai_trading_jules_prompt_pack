import pytest
from httpx import ASGITransport, AsyncClient

from app.api import backtest_runner
from app.main import app


@pytest.mark.asyncio
async def test_backtest_status_reports_primary_and_futures_wallets(monkeypatch):
    class FakeBroker:
        def is_ready(self):
            return True

        def is_live_capable(self):
            return False

        def get_wallet_balances(self, account_mode="SPOT"):
            if account_mode == "FUTURES":
                return {
                    "coin": "USDT",
                    "account_mode": "FUTURES",
                    "balance": 19.38,
                    "asset_count": 2,
                    "assets": [
                        {"coin": "USDT", "balance": 19.38},
                        {"coin": "BTC", "balance": 0.01},
                    ],
                }
            return {
                "coin": "USDT",
                "account_mode": "SPOT",
                "balance": 8.4,
                "asset_count": 2,
                "assets": [
                    {"coin": "USDT", "balance": 8.4},
                    {"coin": "ETH", "balance": 0.2},
                    ],
                }

        def get_open_positions(self):
            return {
                "account_mode": "FUTURES",
                "open_count": 1,
                "positions": [{"symbol": "ZEC_USDT_PERP", "initial_margin": 8.25}],
                "summary": {"total_initial_margin": 8.25},
            }

        def get_running_bots(self):
            return {
                "status": "running",
                "open_count": 1,
                "bots": [{"symbol": "ZEC_USDT", "margin_balance": 9.5}],
                "summary": {"zcash_margin_balance": 9.5},
            }

    monkeypatch.setattr(backtest_runner, "_get_broker", lambda: FakeBroker())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/backtest/status")

    assert response.status_code == 200
    broker = response.json()["broker"]
    assert broker["wallets"]["primary"]["balance"] == 8.4
    assert broker["wallets"]["futures"]["balance"] == 19.38
    assert broker["wallets"]["primary"]["assets"][1]["coin"] == "ETH"
    assert broker["wallets"]["futures"]["assets"][1]["coin"] == "BTC"
    assert broker["balance"] == broker["wallets"]["primary"]
    assert broker["positions"]["open_count"] == 1
    assert broker["positions"]["positions"][0]["symbol"] == "ZEC_USDT_PERP"
    assert broker["bots"]["open_count"] == 1
    assert broker["bots"]["summary"]["zcash_margin_balance"] == 9.5
