"""
Tests for PricePoller — background price fetching and auto-exit logic.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest

from app.services.price_poller import PricePoller
from app.services.live_fill_tracker import live_fill_tracker, FillData, PositionIntent


@pytest.fixture(autouse=True)
def reset_tracker_and_poller():
    live_fill_tracker.reset()
    poller = PricePoller()
    poller.stop()
    poller._running = False
    poller._task = None
    yield
    live_fill_tracker.reset()
    poller.stop()


def _create_position(trade_id: str, symbol: str, direction: str,
                     entry: float, stop: float, target: float, size: float = 1.0):
    intent = PositionIntent(
        trade_id=trade_id,
        symbol=symbol,
        direction=direction,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        size=size,
        strategy_id=None,
        decision="PROCEED_TO_SIMULATION",
    )
    live_fill_tracker.record_intent(intent)
    live_fill_tracker.record_fill(
        trade_id,
        FillData(
            entry_price=entry,
            fill_time=datetime.now(timezone.utc),
            size=size,
            side=direction,
            fees=0.0,
            slippage=0.0,
        ),
    )


class TestPricePollerLifecycle:
    def test_singleton(self):
        p1 = PricePoller()
        p2 = PricePoller()
        assert p1 is p2

    @pytest.mark.asyncio
    async def test_start_stop(self):
        poller = PricePoller()
        poller.stop()  # ensure clean state
        poller._task = None
        poller.set_interval(0.1)
        poller.start()
        assert poller.is_running is True
        await asyncio.sleep(0.05)
        poller.stop()
        assert poller.is_running is False


class TestPriceFetching:
    def test_fetch_prices_empty_symbols(self):
        poller = PricePoller()
        prices = poller._fetch_prices([])
        assert prices == {}

    def test_fetch_prices_returns_dict(self):
        poller = PricePoller()
        # Mock the Bybit API response
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {
                "list": [
                    {"symbol": "BTCUSDT", "markPrice": "50000.0", "lastPrice": "49999.0"},
                    {"symbol": "ETHUSDT", "markPrice": "3000.0", "lastPrice": "2999.0"},
                ]
            }
        }
        with patch("requests.get", return_value=mock_resp):
            prices = poller._fetch_prices(["BTCUSDT", "ETHUSDT"])
        assert prices == {"BTCUSDT": 50000.0, "ETHUSDT": 3000.0}

    def test_fetch_prices_uses_last_price_fallback(self):
        poller = PricePoller()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {
                "list": [
                    {"symbol": "BTCUSDT", "lastPrice": "49999.0"},
                ]
            }
        }
        with patch("requests.get", return_value=mock_resp):
            prices = poller._fetch_prices(["BTCUSDT"])
        assert prices == {"BTCUSDT": 49999.0}

    def test_fetch_prices_api_failure_graceful(self):
        poller = PricePoller()
        with patch("requests.get", side_effect=Exception("network error")):
            prices = poller._fetch_prices(["BTCUSDT"])
        assert prices == {}


class TestPollingLoop:
    @pytest.mark.asyncio
    async def test_poll_loop_updates_prices_and_exits(self):
        _create_position("tp1", "BTCUSDT", "LONG", entry=50000, stop=49000, target=52000, size=1.0)
        poller = PricePoller()
        poller.stop()
        poller._task = None
        poller.set_interval(0.05)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": {"list": [{"symbol": "BTCUSDT", "markPrice": "52100.0"}]}
        }

        with patch("requests.get", return_value=mock_resp):
            poller.start()
            # Wait for multiple poll cycles
            await asyncio.sleep(0.25)
            poller.stop()

        # Position should be closed by take-profit
        assert live_fill_tracker.get_position("tp1") is None

    @pytest.mark.asyncio
    async def test_poll_loop_no_positions_sleeps_longer(self):
        poller = PricePoller()
        poller.stop()
        poller._task = None
        poller.set_interval(0.05)
        call_count = 0
        original_sleep = asyncio.sleep

        async def counting_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count > 5:
                poller.stop()
            return await original_sleep(seconds)

        with patch("asyncio.sleep", side_effect=counting_sleep):
            poller.start()
            await asyncio.sleep(0.4)

        # Should have run but without fetching since no positions
        assert call_count >= 2

    def test_get_last_price(self):
        poller = PricePoller()
        poller._last_prices = {"BTCUSDT": 50000.0}
        assert poller.get_last_price("BTCUSDT") == 50000.0
        assert poller.get_last_price("ETHUSDT") is None
