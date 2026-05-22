from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


MS_PER_MINUTE = 60_000


@dataclass(frozen=True)
class Candle:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float


@dataclass(frozen=True)
class CISDSeries:
    states: tuple[int, ...]
    bull_transitions: tuple[bool, ...]
    bear_transitions: tuple[bool, ...]


@dataclass(frozen=True)
class MTFCISDRow:
    ts: int
    local_state: int
    local_bull: bool
    local_bear: bool
    timeframe_states: dict[int, int]
    bull_alignment: int
    bear_alignment: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timeframe_states"] = {str(key): value for key, value in self.timeframe_states.items()}
        return data


def candle_from_record(record: Mapping[str, Any]) -> Candle:
    return Candle(
        ts=int(record["open_time"]),
        o=float(record["open"]),
        h=float(record["high"]),
        l=float(record["low"]),
        c=float(record["close"]),
        v=float(record.get("volume", 0.0)),
    )


def candles_from_records(records: Iterable[Mapping[str, Any]]) -> list[Candle]:
    candles = [candle_from_record(record) for record in records]
    return sorted(candles, key=lambda candle: candle.ts)


def resample_candles(candles: Sequence[Candle], timeframe_minutes: int) -> list[Candle]:
    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")
    if not candles:
        return []

    bucket_ms = timeframe_minutes * MS_PER_MINUTE
    grouped: list[Candle] = []
    current_bucket: int | None = None
    rows: list[Candle] = []

    for candle in sorted(candles, key=lambda item: item.ts):
        bucket = (candle.ts // bucket_ms) * bucket_ms
        if current_bucket is None:
            current_bucket = bucket
        if bucket != current_bucket:
            grouped.append(_merge_bucket(rows, current_bucket))
            rows = []
            current_bucket = bucket
        rows.append(candle)

    if rows and current_bucket is not None:
        grouped.append(_merge_bucket(rows, current_bucket))
    return grouped


def _merge_bucket(rows: Sequence[Candle], bucket_ts: int) -> Candle:
    return Candle(
        ts=bucket_ts,
        o=rows[0].o,
        h=max(row.h for row in rows),
        l=min(row.l for row in rows),
        c=rows[-1].c,
        v=sum(row.v for row in rows),
    )


def cisd_sequence(candles: Sequence[Candle]) -> CISDSeries:
    state = 0
    states: list[int] = []
    bull: list[bool] = []
    bear: list[bool] = []

    for index, candle in enumerate(candles):
        previous = candles[index - 1] if index > 0 else candle
        is_bull = candle.c > candle.o
        is_bear = candle.c < candle.o
        inside_bar = candle.h < previous.h and candle.l > previous.l
        bull_transition = False
        bear_transition = False

        if is_bear and state != -1 and candle.c < previous.o and not inside_bar:
            state = -1
            bear_transition = True
        if is_bull and state != 1 and candle.c > previous.o and not inside_bar:
            state = 1
            bull_transition = True

        states.append(state)
        bull.append(bull_transition)
        bear.append(bear_transition)

    return CISDSeries(
        states=tuple(states),
        bull_transitions=tuple(bull),
        bear_transitions=tuple(bear),
    )


def completed_timeframe_state_map(candles: Sequence[Candle], timeframe_minutes: int) -> dict[int, int]:
    """Map base candles to the previous completed higher-timeframe CISD state.

    The current bucket is intentionally not used. That avoids leaking the close
    of a still-forming higher-timeframe candle into lower-timeframe decisions.
    """
    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be positive")
    if not candles:
        return {}

    higher_tf = resample_candles(candles, timeframe_minutes)
    cisd = cisd_sequence(higher_tf)
    by_bucket = {candle.ts: state for candle, state in zip(higher_tf, cisd.states)}
    bucket_ms = timeframe_minutes * MS_PER_MINUTE

    state_by_base_ts: dict[int, int] = {}
    for candle in candles:
        bucket = (candle.ts // bucket_ms) * bucket_ms
        state_by_base_ts[candle.ts] = by_bucket.get(bucket - bucket_ms, 0)
    return state_by_base_ts


def build_mtf_cisd_rows(
    candles: Sequence[Candle],
    timeframes: Sequence[int] = (5, 15, 60, 240),
) -> list[MTFCISDRow]:
    ordered = sorted(candles, key=lambda candle: candle.ts)
    local = cisd_sequence(ordered)
    state_maps = {
        timeframe: completed_timeframe_state_map(ordered, timeframe)
        for timeframe in timeframes
    }

    rows: list[MTFCISDRow] = []
    for index, candle in enumerate(ordered):
        timeframe_states = {
            timeframe: state_maps[timeframe].get(candle.ts, 0)
            for timeframe in timeframes
        }
        bull_alignment = sum(1 for state in timeframe_states.values() if state == 1)
        bear_alignment = sum(1 for state in timeframe_states.values() if state == -1)
        rows.append(
            MTFCISDRow(
                ts=candle.ts,
                local_state=local.states[index],
                local_bull=local.bull_transitions[index],
                local_bear=local.bear_transitions[index],
                timeframe_states=timeframe_states,
                bull_alignment=bull_alignment,
                bear_alignment=bear_alignment,
            )
        )
    return rows


def summarize_mtf_cisd(
    candles: Sequence[Candle],
    timeframes: Sequence[int] = (5, 15, 60, 240),
) -> dict[str, Any]:
    rows = build_mtf_cisd_rows(candles, timeframes=timeframes)
    if not rows:
        return {
            "candles": 0,
            "timeframes": list(timeframes),
            "last": None,
            "bull_rows": 0,
            "bear_rows": 0,
        }

    return {
        "candles": len(rows),
        "timeframes": list(timeframes),
        "last": rows[-1].to_dict(),
        "bull_rows": sum(1 for row in rows if row.bull_alignment > row.bear_alignment),
        "bear_rows": sum(1 for row in rows if row.bear_alignment > row.bull_alignment),
    }

