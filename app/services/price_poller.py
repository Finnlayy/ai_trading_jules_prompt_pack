"""
Price Poller — background task that polls current prices for open positions
and auto-closes them via PositionMonitor when stop/target/time conditions hit.
"""

from __future__ import annotations

import asyncio
import json
from typing import Dict

import requests

from app.core.config import AUTONOMOUS_LOOP_ENABLED
from app.services.dashboard_sse import SSEEvent
from app.services.live_fill_tracker import live_fill_tracker
from app.services.position_monitor import position_monitor
from app.services.dashboard_sse import dashboard_sse_manager


class PricePoller:
    """
    Singleton asyncio background task for live position price monitoring.
    Fetches tickers from Bybit and checks exit conditions every 10 seconds.
    """

    _instance: PricePoller | None = None

    def __new__(cls, *args, **kwargs) -> PricePoller:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, interval_seconds: float = 10.0) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._interval = interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_prices: Dict[str, float] = {}

    # -- Lifecycle ----------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    @property
    def is_running(self) -> bool:
        return self._running

    def set_interval(self, seconds: float) -> None:
        self._interval = seconds

    # -- Polling loop -------------------------------------------------------

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                positions = live_fill_tracker.get_open_positions()
                if positions:
                    symbols = list({p.symbol.upper() for p in positions})
                    prices = await asyncio.to_thread(self._fetch_prices, symbols)
                    self._last_prices.update(prices)

                    # Update unrealized PnL for all positions
                    for pos in positions:
                        price = prices.get(pos.symbol.upper())
                        if price:
                            live_fill_tracker.update_price(pos.trade_id, price)

                    # Check exits
                    exits = position_monitor.check_price_based_exits(prices)
                    if exits:
                        position_monitor.execute_exits(exits)

                    # Broadcast price update
                    if prices:
                        dashboard_sse_manager.broadcast(
                            SSEEvent(
                                event_type="price_update",
                                payload={"prices": prices},
                            )
                        )
                else:
                    # No open positions — slow down polling
                    await asyncio.sleep(max(self._interval, 30.0))
                    continue

            except asyncio.CancelledError:
                break
            except Exception as exc:
                dashboard_sse_manager.broadcast_alert(
                    f"PricePoller error: {exc}", level="warning"
                )

            await asyncio.sleep(self._interval)

    # -- Price fetching -----------------------------------------------------

    @staticmethod
    def _fetch_prices(symbols: list[str]) -> Dict[str, float]:
        """Fetch latest mark prices from Bybit tickers endpoint."""
        prices: Dict[str, float] = {}
        try:
            resp = requests.get(
                "https://api.bybit.com/v5/market/tickers",
                params={"category": "linear"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            tickers = data.get("result", {}).get("list", [])
            for t in tickers:
                sym = t.get("symbol", "").upper()
                if sym in symbols:
                    # Use markPrice if available, else lastPrice
                    price = t.get("markPrice") or t.get("lastPrice")
                    if price:
                        prices[sym] = float(price)
        except Exception:
            pass
        return prices

    def get_last_price(self, symbol: str) -> float | None:
        return self._last_prices.get(symbol.upper())


# Global singleton
price_poller = PricePoller()
