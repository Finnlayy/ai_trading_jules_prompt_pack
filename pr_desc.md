🎯 **What:**
- Discovered and fixed an `AttributeError` in `PerformanceCalculator._extract_pnl()` where it mistakenly queried `entry.exit_price` instead of safely handling missing dictionary attributes when deserializing JSON.
- Implemented a comprehensive pytest test suite for `PerformanceCalculator`.

📊 **Coverage:**
- `calculate_metrics`: Edge cases with empty lists, mathematical calculation correctness using fixed PnLs.
- `_extract_pnl`: Accurate extraction falling back across dictionaries vs. schema objects and accessing both result and simulated execution fields.
- Mathematical functions `_sharpe` and `_sortino`: Covered single-pass numerical arrays evaluating accurate annualized standard deviations and variance logic.
- `calculate_equity_curve_data`: Ensures properly formatted `{"trade_idx": i, "equity": val}` outputs for frontend charting.

✨ **Result:**
- Full function coverage achieved over core statistical tracking algorithms.
- `PerformanceCalculator` isolated tests are robust and deterministically passing, enabling confident downstream risk validation.
