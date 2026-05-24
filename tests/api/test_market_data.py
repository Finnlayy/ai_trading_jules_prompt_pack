from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.signal_generator import OHLCV


@pytest.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def _make_bars(count: int):
    return [
        OHLCV(
            ts=1_700_000_000_000 + i * 60_000,
            o=100.0 + i * 0.01,
            h=101.0 + i * 0.01,
            l=99.0 + i * 0.01,
            c=100.5 + i * 0.01,
            v=1000.0 + i,
        )
        for i in range(count)
    ]


@pytest.mark.anyio
async def test_market_ohlcv_returns_bars(ac):
    bars = _make_bars(100)
    with patch("app.api.market_data.BybitDataFeed.fetch", return_value=bars):
        response = await ac.get("/market/ohlcv?symbol=BTCUSDT&timeframe=1h&bars=100")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["timeframe"] == "1h"
    assert len(data["bars"]) == 100
    first = data["bars"][0]
    assert first["time"] == 1_700_000_000
    assert first["open"] == 100.0
    assert first["high"] == 101.0
    assert first["low"] == 99.0
    assert first["close"] == 100.5
    assert first["volume"] == 1000.0


@pytest.mark.anyio
async def test_market_ohlcv_invalid_timeframe_returns_empty(ac):
    response = await ac.get("/market/ohlcv?symbol=BTCUSDT&timeframe=99h&bars=100")
    assert response.status_code == 200
    data = response.json()
    assert data["bars"] == []


@pytest.mark.anyio
async def test_market_ohlcv_fetch_failure_returns_empty(ac):
    with patch("app.api.market_data.BybitDataFeed.fetch", side_effect=Exception("network error")):
        response = await ac.get("/market/ohlcv?symbol=BTCUSDT&timeframe=1h&bars=100")
    assert response.status_code == 200
    data = response.json()
    assert data["bars"] == []


@pytest.mark.anyio
async def test_market_indicators_returns_scores(ac):
    bars = _make_bars(100)
    with patch("app.api.market_data.BybitDataFeed.fetch", return_value=bars):
        response = await ac.get("/market/indicators?symbol=BTCUSDT&timeframe=1h&bars=100")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["timeframe"] == "1h"
    assert len(data["indicators"]) == 100
    first = data["indicators"][0]
    assert "time" in first
    assert "confluence_score" in first
    assert "direction_hint" in first
    assert "alignment_count" in first


@pytest.mark.anyio
async def test_market_indicators_too_few_bars_returns_empty(ac):
    bars = _make_bars(10)
    with patch("app.api.market_data.BybitDataFeed.fetch", return_value=bars):
        response = await ac.get("/market/indicators?symbol=BTCUSDT&timeframe=1h&bars=10")
    # bars=10 is below the ge=50 validation on the indicators endpoint
    assert response.status_code == 422


@pytest.mark.anyio
async def test_market_indicators_invalid_timeframe_returns_empty(ac):
    response = await ac.get("/market/indicators?symbol=BTCUSDT&timeframe=99h&bars=100")
    assert response.status_code == 200
    data = response.json()
    assert data["indicators"] == []
