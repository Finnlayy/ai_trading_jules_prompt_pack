"""
Recommendations API — computes suggested parameter values and 4-word hints
based on recent OHLCV data for a given symbol, timeframe, and strategy.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.signal_generator import BybitDataFeed

logger = logging.getLogger(__name__)

router = APIRouter()

_TF_MAP = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}

_HINTS: dict[str, str] = {
    "signal_id": "unique traceable identifier",
    "symbol": "top coin high liquidity",
    "timeframe": "higher tf fewer signals",
    "direction": "trend follow higher probability",
    "intent": "entry open close exit",
    "account_mode": "futures more leverage spot",
    "entry_price": "mid range better rr",
    "stop_price": "tighter sl smaller loss",
    "target_price": "higher tp higher winrate",
    "execution_quantity": "size risks smaller drawdown",
    "confluence_score": "higher score stronger signal",
    "crisis_score": "lower crisis safer trade",
    "mc_dispersion": "lower dispersion cleaner setup",
    "spread": "tight spread lower cost",
    "order_command": "go trade hold wait",
    "market_regime": "green trade red stop",
    "relative_volume": "high volume confirms move",
    "chop_index": "low chop trends persist",
    "hurst_exponent": "high hurst trend reliable",
    "drawdown_pct": "lower drawdown higher pf",
    "pending_order_age_seconds": "fresh orders fill faster",
    "leverage": "lower leverage safer trade",
    "bar_confirmed": "confirmed bar less whipsaw",
    "macro_event_risk": "avoid news reduce slippage",
}


def _atr(bars: list) -> float:
    if len(bars) < 2:
        return bars[0]["h"] - bars[0]["l"] if bars else 1.0
    trs = []
    prev_close = bars[0]["c"]
    for b in bars[1:]:
        trs.append(max(b["h"] - b["l"], abs(b["h"] - prev_close), abs(b["l"] - prev_close)))
        prev_close = b["c"]
    return sum(trs) / len(trs) if trs else 1.0


def _sma(values: list[float], period: int) -> list[float]:
    out = []
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= period:
            s -= values[i - period]
        out.append(s / min(i + 1, period))
    return out


def _trend_direction(bars: list) -> str:
    if len(bars) < 20:
        return "LONG"
    closes = [b["c"] for b in bars]
    sma20 = _sma(closes, 20)
    if closes[-1] > sma20[-1]:
        return "LONG"
    return "SHORT"


def _volatility_regime(atr_val: float, entry: float) -> str:
    atr_pct = (atr_val / entry) * 100.0 if entry else 0.0
    if atr_pct > 5.0:
        return "RED"
    if atr_pct > 3.0:
        return "ORANGE"
    if atr_pct > 1.5:
        return "YELLOW"
    return "GREEN"


def _recommend_leverage(timeframe: str) -> int:
    minutes = _TF_MAP.get(timeframe, 60)
    if minutes >= 240:
        return 3
    if minutes >= 60:
        return 5
    if minutes >= 15:
        return 10
    return 20


def _confluence_threshold(timeframe: str, atr_pct: float) -> float:
    base = 70.0
    minutes = _TF_MAP.get(timeframe, 60)
    if minutes >= 240:
        base = 75.0
    if minutes <= 5:
        base = 65.0
    if atr_pct > 4.0:
        base += 5.0
    return round(base, 1)


class RecommendResponse(BaseModel):
    symbol: str
    timeframe: str
    strategy: str | None
    recommendations: dict[str, Any]
    hints: dict[str, str]


@router.get("/recommend", response_model=RecommendResponse)
async def get_recommendations(
    symbol: str = Query(..., min_length=1, pattern=r"^[A-Za-z0-9_\-\.]+$"),
    timeframe: str = Query("1h"),
    strategy: str | None = Query(None),
):
    try:
        raw = BybitDataFeed.fetch(symbol, 100, timeframe)
    except Exception as exc:
        logger.warning("Recommend fetch failed: %s", exc)
        return RecommendResponse(
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            recommendations={},
            hints=_HINTS,
        )

    if not raw:
        return RecommendResponse(
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            recommendations={},
            hints=_HINTS,
        )

    bars = [{"o": b.o, "h": b.h, "l": b.l, "c": b.c, "v": b.v, "ts": b.ts} for b in raw]
    last = bars[-1]
    entry = last["c"]
    atr_val = _atr(bars)
    atr_pct = (atr_val / entry) * 100.0 if entry else 0.0
    direction = _trend_direction(bars)
    regime = _volatility_regime(atr_val, entry)

    vols = [b["v"] for b in bars]
    avg_vol = sum(vols[:-1]) / max(1, len(vols) - 1) if len(vols) > 1 else vols[0]
    rel_vol = round(last["v"] / avg_vol, 2) if avg_vol else 1.0

    sl_atr_mul = 1.5
    tp_atr_mul = 3.0

    if direction == "LONG":
        stop = round(entry - atr_val * sl_atr_mul, 4)
        target = round(entry + atr_val * tp_atr_mul, 4)
    else:
        stop = round(entry + atr_val * sl_atr_mul, 4)
        target = round(entry - atr_val * tp_atr_mul, 4)

    crisis = min(100.0, max(0.0, (atr_pct - 1.0) * 15.0))
    spread = round((last["h"] - last["l"]) / entry * 10000.0, 2) if entry else 0.0

    recommendations = {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "direction": direction,
        "intent": "ENTRY",
        "account_mode": "FUTURES",
        "entry_price": round(entry, 4),
        "stop_price": stop,
        "target_price": target,
        "execution_quantity": "",
        "confluence_score": _confluence_threshold(timeframe, atr_pct),
        "crisis_score": round(crisis, 2),
        "mc_dispersion": round(2.0 if regime in {"GREEN", "YELLOW"} else 3.5, 2),
        "spread": spread,
        "order_command": "GO",
        "market_regime": regime,
        "relative_volume": rel_vol,
        "chop_index": "",
        "hurst_exponent": "",
        "drawdown_pct": "",
        "pending_order_age_seconds": "",
        "leverage": _recommend_leverage(timeframe),
        "bar_confirmed": True,
        "macro_event_risk": False,
    }

    return RecommendResponse(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy,
        recommendations=recommendations,
        hints=_HINTS,
    )
