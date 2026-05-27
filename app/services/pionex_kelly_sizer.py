from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.m8_payload import M8Payload


@dataclass(frozen=True)
class KellyConfig:
    deploy_mode: str = "half"
    lookback_trades: int = 50
    min_trades: int = 20
    fixed_risk_pct: float = 1.0
    min_risk_pct: float = 0.2
    max_risk_pct: float = 2.0
    payoff_buffer: float = 0.0
    min_order_usdt: float = 5.0
    max_order_usdt: float = 200.0
    min_base_size: float = 0.0001
    max_base_size: float = 10.0


@dataclass(frozen=True)
class KellySizingResult:
    risk_pct: float
    risk_amount: float
    size_base: float
    order_value_usdt: float
    kelly_fraction: float
    mode: str
    history_trades: int
    win_rate: float
    avg_win_r: float
    avg_loss_r: float


class KellySizer:
    def __init__(self, config: KellyConfig, journal_path: str = "trade_journal.jsonl") -> None:
        self.config = config
        self.journal_path = Path(journal_path)

    def _load_realized_returns(self) -> list[float]:
        if not self.journal_path.exists():
            return []

        realized_r: list[float] = []
        with self.journal_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("final_decision") != "EXECUTED_SIM":
                    continue
                result = entry.get("result") or {}
                if not result.get("status", "").startswith("CLOSED"):
                    continue
                pnl = result.get("realized_pnl_quote")
                risk_amount = result.get("risk_amount")
                try:
                    pnl_f = float(pnl)
                    risk_f = float(risk_amount)
                except (TypeError, ValueError):
                    continue
                if risk_f <= 0:
                    continue
                realized_r.append(pnl_f / risk_f)

        if self.config.lookback_trades <= 0:
            return realized_r
        return realized_r[-self.config.lookback_trades :]

    def _kelly_fraction(self) -> tuple[float, int, float, float, float]:
        samples = self._load_realized_returns()
        trade_count = len(samples)
        if trade_count < self.config.min_trades:
            return 0.0, trade_count, 0.0, 0.0, 0.0

        winners = [value for value in samples if value > 0]
        losers = [value for value in samples if value <= 0]

        if not winners or not losers:
            return 0.0, trade_count, 0.0, 0.0, 0.0

        win_rate = len(winners) / trade_count
        avg_win_r = sum(winners) / len(winners)
        avg_loss_r = abs(sum(losers) / len(losers))
        if avg_loss_r <= 0:
            return 0.0, trade_count, win_rate, avg_win_r, avg_loss_r

        payoff_ratio = max((avg_win_r / avg_loss_r) - self.config.payoff_buffer, 0.0001)
        kelly = win_rate - ((1.0 - win_rate) / payoff_ratio)
        return max(kelly, 0.0), trade_count, win_rate, avg_win_r, avg_loss_r

    def _deployed_risk_pct(self, kelly_fraction: float, risk_cap_pct: float | None = None) -> float:
        mode = self.config.deploy_mode
        if mode == "fixed":
            risk_pct = self.config.fixed_risk_pct
        elif mode == "full":
            risk_pct = kelly_fraction * 100.0
        else:  # default half-kelly
            risk_pct = (kelly_fraction * 0.5) * 100.0

        max_risk = self.config.max_risk_pct
        if risk_cap_pct is not None:
            max_risk = min(max_risk, risk_cap_pct)
        return min(max(risk_pct, self.config.min_risk_pct), max_risk)

    def _stop_distance(self, payload: M8Payload) -> float:
        if payload.direction == "LONG":
            return payload.entry_price - payload.stop_price
        return payload.stop_price - payload.entry_price

    def size_trade(
        self,
        payload: M8Payload,
        balance: float,
        risk_cap_pct: float | None = None,
    ) -> KellySizingResult:
        kelly_fraction, history_trades, win_rate, avg_win_r, avg_loss_r = self._kelly_fraction()
        risk_pct = self._deployed_risk_pct(kelly_fraction, risk_cap_pct=risk_cap_pct)
        risk_amount = max(balance * (risk_pct / 100.0), 0.0)

        stop_distance = self._stop_distance(payload)
        if stop_distance <= 0:
            size_base = self.config.min_base_size
        else:
            size_base = risk_amount / stop_distance

        size_base = min(max(size_base, self.config.min_base_size), self.config.max_base_size)
        order_value = size_base * payload.entry_price

        if order_value < self.config.min_order_usdt and payload.entry_price > 0:
            size_base = self.config.min_order_usdt / payload.entry_price
            order_value = self.config.min_order_usdt

        if order_value > self.config.max_order_usdt and payload.entry_price > 0:
            size_base = self.config.max_order_usdt / payload.entry_price
            order_value = self.config.max_order_usdt

        size_base = min(max(size_base, self.config.min_base_size), self.config.max_base_size)
        order_value = size_base * payload.entry_price

        return KellySizingResult(
            risk_pct=risk_pct,
            risk_amount=risk_amount,
            size_base=size_base,
            order_value_usdt=order_value,
            kelly_fraction=kelly_fraction,
            mode=self.config.deploy_mode,
            history_trades=history_trades,
            win_rate=win_rate,
            avg_win_r=avg_win_r,
            avg_loss_r=avg_loss_r,
        )
