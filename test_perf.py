import time
from dataclasses import dataclass
from typing import List, Sequence

from app.schemas.journal import TradeJournalEntry

class PerformanceCalculatorOld:
    def _sharpe(self, returns: List[float], risk_free_rate: float = 0.0) -> float:
        if not returns:
            return 0.0
        excess = [r - risk_free_rate for r in returns]
        avg = sum(excess) / len(excess)
        import math
        std = math.sqrt(sum((x - avg) ** 2 for x in excess) / len(excess))
        return (avg / std if std != 0 else 0) * math.sqrt(252)

class PerformanceCalculatorNew:
    def _sharpe(self, returns: List[float], risk_free_rate: float = 0.0) -> float:
        if not returns:
            return 0.0
        import numpy as np
        import math
        arr = np.array(returns) - risk_free_rate
        std = np.std(arr)
        if std == 0:
            return 0.0
        return (np.mean(arr) / std) * math.sqrt(252)

old_calc = PerformanceCalculatorOld()
new_calc = PerformanceCalculatorNew()

import random
returns = [random.uniform(-0.02, 0.02) for _ in range(1000000)]

t0 = time.time()
r1 = old_calc._sharpe(returns)
t1 = time.time()

t2 = time.time()
r2 = new_calc._sharpe(returns)
t3 = time.time()

print(f"Old: {t1-t0:.4f}s")
print(f"New: {t3-t2:.4f}s")
print(f"Match: {abs(r1 - r2) < 1e-6}")
