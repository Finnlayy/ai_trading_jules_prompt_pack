💡 **What:**
Removed a redundant list comprehension initialization for `normalized_symbols` in `app/services/price_poller.py`.

🎯 **Why:**
The exact same generator expression was being evaluated twice consecutively (`normalized_symbols = list({normalize_symbol(p.symbol) for p in positions})`), causing unnecessary loop iterations and function calls in the hot path.

📊 **Impact:**
Reduced CPU overhead and function calls in `_poll_loop`, slightly decreasing event loop blocking time.

🔬 **Measurement:**
Benchmarking `list({normalize_symbol(p.symbol) for p in positions})` execution twice vs once with 100 items for 10,000 iterations:
- Baseline: 0.4104s
- Optimized: 0.2035s
- Improvement: 50.40% speed up over baseline execution time.
