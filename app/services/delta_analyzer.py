"""Delta analyzer: compare theoretical backtest trades vs. real executed trades.

Calculates slippage, volume mismatch, and latency delta between
what the strategy predicted and what actually happened.
"""

from __future__ import annotations

from typing import Any


def compare_backtest_vs_real(
    backtest_trade: dict[str, Any],
    real_trade: dict[str, Any],
) -> dict[str, Any]:
    """Compute delta metrics between a backtest trade and a real trade.

    Args:
        backtest_trade: Dict with at least "type", "price", "volume".
        real_trade: Dict with at least "fill_price", "volume".

    Returns:
        Dict with slippage, slippage_pct, volume_mismatch, volume_delta.
    """
    back_price = float(backtest_trade.get("price", 0))
    real_price = float(real_trade.get("fill_price", 0))
    back_volume = float(backtest_trade.get("volume", 0))
    real_volume = float(real_trade.get("volume", 0))

    # Slippage: difference between expected (backtest) and actual (real) price
    slippage = round(real_price - back_price, 8)
    slippage_pct = round((slippage / back_price) * 100, 4) if back_price != 0 else 0.0

    # Volume mismatch
    volume_delta = round(real_volume - back_volume, 8)
    volume_mismatch = abs(volume_delta) > 0.0001

    return {
        "slippage": slippage,
        "slippage_pct": slippage_pct,
        "volume_delta": volume_delta,
        "volume_mismatch": volume_mismatch,
        "backtest_price": back_price,
        "real_price": real_price,
        "backtest_volume": back_volume,
        "real_volume": real_volume,
    }
