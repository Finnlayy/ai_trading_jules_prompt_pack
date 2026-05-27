import time
import math
import random
import numpy as np
from typing import Sequence, List

def old_sharpe(returns, risk_free_rate=0.0):
    if not returns:
        return 0.0
    excess = [r - risk_free_rate for r in returns]
    avg = sum(excess) / len(excess)
    std = math.sqrt(sum((x - avg) ** 2 for x in excess) / len(excess))
    return (avg / std if std != 0 else 0) * math.sqrt(252)

def new_sharpe(returns, risk_free_rate=0.0):
    if not returns:
        return 0.0
    arr = np.asarray(returns)
    excess = arr - risk_free_rate
    avg = np.mean(excess)
    std = np.std(excess)
    return (float(avg) / float(std) if std != 0 else 0.0) * math.sqrt(252)

returns = [random.uniform(-0.02, 0.02) for _ in range(1000000)]

t0 = time.time()
r1 = old_sharpe(returns)
t1 = time.time()
r2 = new_sharpe(returns)
t2 = time.time()

print(f"Old sharpe: {t1-t0:.4f}s")
print(f"New sharpe: {t2-t1:.4f}s")

def old_sortino(returns):
    if not returns:
        return 0.0
    avg = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return float("inf") if avg > 0 else 0.0
    downside_std = math.sqrt(sum(r ** 2 for r in downside) / len(downside))
    return (avg / downside_std if downside_std != 0 else 0) * math.sqrt(252)

def new_sortino(returns):
    if not returns:
        return 0.0
    arr = np.asarray(returns)
    avg = np.mean(arr)
    downside = arr[arr < 0]
    if len(downside) == 0:
        return float("inf") if avg > 0 else 0.0
    downside_std = math.sqrt(np.sum(downside**2) / len(downside))
    return (float(avg) / downside_std if downside_std != 0 else 0) * math.sqrt(252)

t3 = time.time()
s1 = old_sortino(returns)
t4 = time.time()
s2 = new_sortino(returns)
t5 = time.time()

print(f"Old sortino: {t4-t3:.4f}s")
print(f"New sortino: {t5-t4:.4f}s")
