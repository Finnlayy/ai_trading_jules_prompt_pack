"""
Autonomous Trading Loop — background task that polls market data,
generates signals, and routes them through the full M8 pipeline.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from app.core.config import (
    AUTONOMOUS_LOOP_ENABLED,
    AUTONOMOUS_LOOP_POLL_INTERVAL_SECONDS,
    AUTONOMOUS_LOOP_MAX_ERRORS_5MIN,
    AUTONOMOUS_LOOP_PAUSE_ON_ERROR_COUNT,
    AUTONOMOUS_LOOP_ERROR_PAUSE_SECONDS,
    AUTONOMOUS_LOOP_STRATEGY_ROTATION_ENABLED,
    BROKER_MODE,
)
from app.schemas.m8_payload import M8Payload
from app.services.last_processed_bar_store import LastProcessedBarStore, last_processed_bar_store
from app.services.signal_generator import BybitDataFeed, SignalGenerator
from app.services.strategy_engine import strategy_registry
from app.services.watchlist_manager import WatchlistManager, WatchlistItem, watchlist_manager
from app.services.loop_health_monitor import LoopHealthMonitor
from app.services.regime_engine import regime_engine_instance


@dataclass
class StrategyRotationLog:
    symbol: str
    old_strategy: str
    new_strategy: str
    regime: str
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AutonomousTradingLoop:
    """
    Asyncio-based background trading loop.
    Polls symbols from the watchlist, generates candidates, and executes
    them through the paper-training pipeline.
    """

    def __init__(self) -> None:
        self.is_running = False
        self.is_paused = False
        self.poll_interval = AUTONOMOUS_LOOP_POLL_INTERVAL_SECONDS
        self._task: asyncio.Task | None = None
        self._watchlist = watchlist_manager
        self._health = LoopHealthMonitor()
        self._generator = SignalGenerator()
        self._processed_bars: LastProcessedBarStore = last_processed_bar_store
        self._last_poll_times: dict[str, datetime] = {}
        self._rotation_log: List[StrategyRotationLog] = []
        self._error_timestamps: List[float] = []

    # -- Public control API -------------------------------------------------

    def start(self) -> None:
        if not AUTONOMOUS_LOOP_ENABLED:
            raise RuntimeError("Autonomous loop is disabled in configuration")
        if self.is_running:
            return
        self.is_running = True
        self.is_paused = False
        self._task = asyncio.create_task(self._run_loop())

    def stop(self) -> None:
        self.is_running = False
        self.is_paused = False
        if self._task:
            self._task.cancel()
            self._task = None

    def pause(self) -> None:
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False

    def get_status(self) -> dict[str, Any]:
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "active_symbols": [item.symbol for item in self._watchlist.get_active()],
            "poll_interval_seconds": self.poll_interval,
            "loop_stats": {
                "cycles_completed": self._health.stats.cycles_completed,
                "signals_generated": self._health.stats.signals_generated,
                "trades_executed": self._health.stats.trades_executed,
                "errors_last_5min": self._health.stats.errors_last_5min,
            },
            "health": self._health.update_status(
                self.is_running and not self.is_paused
            ).__dict__,
            "current_strategy_id": strategy_registry.active_strategy_id,
            "last_generation_summary": getattr(self._generator, "last_generation_summary", {}),
            "last_processed_bars": self._processed_bars.dump(),
        }

    def get_rotation_log(self) -> List[dict]:
        return [log.__dict__ for log in self._rotation_log[-50:]]

    # -- Loop internals -----------------------------------------------------

    async def _run_loop(self) -> None:
        while self.is_running:
            if self.is_paused:
                await asyncio.sleep(1)
                continue

            cycle_start = time.perf_counter()

            try:
                await self._run_single_cycle()
                self._health.stats.record_cycle()
                self._health.record_cycle_time((time.perf_counter() - cycle_start) * 1000)
            except Exception as exc:
                self._health.stats.record_error(str(exc))
                self._record_error()
                if self._should_pause_on_errors():
                    await asyncio.sleep(AUTONOMOUS_LOOP_ERROR_PAUSE_SECONDS)
                if self._should_halt_on_errors():
                    self.is_running = False
                    break

            # Reset error window periodically
            self._prune_old_errors()

            await asyncio.sleep(self._calculate_sleep_interval())

    async def _run_single_cycle(self) -> None:
        active_items = self._watchlist.get_active()
        if not active_items:
            return

        for item in active_items:
            if not self.is_running or self.is_paused:
                break

            for tf in item.timeframes:
                if not self._should_poll(item.symbol, tf):
                    continue

                # Regime check + optional strategy rotation
                if AUTONOMOUS_LOOP_STRATEGY_ROTATION_ENABLED:
                    await self._check_strategy_rotation(item)

                # Generate at most one live-paper candidate from the latest
                # closed candle. Historical replay belongs in backtests.
                try:
                    last_processed_ts = self._processed_bars.get(item.symbol, tf)
                    payload = self._generator.generate_latest_candidate(
                        symbol=item.symbol,
                        timeframe=tf,
                        bars=200,
                        min_confluence=item.min_confluence,
                        last_processed_ts=last_processed_ts,
                    )
                except Exception as exc:
                    self._health.stats.record_error(f"Signal generation failed for {item.symbol}: {exc}")
                    continue

                summary = getattr(self._generator, "last_generation_summary", {}) or {}
                latest_ts = summary.get("last_closed_bar_ts")

                if payload:
                    self._health.stats.record_signal()
                    await self._execute_payloads([payload])

                if self._processed_bars.should_process(item.symbol, tf, latest_ts):
                    self._processed_bars.mark_processed(item.symbol, tf, int(latest_ts))

                self._last_poll_times[f"{item.symbol}:{tf}"] = datetime.now(timezone.utc)

    async def _execute_payloads(self, payloads: list[M8Payload]) -> None:
        from app.services.paper_training_pipeline import paper_training_pipeline

        for payload in payloads:
            if not self.is_running or self.is_paused:
                break
            try:
                result = await paper_training_pipeline.process_candidate(payload)
                if result.get("final_decision") == "PAPER_EXECUTED":
                    self._health.stats.record_trade()
            except Exception as exc:
                self._health.stats.record_error(f"Execution failed for {payload.signal_id}: {exc}")

    async def _check_strategy_rotation(self, item: WatchlistItem) -> None:
        """Rotate strategy based on current market regime."""
        try:
            bars = await asyncio.to_thread(
                BybitDataFeed.fetch,
                item.symbol,
                bars=50,
                timeframe=item.timeframes[0] if item.timeframes else "1h",
            )
            if not bars or len(bars) < 30:
                return

            closes = [bar.c for bar in bars]
            regime_result = regime_engine_instance.should_trade(closes)
            regime = regime_result.get("regime", "UNKNOWN")

            recommended = self._regime_to_strategy(str(regime))
            if recommended and recommended != strategy_registry.active_strategy_id:
                old = strategy_registry.active_strategy_id
                strategy_registry.set_active_strategy(recommended)
                self._rotation_log.append(
                    StrategyRotationLog(
                        symbol=item.symbol,
                        old_strategy=old,
                        new_strategy=recommended,
                        regime=str(regime),
                        reason=f"Regime changed to {regime}",
                    )
                )
        except Exception:
            pass

    @staticmethod
    def _regime_to_strategy(regime: str) -> str | None:
        mapping = {
            "INEFFICIENT_TREND": "pattern_enhanced",
            "RW3_HETEROSKEDASTIC": "pattern_enhanced",
            "INEFFICIENT_MEAN_REVERSION": "default",
            "RW2_WEAK_EFFICIENT": "default",
            "RW1_EFFICIENT": "default",
            "UNKNOWN": None,
        }
        return mapping.get(regime)

    def _should_poll(self, symbol: str, timeframe: str) -> bool:
        key = f"{symbol}:{timeframe}"
        last = self._last_poll_times.get(key)
        if last is None:
            return True
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed >= self.poll_interval

    def _calculate_sleep_interval(self) -> float:
        active = len(self._watchlist.get_active())
        if active == 0:
            return self.poll_interval
        # Respect Bybit rate limit: 120 req/min
        min_interval = max(self.poll_interval, 60.0 / (120.0 / max(1, active)))
        return min_interval

    def _record_error(self) -> None:
        self._error_timestamps.append(time.time())

    def _prune_old_errors(self) -> None:
        cutoff = time.time() - 300  # 5 minutes
        self._error_timestamps = [t for t in self._error_timestamps if t > cutoff]
        self._health.stats.reset_error_window()
        self._health.stats.errors_last_5min = len(self._error_timestamps)

    def _should_pause_on_errors(self) -> bool:
        return len(self._error_timestamps) >= AUTONOMOUS_LOOP_PAUSE_ON_ERROR_COUNT

    def _should_halt_on_errors(self) -> bool:
        return len(self._error_timestamps) >= AUTONOMOUS_LOOP_MAX_ERRORS_5MIN


# Global singleton
autonomous_loop_instance = AutonomousTradingLoop()
