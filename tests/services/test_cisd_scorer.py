from typing import List
from app.services.cisd_scorer import (
    Candle,
    CISDScorer,
    cisd_sequence,
    aggregate,
    mtf_state_for_1m,
    compute_ob_fvg_touches
)

def _c(minute: int, o: float, h: float, l: float, c: float, v: float = 1.0) -> Candle:
    return Candle(ts=minute * 60_000, o=o, h=h, l=l, c=c, v=v)

def test_cisd_sequence_identifies_bull_bear_transitions():
    candles = [
        _c(0, 10, 12, 8, 11),  # Bull
        _c(1, 11, 13, 10, 9),  # Bear
        _c(2, 9, 10, 7, 8),    # Bear
        _c(3, 8, 11, 7, 10),   # Bull
    ]
    states, bull, bear = cisd_sequence(candles)

    assert states == [1, -1, -1, 1]
    assert bull == [True, False, False, True]
    assert bear == [False, True, False, False]

def test_aggregate_rolls_up_candles():
    candles = [
        _c(0, 100, 101, 99, 100.5, 10),
        _c(1, 100.5, 103, 100, 102, 11),
        _c(2, 102, 104, 101, 103, 12),
        _c(3, 103, 104, 98, 99, 13),
    ]
    # Aggregate to 2m timeframe
    agg = aggregate(candles, 2)
    assert len(agg) == 2

    c1 = agg[0]
    assert c1.ts == 0
    assert c1.o == 100
    assert c1.h == 103
    assert c1.l == 99
    assert c1.c == 102
    assert c1.v == 21

    c2 = agg[1]
    assert c2.ts == 120_000
    assert c2.o == 102
    assert c2.h == 104
    assert c2.l == 98
    assert c2.c == 99
    assert c2.v == 25

def test_mtf_state_for_1m_offsets_state_correctly():
    candles = [
        _c(0, 10, 12, 8, 11),  # m0 (bucket 0) -> Bull
        _c(1, 11, 13, 10, 12), # m1 (bucket 0) -> Bull
        _c(2, 12, 14, 11, 10), # m2 (bucket 1) -> Bear
        _c(3, 10, 11, 9, 8),   # m3 (bucket 1) -> Bear
        _c(4, 8, 10, 7, 9),    # m4 (bucket 2) -> Bull
    ]
    # Using a 2m MTF
    state_dict = mtf_state_for_1m(candles, 2)

    # Bucket 0 is ts 0, 60_000
    # Bucket 1 is ts 120_000, 180_000
    # Bucket 2 is ts 240_000

    # State mapping requires the PREVIOUS bucket's state.
    # Bucket 0 -> no previous bucket, default 0
    assert state_dict[0] == 0
    assert state_dict[60_000] == 0

    # Bucket 1 -> previous bucket is 0, which closed bullish (state 1)
    assert state_dict[120_000] == 1
    assert state_dict[180_000] == 1

    # Bucket 2 -> previous bucket is 1, which closed bearish (state -1)
    assert state_dict[240_000] == -1

def test_compute_ob_fvg_touches():
    # Construct a sequence that forms an FVG
    candles = [
        _c(0, 10, 11, 9, 10.5), # bar 0
        _c(1, 10.5, 15, 10, 14), # bar 1: large impulsive up move
        _c(2, 14, 16, 12, 15), # bar 2: leaves FVG between high of bar 0 (11) and low of bar 2 (12)
        _c(3, 15, 17, 14, 16), # bar 3: continues up
        _c(4, 16, 17, 11.5, 12), # bar 4: pulls back and touches the FVG (low 11.5 goes into 11-12 gap)
    ]

    # For OB to form, we need at least 2*ob_pivot + 1 bars
    # Let's set ob_pivot to 1 for easier testing
    bull_ob_touch, bear_ob_touch, bull_fvg_touch, bear_fvg_touch = compute_ob_fvg_touches(
        candles, ob_pivot=1, ob_atr_mul=10.0
    )

    # FVG formed at bar 2 (bull_fvg_now condition: lows[2] (12) > highs[0] (11) and c[1]>o[1] (14>10.5))
    # It gets touched at bar 4 (lows[4] <= 12 and highs[4] >= 11) -> 11.5 <= 12 and 17 >= 11 (True)
    assert bull_fvg_touch[4] is True

def test_scorer_integration():
    # Need at least 50 candles to pass the length check
    candles = [_c(i, 10, 12, 8, 11) for i in range(50)]

    scorer = CISDScorer()
    res = scorer.score_series(candles)
    assert len(res) == 50
    assert "confluence_score" in res[-1]

    res_latest = scorer.score_latest(candles)
    assert res_latest == res[-1]
