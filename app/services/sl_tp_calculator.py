"""SL/TP Calculator — default risk:reward levels for paper positions."""

from __future__ import annotations

from typing import Optional


def calculate_sl_tp(
    entry_price: float,
    direction: str,
    risk_pct: float = 0.02,
    reward_risk_ratio: float = 2.0,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
) -> tuple[float, float]:
    """Calculate or validate stop-loss and take-profit levels.

    Args:
        entry_price: Position entry price
        direction: "LONG" or "SHORT"
        risk_pct: Percentage of entry price to risk (default 2%)
        reward_risk_ratio: Reward-to-risk ratio (default 2:1)
        stop_loss: Optional explicit SL level
        take_profit: Optional explicit TP level

    Returns:
        Tuple of (stop_loss, take_profit) prices
    """
    dir_norm = direction.upper()

    if stop_loss is not None and take_profit is not None:
        return (stop_loss, take_profit)

    risk_amount = entry_price * risk_pct

    if dir_norm == "LONG":
        sl = stop_loss if stop_loss is not None else entry_price - risk_amount
        tp = take_profit if take_profit is not None else entry_price + (risk_amount * reward_risk_ratio)
    else:  # SHORT
        sl = stop_loss if stop_loss is not None else entry_price + risk_amount
        tp = take_profit if take_profit is not None else entry_price - (risk_amount * reward_risk_ratio)

    return (round(sl, 8), round(tp, 8))
