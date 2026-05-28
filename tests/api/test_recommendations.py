import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

@pytest.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

@pytest.mark.anyio
async def test_recommendations_invalid_symbol(ac):
    response = await ac.get("/market/recommend?symbol=BTC!@#&timeframe=1h")
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    # Ensure it's caught as a pattern mismatch
    assert any("pattern" in str(error) or "match" in str(error) for error in data["detail"])

@pytest.mark.anyio
async def test_recommendations_valid_symbol(ac, monkeypatch):
    # Mock the Bybit fetch so it doesn't try to make a real network request
    import app.api.recommendations as rec_api
    class DummyFetch:
        @staticmethod
        def fetch(symbol, bars, timeframe):
            return []

    monkeypatch.setattr(rec_api.BybitDataFeed, "fetch", DummyFetch.fetch)

    response = await ac.get("/market/recommend?symbol=BTCUSDT&timeframe=1h")
    assert response.status_code == 200
