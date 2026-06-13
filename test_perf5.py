import time
import math
import numpy as np
from dataclasses import dataclass
from typing import Sequence, List

@dataclass
class Candle:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float

def compute_ob_fvg_touches_old(candles: Sequence[Candle], ob_pivot: int, ob_atr_mul: float, max_ob_boxes: int = 25, max_fvg_boxes: int = 25):
    n = len(candles)
    lows = [c.l for c in candles]
    highs = [c.h for c in candles]
    closes = [c.c for c in candles]
    opens = [c.o for c in candles]

    # Dummy ATR for simplicity
    atr14 = [1.0] * n
    bull_ob = []
    bear_ob = []
    bull_fvg = []
    bear_fvg = []

    bull_ob_touch = [False] * n
    bear_ob_touch = [False] * n
    bull_fvg_touch = [False] * n
    bear_fvg_touch = [False] * n

    for i in range(n):
        # OB creation
        if i >= ob_pivot * 2:
            piv = i - ob_pivot
            left = piv - ob_pivot
            right = piv + ob_pivot
            if left >= 0 and right <= i:
                if lows[piv] == min(lows[left:right + 1]):
                    ob_top = highs[piv]
                    ob_bot = lows[piv]
                    if (ob_top - ob_bot) <= atr14[i] * ob_atr_mul:
                        bull_ob.append((ob_top, ob_bot))
                        if len(bull_ob) > max_ob_boxes:
                            bull_ob.pop(0)
                if highs[piv] == max(highs[left:right + 1]):
                    ob_top = highs[piv]
                    ob_bot = lows[piv]
                    if (ob_top - ob_bot) <= atr14[i] * ob_atr_mul:
                        bear_ob.append((ob_top, ob_bot))
                        if len(bear_ob) > max_ob_boxes:
                            bear_ob.pop(0)

        # FVG creation
        if i >= 2:
            bull_fvg_now = lows[i] > highs[i - 2] and closes[i - 1] > opens[i - 1]
            bear_fvg_now = highs[i] < lows[i - 2] and closes[i - 1] < opens[i - 1]
            if bull_fvg_now:
                bull_fvg.append((lows[i], highs[i - 2]))
                if len(bull_fvg) > max_fvg_boxes:
                    bull_fvg.pop(0)
            if bear_fvg_now:
                bear_fvg.append((lows[i - 2], highs[i]))
                if len(bear_fvg) > max_fvg_boxes:
                    bear_fvg.pop(0)

        # Touches on current bar
        c = candles[i]

        # Bull OB
        if bull_ob:
            found = False
            for top, bot in bull_ob[-5:]:
                if c.l <= top and c.h >= bot:
                    found = True
                    break
            bull_ob_touch[i] = found

        # Bear OB
        if bear_ob:
            found = False
            for top, bot in bear_ob[-5:]:
                if c.h >= bot and c.l <= top:
                    found = True
                    break
            bear_ob_touch[i] = found

        # Bull FVG
        if bull_fvg:
            found = False
            for top, bot in bull_fvg[-5:]:
                if c.l <= top and c.h >= bot:
                    found = True
                    break
            bull_fvg_touch[i] = found

        # Bear FVG
        if bear_fvg:
            found = False
            for top, bot in bear_fvg[-5:]:
                if c.h >= bot and c.l <= top:
                    found = True
                    break
            bear_fvg_touch[i] = found

    return bull_ob_touch, bear_ob_touch, bull_fvg_touch, bear_fvg_touch

candles = []
o, h, l, c = 1.0, 2.0, 0.5, 1.5
for i in range(10000):
    if i % 10 == 0:
        l = min(l * 0.9, 0.1)
    if i % 10 == 5:
        h = h * 1.1
    candles.append(Candle(ts=i, o=o, h=h, l=l, c=c, v=100.0))

t0 = time.time()
compute_ob_fvg_touches_old(candles, 6, 1.6)
t1 = time.time()
print(f"Old touches: {t1-t0:.4f}s")
