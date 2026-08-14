from __future__ import annotations

from app.services.paper_training_engine import PaperTrainingEngine


class FakeLoop:
    def __init__(self) -> None:
        self.is_running = False
        self.is_paused = False
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1
        self.is_running = True
        self.is_paused = False

    def stop(self) -> None:
        self.stopped += 1
        self.is_running = False
        self.is_paused = False

    def pause(self) -> None:
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False

    def get_status(self) -> dict:
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "active_symbols": ["BTCUSDT"],
            "poll_interval_seconds": 60.0,
            "loop_stats": {"cycles_completed": 1},
        }


class FakeMonitor:
    def __init__(self) -> None:
        self.is_running = False
        self.started = 0
        self.stopped = 0
        self.check_interval_seconds = 5.0

    def start(self) -> None:
        self.started += 1
        self.is_running = True

    def stop(self) -> None:
        self.stopped += 1
        self.is_running = False


def test_paper_training_engine_starts_loop_and_position_monitor():
    loop = FakeLoop()
    monitor = FakeMonitor()
    engine = PaperTrainingEngine(loop=loop, monitor=monitor)

    status = engine.control("start")

    assert loop.started == 1
    assert monitor.started == 1
    assert status["engine"]["state"] == "running"
    assert status["engine"]["execution_mode"] == "paper"
    assert status["engine"]["live_trading_enabled"] is False


def test_paper_training_engine_pauses_loop_but_keeps_monitor_running():
    loop = FakeLoop()
    monitor = FakeMonitor()
    engine = PaperTrainingEngine(loop=loop, monitor=monitor)

    engine.control("start")
    status = engine.control("pause")

    assert status["engine"]["state"] == "paused"
    assert status["components"]["position_monitor"]["running"] is True


def test_paper_training_engine_stop_stops_all_runtime_components():
    loop = FakeLoop()
    monitor = FakeMonitor()
    engine = PaperTrainingEngine(loop=loop, monitor=monitor)

    engine.control("start")
    status = engine.control("stop")

    assert loop.stopped == 1
    assert monitor.stopped == 1
    assert status["engine"]["state"] == "stopped"


def test_paper_training_engine_reports_partial_as_running_runtime():
    loop = FakeLoop()
    monitor = FakeMonitor()
    monitor.start()
    engine = PaperTrainingEngine(loop=loop, monitor=monitor)

    status = engine.status()

    assert status["engine"]["state"] == "partial"
    assert status["engine"]["is_running"] is True
