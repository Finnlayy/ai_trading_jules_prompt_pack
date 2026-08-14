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
