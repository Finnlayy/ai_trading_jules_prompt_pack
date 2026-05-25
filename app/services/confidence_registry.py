"""
ConfidenceRegistry — per-symbol, per-scout, per-direction accuracy tracking.

Stores historical performance metrics that get injected into scout prompts
to simulate "learning" across stateless LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ScoutStats:
    """Performance stats for a single scout on a single symbol."""
    calls: int = 0
    approvals: int = 0
    rejections: int = 0
    avg_confidence: float = 0.0
    # Track when scout agreed with eventual outcome
    correct_calls: int = 0

    def record_call(self, decision: str, confidence: float, was_correct: bool | None = None) -> None:
        self.calls += 1
        if decision.upper() in {"PROCEED_TO_SIMULATION", "APPROVE"}:
            self.approvals += 1
        else:
            self.rejections += 1
        # Rolling average confidence
        self.avg_confidence = (self.avg_confidence * (self.calls - 1) + confidence) / self.calls
        if was_correct is not None and was_correct:
            self.correct_calls += 1

    @property
    def accuracy(self) -> float:
        if self.calls == 0:
            return 0.5
        return self.correct_calls / self.calls

    @property
    def approval_rate(self) -> float:
        if self.calls == 0:
            return 0.5
        return self.approvals / self.calls


@dataclass
class DirectionStats:
    """Performance stats for a symbol+direction combo."""
    total: int = 0
    wins: int = 0
    losses: int = 0
    avg_pnl_pct: float = 0.0
    avg_rr: float = 0.0
    total_pnl_pct: float = 0.0

    def record_trade(self, pnl_pct: float, rr: float, win: bool) -> None:
        self.total += 1
        if win:
            self.wins += 1
        else:
            self.losses += 1
        self.total_pnl_pct += pnl_pct
        self.avg_pnl_pct = self.total_pnl_pct / self.total
        self.avg_rr = (self.avg_rr * (self.total - 1) + rr) / self.total

    @property
    def win_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.wins / self.total

    @property
    def profit_factor(self) -> float:
        if self.total == 0 or self.losses == 0:
            return 0.0
        gross_profit = sum([1 for _ in range(self.wins)])  # simplified
        # Real PF needs actual PnL amounts; we use a proxy
        wins_pnl = max(self.avg_pnl_pct * self.wins, 0.01)
        losses_pnl = max(abs(self.avg_pnl_pct * self.losses), 0.01)
        return wins_pnl / losses_pnl if losses_pnl > 0 else wins_pnl


@dataclass
class SymbolStats:
    """All stats for a single symbol."""
    symbol: str
    total_signals: int = 0
    scout_stats: dict[str, ScoutStats] = field(default_factory=dict)
    long_stats: DirectionStats = field(default_factory=lambda: DirectionStats())
    short_stats: DirectionStats = field(default_factory=lambda: DirectionStats())
    avg_confluence: float = 0.0
    avg_crisis: float = 0.0
    last_updated: str = ""

    def get_direction_stats(self, direction: str) -> DirectionStats:
        if direction.upper() == "LONG":
            return self.long_stats
        return self.short_stats

    def record_signal(self, confluence: float, crisis: float) -> None:
        self.total_signals += 1
        self.avg_confluence = (self.avg_confluence * (self.total_signals - 1) + confluence) / self.total_signals
        self.avg_crisis = (self.avg_crisis * (self.total_signals - 1) + crisis) / self.total_signals


class ConfidenceRegistry:
    """
    JSON-backed registry for per-symbol scout confidence tracking.
    File: logs/confidence_registry.json
    """

    SCOUT_NAMES = ["technical", "sentiment", "risk", "macro"]

    def __init__(self, filepath: str = "logs/confidence_registry.json") -> None:
        self.filepath = Path(filepath)
        self._symbols: dict[str, SymbolStats] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self.filepath.exists():
            return
        try:
            raw = json.loads(self.filepath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        if not isinstance(raw, dict):
            return

        for symbol, data in raw.items():
            self._symbols[symbol] = self._deserialize_symbol(data)

    def _save(self) -> None:
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        payload = {sym: self._serialize_symbol(stats) for sym, stats in self._symbols.items()}
        self.filepath.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _serialize_symbol(stats: SymbolStats) -> dict[str, Any]:
        return {
            "symbol": stats.symbol,
            "total_signals": stats.total_signals,
            "scout_stats": {k: asdict(v) for k, v in stats.scout_stats.items()},
            "long_stats": asdict(stats.long_stats),
            "short_stats": asdict(stats.short_stats),
            "avg_confluence": stats.avg_confluence,
            "avg_crisis": stats.avg_crisis,
            "last_updated": stats.last_updated,
        }

    @staticmethod
    def _deserialize_symbol(data: dict[str, Any]) -> SymbolStats:
        ss = SymbolStats(symbol=data.get("symbol", "UNKNOWN"))
        ss.total_signals = data.get("total_signals", 0)
        ss.avg_confluence = data.get("avg_confluence", 0.0)
        ss.avg_crisis = data.get("avg_crisis", 0.0)
        ss.last_updated = data.get("last_updated", "")
        for name, sdata in data.get("scout_stats", {}).items():
            ss.scout_stats[name] = ScoutStats(**sdata)
        if "long_stats" in data:
            ss.long_stats = DirectionStats(**data["long_stats"])
        if "short_stats" in data:
            ss.short_stats = DirectionStats(**data["short_stats"])
        return ss

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_symbol_stats(self, symbol: str) -> SymbolStats:
        symbol = symbol.upper()
        if symbol not in self._symbols:
            self._symbols[symbol] = SymbolStats(symbol=symbol)
        return self._symbols[symbol]

    def record_scout_review(
        self,
        symbol: str,
        scout_name: str,
        direction: str,
        decision: str,
        confidence: float,
        was_correct: bool | None = None,
    ) -> None:
        """Call after a scout renders its review."""
        stats = self.get_symbol_stats(symbol)
        if scout_name not in stats.scout_stats:
            stats.scout_stats[scout_name] = ScoutStats()
        stats.scout_stats[scout_name].record_call(decision, confidence, was_correct)
        self._save()

    def record_signal_review(
        self,
        symbol: str,
        confluence: float,
        crisis: float,
        direction: str,
    ) -> None:
        """Call once per signal after all scouts have reviewed."""
        stats = self.get_symbol_stats(symbol)
        stats.record_signal(confluence, crisis)
        self._save()

    def record_trade_outcome(
        self,
        symbol: str,
        direction: str,
        pnl_pct: float,
        rr: float,
        win: bool,
    ) -> None:
        """Call when a trade closes to update direction stats."""
        stats = self.get_symbol_stats(symbol)
        dstats = stats.get_direction_stats(direction)
        dstats.record_trade(pnl_pct, rr, win)
        self._save()

    def mark_scout_outcome(
        self,
        symbol: str,
        scout_names: list[str],
        was_correct: bool,
    ) -> None:
        """
        Mark already-recorded scout calls as correct after a paper/live outcome is known.

        Scout calls are recorded when the LLM review runs. Paper replay learns later, when
        a virtual trade closes, so this method updates correctness without double-counting
        another scout call.
        """
        stats = self.get_symbol_stats(symbol)
        if not was_correct:
            return
        changed = False
        for scout_name in scout_names:
            sstats = stats.scout_stats.get(scout_name)
            if not sstats or sstats.calls <= 0:
                continue
            if sstats.correct_calls < sstats.calls:
                sstats.correct_calls += 1
                changed = True
        if changed:
            self._save()

    def get_symbol_context(self, symbol: str, direction: str) -> str:
        """
        Build a concise context string for injection into scout prompts.
        Example:
          "Symbol: BTCUSDT | Direction: LONG | 12 signals reviewed.
           LONG win rate: 68% (8W/4L), avg RR: 2.3, avg PnL: +1.2%.
           Technical scout accuracy: 75% (9/12), Risk scout: 67% (8/12)."
        """
        stats = self.get_symbol_stats(symbol)
        d = stats.get_direction_stats(direction)
        lines = [
            f"Symbol: {symbol} | Direction: {direction.upper()}",
            f"Total signals reviewed: {stats.total_signals}",
        ]

        if d.total > 0:
            lines.append(
                f"{direction.upper()} track record: {d.win_rate:.0%} win rate "
                f"({d.wins}W/{d.losses}L), avg RR: {d.avg_rr:.2f}, avg PnL: {d.avg_pnl_pct:+.2f}%"
            )

        for scout_name in self.SCOUT_NAMES:
            sstats = stats.scout_stats.get(scout_name)
            if sstats and sstats.calls > 0:
                lines.append(
                    f"  {scout_name.title()} scout: {sstats.accuracy:.0%} accuracy "
                    f"({sstats.correct_calls}/{sstats.calls}), "
                    f"avg confidence: {sstats.avg_confidence:.2f}"
                )

        if stats.total_signals > 0:
            lines.append(
                f"Historical avg confluence: {stats.avg_confluence:.1f}, "
                f"avg crisis: {stats.avg_crisis:.1f}"
            )

        return "\n".join(lines)

    def get_scout_weight(self, symbol: str, scout_name: str) -> float:
        """
        Return a weight (0.0–1.0) for a scout based on its historical accuracy
        for this symbol. Default 0.5 if no data.
        """
        stats = self.get_symbol_stats(symbol)
        sstats = stats.scout_stats.get(scout_name)
        if not sstats or sstats.calls < 3:
            return 0.5
        return sstats.accuracy

    def reset_symbol(self, symbol: str) -> None:
        symbol = symbol.upper()
        if symbol in self._symbols:
            del self._symbols[symbol]
            self._save()

    def reset_all(self) -> None:
        self._symbols.clear()
        self._save()

    def dump(self) -> dict[str, Any]:
        return {sym: self._serialize_symbol(stats) for sym, stats in self._symbols.items()}


# Singleton instance
confidence_registry = ConfidenceRegistry()
