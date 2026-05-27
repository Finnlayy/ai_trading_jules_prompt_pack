## 2026-05-22 - Vectorizing Statistical Battery
**Learning:** Python loops over large numpy arrays inside the `app/services/statistical_battery.py` calculation logic were found to be very slow (over 100x slower) than pure vectorization. The `variance_ratio` method used a python list comprehension spanning a numpy array over multiple lookback windows, and `runs_test` looped element-wise to compute differences.
**Action:** When computing statistical indicators on large time-series arrays, prefer using native numpy methods such as `.reshape(-1, k).sum(axis=1)` to simulate sliding windows, and `np.diff` paired with `np.count_nonzero` to eliminate Python-level loops.

## 2026-05-23 - Generator Expressions in Hot Paths
**Learning:** Using Python generator expressions like `any(condition for x in iter)` in performance hot paths (e.g. iterating over 1m candles for touch detection) incurs significant function call and generator overhead. Unrolling the generator into a native `for` loop with an early `break` can dramatically improve execution time (e.g. 10x faster for touch evaluation).
**Action:** When iterating over small loops inside massive outer loops (e.g. backtest engines, scorers), replace `any(...)` with an explicitly unrolled `for` loop containing an early `break`.
## 2026-05-27 - Vectorizing Performance Metrics
**Learning:** Python-level list comprehensions for standard deviation calculations in performance metrics (`_sharpe` and `_sortino` loops) are significantly slower than native numpy equivalents, particularly as journal entries grow.
**Action:** Replace iterative mathematical loops over return sequences with `np.asarray`, `np.std`, and boolean indexing (`arr[arr < 0]`) to achieve measurable ~2-3x speedups on large collections.
