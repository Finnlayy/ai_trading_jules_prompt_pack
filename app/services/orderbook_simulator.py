import time
from typing import Dict, Any
from app.schemas.simulator import OrderbookSnapshot, OrderbookLevel, SimulatedFill
import httpx

class OrderbookSimulator:
    def __init__(self):
        self.client = httpx.AsyncClient()
        self.base_fee_pct = 0.001  # 0.1% Taker fee

    async def fetch_snapshot(self, venue: str, symbol: str) -> OrderbookSnapshot:
        """Fetch REST snapshot from public APIs."""
        if venue.lower() == "binance":
            # Binance uses standard format, adapt symbol if needed (e.g. BTCUSDT)
            url = f"https://api.binance.com/api/v3/depth?symbol={symbol.replace('/', '').replace('_', '')}&limit=100"
            resp = await self.client.get(url)
            resp.raise_for_status()
            data = resp.json()

            bids = [OrderbookLevel(price=float(p), quantity=float(q)) for p, q in data['bids']]
            asks = [OrderbookLevel(price=float(p), quantity=float(q)) for p, q in data['asks']]

        elif venue.lower() == "kraken":
            # Kraken formatting
            k_symbol = symbol.replace('/', '').replace('_', '')
            url = f"https://api.kraken.com/0/public/Depth?pair={k_symbol}&count=100"
            resp = await self.client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if data['error']:
                raise Exception(f"Kraken error: {data['error']}")

            # Kraken returns under the pair name key
            pair_key = list(data['result'].keys())[0]
            book = data['result'][pair_key]

            bids = [OrderbookLevel(price=float(lvl[0]), quantity=float(lvl[1])) for lvl in book['bids']]
            asks = [OrderbookLevel(price=float(lvl[0]), quantity=float(lvl[1])) for lvl in book['asks']]

        else:
            # Mock fallback
            bids = [OrderbookLevel(price=100.0 - i*0.1, quantity=1.0) for i in range(10)]
            asks = [OrderbookLevel(price=100.1 + i*0.1, quantity=1.0) for i in range(10)]

        return OrderbookSnapshot(
            symbol=symbol,
            venue=venue,
            timestamp=int(time.time()),
            bids=bids,
            asks=asks
        )

    async def simulate_fill(self, snapshot: OrderbookSnapshot, direction: str, size: float) -> SimulatedFill:
        levels = snapshot.asks if direction == "LONG" else snapshot.bids

        remaining_size = size
        total_cost = 0.0
        filled_size = 0.0

        for lvl in levels:
            if remaining_size <= 0:
                break

            fill_qty = min(remaining_size, lvl.quantity)
            total_cost += fill_qty * lvl.price
            filled_size += fill_qty
            remaining_size -= fill_qty

        if filled_size == 0:
            return SimulatedFill(
                symbol=snapshot.symbol,
                requested_size=size,
                filled_size=0.0,
                fill_price=0.0,
                slippage_absolute=0.0,
                slippage_pct=0.0,
                simulated_fees=0.0,
                orderbook_impact=0.0,
                partial_fill=False,
                status="REJECTED"
            )

        vwap = total_cost / filled_size
        top_price = levels[0].price
        slippage_abs = abs(vwap - top_price)
        slippage_pct = (slippage_abs / top_price) * 100

        fees = total_cost * self.base_fee_pct

        return SimulatedFill(
            symbol=snapshot.symbol,
            requested_size=size,
            filled_size=filled_size,
            fill_price=vwap,
            slippage_absolute=slippage_abs,
            slippage_pct=slippage_pct,
            simulated_fees=fees,
            orderbook_impact=slippage_abs,
            partial_fill=(filled_size < size),
            status="PARTIAL" if filled_size < size else "FILLED"
        )

orderbook_simulator = OrderbookSimulator()
