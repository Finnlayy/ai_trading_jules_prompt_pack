import time
from dataclasses import dataclass
from typing import List, Sequence, Optional

@dataclass
class Candle:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float

def aggregate_old(candles: Sequence[Candle], tf_minutes: int) -> List[Candle]:
    bucket_ms = tf_minutes * 60_000
    grouped: List[Candle] = []
    current: Optional[int] = None
    rows: List[Candle] = []
    for c in candles:
        bucket = (c.ts // bucket_ms) * bucket_ms
        if current is None:
            current = bucket
        if bucket != current:
            if rows:
                grouped.append(Candle(
                    ts=current,
                    o=rows[0].o,
                    h=max(x.h for x in rows),
                    l=min(x.l for x in rows),
                    c=rows[-1].c,
                    v=sum(x.v for x in rows),
                ))
            current = bucket
            rows = []
        rows.append(c)
    if rows:
        grouped.append(Candle(
            ts=current if current is not None else rows[0].ts,
            o=rows[0].o,
            h=max(x.h for x in rows),
            l=min(x.l for x in rows),
            c=rows[-1].c,
            v=sum(x.v for x in rows),
        ))
    return grouped

def aggregate_new(candles: Sequence[Candle], tf_minutes: int) -> List[Candle]:
    bucket_ms = tf_minutes * 60_000
    grouped: List[Candle] = []
    if not candles:
        return grouped

    current = (candles[0].ts // bucket_ms) * bucket_ms
    o = candles[0].o
    h = candles[0].h
    l = candles[0].l
    c = candles[0].c
    v = candles[0].v

    for cand in candles[1:]:
        bucket = (cand.ts // bucket_ms) * bucket_ms
        if bucket != current:
            grouped.append(Candle(ts=current, o=o, h=h, l=l, c=c, v=v))
            current = bucket
            o = cand.o
            h = cand.h
            l = cand.l
            c = cand.c
            v = cand.v
        else:
            if cand.h > h: h = cand.h
            if cand.l < l: l = cand.l
            c = cand.c
            v += cand.v

    grouped.append(Candle(ts=current, o=o, h=h, l=l, c=c, v=v))
    return grouped

candles = [Candle(ts=i*60000, o=1.0, h=2.0, l=0.5, c=1.5, v=100) for i in range(100000)]

t0 = time.time()
res1 = aggregate_old(candles, 15)
t1 = time.time()

t2 = time.time()
res2 = aggregate_new(candles, 15)
t3 = time.time()

print(f"Old: {t1-t0:.4f}s")
print(f"New: {t3-t2:.4f}s")
print(f"Match: {len(res1) == len(res2)}")
