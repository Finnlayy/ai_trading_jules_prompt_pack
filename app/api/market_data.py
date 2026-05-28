"""
Market Data API — serves OHLCV candles and computed indicators to the frontend.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.signal_generator import BybitDataFeed, OHLCV
from app.services.cisd_scorer import CISDScorer, Candle as CISDScorerCandle

logger = logging.getLogger(__name__)

router = APIRouter()

_TF_OPTIONS = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}


class OHLCVBar(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorPoint(BaseModel):
    time: int
    confluence_score: float
    direction_hint: str
    alignment_count: int


class OHLCVResponse(BaseModel):
    symbol: str
    timeframe: str
    bars: List[OHLCVBar]


class IndicatorsResponse(BaseModel):
    symbol: str
    timeframe: str
    indicators: List[IndicatorPoint]


def _to_cisd_candles(bars: List[OHLCV]) -> List[CISDScorerCandle]:
    return [
        CISDScorerCandle(ts=b.ts, o=b.o, h=b.h, l=b.l, c=b.c, v=b.v)
        for b in bars
    ]


def _to_ohlcv_bars(bars: List[OHLCV]) -> List[OHLCVBar]:
    return [
        OHLCVBar(
            time=b.ts // 1000,
            open=b.o,
            high=b.h,
            low=b.l,
            close=b.c,
            volume=b.v,
        )
        for b in bars
    ]


@router.get("/ohlcv", response_model=OHLCVResponse)
async def get_ohlcv(
    symbol: str = Query(..., min_length=1, pattern=r"^[A-Za-z0-9_\-\.]+$", description="Trading pair, e.g. BTCUSDT"),
    timeframe: str = Query("1h", description="Candle timeframe"),
    bars: int = Query(300, ge=10, le=1000, description="Number of candles to fetch"),
):
    if timeframe not in _TF_OPTIONS:
        return OHLCVResponse(symbol=symbol, timeframe=timeframe, bars=[])

    try:
        raw = await asyncio.to_thread(BybitDataFeed.fetch, symbol, bars, timeframe)
    except Exception as exc:
        logger.warning("Bybit fetch failed for %s %s: %s", symbol, timeframe, exc)
        return OHLCVResponse(symbol=symbol, timeframe=timeframe, bars=[])

    return OHLCVResponse(
        symbol=symbol,
        timeframe=timeframe,
        bars=_to_ohlcv_bars(raw),
    )


@router.get("/indicators", response_model=IndicatorsResponse)
async def get_indicators(
    symbol: str = Query(..., min_length=1, pattern=r"^[A-Za-z0-9_\-\.]+$", description="Trading pair, e.g. BTCUSDT"),
    timeframe: str = Query("1h", description="Candle timeframe"),
    bars: int = Query(300, ge=50, le=1000, description="Number of candles to fetch"),
):
    if timeframe not in _TF_OPTIONS:
        return IndicatorsResponse(symbol=symbol, timeframe=timeframe, indicators=[])

    try:
        raw = await asyncio.to_thread(BybitDataFeed.fetch, symbol, bars, timeframe)
    except Exception as exc:
        logger.warning("Bybit fetch failed for %s %s: %s", symbol, timeframe, exc)
        return IndicatorsResponse(symbol=symbol, timeframe=timeframe, indicators=[])

    if len(raw) < 50:
        return IndicatorsResponse(symbol=symbol, timeframe=timeframe, indicators=[])

    cisd_candles = _to_cisd_candles(raw)
    # Use the same GA-optimized scorer weights as the signal generator
    scorer = CISDScorer(
        min_alignment=3,
        ob_atr_mul=0.798,
        ob_pivot=6,
        w_align_full=1,
        w_align_part=1,
        w_cisd=2,
        w_ob_touch=3,
        w_fvg_touch=2,
        w_vol_score=2,
        w_body_score=1,
        body_atr_mul=0.375,
        vol_mult=1.103,
        vol_period=20,
    )
    scores = scorer.score_series(cisd_candles)

    indicators = []
    for bar, score in zip(raw, scores):
        indicators.append(
            IndicatorPoint(
                time=bar.ts // 1000,
                confluence_score=round(float(score.get("confluence_score", 0)), 2),
                direction_hint=str(score.get("direction_hint", "NEUTRAL")),
                alignment_count=int(score.get("alignment_count", 0)),
            )
        )

    return IndicatorsResponse(
        symbol=symbol,
        timeframe=timeframe,
        indicators=indicators,
    )
