"""
Loop Health Monitor — tracks metrics and health status of the autonomous trading loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict

from app.services.telegram_notifier import TelegramNotifier


@dataclass
class LoopStats:
    cycles_completed: int = 0
    signals_generated: int = 0
    trades_executed: int = 0
    errors_last_5min: int = 0
    error_history: list[dict] = field(default_factory=list)

    def record_cycle(self) -> None:
        self.cycles_completed += 1

    def record_signal(self) -> None:
        self.signals_generated += 1

    def record_trade(self) -> None:
        self.trades_executed += 1

    def record_error(self, error: str) -> None:
        self.errors_last_5min += 1
        self.error_history.append(
            {"error": error, "timestamp": datetime.now(timezone.utc).isoformat()}
        )
        # Keep only last 20 errors
        if len(self.error_history) > 20:
            self.error_history = self.error_history[-20:]

    def reset_error_window(self) -> None:
        self.errors_last_5min = 0


@dataclass
class HealthSnapshot:
    status: str = "healthy"  # "healthy" | "degraded" | "halted"
    cycles_completed: int = 0
    signals_generated: int = 0
    trades_executed: int = 0
    errors_last_5min: int = 0
    avg_cycle_time_ms: float = 0.0
    next_poll: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LoopHealthMonitor:
    """Monitors the autonomous trading loop health and emits alerts."""

    def __init__(self) -> None:
        self.stats = LoopStats()
        self._cycle_times: list[float] = []
        self._status: str = "healthy"
        self._last_alert_status: str | None = None

    def record_cycle_time(self, duration_ms: float) -> None:
        self._cycle_times.append(duration_ms)
        if len(self._cycle_times) > 100:
            self._cycle_times = self._cycle_times[-100:]

    def get_avg_cycle_time_ms(self) -> float:
        if not self._cycle_times:
            return 0.0
        return sum(self._cycle_times) / len(self._cycle_times)

    def update_status(self, is_running: bool, next_poll: datetime | None = None) -> HealthSnapshot:
        """Evaluate health based on recent error rate."""
        if not is_running:
            self._status = "halted"
        elif self.stats.errors_last_5min >= 5:
            self._status = "degraded"
        else:
            self._status = "healthy"

        snapshot = HealthSnapshot(
            status=self._status,
            cycles_completed=self.stats.cycles_completed,
            signals_generated=self.stats.signals_generated,
            trades_executed=self.stats.trades_executed,
            errors_last_5min=self.stats.errors_last_5min,
            avg_cycle_time_ms=round(self.get_avg_cycle_time_ms(), 2),
            next_poll=next_poll.isoformat() if next_poll else None,
        )

        self._maybe_send_alert(snapshot)
        return snapshot

    def _maybe_send_alert(self, snapshot: HealthSnapshot) -> None:
        """Send Telegram alert on status transitions."""
        if self._last_alert_status == snapshot.status:
            return
        self._last_alert_status = snapshot.status

        if snapshot.status in ("degraded", "halted"):
            try:
                from app.services.telegram_notifier import TelegramNotifier, TelegramConfig
                from app.core.config import TELEGRAM_NOTIFICATIONS_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
                config = TelegramConfig(
                    enabled=TELEGRAM_NOTIFICATIONS_ENABLED,
                    bot_token=TELEGRAM_BOT_TOKEN,
                    chat_id=TELEGRAM_CHAT_ID,
                )
                notifier = TelegramNotifier(config)
                if notifier._is_configured():
                    notifier.send_reconcile_alert(
                        f"🚨 Autonomous Loop Status: {snapshot.status.upper()}\n"
                        f"Cycles: {snapshot.cycles_completed}\n"
                        f"Errors (5min): {snapshot.errors_last_5min}\n"
                        f"Avg cycle time: {snapshot.avg_cycle_time_ms}ms"
                    )
            except Exception:
                pass

    def reset(self) -> None:
        self.stats = LoopStats()
        self._cycle_times.clear()
        self._status = "healthy"
        self._last_alert_status = None


# Global singleton
loop_health_monitor = LoopHealthMonitor()
