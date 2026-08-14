"""
ConfidenceRegistry — per-symbol, per-scout, per-direction accuracy tracking.

Stores historical performance metrics that get injected into scout prompts
to simulate "learning" across stateless LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

@dataclass
class ScoutReviewParams:
    symbol: str
    scout_name: str
    direction: str
    decision: str
    confidence: float
    was_correct: bool | None = None

from typing import Any
from app.schemas.academy import CareerEntry
from app.services.ai.gem_agents import DEFAULT_AGENT_NAMES
from app.services.agent_registry import agent_registry
import asyncio


@dataclass
class ScoutStats:
    """Performance stats for a single scout on a single symbol."""
    calls: int = 0
    approvals: int = 0
    rejections: int = 0
    avg_confidence: float = 0.0
    # Track when scout agreed with eventual outcome
    correct_calls: int = 0
    # Experience & specialization (new)
    experience: int = 0
    specialization_score: float = 0.0
    last_5_results: list[bool] = field(default_factory=list)

    def record_call(self, decision: str, confidence: float, was_correct: bool | None = None) -> None:
        self.calls += 1
        self.experience += 1
        if decision.upper() in {"PROCEED_TO_SIMULATION", "APPROVE"}:
            self.approvals += 1
        else:
            self.rejections += 1
        # Rolling average confidence
        self.avg_confidence = (self.avg_confidence * (self.calls - 1) + confidence) / self.calls
        if was_correct is not None and was_correct:
            self.correct_calls += 1
        # Update last 5 results window
        if was_correct is not None:
            self.last_5_results.append(was_correct)
            if len(self.last_5_results) > 5:
                self.last_5_results.pop(0)
        # Specialization = accuracy * log(experience), capped at 1.0
        import math
        exp_bonus = min(math.log10(max(self.experience, 1)) / 3.0, 1.0)
        self.specialization_score = self.accuracy * exp_bonus

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

    @property
    def recent_accuracy(self) -> float:
        """Accuracy over last 5 calls."""
        if not self.last_5_results:
            return self.accuracy
        return sum(self.last_5_results) / len(self.last_5_results)


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

    SCOUT_NAMES = list(DEFAULT_AGENT_NAMES)

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

    def record_scout_review(self, params: ScoutReviewParams) -> None:
        """Call after a scout renders its review."""
        stats = self.get_symbol_stats(params.symbol)
        if params.scout_name not in stats.scout_stats:
            stats.scout_stats[params.scout_name] = ScoutStats()
        stats.scout_stats[params.scout_name].record_call(params.decision, params.confidence, params.was_correct)
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
        auto_save: bool = True,
    ) -> None:
        """Call when a trade closes to update direction stats."""
        stats = self.get_symbol_stats(symbol)
        dstats = stats.get_direction_stats(direction)
        dstats.record_trade(pnl_pct, rr, win)
        if auto_save:
            self._save()

    def mark_scout_outcome(
        self,
        symbol: str,
        scout_names: list[str],
        was_correct: bool,
        details: dict[str, Any] | None = None,
        auto_save: bool = True,
    ) -> None:
        """
        Mark already-recorded scout calls as correct after a paper/live outcome is known.
        Also updates last_5_results and specialization_score.
        """
        stats = self.get_symbol_stats(symbol)
        changed = False
        for scout_name in scout_names:
            sstats = stats.scout_stats.get(scout_name)
            if not sstats or sstats.calls <= 0:
                continue
            if was_correct:
                if sstats.correct_calls < sstats.calls:
                    sstats.correct_calls += 1
                    changed = True
            # Always update last_5_results and specialization
            sstats.last_5_results.append(was_correct)
            if len(sstats.last_5_results) > 5:
                sstats.last_5_results.pop(0)
            import math
            exp_bonus = min(math.log10(max(sstats.experience, 1)) / 3.0, 1.0)
            sstats.specialization_score = sstats.accuracy * exp_bonus
            changed = True

            # Integrate with Agent Registry
            career_entry = CareerEntry(
                scout_name=scout_name,
                event_type="prediction_result",
                details={
                    **(details or {}),
                    "symbol": symbol,
                    "is_correct": was_correct,
                    "accuracy": sstats.accuracy,
                    "specialization": sstats.specialization_score
                }
            )
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(agent_registry.log_career_event(career_entry))
            except RuntimeError:
                asyncio.run(agent_registry.log_career_event(career_entry))
        if changed and auto_save:
            self._save()

    def save(self) -> None:
        """Public method to manually trigger save (useful for batching)."""
        self._save()

    def get_symbol_context(self, symbol: str, direction: str) -> str:
        """
        Build a concise context string for injection into scout prompts.
        Includes scout specialization scores and recent accuracy trends.
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

        for scout_name in self._context_scout_names(stats):
            sstats = stats.scout_stats.get(scout_name)
            if sstats and sstats.calls > 0:
                spec_label = ""
                if sstats.specialization_score >= 0.7:
                    spec_label = " [SPECIALIST]"
                elif sstats.specialization_score >= 0.4:
                    spec_label = " [TRAINED]"
                recent = ""
                if sstats.last_5_results:
                    recent_pct = sum(sstats.last_5_results) / len(sstats.last_5_results)
                    recent = f", recent: {recent_pct:.0%}"
                lines.append(
                    f"  {scout_name.title()} scout: {sstats.accuracy:.0%} accuracy "
                    f"({sstats.correct_calls}/{sstats.calls}), "
                    f"exp: {sstats.experience}{recent}{spec_label}"
                )

        if stats.total_signals > 0:
            lines.append(
                f"Historical avg confluence: {stats.avg_confluence:.1f}, "
                f"avg crisis: {stats.avg_crisis:.1f}"
            )

        return "\n".join(lines)

    def _context_scout_names(self, stats: SymbolStats) -> list[str]:
        names = list(self.SCOUT_NAMES)
        for scout_name in stats.scout_stats:
            if scout_name not in names:
                names.append(scout_name)
        return names

    def get_scout_weight(self, symbol: str, scout_name: str) -> float:
        """
        Return a weight (0.0–1.0) for a scout based on:
        - historical accuracy (base)
        - specialization score for this symbol (bonus)
        - recent performance (malus if <20%)
        Default 0.5 if no data.
        """
        stats = self.get_symbol_stats(symbol)
        sstats = stats.scout_stats.get(scout_name)
        if not sstats or sstats.calls < 3:
            return 0.5

        weight = sstats.accuracy

        # Specialization bonus: up to +0.15 for high specialization
        weight += min(sstats.specialization_score * 0.15, 0.15)

        # Recent performance malus: if last 5 are terrible, reduce weight
        if len(sstats.last_5_results) >= 3:
            recent = sum(sstats.last_5_results) / len(sstats.last_5_results)
            if recent < 0.2:
                weight -= 0.2
            elif recent < 0.4:
                weight -= 0.1

        return max(0.1, min(1.0, weight))

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

    def get_aggregate_stats(self) -> dict[str, Any]:
        """
        Aggregate performance metrics across all tracked symbols.
        Returns totals, weighted averages, and recency info.
        """
        import math

        total_signals = 0
        total_wins = 0
        total_losses = 0
        total_pnl_pct = 0.0
        total_trades = 0
        last_updated_ts: float | None = None

        for stats in self._symbols.values():
            total_signals += stats.total_signals
            for d in (stats.long_stats, stats.short_stats):
                total_wins += d.wins
                total_losses += d.losses
                total_pnl_pct += d.total_pnl_pct
                total_trades += d.total
            if stats.last_updated:
                try:
                    ts = datetime.fromisoformat(stats.last_updated).timestamp()
                    if last_updated_ts is None or ts > last_updated_ts:
                        last_updated_ts = ts
                except (ValueError, TypeError):
                    pass

        win_rate = total_wins / total_trades if total_trades > 0 else 0.0
        avg_pnl_pct = total_pnl_pct / total_trades if total_trades > 0 else 0.0

        # Profit factor proxy using avg pnl per win/loss
        gross_wins = max(avg_pnl_pct * total_wins, 0.01) if total_wins > 0 else 0.0
        gross_losses = max(abs(avg_pnl_pct) * total_losses, 0.01) if total_losses > 0 else 0.0
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else 0.0

        # Max drawdown proxy: worst total_pnl_pct among symbols
        max_dd = 0.0
        for stats in self._symbols.values():
            for d in (stats.long_stats, stats.short_stats):
                if d.total > 0 and d.total_pnl_pct < max_dd:
                    max_dd = d.total_pnl_pct

        now = datetime.now(timezone.utc).timestamp()
        last_signal_age_seconds = now - last_updated_ts if last_updated_ts else None

        # Composite health score (0-100)
        # 40% win_rate, 20% profit_factor, 20% recency, 20% volume
        score = 0.0
        if total_trades > 0:
            score += min(win_rate * 100, 40)  # win_rate * 100, capped at 40
            score += min(profit_factor * 20, 20)  # pf * 20, capped at 20
            if last_signal_age_seconds is not None:
                recency_score = max(0, 20 - (last_signal_age_seconds / 3600))  # decays over 20h
                score += recency_score
            volume_score = min(total_trades / 10, 20)  # 20 trades = full score
            score += volume_score
        score = round(max(0.0, min(100.0, score)), 1)

        return {
            "total_signals": total_signals,
            "total_trades": total_trades,
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
            "avg_pnl_pct": round(avg_pnl_pct, 4),
            "max_drawdown_pct": round(abs(max_dd), 4),
            "last_signal_age_seconds": last_signal_age_seconds,
            "health_score": score,
        }


# Singleton instance
confidence_registry = ConfidenceRegistry()
