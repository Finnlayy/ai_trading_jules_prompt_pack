from app.research.mtf_cisd import (
    Candle,
    build_mtf_cisd_rows,
    cisd_sequence,
    completed_timeframe_state_map,
    resample_candles,
    summarize_mtf_cisd,
)


def _candle(minute: int, open_: float, high: float, low: float, close: float, volume: float = 1.0) -> Candle:
    return Candle(
        ts=minute * 60_000,
        o=open_,
        h=high,
        l=low,
        c=close,
        v=volume,
    )


def test_resample_candles_builds_true_ohlcv_buckets():
    candles = [
        _candle(0, 100, 101, 99, 100.5, 10),
        _candle(1, 100.5, 103, 100, 102, 11),
        _candle(2, 102, 104, 101, 103, 12),
        _candle(3, 103, 104, 98, 99, 13),
    ]

    result = resample_candles(candles, timeframe_minutes=2)

    assert result == [
        Candle(ts=0, o=100, h=103, l=99, c=102, v=21),
        Candle(ts=120_000, o=102, h=104, l=98, c=99, v=25),
    ]


def test_cisd_sequence_tracks_bull_and_bear_transitions():
    candles = [
        _candle(0, 100, 101, 99, 100),
        _candle(1, 100, 104, 99, 103),
        _candle(2, 103, 104, 96, 98),
    ]

    sequence = cisd_sequence(candles)

    assert sequence.states == (0, 1, -1)
    assert sequence.bull_transitions == (False, True, False)
    assert sequence.bear_transitions == (False, False, True)


def test_completed_timeframe_state_map_uses_previous_closed_bucket():
    candles = [
        _candle(0, 100, 101, 99, 100),
        _candle(1, 100, 104, 99, 103),
        _candle(2, 103, 104, 96, 98),
        _candle(3, 98, 99, 94, 95),
    ]

    state_map = completed_timeframe_state_map(candles, timeframe_minutes=2)

    assert state_map[0] == 0
    assert state_map[60_000] == 0
    assert state_map[120_000] == 1
    assert state_map[180_000] == 1


def test_build_mtf_cisd_rows_reports_alignment_counts():
    candles = [
        _candle(0, 100, 101, 99, 100),
        _candle(1, 100, 104, 99, 103),
        _candle(2, 103, 104, 96, 98),
        _candle(3, 98, 99, 94, 95),
    ]

    rows = build_mtf_cisd_rows(candles, timeframes=(2,))

    assert rows[-1].timeframe_states == {2: 1}
    assert rows[-1].bull_alignment == 1
    assert rows[-1].bear_alignment == 0


def test_summarize_mtf_cisd_is_json_ready():
    candles = [
        _candle(0, 100, 101, 99, 100),
        _candle(1, 100, 104, 99, 103),
    ]

    summary = summarize_mtf_cisd(candles, timeframes=(1, 2))

    assert summary["candles"] == 2
    assert summary["timeframes"] == [1, 2]
    assert summary["last"]["timeframe_states"] == {"1": 0, "2": 0}

