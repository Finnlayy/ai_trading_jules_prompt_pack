import pytest
<<<<<<< HEAD
import json
from pathlib import Path
from unittest.mock import patch, mock_open
from app.services.watchlist_manager import WatchlistItem, WatchlistManager

def test_watchlist_item_to_dict():
    item = WatchlistItem(symbol="BTCUSDT", active=True)
    item_dict = item.to_dict()
    assert item_dict["symbol"] == "BTCUSDT"
    assert item_dict["active"] is True
    assert "timeframes" in item_dict
    assert "added_at" in item_dict

def test_watchlist_item_from_dict():
    data = {
        "symbol": "ETHUSDT",
        "timeframes": ["1h", "4h"],
        "active": False,
        "strategy_id": "strat_1",
        "min_confluence": 0.8,
        "max_position_size_usdt": 100.0,
        "added_at": "2023-10-27T10:00:00Z"
    }
    item = WatchlistItem.from_dict(data)
    assert item.symbol == "ETHUSDT"
    assert item.timeframes == ["1h", "4h"]
    assert item.active is False
    assert item.strategy_id == "strat_1"
    assert item.min_confluence == 0.8
    assert item.max_position_size_usdt == 100.0
    assert item.added_at == "2023-10-27T10:00:00Z"

@pytest.fixture
def mock_persist_path(tmp_path):
    return tmp_path / "watchlist.json"

def test_watchlist_manager_init(mock_persist_path):
    manager = WatchlistManager(persist_path=str(mock_persist_path))
    assert manager._path == mock_persist_path
    assert manager._items == {}

def test_watchlist_manager_add(mock_persist_path):
    manager = WatchlistManager(persist_path=str(mock_persist_path))
    item = WatchlistItem(symbol="BTCUSDT")
    manager.add(item)
    assert manager.get("BTCUSDT") == item
    assert manager.get("btcusdt") == item # case insensitivity check

def test_watchlist_manager_remove(mock_persist_path):
    manager = WatchlistManager(persist_path=str(mock_persist_path))
    item = WatchlistItem(symbol="BTCUSDT")
    manager.add(item)
    assert manager.get("BTCUSDT") is not None
    manager.remove("BTCUSDT")
    assert manager.get("BTCUSDT") is None

def test_watchlist_manager_update(mock_persist_path):
    manager = WatchlistManager(persist_path=str(mock_persist_path))
    item = WatchlistItem(symbol="BTCUSDT", active=True)
    manager.add(item)
    updated_item = manager.update("BTCUSDT", active=False, min_confluence=0.9)
    assert updated_item is not None
    assert updated_item.active is False
    assert updated_item.min_confluence == 0.9
    assert manager.get("BTCUSDT").active is False

def test_watchlist_manager_update_non_existent(mock_persist_path):
    manager = WatchlistManager(persist_path=str(mock_persist_path))
    updated_item = manager.update("UNKNOWN", active=False)
    assert updated_item is None

def test_watchlist_manager_get_active(mock_persist_path):
    manager = WatchlistManager(persist_path=str(mock_persist_path))
    item1 = WatchlistItem(symbol="BTCUSDT", active=True)
    item2 = WatchlistItem(symbol="ETHUSDT", active=False)
    manager.add(item1)
    manager.add(item2)
    active_items = manager.get_active()
    assert len(active_items) == 1
    assert active_items[0].symbol == "BTCUSDT"

def test_watchlist_manager_list_all(mock_persist_path):
    manager = WatchlistManager(persist_path=str(mock_persist_path))
    item1 = WatchlistItem(symbol="BTCUSDT")
    item2 = WatchlistItem(symbol="ETHUSDT")
    manager.add(item1)
    manager.add(item2)
    all_items = manager.list_all()
    assert len(all_items) == 2
    symbols = [item.symbol for item in all_items]
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols

def test_watchlist_manager_reset(mock_persist_path):
    manager = WatchlistManager(persist_path=str(mock_persist_path))
    item = WatchlistItem(symbol="BTCUSDT")
    manager.add(item)
    manager.reset()
    assert len(manager.list_all()) == 0

def test_watchlist_manager_persist_and_load(mock_persist_path):
    manager1 = WatchlistManager(persist_path=str(mock_persist_path))
    item = WatchlistItem(symbol="BTCUSDT", timeframes=["1h"])
    manager1.add(item)

    # Create new manager with same path, it should load the persisted data
    manager2 = WatchlistManager(persist_path=str(mock_persist_path))
    loaded_item = manager2.get("BTCUSDT")
    assert loaded_item is not None
    assert loaded_item.symbol == "BTCUSDT"
    assert loaded_item.timeframes == ["1h"]

def test_watchlist_manager_load_corrupted_file(mock_persist_path):
    # Write invalid json
    mock_persist_path.write_text("invalid json")

    # Manager should not crash, should just load empty items
    manager = WatchlistManager(persist_path=str(mock_persist_path))
    assert manager._items == {}

def test_watchlist_manager_persist_error(tmp_path):
    # Create a manager pointing to a directory that cannot be written to
    # Mock Path.write_text to raise an exception
    manager = WatchlistManager(persist_path=str(tmp_path / "test.json"))
    item = WatchlistItem(symbol="BTCUSDT")

    with patch.object(Path, 'write_text', side_effect=PermissionError("Permission denied")):
        manager.add(item) # Should catch the exception and not crash
        assert manager.get("BTCUSDT") is not None
=======
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
>>>>>>> main
