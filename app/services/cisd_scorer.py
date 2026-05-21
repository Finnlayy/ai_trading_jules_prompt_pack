"""
CISD Scorer — extracts MTF CISD + OB/FVG scoring logic from the HYPE backtester
and exposes it as a reusable service for M8Payload enrichment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple, Optional, Dict

import numpy as np


@dataclass(frozen=True)
class Candle:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float


def ema(values: Sequence[float], period: int) -> List[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    out = [values[0]]
    for x in values[1:]:
        out.append(out[-1] * (1.0 - alpha) + x * alpha)
    return out


def sma(values: Sequence[float], period: int) -> List[float]:
    out: List[float] = []
    s = 0.0
    for i, x in enumerate(values):
        s += x
        if i >= period:
            s -= values[i - period]
        out.append(s / min(i + 1, period))
    return out


def atr(candles: Sequence[Candle], period: int = 14) -> List[float]:
    trs: List[float] = []
    prev = candles[0].c
    for c in candles:
        trs.append(max(c.h - c.l, abs(c.h - prev), abs(c.l - prev)))
        prev = c.c
    return ema(trs, period)


def rsi(closes: Sequence[float], length: int) -> List[float]:
    if len(closes) < 2:
        return [50.0] * len(closes)
    gains = [0.0]
    losses = [0.0]
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))

    out = [50.0] * len(closes)
    avg_gain = sum(gains[1:length + 1]) / length if len(closes) > length else sum(gains[1:]) / max(1, len(closes) - 1)
    avg_loss = sum(losses[1:length + 1]) / length if len(closes) > length else sum(losses[1:]) / max(1, len(closes) - 1)

    start = max(1, length)
    for i in range(start, len(closes)):
        if i > start:
            avg_gain = (avg_gain * (length - 1) + gains[i]) / length
            avg_loss = (avg_loss * (length - 1) + losses[i]) / length
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def cisd_sequence(candles: Sequence[Candle]) -> Tuple[List[int], List[bool], List[bool]]:
    state = 0
    states: List[int] = []
    bull: List[bool] = []
    bear: List[bool] = []
    for i, c in enumerate(candles):
        prev = candles[i - 1] if i > 0 else c
        is_bull = c.c > c.o
        is_bear = c.c < c.o
        bull_tr = False
        bear_tr = False
        inside = c.h < prev.h and c.l > prev.l
        if is_bear and state != -1:
            if c.c < prev.o and not inside:
                state = -1
                bear_tr = True
        if is_bull and state != 1:
            if c.c > prev.o and not inside:
                state = 1
                bull_tr = True
        states.append(state)
        bull.append(bull_tr)
        bear.append(bear_tr)
    return states, bull, bear


def aggregate(candles: Sequence[Candle], tf_minutes: int) -> List[Candle]:
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


def mtf_state_for_1m(candles_1m: Sequence[Candle], tf_minutes: int) -> Dict[int, int]:
    agg = aggregate(candles_1m, tf_minutes)
    states, _, _ = cisd_sequence(agg)
    by_bucket = {c.ts: s for c, s in zip(agg, states)}
    tf_ms = tf_minutes * 60_000
    out: Dict[int, int] = {}
    for c in candles_1m:
        bucket = (c.ts // tf_ms) * tf_ms
        prev_bucket = bucket - tf_ms
        out[c.ts] = by_bucket.get(prev_bucket, 0)
    return out


def compute_ob_fvg_touches(
    candles: Sequence[Candle],
    ob_pivot: int,
    ob_atr_mul: float,
    max_ob_boxes: int = 25,
    max_fvg_boxes: int = 25,
) -> Tuple[List[bool], List[bool], List[bool], List[bool]]:
    """Returns (bull_ob_touch, bear_ob_touch, bull_fvg_touch, bear_fvg_touch) per bar."""
    n = len(candles)
    lows = [c.l for c in candles]
    highs = [c.h for c in candles]
    closes = [c.c for c in candles]
    opens = [c.o for c in candles]

    atr14 = atr(candles, 14)
    bull_ob: List[Tuple[float, float]] = []
    bear_ob: List[Tuple[float, float]] = []
    bull_fvg: List[Tuple[float, float]] = []
    bear_fvg: List[Tuple[float, float]] = []

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
        bull_ob_touch[i] = any((c.l <= top and c.h >= bot) for top, bot in bull_ob[-5:]) if bull_ob else False
        bear_ob_touch[i] = any((c.h >= bot and c.l <= top) for top, bot in bear_ob[-5:]) if bear_ob else False
        bull_fvg_touch[i] = any((c.l <= top and c.h >= bot) for top, bot in bull_fvg[-5:]) if bull_fvg else False
        bear_fvg_touch[i] = any((c.h >= bot and c.l <= top) for top, bot in bear_fvg[-5:]) if bear_fvg else False

    return bull_ob_touch, bear_ob_touch, bull_fvg_touch, bear_fvg_touch


class CISDScorer:
    """
    Computes MTF CISD + OB/FVG confluence scores for a series of candles.
    Produces a confluence_score (0-100) per bar suitable for M8Payload.
    """

    def __init__(
        self,
        min_alignment: int = 3,
        ob_atr_mul: float = 1.6,
        ob_pivot: int = 6,
        w_align_full: int = 4,
        w_align_part: int = 2,
        w_cisd: int = 3,
        w_ob_touch: int = 3,
        w_fvg_touch: int = 3,
        w_vol_score: int = 2,
        w_body_score: int = 2,
        body_atr_mul: float = 0.5,
        vol_mult: float = 1.05,
        vol_period: int = 20,
    ):
        self.min_alignment = min_alignment
        self.ob_atr_mul = ob_atr_mul
        self.ob_pivot = ob_pivot
        self.w_align_full = w_align_full
        self.w_align_part = w_align_part
        self.w_cisd = w_cisd
        self.w_ob_touch = w_ob_touch
        self.w_fvg_touch = w_fvg_touch
        self.w_vol_score = w_vol_score
        self.w_body_score = w_body_score
        self.body_atr_mul = body_atr_mul
        self.vol_mult = vol_mult
        self.vol_period = vol_period

    def score_series(self, candles: Sequence[Candle]) -> List[Dict]:
        """
        Score every bar and return a list of score dicts.
        Each dict has: confluence_score, direction_hint, alignment_count, etc.
        """
        n = len(candles)
        if n < 50:
            return []

        o = [c.o for c in candles]
        h = [c.h for c in candles]
        l = [c.l for c in candles]
        c = [c.c for c in candles]
        v = [c.v for c in candles]

        atr14 = atr(candles, 14)
        vol_sma = sma(v, self.vol_period)

        local_state, local_bull_cisd, local_bear_cisd = cisd_sequence(candles)
        state_h4 = mtf_state_for_1m(candles, 48)
        state_h1 = mtf_state_for_1m(candles, 12)
        state_m15 = mtf_state_for_1m(candles, 3)

        bull_ob_touch, bear_ob_touch, bull_fvg_touch, bear_fvg_touch = compute_ob_fvg_touches(
            candles, self.ob_pivot, self.ob_atr_mul
        )

        en_h4, en_h1, en_m15, en_m5 = True, True, True, False
        active_tfs = sum([en_h4, en_h1, en_m15, en_m5])

        results = []
        for i in range(n):
            ts = candles[i].ts
            sh4 = state_h4.get(ts, 0) if en_h4 else 0
            sh1 = state_h1.get(ts, 0) if en_h1 else 0
            sm15 = state_m15.get(ts, 0) if en_m15 else 0

            bull_count = (1 if en_h4 and sh4 == 1 else 0) + \
                         (1 if en_h1 and sh1 == 1 else 0) + \
                         (1 if en_m15 and sm15 == 1 else 0)
            bear_count = (1 if en_h4 and sh4 == -1 else 0) + \
                         (1 if en_h1 and sh1 == -1 else 0) + \
                         (1 if en_m15 and sm15 == -1 else 0)

            bull_aligned = bull_count >= self.min_alignment
            bear_aligned = bear_count >= self.min_alignment

            # Scoring
            bull_conf = 0
            bull_conf += self.w_align_full if (bull_count == active_tfs and active_tfs >= 3) else \
                         (self.w_align_part if bull_aligned else 0)
            bull_conf += self.w_cisd if local_bull_cisd[i] else 0
            bull_conf += self.w_ob_touch if bull_ob_touch[i] else 0
            bull_conf += self.w_fvg_touch if bull_fvg_touch[i] else 0
            bull_conf += self.w_vol_score if v[i] > vol_sma[i] * self.vol_mult else 0
            bull_conf += self.w_body_score if (c[i] > o[i] and (c[i] - o[i]) > atr14[i] * self.body_atr_mul) else 0

            bear_conf = 0
            bear_conf += self.w_align_full if (bear_count == active_tfs and active_tfs >= 3) else \
                         (self.w_align_part if bear_aligned else 0)
            bear_conf += self.w_cisd if local_bear_cisd[i] else 0
            bear_conf += self.w_ob_touch if bear_ob_touch[i] else 0
            bear_conf += self.w_fvg_touch if bear_fvg_touch[i] else 0
            bear_conf += self.w_vol_score if v[i] > vol_sma[i] * self.vol_mult else 0
            bear_conf += self.w_body_score if (o[i] > c[i] and (o[i] - c[i]) > atr14[i] * self.body_atr_mul) else 0

            # Normalize to 0-100 scale
            max_possible = self.w_align_full + self.w_cisd + self.w_ob_touch + self.w_fvg_touch + self.w_vol_score + self.w_body_score
            norm_bull = (bull_conf / max_possible * 100) if max_possible > 0 else 0
            norm_bear = (bear_conf / max_possible * 100) if max_possible > 0 else 0

            direction = "LONG" if bull_conf > bear_conf else "SHORT" if bear_conf > bull_conf else "NEUTRAL"
            confluence = max(norm_bull, norm_bear)

            # Scale factor: GA-optimized min_conf=6 maps to ~70 on M8 scale
            # max_possible with GA weights = 11, so 6/11*100 = 54.5
            # We want 6 to map to ~70, so scale factor = 70/54.5 ≈ 1.28
            # But for stronger signals we need more headroom, use 2.0x
            m8_scaled = min(100.0, confluence * 2.0)

            results.append({
                "timestamp": ts,
                "confluence_score": round(m8_scaled, 2),
                "raw_score": max(bull_conf, bear_conf),
                "direction_hint": direction,
                "bull_conf": bull_conf,
                "bear_conf": bear_conf,
                "bull_aligned": bull_aligned,
                "bear_aligned": bear_aligned,
                "alignment_count": max(bull_count, bear_count),
            })

        return results

    def score_latest(self, candles: Sequence[Candle]) -> Optional[Dict]:
        """Score the most recent bar only."""
        scores = self.score_series(candles)
        return scores[-1] if scores else None
