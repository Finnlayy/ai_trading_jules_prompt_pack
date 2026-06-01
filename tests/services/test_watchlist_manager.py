import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.watchlist_manager import WatchlistItem, WatchlistManager


def test_watchlist_item_serialization():
    item = WatchlistItem(
        symbol="BTCUSDT",
        timeframes=["1m", "5m"],
        active=True,
        strategy_id="strat_1",
        min_confluence=0.8,
        max_position_size_usdt=100.0,
    )

    data = item.to_dict()
    assert data["symbol"] == "BTCUSDT"
    assert data["timeframes"] == ["1m", "5m"]
    assert data["active"] is True
    assert data["strategy_id"] == "strat_1"
    assert data["min_confluence"] == 0.8
    assert data["max_position_size_usdt"] == 100.0
    assert "added_at" in data

    item2 = WatchlistItem.from_dict(data)
    assert item2.symbol == "BTCUSDT"
    assert item2.timeframes == ["1m", "5m"]
    assert item2.active is True
    assert item2.strategy_id == "strat_1"
    assert item2.min_confluence == 0.8
    assert item2.max_position_size_usdt == 100.0
    assert item2.added_at == data["added_at"]


def test_watchlist_item_defaults():
    item = WatchlistItem(symbol="ETHUSDT")
    assert item.timeframes == ["1m", "5m", "15m"]
    assert item.active is True
    assert item.strategy_id is None
    assert item.min_confluence is None
    assert item.max_position_size_usdt is None

    data = item.to_dict()
    item2 = WatchlistItem.from_dict(data)
    assert item2.timeframes == ["1m", "5m", "15m"]


@pytest.fixture
def temp_watchlist_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_watchlist.json")


def test_watchlist_manager_add_and_get(temp_watchlist_path):
    manager = WatchlistManager(persist_path=temp_watchlist_path)
    item = WatchlistItem(symbol="BTCUSDT")
    manager.add(item)

    retrieved = manager.get("BTCUSDT")
    assert retrieved is not None
    assert retrieved.symbol == "BTCUSDT"

    # Check case-insensitivity
    retrieved_lower = manager.get("btcusdt")
    assert retrieved_lower is not None
    assert retrieved_lower.symbol == "BTCUSDT"


def test_watchlist_manager_persistence(temp_watchlist_path):
    manager1 = WatchlistManager(persist_path=temp_watchlist_path)
    manager1.add(WatchlistItem(symbol="BTCUSDT"))
    manager1.add(WatchlistItem(symbol="ETHUSDT", active=False))

    # Check if the file was written
    assert Path(temp_watchlist_path).exists()

    # Load with a new manager to verify persistence
    manager2 = WatchlistManager(persist_path=temp_watchlist_path)
    assert manager2.get("BTCUSDT") is not None
    assert manager2.get("ETHUSDT") is not None
    assert manager2.get("ETHUSDT").active is False
    assert len(manager2.list_all()) == 2


def test_watchlist_manager_remove(temp_watchlist_path):
    manager = WatchlistManager(persist_path=temp_watchlist_path)
    manager.add(WatchlistItem(symbol="BTCUSDT"))
    assert manager.get("BTCUSDT") is not None

    manager.remove("BTCUSDT")
    assert manager.get("BTCUSDT") is None
    assert len(manager.list_all()) == 0


def test_watchlist_manager_update(temp_watchlist_path):
    manager = WatchlistManager(persist_path=temp_watchlist_path)
    manager.add(WatchlistItem(symbol="BTCUSDT", active=True, max_position_size_usdt=50.0))

    manager.update("BTCUSDT", active=False, max_position_size_usdt=200.0, strategy_id="new_strat")

    item = manager.get("BTCUSDT")
    assert item.active is False
    assert item.max_position_size_usdt == 200.0
    assert item.strategy_id == "new_strat"


def test_watchlist_manager_update_nonexistent(temp_watchlist_path):
    manager = WatchlistManager(persist_path=temp_watchlist_path)
    res = manager.update("UNKNOWN", active=False)
    assert res is None


def test_watchlist_manager_get_active(temp_watchlist_path):
    manager = WatchlistManager(persist_path=temp_watchlist_path)
    manager.add(WatchlistItem(symbol="BTCUSDT", active=True))
    manager.add(WatchlistItem(symbol="ETHUSDT", active=False))
    manager.add(WatchlistItem(symbol="SOLUSDT", active=True))

    active_items = manager.get_active()
    assert len(active_items) == 2
    symbols = set(item.symbol for item in active_items)
    assert symbols == {"BTCUSDT", "SOLUSDT"}


def test_watchlist_manager_reset(temp_watchlist_path):
    manager = WatchlistManager(persist_path=temp_watchlist_path)
    manager.add(WatchlistItem(symbol="BTCUSDT"))
    manager.add(WatchlistItem(symbol="ETHUSDT"))
    assert len(manager.list_all()) == 2

    manager.reset()
    assert len(manager.list_all()) == 0

    manager2 = WatchlistManager(persist_path=temp_watchlist_path)
    assert len(manager2.list_all()) == 0


def test_watchlist_manager_load_corrupt_data(temp_watchlist_path):
    # Write invalid JSON to the path
    path = Path(temp_watchlist_path)
    path.write_text("invalid json {", encoding="utf-8")

    # Initialization shouldn't crash
    manager = WatchlistManager(persist_path=temp_watchlist_path)
    assert len(manager.list_all()) == 0
