import time
import numpy as np

def _safe_div(num: float, den: float) -> float:
    return num / den if den != 0 else 0.0

def old_sharpe(returns, risk_free_rate=0.0):
    if not returns:
        return 0.0
    import math
    excess = [r - risk_free_rate for r in returns]
    avg = sum(excess) / len(excess)
    std = math.sqrt(sum((x - avg) ** 2 for x in excess) / len(excess))
    return _safe_div(avg, std) * math.sqrt(252)

def new_sharpe(returns, risk_free_rate=0.0):
    if not returns:
        return 0.0
    import math
    # pure python without list comprehension
    n = len(returns)
    s = 0.0
    for r in returns:
        s += (r - risk_free_rate)
    avg = s / n
    s2 = 0.0
    for r in returns:
        s2 += (r - risk_free_rate - avg)**2
    std = math.sqrt(s2 / n)
    return _safe_div(avg, std) * math.sqrt(252)

def new2_sharpe(returns, risk_free_rate=0.0):
    if not returns:
        return 0.0
    import math
    arr = np.asarray(returns)
    excess = arr - risk_free_rate
    avg = np.mean(excess)
    std = np.std(excess)
    return _safe_div(float(avg), float(std)) * math.sqrt(252)


import random
returns = [random.uniform(-0.02, 0.02) for _ in range(1000000)]

t0 = time.time()
old_sharpe(returns)
t1 = time.time()

t2 = time.time()
new_sharpe(returns)
t3 = time.time()

t4 = time.time()
new2_sharpe(returns)
t5 = time.time()

print(f"Old: {t1-t0:.4f}")
print(f"New: {t3-t2:.4f}")
print(f"New2 (numpy): {t5-t4:.4f}")
