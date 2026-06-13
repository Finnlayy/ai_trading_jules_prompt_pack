import time
import numpy as np

def _safe_div(num: float, den: float) -> float:
    return num / den if den != 0 else 0.0

def old_sortino(returns):
    if not returns:
        return 0.0
    import math
    avg = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return float("inf") if avg > 0 else 0.0
    downside_std = math.sqrt(sum(r ** 2 for r in downside) / len(downside))
    return _safe_div(avg, downside_std) * math.sqrt(252)

def new_sortino(returns):
    if not returns:
        return 0.0
    import math
    arr = np.asarray(returns)
    avg = np.mean(arr)
    downside = arr[arr < 0]
    if len(downside) == 0:
        return float("inf") if avg > 0 else 0.0
    # standard sortino uses sum of squared downside returns divided by *total* length of downside
    downside_std = math.sqrt(np.sum(downside**2) / len(downside))
    return _safe_div(float(avg), downside_std) * math.sqrt(252)

import random
returns = [random.uniform(-0.02, 0.02) for _ in range(1000000)]

t0 = time.time()
old_sortino(returns)
t1 = time.time()

t2 = time.time()
new_sortino(returns)
t3 = time.time()

print(f"Old: {t1-t0:.4f}")
print(f"New: {t3-t2:.4f}")
