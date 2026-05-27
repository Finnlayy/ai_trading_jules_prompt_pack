import time
from dataclasses import dataclass
from typing import Sequence

@dataclass
class Candle:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float

def compute_touches_old(candles, ob_pivot=6, ob_atr_mul=1.6):
    n = len(candles)
    # fake atr14 for testing
    atr14 = [1.0] * n
    bull_ob = []
    bull_ob_touch = [False] * n

    for i in range(n):
        # OB creation
        if i >= ob_pivot * 2:
            piv = i - ob_pivot
            left = piv - ob_pivot
            right = piv + ob_pivot
            if left >= 0 and right <= i:
                pass # simplified

        c = candles[i]
        # Bull OB
        if bull_ob:
            found = False
            for top, bot in bull_ob[-5:]:
                if c.l <= top and c.h >= bot:
                    found = True
                    break
            bull_ob_touch[i] = found

def cisd_score_series(candles):
    n = len(candles)
    o = [c.o for c in candles]
    h = [c.h for c in candles]
    l = [c.l for c in candles]
    c_p = [c.c for c in candles]
    v = [c.v for c in candles]

    # test building loop
    results = []
    for i in range(n):
        c = candles[i]
        # do something
        results.append({"ts": c.ts})
    return results


import random
candles = [Candle(ts=i, o=1.0, h=2.0, l=0.5, c=1.5, v=100.0) for i in range(100000)]

t0 = time.time()
compute_touches_old(candles)
cisd_score_series(candles)
t1 = time.time()
print(f"Old: {t1-t0:.4f}")
