"""API endpoints for strategy management and switching."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.strategy import (
    StrategyConfig,
    StrategySmokeRequest,
    StrategySmokeResponse,
    StrategyStatusResponse,
    StrategySwitchRequest,
)
from app.services.strategy_engine import strategy_registry
from app.services.signal_generator import BybitDataFeed

router = APIRouter()


def _metadata_to_config(meta) -> StrategyConfig:
    return StrategyConfig(
        strategy_id=meta.strategy_id,
        name=meta.name,
        description=meta.description,
        strategy_type=meta.strategy_type,  # type: ignore[arg-type]
        timeframes=meta.timeframes,
        created_at=meta.created_at,
        updated_at=meta.updated_at,
    )


@router.get("", response_model=StrategyStatusResponse)
async def list_strategies():
    """List all registered strategies and active configuration."""
    configs = [_metadata_to_config(m) for m in strategy_registry.list_metadata()]
    return StrategyStatusResponse(
        active_strategy_id=strategy_registry.active_strategy_id,
        available_strategies=configs,
        last_switch=strategy_registry.last_switch,
        pattern_stats={},
    )


@router.get("/active", response_model=StrategyConfig)
async def get_active_strategy():
    """Return metadata for the currently active strategy."""
    strategy = strategy_registry.get_active_strategy()
    return _metadata_to_config(strategy.get_metadata())


@router.post("/switch")
async def switch_strategy(req: StrategySwitchRequest):
    """Switch the active strategy at runtime."""
    try:
        strategy_registry.set_active_strategy(req.strategy_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "success": True,
        "active_strategy_id": strategy_registry.active_strategy_id,
        "last_switch": strategy_registry.last_switch,
    }


@router.post("/{strategy_id}/backtest-smoke", response_model=StrategySmokeResponse)
async def backtest_smoke(strategy_id: str, req: StrategySmokeRequest | None = None):
    """
    Run a quick smoke-test of a strategy on the most recent bars.
    Does NOT persist anything — purely diagnostic.
    """
    if req is None:
        req = StrategySmokeRequest()

    try:
        strategy = strategy_registry.get(strategy_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        bars = BybitDataFeed.fetch(req.symbol, bars=req.bars, timeframe=req.timeframe)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}")

    if len(bars) < 20:
        raise HTTPException(status_code=422, detail="Insufficient bars for scoring")

    scores = strategy.score_bars(bars)
    signals = [s for s in scores if s.direction != "NEUTRAL" and s.confluence_score >= req.min_confluence]
    max_conf = max((s.confluence_score for s in scores), default=0.0)

    sample = [
        {
            "direction": s.direction,
            "confluence_score": s.confluence_score,
            "confidence": s.confidence,
            "metadata": s.metadata,
        }
        for s in scores[:5]
    ]

    return StrategySmokeResponse(
        strategy_id=strategy_id,
        symbol=req.symbol,
        timeframe=req.timeframe,
        bars_scored=len(scores),
        signals_generated=len(signals),
        max_confluence=round(max_conf, 2),
        sample_scores=sample,
    )
