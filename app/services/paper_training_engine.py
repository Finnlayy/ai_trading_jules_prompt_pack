"""Operator control layer for the live-paper training engine."""

from __future__ import annotations

from typing import Any, Literal

from app.services.autonomous_loop import autonomous_loop_instance
from app.services.position_monitor import paper_position_monitor_instance

EngineAction = Literal["start", "stop", "pause", "resume"]


class PaperTrainingEngine:
    """Coordinates the autonomous candidate loop and paper position monitor."""

    def __init__(self, *, loop: Any = None, monitor: Any = None) -> None:
        self.loop = loop or autonomous_loop_instance
        self.monitor = monitor or paper_position_monitor_instance

    def status(self) -> dict[str, Any]:
        loop_status = self.loop.get_status()
        monitor_running = bool(getattr(self.monitor, "is_running", False))
        loop_running = bool(loop_status.get("is_running", False))
        loop_paused = bool(loop_status.get("is_paused", False))
        active_symbols = loop_status.get("active_symbols", [])
        lifecycle_state = self._state(loop_running, loop_paused, monitor_running)
        return {
            "status": "ok",
            "engine": {
                "state": lifecycle_state,
                "is_running": lifecycle_state != "stopped",
                "is_paused": loop_paused,
                "execution_mode": "paper",
                "live_trading_enabled": False,
            },
            "components": {
                "autonomous_loop": {
                    "running": loop_running,
                    "paused": loop_paused,
                    "active_symbols": active_symbols,
                    "poll_interval_seconds": loop_status.get("poll_interval_seconds"),
                    "stats": loop_status.get("loop_stats", {}),
                },
                "position_monitor": {
                    "running": monitor_running,
                    "check_interval_seconds": getattr(self.monitor, "check_interval_seconds", None),
                },
            },
            "warnings": self._warnings(active_symbols, monitor_running),
        }

    def control(self, action: EngineAction) -> dict[str, Any]:
        if action == "start":
            self.monitor.start()
            self.loop.start()
        elif action == "stop":
            self.loop.stop()
            self.monitor.stop()
        elif action == "pause":
            self.loop.pause()
        elif action == "resume":
            self.loop.resume()
        else:
            raise ValueError(f"Unknown paper training engine action: {action}")

        result = self.status()
        result["action"] = action
        return result

    @staticmethod
    def _state(loop_running: bool, loop_paused: bool, monitor_running: bool) -> str:
        if loop_running and loop_paused:
            return "paused"
        if loop_running and monitor_running:
            return "running"
        if loop_running or monitor_running:
            return "partial"
        return "stopped"

    @staticmethod
    def _warnings(active_symbols: list[str], monitor_running: bool) -> list[str]:
        warnings: list[str] = []
        if not active_symbols:
            warnings.append("No active watchlist symbols; loop will not generate candidates.")
        if not monitor_running:
            warnings.append("Paper position monitor is stopped; open paper positions will not auto-close.")
        return warnings


paper_training_engine = PaperTrainingEngine()
