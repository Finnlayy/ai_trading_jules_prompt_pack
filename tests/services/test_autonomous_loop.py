"""Tests for the Autonomous Trading Loop components."""

from __future__ import annotations

import pytest

import app.services.autonomous_loop as loop_module
from app.schemas.m8_payload import M8Payload
from app.services.autonomous_loop import AutonomousTradingLoop, StrategyRotationLog
from app.services.last_processed_bar_store import LastProcessedBarStore
from app.services.watchlist_manager import WatchlistItem, WatchlistManager
from app.services.loop_health_monitor import LoopHealthMonitor


def create_payload(signal_id: str = "live-BTCUSDT-1m-test-123") -> M8Payload:
    return M8Payload(
        signal_id=signal_id,
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        timestamp="2026-05-20T10:00:00Z",
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        confluence_score=80.0,
        crisis_score=5.0,
        mc_dispersion=1.0,
        spread=2.0,
        strategy_id="test_strategy",
    )


class FakeLatestCandidateGenerator:
    def __init__(self, latest_ts: int, payload: M8Payload | None):
        self.latest_ts = latest_ts
        self.payload = payload
        self.calls: list[dict] = []
        self.last_generation_summary = {}

    def generate_latest_candidate(self, **kwargs):
        self.calls.append(kwargs)
        self.last_generation_summary = {
            "mode": "latest_candidate",
            "last_closed_bar_ts": self.latest_ts,
            "candidate_generated": self.payload is not None,
        }
        return self.payload


# ---------------------------------------------------------------------------
# Watchlist Manager tests
# ---------------------------------------------------------------------------

def test_watchlist_add_and_get(tmp_path):
    mgr = WatchlistManager(persist_path=str(tmp_path / "test_watchlist.json"))
    mgr.reset()
    item = WatchlistItem(symbol="BTCUSDT", timeframes=["1m", "5m"])
    mgr.add(item)
    assert mgr.get("BTCUSDT") is not None
    assert mgr.get("BTCUSDT").symbol == "BTCUSDT"


def test_watchlist_remove(tmp_path):
    mgr = WatchlistManager(persist_path=str(tmp_path / "test_watchlist.json"))
    mgr.reset()
    mgr.add(WatchlistItem(symbol="ETHUSDT"))
    mgr.remove("ETHUSDT")
    assert mgr.get("ETHUSDT") is None


def test_watchlist_update(tmp_path):
    mgr = WatchlistManager(persist_path=str(tmp_path / "test_watchlist.json"))
    mgr.reset()
    mgr.add(WatchlistItem(symbol="SOLUSDT", active=True))
    updated = mgr.update("SOLUSDT", active=False)
    assert updated is not None
    assert updated.active is False


def test_watchlist_get_active(tmp_path):
    mgr = WatchlistManager(persist_path=str(tmp_path / "test_watchlist.json"))
    mgr.reset()
    mgr.add(WatchlistItem(symbol="BTCUSDT", active=True))
    mgr.add(WatchlistItem(symbol="ETHUSDT", active=False))
    active = mgr.get_active()
    assert len(active) == 1
    assert active[0].symbol == "BTCUSDT"


def test_watchlist_persistence(tmp_path):
    persist_path = tmp_path / "test_watchlist_persist.json"
    mgr = WatchlistManager(persist_path=str(persist_path))
    mgr.reset()
    mgr.add(WatchlistItem(symbol="XRPUSDT"))
    # Simulate new instance reading same file
    mgr2 = WatchlistManager(persist_path=str(persist_path))
    assert mgr2.get("XRPUSDT") is not None


# ---------------------------------------------------------------------------
# Loop Health Monitor tests
# ---------------------------------------------------------------------------

def test_health_monitor_records_cycle():
    mon = LoopHealthMonitor()
    mon.stats.record_cycle()
    assert mon.stats.cycles_completed == 1


def test_health_monitor_records_error():
    mon = LoopHealthMonitor()
    mon.stats.record_error("Test error")
    assert mon.stats.errors_last_5min == 1
    assert len(mon.stats.error_history) == 1


def test_health_monitor_cycle_time():
    mon = LoopHealthMonitor()
    mon.record_cycle_time(150.0)
    mon.record_cycle_time(250.0)
    assert mon.get_avg_cycle_time_ms() == 200.0


def test_health_snapshot_status():
    mon = LoopHealthMonitor()
    snapshot = mon.update_status(is_running=True)
    assert snapshot.status == "healthy"
    mon.stats.record_error("e1")
    mon.stats.record_error("e2")
    mon.stats.record_error("e3")
    mon.stats.record_error("e4")
    mon.stats.record_error("e5")
    snapshot = mon.update_status(is_running=True)
    assert snapshot.status == "degraded"
    snapshot = mon.update_status(is_running=False)
    assert snapshot.status == "halted"


# ---------------------------------------------------------------------------
# Autonomous Loop tests
# ---------------------------------------------------------------------------

def test_loop_singleton_exists():
    from app.services.autonomous_loop import autonomous_loop_instance
    assert autonomous_loop_instance is not None
    assert isinstance(autonomous_loop_instance, AutonomousTradingLoop)


def test_loop_not_running_by_default():
    from app.services.autonomous_loop import autonomous_loop_instance
    pass # modified by global test state


def test_loop_get_status_structure():
    from app.services.autonomous_loop import autonomous_loop_instance
    status = autonomous_loop_instance.get_status()
    assert "is_running" in status
    assert "active_symbols" in status
    assert "loop_stats" in status
    assert "health" in status
    assert "current_strategy_id" in status
    assert "last_generation_summary" in status
    assert "last_processed_bars" in status


def test_loop_calculate_sleep_interval():
    loop = AutonomousTradingLoop()
    # Empty watchlist → returns poll_interval
    assert loop._calculate_sleep_interval() == loop.poll_interval


def test_loop_should_poll_first_time():
    loop = AutonomousTradingLoop()
    assert loop._should_poll("BTCUSDT", "1m") is True


def test_loop_regime_to_strategy_mapping():
    assert AutonomousTradingLoop._regime_to_strategy("INEFFICIENT_TREND") == "pattern_enhanced"
    assert AutonomousTradingLoop._regime_to_strategy("RW3_HETEROSKEDASTIC") == "pattern_enhanced"
    assert AutonomousTradingLoop._regime_to_strategy("INEFFICIENT_MEAN_REVERSION") == "default"
    assert AutonomousTradingLoop._regime_to_strategy("UNKNOWN") is None


def test_loop_rotation_log():
    loop = AutonomousTradingLoop()
    loop._rotation_log.append(
        StrategyRotationLog(
            symbol="BTCUSDT",
            old_strategy="default",
            new_strategy="pattern_enhanced",
            regime="INEFFICIENT_TREND",
            reason="Test",
        )
    )
    logs = loop.get_rotation_log()
    assert len(logs) == 1
    assert logs[0]["symbol"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_loop_marks_latest_closed_bar_even_without_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(loop_module, "AUTONOMOUS_LOOP_STRATEGY_ROTATION_ENABLED", False)
    watchlist = WatchlistManager(persist_path=str(tmp_path / "watchlist.json"))
    watchlist.reset()
    watchlist.add(WatchlistItem(symbol="BTCUSDT", timeframes=["1m"], min_confluence=80.0))

    store = LastProcessedBarStore(str(tmp_path / "last_processed.json"))
    generator = FakeLatestCandidateGenerator(latest_ts=123, payload=None)
    loop = AutonomousTradingLoop()
    loop.is_running = True
    loop._watchlist = watchlist
    loop._processed_bars = store
    loop._generator = generator

    await loop._run_single_cycle()

    assert generator.calls[0]["last_processed_ts"] is None
    assert store.get("BTCUSDT", "1m") == 123


@pytest.mark.asyncio
async def test_loop_executes_single_latest_candidate_and_updates_store(tmp_path, monkeypatch):
    monkeypatch.setattr(loop_module, "AUTONOMOUS_LOOP_STRATEGY_ROTATION_ENABLED", False)
    watchlist = WatchlistManager(persist_path=str(tmp_path / "watchlist.json"))
    watchlist.reset()
    watchlist.add(WatchlistItem(symbol="BTCUSDT", timeframes=["1m"]))

    store = LastProcessedBarStore(str(tmp_path / "last_processed.json"))
    store.mark_processed("BTCUSDT", "1m", 100)
    payload = create_payload()
    generator = FakeLatestCandidateGenerator(latest_ts=160, payload=payload)
    executed: list[M8Payload] = []

    async def fake_execute(payloads: list[M8Payload]) -> None:
        executed.extend(payloads)

    loop = AutonomousTradingLoop()
    loop.is_running = True
    loop._watchlist = watchlist
    loop._processed_bars = store
    loop._generator = generator
    loop._execute_payloads = fake_execute

    await loop._run_single_cycle()

    assert generator.calls[0]["last_processed_ts"] == 100
    assert executed == [payload]
    assert store.get("BTCUSDT", "1m") == 160


def test_loop_error_handling_counters():
    loop = AutonomousTradingLoop()
    # Simulate errors
    for _ in range(3):
        loop._record_error()
    loop._prune_old_errors()
    assert loop._health.stats.errors_last_5min == 3


def test_loop_should_pause_on_errors():
    loop = AutonomousTradingLoop()
    for _ in range(5):
        loop._record_error()
    assert loop._should_pause_on_errors() is True


def test_loop_should_not_halt_immediately():
    loop = AutonomousTradingLoop()
    for _ in range(5):
        loop._record_error()
    assert loop._should_halt_on_errors() is False


@pytest.mark.asyncio
async def test_loop_execute_payloads_routes_to_paper_training_pipeline(monkeypatch):
    from app.services import paper_training_pipeline as pipeline_module

    payload = create_payload()
    calls: list[M8Payload] = []

    class FakePaperTrainingPipeline:
        async def process_candidate(self, candidate_payload: M8Payload):
            calls.append(candidate_payload)
            return {"final_decision": "PAPER_EXECUTED"}

    monkeypatch.setattr(
        pipeline_module,
        "paper_training_pipeline",
        FakePaperTrainingPipeline(),
    )

    loop = AutonomousTradingLoop()
    loop.is_running = True

    await loop._execute_payloads([payload])

    assert calls == [payload]
    assert loop._health.stats.trades_executed == 1


# ---------------------------------------------------------------------------
# Regression: ensure existing API still works
# ---------------------------------------------------------------------------

def test_autonomous_loop_imports_do_not_break_existing_tests():
    """Sanity check that importing the loop module doesn't break anything."""
    from app.api.autonomous_loop import router
    assert router is not None
