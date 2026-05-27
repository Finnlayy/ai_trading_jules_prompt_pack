"""
Portfolio Circuit Breaker — daily drawdown and loss-limit protection.

Tracks realized PnL from the trade journal, maintains a high-watermark,
and halts new entries when MAX_DAILY_DRAWDOWN_PCT is breached.

State persists to logs/portfolio_circuit_breaker.json so restarts
do not reset protection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import MAX_DAILY_DRAWDOWN


@dataclass
class CircuitState:
    date: str  # "YYYY-MM-DD"
    starting_balance: float = 0.0  # set externally from wallet
    high_watermark: float = 0.0
    realized_pnl: float = 0.0
    trades_count: int = 0
    halted: bool = False
    halt_reason: str = ""
    last_updated: str = ""


class PortfolioCircuitBreaker:
    """
    Daily portfolio-level circuit breaker.
    """

    def __init__(
        self,
        max_daily_drawdown_pct: float = MAX_DAILY_DRAWDOWN,
        filepath: str = "logs/portfolio_circuit_breaker.json",
    ) -> None:
        self.max_dd_pct = max_daily_drawdown_pct
        self.filepath = Path(filepath)
        self._state = self._load_or_init()

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load_or_init(self) -> CircuitState:
        if not self.filepath.exists():
            return CircuitState(date=self._today())
        try:
            raw = json.loads(self.filepath.read_text(encoding="utf-8"))
            state = CircuitState(**raw)
        except (json.JSONDecodeError, TypeError):
            return CircuitState(date=self._today())

        # Auto-reset if date rolled over
        if state.date != self._today():
            return CircuitState(date=self._today())
        return state

    def _save(self) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._state.last_updated = datetime.now(timezone.utc).isoformat()
        self.filepath.write_text(json.dumps(asdict(self._state), indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_starting_balance(self, balance: float) -> None:
        """Call once at startup with current wallet balance."""
        if self._state.starting_balance <= 0:
            self._state.starting_balance = balance
            self._state.high_watermark = balance
            self._save()

    def record_trade_pnl(self, pnl: float) -> dict[str, Any]:
        """
        Record a closed trade's realized PnL.
        Returns {trade_allowed, drawdown_pct, halt_triggered, reason}.
        """
        today = self._today()
        if self._state.date != today:
            # Reset for new day
            prev_balance = self._state.starting_balance + self._state.realized_pnl
            self._state = CircuitState(
                date=today,
                starting_balance=prev_balance,
                high_watermark=prev_balance,
            )

        self._state.realized_pnl += pnl
        self._state.trades_count += 1

        # Update high watermark
        current_equity = self._state.starting_balance + self._state.realized_pnl
        if current_equity > self._state.high_watermark:
            self._state.high_watermark = current_equity

        # Calculate drawdown from high watermark
        if self._state.high_watermark > 0:
            dd_pct = (self._state.high_watermark - current_equity) / self._state.high_watermark * 100.0
        else:
            dd_pct = 0.0

        # Check halt
        if not self._state.halted and dd_pct >= self.max_dd_pct:
            self._state.halted = True
            self._state.halt_reason = f"Daily drawdown {dd_pct:.2f}% >= limit {self.max_dd_pct:.2f}%"
            self._save()
            return {
                "trade_allowed": False,
                "drawdown_pct": round(dd_pct, 2),
                "halt_triggered": True,
                "reason": self._state.halt_reason,
            }

        self._save()
        return {
            "trade_allowed": not self._state.halted,
            "drawdown_pct": round(dd_pct, 2),
            "halt_triggered": False,
            "reason": self._state.halt_reason if self._state.halted else "",
        }

    def check_trade_allowed(self) -> dict[str, Any]:
        """Check if new trades are permitted right now."""
        today = self._today()
        if self._state.date != today:
            return {"trade_allowed": True, "drawdown_pct": 0.0, "halted": False, "reason": ""}

        if self._state.halted:
            return {
                "trade_allowed": False,
                "drawdown_pct": self._current_drawdown_pct(),
                "halted": True,
                "reason": self._state.halt_reason,
            }

        dd_pct = self._current_drawdown_pct()
        return {
            "trade_allowed": True,
            "drawdown_pct": round(dd_pct, 2),
            "halted": False,
            "reason": "",
        }

    def _current_drawdown_pct(self) -> float:
        current_equity = self._state.starting_balance + self._state.realized_pnl
        if self._state.high_watermark > 0:
            return (self._state.high_watermark - current_equity) / self._state.high_watermark * 100.0
        return 0.0

    def reset(self) -> None:
        self._state = CircuitState(date=self._today())
        self._save()

    def get_state(self) -> dict[str, Any]:
        return asdict(self._state)


# Global instance
circuit_breaker_instance = PortfolioCircuitBreaker()
