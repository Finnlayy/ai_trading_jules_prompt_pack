"""API endpoints for chart pattern scanning and statistics."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.schemas.strategy import (
    PatternMatchSchema,
    PatternScanResponse,
    PatternStatsResponse,
)
from app.services.pattern_recognition import scan_bars, aggregate_pattern_score
from app.services.signal_generator import BybitDataFeed

router = APIRouter()

# In-memory stats (ephemeral; restart resets)
_pattern_scan_history: list[dict] = []


@router.get("/scan", response_model=PatternScanResponse)
async def scan_patterns(
    symbol: str = Query(default="BTCUSDT"),
    timeframe: str = Query(default="1h"),
    bars: int = Query(default=200, ge=20, le=2000),
):
    """
    Scan historical market data for classical chart patterns.
    """
    try:
        raw_bars = BybitDataFeed.fetch(symbol, bars=bars, timeframe=timeframe)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    if len(raw_bars) < 20:
        raise HTTPException(status_code=422, detail="Insufficient bars for pattern detection")

    matches = scan_bars(raw_bars)
    agg_score, dominant, avg_conf = aggregate_pattern_score(matches)

    _pattern_scan_history.append({
        "symbol": symbol,
        "timeframe": timeframe,
        "patterns": [m.pattern_type for m in matches],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return PatternScanResponse(
        symbol=symbol,
        timeframe=timeframe,
        bars_scanned=len(raw_bars),
        patterns_found=[
            PatternMatchSchema(
                pattern_type=m.pattern_type,
                direction=m.direction,  # type: ignore[arg-type]
                confidence=round(m.confidence, 3),
                start_idx=m.start_idx,
                end_idx=m.end_idx,
                neckline=m.neckline,
                target_price=m.target_price,
            )
            for m in matches
        ],
        aggregated_score=agg_score,
        dominant_pattern=dominant,
        avg_confidence=avg_conf if avg_conf is not None else 0.0,
    )


@router.get("/stats", response_model=PatternStatsResponse)
async def pattern_stats():
    """
    Return aggregated pattern detection statistics from recent scans.
    """
    counts: dict[str, int] = {}
    for entry in _pattern_scan_history:
        for pt in entry.get("patterns", []):
            counts[pt] = counts.get(pt, 0) + 1

    last_scan = None
    if _pattern_scan_history:
        last_scan = datetime.fromisoformat(_pattern_scan_history[-1]["timestamp"])

    return PatternStatsResponse(
        pattern_counts=counts,
        last_scan=last_scan,
        total_scans=len(_pattern_scan_history),
    )
