from app.services.last_processed_bar_store import LastProcessedBarStore


def test_last_processed_bar_store_marks_and_loads(tmp_path):
    path = tmp_path / "last_processed.json"
    store = LastProcessedBarStore(str(path))

    assert store.get("btcusdt", "1m") is None
    assert store.should_process("btcusdt", "1m", 123) is True

    store.mark_processed("btcusdt", "1m", 123)

    assert store.get("BTCUSDT", "1m") == 123
    assert store.should_process("BTCUSDT", "1m", 123) is False
    assert store.should_process("BTCUSDT", "1m", 124) is True

    reloaded = LastProcessedBarStore(str(path))
    assert reloaded.get("BTCUSDT", "1m") == 123
    assert "BTCUSDT:1m" in reloaded.dump()


def test_last_processed_bar_store_reset(tmp_path):
    path = tmp_path / "last_processed.json"
    store = LastProcessedBarStore(str(path))
    store.mark_processed("ETHUSDT", "5m", 456)

    store.reset()

    assert store.get("ETHUSDT", "5m") is None
    assert store.dump() == {}
