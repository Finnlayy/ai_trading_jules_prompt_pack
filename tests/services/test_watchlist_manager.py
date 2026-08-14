from pathlib import Path
import pytest
from app.services.watchlist_manager import WatchlistItem, WatchlistManager
import json

def test_watchlist_manager_add_remove_get(tmp_path):
    path = tmp_path / "watchlist.json"
    manager = WatchlistManager(persist_path=str(path))

    item = WatchlistItem(symbol="BTCUSDT", active=True)
    manager.add(item)
    assert manager.get("BTCUSDT") == item
    assert len(manager.list_all()) == 1

    manager.remove("BTCUSDT")
    assert manager.get("BTCUSDT") is None
    assert len(manager.list_all()) == 0

def test_watchlist_manager_persistence(tmp_path):
    path = tmp_path / "watchlist.json"
    manager1 = WatchlistManager(persist_path=str(path))
    item = WatchlistItem(symbol="ETHUSDT", active=False)
    manager1.add(item)

    # Reload from disk
    manager2 = WatchlistManager(persist_path=str(path))
    reloaded_item = manager2.get("ETHUSDT")
    assert reloaded_item is not None
    assert reloaded_item.symbol == "ETHUSDT"
    assert reloaded_item.active is False

def test_watchlist_manager_corrupted_json_graceful_handling(tmp_path):
    path = tmp_path / "watchlist.json"
    path.write_text("{corrupted_json: true,")

    # Should handle decode error gracefully and start with empty watchlist
    manager = WatchlistManager(persist_path=str(path))
    assert manager.list_all() == []


@pytest.fixture
def temp_watchlist_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_watchlist.json")

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

def test_watchlist_manager_update_nonexistent(temp_watchlist_path):
    manager = WatchlistManager(persist_path=temp_watchlist_path)
    res = manager.update("UNKNOWN", active=False)
    assert res is None

def test_watchlist_manager_load_corrupt_data(temp_watchlist_path):
    # Write invalid JSON to the path
    path = Path(temp_watchlist_path)
    path.write_text("invalid json {", encoding="utf-8")

    # Initialization shouldn't crash
    manager = WatchlistManager(persist_path=temp_watchlist_path)
    assert len(manager.list_all()) == 0
