"""
Performance Calculator — computes trading metrics from journal entries and live fills.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Sequence

from app.schemas.journal import TradeJournalEntry


@dataclass
class PerformanceMetrics:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    winrate_pct: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_start_idx: int = 0
    max_drawdown_end_idx: int = 0
    total_pnl: float = 0.0
    avg_trade_pnl: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    largest_winner: float = 0.0
    largest_loser: float = 0.0
    avg_holding_time_minutes: float = 0.0
    calculated_at: str = ""


def _safe_div(num: float, den: float) -> float:
    return num / den if den != 0 else 0.0


class PerformanceCalculator:
    """Calculate performance metrics from a list of completed trades."""

    def calculate_metrics(
        self,
        trades: Sequence[TradeJournalEntry],
        risk_free_rate: float = 0.0,
    ) -> PerformanceMetrics:
        if not trades:
            return PerformanceMetrics(calculated_at=datetime.now(timezone.utc).isoformat())

        pnls: List[float] = []
        winners: List[float] = []
        losers: List[float] = []
        holding_times: List[float] = []

        for t in trades:
            pnl = self._extract_pnl(t)
            if pnl is None:
                continue
            pnls.append(pnl)
            if pnl > 0:
                winners.append(pnl)
            elif pnl < 0:
                losers.append(pnl)
            # Holding time estimation from result timestamp if available
            ht = self._extract_holding_time(t)
            if ht is not None:
                holding_times.append(ht)

        total = len(pnls)
        if total == 0:
            return PerformanceMetrics(calculated_at=datetime.now(timezone.utc).isoformat())

        total_pnl = sum(pnls)
        equity_curve = self._build_equity_curve(pnls)
        max_dd, dd_start, dd_end = self._calculate_max_drawdown(equity_curve)

        returns = [p / 1000.0 for p in pnls]  # Normalize for Sharpe

        return PerformanceMetrics(
            total_trades=total,
            winning_trades=len(winners),
            losing_trades=len(losers),
            winrate_pct=round(_safe_div(len(winners), total) * 100, 2),
            profit_factor=round(_safe_div(sum(winners), abs(sum(losers))), 3),
            expectancy=round(_safe_div(total_pnl, total), 4),
            sharpe_ratio=round(self._sharpe(returns, risk_free_rate), 3),
            sortino_ratio=round(self._sortino(returns), 3),
            max_drawdown_pct=round(max_dd, 3),
            max_drawdown_start_idx=dd_start,
            max_drawdown_end_idx=dd_end,
            total_pnl=round(total_pnl, 4),
            avg_trade_pnl=round(_safe_div(total_pnl, total), 4),
            avg_winner=round(_safe_div(sum(winners), len(winners)), 4),
            avg_loser=round(_safe_div(sum(losers), len(losers)), 4),
            largest_winner=round(max(winners, default=0.0), 4),
            largest_loser=round(min(losers, default=0.0), 4),
            avg_holding_time_minutes=round(_safe_div(sum(holding_times), len(holding_times)), 2),
            calculated_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _extract_pnl(entry: TradeJournalEntry) -> float | None:
        """Best-effort PnL extraction from journal entry."""
        if entry.result and "pnl" in entry.result:
            return float(entry.result["pnl"])
        if entry.simulated_fill and "pnl" in entry.simulated_fill:
            return float(entry.simulated_fill["pnl"])
        # Approximate from prices if available
        if entry.entry_price and entry.exit_price:
            # Direction unknown in journal; try to infer from payload if present
            return None
        return None

    @staticmethod
    def _extract_holding_time(entry: TradeJournalEntry) -> float | None:
        """Holding time in minutes, if timestamps available."""
        # Journal entries don't currently store open/close times separately
        return None

    @staticmethod
    def _build_equity_curve(pnls: List[float]) -> List[float]:
        curve = [0.0]
        for p in pnls:
            curve.append(curve[-1] + p)
        return curve

    @staticmethod
    def _calculate_max_drawdown(equity_curve: List[float]) -> tuple[float, int, int]:
        peak = equity_curve[0]
        peak_idx = 0
        max_dd = 0.0
        dd_start = 0
        dd_end = 0

        for i, val in enumerate(equity_curve):
            if val > peak:
                peak = val
                peak_idx = i
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
                dd_start = peak_idx
                dd_end = i

        # Express as percentage of peak
        pct = _safe_div(max_dd, peak) * 100 if peak > 0 else 0.0
        return pct, dd_start, dd_end

    @staticmethod
    def _sharpe(returns: List[float], risk_free_rate: float = 0.0) -> float:
        if not returns:
            return 0.0
        excess = [r - risk_free_rate for r in returns]
        avg = sum(excess) / len(excess)
        std = math.sqrt(sum((x - avg) ** 2 for x in excess) / len(excess))
        return _safe_div(avg, std) * math.sqrt(252)  # Annualized

    @staticmethod
    def _sortino(returns: List[float]) -> float:
        if not returns:
            return 0.0
        avg = sum(returns) / len(returns)
        downside = [r for r in returns if r < 0]
        if not downside:
            return float("inf") if avg > 0 else 0.0
        downside_std = math.sqrt(sum(r ** 2 for r in downside) / len(downside))
        return _safe_div(avg, downside_std) * math.sqrt(252)

    def calculate_equity_curve_data(
        self,
        trades: Sequence[TradeJournalEntry],
    ) -> List[dict]:
        """Return equity curve points for charting."""
        pnls = []
        for t in trades:
            pnl = self._extract_pnl(t)
            if pnl is not None:
                pnls.append(pnl)

        curve = self._build_equity_curve(pnls)
        return [
            {"trade_idx": i, "equity": round(e, 4)}
            for i, e in enumerate(curve)
        ]


# Global singleton
performance_calculator = PerformanceCalculator()
