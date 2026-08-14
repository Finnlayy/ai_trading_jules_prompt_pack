"""Bar-by-bar backtest engine with zero future-leak guarantee.

Implements a strict iterative simulation where the strategy rule
only receives bars[0..i] at step i. This mirrors Pine Script v6
execution semantics.
"""

from __future__ import annotations

from typing import Any, Callable


def run_bar_by_bar_backtest(
    ohlc: list[list[float]],
    rule: Callable[[int, list[list[float]]], str | None],
    initial_balance: float = 1000.0,
    fee_pct: float = 0.0026,
) -> list[dict[str, Any]]:
    """Run a bar-by-bar backtest with strict no-future-leak enforcement.

    Args:
        ohlc: List of [time, open, high, low, close, volume] bars.
        rule: Function(rule_index, visible_bars) -> "BUY", "SELL", or None.
              visible_bars always contains bars[0..rule_index] ONLY.
        initial_balance: Starting USD balance.
        fee_pct: Taker fee applied to each trade.

    Returns:
        List of executed trade dicts.
    """
    balance = initial_balance
    position = 0.0  # positive = long, negative = short
    avg_entry = 0.0
    trades: list[dict[str, Any]] = []

    for i in range(len(ohlc)):
        # CRITICAL: Only pass bars up to current index — no future data
        visible_bars = ohlc[: i + 1]
        signal = rule(i, visible_bars)

        if signal is None:
            continue

        bar = ohlc[i]
        price = bar[4]  # close price at this bar

        if signal == "BUY" and position <= 0:
            # Enter long (or flip from short)
            if position < 0:
                # Close short first
                pnl = (avg_entry - price) * abs(position)
                balance += pnl
                trades.append({
                    "type": "CLOSE_SHORT",
                    "bar_index": i,
                    "price": price,
                    "pnl": round(pnl, 8),
                    "balance": round(balance, 8),
                })
                position = 0.0

            # Open long with 10% of balance per trade
            invest = balance * 0.1
            volume = invest / price
            fee = invest * fee_pct
            balance -= invest + fee
            position = volume
            avg_entry = price
            trades.append({
                "type": "BUY",
                "bar_index": i,
                "price": price,
                "volume": round(volume, 8),
                "fee": round(fee, 8),
                "balance": round(balance, 8),
            })

        elif signal == "SELL" and position >= 0:
            # Enter short (or flip from long)
            if position > 0:
                # Close long first
                pnl = (price - avg_entry) * position
                balance += pnl
                trades.append({
                    "type": "CLOSE_LONG",
                    "bar_index": i,
                    "price": price,
                    "pnl": round(pnl, 8),
                    "balance": round(balance, 8),
                })
                position = 0.0

            # Open short with 10% of balance
            invest = balance * 0.1
            volume = invest / price
            fee = invest * fee_pct
            balance -= invest + fee
            position = -volume
            avg_entry = price
            trades.append({
                "type": "SELL",
                "bar_index": i,
                "price": price,
                "volume": round(volume, 8),
                "fee": round(fee, 8),
                "balance": round(balance, 8),
            })

    return trades
