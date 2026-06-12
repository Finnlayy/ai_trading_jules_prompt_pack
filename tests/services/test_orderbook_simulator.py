import pytest
from app.services.orderbook_simulator import OrderbookSimulator
from app.schemas.simulator import OrderbookSnapshot, OrderbookLevel

@pytest.fixture
def simulator():
    return OrderbookSimulator()

@pytest.fixture
def mock_snapshot():
    bids = [
        OrderbookLevel(price=99.0, quantity=10.0),
        OrderbookLevel(price=98.0, quantity=20.0)
    ]
    asks = [
        OrderbookLevel(price=101.0, quantity=5.0),
        OrderbookLevel(price=102.0, quantity=15.0)
    ]
    return OrderbookSnapshot(
        symbol="BTCUSD",
        venue="mock",
        timestamp=1234567890,
        bids=bids,
        asks=asks
    )

@pytest.mark.asyncio
async def test_simulate_fill_long(simulator, mock_snapshot):
    fill = await simulator.simulate_fill(mock_snapshot, "LONG", 10.0)

    assert fill.status == "FILLED"
    assert fill.filled_size == 10.0
    # 5 @ 101, 5 @ 102 => Total Cost = 505 + 510 = 1015 => VWAP = 101.5
    assert fill.fill_price == 101.5
    assert fill.slippage_absolute == 0.5
    assert fill.partial_fill is False

@pytest.mark.asyncio
async def test_simulate_fill_partial(simulator, mock_snapshot):
    # Try to buy 30, but only 20 available in asks
    fill = await simulator.simulate_fill(mock_snapshot, "LONG", 30.0)

    assert fill.status == "PARTIAL"
    assert fill.filled_size == 20.0
    assert fill.partial_fill is True

@pytest.mark.asyncio
async def test_simulate_fill_short(simulator, mock_snapshot):
    fill = await simulator.simulate_fill(mock_snapshot, "SHORT", 5.0)

    assert fill.status == "FILLED"
    assert fill.filled_size == 5.0
    assert fill.fill_price == 99.0
    assert fill.slippage_absolute == 0.0
